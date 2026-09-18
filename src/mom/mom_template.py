"""HTML template for the MoM (Month-on-Month) comparison report.

Same visual language as v4 monthly (CSS, fonts, KPI cards, tables).
Sections:
  1. KPI Cover (cumulative + per-partner)
  2. Section 1: Income
  3. Section 2: Savings
  4. Section 3: Home
  5. Section 4: Common
    6. Section 5: Personal (Partner A / Partner B)
  7. Section 6: Excluded
  8. Section 6b: CC Paydowns by Card
  9. Section 7: Trips
  10. Section 8: Recommendations
  11. Appendices
"""

from typing import Dict, List, Any
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from line_chart import render_line_chart  # noqa: E402
from bar_chart import render_bar_chart  # noqa: E402
from compare import section_totals_per_month  # noqa: E402

# CSS — same as v4 monthly
_CSS = """
@page { size: A4; margin: 12mm; }
@page landscape { size: A4 landscape; margin: 10mm; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
       color: #1a1a1a; margin: 8px; font-size: 12pt; line-height: 1.35; }
.landscape-page { page: landscape; }
h1 { font-size: 26pt; margin-bottom: 4px; text-align: center; color: #1f77b4; font-weight: 700; }
h2 { font-size: 18pt; margin-top: 0; border-bottom: 2px solid #1f77b4; padding-bottom: 4px;
     page-break-before: always; page-break-after: avoid; }
h3 { font-size: 14pt; margin-top: 12px; color: #333; }
.period { text-align: center; color: #555; font-size: 12pt; margin-bottom: 14px; }
.kpi-row { display: flex; gap: 12px; margin: 12px 0 18px 0; }
.kpi-card { flex: 1; background: #f0f7fc; border: 1px solid #1f77b4; border-radius: 6px;
            padding: 12px; text-align: center; }
.kpi-card .label { color: #555; font-size: 10pt; }
.kpi-card .value { font-size: 22pt; font-weight: 700; color: #1f77b4; }
.kpi-card .kpi-pct { color: #555; font-size: 9pt; margin-top: 6px; }
.kpi-card.red .value { color: #d62728; }
.kpi-card.green .value { color: #2ca02c; }
.partner-row { display: flex; gap: 12px; margin: 12px 0 18px 0; }
.partner-box { flex: 1; border: 1px solid #ccc; border-radius: 6px; padding: 12px; }
.partner-box h3 { margin-top: 0; }
.partner-box.partner-a { border-color: #1f77b4; }
.partner-box.partner-b { border-color: #ff7f0e; }
.partner-box .row { display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #eee; }
.partner-box .row:last-child { border-bottom: none; }
.partner-box .label { color: #555; }
.partner-box .val { font-weight: 700; }
.partner-box .val.pos { color: #2ca02c; }
.partner-box .val.neg { color: #d62728; }
table.cat-table { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 10pt; }
table.cat-table.landscape { font-size: 9pt; }
table.cat-table th { background: #f0f7fc; padding: 6px 8px; text-align: left; border-bottom: 2px solid #1f77b4; }
table.cat-table td { padding: 4px 8px; border-bottom: 1px solid #eee; }
table.cat-table td.num { text-align: right; font-variant-numeric: tabular-nums; }
table.cat-table tr.subtotal td { border-top: 1px solid #1f77b4; background: #f9f9f9; font-weight: 700; }
table.cat-table tr.reimb-row td { color: #777; font-style: italic; }
table.tx-table { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 8pt; }
table.tx-table th { background: #f0f7fc; padding: 4px; text-align: left; }
table.tx-table td { padding: 3px 4px; border-bottom: 1px solid #f0f0f0; }
table.tx-table td.num { text-align: right; }
svg.line-chart { width: 100%; height: auto; max-width: 720px; display: block; margin: 8px auto; }
.recommendation { background: #fff8e1; border-left: 4px solid #ff9800; padding: 8px 12px;
                  margin: 6px 0; font-size: 11pt; }
.recommendation .num { color: #ff9800; font-weight: 700; }
.action { background: #e8f5e9; border-left: 4px solid #2ca02c; padding: 8px 12px;
          margin: 6px 0; font-size: 11pt; }
.action .num { color: #2ca02c; font-weight: 700; }
.action .tip { font-style: italic; color: #555; font-size: 10pt; margin-top: 4px; }
.observation { background: #f5f5f5; border-left: 4px solid #888; padding: 6px 10px;
               margin: 4px 0; font-size: 10pt; }
.observation .num { color: #888; font-weight: 700; }
p.note { font-size: 9pt; color: #666; margin: 6px 0; }
p.empty { color: #999; font-style: italic; }
"""


