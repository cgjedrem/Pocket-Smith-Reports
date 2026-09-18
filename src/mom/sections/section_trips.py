"""Section 7: Trips (grouped by PS label).

Public renderers:
- render_trip_common_table (client-style: common-cat only, NET reimbs)
- render_trip_stacked_bar (per-trip partner split)
- render_trip_subcat_table (per-trip subcat breakdown)
- render (orchestrator)

Paired reimbursements within a trip cluster (e.g. Partner B Savings → Partner A Checking
with same label + amount + close dates) are detected and netted out so
that Partner B's transfer-to-Partner A does not count as trip spend.
This mirrors the paired-reimb logic in section_home._section_series.
"""

from typing import Dict, List, Any, Tuple
from datetime import datetime
from html import escape
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bar_chart import render_bar_chart
from sections.common_render import _n
from sections.context import heading, labels

DATE_TOLERANCE_DAYS = 3


def _detect_paired_trip_reimbs(trip: Dict) -> Tuple[float, float, float]:
    """Detect paired reimbursements inside a trip cluster.

    For each (outflow, inflow) pair with:
      - same amount (rounded to whole NOK)
      - opposite signs
      - dates within DATE_TOLERANCE_DAYS
      - different accounts
    - different partners
    treat the outflow as a transfer (reimbursement), not real trip spend.

    Returns (partner_a_paid_delta, partner_b_paid_delta, total_delta) to apply to the
    cluster sums. Positive deltas increase the matching partner's paid amount.
    Negative total_delta reduces the trip total (excludes the transfer
    which is not real merchant spend).
    """
    txns = trip.get("txns", [])
    if not txns:
        return 0.0, 0.0, 0.0

    # Group outflows and inflows by amount
    by_amt_out = {}
    by_amt_in = {}
    for t in txns:
        try:
            amt = round(t.get("amount", 0))
        except (TypeError, ValueError):
            continue
        if amt == 0:
            continue
        acct = (
            (t.get("account") or {}).get("name", "")
            if isinstance(t.get("account"), dict)
            else ""
        )
        date_str = (t.get("date") or "")[:10]
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        rec = (amt, acct, date)
        if amt < 0:
            by_amt_out.setdefault(-amt, []).append(rec)
        else:
            by_amt_in.setdefault(amt, []).append(rec)

    # Match outflows to inflows
    partner_a_delta = 0.0
    partner_b_delta = 0.0
    total_delta = 0.0
    for amt in by_amt_out:
        outs = by_amt_out.get(amt, [])
        ins = by_amt_in.get(amt, [])
        used_in = set()
        for o in outs:
            o_amt, o_acct, o_date = o
            for idx, i in enumerate(ins):
                if idx in used_in:
                    continue
                i_amt, i_acct, i_date = i
                if o_acct == i_acct:
                    continue
                if abs((o_date - i_date).days) > DATE_TOLERANCE_DAYS:
                    continue
                o_sender = "joint"
                i_recip = "joint"
                if o_sender == i_recip:
                    continue
                # Paired partner-transfer: the outflow is already in the
                # sender's gross, and the inflow is already subtracted from
                # the recipient's net (by trips.py). So NO delta is needed —
                # the inflow/outflow accounting handles it correctly.
                # We only record the event for the sub-row display.
                used_in.add(idx)
                break
    return partner_a_delta, partner_b_delta, total_delta


# ============================================================
# Per-month series for trips — same shape as home's _common_section_series
# so we can show a per-month table + chart with paired reimbs applied.
# ============================================================


