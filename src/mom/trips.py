"""Trip clustering by PS labels.

A single trip = a set of transactions sharing the same PS `labels` value.
For txns without labels, they fall into the "untagged" bucket and are NOT
grouped as trips (they go to the regular cat buckets).

The clustering respects:
- Same label string = same trip
- Per-partner attribution: which side paid for the trip
- Date range: from earliest to latest txn
- Total cost: sum of all txns (outflows only, in absolute value)

Usage:
    from trips import cluster_by_label
    all_txns = [...]  # concatenated across all months
    clusters = cluster_by_label(all_txns)
    # clusters = [{'label': 'trip', 'txns': [...], 'date_start': '2026-04-01',
    #             'date_end': '2026-04-07', 'total': 5430.5, 'partner_a_paid': 1234,
    #             'partner_b_paid': 4196}, ...]
"""

import os
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Any, Optional


def _account_names(env_var: str, defaults: set[str]) -> set[str]:
    configured = os.environ.get(env_var)
    if not configured:
        return defaults
    return {name.strip() for name in configured.split(",") if name.strip()}


# Configure production account names through these environment variables.
PARTNER_A_ACCOUNTS = _account_names(
    "POCKETSMITH_PARTNER_A_ACCOUNTS",
    {"Partner A Checking", "Partner A Credit", "Partner A Savings"},
)
PARTNER_B_ACCOUNTS = _account_names(
    "POCKETSMITH_PARTNER_B_ACCOUNTS",
    {"Partner B Checking", "Partner B Credit", "Partner B Savings"},
)


def _partner_of(transaction: Dict[str, Any] | str) -> str:
    """Prefer normalized ownership; retain legacy standalone caller support."""
    if isinstance(transaction, dict):
        owner = transaction.get("owner")
        if owner == "partner_a":
            return "Partner A"
        if owner == "partner_b":
            return "Partner B"
        account_name = (transaction.get("account") or {}).get("name", "")
    else:
        account_name = transaction
    if account_name in PARTNER_A_ACCOUNTS:
        return "Partner A"
    if account_name in PARTNER_B_ACCOUNTS:
        return "Partner B"
    return "Joint"


def cluster_by_label(txns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group txns by PS label, returning per-trip clusters.

    Each txn must have 'labels' (list of strings), 'date' (YYYY-MM-DD),
    'amount' (float, negative=outflow), and 'account' (dict with 'name').
    """
    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for t in txns:
        labels = t.get("labels") or []
        for lab in labels:
            if isinstance(lab, dict):
                lab = lab.get("title", "")
            if not lab:
                continue
            buckets[lab].append(t)

    clusters = []
    for label, items in buckets.items():
        # Sort by date
        items.sort(key=lambda t: t.get("date", ""))
        date_start = items[0].get("date", "")
        date_end = items[-1].get("date", "")
        # Outflows + inflows (inflows reduce per-person net spend)
        outflows = [t for t in items if t.get("amount", 0) < 0]
        inflows = [t for t in items if t.get("amount", 0) > 0]
        # Total = gross outflows - third-party inflows only.
        # Partner-to-partner transfers are NOT subtracted from
        # total because they move between partners (the recipient's net goes
        # down, the sender's net goes up, total unchanged).
        # We detect partner transfers: inflow on one partner's account matching
        # an outflow on the other partner's account with same amount + close date.
        all_inflows = sum(t.get("amount", 0) for t in inflows)
        # Detect partner-transfer inflows (to exclude from total subtraction)
        partner_transfer_inflows = 0.0
        from datetime import datetime as _dt

        _outs_by_amt = {}
        _ins_by_amt = {}
        for t in items:
            amt = round(t.get("amount", 0))
            if amt == 0:
                continue
            acct = (t.get("account") or {}).get("name", "")
            date_str = (t.get("date") or "")[:10]
            try:
                date = _dt.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue
            if amt < 0:
                _outs_by_amt.setdefault(-amt, []).append((_partner_of(t), acct, date))
            else:
                _ins_by_amt.setdefault(amt, []).append((_partner_of(t), acct, date))
        for amt, outs in _outs_by_amt.items():
            ins = _ins_by_amt.get(amt, [])
            used = set()
            for o_owner, o_acct, o_date in outs:
                for idx, (i_owner, i_acct, i_date) in enumerate(ins):
                    if idx in used:
                        continue
                    if o_acct == i_acct:
                        continue
                    if abs((o_date - i_date).days) > 3:
                        continue
                    if o_owner == i_owner:
                        continue
                    partner_transfer_inflows += amt
                    used.add(idx)
                    break
        third_party_inflows = all_inflows - partner_transfer_inflows
        # Total = gross outflows - partner transfers - third-party inflows.
        # Partner transfers are not merchant spend (just money moving between
        # partners). Third-party inflows
        # costs) reduce the real trip cost.
        total = (
            sum(abs(t.get("amount", 0)) for t in outflows)
            - partner_transfer_inflows
            - third_party_inflows
        )
        # Per-partner NET: outflows minus inflows (third-party reims reduce net)
        partner_a_gross = sum(
            abs(t.get("amount", 0)) for t in outflows if _partner_of(t) == "Partner A"
        )
        partner_b_gross = sum(
            abs(t.get("amount", 0)) for t in outflows if _partner_of(t) == "Partner B"
        )
        partner_a_inflows = sum(
            t.get("amount", 0) for t in inflows if _partner_of(t) == "Partner A"
        )
        partner_b_inflows = sum(
            t.get("amount", 0) for t in inflows if _partner_of(t) == "Partner B"
        )
        partner_a_paid = partner_a_gross - partner_a_inflows
        partner_b_paid = partner_b_gross - partner_b_inflows
        # Cat breakdown
        cat_breakdown: Dict[str, float] = defaultdict(float)
        for t in outflows:
            cat = (t.get("category") or {}).get("title", "Uncategorized")
            cat_breakdown[cat] += abs(t.get("amount", 0))
        # Cat titles used
        cat_titles = list(cat_breakdown.keys())
        clusters.append(
            {
                "label": label,
                "date_start": date_start,
                "date_end": date_end,
                "days": (
                    (
                        datetime.strptime(date_end, "%Y-%m-%d")
                        - datetime.strptime(date_start, "%Y-%m-%d")
                    ).days
                    + 1
                    if date_start and date_end
                    else 0
                ),
                "txn_count": len(items),
                "total": total,
                "partner_a_paid": partner_a_paid,
                "partner_b_paid": partner_b_paid,
                "cats": cat_titles,
                "cat_breakdown": dict(cat_breakdown),
                "txns": items,
            }
        )

    # Sort by date_start
    clusters.sort(key=lambda c: c["date_start"])
    return clusters


def trip_summary(cluster: Dict[str, Any]) -> str:
    """One-line summary of a trip cluster."""
    return (
        f"{cluster['label']}: {cluster['date_start']} → {cluster['date_end']} "
        f"({cluster['days']} days), total {cluster['total']:,.0f} NOK "
        f"(Partner A {cluster['partner_a_paid']:,.0f} / Partner B {cluster['partner_b_paid']:,.0f})"
    )