def _n(v) -> str:
    """Format a number as comma-separated integer."""
    try:
        return f"{round(float(v)):,}"
    except (TypeError, ValueError):
        return str(v)


def _pct(v: float) -> str:
    """Format a 0-1 fraction as percentage."""
    try:
        return f"{float(v) * 100:.1f}%"
    except (TypeError, ValueError):
        return "0.0%"


def _render_kpi_cover(agg: Dict[str, Any]) -> str:
    cum = agg["cumulative"]
    inc = cum["income"]["total"]
    spend = cum["real_spend"]["total"]
    nc = cum["net_cash"]["total"]
    sav = cum["savings"]["total"]
    # Per-person % of total
    inc_partner_a_pct = cum["income"]["partner_a"] / inc * 100 if inc else 0
    inc_partner_b_pct = cum["income"]["partner_b"] / inc * 100 if inc else 0
    spend_partner_a_pct = cum["real_spend"]["partner_a"] / spend * 100 if spend else 0
    spend_partner_b_pct = cum["real_spend"]["partner_b"] / spend * 100 if spend else 0
    sav_partner_a_pct = cum["savings"]["net_partner_a"] / sav * 100 if sav else 0
    sav_partner_b_pct = cum["savings"]["net_partner_b"] / sav * 100 if sav else 0
    # Net cash per person
    nc_partner_a = cum["net_cash"]["partner_a"]
    nc_partner_b = cum["net_cash"]["partner_b"]
    nc_partner_a_pct = nc_partner_a / nc * 100 if nc else 0
    nc_partner_b_pct = nc_partner_b / nc * 100 if nc else 0

    nc_class = "red" if nc < 0 else "green"
    sav_class = "red" if sav < 0 else "green"

    parts = []
    # Top: 4 cumulative KPI cards with per-person % below each
    parts.append('<div class="kpi-row">')
    parts.append(
        f'<div class="kpi-card green">'
        f'<div class="label">Total Income (cumulative)</div>'
        f'<div class="value">{_n(inc)}</div>'
        f'<div class="kpi-pct">Partner A {_pct(inc_partner_a_pct/100)} | Partner B {_pct(inc_partner_b_pct/100)}</div>'
        f"</div>"
    )
    parts.append(
        f'<div class="kpi-card">'
        f'<div class="label">Real Spend (cumulative)</div>'
        f'<div class="value">{_n(spend)}</div>'
        f'<div class="kpi-pct">Partner A {_pct(spend_partner_a_pct/100)} | Partner B {_pct(spend_partner_b_pct/100)}</div>'
        f"</div>"
    )
    parts.append(
        f'<div class="kpi-card {nc_class}">'
        f'<div class="label">Net Cash (cumulative)</div>'
        f'<div class="value">{_n(nc)}</div>'
        f'<div class="kpi-pct">Partner A {_n(nc_partner_a)} ({_pct(nc_partner_a_pct/100)}) | Partner B {_n(nc_partner_b)} ({_pct(nc_partner_b_pct/100)})</div>'
        f"</div>"
    )
    parts.append(
        f'<div class="kpi-card {sav_class}">'
        f'<div class="label">Net Savings (cumulative)</div>'
        f'<div class="value">{_n(sav)}</div>'
        f'<div class="kpi-pct">Partner A {_pct(sav_partner_a_pct/100)} | Partner B {_pct(sav_partner_b_pct/100)}</div>'
        f"</div>"
    )
    parts.append("</div>")

    # Per-partner boxes
    parts.append('<div class="partner-row">')
    # Partner A box
    nc_partner_a_class = "pos" if nc_partner_a >= 0 else "neg"
    sav_partner_a = cum["savings"]["net_partner_a"]
    sav_partner_a_class = "pos" if sav_partner_a >= 0 else "neg"
    parts.append('<div class="partner-box partner-a">')
    parts.append("<h3>Partner A (cumulative)</h3>")
    parts.append(
        f'<div class="row"><span class="label">Income</span><span class="val">{_n(cum["income"]["partner_a"])}</span></div>'
    )
    parts.append(
        f'<div class="row"><span class="label">Real spend</span><span class="val">{_n(cum["real_spend"]["partner_a"])}</span></div>'
    )
    parts.append(
        f'<div class="row"><span class="label">Net cash</span><span class="val {nc_partner_a_class}">{_n(nc_partner_a)}</span></div>'
    )
    parts.append(
        f'<div class="row"><span class="label">Net saved</span><span class="val {sav_partner_a_class}">{_n(sav_partner_a)}</span></div>'
    )
    parts.append("</div>")
    # Partner B box
    nc_partner_b_class = "pos" if nc_partner_b >= 0 else "neg"
    sav_partner_b = cum["savings"]["net_partner_b"]
    sav_partner_b_class = "pos" if sav_partner_b >= 0 else "neg"
    parts.append('<div class="partner-box partner-b">')
    parts.append("<h3>Partner B (cumulative)</h3>")
    parts.append(
        f'<div class="row"><span class="label">Income</span><span class="val">{_n(cum["income"]["partner_b"])}</span></div>'
    )
    parts.append(
        f'<div class="row"><span class="label">Real spend</span><span class="val">{_n(cum["real_spend"]["partner_b"])}</span></div>'
    )
    parts.append(
        f'<div class="row"><span class="label">Net cash</span><span class="val {nc_partner_b_class}">{_n(nc_partner_b)}</span></div>'
    )
    parts.append(
        f'<div class="row"><span class="label">Net saved</span><span class="val {sav_partner_b_class}">{_n(sav_partner_b)}</span></div>'
    )
    parts.append("</div>")
    parts.append("</div>")
    return "\n".join(parts)