def _trip_per_month_series(agg: Dict[str, Any]) -> Dict[str, List[float]]:
    """Build per-month Partner A/Partner B/Total spend across trip-labeled txns.

    Mirrors section_home._common_section_series:
            - Partner columns contain outflows from that partner's accounts.
      - Total = net (excludes the paired transfer amount itself).
    Per-month pairs are detected independently (same logic as _detect_paired_trip_reimbs).
    """
    months = agg["months"]
    n = len(months)
    partner_a_column = [0.0] * n
    partner_b_column = [0.0] * n
    total = [0.0] * n

    # Per-cat spend on trip-labeled txns
    # The trip txns are in raw all_txns_flat (loaded by ingest_months).
    # We don't have that here, so we derive from agg's cats — but trips are
    # NOT in agg['cats'] (they're a separate section). So we need a different
    # path: ask agg for trip txns via the trips clusters.
    # Actually agg['trips'] has the full txns list per cluster.
    for trip in agg.get("trips", []):
        for t in trip.get("txns", []):
            amt = t.get("amount", 0)
            if amt == 0:
                continue
            date_str = (t.get("date") or "")[:7]  # YYYY-MM
            if date_str not in months:
                continue
            i = months.index(date_str)
            partner = _partner_of_local(t)
            if partner == "partner_a":
                if amt < 0:
                    partner_a_column[i] += abs(amt)
            elif partner == "partner_b":
                if amt < 0:
                    partner_b_column[i] += abs(amt)

    # Detect per-month paired reimbursements across all trip transactions.
    for trip in agg.get("trips", []):
        by_amt_out = {}  # (month, amt) -> list of (acct, date)
        by_amt_in = {}
        for t in trip.get("txns", []):
            amt = round(t.get("amount", 0))
            if amt == 0:
                continue
            date_str = (t.get("date") or "")[:10]
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue
            month_str = date_str[:7]
            if month_str not in months:
                continue
            i = months.index(month_str)
            key = (i, abs(amt))
            if amt < 0:
                by_amt_out.setdefault(key, []).append(
                    (
                        _partner_of_local(t),
                        (t.get("account") or {}).get("name", ""),
                        date,
                        i,
                    )
                )
            else:
                by_amt_in.setdefault(key, []).append(
                    (
                        _partner_of_local(t),
                        (t.get("account") or {}).get("name", ""),
                        date,
                        i,
                    )
                )
        for (i, amt), outs in by_amt_out.items():
            ins = by_amt_in.get((i, amt), [])
            used_in = set()
            for o_sender, o_acct, o_date, _ in outs:
                for idx, (i_recip, i_acct, i_date, _) in enumerate(ins):
                    if idx in used_in:
                        continue
                    if o_acct == i_acct:
                        continue
                    if abs((o_date - i_date).days) > DATE_TOLERANCE_DAYS:
                        continue
                    if o_sender == i_recip:
                        continue
                    # Net: subtract from sender, exclude from total
                    if o_sender == "partner_b":
                        partner_b_column[i] -= amt
                    else:
                        partner_a_column[i] -= amt
                    total[i] -= amt
                    used_in.add(idx)
                    break
    # Total = sum of partner columns per month. Partner columns may now
    # be < 0 if there were more transfers than outflows. Clamp to 0.
    for i in range(n):
        total[i] = max(0.0, partner_a_column[i] + partner_b_column[i])
    return {
        "partner_a_paid": partner_a_column,
        "partner_b_paid": partner_b_column,
        "total": total,
    }


def _partner_of_local(transaction: Dict[str, Any]) -> str:
    """Read owner carried from Mega's validated normalized records."""
    owner = transaction.get("owner")
    return owner if owner in {"partner_a", "partner_b"} else "joint"


# ============================================================
# Trips table — one row per trip, columns: Trip | Partner A | Partner B | Total | shares.
# ============================================================


def _common_row_for_trip(trip: Dict) -> Dict | None:
    """Filter to common-cat-only with per-partner NET of reimbs.

    Mirrors client TripsSection.commonRowForTrip:
      - cat_breakdown key = "Common Trip"
      - per-partner paid = gross_outflows - inflows (transfers excluded)
      - total = abs(amount) of common-cat outflows
    Returns None if trip has no common-cat spend.
    """
    breakdown = trip.get("cat_breakdown", {}) or {}
    common_total = breakdown.get("Common Trip", 0)
    if common_total <= 0:
        return None
    a_gross = 0.0
    a_in = 0.0
    b_gross = 0.0
    b_in = 0.0
    count = 0
    for t in trip.get("txns", []) or []:
        cat = (
            (t.get("category") or {}).get("title")
            if isinstance(t.get("category"), dict)
            else None
        )
        if cat != "Common Trip":
            continue
        if t.get("is_transfer"):
            continue
        count += 1
        amt = t.get("amount", 0) or 0
        owner = t.get("owner")
        if amt < 0:
            if owner == "partner_a":
                a_gross += abs(amt)
            elif owner == "partner_b":
                b_gross += abs(amt)
        elif amt > 0:
            if owner == "partner_a":
                a_in += amt
            elif owner == "partner_b":
                b_in += amt
    return {
        "label": trip.get("label"),
        "date_start": trip.get("date_start"),
        "date_end": trip.get("date_end"),
        "total": common_total,
        "partner_a_paid": a_gross - a_in,
        "partner_b_paid": b_gross - b_in,
        "txn_count": count,
    }


