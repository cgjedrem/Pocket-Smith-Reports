"""Multi-month aggregator for the MoM (Month-on-Month) comparison report.

Takes the per-month data (txns + tally + wallet) from each month in the
period, and produces:
  - Per-month time series for every metric
  - Per-cat trends across the period
  - Cumulative totals (sum of all months)
    - Per-partner splits (Partner A / Partner B)

The output is a dict structure that the MoM render layer can consume
directly to build the PDF.

Usage:
    from compare import aggregate_months
    months = [{'month': 'YYYY-MM', 'txns': [...], 'totals': {...}, 'wallet': {...}}]
    agg = aggregate_months(months)
    # agg['cumulative']['income'] -> {partner_a, partner_b, total}
    # agg['series']['income']['partner_a'] -> [value, ...]
"""

from collections import defaultdict
from typing import Dict, List, Any, Optional


def _partner_values(values: Dict[str, Any]) -> tuple[Any, Any]:
    """Return the two partner values from a wallet mapping, excluding total."""
    partners = [value for key, value in values.items() if key != "total"]
    if len(partners) != 2:
        raise ValueError(
            "Wallet partner mapping must contain exactly two non-total values"
        )
    return partners[0], partners[1]


def aggregate_normalized_months(months: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate shared monthly contracts with values at source month indexes."""
    months_sorted = sorted(months, key=lambda month: month["month"])
    labels = [month["month"] for month in months_sorted]
    categories = _aggregate_normalized_entries(months_sorted, labels, "categories")
    reconciliation = {
        field: [
            month["contract"].get("reconciliation", {}).get(field, 0.0)
            for month in months_sorted
        ]
        for field in ("source", "report", "difference")
    }
    return {
        "months": labels,
        "categories": categories,
        "reconciliation": reconciliation,
    }


def _aggregate_normalized_entries(
    months_sorted: List[Dict[str, Any]], labels: List[str], field: str
) -> Dict[str, Dict[str, Any]]:
    entries: Dict[str, Dict[str, Any]] = {}
    for index, month in enumerate(months_sorted):
        for category in month["contract"].get(field, []):
            entry = entries.setdefault(
                category["id"],
                {
                    "id": category["id"],
                    "title": category["title"],
                    "parent_id": category["parent_id"],
                    "path": category.get("path", []),
                    "paid": [0.0] * len(labels),
                    "received": [0.0] * len(labels),
                    "net": [0.0] * len(labels),
                    "count": [0] * len(labels),
                },
            )
            entry["paid"][index] = category["paid"]
            entry["received"][index] = category["received"]
            entry["net"][index] = category["net"]
            entry["count"][index] = category["count"]
    return entries


def aggregate_months(months: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate per-month data into MoM time series.

    Args:
        months: list of dicts, each with keys:
          - 'month': 'YYYY-MM' string
          - 'txns': list of raw txns
          - 'totals': tally.compute() output
          - 'wallet': wallet.compute() output

    Returns:
        dict with: period, months, cumulative, series, cats, paired_reimbs
    """
    if not months:
        return {
            "period": "",
            "months": [],
            "cumulative": {},
            "series": {},
            "cats": [],
            "paired_reimbs": [],
        }

    months_sorted = sorted(months, key=lambda m: m["month"])
    period = f"{months_sorted[0]['month']} → {months_sorted[-1]['month']} ({len(months_sorted)} months)"

    # Cumulative totals
    cumulative = {
        "income": {"partner_a": 0.0, "partner_b": 0.0, "total": 0.0},
        "savings": {"net_partner_a": 0.0, "net_partner_b": 0.0, "total": 0.0},
        "real_spend": {"partner_a": 0.0, "partner_b": 0.0, "total": 0.0},
        "net_cash": {"partner_a": 0.0, "partner_b": 0.0, "total": 0.0},
    }

    # Per-month series
    series = {
        "income": {"partner_a": [], "partner_b": [], "total": []},
        "savings": {"net_partner_a": [], "net_partner_b": [], "total": []},
        "real_spend": {"partner_a": [], "partner_b": [], "total": []},
        "net_cash": {"partner_a": [], "partner_b": [], "total": []},
    }
    # Per-cat series: cat -> {section -> data: list of partner values and totals}
    cats = {}

    # Paired reimbs
    all_paired_reimbs = []

    month_labels = []
    for m in months_sorted:
        month_labels.append(m["month"])
        wallet = m["wallet"]
        totals = m["totals"]
        sav = wallet.get("savings", {})
        income_a, income_b = _partner_values(wallet["income"])
        savings_a, savings_b = _partner_values(sav)
        spend_a, spend_b = _partner_values(wallet["wallets"])
        cash_a, cash_b = _partner_values(wallet["net_cash"])

        # Cumulative income
        cumulative["income"]["partner_a"] += income_a
        cumulative["income"]["partner_b"] += income_b
        cumulative["income"]["total"] += wallet["income"]["total"]

        cumulative["savings"]["net_partner_a"] += savings_a
        cumulative["savings"]["net_partner_b"] += savings_b
        cumulative["savings"]["total"] += sav.get("total", 0)

        # Cumulative real spend
        cumulative["real_spend"]["partner_a"] += spend_a
        cumulative["real_spend"]["partner_b"] += spend_b
        cumulative["real_spend"]["total"] += wallet["wallets"]["total"]

        # Cumulative net cash
        cumulative["net_cash"]["partner_a"] += cash_a
        cumulative["net_cash"]["partner_b"] += cash_b
        cumulative["net_cash"]["total"] += wallet["net_cash"]["total"]

        # Series
        series["income"]["partner_a"].append(income_a)
        series["income"]["partner_b"].append(income_b)
        series["income"]["total"].append(wallet["income"]["total"])
        series["savings"]["net_partner_a"].append(savings_a)
        series["savings"]["net_partner_b"].append(savings_b)
        series["savings"]["total"].append(sav.get("total", 0))
        series["real_spend"]["partner_a"].append(spend_a)
        series["real_spend"]["partner_b"].append(spend_b)
        series["real_spend"]["total"].append(wallet["wallets"]["total"])
        series["net_cash"]["partner_a"].append(cash_a)
        series["net_cash"]["partner_b"].append(cash_b)
        series["net_cash"]["total"].append(wallet["net_cash"]["total"])

        # Per-cat
        for cat_title, cat_info in wallet["cats"].items():
            if cat_title not in cats:
                cats[cat_title] = {
                    "section": cat_info.get("section", "common"),
                    "partner_a_paid": [0.0] * len(months_sorted),
                    "partner_b_paid": [0.0] * len(months_sorted),
                    "partner_a_received": [0.0] * len(months_sorted),
                    "partner_b_received": [0.0] * len(months_sorted),
                    "partner_a_net": [0.0] * len(months_sorted),
                    "partner_b_net": [0.0] * len(months_sorted),
                    "total": [0.0] * len(months_sorted),
                    "count": [0] * len(months_sorted),
                    "is_reimbursement": cat_info.get("is_reimbursement", False),
                }
            partner_paid = [
                value for key, value in cat_info.items() if key.endswith("_paid")
            ]
            partner_received = [
                value for key, value in cat_info.items() if key.endswith("_received")
            ]
            partner_net = [
                value for key, value in cat_info.items() if key.endswith("_net")
            ]
            if not partner_received:
                partner_received = [0, 0]
            if (
                len(partner_paid) != 2
                or len(partner_received) != 2
                or len(partner_net) != 2
            ):
                raise ValueError(
                    "Category partner values must contain exactly two entries"
                )
            index = len(month_labels) - 1
            cats[cat_title]["partner_a_paid"][index] = partner_paid[0]
            cats[cat_title]["partner_b_paid"][index] = partner_paid[1]
            cats[cat_title]["partner_a_received"][index] = partner_received[0]
            cats[cat_title]["partner_b_received"][index] = partner_received[1]
            cats[cat_title]["partner_a_net"][index] = partner_net[0]
            cats[cat_title]["partner_b_net"][index] = partner_net[1]
            # v4 wallet uses 'effective_total', not 'total'
            cats[cat_title]["total"][index] = cat_info.get("effective_total", 0) or 0
            cats[cat_title]["count"][index] = cat_info.get("count", 0)

        # Paired reimbs
        for e in wallet.get("paired_reimb_events", []):
            all_paired_reimbs.append({**e, "month": m["month"]})

    return {
        "period": period,
        "months": month_labels,
        "cumulative": cumulative,
        "series": series,
        "cats": cats,
        "paired_reimbs": all_paired_reimbs,
    }


def series_for_cat(
    agg: Dict[str, Any], cat_title: str
) -> Optional[Dict[str, List[float]]]:
    """Get the per-month series for a specific cat."""
    if cat_title not in agg["cats"]:
        return None
    c = agg["cats"][cat_title]
    return {
        "partner_a_paid": c["partner_a_paid"],
        "partner_b_paid": c["partner_b_paid"],
        "partner_a_net": c["partner_a_net"],
        "partner_b_net": c["partner_b_net"],
        "total": c["total"],
    }


def section_totals_per_month(
    agg: Dict[str, Any], section: str
) -> Dict[str, List[float]]:
    """Sum per-cat values within a section, per month.

    Useful for Section totals (e.g. Home total per month).
    """
    result = {
        "partner_a_paid": [0.0] * len(agg["months"]),
        "partner_b_paid": [0.0] * len(agg["months"]),
        "partner_a_net": [0.0] * len(agg["months"]),
        "partner_b_net": [0.0] * len(agg["months"]),
        "total": [0.0] * len(agg["months"]),
    }
    for cat_title, c in agg["cats"].items():
        if c.get("section") != section:
            continue
        for i in range(len(agg["months"])):
            result["partner_a_paid"][i] += c["partner_a_paid"][i]
            result["partner_b_paid"][i] += c["partner_b_paid"][i]
            result["partner_a_net"][i] += c["partner_a_net"][i]
            result["partner_b_net"][i] += c["partner_b_net"][i]
            result["total"][i] += c["total"][i]
    return result


def mom_deltas(series: List[float]) -> List[Optional[float]]:
    """Compute month-on-month deltas (None for first month)."""
    result: List[Optional[float]] = [None]
    for i in range(1, len(series)):
        result.append(series[i] - series[i - 1])
    return result