def _render_overview_table(agg: Dict[str, Any], section_name: str) -> str:
    """Render the per-month table for a given section.

    The table is split into TWO halves to keep it readable:
      - Part 1: months 1-6 + Total
      - Part 2: months 7-11 + Total

    Each half includes per-partner percentages per month.
    """
    months = agg["months"]
    series = agg["series"]
    if not months:
        return '<p class="empty">No data.</p>'

    # Choose the data series + label based on section_name
    if section_name == "Income":
        rows = [
            ("Partner A", series["income"]["partner_a"]),
            ("Partner B", series["income"]["partner_b"]),
            ("Total", series["income"]["total"]),
        ]
    elif section_name == "Savings":
        rows = [
            ("Partner A net saved", series["savings"]["net_partner_a"]),
            ("Partner B net saved", series["savings"]["net_partner_b"]),
            ("Total", series["savings"]["total"]),
        ]
    elif section_name == "Real Spend":
        rows = [
            ("Partner A", series["real_spend"]["partner_a"]),
            ("Partner B", series["real_spend"]["partner_b"]),
            ("Total", series["real_spend"]["total"]),
        ]
    elif section_name == "Net Cash":
        rows = [
            ("Partner A", series["net_cash"]["partner_a"]),
            ("Partner B", series["net_cash"]["partner_b"]),
            ("Total", series["net_cash"]["total"]),
        ]
    else:
        return f'<p class="empty">Unknown section: {section_name}</p>'

    # Split months into 2 halves
    mid = (len(months) + 1) // 2
    halves = [(months[:mid], "1st half"), (months[mid:], "2nd half")]

    parts = []
    for half_months, half_label in halves:
        if not half_months:
            continue
        start_index = months.index(half_months[0])
        parts.append('<div class="landscape-page">')
        parts.append(f"<h3>Overview table ({half_label})</h3>")
        parts.append('<table class="cat-table landscape"><thead><tr>')
        parts.append(f"<th>{section_name}</th>")
        for m in half_months:
            parts.append(f'<th class="num">{m[2:].replace("-", "/")}</th>')
        parts.append('<th class="num">Total</th>')
        parts.append("</tr></thead><tbody>")

        for name, vals in rows:
            parts.append(f"<tr><td>{name}</td>")
            for v in vals[start_index : start_index + len(half_months)]:
                parts.append(f'<td class="num">{_n(v) if v else ""}</td>')
            half_total = sum(vals[start_index : start_index + len(half_months)])
            parts.append(f'<td class="num"><b>{_n(half_total)}</b></td></tr>')

        # Per-person % row for "Total" sections
        if name == "Total":
            total_vals = vals
            partner_a_values = next((v for nm, v in rows if nm == "Partner A"), [])
            partner_b_values = next((v for nm, v in rows if nm == "Partner B"), [])
            parts.append(
                '<tr style="background:#f9f9f9"><td><i>Partner A % of total</i></td>'
            )
            for i in range(start_index, start_index + len(half_months)):
                v_total = total_vals[i] if i < len(total_vals) else 0
                partner_value = partner_a_values[i] if i < len(partner_a_values) else 0
                pct = partner_value / v_total * 100 if v_total else 0
                parts.append(f'<td class="num"><i>{pct:.1f}%</i></td>')
            parts.append('<td class="num"></td></tr>')
            parts.append(
                '<tr style="background:#f9f9f9"><td><i>Partner B % of total</i></td>'
            )
            for i in range(start_index, start_index + len(half_months)):
                v_total = total_vals[i] if i < len(total_vals) else 0
                partner_value = partner_b_values[i] if i < len(partner_b_values) else 0
                pct = partner_value / v_total * 100 if v_total else 0
                parts.append(f'<td class="num"><i>{pct:.1f}%</i></td>')
            parts.append('<td class="num"></td></tr>')

        parts.append("</tbody></table>")
        parts.append("</div>")

    return "\n".join(parts)