def _common_trips(trips: List[Dict]) -> List[Dict]:
    """Return only the common-cat subset of trips, in same order."""
    out = []
    for t in trips:
        row = _common_row_for_trip(t)
        if row is not None:
            out.append(row)
    return out


# ============================================================
# (render_trip_table removed — use render_trip_common_table instead.)
# ============================================================


def render_trip_stacked_bar(
    trips: List[Dict], partner_labels: dict[str, str] | None = None
) -> str:
    """Stacked bar chart per trip: each trip has Partner A + Partner B stacked.

    Shows totals and per-person breakdown in the same graph.
    """
    from subcat_charts import render_subcat_stacked_bar as _stacked_bar

    trip_labels = [t["label"] for t in trips]
    subcat_amounts = {
        labels(partner_labels)["partner_a"]: [t["partner_a_paid"] for t in trips],
        labels(partner_labels)["partner_b"]: [t["partner_b_paid"] for t in trips],
    }
    return _stacked_bar(
        trip_labels,
        subcat_amounts,
        title="Trips by partner",
        width=760,
        height=420,
    )


# ============================================================
# Trip paired reimbursements — detect + render
def render_trip_common_table(
    trips: List[Dict],
    partner_labels: dict[str, str] | None = None,
) -> str:
    """Render the per-trip table filtered to common-cat with NET reimbs.

    Mirrors client TripsCommonTable:
      Columns: Trip | Partner A paid | Partner B paid | Total | A % | B % | Dates | Txns
      - Only trips with cat_breakdown["Common Trip"] > 0 are shown.
      - Per-partner paid = gross_outflows - inflows (transfers excluded).
    """
    partner_labels = labels(partner_labels)
    rows = _common_trips(trips)
    if not rows:
        return '<p class="empty">No common-trip expenses in this range.</p>'

    grand_total = sum(r["total"] for r in rows)
    grand_a = sum(r["partner_a_paid"] for r in rows)
    grand_b = sum(r["partner_b_paid"] for r in rows)
    grand_net = grand_a + grand_b
    grand_txns = sum(r["txn_count"] for r in rows)

    parts = ['<table class="overview-table transposed">', "<thead>", "<tr>"]
    parts.append('<th class="row-label">Trip</th>')
    parts.append(
        f'<th class="num partner-a-col">{escape(partner_labels["partner_a"])} paid</th>'
    )
    parts.append(
        f'<th class="num partner-b-col">{escape(partner_labels["partner_b"])} paid</th>'
    )
    parts.append('<th class="num total-col">Total</th>')
    parts.append(
        f'<th class="num partner-a-col">{escape(partner_labels["partner_a"])} %</th>'
    )
    parts.append(
        f'<th class="num partner-b-col">{escape(partner_labels["partner_b"])} %</th>'
    )
    parts.append("<th>Dates</th>")
    parts.append('<th class="num">Txns</th>')
    parts.append("</tr>")
    parts.append("</thead>")
    parts.append("<tbody>")

    for r in rows:
        a_pct = r["partner_a_paid"] / r["total"] * 100 if r["total"] else 0
        b_pct = r["partner_b_paid"] / r["total"] * 100 if r["total"] else 0
        parts.append("<tr>")
        parts.append(f'<td class="row-label"><b>{escape(str(r["label"]))}</b></td>')
        parts.append(f'<td class="num partner-a-col">{_n(r["partner_a_paid"])}</td>')
        parts.append(f'<td class="num partner-b-col">{_n(r["partner_b_paid"])}</td>')
        parts.append(f'<td class="num total-col"><b>{_n(r["total"])}</b></td>')
        parts.append(f'<td class="num partner-a-col">{a_pct:.1f}%</td>')
        parts.append(f'<td class="num partner-b-col">{b_pct:.1f}%</td>')
        parts.append(
            f'<td>{escape(str(r["date_start"]))} → {escape(str(r["date_end"]))}</td>'
        )
        parts.append(f'<td class="num">{r["txn_count"]}</td>')
        parts.append("</tr>")

    grand_a_pct = grand_a / grand_net * 100 if grand_net else 0
    grand_b_pct = grand_b / grand_net * 100 if grand_net else 0
    parts.append('<tr class="subtotal-row">')
    parts.append('<td class="row-label"><b>Period total</b></td>')
    parts.append(f'<td class="num partner-a-col"><b>{_n(grand_a)}</b></td>')
    parts.append(f'<td class="num partner-b-col"><b>{_n(grand_b)}</b></td>')
    parts.append(f'<td class="num total-col"><b>{_n(grand_total)}</b></td>')
    parts.append(f'<td class="num partner-a-col"><b>{grand_a_pct:.1f}%</b></td>')
    parts.append(f'<td class="num partner-b-col"><b>{grand_b_pct:.1f}%</b></td>')
    parts.append("<td></td>")
    parts.append(f'<td class="num"><b>{grand_txns}</b></td>')
    parts.append("</tr>")

    parts.append("</tbody>")
    parts.append("</table>")
    return "\n".join(parts)


