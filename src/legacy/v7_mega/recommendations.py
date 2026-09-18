#!/usr/bin/env python3
"""recommendations.py — auto-generate recommendations from comparison data.

Rules engine (locked 2026-07-21 design round 1).

Each rule returns a dict {severity, title, evidence, action} or None.
"""

from typing import List, Dict, Any


def _fmt_nok(n):
    if n is None:
        return "n/a"
    return f"{n:,.0f} NOK"


def _fmt_pct(p):
    if p is None:
        return "n/a"
    sign = "+" if p > 0 else ""
    return f"{sign}{p:.1f}%"


def generate(cmp: dict, trend_rows: list = None) -> List[Dict[str, Any]]:
    """Return ordered list of recommendation dicts."""
    recs = []
    deltas = cmp["deltas"]
    cat_deltas = cmp["category_deltas"]
    trips = cmp.get("trips", [])

    cur_km = deltas

    # 1) Category spikes
    for c in cat_deltas:
        if (
            c["abs_delta"] >= 5000
            and c["pct_delta"] is not None
            and c["pct_delta"] >= 30
        ):
            recs.append(
                {
                    "severity": "warn",
                    "category": c["category"],
                    "title": f"{c['category']} up {_fmt_pct(c['pct_delta'])} MoM",
                    "evidence": f"{_fmt_nok(c['prior'])} → {_fmt_nok(c['current'])} (Δ {_fmt_nok(c['abs_delta'])})",
                    "action": "Investigate transactions; check if one-off or recurring",
                }
            )
        elif (
            c["abs_delta"] <= -5000
            and c["pct_delta"] is not None
            and c["pct_delta"] <= -30
        ):
            recs.append(
                {
                    "severity": "good",
                    "category": c["category"],
                    "title": f"{c['category']} down {_fmt_pct(c['pct_delta'])} MoM",
                    "evidence": f"{_fmt_nok(c['prior'])} → {_fmt_nok(c['current'])} (Δ {_fmt_nok(c['abs_delta'])})",
                    "action": "Good — review whether this is sustainable or a one-off",
                }
            )

    # 2) Trip costliness
    if trips:
        for t in trips:
            if t["days"] >= 7 and t["per_day"] <= -3000:
                recs.append(
                    {
                        "severity": "warn",
                        "category": "trips",
                        "title": f"Trip to {t['location']}: {_fmt_nok(-t['per_day'])}/day",
                        "evidence": f"{t['days']} days, {_fmt_nok(-t['total'])} total ({t['txn_count']} txns)",
                        "action": "High cost/day — consider shorter stay or budget cap next time",
                    }
                )
            elif t["days"] >= 2 and t["per_day"] >= -700:
                recs.append(
                    {
                        "severity": "good",
                        "category": "trips",
                        "title": f"Trip to {t['location']}: efficient {_fmt_nok(-t['per_day'])}/day",
                        "evidence": f"{t['days']} days, {_fmt_nok(-t['total'])} total",
                        "action": "Reference pattern for budget trips",
                    }
                )
            # NEW: very short trip with high cost (e.g. day-trip flight)
            elif t["days"] == 1 and t["total"] <= -3000:
                recs.append(
                    {
                        "severity": "info",
                        "category": "trips",
                        "title": f"Day-trip to {t['location']}: {_fmt_nok(-t['total'])} in 1 day",
                        "evidence": f"{t['txn_count']} txns (likely flight + bookings)",
                        "action": "Consider booking earlier; day-trips often overpriced",
                    }
                )

    # 3) Savings rate trend (3+ months)
    if trend_rows and len(trend_rows) >= 3:
        last3 = trend_rows[-3:]

        # Combined partner savings rate.
        def combined_sav(r):
            rates = [value for key, value in r.items() if key.endswith("_savings_rate")]
            if len(rates) != 2:
                raise ValueError("Expected exactly two partner savings rates")
            return sum(rates)

        rates = [combined_sav(r) for r in last3]
        if rates[0] - rates[-1] >= 5:
            evidence_str = " → ".join(
                f"{r['month']}: {combined_sav(r):.1f}%" for r in last3
            )
            recs.append(
                {
                    "severity": "warn",
                    "category": "savings",
                    "title": f"Savings rate declining 3 months running",
                    "evidence": evidence_str,
                    "action": "Re-anchor budget; check discretionary categories",
                }
            )

    # 4) Net cash
    nc = cur_km.get("net_cash", {}).get("abs")
    if nc is not None and nc < 0:
        recs.append(
            {
                "severity": "warn" if abs(nc) < 20000 else "high",
                "category": "cashflow",
                "title": f"Net cash {nc:+,.0f} NOK",
                "evidence": f"Real spend {cur_km['real_spend']['current']:,.0f} - income {cur_km['income']['current']:,.0f} - savings {cur_km['savings']['current']:,.0f}",
                "action": "Cash flow negative; consider pause on discretionary spend",
            }
        )

    # 5) Wallet imbalance
    wallet_values = [value for key, value in cur_km.items() if key.endswith("_wallet")]
    if len(wallet_values) != 2:
        raise ValueError("Expected exactly two partner wallet metrics")
    partner_a_wallet, partner_b_wallet = wallet_values
    partner_a_pct = (
        partner_a_wallet.get("current", 0)
        / max(cur_km.get("real_spend", {}).get("current", 1), 1)
        * 100
    )
    partner_b_pct = 100 - partner_a_pct
    if partner_a_pct >= 55:
        recs.append(
            {
                "severity": "info",
                "category": "balance",
                "title": f"Partner A paid {partner_a_pct:.1f}% of household real spend",
                "evidence": f"Partner A {_fmt_nok(partner_a_wallet['current'])} / Partner B {_fmt_nok(partner_b_wallet['current'])}",
                "action": "Partner A-heavy month: review reimbursement pattern with Partner B",
            }
        )
    elif partner_b_pct >= 55:
        recs.append(
            {
                "severity": "info",
                "category": "balance",
                "title": f"Partner B paid {partner_b_pct:.1f}% of household real spend",
                "evidence": f"Partner B {_fmt_nok(partner_b_wallet['current'])} / Partner A {_fmt_nok(partner_a_wallet['current'])}",
                "action": "Partner B-heavy month: review reimbursement pattern with Partner A",
            }
        )

    # 6) NEW: Income drop warning (income down >10% MoM)
    inc_d = deltas.get("income", {})
    if inc_d.get("pct") is not None and inc_d["pct"] <= -10:
        recs.append(
            {
                "severity": "warn" if inc_d["pct"] > -20 else "high",
                "category": "income",
                "title": f"Income down {_fmt_pct(inc_d['pct'])} MoM",
                "evidence": f"{_fmt_nok(inc_d['prior'])} → {_fmt_nok(inc_d['current'])}",
                "action": "Income drop — confirm expected (bonus gone, parental leave, etc)",
            }
        )

    # 7) NEW: Spend down — good if >10% drop
    sp_d = deltas.get("real_spend", {})
    if sp_d.get("pct") is not None and sp_d["pct"] <= -10:
        recs.append(
            {
                "severity": "good",
                "category": "spend",
                "title": f"Spend down {_fmt_pct(sp_d['pct'])} MoM",
                "evidence": f"{_fmt_nok(sp_d['prior'])} → {_fmt_nok(sp_d['current'])}",
                "action": "Good — likely no trips this month; sustainable baseline",
            }
        )

    # 8) NEW: Trip total as % of real spend
    if trips and cur_km.get("real_spend", {}).get("current", 0) > 0:
        trip_total = sum(-t["total"] for t in trips)
        spend = cur_km["real_spend"]["current"]
        if trip_total / spend >= 0.4:
            recs.append(
                {
                    "severity": "warn" if trip_total / spend < 0.6 else "high",
                    "category": "trips",
                    "title": f"Trips = {trip_total/spend*100:.0f}% of real spend this period",
                    "evidence": f"{_fmt_nok(trip_total)} in trips / {_fmt_nok(spend)} total spend",
                    "action": "Travel-heavy period — expect lower spend next month when home",
                }
            )

    # 9) NEW: New categories (cat present in current but not prior with abs > 1000)
    if cat_deltas:
        for c in cat_deltas:
            if c["prior"] == 0 and c["current"] >= 1000 and c["pct_delta"] is None:
                recs.append(
                    {
                        "severity": "info",
                        "category": c["category"],
                        "title": f"New category: {c['category']} ({_fmt_nok(c['current'])})",
                        "evidence": f"No spend in prior period, {_fmt_nok(c['current'])} in current",
                        "action": "Confirm this is a one-off; consider adding to budget",
                    }
                )

    # Dedupe: keep max 6, prefer warn > good > info
    sev_order = {"high": 0, "warn": 1, "info": 2, "good": 3}
    recs.sort(
        key=lambda r: (
            sev_order.get(r["severity"], 9),
            -abs(r.get("abs_delta", 0) if "abs_delta" in r else 0),
        )
    )
    return recs[:6]


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from compare import compare_periods, trend

    raise SystemExit("Pass periods through the supported report entry point.")
    t = trend(None)
    recs = generate(cmp, t)
    for r in recs:
        print(f"[{r['severity']:4s}] {r['title']}")
        print(f"        Evidence: {r['evidence']}")
        print(f"        Action:   {r['action']}")
        print()