def _render_section_section(agg: Dict[str, Any], section: str) -> str:
    """Render a v4-style section (Home/Common/Personal/Excluded)
    with per-cat per-month table. Uses LANDSCAPE layout, split into 2 halves."""
    months = agg["months"]
    cats = agg["cats"]
    if not months or not cats:
        return '<p class="empty">No data.</p>'

    # Get cats in this section, sorted by total descending
    section_cats = [
        (title, c) for title, c in cats.items() if c.get("section") == section
    ]
    section_cats.sort(key=lambda x: -sum(x[1]["total"]))

    if not section_cats:
        return '<p class="empty">No data for this section.</p>'

    # Split into 2 halves
    mid = (len(months) + 1) // 2
    halves = [(months[:mid], "1st half"), (months[mid:], "2nd half")]

    parts = []
    for half_months, half_label in halves:
        if not half_months:
            continue
        start_index = months.index(half_months[0])
        parts.append('<div class="landscape-page">')
        parts.append(f"<h3>Per-category breakdown ({half_label})</h3>")
        parts.append('<table class="cat-table landscape"><thead><tr>')
        parts.append("<th>Category</th>")
        for m in half_months:
            parts.append(f'<th class="num">{m[2:].replace("-", "/")}</th>')
        parts.append('<th class="num">Total</th>')
        parts.append("</tr></thead><tbody>")

        for cat_title, c in section_cats:
            parts.append(f"<tr><td>{cat_title}</td>")
            for i in range(start_index, start_index + len(half_months)):
                v = c["total"][i] if i < len(c["total"]) else 0
                parts.append(f'<td class="num">{_n(v) if v else ""}</td>')
            half_total = sum(c["total"][start_index : start_index + len(half_months)])
            parts.append(f'<td class="num"><b>{_n(half_total)}</b></td></tr>')

        # Subtotal
        parts.append('<tr class="subtotal"><td><b>Section Total</b></td>')
        section_total = 0
        for i in range(start_index, start_index + len(half_months)):
            month_total = sum(c["total"][i] for _, c in section_cats)
            section_total += month_total
            parts.append(f'<td class="num"><b>{_n(month_total)}</b></td>')
        parts.append(f'<td class="num"><b>{_n(section_total)}</b></td></tr>')

        parts.append("</tbody></table>")
        parts.append("</div>")

    return "\n".join(parts)