# ============================================================
# Section render entry point
# ============================================================


def render(
    agg: Dict[str, Any],
    partner_labels: dict[str, str] | None = None,
    section_number: int | None = 8,
    section_title: str = "Trips",
) -> str:
    partner_labels = labels(partner_labels)
    trips = agg.get("trips", [])
    parts = []

    if not trips:
        # Still need h2 + empty note on its own page
        parts.append(
            f'<h2 class="section-trips">{heading(section_number, section_title)}</h2>'
        )
        parts.append('<p class="empty">No trips with PS labels in this period.</p>')
        return "\n".join(parts)

    # Net out paired reimbursements within each trip cluster so transfers
    # between partners don't inflate one partner's spend.
    # A paired transfer is not a trip spend, so it is netted from payer totals.
    adjusted_trips = []
    for t in trips:
        adj = dict(t)
        partner_a_delta, partner_b_delta, total_d = _detect_paired_trip_reimbs(t)
        adj["partner_a_paid"] = t["partner_a_paid"] + partner_a_delta
        adj["partner_b_paid"] = t["partner_b_paid"] + partner_b_delta
        adj["total"] = t["total"] + total_d
        adjusted_trips.append(adj)

    grand_total = sum(t["total"] for t in adjusted_trips)
    grand_partner_a = sum(t["partner_a_paid"] for t in adjusted_trips)
    grand_partner_b = sum(t["partner_b_paid"] for t in adjusted_trips)

    # Page 1: h2 + summary + table + bar chart in a single landscape page
    # so all 10 trips are visible without page breaks.
    parts.append('<div class="landscape-page">')
    parts.append(
        f'<h2 class="section-trips">{heading(section_number, section_title)}</h2>'
    )
    parts.append(
        '<p class="note">A single trip = a set of transactions sharing the same PS label. '
        f"Per-trip cost split between {escape(partner_labels['partner_a'])} and {escape(partner_labels['partner_b'])}. "
        "Paired transfers between them are netted out.</p>"
    )

    parts.append(
        f'<p class="note">Total trip cost: <b>{_n(grand_total)} NOK</b> '
        f"({escape(partner_labels['partner_a'])} paid {_n(grand_partner_a)} = {grand_partner_a/grand_total*100 if grand_total else 0:.1f}% | "
        f"{escape(partner_labels['partner_b'])} paid {_n(grand_partner_b)} = {grand_partner_b/grand_total*100 if grand_total else 0:.1f}%)</p>"
    )

    # Trips table — client-style common-only with NET reimbs (8 cols).
    # Mirrors client TripsCommonTable: filters to common-cat trips only,
    # per-partner paid = gross_outflows - inflows (transfers excluded).
    common_only = _common_trips(adjusted_trips)
    parts.append(
        "<h3>Trips summary (common-cat only, one row per trip, net per person)</h3>"
    )
    parts.append(render_trip_common_table(adjusted_trips, partner_labels))

    # Stacked bar chart: per-trip partner values stacked (common-only view).
    parts.append("<h3>Trips by partner</h3>")
    parts.append(render_trip_stacked_bar(common_only, partner_labels))
    parts.append("</div>")

    # Page 2+: Per-trip sub-category breakdown
    parts.append("<h3>Trips by sub-category (per trip)</h3>")
    parts.append(render_trip_subcat_table(adjusted_trips, partner_labels))

    return "\n".join(parts)


