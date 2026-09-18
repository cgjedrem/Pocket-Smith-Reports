#!/usr/bin/env python3
"""compare.py — compute period-over-period deltas for the household report.

Inputs: two PocketSmith JSON exports + the v5 wallet/tally functions.
Output: a comparison dict with current, prior, delta, %delta per metric.

For Q-on-Q use: pass 3 months of exports, then call with current=q1, prior=q4.
For MoM: pass 2+ months, call with current=this_month, prior=prev_month.

Locked from design round 1 (2026-07-21).
"""

import json
import sys
import os
from datetime import date as D
from pathlib import Path

# Re-use the v5 pipeline
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
V5_DIR = str(Path(__file__).resolve().parents[1] / "v4_pipeline")
sys.path.insert(0, V5_DIR)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from data_loader import load as v5_load
from tally import compute as v5_tally
from wallet import compute as v5_wallet
from input_contract import InputContractError, resolve_month_input

# Local
sys.path.insert(0, SCRIPT_DIR)
from trips import detect_trips, trips_summary

MONTH_NAMES = [
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
]


def _resolve_month_path(month):
    """Resolve one configured month from the strict source contract."""
    base = os.environ.get("POCKETSMITH_DATA_DIR")
    if not base:
        raise FileNotFoundError("POCKETSMITH_DATA_DIR must name the export directory")
    input_kind = os.environ.get("POCKETSMITH_INPUT_KIND")
    if input_kind not in ("live", "synthetic"):
        raise FileNotFoundError(
            "POCKETSMITH_INPUT_KIND must be explicitly set to live or synthetic"
        )
    try:
        return str(resolve_month_input(month, Path(base), input_kind))
    except InputContractError as error:
        raise FileNotFoundError(str(error)) from error


def _enrich_txns(txns):
    """Add __account_name to each txn from the nested account object.

    The v5 data_loader assumes the field exists, but raw MCP PS exports
    only have 'account': {id, name}. Tally uses __account_name for payer
    detection. Without enrichment, 3rd-party income goes to wrong bucket.
    """
    for t in txns:
        if (
            "__account_name" not in t
            and "account" in t
            and isinstance(t["account"], dict)
        ):
            t["__account_name"] = t["account"].get("name", "")
    return txns


def _load_wallet(month):
    """Return (totals, wallet) dicts for a given month."""
    path = _resolve_month_path(month)
    txns = _enrich_txns(v5_load(month, path))
    totals = v5_tally(txns, {})
    wallet = v5_wallet(totals)
    return totals, wallet, txns


def _delta(curr, prior):
    """Return (delta, pct) for two numbers. pct=None if prior==0."""
    d = curr - prior
    if prior == 0:
        return d, None
    return d, (d / abs(prior)) * 100


def _partner_metric(wallet, metric, index):
    """Return a metric from one of the two non-total partner wallet buckets."""
    partners = [value for key, value in wallet.items() if key != "totals"]
    if len(partners) != 2:
        raise ValueError("Expected exactly two partner wallet buckets")
    return partners[index][metric]