def _render_recommendations(recs: List[str]) -> str:
    if not recs:
        return '<p class="empty">No recommendations for this period.</p>'
    parts = []
    for r in recs:
        if r and r[0].isdigit():
            num, _, rest = r.partition(". ")
            parts.append(
                f'<div class="recommendation"><span class="num">{num}.</span> {rest}</div>'
            )
        else:
            parts.append(f'<div class="recommendation">{r}</div>')
    return "\n".join(parts)


def _render_actions(actions: List[str]) -> str:
    if not actions:
        return '<p class="empty">No actionable savings tips for this period.</p>'
    parts = []
    for a in actions:
        if a and a[0].isdigit():
            num, _, rest = a.partition(". ")
            parts.append(
                f'<div class="action"><span class="num">{num}.</span> {rest}</div>'
            )
        else:
            parts.append(f'<div class="action">{a}</div>')
    return "\n".join(parts)


def _render_cc_paydowns(
    all_txns_by_month: Dict[str, List[Dict]], months: List[str]
) -> tuple:
    """Render CC paydowns by card: overview summary + line chart + per-month table.

    Returns (line_chart_svg, per_month_table_html, overview_table_html).
    """
    # Find all CC accounts that received paydowns (inflows)
    cc_accounts = set()
    paydown_by_account_month: Dict[str, Dict[str, float]] = {}
    for month, txns in all_txns_by_month.items():
        for t in txns:
            cat_title = (t.get("category") or {}).get("title", "")
            if cat_title != "CC Payment (paired)":
                continue
            amt = t.get("amount", 0)
            if amt <= 0:
                continue
            acct = (t.get("account") or {}).get("name", "")
            if "CC" not in acct:
                continue
            cc_accounts.add(acct)
            paydown_by_account_month.setdefault(acct, {})
            paydown_by_account_month[acct][month] = (
                paydown_by_account_month[acct].get(month, 0) + amt
            )

    if not cc_accounts:
        return None, None, None

    # Sort by total
    totals = {a: sum(paydown_by_account_month[a].values()) for a in cc_accounts}
    sorted_accts = sorted(cc_accounts, key=lambda a: -totals[a])
    grand_total = sum(totals.values())

    # Overview table: per-card summary (portrait-friendly)
    overview_parts = [
        '<table class="cat-table"><thead><tr>',
        "<th>CC Card</th>",
        '<th class="num">Months with paydown</th>',
        '<th class="num">Total paydown</th>',
        '<th class="num">Avg per month</th>',
        '<th class="num">% of all paydowns</th>',
        "</tr></thead><tbody>",
    ]
    for acct in sorted_accts:
        months_with = sum(
            1 for m in months if paydown_by_account_month[acct].get(m, 0) > 0
        )
        total = totals[acct]
        avg = total / len(months) if months else 0
        pct = total / grand_total * 100 if grand_total else 0
        overview_parts.append(
            f"<tr><td>{acct}</td>"
            f'<td class="num">{months_with}</td>'
            f'<td class="num"><b>{_n(total)}</b></td>'
            f'<td class="num">{_n(avg)}</td>'
            f'<td class="num">{pct:.1f}%</td></tr>'
        )
    # Total row
    overview_parts.append(
        '<tr class="subtotal"><td><b>Total</b></td>'
        f'<td class="num"></td>'
        f'<td class="num"><b>{_n(grand_total)}</b></td>'
        f'<td class="num"><b>{_n(grand_total/len(months)) if months else 0}</b></td>'
        '<td class="num">100.0%</td></tr>'
    )
    overview_parts.append("</tbody></table>")

    # Line chart: per-CC-account paydowns over time
    series = {}
    for acct in sorted_accts:
        series[acct] = [paydown_by_account_month[acct].get(m, 0) for m in months]
    chart_svg = render_line_chart(
        months,
        series,
        "CC Paydowns by Card (per month, NOK received)",
        y_label="NOK",
    )

    # Per-month table (landscape)
    table_parts = ['<div class="landscape-page">']
    table_parts.append("<h3>CC paydowns per month (per card)</h3>")
    table_parts.append('<table class="cat-table landscape"><thead><tr>')
    table_parts.append("<th>CC Card</th>")
    for m in months:
        table_parts.append(f'<th class="num">{m[2:].replace("-", "/")}</th>')
    table_parts.append('<th class="num">Total</th>')
    table_parts.append("</tr></thead><tbody>")

    for acct in sorted_accts:
        table_parts.append(f"<tr><td>{acct}</td>")
        row_total = 0
        for m in months:
            v = paydown_by_account_month[acct].get(m, 0)
            row_total += v
            table_parts.append(f'<td class="num">{_n(v) if v else ""}</td>')
        table_parts.append(f'<td class="num"><b>{_n(row_total)}</b></td></tr>')

    # Grand total row
    table_parts.append('<tr class="subtotal"><td><b>Total</b></td>')
    for m in months:
        month_total = sum(paydown_by_account_month[a].get(m, 0) for a in cc_accounts)
        table_parts.append(f'<td class="num"><b>{_n(month_total)}</b></td>')
    table_parts.append(f'<td class="num"><b>{_n(grand_total)}</b></td></tr>')

    table_parts.append("</tbody></table>")
    table_parts.append("</div>")

    return chart_svg, "\n".join(table_parts), "\n".join(overview_parts)