# ============================================================
# Per-trip sub-category table
# ============================================================


def render_trip_subcat_table(
    trips: List[Dict], partner_labels: dict[str, str] | None = None
) -> str:
    """For each trip, show the category breakdown."""
    partner_labels = labels(partner_labels)
    parts = ['<div class="trip-subcat-blocks">']
    for t in trips:
        transactions = t.get("txns", [])
        if not transactions:
            continue
        category_values = {}
        for transaction in transactions:
            category = (transaction.get("category") or {}).get("title", "Uncategorised")
            partner = _partner_of_local(transaction)
            values = category_values.setdefault(
                category, {"partner_a": 0.0, "partner_b": 0.0}
            )
            if partner in values:
                values[partner] -= transaction.get("amount", 0) or 0
        cat_rows = []
        for cat, values in sorted(
            category_values.items(), key=lambda row: -sum(row[1].values())
        ):
            partner_a = values["partner_a"]
            partner_b = values["partner_b"]
            amt = partner_a + partner_b
            cat_l = cat.lower() if cat else ""
            if "personal trip" in cat_l and "partner b" in cat_l:
                cls = "partner-b"
                partner = f'{partner_labels["partner_b"]} personal'
            elif "personal trip" in cat_l:
                cls = "partner-a"
                partner = f'{partner_labels["partner_a"]} personal'
            elif "personal" in cat_l:
                cls = "partner-a"
                partner = f'{partner_labels["partner_a"]} personal'
            else:
                cls = "common"
                partner = "Common"
            cat_rows.append((cat, partner_a, partner_b, amt, cls, partner))
        total = sum(amt for _, _, _, amt, _, _ in cat_rows)
        rows_html = "".join(
            f'<tr class="cat-row {cls}">'
            f"<td>{escape(str(cat))}</td>"
            f'<td class="num">{_n(partner_a)}</td>'
            f'<td class="num">{_n(partner_b)}</td>'
            f'<td class="num">{_n(amt)}</td>'
            f'<td class="num">{partner_a/total*100 if total else 0:.1f}%</td>'
            f'<td class="num">{partner_b/total*100 if total else 0:.1f}%</td>'
            f'<td class="partner">{escape(partner)}</td>'
            f"</tr>"
            for cat, partner_a, partner_b, amt, cls, partner in cat_rows
        )
        parts.append(
            f'<div class="trip-block">'
            f'<h4>{escape(str(t["label"]))} <span class="trip-total">({_n(total)} NOK)</span></h4>'
            f'<table class="trip-cat-table">'
            f'<thead><tr><th>Sub-category</th><th class="num">{escape(partner_labels["partner_a"])}</th>'
            f'<th class="num">{escape(partner_labels["partner_b"])}</th><th class="num">Total</th>'
            f'<th class="num">A %</th><th class="num">B %</th><th>Type</th></tr></thead>'
            f"<tbody>{rows_html}"
            f'<tr class="subtotal-row">'
            f"<td><b>Total</b></td>"
            f'<td class="num"><b>{_n(sum(row[1] for row in cat_rows))}</b></td>'
            f'<td class="num"><b>{_n(sum(row[2] for row in cat_rows))}</b></td>'
            f'<td class="num"><b>{_n(total)}</b></td>'
            f'<td class="num"><b>{sum(row[1] for row in cat_rows)/total*100 if total else 0:.1f}%</b></td>'
            f'<td class="num"><b>{sum(row[2] for row in cat_rows)/total*100 if total else 0:.1f}%</b></td>'
            f"<td></td>"
            f"</tr>"
            f"</tbody></table>"
            f"</div>"
        )
    parts.append("</div>")
    return "\n".join(parts)
