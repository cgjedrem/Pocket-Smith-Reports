"""Re-sync July 2026 bills snapshot from disk cache.

Loads events + raw txns for 2026-07 + 2026-06 (m-1) from data/private/,
calls build_bills_snapshot, overwrites bills_dashboard_2026-07.json.
Prints the new cc_usage + supporting fields for validation.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from budget_api.services import storage  # noqa: E402
from budget_api.services.bills_builder import build_bills_snapshot  # noqa: E402

MONTH = "2026-07"
PRIOR = "2026-06"


def _load(path: Path) -> object:
    """Read JSON or warn-and-return None when missing."""
    if not path.exists():
        print(f"  WARN missing: {path.name}")
        return None
    return storage.read_json(path)


def main() -> None:
    # 1. Load target + prior data.
    events = _load(storage.PRIVATE_DATA_DIR / f"events_{MONTH}.json") or []
    txns = _load(storage.monthly_ps_raw_path(MONTH)) or []
    prior_events = _load(storage.PRIVATE_DATA_DIR / f"events_{PRIOR}.json")
    prior_txns = _load(storage.monthly_ps_raw_path(PRIOR))

    # Fallback: prior raw missing -> pull m-1 events list and accept None
    # for prior_transactions. Builder handles None gracefully.
    if prior_txns is None:
        prior_txns = []

    # 2. Load reference data.
    account_mappings = storage.read_json(storage.ACCOUNT_MAPPING_PATH) or {}
    category_roles = storage.read_json(storage.CATEGORY_ROLES_PATH) or {}
    cat_doc = storage.read_json(storage.CATEGORY_CATALOG_PATH) or {}
    category_catalog = cat_doc.get("categories", [])
    acct_doc = storage.read_json(storage.ACCOUNT_CATALOG_PATH) or {}
    account_catalog = acct_doc.get("accounts", [])

    print(f"Target month : {MONTH}")
    print(f"  events={len(events)}  txns={len(txns)}")
    print(f"Prior month  : {PRIOR}")
    print(
        f"  prior_events={len(prior_events) if isinstance(prior_events, list) else 'None'}  "
        f"prior_txns={len(prior_txns)}"
    )

    # 3. Build snapshot (legacy single-month — no chain anchor).
    snap = build_bills_snapshot(
        MONTH,
        events,
        txns,
        account_mappings,
        category_roles,
        category_catalog,
        account_catalog,
        prior_events=prior_events if isinstance(prior_events, list) else None,
        prior_transactions=prior_txns,
        warnings=[],
        live_combined=None,
        deltas_per_month=None,
    )

    # 4. Write.
    out_path = storage.bills_dashboard_path(MONTH)
    storage.atomic_write_json(out_path, snap)
    print(f"Wrote {out_path.name} (schema_version={snap['schema_version']})")

    # 5. Report per-partner.
    print()
    for p in snap["partners"]:
        print(
            f"[{p['partner']}] "
            f"cc_usage={p['cc_usage']:.2f}  "
            f"planned_cc_buys={p['planned_cc_buys']:.2f}  "
            f"real_cc_bill={p['real_cc_bill']}  "
            f"real_bills={p['real_bills']}"
        )

    # 6. Independent HelloFresh breakdown for Fixture A.
    #    Walk raw txns on Fixture A's CC accounts, isolate category 2100012,
    #    and compute overage vs planned buys for that category only.
    fxa_acct_ids = {
        aid
        for aid, m in account_mappings.get("accounts", {}).items()
        if m.get("partner_id") == "partner_a" and m.get("type") == "cc"
    }
    hellofresh_cat_id = 2100012
    hellofresh_real = 0.0
    card_b_hellofresh_real = 0.0
    other_cc_real_by_cat: dict[int, float] = {}
    for t in txns:
        if t.get("status") != "posted":
            continue
        acct = (t.get("transaction_account") or {}).get("id")
        if str(acct) not in fxa_acct_ids:
            continue
        cat = t.get("category") or {}
        cat_id = cat.get("id")
        if cat_id is None:
            continue
        if cat.get("is_transfer", False):
            continue
        # Skip exclude-role.
        if category_roles.get(str(cat_id)) == "exclude":
            continue
        amt = abs(t.get("amount", 0))
        if cat_id == hellofresh_cat_id:
            hellofresh_real += amt
            if str(acct) == "1100005":  # Card B
                card_b_hellofresh_real += amt
        else:
            other_cc_real_by_cat[cat_id] = other_cc_real_by_cat.get(cat_id, 0.0) + amt

    # Build planned map: event.scenario.account_id (bank id) → catalog.id via
    # catalog.account_id field. Same lookup as bills_classifier.
    bank_to_acct: dict[int, int] = {
        int(a.get("account_id")): int(a.get("id"))
        for a in account_catalog
        if a.get("account_id") is not None
    }
    fxa_cc_bank_ids: set[int] = {
        bank_id
        for bank_id, acct_id in bank_to_acct.items()
        if str(acct_id) in fxa_acct_ids
    }
    planned_by_cat: dict[int, float] = {}
    for e in events:
        cat = e.get("category") or {}
        cat_id = cat.get("id")
        if cat_id is None or cat.get("is_transfer", False):
            continue
        sc = e.get("scenario") or {}
        if sc.get("account_id") not in fxa_cc_bank_ids:
            continue
        planned_by_cat[cat_id] = planned_by_cat.get(cat_id, 0.0) + abs(
            e.get("amount", 0)
        )
    hellofresh_planned = planned_by_cat.get(hellofresh_cat_id, 0.0)
    hellofresh_overage = max(0.0, hellofresh_real - hellofresh_planned)
    # Find CC-payment cat id (mirror builder logic: title contains "cc payment"
    # in category OR any child).
    cc_pay_cat_id: int | None = None
    for c in category_catalog:
        if "cc payment" in (c.get("title", "")).lower():
            cc_pay_cat_id = c.get("id")
            break
        for ch in c.get("children", []):
            if "cc payment" in (ch.get("title", "")).lower():
                cc_pay_cat_id = ch.get("id")
                break
        if cc_pay_cat_id is not None:
            break
    other_cc_total = sum(other_cc_real_by_cat.values())
    other_cc_excl_ccpay = sum(
        v for cid, v in other_cc_real_by_cat.items() if cid != cc_pay_cat_id
    )
    other_cc_overage = (
        other_cc_excl_ccpay  # full real counts (no planned buys in those cats)
    )

    print()
    print(f"HelloFresh (cat {hellofresh_cat_id}) [Fixture A]:")
    print(
        f"  real={hellofresh_real:.2f}  planned={hellofresh_planned:.2f}  "
        f"overage={hellofresh_overage:.2f}"
    )
    print(f"  Card B HelloFresh real (acct 1100005)={card_b_hellofresh_real:.2f}")
    print(
        f"Other CC cats (Fixture A): real={other_cc_excl_ccpay:.2f}  "
        f"overage={other_cc_overage:.2f}"
    )
    print(
        f"  (excluded CC-paydown cat {cc_pay_cat_id} sum={other_cc_total - other_cc_excl_ccpay:.2f})"
    )
    print(f"  per-cat (incl. cc-pay): {dict(other_cc_real_by_cat)}")
    print(
        f"Expected total Fixture A overage: "
        f"{hellofresh_overage + other_cc_overage:.2f}"
    )


if __name__ == "__main__":
    main()