def _render_trips_section(trips_data: List[Dict[str, Any]]) -> str:
    if not trips_data:
        return '<p class="empty">No trips with PS labels in this period.</p>'
    parts = []

    # Per-trip bar chart (total cost)
    labels = [t["label"] for t in trips_data]
    values = [t["total"] for t in trips_data]
    parts.append("<h3>Total cost per trip (bar chart)</h3>")
    parts.append(render_bar_chart(labels, values, "Trip costs (NOK total)"))

    # Per-trip partner breakdown chart.
    parts.append("<h3>Per-partner split per trip</h3>")
    partner_a_values = [t["partner_a_paid"] for t in trips_data]
    partner_b_values = [t["partner_b_paid"] for t in trips_data]
    # Use the line_chart in bar mode? Just emit two side-by-side bar charts
    parts.append('<div class="trip-charts">')
    parts.append(
        render_bar_chart(labels, partner_a_values, "Partner A paid per trip (NOK)")
    )
    parts.append(
        render_bar_chart(labels, partner_b_values, "Partner B paid per trip (NOK)")
    )
    parts.append("</div>")

    # Per-trip detail table
    parts.append("<h3>Trip details</h3>")
    parts.append('<table class="cat-table"><thead><tr>')
    parts.append('<th>Trip</th><th>Dates</th><th class="num">Days</th>')
    parts.append('<th class="num">Txns</th><th class="num">Total</th>')
    parts.append(
        '<th class="num">Partner A paid</th><th class="num">Partner B paid</th>'
    )
    parts.append('<th class="num">Partner A %</th><th class="num">Partner B %</th>')
    parts.append("<th>Categories</th>")
    parts.append("</tr></thead><tbody>")
    for t in trips_data:
        partner_a_pct = t["partner_a_paid"] / t["total"] * 100 if t["total"] else 0
        partner_b_pct = t["partner_b_paid"] / t["total"] * 100 if t["total"] else 0
        parts.append("<tr>")
        parts.append(f'<td><b>{t["label"]}</b></td>')
        parts.append(f'<td>{t["date_start"]} → {t["date_end"]}</td>')
        parts.append(f'<td class="num">{t["days"]}</td>')
        parts.append(f'<td class="num">{t["txn_count"]}</td>')
        parts.append(f'<td class="num"><b>{_n(t["total"])}</b></td>')
        parts.append(f'<td class="num">{_n(t["partner_a_paid"])}</td>')
        parts.append(f'<td class="num">{_n(t["partner_b_paid"])}</td>')
        parts.append(f'<td class="num">{partner_a_pct:.1f}%</td>')
        parts.append(f'<td class="num">{partner_b_pct:.1f}%</td>')
        parts.append(f'<td>{", ".join(t["cats"])}</td>')
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "\n".join(parts)


