#!/usr/bin/env python3
"""trend11.py — compute configured-period trend series for the v7 mega report.

Inputs: configured PocketSmith-compatible monthly JSON exports.
Outputs: dict per metric (income, real_spend, net_cash, savings, partner shares)
         per category (top-N), per merchant (repeating top-N).

Reuses v5 wallet/tally via the existing compare._load_wallet() pattern.
"""

import json
import os
import sys
from collections import defaultdict, Counter
from datetime import date as D

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
V5_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "v4_pipeline")
sys.path.insert(0, V5_DIR)
sys.path.insert(0, SCRIPT_DIR)

from data_loader import load as v5_load
from tally import compute as v5_tally
from wallet import compute as v5_wallet
from compare import _enrich_txns, _resolve_month_path, MONTH_NAMES


def _partner_buckets(values, prefix):
    """Return the two partner buckets for a namespaced totals mapping."""
    buckets = [value for key, value in values.items() if key.startswith(prefix)]
    if len(buckets) != 2:
        raise ValueError(f"Expected exactly two {prefix} partner buckets")
    return buckets


def _partner_values(values, suffix):
    """Return the two partner values for a namespaced wallet row."""
    partners = [value for key, value in values.items() if key.endswith(suffix)]
    if len(partners) != 2:
        raise ValueError(f"Expected exactly two {suffix} partner values")
    return partners


def _configured_months():
    """Read report months from POCKETSMITH_REPORT_MONTHS (YYYY-MM list)."""
    values = [
        value.strip()
        for value in os.environ.get("POCKETSMITH_REPORT_MONTHS", "").split(",")
        if value.strip()
    ]
    result = []
    for value in values:
        yyyy, mm = value.split("-", 1)
        mm_int = int(mm)
        if len(yyyy) != 4 or not 1 <= mm_int <= 12:
            raise ValueError(f"Invalid report month: {value}")
        result.append((value, MONTH_NAMES[mm_int - 1], int(yyyy)))
    return result


MONTHS = _configured_months()


def _vault_path(yyyy_mm, name, yyyy):
    """Resolve one configured month from the strict source contract."""
    return _resolve_month_path(yyyy_mm)


def _load_month(yyyy_mm):
    """Return (totals, wallet, txns) for one month. None if missing."""
    for a, b, yyyy in MONTHS:
        if a == yyyy_mm:
            name = b
            break
    else:
        return None
    p = _vault_path(yyyy_mm, name, yyyy)
    txns = _enrich_txns(v5_load(yyyy_mm, p))
    totals = v5_tally(txns, {})
    wallet = v5_wallet(totals)
    return totals, wallet, txns


def compute_all():
    """Return ordered list of (label, totals, wallet, txns) for configured months."""
    series = []
    for yyyy_mm, name, yyyy in MONTHS:
        r = _load_month(yyyy_mm)
        t, w, tx = r
        series.append((name.title(), t, w, tx))
    return series


def _sum_dict(d):
    """Sum a dict's values, handling nested dicts with 'total' key."""
    s = 0.0
    for v in d.values():
        if isinstance(v, (int, float)):
            s += v
        elif isinstance(v, dict):
            s += v.get("total", 0)
    return s


def real_spend_series(series):
    """Real spend = common plus both personal buckets (absolute)."""
    out = []
    for label, t, w, tx in series:
        if t is None:
            out.append(None)
            continue
        personal_a, personal_b = _partner_buckets(t, "personal_")
        s = (
            _sum_dict(t.get("common", {}))
            + _sum_dict(personal_a)
            + _sum_dict(personal_b)
        )
        out.append(round(s, 0))
    return out


def income_series(series):
    """Total household income (both partners + 3rd party)."""
    out = []
    for label, t, w, tx in series:
        if t is None:
            out.append(None)
            continue
        inc = t.get("income", {})
        s = 0.0
        salary_a, salary_b = _partner_buckets(inc, "salary_")
        s += _sum_dict(salary_a) if isinstance(salary_a, dict) else salary_a or 0
        s += _sum_dict(salary_b) if isinstance(salary_b, dict) else salary_b or 0
        s += (
            _sum_dict(inc.get("third_party", {}))
            if isinstance(inc.get("third_party"), dict)
            else 0
        )
        out.append(round(s, 0))
    return out


def savings_series(series):
    out = []
    for label, t, w, tx in series:
        if t is None:
            out.append(None)
            continue
        sav = t.get("savings", {})
        # savings may be a dict with sub-buckets or a scalar
        s = _sum_dict(sav) if isinstance(sav, dict) else (sav or 0)
        out.append(round(s, 0))
    return out


def metric_series(series, key_path):
    """Pull a single scalar per month from totals. key_path is dotted."""
    out = []
    for label, t, w, tx in series:
        if t is None:
            out.append(None)
            continue
        cur = t
        for k in key_path.split("."):
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                cur = None
                break
        out.append(cur)
    return out


