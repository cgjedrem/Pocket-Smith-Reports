"""F2-BE bills builder — orchestrates classifier + derivations into a snapshot.

Entry point: build_bills_snapshot(month, events, transactions, ...) -> dict.
Returns a dict validated against BillsSnapshot. Raises NoBillsAccountError on
hard failure. The sync runner catches per-month and appends warnings.

ensure_prior_month: reads disk cache for prior month, auto-fetches if missing.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from budget_api.models.bills import BillsSnapshot
from budget_api.services import bills_classifier, bills_derivations, storage
from budget_api.services.ps_client import PSClient, PSClientError


class NoBillsAccountError(Exception):
    """Partner has no bills/checking account mapped — bills snapshot cannot be built."""


# Per-step calculation log for past-month derivations.
# Append-only, file in data/private/ (gitignored), user can tail to inspect
# how the math unfolded. Set BILLS_CALC_LOG=0 to disable (default: enabled
# for past months only).
import os as _os

_CALC_LOG_PATH = Path("data/private/_bills_calc.log")
_CALC_LOG = logging.getLogger("bills.calc")
_CALC_LOG.setLevel(logging.INFO)
_CALC_LOG.propagate = False  # don't double-log via root
if not _CALC_LOG.handlers and _os.environ.get("BILLS_CALC_LOG", "1") != "0":
    try:
        _CALC_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _fh = logging.FileHandler(_CALC_LOG_PATH, mode="a", encoding="utf-8")
        _fh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        _CALC_LOG.addHandler(_fh)
    except OSError:
        # data/private/ may not exist in some test envs — silently skip.
        pass


def _calc_log(partner: str, month: str, message: str) -> None:
    """Append a labeled line to the calc log (no-op if handler disabled)."""
    _CALC_LOG.info(f"[{month}][{partner}] {message}")


def _month_label(month: str) -> str:
    """YYYY-MM → 'July 2026'."""
    year, m = map(int, month.split("-"))
    names = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    return f"{names[m - 1]} {year}"


def _current_month(today: date | None = None) -> str:
    """Current YYYY-MM in the server's local timezone.

    Why local: month-boundary classification (`is_past` / `is_current` /
    `is_future`) is a user-facing concept — what month the user is in
    *now*. Using UTC drifts up to ±1 day at the edges, so a user in a
    positive UTC offset would see next-month marked as `is_past` for the
    first few hours of their local day.

    `today` may be injected (tests) — None reads the real clock.
    """
    return (today or datetime.now().date()).strftime("%Y-%m")


def _month_flags(month: str, today: date | None = None) -> tuple[bool, bool, bool]:
    """Return (is_past, is_current, is_future) for the given month.

    `today` may be injected (tests) — None reads the real clock via
    `_current_month()` (kept call-arg-free so tests can stub it).
    """
    current = today.strftime("%Y-%m") if today is not None else _current_month()
    if month < current:
        return True, False, False
    if month > current:
        return False, False, True
    return False, True, False


def _bills_account_id(account_mappings: dict[str, Any], partner: str) -> int | None:
    """Find the checking account id for a partner. Returns None if not mapped."""
    accounts = account_mappings.get("accounts", {})
    for account_id, mapping in accounts.items():
        if (
            mapping.get("partner_id") == partner
            and mapping.get("type") == "checking"
            and not mapping.get("excluded", True)
        ):
            return int(account_id)
    return None


def _savings_account_ids(account_mappings: dict[str, Any], partner: str) -> list[int]:
    """Find all savings account ids for a partner."""
    accounts = account_mappings.get("accounts", {})
    result: list[int] = []
    for account_id, mapping in accounts.items():
        if (
            mapping.get("partner_id") == partner
            and mapping.get("type") == "savings"
            and not mapping.get("excluded", True)
        ):
            result.append(int(account_id))
    return result


def _cc_account_ids(account_mappings: dict[str, Any], partner: str) -> list[int]:
    """Find all CC account ids for a partner."""
    accounts = account_mappings.get("accounts", {})
    result: list[int] = []
    for account_id, mapping in accounts.items():
        if (
            mapping.get("partner_id") == partner
            and mapping.get("type") == "cc"
            and not mapping.get("excluded", True)
        ):
            result.append(int(account_id))
    return result


def _account_balance(account_catalog: list[dict], account_id: int) -> float:
    """Read current_balance for an account from the catalog."""
    for account in account_catalog:
        if account.get("id") == account_id:
            return float(account.get("current_balance", 0))
    return 0.0


def _starting_balance(account_catalog: list[dict], account_id: int) -> float:
    """Read starting_balance for an account from the catalog."""
    for account in account_catalog:
        if account.get("id") == account_id:
            return float(account.get("starting_balance", 0))
    return 0.0


def _filter_posted(transactions: list[dict]) -> list[dict]:
    """Filter to status=posted only."""
    return [t for t in transactions if t.get("status") == "posted"]


def _partner_label(account_mappings: dict[str, Any], partner_id: str) -> str:
    """Get the human label for a partner."""
    partners = account_mappings.get("partners", {})
    return partners.get(partner_id, {}).get("label", partner_id)


def _all_partner_ids(account_mappings: dict[str, Any]) -> list[str]:
    """List all partner ids from mappings."""
    return list(account_mappings.get("partners", {}).keys())


def _partner_slot_map(account_mappings: dict[str, Any]) -> dict[str, str]:
    """Deterministic display slot per partner id: sorted ids → "a", "b".

    Identity-neutral ordering key — labels are user data and must never
    determine display order.

    The contract type is "a" | "b" | "" (client PartnerSlot union), so a
    third+ partner degrades to the neutral slot "" rather than inventing
    undocumented slots ("c", "d", ...). Rows still key on partner_id; ""
    renders with neutral styling, consistent with schema-4 payloads.
    """
    slots: dict[str, str] = {}
    for i, pid in enumerate(sorted(_all_partner_ids(account_mappings))):
        slots[pid] = chr(ord("a") + i) if i < 2 else ""
    return slots


def _partner_savings_category_id(
    account_mappings: dict[str, Any],
    partner_id: str,
) -> int | None:
    """Get the per-partner savings category id (None if not set)."""
    partner = account_mappings.get("partners", {}).get(partner_id, {})
    cat_id = partner.get("savings_category_id")
    return int(cat_id) if cat_id is not None else None


# CC-payment category id is resolved per-partner via _cc_payment_category_id
# (walks the PS category catalog for a child titled 'CC Payment (paired)').
# No module-level constant — id can drift if PS renames/restructures the tree.
# A None result means the partner has no CC-payment category in the catalog;
# the override is skipped (no fallback).


def _cc_payment_event_sum(
    events: list[dict[str, Any]],
    partner_id: str,
    account_mappings: dict[str, Any],
    account_catalog: list[dict[str, Any]],
    cat_id: int | None,
) -> float:
    """Sum of CC-payment events for this partner (absolute total).

    Walks the raw `events` list — NOT the classified list. Reason: a
    CC-payment event on a checking account with `is_transfer: True` is
    classified as "excluded" and dropped before reaching `classified`,
    so the safety-net override would never fire for the very case it
    is meant to catch (CC paydown cash leaving checking). Scans raw
    events filtered by (account ∈ partner's accounts) AND
    (category.id == cat_id) — includes events the classifier would
    drop on the is_transfer rule.

    Returns 0.0 if `cat_id` is None (helper couldn't resolve the
    CC-payment category in the catalog) or no events match. Caller
    must treat 0.0 as "no override, fall back to prior-month proxy".
    """
    if cat_id is None:
        return 0.0
    accounts = account_mappings.get("accounts", {})
    partner_account_ids: set[str] = {
        acct_id
        for acct_id, mapping in accounts.items()
        if mapping.get("partner_id") == partner_id
    }
    total = 0.0
    for event in events:
        event_acct_id = bills_classifier.resolve_event_account_id(
            event, account_catalog
        )
        if event_acct_id not in partner_account_ids:
            continue
        category = event.get("category") or {}
        if category.get("id") != cat_id:
            continue
        # Include regardless of is_transfer — see docstring.
        total += abs(event.get("amount", 0))
    return total


def _account_end_balance_from_raw(
    account_id: int,
    month: str,
    account_mappings: dict[str, Any],
    account_catalog: list[dict],
    posted_txns: list[dict],
    later_txns: list[dict] | None = None,
) -> float:
    """End-of-month balance for `account_id`.

    DEAD CODE as of savings-anchor change — past savings_balance now
    back-walks from live combined. Kept awaiting user OK to delete.

    Walk backwards from `current_balance` (end-of-today) by subtracting
    every transaction that occurred AFTER the target month. `later_txns`
    carries the cross-month cache (caller collects from disk). `posted_txns`
    is the target month's txns. Tests can pass later_txns=[] to keep
    isolation.

    Fallback (no later months synced): `month` is the last past month on
    disk. `current_balance` is end-of-today, polluted by post-month
    activity. Subtract this-month posted txns on this account to recover
    the real end-of-month.
    """
    current = _account_balance(account_catalog, account_id)
    target_year_month = month

    if later_txns is None:
        # Production path — read disk (filtered to months > target).
        later_txns = _load_later_months_txns(target_year_month)

    post_total = 0.0
    if later_txns:
        for t in later_txns:
            if str((t.get("transaction_account") or {}).get("id", "")) != str(
                account_id
            ):
                continue
            post_total += t.get("amount", 0)
        return current - post_total

    # Fallback: no later months synced. Last past month on disk — current
    # baseline is end-of-today, polluted by post-month activity. Subtract
    # this-month posted txns on this account to get a real end-of-month.
    target_prefix = f"{month}-"
    month_total = 0.0
    for txn in posted_txns:
        if str((txn.get("transaction_account") or {}).get("id", "")) != str(account_id):
            continue
        if not (txn.get("date", "")).startswith(target_prefix):
            continue
        month_total += txn.get("amount", 0)
    return current - month_total


def _load_later_months_txns(
    target_year_month: str,
    inclusive: bool = False,
) -> list[dict]:
    """Read every *_ps_raw.json on disk for months > (or >=) target.

    Used by the backward-walk balance math. Returned flat list (not
    per-month) so callers can filter by account_id once.
    """
    out: list[dict] = []
    for later_path in sorted(storage.PRIVATE_DATA_DIR.glob("*_ps_raw.json")):
        fname = later_path.name
        if not fname.endswith("_ps_raw.json"):
            continue
        m = fname[:7]
        if inclusive:
            if m < target_year_month:
                continue
        else:
            if m <= target_year_month:
                continue
        try:
            out.extend(storage.read_json(later_path) or [])
        except (json.JSONDecodeError, OSError):
            continue
    return out


def _past_month_cash_flow(
    posted_txns: list[dict],
    month: str,
    partner_acct_ids: set[str],
) -> float:
    """Real net cash flow on the given accounts during month.

    Sum of posted txns dated in `month` on the given accounts. Shared by
    build_bills_snapshot + build_bills_chain.
    SPLIT (2026-08-28): called with savings-account ids ONLY for the
    displayed savings_delta field. The chain's internal back-walk deltas
    (build_bills_chain) stay combined bills+savings so the invariant
    balance[m+1] = balance[m] + delta[m] holds for the combined balances.
    """
    target_prefix = f"{month}-"
    return sum(
        t.get("amount", 0)
        for t in posted_txns
        if (t.get("date", "")).startswith(target_prefix)
        and str((t.get("transaction_account") or {}).get("id", "")) in partner_acct_ids
    )


def _back_walk_past_balances(
    anchor: float,
    deltas_per_month: dict[str, float],
) -> dict[str, float]:
    """Back-walk every past month from a current-month anchor.

    Walks `deltas_per_month` newest-first. Each step:
    balance[m] = balance[m+1] - delta[m]. Prior balance starts as `anchor`
    (the current month's live combined). Current month must NOT be a key.

    Returns dict[month, balance] for every past month.
    """
    balances: dict[str, float] = {}
    prior_balance = anchor
    for m in sorted(deltas_per_month, reverse=True):
        prior_balance = bills_derivations.compute_savings_balance_past(
            prior_balance, m, deltas_per_month
        )
        balances[m] = prior_balance
    return balances


def _prior_month_savings_balance(
    partner_label: str,
    month: str,
    account_mappings: dict[str, Any],
) -> float:
    """Read prior month's snapshot and return that partner's savings_balance.

    Used to chain future-month projections.
    """
    prior_month = _month_minus_one(month)
    path = storage.bills_dashboard_path(prior_month)
    if not path.exists():
        return 0.0
    try:
        snap = storage.read_json(path) or {}
    except (json.JSONDecodeError, OSError):
        return 0.0
    for p in snap.get("partners", []):
        if p.get("partner") == partner_label:
            return float(p.get("savings_balance", 0) or 0)
    return 0.0


def _prior_month_savings_delta(
    partner_label: str,
    month: str,
    account_mappings: dict[str, Any],
) -> float:
    """Read prior month's snapshot and return that partner's savings_delta.

    Mirrors _prior_month_savings_balance. Returns 0.0 if prior snapshot
    missing (caller-side bug or first-ever sync).
    """
    prior_month = _month_minus_one(month)
    path = storage.bills_dashboard_path(prior_month)
    if not path.exists():
        return 0.0
    try:
        snap = storage.read_json(path) or {}
    except (json.JSONDecodeError, OSError):
        return 0.0
    for p in snap.get("partners", []):
        if p.get("partner") == partner_label:
            return float(p.get("savings_delta", 0) or 0)
    return 0.0


def _cc_payment_category_id(
    account_mappings: dict[str, Any],
    category_catalog: list[dict],
    partner: str,
) -> int | None:
    """Find the CC payments category id for a partner.

    Walks the category tree for a child titled 'CC Payment (paired)' or similar.
    TBD — per ps-integration doc, confirm exact title per partner.
    For now, searches by title containing 'CC Payment'.
    """
    for category in category_catalog:
        title = (category.get("title") or "").lower()
        if "cc payment" in title:
            return category.get("id")
        for child in category.get("children", []):
            child_title = (child.get("title") or "").lower()
            if "cc payment" in child_title:
                return child.get("id")
    return None


def _month_minus_one(month: str) -> str:
    """YYYY-MM → previous month."""
    year, m = map(int, month.split("-"))
    if m == 1:
        return f"{year - 1}-12"
    return f"{year}-{m - 1:02d}"


def _month_plus_one(month: str) -> str:
    """YYYY-MM → next month."""
    year, m = map(int, month.split("-"))
    if m == 12:
        return f"{year + 1}-01"
    return f"{year}-{m + 1:02d}"


def _classify_partner_events(
    events: list[dict[str, Any]],
    partner_id: str,
    partner_label: str,
    partner_account_ids: set[str],
    account_mappings: dict[str, Any],
    category_roles: dict[str, Any],
    account_catalog: list[dict],
    partner_savings_cat_id: int | None,
    cc_payment_cat_id: int | None,
) -> list[dict[str, Any]]:
    """Classify events for one partner's accounts.

    Skips events on other partners' accounts + excluded buckets. Stamps
    partner, type, is_cc_payment on each kept event (new dict per event).
    Used for month m's own events and m+1's (everyday_budget inputs).
    """
    classified: list[dict[str, Any]] = []
    for event in events:
        # Skip events on other partners' accounts.
        # Real PS events use scenario.account_id (bank); helper translates
        # to transaction_account.id via account_catalog.
        event_acct_id = bills_classifier.resolve_event_account_id(
            event, account_catalog
        )
        if event_acct_id not in partner_account_ids:
            continue

        event_with_partner = dict(event)
        event_with_partner["partner"] = partner_label
        bucket = bills_classifier.classify_event(
            event,
            account_mappings,
            category_roles,
            account_catalog,
            partner_savings_cat_id,
        )
        if bucket == "excluded":
            continue
        event_with_partner["type"] = bucket
        event_with_partner["is_cc_payment"] = (
            bills_classifier.is_cc_payment(event, cc_payment_cat_id)
            if cc_payment_cat_id is not None
            else False
        )
        classified.append(event_with_partner)
    return classified


def _month_dates(month: str) -> tuple[str, str]:
    """Return (first_day, last_day) ISO dates for a YYYY-MM month."""
    import calendar

    year, month_number = map(int, month.split("-"))
    last_day = calendar.monthrange(year, month_number)[1]
    return f"{month}-01", f"{month}-{last_day:02d}"


def ensure_prior_month(
    client: PSClient,
    user_id: str,
    month: str,
    warnings: list[str],
) -> tuple[list[dict], list[dict]]:
    """Read prior-month PS data from disk cache, or auto-fetch if missing.

    Returns (prior_events, prior_transactions).
    Appends warning if auto-fetched.
    """
    prior_month = _month_minus_one(month)
    events_path = storage.PRIVATE_DATA_DIR / f"events_{prior_month}.json"
    txns_path = storage.monthly_ps_raw_path(prior_month)

    if events_path.exists() and txns_path.exists():
        prior_events = storage.read_json(events_path) or []
        prior_txns = storage.read_json(txns_path) or []
        return prior_events, prior_txns

    # Auto-fetch.
    start_date, end_date = _month_dates(prior_month)
    prior_events = client.get_events(user_id, start_date, end_date)
    prior_txns = client.get_transactions(user_id, start_date, end_date)

    storage.atomic_write_json(events_path, prior_events)
    storage.atomic_write_json(txns_path, prior_txns)
    warnings.append(f"Prior month {prior_month} auto-fetched during sync")

    return prior_events, prior_txns


def build_bills_snapshot(
    month: str,
    events: list[dict[str, Any]],
    transactions: list[dict[str, Any]],
    account_mappings: dict[str, Any],
    category_roles: dict[str, Any],
    category_catalog: list[dict],
    account_catalog: list[dict],
    prior_events: list[dict[str, Any]] | None = None,
    prior_transactions: list[dict[str, Any]] | None = None,
    next_events: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
    *,
    live_combined: dict[str, float | None] | None,
    deltas_per_month: dict[str, dict[str, float]] | None,
    prior_snapshot: dict[str, Any] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Build the bills dashboard snapshot dict for one month.

    `live_combined` maps partner_id -> live combined balance (anchor) or
    None when the live catalog is missing for that partner.
    `deltas_per_month` maps partner_id -> {past month: savings_delta}.
    Both are required kwargs — pass None explicitly for legacy behavior
    (lag model, no anchor). Chain callers pass real values.
    `prior_snapshot` = in-memory m-1 snapshot (chain build) — used by the
    lag model instead of the disk read so future months chain off
    just-built values, not stale disk.
    `next_events` = events for month m+1 (chain build) — feeds
    everyday_budget = salary(m+1) − bills(m+1) − ccBuys(m+1). None →
    everyday_budget = None (last window month / standalone call).
    `today` may be injected (tests) — None reads the real clock.

    Raises NoBillsAccountError if a partner has no checking account.
    Returns a dict validated against BillsSnapshot.
    """
    if warnings is None:
        warnings = []

    is_past, is_current, is_future = _month_flags(month, today)
    if is_past:
        _calc_log(
            "_build_",
            month,
            f"START month={month} events={len(events)} txns={len(transactions)}",
        )
    posted_txns = _filter_posted(transactions)

    # Warn on posted txns with null/missing category — PS sends explicit
    # null when a txn is uncategorized. Silent skip hides data-quality
    # issues; surface id+date+account so user can fix in PocketSmith.
    for t in posted_txns:
        cat = t.get("category")
        if cat is None:
            acct = t.get("transaction_account") or {}
            warnings.append(
                f"Uncategorized txn: id={t.get('id')} date={t.get('date')} "
                f"amount={t.get('amount')} account={acct.get('name', '?')} "
                f"— assign a category in PocketSmith"
            )

    partners_data: list[dict[str, Any]] = []
    all_events: list[dict[str, Any]] = []
    bills_count = 0
    buys_count = 0
    slot_map = _partner_slot_map(account_mappings)

    for partner_id in _all_partner_ids(account_mappings):
        partner_label = _partner_label(account_mappings, partner_id)
        partner_slot = slot_map[partner_id]

        # Find bills account.
        bills_acct_id = _bills_account_id(account_mappings, partner_id)
        if bills_acct_id is None:
            raise NoBillsAccountError(
                f"{partner_label} has no bills/checking account mapped"
            )

        # Find savings + CC accounts.
        savings_acct_ids = _savings_account_ids(account_mappings, partner_id)
        cc_acct_ids = _cc_account_ids(account_mappings, partner_id)
        cc_payment_cat_id = _cc_payment_category_id(
            account_mappings, category_catalog, partner_label
        )
        partner_savings_cat_id = _partner_savings_category_id(
            account_mappings, partner_id
        )

        # Classify events — ONLY events on this partner's accounts.
        partner_account_ids: set[str] = set()
        for acct_id, mapping in account_mappings.get("accounts", {}).items():
            if mapping.get("partner_id") == partner_id:
                partner_account_ids.add(str(acct_id))

        classified = _classify_partner_events(
            events,
            partner_id,
            partner_label,
            partner_account_ids,
            account_mappings,
            category_roles,
            account_catalog,
            partner_savings_cat_id,
            cc_payment_cat_id,
        )

        # Match scheduled buys.
        classified = bills_classifier.match_scheduled_buys(classified, posted_txns)

        # Compute derived fields.
        # Salary uses the full classified list. CC-payment events can
        # never be salary (category is_transfer), so no filter needed.
        salary = bills_derivations.compute_salary(classified, partner_label)
        # bills / planned_cc_buys exclude CC-payment events. The
        # classifier already drops them on checking accounts (is_transfer
        # rule), but on CC accounts the event lands in type="buy" —
        # without this filter, planned_cc_buys would double-count the
        # cash leaving checking AND the event that drives the override.
        # No recognized CC-payment category -> nothing to exclude
        # (same None-guard as the m+1 filter below).
        classified_no_ccpay = [
            e
            for e in classified
            if cc_payment_cat_id is None
            or (e.get("category") or {}).get("id") != cc_payment_cat_id
        ]
        bills = bills_derivations.compute_bills(classified_no_ccpay, partner_label)
        planned_cc_buys = bills_derivations.compute_planned_cc_buys(
            classified_no_ccpay, partner_label
        )

        # Everyday budget (F2 §8, corrected 2026-08-30): CC allowance for
        # month m = salary(m+1) − bills(m+1) − plannedCcBuys(m). Month m's
        # CC spend (incl. scheduled buys) is paid with m+1's income — the
        # buys term is THIS month's envelopes, not m+1's (that was the bug:
        # Sep showed Oct's 18,586 buy sum instead of Sep's own).
        # None when m+1 data missing (last window month) — FE hides zone.
        if next_events is None:
            everyday_budget: float | None = None
        else:
            next_classified = _classify_partner_events(
                next_events,
                partner_id,
                partner_label,
                partner_account_ids,
                account_mappings,
                category_roles,
                account_catalog,
                partner_savings_cat_id,
                cc_payment_cat_id,
            )
            # No recognized CC-payment category -> nothing to exclude.
            # (The old conjunction dropped EVERY event when the id was
            # None, making the budget salary-only — PR62 review.)
            next_no_ccpay = [
                e
                for e in next_classified
                if cc_payment_cat_id is None
                or (e.get("category") or {}).get("id") != cc_payment_cat_id
            ]
            everyday_budget = bills_derivations.compute_everyday_budget(
                bills_derivations.compute_salary(next_classified, partner_label),
                bills_derivations.compute_bills(next_no_ccpay, partner_label),
                planned_cc_buys,
            )

        # Scheduled savings from events (type=savings bucket — both legs of
        # the transfer pair land here, so divide by 2).
        scheduled_savings_events = sum(
            abs(e.get("amount", 0)) for e in classified if e.get("type") == "savings"
        )
        # Scheduled savings from posted transactions (real cash that moved).
        # Filter to the partner's savings category id only.
        scheduled_savings_txns = sum(
            abs(t.get("amount", 0))
            for t in posted_txns
            if (t.get("category") or {}).get("id") == partner_savings_cat_id
        )
        # Both legs of the transfer pair are in each sum (one positive, one
        # negative). The pair totals cancel by sign, but absolute-value sums
        # double-count. Use only the negative leg (cash out of bills) — that
        # IS the savings transfer amount. Equivalently: divide by 2.
        # Prefer posted txns (real money) when present; fall back to events
        # (only what's planned) for current/future months with no posted
        # transfers yet.
        if scheduled_savings_txns > 0:
            scheduled_savings = scheduled_savings_txns / 2
        else:
            scheduled_savings = scheduled_savings_events / 2

        # Savings transfer (kept for UI backward compat) = scheduled amount.
        savings_transfer = scheduled_savings

        # CC bill estimates per month kind (user model 2026-09-15).
        # Scheduled CC buys are budget envelopes, never matched to txns.
        # m (current): estimated = m−1 proxy — per envelope category,
        #   max(scheduled buy, real posted m−1 CC spend) + unenveloped
        #   m−1 spend. That IS the statement being paid this month.
        # m+1: estimated = posted-so-far(m) + remaining scheduled
        #   buys(m, future-dated) — month m's card activity IS the
        #   statement paid in m+1 (wiring corrected 2026-09-18: the old
        #   code read m+1's own data, which is empty pre-month-start and
        #   dropped e.g. a 9000 m-dated trip buy from the m+1 estimate).
        # m+2+: estimated = the month's own scheduled buy envelopes only;
        #   no posted data or reliable baseline exists this far out.
        # Past: cc_spend-only path (prior m−1 spend) for the back-compat
        #   field; real_cc_bill carries posted paydown truth.
        month_buys = [
            e
            for e in classified
            if e.get("type") == "buy"
            and (
                cc_payment_cat_id is None
                or (e.get("category") or {}).get("id") != cc_payment_cat_id
            )
        ]
        prior_buy_events = []
        if prior_events:
            prior_classified = _classify_partner_events(
                prior_events,
                partner_id,
                partner_label,
                partner_account_ids,
                account_mappings,
                category_roles,
                account_catalog,
                partner_savings_cat_id,
                cc_payment_cat_id,
            )
            prior_buy_events = [
                e
                for e in prior_classified
                if e.get("type") == "buy"
                and (
                    cc_payment_cat_id is None
                    or (e.get("category") or {}).get("id") != cc_payment_cat_id
                )
            ]
        if is_current:
            # m−1 max-formula (user 2026-08-30): per envelope category,
            # max(scheduled buy, real posted spend) — robust to tiny
            # events covering big real spend. No m−1 txns → real terms
            # are 0 and the envelopes carry the estimate.
            estimated_cc_bill = bills_derivations.compute_future_estimated_cc_bill(
                partner_label,
                prior_buy_events,
                _filter_posted(prior_transactions or []),
                account_mappings,
                partner_account_ids,
                cc_payment_cat_id,
            )
        elif month == _month_plus_one(_current_month(today)):
            # m+1: the statement PAID in m+1 is month m's card activity —
            # posted-so-far(m) + remaining envelope(m). Classified buy
            # events only — raw events would let a future-dated transfer
            # or exclude-role event on a CC account inflate the remaining
            # envelope (PR63 review).
            estimated_cc_bill = bills_derivations.compute_estimated_cc_bill(
                partner_label,
                _filter_posted(prior_transactions or []),
                prior_buy_events,
                account_mappings,
                account_catalog,
                partner_account_ids,
                cc_payment_cat_id,
                month_kind="current",
                today=today or datetime.now().date(),
            )
        elif is_future:
            # m+2 and beyond: scheduled buy envelopes only.
            estimated_cc_bill = bills_derivations.compute_scheduled_cc_bill(
                partner_label,
                month_buys,
            )
        else:
            # Past back-compat: m−1 posted CC spend proxy. Events ignored.
            estimated_cc_bill = bills_derivations.compute_estimated_cc_bill(
                partner_label,
                prior_transactions or [],
                prior_events or [],
                account_mappings,
                account_catalog,
                partner_account_ids,
                cc_payment_cat_id,
                month_kind="future",
            )
        if is_past:
            real_cc_bill = bills_derivations.compute_real_cc_bill(
                partner_label,
                posted_txns,
                account_mappings,
                cc_payment_cat_id or 0,
                partner_account_ids,
            )
        else:
            real_cc_bill = None

        # savings_planned — static plan, all month kinds.
        # salary - bills - cc_bill. Past uses real_cc_bill (posted),
        # current/future estimated_cc_bill (proxy). Mirror of the
        # compute_net past/current cc-bill pick. Compute AFTER the
        # current-month CC-payment override so the override value wins.
        # savings_delta — actual-so-far, per month kind. Savings-accounts-
        # ONLY posted flow for past AND current (checking never counts —
        # user decision 2026-08-28). Future: None (no reality yet).
        if is_past:
            cc_for_planned = (
                real_cc_bill
                if real_cc_bill is not None
                else (estimated_cc_bill or 0)
            )
            savings_planned = salary - bills - cc_for_planned

        # Savings balance — depends on month kind.
        if is_past:
            _calc_log(
                partner_label,
                month,
                f"=== past-month balance chain ===",
            )
            _calc_log(
                partner_label,
                month,
                f"  bills_acct_id={bills_acct_id} savings_acct_ids={savings_acct_ids}",
            )
            # Savings delta = real net cash flow on partner's SAVINGS
            # accounts ONLY (posted txns dated in-month). Checking noise
            # (salary timing, CC paydowns) never counts — user decision
            # 2026-08-28. NOTE: the chain's deltas_per_month (back-walk)
            # stays combined bills+savings — combined balances demand it.
            savings_delta = _past_month_cash_flow(
                posted_txns, month, set(map(str, savings_acct_ids))
            )

            # Balance: back-walk from live anchor when chain inputs given.
            partner_deltas = (deltas_per_month or {}).get(partner_id)
            anchor = (live_combined or {}).get(partner_id)
            if (
                partner_deltas is not None
                and anchor is not None
                and month in partner_deltas
            ):
                walked = _back_walk_past_balances(anchor, partner_deltas)
                savings_balance = walked[month]
                # log full step: balance[m] = balance[m+1] - delta[m]
                later = [k for k in sorted(partner_deltas) if k > month]
                next_balance = walked[later[0]] if later else anchor
                _calc_log(
                    partner_label,
                    month,
                    f"  => back-walk: balance[{month}] = next({next_balance:.2f}) - delta({partner_deltas[month]:.2f}) = {savings_balance:.2f}",
                )
            else:
                # Legacy lag fallback: prior snapshot balance + delta.
                # Silent when chain kwargs are None (caller opted out);
                # warn when chain inputs exist but this month has no data.
                prior_balance = _prior_month_savings_balance(
                    partner_label, month, account_mappings
                )
                prior_delta = _prior_month_savings_delta(
                    partner_label, month, account_mappings
                )
                savings_balance = prior_balance + prior_delta
                if deltas_per_month is not None:
                    warnings.append(
                        f"{partner_label} {month}: no live anchor/delta — lag fallback"
                    )
                _calc_log(
                    partner_label,
                    month,
                    f"  => lag fallback: {prior_balance:.2f} + {prior_delta:.2f} = {savings_balance:.2f}",
                )
            _calc_log(
                partner_label,
                month,
                f"  => savings_delta = sum(this-month posted txns on partner SAVINGS accounts only) = {savings_delta:.2f}",
            )
        elif is_current or is_future:
            # Current with live anchor: savings_balance = live combined.
            # Otherwise lag model: balance = prior.balance + prior.flow.
            # Flow term: prior savings_delta when real (past/current
            # prior), prior savings_planned when prior is future (delta
            # is null there). This month's own events affect savings_delta
            # (the flow) but not savings_balance (the stock).
            anchor = (live_combined or {}).get(partner_id)
            if is_current and anchor is not None:
                savings_balance = anchor
                _calc_log(
                    partner_label,
                    month,
                    f"  live_combined = {anchor:.2f} (anchor)",
                )
            else:
                # prior_snapshot (chain in-memory) beats disk read
                if prior_snapshot is not None:
                    prior_partner = next(
                        (
                            p
                            for p in prior_snapshot.get("partners", [])
                            if p.get("partner") == partner_label
                        ),
                        {},
                    )
                    prior_balance = float(prior_partner.get("savings_balance", 0) or 0)
                    # null delta (future prior) → fall back to its plan
                    prior_delta = prior_partner.get("savings_delta")
                    if prior_delta is None:
                        prior_delta = float(
                            prior_partner.get("savings_planned", 0) or 0
                        )
                    else:
                        prior_delta = float(prior_delta)
                else:
                    prior_balance = _prior_month_savings_balance(
                        partner_label, month, account_mappings
                    )
                    prior_delta = _prior_month_savings_delta(
                        partner_label, month, account_mappings
                    )
                savings_balance = prior_balance + prior_delta
                if is_current and live_combined is not None:
                    # anchor expected but missing — chain caller wants to know
                    warnings.append(
                        f"{partner_label} {month}: live balance unavailable — lag fallback"
                    )
            # CC-paydown override (current month only). Sets real_cc_bill
            # from paydown truth: a scheduled CC-paydown event mid-month
            # counts (the schedule knows what posted-so-far hasn't caught
            # up with), and an unscheduled eFaktura/eRegning outflow with
            # no paired event must land. Take the max — posted-so-far can
            # be mid-month incomplete; the schedule misses unscheduled
            # payments. estimated stays the m−1 proxy so plan-vs-actual
            # stays visible in the table. Must run BEFORE savings_planned
            # so real wins the cc_for_planned pick.
            if is_current:
                cc_pay_override = _cc_payment_event_sum(
                    events,
                    partner_id,
                    account_mappings,
                    account_catalog,
                    cc_payment_cat_id,
                )
                if cc_payment_cat_id is not None:
                    cc_posted = bills_derivations.compute_current_cc_bill_posted(
                        partner_label,
                        posted_txns,
                        account_mappings,
                        cc_payment_cat_id,
                        partner_account_ids
                        if partner_account_ids
                        else None,
                    )
                else:
                    cc_posted = 0.0
                cc_truth = max(cc_pay_override, cc_posted)
                if cc_truth > 0:
                    real_cc_bill = cc_truth
                    _calc_log(
                        partner_label,
                        month,
                        f"  CC truth: events({cc_pay_override:.2f}) "
                        f"vs posted({cc_posted:.2f}) -> real {cc_truth:.2f} "
                        f"(est stays m-1 proxy {estimated_cc_bill:.2f})",
                    )
            # savings_planned = salary - bills - cc_for_planned. Current
            # prefers the paydown truth (real) when a paydown landed;
            # otherwise the m−1 proxy (estimated). Future only has the
            # proxy. Mirrors the past-month pick (real ?? estimated).
            # Consistent with user mental model: "total bills" = bills + CC.
            cc_for_planned = (
                real_cc_bill
                if real_cc_bill is not None
                else (estimated_cc_bill or 0)
            )
            savings_planned = salary - (bills + cc_for_planned)
            _calc_log(
                partner_label,
                month,
                f"  savings_planned = salary({salary:.2f}) - bills({bills:.2f})"
                f" - cc({'real' if real_cc_bill is not None else 'est'}: "
                f"{cc_for_planned:.2f}) = {savings_planned:.2f}",
            )
            # savings_delta = actual-so-far on the SAVINGS accounts.
            # Current: signed sum of this-month posted txns on the
            # partner's savings accounts ONLY — checking noise (salary
            # timing, CC paydowns, overdraft recovery, reimbursements)
            # never pollutes savings (user decision 2026-08-28). Needs a
            # resolved savings account + chain kwargs for the current
            # month — absent either, honest None + warning (never a
            # silent 0, never plan posing as actual). Savings accounts
            # resolve fine but no txns posted → 0.0 is CORRECT (nothing
            # saved). Future: no reality exists → None.
            if is_current:
                cur_deltas = (deltas_per_month or {}).get(partner_id)
                if savings_acct_ids and cur_deltas is not None:
                    savings_delta = _past_month_cash_flow(
                        posted_txns, month, set(map(str, savings_acct_ids))
                    )
                    _calc_log(
                        partner_label,
                        month,
                        f"  savings_delta = sum(this-month posted txns on SAVINGS {savings_acct_ids}) = {savings_delta:.2f}",
                    )
                else:
                    savings_delta = None
                    warnings.append(
                        f"{partner_label} {month}: savings_delta unavailable "
                        f"(no savings accounts/chain kwargs) — null, not planned"
                    )
            else:
                savings_delta = None

        # CC usage — per-partner total real posted CC spend, per month.
        # Past + current months compute it.
        # Coerce None → 0 for FE compat (formatKr(null) would break).
        if is_past or is_current:
            exclude_cat_ids_cc: set[int] = {
                int(cat_id)
                for cat_id, role in category_roles.items()
                if role == "exclude"
            }
            try:
                cc_usage_val = bills_derivations.compute_cc_usage(
                    partner_label,
                    posted_txns,
                    account_mappings,
                    partner_account_ids,
                    cc_payment_cat_id,
                    exclude_cat_ids_cc,
                )
                # Per-category variant (keyed by category title) — same
                # filters/gate as cc_usage; stays None (unlike cc_usage,
                # not coerced) so FE can hide the free-budget section.
                cc_usage_by_category = bills_derivations.compute_cc_usage_by_category(
                    partner_label,
                    posted_txns,
                    account_mappings,
                    partner_account_ids,
                    cc_payment_cat_id,
                    exclude_cat_ids_cc,
                )
            except Exception:
                # Defensive: bad data in legacy snapshots must not break sync.
                cc_usage_val = None
                cc_usage_by_category = None
            cc_usage = cc_usage_val if cc_usage_val is not None else 0.0
        else:
            cc_usage = 0.0
            cc_usage_by_category = None
        budget_usage = (
            bills_derivations.compute_budget_usage(
                partner_label,
                posted_txns,
                account_mappings,
                cc_payment_cat_id,
                partner_account_ids,
            )
            if is_current
            else 0
        )

        # Real bills (past only) — actual spend on checking that left the
        # account for real bills, excluding CC-paydown transfers, transfer
        # categories, and exclude-role categories. Mirrors the planned row
        # for the planned-vs-actual comparison. None for current/future.
        if is_past:
            # Derive exclude-role category ids from category_roles in scope.
            exclude_cat_ids: set[int] = {
                int(cat_id)
                for cat_id, role in category_roles.items()
                if role == "exclude"
            }
            real_bills = bills_derivations.compute_real_bills(
                partner_label,
                posted_txns,
                account_mappings,
                cc_payment_cat_id,
                partner_account_ids,
                exclude_category_ids=exclude_cat_ids,
            )
        else:
            real_bills = None

        # Net + status.
        net = bills_derivations.compute_net(
            salary, bills, estimated_cc_bill, real_cc_bill
        )
        status = bills_derivations.compute_status(
            salary, bills, estimated_cc_bill, real_cc_bill, savings_balance
        )

        # Build event list for this partner.
        # Contract: title = category, account = scenario.title (bank name).
        partner_events: list[dict[str, Any]] = []
        for event in classified:
            partner_events.append(
                {
                    "id": str(event.get("id", "")),
                    "date": event.get("date", ""),
                    "day": (
                        int(event.get("date", "01")[-2:]) if event.get("date") else 1
                    ),
                    "title": event.get("category", {}).get("title", "Uncategorized"),
                    "type": event.get("type", "bill"),
                    "account": (event.get("scenario") or {}).get("title", "Unknown"),
                    "partner": partner_label,
                    "partner_id": partner_id,
                    "partner_slot": partner_slot,
                    "amount": event.get("amount", 0),
                    "is_cc_payment": event.get("is_cc_payment", False),
                    "is_matched": event.get("is_matched"),
                }
            )

        all_events.extend(partner_events)
        bills_count += sum(1 for e in partner_events if e["type"] == "bill")
        buys_count += sum(1 for e in partner_events if e["type"] == "buy")

        partners_data.append(
            {
                "planned_cc_buys": planned_cc_buys,
                "partner": partner_label,
                "partner_id": partner_id,
                "partner_slot": partner_slot,
                "salary": salary,
                "bills": bills,
                "everyday_budget": everyday_budget,
                "savings_transfer": savings_transfer,
                "savings_planned": savings_planned,
                "savings_delta": savings_delta,
                "savings_balance": savings_balance,
                "estimated_cc_bill": estimated_cc_bill,
                "real_cc_bill": real_cc_bill,
                "real_bills": real_bills,
                "cc_usage": cc_usage,
                "cc_usage_by_category": cc_usage_by_category,
                "budget_usage": budget_usage,
                "net": net,
                "status": status,
                "events": partner_events,
            }
        )

    snapshot = {
        "schema_version": 5,
        "month": month,
        "month_label": _month_label(month),
        "is_past": is_past,
        "is_current": is_current,
        "is_future": is_future,
        "synced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bills_count": bills_count,
        "buys_count": buys_count,
        "warnings": warnings,
        "partners": partners_data,
        "source_counts": {
            "ps_events_fetched": len(events),
            "ps_transactions_fetched": len(transactions),
            "events_kept_after_filter": len(all_events),
        },
    }

    # Validate against Pydantic model.
    BillsSnapshot.model_validate(snapshot)

    return snapshot


def build_bills_chain(
    months: list[str],
    events_per_month: dict[str, list[dict]],
    transactions_per_month: dict[str, list[dict]],
    account_mappings: dict[str, Any],
    category_roles: dict[str, Any],
    category_catalog: list[dict],
    account_catalog: list[dict],
    warnings: list[str] | None = None,
    today: date | None = None,
) -> dict[str, dict]:
    """Build the full savings chain in one pass. Caller writes to disk.

    Order: per-partner past deltas → live anchor → snapshots ascending
    (past back-walk from anchor, current = anchor, future = lag chained
    in-memory off the just-built prior snapshot).

    Months missing from events/transactions dicts are skipped with a
    warning (disk snapshot stays as-is). Returns {month: snapshot_dict}.
    `today` may be injected (tests) — None reads the real clock.
    """
    if warnings is None:
        warnings = []

    months_sorted = sorted(months)
    past_months = [m for m in months_sorted if _month_flags(m, today)[0]]

    # First pass per partner: live anchor + past-month deltas.
    live_combined: dict[str, float | None] = {}
    deltas_per_month: dict[str, dict[str, float]] = {}
    for partner_id in _all_partner_ids(account_mappings):
        partner_label = _partner_label(account_mappings, partner_id)
        anchor = bills_derivations.compute_savings_balance_current(
            partner_id, account_mappings, account_catalog
        )
        live_combined[partner_id] = anchor
        if anchor is None:
            warnings.append(
                f"{partner_label}: no live combined balance — lag fallback for chain"
            )
        else:
            _calc_log(partner_label, "chain", f"live_combined = {anchor:.2f}")

        bills_acct_id = _bills_account_id(account_mappings, partner_id)
        savings_acct_ids = _savings_account_ids(account_mappings, partner_id)
        partner_acct_ids = {str(bills_acct_id), *map(str, savings_acct_ids)}
        deltas: dict[str, float] = {}
        for m in past_months:
            txns = transactions_per_month.get(m)
            if txns is None:
                continue  # missing month warned in build loop below
            posted = _filter_posted(txns)
            deltas[m] = _past_month_cash_flow(posted, m, partner_acct_ids)
        deltas_per_month[partner_id] = deltas

    # Build ascending so future months lag off in-memory prior snapshots.
    # Snapshot the chain-wide seed warnings ONCE: build_bills_snapshot
    # appends month-specific warnings (e.g. uncategorized txns) into the
    # list it receives; if later snapshots seeded from the mutated shared
    # list, month N's warnings would leak into months > N.
    seed_warnings = list(warnings)
    snapshots: dict[str, dict] = {}
    for m in months_sorted:
        if m not in events_per_month or m not in transactions_per_month:
            warnings.append(f"{m}: no PS data in chain input — month skipped")
            continue

        prior_m = _month_minus_one(m)
        prior_events = events_per_month.get(prior_m)
        prior_txns = transactions_per_month.get(prior_m)
        if prior_events is None:
            # earliest month — disk cache fallback, never PS API
            path = storage.PRIVATE_DATA_DIR / f"events_{prior_m}.json"
            prior_events = (storage.read_json(path) or []) if path.exists() else []
        if prior_txns is None:
            path = storage.monthly_ps_raw_path(prior_m)
            prior_txns = (storage.read_json(path) or []) if path.exists() else []

        # per-month copy seeded from the immutable chain-wide warnings —
        # generated month-specific warnings accumulate into `warnings`
        # (sync status) but must not leak into later snapshots.
        month_warnings = list(seed_warnings)
        snapshots[m] = build_bills_snapshot(
            month=m,
            events=events_per_month[m],
            transactions=transactions_per_month[m],
            account_mappings=account_mappings,
            category_roles=category_roles,
            category_catalog=category_catalog,
            account_catalog=account_catalog,
            prior_events=prior_events,
            prior_transactions=prior_txns,
            next_events=events_per_month.get(_month_plus_one(m)),
            warnings=month_warnings,
            live_combined=live_combined,
            deltas_per_month=deltas_per_month,
            prior_snapshot=snapshots.get(prior_m),
            today=today,
        )
        for w in month_warnings:
            if w not in warnings:
                warnings.append(w)

    return snapshots