def _render_appendices(
    agg: Dict[str, Any], all_txns_by_month: Dict[str, List[Dict]]
) -> str:
    """Per-section tx appendix: group txns by month, list them all."""
    months = agg["months"]
    if not months:
        return '<p class="empty">No data.</p>'

    parts = []
    parts.append("<h2>Appendices — all transactions by month</h2>")
    for m in months:
        txns = all_txns_by_month.get(m, [])
        if not txns:
            parts.append(f'<h3>{m}</h3><p class="empty">No transactions.</p>')
            continue
        parts.append(f"<h3>{m} ({len(txns)} txns)</h3>")
        parts.append('<table class="tx-table"><thead><tr>')
        parts.append("<th>Date</th><th>Payee</th><th>Category</th><th>Account</th>")
        parts.append('<th class="num">Amount</th></tr></thead><tbody>')
        # Sort by date asc
        txns_sorted = sorted(txns, key=lambda t: t.get("date", ""))
        for t in txns_sorted:
            cat = (t.get("category") or {}).get("title", "Uncategorized")
            acct = (t.get("account") or {}).get("name", "?")
            amt = t.get("amount", 0)
            color = "color:red" if amt < 0 else "color:green"
            parts.append(
                f'<tr><td>{t.get("date","")}</td>'
                f'<td>{(t.get("payee") or "")[:30]}</td>'
                f"<td>{cat}</td>"
                f"<td>{acct[:20]}</td>"
                f'<td class="num" style="{color}">{_n(amt)}</td></tr>'
            )
        parts.append("</tbody></table>")
    return "\n".join(parts)