def wallet_series(series, key_path):
    """Pull a single scalar per month from wallet dict."""
    out = []
    for label, t, w, tx in series:
        if w is None:
            out.append(None)
            continue
        cur = w
        for k in key_path.split("."):
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                cur = None
                break
        out.append(cur)
    return out


def per_category_series(series, top_n=15):
    """Return list of (cat_name, [amount_per_month...]).

    Categories = common and partner-specific categories combined.
    Rank by total across all months. Top N only.
    """
    cat_totals = defaultdict(lambda: [0.0] * len(series))
    cat_names = {}
    for i, (label, t, w, tx) in enumerate(series):
        if t is None:
            continue
        all_cats = {}
        all_cats.update(t.get("common", {}))
        personal_a, personal_b = _partner_buckets(t, "personal_")
        all_cats.update(personal_a)
        all_cats.update(personal_b)
        for c, vals in all_cats.items():
            v = vals if isinstance(vals, (int, float)) else vals.get("total", 0)
            cat_totals[c][i] = abs(float(v))
            cat_names[c] = c
    # Rank
    ranked = sorted(cat_totals.items(), key=lambda x: sum(x[1]), reverse=True)
    return [(name, series_vals) for name, series_vals in ranked[:top_n]]


def per_parent_category_series(series, top_n=12):
    """Parent-category rollup with paired-reimbursement split.

    Returns ordered list of dicts:
      {
        'parent': str,                  # e.g. 'Home'
        'gross_per_month': [float...],  # sub-cat real spend (HM sub-cat total)
        'paired_reimb_per_month': [float...],  # parent-cat paired legs (count*gross avg)
        'paired_reimb_count_per_month': [int...],
        'sub_cats': {sub_name: [per_month...]},  # e.g. {'Home Maintenance': [...]}
        'total_all_months': float,      # rank key
      }

    The renderer can show:
    Row 1: Parent category gross spend
    Row 2: Indented subcategory spend
    Row 3: Paired reimbursement leg
    Row 4: Parent net after paired reimbursement

    Top N ranked by gross+paired across all months.
    """
    parent_gross = defaultdict(lambda: [0.0] * len(series))
    parent_paired_gross = defaultdict(lambda: [0.0] * len(series))
    parent_paired_count = defaultdict(lambda: [0] * len(series))
    sub_cats_per_parent = defaultdict(lambda: defaultdict(lambda: [0.0] * len(series)))
    parent_sub_map = {}  # parent_name → set of sub-cat names (to detect grouping)

    # Heuristic: assume that if a sub-cat name is "Foo Maintenance" / "Foo Supplies"
    # and "Foo" is a top-level cat, the parent is "Foo". Apply this for the known
    # parents in PARENT_TO_SUB_ALIAS. Also handle "Home Maintenance" → "Home".
    from tally import PARENT_TO_SUB_ALIAS

    sub_to_parent = {v: k for k, v in PARENT_TO_SUB_ALIAS.items()}
    # Plus general heuristic: if cat name starts with known parent name + ' '
    # e.g. "Home Maintenance" → "Home", "Home Supplies" → "Home"

    for i, (label, t, w, tx) in enumerate(series):
        if t is None:
            continue
        common = t.get("common", {})
        personal_a, personal_b = _partner_buckets(t, "personal_")
        # Map every sub-cat to its parent. The parent is identified by:
        # (a) sub_to_parent (alias map), or
        # (b) cat starts with "<Parent> " (e.g. "Home Maintenance" → "Home")
        # (c) the cat itself has a paired_reimbursement_gross > 0 (i.e. it's
        #     the parent cat itself in PS, so render as own parent)
        for cat_name, vals in common.items():
            v = vals.get("total", 0) if isinstance(vals, dict) else vals
            paired_g = (
                vals.get("paired_reimbursement_gross", 0)
                if isinstance(vals, dict)
                else 0
            )
            paired_c = (
                vals.get("paired_reimbursement_count", 0)
                if isinstance(vals, dict)
                else 0
            )
            # Determine parent
            if cat_name in sub_to_parent:
                parent = sub_to_parent[cat_name]
            elif cat_name in PARENT_TO_SUB_ALIAS:
                parent = cat_name
            else:
                # Heuristic: split on first space; "Home Maintenance" → parent "Home"
                # Only apply if the prefix is a known parent (e.g. PARENT_TO_SUB_ALIAS key)
                parts = cat_name.split(" ", 1)
                if len(parts) == 2 and parts[0] in PARENT_TO_SUB_ALIAS:
                    parent = parts[0]
                else:
                    parent = cat_name  # cat IS its own parent
            # Add to parent
            if cat_name == parent:
                # The cat itself is the parent (e.g. "Home" with paired_reimbursement)
                # The real spend total here is the sub-cat alias "Home Maintenance" already
                # captured under parent "Home" via the alias. So this branch is the
                # gross/paired on the parent slot itself.
                parent_gross[parent][i] += abs(float(v))
                parent_paired_gross[parent][i] += float(paired_g)
                parent_paired_count[parent][i] += int(paired_c)
            else:
                # sub-cat, route to parent
                parent_gross[parent][i] += abs(float(v))
                sub_cats_per_parent[parent][cat_name][i] += abs(float(v))
                # If the sub-cat also has paired gross, attach to parent
                if paired_g > 0:
                    parent_paired_gross[parent][i] += float(paired_g)
                    parent_paired_count[parent][i] += int(paired_c)
        # Personal cats don't have parent mapping; bucket under own name
        for cat_name, amt in personal_a.items():
            if cat_name in sub_to_parent:
                parent = sub_to_parent[cat_name]
            else:
                parent = cat_name
            parent_gross[parent][i] += abs(float(amt))
        for cat_name, amt in personal_b.items():
            if cat_name in sub_to_parent:
                parent = sub_to_parent[cat_name]
            else:
                parent = cat_name
            parent_gross[parent][i] += abs(float(amt))

    out = []
    for parent in parent_gross:
        all_months_gross = parent_gross[parent]
        all_months_paired = parent_paired_gross[parent]
        all_months_paired_count = parent_paired_count[parent]
        total_all = sum(all_months_gross) + sum(all_months_paired)
        out.append(
            {
                "parent": parent,
                "gross_per_month": all_months_gross,
                "paired_reimb_per_month": all_months_paired,
                "paired_reimb_count_per_month": all_months_paired_count,
                "sub_cats": dict(sub_cats_per_parent[parent]),
                "total_all_months": total_all,
            }
        )
    out.sort(key=lambda x: x["total_all_months"], reverse=True)
    return out[:top_n]


