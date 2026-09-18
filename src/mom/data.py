"""Data ingestion: pull all months, enrich, aggregate.

This is the data layer for the MoM report. The section renderers consume
the `agg` dict produced here.

Input: ps_<month>_nested.json files in the output_dir.
Output: `agg` dict with:
  - months: list of "YYYY-MM" strings
    - cats: dict of cat_title -> {section, partner_a_paid, partner_b_paid, total, count, is_reimbursement, ...}
    - series: {income, savings, real_spend, net_cash} -> {partner_a, partner_b, total} -> list
  - cumulative: same structure, accumulated
  - paired_reimbs: list of {month, cat, sender, recipient, amount, date}
  - cc_paydowns: {cc_account -> {month -> amount}}
  - trips: list of trip clusters (from trips.py)
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "v4_pipeline"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from data_loader import load as load_month
from accounting import build_month_contract
from tally import compute as tally_compute, _section as tally_section
from wallet import compute as wallet_compute
from input_contract import resolve_month_input


def _partner_values(
    values: Dict[str, Any], prefix: str | None = None
) -> tuple[Any, Any]:
    """Return the two partner values from a wallet mapping, excluding total."""
    if prefix is None:
        partners = [
            value
            for key, value in values.items()
            if key != "total" and not key.startswith("kron_net_")
        ]
    else:
        partners = [value for key, value in values.items() if key.startswith(prefix)]
    if len(partners) != 2:
        raise ValueError(
            "Wallet partner mapping must contain exactly two non-total values"
        )
    return partners[0], partners[1]


def ingest_months(
    months: List[str], data_dir: str | Path, input_kind: str
) -> Dict[str, Any]:
    """Load all months, run tally + wallet + collect raw txns.

    Returns a dict with:
      - 'months': list of month strings
      - 'per_month': list of {month, wallet, totals, txns_count}
      - 'all_txns_by_month': dict of month -> list of raw txns
      - 'all_txns_flat': list of ALL txns across ALL months
    """
    per_month = []
    all_txns_by_month: Dict[str, List[Dict]] = {}
    for m in months:
        fn = str(resolve_month_input(m, Path(data_dir), input_kind))
        txns = load_month(m, fn)
        contract = build_month_contract(txns)
        totals = tally_compute(txns)
        wallet = wallet_compute(totals, txns)
        per_month.append(
            {
                "month": m,
                "contract": contract,
                "wallet": wallet,
                "totals": totals,
                "txns_count": len(txns),
            }
        )
        with open(fn, encoding="utf-8") as source:
            raw = json.load(source)
        raw_txns = raw if isinstance(raw, list) else raw.get("transactions", [])
        all_txns_by_month[m] = raw_txns

    all_txns_flat = []
    for m in months:
        all_txns_flat.extend(all_txns_by_month.get(m, []))

    from compare import aggregate_normalized_months

    return {
        "months": months,
        "per_month": per_month,
        "all_txns_by_month": all_txns_by_month,
        "all_txns_flat": all_txns_flat,
    }


def aggregate(ingested: Dict[str, Any]) -> Dict[str, Any]:
    """Build the per-month time series + cumulative totals from ingested data.

    Adds:
      - 'series': {income, savings, real_spend, net_cash} -> per-partner -> list
    - 'cats': cat -> {section, partner_a_paid, partner_b_paid, total, count, is_reimbursement}
      - 'cumulative': same as series but accumulated
      - 'paired_reimbs': list of paired reimbursement events
      - 'cc_paydowns': {cc_account -> {month -> amount}}
      - 'trips': list of trip clusters
    """
    months = ingested["months"]
    per_month = ingested["per_month"]

    # Series init
    series = {
        "income": {"partner_a": [], "partner_b": [], "total": []},
        "savings": {
            "net_partner_a": [],
            "net_partner_b": [],
            "total": [],
            "kron_net_partner_a": [],
            "kron_net_partner_b": [],
            "kron_net_total": [],
        },
        "real_spend": {"partner_a": [], "partner_b": [], "total": []},
        "net_cash": {"partner_a": [], "partner_b": [], "total": []},
    }
    cumulative = {
        "income": {"partner_a": 0.0, "partner_b": 0.0, "total": 0.0},
        "savings": {
            "net_partner_a": 0.0,
            "net_partner_b": 0.0,
            "total": 0.0,
            "kron_net_partner_a": 0.0,
            "kron_net_partner_b": 0.0,
            "kron_net_total": 0.0,
        },
        "real_spend": {"partner_a": 0.0, "partner_b": 0.0, "total": 0.0},
        "net_cash": {"partner_a": 0.0, "partner_b": 0.0, "total": 0.0},
    }
    cats: Dict[str, Dict[str, Any]] = {}
    all_paired_reimbs = []

    for m in per_month:
        wallet = m["wallet"]
        sav = wallet.get("savings", {})
        wallets = wallet.get("wallets", {})
        nc = wallet.get("net_cash", {})
        income_a, income_b = _partner_values(wallet["income"])
        savings_a, savings_b = _partner_values(sav)
        kron_savings_a, kron_savings_b = _partner_values(sav, "kron_net_")
        real_spend_a, real_spend_b = _partner_values(wallets)
        net_cash_a, net_cash_b = _partner_values(nc)
        # Series
        series["income"]["partner_a"].append(income_a)
        series["income"]["partner_b"].append(income_b)
        series["income"]["total"].append(wallet["income"]["total"])
        series["savings"]["net_partner_a"].append(savings_a)
        series["savings"]["net_partner_b"].append(savings_b)
        series["savings"]["total"].append(sav.get("total", 0))
        series["savings"]["kron_net_partner_a"].append(kron_savings_a)
        series["savings"]["kron_net_partner_b"].append(kron_savings_b)
        series["savings"]["kron_net_total"].append(sav.get("kron_net_total", 0))
        # Real spend from wallet.wallets
        real_spend_total = wallets.get("total", real_spend_a + real_spend_b)
        series["real_spend"]["partner_a"].append(real_spend_a)
        series["real_spend"]["partner_b"].append(real_spend_b)
        series["real_spend"]["total"].append(real_spend_total)
        # Net cash from wallet.net_cash
        nc_total = nc.get("total", net_cash_a + net_cash_b)
        series["net_cash"]["partner_a"].append(net_cash_a)
        series["net_cash"]["partner_b"].append(net_cash_b)
        series["net_cash"]["total"].append(nc_total)
        # Cumulative
        cumulative["income"]["partner_a"] += income_a
        cumulative["income"]["partner_b"] += income_b
        cumulative["income"]["total"] += wallet["income"]["total"]
        cumulative["savings"]["net_partner_a"] += savings_a
        cumulative["savings"]["net_partner_b"] += savings_b
        cumulative["savings"]["total"] += sav.get("total", 0)
        cumulative["savings"]["kron_net_partner_a"] += kron_savings_a
        cumulative["savings"]["kron_net_partner_b"] += kron_savings_b
        cumulative["savings"]["kron_net_total"] += sav.get("kron_net_total", 0)
        cumulative["real_spend"]["partner_a"] += real_spend_a
        cumulative["real_spend"]["partner_b"] += real_spend_b
        cumulative["real_spend"]["total"] += real_spend_total
        cumulative["net_cash"]["partner_a"] += net_cash_a
        cumulative["net_cash"]["partner_b"] += net_cash_b
        cumulative["net_cash"]["total"] += nc_total
        # Per-cat
        for cat_title, cat_info in wallet["cats"].items():
            if cat_title not in cats:
                cats[cat_title] = {
                    "section": cat_info.get("section", "common"),
                    "partner_a_paid": [],
                    "partner_b_paid": [],
                    "partner_a_received": [],
                    "partner_b_received": [],
                    "partner_a_net": [],
                    "partner_b_net": [],
                    "total": [],
                    "count": [],
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
            cats[cat_title]["partner_a_paid"].append(partner_paid[0])
            cats[cat_title]["partner_b_paid"].append(partner_paid[1])
            cats[cat_title]["partner_a_received"].append(partner_received[0])
            cats[cat_title]["partner_b_received"].append(partner_received[1])
            cats[cat_title]["partner_a_net"].append(partner_net[0])
            cats[cat_title]["partner_b_net"].append(partner_net[1])
            cats[cat_title]["total"].append(cat_info.get("effective_total", 0) or 0)
            cats[cat_title]["count"].append(cat_info.get("count", 0))
        # Paired reimbs
        for e in wallet.get("paired_reimb_events", []):
            e_copy = dict(e)
            e_copy["month"] = m["month"]
            all_paired_reimbs.append(e_copy)

    # ============================================================
    # EXCLUDED SECTION — pull from raw txns
    # (wallet.py filters out excluded cats because they're internal transfers)
    # ============================================================
    for month_str, raw_txns in ingested["all_txns_by_month"].items():
        for t in raw_txns:
            cat_title = (t.get("category") or {}).get("title") or "Uncategorised"
            sec = tally_section(cat_title) or ""
            if sec != "excluded":
                continue
            if cat_title not in cats:
                cats[cat_title] = {
                    "section": "excluded",
                    "partner_a_paid": [0.0] * len(months),
                    "partner_b_paid": [0.0] * len(months),
                    "partner_a_received": [0.0] * len(months),
                    "partner_b_received": [0.0] * len(months),
                    "partner_a_net": [0.0] * len(months),
                    "partner_b_net": [0.0] * len(months),
                    "total": [0.0] * len(months),
                    "count": [0] * len(months),
                    "is_reimbursement": False,
                }
            idx = months.index(month_str)
            amount = t.get("amount", 0) or 0
            cats[cat_title]["count"][idx] += 1
            cats[cat_title]["total"][idx] += amount
            acct_name = (t.get("account") or {}).get("name", "") or ""
            if "Partner A" in acct_name:
                if amount > 0:
                    cats[cat_title]["partner_a_received"][idx] += amount
                else:
                    cats[cat_title]["partner_a_paid"][idx] += amount
            elif "Partner B" in acct_name:
                if amount > 0:
                    cats[cat_title]["partner_b_received"][idx] += amount
                else:
                    cats[cat_title]["partner_b_paid"][idx] += amount

    # ============================================================
    # CC PAYDOWNS — from raw txns, look at the INFLOW side of
    # CC Payment (paired) — the receiving account is the CC card.
    # ============================================================
    cc_paydowns: Dict[str, Dict[str, float]] = {}
    excluded_transactions: Dict[str, List[Dict[str, Any]]] = {
        month: [] for month in months
    }
    for month_str, raw_txns in ingested["all_txns_by_month"].items():
        for t in raw_txns:
            cat_title = (t.get("category") or {}).get("title") or ""
            if tally_section(cat_title) == "excluded":
                account = t.get("account") or {}
                account_name = (
                    account.get("name", "") if isinstance(account, dict) else ""
                )
                owner = (
                    "partner_a"
                    if "Partner A" in account_name
                    else "partner_b" if "Partner B" in account_name else None
                )
                excluded_transactions[month_str].append(
                    {
                        "date": t.get("date", ""),
                        "description": t.get("payee") or t.get("description") or "",
                        "category": cat_title,
                        "owner": owner,
                        "amount": t.get("amount", 0) or 0,
                    }
                )
            if cat_title != "CC Payment (paired)":
                continue
            amount = t.get("amount", 0) or 0
            if amount <= 0:
                continue
            acct = (t.get("account") or {}).get("name", "") or ""
            if "CC" not in acct:
                continue
            cc_paydowns.setdefault(acct, {})
            cc_paydowns[acct][month_str] = cc_paydowns[acct].get(month_str, 0) + amount

    return {
        "months": months,
        "series": series,
        "cumulative": cumulative,
        "cats": cats,
        "paired_reimbs": all_paired_reimbs,
        "cc_paydowns": cc_paydowns,
        "excluded_transactions": excluded_transactions,
        "trips": [],
        "cumulative_by_section": _section_cumulatives(cats, len(months)),
        "accounting": aggregate_normalized_months(per_month),
    }


def _section_cumulatives(
    cats: Dict[str, Dict[str, Any]], n: int
) -> Dict[str, Dict[str, Any]]:
    """Sum partner paid values and totals per section across all months.
    Returns: {section_name: {partner_a: float, partner_b: float, total: float}}
    """
    out: Dict[str, Dict[str, Any]] = {}
    for cat, info in cats.items():
        sec = info.get("section", "unknown")
        if sec not in out:
            out[sec] = {"partner_a": 0.0, "partner_b": 0.0, "total": 0.0}
        partner_a_paid = info.get("partner_a_paid") or []
        partner_b_paid = info.get("partner_b_paid") or []
        tt = info.get("total") or []
        out[sec]["partner_a"] += sum(v or 0 for v in partner_a_paid)
        out[sec]["partner_b"] += sum(v or 0 for v in partner_b_paid)
        out[sec]["total"] += sum(v or 0 for v in tt)
    return out


def build(start: str, end: str) -> Dict[str, Any]:
    """One-shot: load all months between start and end, return the agg dict."""
    import datetime

    sy, sm = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    months = []
    y, mo = sy, sm
    while (y, mo) <= (ey, em):
        months.append(f"{y}-{mo:02d}")
        mo += 1
        if mo > 12:
            mo = 1
            y += 1
    ingested = ingest_months(months)
    agg = aggregate(ingested)
    return agg