def compare_periods(current_month, prior_month, export_paths=None):
    """Build a comparison dict between two months.

    Returns dict with:
      - 'current': {month, totals, wallet, key_metrics}
      - 'prior': same
      - 'deltas': {metric: {abs, pct, direction}}
      - 'category_deltas': list of {cat, curr, prior, abs_delta, pct_delta}
      - 'category_txns': {cat: [txn dicts]} — drilldown for the comparison period
      - 'trips': detected trips for the combined range
    """
    cur_totals, cur_wallet, cur_txns = _load_wallet(current_month)
    pri_totals, pri_wallet, pri_txns = _load_wallet(prior_month)

    # Per-category txn list (current + prior combined) for drilldown
    cat_txns = {}
    for t in cur_txns + pri_txns:
        c = t.get("category") or {}
        cat = c.get("title", "Uncategorized")
        cat_txns.setdefault(cat, []).append(t)

    cur_t = cur_wallet["totals"]
    pri_t = pri_wallet["totals"]

    def km(w):
        partner_a, partner_b = [value for key, value in w.items() if key != "totals"]
        return {
            "income": int(round(w["totals"]["income"])),
            "real_spend": int(round(w["totals"]["wallet"])),
            "net_cash": int(round(w["totals"]["net_cash"])),
            "savings": int(round(w["totals"]["savings"])),
            "partner_a_income": int(round(partner_a["income"])),
            "partner_a_wallet": int(round(partner_a["wallet"])),
            "partner_a_net": int(round(partner_a["net_cash"])),
            "partner_a_savings": int(round(partner_a["savings"])),
            "partner_b_income": int(round(partner_b["income"])),
            "partner_b_wallet": int(round(partner_b["wallet"])),
            "partner_b_net": int(round(partner_b["net_cash"])),
            "partner_b_savings": int(round(partner_b["savings"])),
        }

    cur_km = km(cur_wallet)
    pri_km = km(pri_wallet)

    deltas = {}
    for k in cur_km:
        d, p = _delta(cur_km[k], pri_km[k])
        deltas[k] = {
            "abs": round(d, 2),
            "pct": round(p, 1) if p is not None else None,
            "direction": "up" if d > 0 else ("down" if d < 0 else "flat"),
            "current": round(cur_km[k], 2),
            "prior": round(pri_km[k], 2),
        }

    # Per-category comparison
    cur_rows = cur_wallet["rows"]
    pri_rows = pri_wallet["rows"]
    all_cats = sorted(set(cur_rows.keys()) | set(pri_rows.keys()))
    cat_deltas = []
    for cat in all_cats:
        c_tot = cur_rows.get(cat, {}).get("total", 0) or 0
        p_tot = pri_rows.get(cat, {}).get("total", 0) or 0
        d, p = _delta(c_tot, p_tot)
        cat_deltas.append(
            {
                "category": cat,
                "current": round(c_tot, 2),
                "prior": round(p_tot, 2),
                "abs_delta": round(d, 2),
                "pct_delta": round(p, 1) if p is not None else None,
                "direction": "up" if d > 0 else ("down" if d < 0 else "flat"),
            }
        )
    cat_deltas.sort(key=lambda x: -abs(x["abs_delta"]))

    # Trips across both months
    if export_paths is None:
        export_paths = [
            _resolve_month_path(current_month),
            _resolve_month_path(prior_month),
        ]
    trips = detect_trips(export_paths)
    # Filter trips to those touching either current or prior month
    rel_trips = [
        t for t in trips if current_month in t["months"] or prior_month in t["months"]
    ]

    return {
        "current": {
            "month": current_month,
            "txn_count": len(cur_txns),
            "key_metrics": cur_km,
            "totals": cur_totals,
            "wallet": cur_wallet,
        },
        "prior": {
            "month": prior_month,
            "txn_count": len(pri_txns),
            "key_metrics": pri_km,
            "totals": pri_totals,
            "wallet": pri_wallet,
        },
        "deltas": deltas,
        "category_deltas": cat_deltas,
        "category_txns": cat_txns,
        "trips": rel_trips,
        "trips_summary": trips_summary(rel_trips),
    }


def trend(export_paths):
    """Build a 9-month trend table for KPI tracking."""
    if export_paths is None:
        months = [
            value.strip()
            for value in os.environ.get("POCKETSMITH_REPORT_MONTHS", "").split(",")
            if value.strip()
        ]
        if not months:
            raise FileNotFoundError(
                "POCKETSMITH_REPORT_MONTHS must list configured report months"
            )
        export_paths = [_resolve_month_path(month) for month in months]
    else:
        months = []
    trend_rows = []
    for index, fp in enumerate(export_paths):
        with open(fp) as f:
            d = json.load(f)
        month = months[index] if months else d.get("month")
        if not month:
            raise ValueError(f"Missing month in trend source: {fp}")
        totals, wallet, txns = _load_wallet(month)
        trend_rows.append(
            {
                "month": month,
                "txn_count": len(txns),
                "income": round(wallet["totals"]["income"], 2),
                "real_spend": round(wallet["totals"]["wallet"], 2),
                "net_cash": round(wallet["totals"]["net_cash"], 2),
                "savings": round(wallet["totals"]["savings"], 2),
                "partner_a_savings_rate": round(
                    _partner_metric(wallet, "savings_rate", 0), 2
                ),
                "partner_b_savings_rate": round(
                    _partner_metric(wallet, "savings_rate", 1), 2
                ),
            }
        )
    trend_rows.sort(key=lambda x: x["month"])
    return trend_rows


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--current", required=True, help="Current month YYYY-MM")
    p.add_argument("--prior", required=True, help="Prior month YYYY-MM")
    args = p.parse_args()
    cmp = compare_periods(args.current, args.prior)
    print(f"\n=== {args.current} vs {args.prior} ===\n")
    print(f"{'Metric':<20s} {'Current':>12s} {'Prior':>12s} {'Δ':>12s} {'%':>8s}")
    print("-" * 70)
    for k, d in cmp["deltas"].items():
        pct = f"{d['pct']:+.1f}%" if d["pct"] is not None else "n/a"
        print(
            f"{k:<20s} {d['current']:>12,.0f} {d['prior']:>12,.0f} {d['abs']:>+12,.0f} {pct:>8s}"
        )
    print(f"\n=== Top 10 category deltas ===")
    for c in cmp["category_deltas"][:10]:
        pct = f"{c['pct_delta']:+.1f}%" if c["pct_delta"] is not None else "n/a"
        print(
            f"  {c['category']:35s} {c['current']:>+10,.0f}  vs  {c['prior']:>+10,.0f}  Δ {c['abs_delta']:>+10,.0f}  ({pct})"
        )
    print(f"\n=== Trips ({len(cmp['trips'])}) ===")
    for t in cmp["trips"]:
        print(
            f"  T{t['idx']:2d}  {t['location']:25s}  {t['start']}→{t['end']}  {t['total']:>10,.0f} NOK  ({t['per_day']:,.0f}/day)"
        )