def per_merchant_series(series, min_months=3, top_n=10):
    """Top repeating merchants: payee appears in >= min_months, ranked by total.

    Returns [(payee, [amount_per_month...]), ...]
    Negative amounts only (spend). Excludes transfers.
    """
    payee_month = defaultdict(lambda: defaultdict(float))
    payee_total = defaultdict(float)
    payee_count_months = defaultdict(int)
    for i, (label, t, w, tx) in enumerate(series):
        for x in tx:
            amt = float(x.get("amount", 0))
            if amt >= 0:  # income
                continue
            p = (x.get("payee") or "").strip()
            if not p:
                continue
            # Normalize: strip "Fra:" prefixes, dates, common prefixes
            p_norm = p.upper()
            for prefix in ["FRA: ", "BETALT: "]:
                if prefix in p_norm:
                    p_norm = p_norm.split(prefix, 1)[-1]
            # Take first chunk before digits/date
            p_norm = p_norm.split("  ")[0].split(" BETALT")[0].strip()
            if len(p_norm) < 3:
                continue
            payee_month[p_norm][i] += abs(amt)
            payee_total[p_norm] += abs(amt)
        # after processing all txns, count months
        for p in payee_month:
            if payee_month[p].get(i, 0) > 0:
                payee_count_months[p] = max(
                    payee_count_months[p],
                    sum(1 for m in range(len(series)) if payee_month[p].get(m, 0) > 0),
                )
    # filter
    cand = [
        (p, v) for p, v in payee_total.items() if payee_count_months[p] >= min_months
    ]
    cand.sort(key=lambda x: x[1], reverse=True)
    out = []
    for p, _ in cand[:top_n]:
        vals = [payee_month[p].get(i, 0.0) for i in range(len(series))]
        out.append((p, vals))
    return out


def pct_partner_shares(series):
    """Return each partner's household real-spend share per month."""
    partner_a_pct, partner_b_pct = [], []
    for label, t, w, tx in series:
        if w is None:
            partner_a_pct.append(None)
            partner_b_pct.append(None)
            continue
        rows = w.get("rows", {})
        partner_a_cash = partner_b_cash = 0
        for row in rows.values():
            cash_a, cash_b = _partner_values(row, "_cash")
            partner_a_cash += cash_a
            partner_b_cash += cash_b
        tot = partner_a_cash + partner_b_cash
        if tot == 0:
            partner_a_pct.append(None)
            partner_b_pct.append(None)
            continue
        partner_a_pct.append(round(partner_a_cash / tot * 100, 1))
        partner_b_pct.append(round(partner_b_cash / tot * 100, 1))
    return partner_a_pct, partner_b_pct


if __name__ == "__main__":
    s = compute_all()
    print(f"Loaded {sum(1 for _, t, _, _ in s if t is not None)}/{len(s)} months")
    inc = income_series(s)
    print("income:", inc)
    rs = real_spend_series(s)
    print("real_spend:", rs)
    sv = savings_series(s)
    print("savings:", sv)
    partner_a_share, partner_b_share = pct_partner_shares(s)
    print("%partner_a:", partner_a_share)
    print("%partner_b:", partner_b_share)
    pcats = per_category_series(s, top_n=5)
    for name, vals in pcats:
        print(f"  {name:30s} {vals}")
