"""F2-BE bills derivations — per-field math functions.

Pure functions. No I/O. One function per derived field.
Called by bills_builder during sync.
"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from dataclasses import dataclass
from decimal import Decimal, localcontext
import calendar
import hashlib
import json
import re
from typing import Any, Literal

from budget_api.models.bills import CCSpendHistory, canonical_decimal
from budget_api.models.category_mappings import KPI_ROLES


@dataclass(frozen=True)
class MonthAcquisition:
    """Successful full-range fetch context, bound to the supplied collection."""

    month: str
    start_date: str
    end_date: str
    started_at: datetime
    transactions: list[dict]

    def valid_for(self, month: str, transactions: list[dict]) -> bool:
        first = _date.fromisoformat(month + "-01")
        last = f"{month}-{calendar.monthrange(first.year, first.month)[1]:02d}"
        return (self.month == month and self.start_date == month + "-01"
                and self.end_date == last and isinstance(self.started_at, datetime)
                and self.transactions is transactions and isinstance(transactions, list))


def exact_decimal_precision(values: list[Decimal]) -> int:
    """Precision sufficient for sums and two-factor products of these values."""
    if not values:
        return 28
    width = max(v.adjusted() for v in values) - min(v.as_tuple().exponent for v in values) + 1
    return max(28, 2 * max(width, 1) + len(str(len(values))) + 20)


def _source_id(value: Any) -> str:
    if type(value) is int and value > 0:
        return str(value)
    if isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value):
        return value
    raise ValueError("invalid source identity")


def _source_title(record: dict) -> str:
    title = record.get("title", "")
    if not isinstance(title, str):
        raise ValueError("invalid source label")
    return title


def compute_cc_spend_history(
    month: str,
    transactions: list[dict],
    account_mappings: dict,
    category_roles: dict,
    category_catalog: list[dict],
    account_catalog: list[dict],
    partner_id: str,
    partner_account_ids: set[str],
    cc_payment_category_id: int | None,
) -> CCSpendHistory:
    """Validate source inputs, then aggregate the canonical CC population."""
    if not isinstance(month, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}", month):
        raise ValueError("invalid source month")
    _date.fromisoformat(month + "-01")
    if (not isinstance(transactions, list) or not isinstance(account_mappings, dict)
            or not isinstance(category_roles, dict) or not isinstance(category_catalog, list)
            or not isinstance(account_catalog, list) or not isinstance(partner_account_ids, set)):
        raise ValueError("invalid source collection")
    partners = account_mappings.get("partners")
    accounts = account_mappings.get("accounts")
    if not isinstance(partners, dict) or not isinstance(accounts, dict):
        raise ValueError("invalid source ownership")
    for pid, partner in partners.items():
        if not isinstance(pid, str) or not pid.strip() or not isinstance(partner, dict):
            raise ValueError("invalid source ownership")
        if "label" in partner and not isinstance(partner["label"], str):
            raise ValueError("invalid source label")
    if not isinstance(partner_id, str) or partner_id not in partners:
        raise ValueError("invalid source partner")
    catalog_accounts = set()
    for record in account_catalog:
        if not isinstance(record, dict):
            raise ValueError("invalid source account")
        aid = _source_id(record.get("id"))
        if aid in catalog_accounts:
            raise ValueError("duplicate source account")
        catalog_accounts.add(aid)
    if not catalog_accounts.issubset(accounts):
        raise ValueError("unresolved catalog ownership")
    owned = set()
    cc_records = []
    eligible = set()
    for aid, record in accounts.items():
        if not isinstance(aid, str) or _source_id(aid) != aid or not isinstance(record, dict):
            raise ValueError("invalid source mapping")
        owner = record.get("partner_id")
        kind = record.get("type")
        excluded = record.get("excluded")
        valid_owner = isinstance(owner, str) and owner in partners
        valid_kind = isinstance(kind, str) and kind in {"cc", "checking", "savings"}
        # Excluded null bindings need no invented ownership/type.
        if (type(excluded) is not bool
                or not (valid_owner or (excluded and owner is None))
                or not (valid_kind or (excluded and kind is None))):
            raise ValueError("unresolved source ownership")
        if not excluded and aid not in catalog_accounts:
            raise ValueError("missing source account")
        if owner == partner_id:
            owned.add(aid)
            if kind == "cc":
                cc_records.append(dict(account_id=aid, partner_id=owner, type=kind, excluded=excluded))
                if not excluded:
                    eligible.add(aid)
    if owned != partner_account_ids:
        raise ValueError("inexact partner account set")
    excludes = set()
    for cid, role in category_roles.items():
        if not isinstance(role, str) or role not in KPI_ROLES:
            raise ValueError("invalid category role")
        # Only exclude keys shape population. Stray non-ID keys (e.g. synthetic
        # "uncategorized" from reports pipeline) with other roles are ignored.
        if role == "exclude":
            excludes.add(int(_source_id(cid)))
    payment = None if cc_payment_category_id is None else int(_source_id(cc_payment_category_id))
    titles = {}
    transfers = set()

    def visit(nodes):
        if not isinstance(nodes, list):
            raise ValueError("invalid category catalog")
        for node in nodes:
            if not isinstance(node, dict):
                raise ValueError("invalid category catalog")
            cid = int(_source_id(node.get("id")))
            if cid in titles:
                raise ValueError("duplicate source category")
            titles[cid] = _source_title(node)
            transfer = node.get("is_transfer", False)
            if type(transfer) is not bool:
                raise ValueError("invalid transfer flag")
            if transfer:
                transfers.add(cid)
            visit(node.get("children", []))

    visit(category_catalog)
    normalized = []
    embedded_titles: dict[int, set[str]] = {}
    for txn in transactions:
        if not isinstance(txn, dict):
            raise ValueError("invalid transaction")
        when = txn.get("date")
        if not isinstance(when, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", when):
            raise ValueError("invalid transaction date")
        _date.fromisoformat(when)
        if when[:7] != month:
            raise ValueError("transaction outside source month")
        amount = txn.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, (int, float, Decimal)):
            raise ValueError("invalid transaction amount")
        amount = Decimal(str(amount))
        if not amount.is_finite():
            raise ValueError("invalid transaction amount")
        if not isinstance(txn.get("status"), str) or txn["status"] not in {"posted", "pending"}:
            raise ValueError("invalid transaction status")
        account = txn.get("transaction_account")
        if not isinstance(account, dict):
            raise ValueError("missing transaction account")
        aid = _source_id(account.get("id"))
        if aid not in accounts or aid not in catalog_accounts:
            raise ValueError("unknown transaction account")
        category = txn.get("category")
        if category is not None and not isinstance(category, dict):
            raise ValueError("invalid transaction category")
        category = category or {}
        cid = None if category.get("id") is None else int(_source_id(category["id"]))
        title = _source_title(category)
        transfer = category.get("is_transfer", cid in transfers)
        if type(transfer) is not bool or transfer != (cid in transfers):
            raise ValueError("contradictory transfer context")
        if cid is not None and title:
            embedded_titles.setdefault(cid, set()).add(title)
        normalized.append(txn | {"amount": amount, "transaction_account": {"id": aid},
                                 "category": {"id": cid, "title": title, "is_transfer": transfer}})
    scope = {
        "version": "cc-spend-v1", "partner_id": partner_id,
        "owned_cc_accounts": sorted(cc_records, key=lambda r: r["account_id"]),
        "eligible_cc_account_ids": sorted(eligible),
        "cc_payment_category_id": payment, "exclude_category_ids": sorted(excludes),
        "transfer_category_ids": sorted(transfers),
        "policy": {"posted_outgoing_only": True, "positive_magnitude": True,
                   "refunds_netted": False, "parent_rollup": False, "uncategorized_separate": True},
    }
    digest = hashlib.sha256(json.dumps(scope, sort_keys=True, separators=(",", ":"),
                                       ensure_ascii=False).encode("utf-8")).hexdigest()
    totals: dict[int, Decimal] = {}
    with localcontext() as ctx:
        ctx.prec = exact_decimal_precision([t["amount"] for t in normalized])
        for txn, cid in _iter_real_cc_txns(normalized, account_mappings, partner_account_ids, payment, excludes):
            totals[cid] = totals.get(cid, Decimal(0)) + txn["amount"].copy_abs()
    uncategorized = totals.pop(-1, Decimal(0))
    categories = {
        str(cid): {"title": titles.get(cid) or min(embedded_titles.get(cid, {""})),
                   "amount": canonical_decimal(totals[cid])}
        for cid in sorted(totals, key=str)
    }
    return CCSpendHistory(status="complete", reason=None, scope_key="cc-spend-v1:" + digest,
                          categories=categories, uncategorized_amount=canonical_decimal(uncategorized))


def compute_salary(
    classified_events: list[dict[str, Any]],
    partner: str,
) -> float:
    """Sum of income events on bills account for this partner.

    Events are already classified (type=salary). Sum absolute amounts.
    """
    total = 0.0
    for event in classified_events:
        if event.get("type") == "salary" and event.get("partner") == partner:
            total += abs(event.get("amount", 0))
    return total


def compute_bills(
    classified_events: list[dict[str, Any]],
    partner: str,
) -> float:
    """Sum of bills-account spend events for this partner (absolute value)."""
    total = 0.0
    for event in classified_events:
        if event.get("type") == "bill" and event.get("partner") == partner:
            total += abs(event.get("amount", 0))
    return total


def compute_planned_cc_buys(
    classified_events: list[dict[str, Any]],
    partner: str,
) -> float:
    """Sum of buy-bucket events for this partner (planned CC purchases).

    Distinct from `estimated_cc_bill` / `real_cc_bill`, which are the
    REALIZED card spend. Used by the Budget zone (event-driven envelope):
    budget = salary - planned_bills - planned_cc_buys.
    """
    total = 0.0
    for event in classified_events:
        if event.get("type") == "buy" and event.get("partner") == partner:
            total += abs(event.get("amount", 0))
    return total


def compute_everyday_budget(
    next_salary: float,
    next_bills: float,
    cc_buys: float,
) -> float:
    """Everyday budget for month m = salary(m+1) − bills(m+1) − ccBuys(m).

    CC spending allowance for month m, funded by next month's income
    (the CC bill is paid next month). The buys term is month m's OWN
    scheduled buy envelopes — that card spend lands on the bill paid
    from m+1's salary. Same formula for all month kinds.
    Negative stays negative — honest signal, no clamping.
    Caller returns None when m+1 data doesn't exist (last window month).
    """
    return next_salary - next_bills - cc_buys


def compute_savings_balance_current(
    partner_id: str,
    account_mappings: dict[str, Any],
    account_catalog: list[dict[str, Any]],
) -> float | None:
    """Sum of current_balance for partner's bills + savings accounts.

    Returns None when partner has no bills (checking) account mapped —
    caller decides fallback (lag model). Never returns 0.0 for "missing":
    an empty savings list is a legitimate partner state, bills balance
    alone is returned.

    Pure function — reads only the in-memory catalog passed in.
    """
    accounts = account_mappings.get("accounts", {})
    # inline lookup — bills = checking, plus all savings (builder helpers stay private)
    bills_id: int | None = None
    savings_ids: list[int] = []
    for account_id, mapping in accounts.items():
        if mapping.get("partner_id") != partner_id or mapping.get("excluded", True):
            continue
        if mapping.get("type") == "checking" and bills_id is None:
            bills_id = int(account_id)
        elif mapping.get("type") == "savings":
            savings_ids.append(int(account_id))
    if bills_id is None:
        return None

    def _balance(account_id: int) -> float:
        # same read as builder._account_balance — missing account = 0.0
        for account in account_catalog:
            if account.get("id") == account_id:
                return float(account.get("current_balance", 0))
        return 0.0

    return _balance(bills_id) + sum(_balance(sid) for sid in savings_ids)


def compute_savings_balance_past(
    prior_balance: float,
    target_month: str,
    deltas_per_month: dict[str, float],
) -> float:
    """Back-walk one step: target month's balance from the month after it.

    `prior_balance` = balance of the month immediately AFTER target_month.
    Returns prior_balance - deltas_per_month[target_month].
    Target month key MUST be present — caller checks.
    """
    return prior_balance - deltas_per_month[target_month]


def _posted_cc_spend(
    transactions: list[dict[str, Any]],
    accounts: dict[str, Any],
    partner_set: set[str] | None,
    cc_payment_category_id: int | None,
) -> float:
    """Abs-sum of posted CC-account DEBITS. CC-paydown category excluded —
    cash moving checking→card, not card spend. Credits/refunds (positive
    amounts) skipped — abs() would turn a refund into extra spend."""
    cc_spend = 0.0
    for txn in transactions:
        txn_account = txn.get("transaction_account", {})
        account_id = str(txn_account.get("id", ""))
        if partner_set is not None and account_id not in partner_set:
            continue
        mapping = accounts.get(account_id, {})
        if mapping.get("type") == "cc" and not mapping.get("excluded", True):
            if txn.get("status") != "posted":
                continue
            amount = txn.get("amount", 0)
            if amount >= 0:
                continue  # refund/credit — not spend
            if cc_payment_category_id is not None:
                txn_cat_id = (txn.get("category") or {}).get("id")
                if txn_cat_id == cc_payment_category_id:
                    continue
            cc_spend += abs(amount)
    return cc_spend


def compute_estimated_cc_bill(
    partner: str,
    transactions: list[dict[str, Any]],
    events: list[dict[str, Any]],
    account_mappings: dict[str, Any],
    account_catalog: list[dict[str, Any]] | None = None,
    partner_account_ids: set[str] | None = None,
    cc_payment_category_id: int | None = None,
    *,
    month_kind: Literal["current", "future"] = "future",
    today: _date | None = None,
) -> float:
    """Estimated CC bill — envelope model (F2 §9 revised, grill-me round 6).

    NOTE (wiring, corrected 2026-09-18): the builder calls this with
    month_kind="current" for month m+1, passing MONTH M's data — posted-
    so-far(m) + remaining envelope(m) IS the statement paid in m+1.
    "future" is only the past-month back-compat path. The current month
    m's estimate moved to `compute_future_estimated_cc_bill` (the m−1
    proxy = the statement being paid this month); m+2+ uses
    `compute_scheduled_cc_bill`.

    Caller passes the RIGHT month's data per kind:
    - `future` month m: `transactions` = posted CC txns of month m−1.
      Estimated = posted CC spend of m−1. Events ignored entirely.
    - `current`: `transactions` = THIS month's posted CC txns (posted-so-far),
      `events` = this month's raw events. Estimated = posted-so-far +
      remaining envelope (abs amounts of CC-account events dated > today).
      Events dated <= today: ignored — posted-so-far already carries reality.

    `account_catalog` translates real PS event shape (scenario.account_id)
    into transaction_account.id the mappings use.
    `partner_account_ids` restricts to this partner's accounts only.
    Without it, the result includes both partners (caller mistake).
    `cc_payment_category_id` excludes the bills-side of a CC paydown
    (category "CC Payment (paired)") from `cc_spend` — those are cash
    transfers from checking, not card spend.
    """
    from budget_api.services.bills_classifier import resolve_event_account_id

    accounts = account_mappings.get("accounts", {})
    partner_set = partner_account_ids  # may be None → caller-side bug

    cc_spend = _posted_cc_spend(
        transactions, accounts, partner_set, cc_payment_category_id
    )

    if month_kind == "future":
        # Envelope model: future = prior posted spend only. No events leg.
        return cc_spend

    # Current month: + remaining envelope (future-dated CC-account events).
    if today is None:
        today = _date.today()
    today_str = today.isoformat()
    remaining_envelope = 0.0
    for event in events:
        if event.get("date", "") > today_str:
            account_id = resolve_event_account_id(event, account_catalog)
            if partner_set is not None and account_id not in partner_set:
                continue
            mapping = accounts.get(account_id, {})
            if mapping.get("type") == "cc" and not mapping.get("excluded", True):
                remaining_envelope += abs(event.get("amount", 0))

    return cc_spend + remaining_envelope


def compute_future_estimated_cc_bill(
    partner: str,
    prior_classified_buys: list[dict[str, Any]],
    prior_transactions: list[dict[str, Any]],
    account_mappings: dict[str, Any],
    partner_account_ids: set[str] | None = None,
    cc_payment_category_id: int | None = None,
) -> float:
    """Estimated CC bill from month m−1 data — per-category max formula.

    Per user formula (2026-08-30): per buy-envelope category, count the
    LARGER of the scheduled event vs real posted spend; plus all posted
    spend in categories with no envelope. Equivalent to
    buys(m−1) − matched(m−1) + free(m−1), but per-category max is robust
    to the "tiny event covers huge real spend" trap (a 30-kr envelope
    never erases 6,000 of real spend in that category).

    Wiring (user model 2026-09-15): the builder uses this for the CURRENT
    month m — m−1's data is the statement being paid this month. Future
    months moved to `compute_estimated_cc_bill` (m+1 envelope model) and
    `compute_scheduled_cc_bill` (m+2+ envelopes only).

    `prior_classified_buys` = m−1's classified events filtered to
    type=="buy" for this partner (CC-payment category excluded by caller).
    Posted-spend filter: posted-only, debits only, partner's non-excluded
    CC accounts, no CC-paydown category, no transfers.
    """
    # Envelope per category title (m−1's own events).
    envelope: dict[str, float] = {}
    for e in prior_classified_buys:
        title = (e.get("category") or {}).get("title") or "Uncategorized"
        envelope[title] = envelope.get(title, 0.0) + abs(e.get("amount", 0))

    # Real posted CC spend per category title (m−1). Debits only —
    # refunds/credits are not spend (PR65 review).
    accounts = account_mappings.get("accounts", {})
    real: dict[str, float] = {}
    for txn in prior_transactions:
        if txn.get("status") != "posted":
            continue
        if txn.get("amount", 0) >= 0:
            continue
        txn_account = txn.get("transaction_account", {}) or {}
        account_id = str(txn_account.get("id", ""))
        if partner_account_ids is not None and account_id not in partner_account_ids:
            continue
        mapping = accounts.get(account_id, {})
        if mapping.get("type") != "cc" or mapping.get("excluded", True):
            continue
        category = txn.get("category") or {}
        if (
            cc_payment_category_id is not None
            and category.get("id") == cc_payment_category_id
        ):
            continue
        if category.get("is_transfer", False):
            continue
        title = category.get("title") or "Uncategorized"
        real[title] = real.get(title, 0.0) + abs(txn.get("amount", 0))

    # Per-category max (envelope-covered) + plain sum (no envelope).
    total = 0.0
    for title in set(envelope) | set(real):
        total += max(envelope.get(title, 0.0), real.get(title, 0.0))
    return total


def compute_scheduled_cc_bill(
    partner: str,
    classified_buys: list[dict[str, Any]],
) -> float:
    """Estimated CC bill for m+2 and later — scheduled buy envelopes only.

    User model (2026-09-15): months beyond m+1 have no posted data and no
    reliable baseline, so the estimate is purely the month's own scheduled
    buys. Equivalent to `compute_future_estimated_cc_bill` with an empty
    real leg: plain abs-sum of the envelopes, no per-category pairing.

    `classified_buys` = the month's classified events filtered to
    type=="buy" for this partner (CC-payment category excluded by caller).
    """
    return sum(abs(e.get("amount", 0)) for e in classified_buys)


def compute_real_cc_bill(
    partner: str,
    transactions: list[dict[str, Any]],
    account_mappings: dict[str, Any],
    cc_payment_category_id: int,
    partner_account_ids: set[str] | None = None,
) -> float:
    """Real CC bill (past months) = sum of CC-payment transactions on this
    partner's CC account.

    The CC-side of a CC paydown — the amount actually charged to the
    card (positive in PS). NOT the bills-side (cash leaving checking):
    that's the paydown transfer, not the bill itself.

    `partner_account_ids` restricts to this partner's accounts only. Without
    it, the result includes both partners.
    """
    accounts = account_mappings.get("accounts", {})
    partner_set = partner_account_ids
    total = 0.0
    for txn in transactions:
        txn_account = txn.get("transaction_account", {})
        account_id = str(txn_account.get("id", ""))
        if partner_set is not None and account_id not in partner_set:
            continue
        mapping = accounts.get(account_id, {})
        if mapping.get("type") != "cc":
            continue
        if mapping.get("excluded", True):
            continue
        # PS can send category=null — .get default won't fire on explicit None
        category = txn.get("category") or {}
        if category.get("id") == cc_payment_category_id:
            total += abs(txn.get("amount", 0))
    return total


def compute_current_cc_bill_posted(
    partner: str,
    transactions: list[dict[str, Any]],
    account_mappings: dict[str, Any],
    cc_payment_category_id: int,
    partner_account_ids: set[str] | None = None,
) -> float:
    """Real CC paydown posted THIS month on any of this partner's accounts.

    The checking-side payment outflow (negative on a non-excluded checking
    account, CC-payment category) is ground truth for the current month: it
    catches unscheduled eFaktura/eRegning paydowns that have no scheduled
    event. Distinct from `compute_real_cc_bill` (past months), which sums the
    positive CC-side charge on the card account.

    Both legs of a paired payment carry the CC-payment category in PS —
    the negative checking leg and the positive card leg. Restricting to
    checking accounts AND negative amounts avoids double-counting the
    pair and excludes positive reversals (refunds of a payment).

    `partner_account_ids` restricts to this partner's accounts only.
    Returns 0.0 when nothing posted yet — caller treats that as
    "no posted paydown; keep the scheduled-event value".
    """
    accounts = account_mappings.get("accounts", {})
    total = 0.0
    for txn in transactions:
        txn_account = txn.get("transaction_account", {}) or {}
        account_id = str(txn_account.get("id", ""))
        if partner_account_ids is not None and account_id not in partner_account_ids:
            continue
        if txn.get("status") != "posted":
            continue
        mapping = accounts.get(account_id, {})
        if mapping.get("type") != "checking" or mapping.get("excluded", True):
            continue
        # PS can send category=null — .get default won't fire on explicit None
        category = txn.get("category") or {}
        if category.get("id") != cc_payment_category_id:
            continue
        amount = txn.get("amount", 0)
        if amount >= 0:
            continue
        total += abs(amount)
    return total


# -- compute_real_cc_spend + compute_cc_usage -------------------------------
#
# cc_usage = per-partner TOTAL real posted CC card spend (2026-08-28
# decision: capsule fill shows total, not per-category overage — planned
# portion of spend must stay visible). Real = posted CC txns on partner's
# CC accounts (excl. CC-paydown, transfers, exclude-role). No flooring,
# no planned subtraction. Returns None when no real CC txns in window
# (past months with no card activity render as None, not a misleading 0).


def _iter_real_cc_txns(
    transactions: list[dict[str, Any]],
    account_mappings: dict[str, Any],
    partner_account_ids: set[str] | None,
    cc_payment_category_id: int | None,
    exclude_category_ids: set[int] | None,
):
    """Yield (txn, category_id) for txns passing the shared CC-spend filters.

    Single source of truth for the cc_usage / cc_usage_by_category
    population: posted txns on partner's non-excluded CC accounts,
    excluding CC-paydown category, is_transfer=true and exclude-role ids.
    Non-negative amounts (refunds/credits) are not spend — skipped here,
    consistent with `_posted_cc_spend` (PR65 review).
    `partner_account_ids` None → all CC accounts (legacy path).
    """
    accounts = account_mappings.get("accounts", {})
    for txn in transactions:
        if txn.get("status") != "posted":
            continue
        if txn.get("amount", 0) >= 0:
            continue  # refund/credit — not card spend
        txn_account = txn.get("transaction_account", {}) or {}
        account_id = str(txn_account.get("id", ""))
        if partner_account_ids is not None and account_id not in partner_account_ids:
            continue
        mapping = accounts.get(account_id, {})
        if mapping.get("type") != "cc":
            continue
        if mapping.get("excluded", True):
            continue
        category = txn.get("category", {}) or {}
        cat_id = category.get("id")
        if cat_id is None:
            # Uncategorized posted CC spend still counts (PR65 review:
            # the future-estimate path keys it under "Uncategorized" —
            # dropping it here broke the est-vs-usage population parity
            # and the sum-invariant). Sentinel id −1; title fallback
            # emits the "Uncategorized" key downstream.
            cat_id = -1
        # Skip CC-paydown category (cash to card, not card spend).
        if cc_payment_category_id is not None and cat_id == cc_payment_category_id:
            continue
        # Skip transfer categories (own-account moves).
        if category.get("is_transfer", False):
            continue
        # Skip exclude-role category ids (KPI noise).
        if exclude_category_ids and cat_id in exclude_category_ids:
            continue
        yield txn, cat_id


def compute_real_cc_spend(
    partner: str,
    transactions: list[dict[str, Any]],
    account_mappings: dict[str, Any],
    partner_account_ids: set[str] | None,
    cc_payment_category_id: int | None,
    exclude_category_ids: set[int] | None = None,
) -> dict[int, float]:
    """Real CC spend per category, per partner, in window.

    Returns {category_id: abs_total_spend} for posted txns on partner's
    non-excluded CC accounts. Excludes CC-payment category (paydown leg),
    is_transfer=true, and exclude-role category ids.

    `partner_account_ids` restricts to this partner's accounts. None
    means caller forgot — function falls through and includes all CC
    accounts (existing behavior for the current-month-only path).
    """
    spend: dict[int, float] = {}
    for txn, cat_id in _iter_real_cc_txns(
        transactions,
        account_mappings,
        partner_account_ids,
        cc_payment_category_id,
        exclude_category_ids,
    ):
        spend[cat_id] = spend.get(cat_id, 0.0) + abs(txn.get("amount", 0))
    return spend


def compute_cc_usage_by_category(
    partner: str,
    transactions: list[dict[str, Any]],
    account_mappings: dict[str, Any],
    partner_account_ids: set[str] | None = None,
    cc_payment_category_id: int | None = None,
    exclude_category_ids: set[int] | None = None,
) -> dict[str, float] | None:
    """cc_usage_by_category = real posted CC spend keyed by category TITLE.

    Identical filters + population to compute_cc_usage (shares
    _iter_real_cc_txns): sum of values always equals the cc_usage total
    for the same inputs. Title comes from the txn's embedded category
    (same mapping snapshot events use, event.title = category.title);
    txns with a category id but no title fall back to str(id) so spend
    is never silently dropped.

    Returns None when no real CC txns in window — same gate as cc_usage
    (absence marker, not a misleading empty dict).
    """
    spend: dict[str, float] = {}
    for txn, cat_id in _iter_real_cc_txns(
        transactions,
        account_mappings,
        partner_account_ids,
        cc_payment_category_id,
        exclude_category_ids,
    ):
        category = txn.get("category") or {}
        title = category.get("title") or ("Uncategorized" if cat_id == -1 else str(cat_id))
        spend[title] = spend.get(title, 0.0) + abs(txn.get("amount", 0))
    # No real CC activity → None marks absence.
    if not spend:
        return None
    return spend


def compute_cc_usage(
    partner: str,
    transactions: list[dict[str, Any]],
    account_mappings: dict[str, Any],
    partner_account_ids: set[str] | None = None,
    cc_payment_category_id: int | None = None,
    exclude_category_ids: set[int] | None = None,
) -> float | None:
    """cc_usage = total real posted CC spend for the partner, in window.

    Real = `compute_real_cc_spend(partner, transactions, ...)` — posted
    CC txns on partner's non-excluded CC accounts (excl. CC-paydown,
    transfers, exclude-role). Returned as the raw total: no per-category
    flooring against planned buys. Planned portion stays visible in the
    capsule budget-zone fill.

    Returns None when no real CC txns in window so past months with no
    card activity don't render as a misleading 0.
    """
    real_spend = compute_real_cc_spend(
        partner,
        transactions,
        account_mappings,
        partner_account_ids,
        cc_payment_category_id,
        exclude_category_ids,
    )
    # No real CC activity → None marks absence.
    if not real_spend:
        return None
    return sum(real_spend.values())


def compute_budget_usage(
    partner: str,
    transactions: list[dict[str, Any]],
    account_mappings: dict[str, Any],
    cc_payment_category_id: int | None = None,
    partner_account_ids: set[str] | None = None,
) -> float:
    """Budget usage (current month) = spend on non-CC, non-savings, non-transfer accounts.

    Excludes CC-paydown transactions (is_cc_payment=true).
    `partner_account_ids` restricts to this partner's accounts. Without it,
    the result includes both partners (caller mistake — household leak).
    """
    accounts = account_mappings.get("accounts", {})
    total = 0.0
    for txn in transactions:
        if txn.get("status") != "posted":
            continue
        txn_account = txn.get("transaction_account", {})
        account_id = str(txn_account.get("id", ""))
        if partner_account_ids is not None and account_id not in partner_account_ids:
            continue
        mapping = accounts.get(account_id, {})

        # Only checking accounts.
        if mapping.get("type") != "checking":
            continue
        if mapping.get("excluded", True):
            continue

        # Exclude CC-paydown transactions.
        # PS can send category=null — .get default won't fire on explicit None
        if cc_payment_category_id is not None:
            category = txn.get("category") or {}
            if category.get("id") == cc_payment_category_id:
                continue

        # Exclude transfers.
        category = txn.get("category") or {}
        if category.get("is_transfer", False):
            continue

        # Only debits (negative amounts).
        amount = txn.get("amount", 0)
        if amount < 0:
            total += abs(amount)

    return total


def compute_real_bills(
    partner: str,
    transactions: list[dict[str, Any]],
    account_mappings: dict[str, Any],
    cc_payment_category_id: int | None,
    partner_account_ids: set[str] | None = None,
    exclude_category_ids: set[int] | None = None,
) -> float:
    """Real bills (past months) = sum of posted checking-account debits.

    The cash that left this partner's checking account for actual spend:
    - status=posted
    - account.type=checking, not excluded
    - category != cc_payment (cash moving to card = paydown transfer, not spend)
    - category not in exclude_category_ids (KPI role "exclude" — pure noise)
    - category.is_transfer != True (savings transfer, own-account moves)
    - amount < 0 (debit)

    `partner_account_ids` restricts to this partner's accounts. Without it,
    the result includes both partners (caller mistake).
    `exclude_category_ids` is the set of category ids where category_roles
    role == "exclude" (e.g. "Personal Transfer (Fixture A)" – pseudo-bills
    that aren't real spend). Builder derives this from category_roles.
    """
    accounts = account_mappings.get("accounts", {})
    total = 0.0
    for txn in transactions:
        if txn.get("status") != "posted":
            continue
        txn_account = txn.get("transaction_account", {})
        account_id = str(txn_account.get("id", ""))
        if partner_account_ids is not None and account_id not in partner_account_ids:
            continue
        mapping = accounts.get(account_id, {})
        if mapping.get("type") != "checking":
            continue
        if mapping.get("excluded", True):
            continue

        category = txn.get("category", {}) or {}
        cat_id = category.get("id")

        # Exclude CC-paydown (cash moving to card).
        if cc_payment_category_id is not None and cat_id == cc_payment_category_id:
            continue
        # Exclude exclude-role categories (per category_roles role=="exclude").
        if exclude_category_ids and cat_id in exclude_category_ids:
            continue
        # Exclude transfer categories.
        if category.get("is_transfer", False):
            continue

        amount = txn.get("amount", 0)
        if amount < 0:
            total += abs(amount)
    return total


def compute_net(
    salary: float,
    bills: float,
    estimated_cc_bill: float | None,
    real_cc_bill: float | None,
) -> float:
    """Net = salary - bills - cc_bill. Real bill wins when present —
    including a legit 0.0 (card paid in full). Estimate is the fallback
    for months with no realized bill yet (PR65 review: est-first ate
    real zeros)."""
    cc_bill = real_cc_bill if real_cc_bill is not None else estimated_cc_bill or 0
    return salary - bills - cc_bill


def compute_status(
    salary: float,
    bills: float,
    estimated_cc_bill: float | None,
    real_cc_bill: float | None,
    savings_balance: float,
) -> Literal["covered", "partial", "shortfall"]:
    """Status rule (unchanged from FE mock):
    covered   if salary - bills >= estCcBill
    partial   if + savings >= estCcBill
    shortfall otherwise
    """
    cc_bill = real_cc_bill if real_cc_bill is not None else estimated_cc_bill or 0
    if salary - bills >= cc_bill:
        return "covered"
    if salary - bills + savings_balance >= cc_bill:
        return "partial"
    return "shortfall"