def render_mom(
    agg: Dict[str, Any],
    trips_data: List[Dict[str, Any]],
    observations: List[str],
    actions: List[str],
    all_txns_by_month: Dict[str, List[Dict]],
) -> str:
    """Render the full MoM HTML."""
    months = agg["months"]
    out = []
    out.append("<!DOCTYPE html><html><head>")
    out.append('<meta charset="utf-8">')
    out.append("<title>Household Financial Report — MoM</title>")
    out.append(f"<style>{_CSS}</style>")
    out.append("</head><body>")

    # Title
    out.append("<h1>Household Financial Report — Month-on-Month</h1>")
    out.append(f'<div class="period">Period analyzed: {agg["period"]}</div>')

    # KPI Cover
    out.append(_render_kpi_cover(agg))

    # Section 1: Income
    out.append("<h2>1. Income</h2>")
    out.append("<h3>Per-month overview</h3>")
    out.append(_render_overview_table(agg, "Income"))
    out.append(
        render_line_chart(
            months,
            {
                "Partner A": agg["series"]["income"]["partner_a"],
                "Partner B": agg["series"]["income"]["partner_b"],
                "Total": agg["series"]["income"]["total"],
            },
            "Income over time (NOK)",
            y_label="NOK",
        )
    )
    # Per-person % line chart for income
    inc_total = agg["series"]["income"]["total"]
    inc_partner_a_pct = [
        value / total * 100 if total else 0
        for value, total in zip(agg["series"]["income"]["partner_a"], inc_total)
    ]
    inc_partner_b_pct = [
        value / total * 100 if total else 0
        for value, total in zip(agg["series"]["income"]["partner_b"], inc_total)
    ]
    out.append(
        render_line_chart(
            months,
            {
                "Partner A % share": inc_partner_a_pct,
                "Partner B % share": inc_partner_b_pct,
            },
            "Income share by partner (% of monthly total)",
            y_label="%",
        )
    )

    # Section 2: Savings
    out.append("<h2>2. Savings</h2>")
    out.append("<h3>Per-month overview</h3>")
    out.append(_render_overview_table(agg, "Savings"))
    out.append(
        render_line_chart(
            months,
            {
                "Partner A": agg["series"]["savings"]["net_partner_a"],
                "Partner B": agg["series"]["savings"]["net_partner_b"],
                "Total": agg["series"]["savings"]["total"],
            },
            "Net Savings over time (NOK)",
            y_label="NOK",
        )
    )
    # Real spend share by partner
    spend_total = agg["series"]["real_spend"]["total"]
    spend_partner_a_pct = [
        value / total * 100 if total else 0
        for value, total in zip(agg["series"]["real_spend"]["partner_a"], spend_total)
    ]
    spend_partner_b_pct = [
        value / total * 100 if total else 0
        for value, total in zip(agg["series"]["real_spend"]["partner_b"], spend_total)
    ]
    out.append(
        render_line_chart(
            months,
            {
                "Partner A % share": spend_partner_a_pct,
                "Partner B % share": spend_partner_b_pct,
            },
            "Real spend share by partner (% of monthly total)",
            y_label="%",
        )
    )

    # Section 3: Home
    out.append("<h2>3. Home</h2>")
    out.append(_render_section_section(agg, "home"))
    # Home line chart — total spend over time (per partner)
    home_ser = section_totals_per_month(agg, "home")
    out.append(
        render_line_chart(
            months,
            {
                "Partner A paid": home_ser["partner_a_paid"],
                "Partner B paid": home_ser["partner_b_paid"],
                "Total": home_ser["total"],
            },
            "Home spend over time (NOK)",
            y_label="NOK",
        )
    )

    # Section 4: Common
    out.append("<h2>4. Common</h2>")
    out.append(_render_section_section(agg, "common"))

    # Section 5: Personal Partner A
    out.append("<h2>5. Personal — Partner A</h2>")
    out.append(_render_section_section(agg, "personal_partner_a"))

    # Section 5b: Personal Partner B
    out.append("<h2>5b. Personal — Partner B</h2>")
    out.append(_render_section_section(agg, "personal_partner_b"))

    # Section 6: Excluded
    out.append("<h2>6. Excluded (Internal transfers: CC paydowns, own-account)</h2>")
    out.append(_render_section_section(agg, "excluded"))

    # Section 6b: CC Paydowns by Card
    out.append("<h2>6b. CC Paydowns by Card (per CC account)</h2>")
    cc_chart, cc_table, cc_overview = _render_cc_paydowns(all_txns_by_month, months)
    if cc_overview:
        out.append("<h3>CC paydowns overview</h3>")
        out.append(cc_overview)
    if cc_chart:
        out.append("<h3>Per-card paydowns over time</h3>")
        out.append(cc_chart)
    if cc_table:
        out.append(cc_table)

    # Section 7: Trips
    out.append("<h2>7. Trips (grouped by PS label)</h2>")
    out.append(_render_trips_section(trips_data))

    # Section 8: Recommendations
    out.append("<h2>8. Observations (data-driven findings)</h2>")
    out.append(
        '<p class="note">These are facts extracted directly from the data — no narrative, '
        "no recommendations, just observed patterns and outlier detection.</p>"
    )
    out.append(_render_recommendations(observations))

    out.append("<h2>9. Actionable saving tips</h2>")
    out.append(
        '<p class="note">Concrete actions you can take to reduce expenses, derived from '
        "the data above. Each shows the estimated annual savings in NOK.</p>"
    )
    out.append(_render_actions(actions))

    # Appendices
    out.append(_render_appendices(agg, all_txns_by_month))

    out.append("</body></html>")
    return "\n".join(out)
