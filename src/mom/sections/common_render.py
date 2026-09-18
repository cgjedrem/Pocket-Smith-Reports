"""Shared table + chart renderers for all sections.

Every section in the MoM report uses the same table format and the same
chart types. The renderers in this module are designed to look
professional — no "1st half" labels, proper column widths, color coding,
and per-person % breakdowns.
"""

from typing import Dict, List, Any, Optional
from html import escape
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from line_chart import render_line_chart
from bar_chart import render_bar_chart
from sections.context import labels


def _n(v, currency: bool = True) -> str:
    """Format a number with thousands separator."""
    if v is None or v == 0:
        return ""
    if v < 0:
        return f"-{abs(v):,.0f}" if currency else f"-{abs(v):,.0f}"
    return f"{v:,.0f}" if currency else f"{v:,.0f}"


def _pct(num: float, den: float) -> str:
    """Format a percentage with 1 decimal."""
    if not den:
        return "0.0%"
    return f"{num / den * 100:.1f}%"


# ============================================================
# TABLE: per-month overview with per-person breakdown
# ============================================================


def render_overview_table(
    months: List[str],
    rows: List[Dict[str, Any]],
    currency_note: str = "NOK",
) -> str:
    """Render a clean per-month overview table.

    rows: list of dicts, each with:
    - 'label': str (row label, e.g. "Partner A", "Partner B", "Total")
      - 'values': list of floats (one per month)
    - 'group': 'partner-a' / 'partner-b' / 'total' / 'other' (for color coding)
      - 'bold': bool (default False) — bold the row
    """
    if not rows:
        return '<p class="empty">No data.</p>'

    parts = [
        '<table class="overview-table">',
        "<thead>",
        "<tr>",
        '<th class="row-label">Metric</th>',
    ]
    for m in months:
        parts.append(f'<th class="num month">{m[2:].replace("-", "/")}</th>')
    parts.append('<th class="num total-col">Total</th>')
    parts.append("</tr>")
    parts.append("</thead>")
    parts.append("<tbody>")

    for r in rows:
        cls = f'row-{r.get("group", "other")}'
        if r.get("bold"):
            cls += " bold"
        parts.append(f'<tr class="{cls}">')
        parts.append(f'<td class="row-label">{r["label"]}</td>')
        total = 0
        for v in r["values"]:
            # % rows are strings ("50.0%"), NOK rows are floats
            if isinstance(v, str):
                parts.append(f'<td class="num pct">{v}</td>')
            else:
                total += v if v else 0
                parts.append(f'<td class="num">{_n(v) if v else "—"}</td>')
        parts.append(f'<td class="num total-col"><b>{_n(total)}</b></td>')
        parts.append("</tr>")
    parts.append("</tbody>")
    parts.append("</table>")
    return "\n".join(parts)


def render_overview_table_with_pct(
    months: List[str],
    label: str,
    partner_a_vals: List[float],
    partner_b_vals: List[float],
    total_vals: List[float],
    add_pct_chart: bool = True,
) -> str:
    """Render a 3-row overview table: Partner A / Partner B / Total, with %.

    Args:
        months: list of "YYYY-MM"
        label: section name (e.g. "Income", "Home")
        partner_a_vals / partner_b_vals / total_vals: per-month values
        add_pct_chart: if True, also render a line chart of % share
    """
    partner_a_total = sum(partner_a_vals)
    partner_b_total = sum(partner_b_vals)
    grand_total = partner_a_total + partner_b_total

    rows = [
        {
            "label": "Partner A (paid/received)",
            "values": partner_a_vals,
            "group": "partner-a",
            "bold": False,
        },
        {
            "label": "  Partner A % of monthly total",
            "values": [
                _pct(value, total) for value, total in zip(partner_a_vals, total_vals)
            ],
            "group": "partner-a",
            "bold": False,
        },
        {
            "label": "Partner B (paid/received)",
            "values": partner_b_vals,
            "group": "partner-b",
            "bold": False,
        },
        {
            "label": "  Partner B % of monthly total",
            "values": [
                _pct(value, total) for value, total in zip(partner_b_vals, total_vals)
            ],
            "group": "partner-b",
            "bold": False,
        },
        {"label": "Total", "values": total_vals, "group": "total", "bold": True},
    ]
    html = [f"<h3>{label} — per-month breakdown (with per-person %)</h3>"]
    html.append(render_overview_table(months, rows))
    return "\n".join(html)


# ============================================================
# TABLE: Income / other-sections transposed — months as rows, metrics as columns
# (For sections where Total column = monthly value, Total % = month/period)
# (Savings has its own render in section_savings.py — not here.)
# ============================================================


def render_income_table(
    months: List[str],
    partner_a_vals: List[float],
    partner_b_vals: List[float],
    total_vals: List[float],
    row_label: str = "Month",
    cumulative_total: bool = False,
    partner_labels: dict[str, str] | None = None,
) -> str:
    """Render the per-month table for Income, Home, Common, Personal sections.

    Columns: <row_label> | Partner A | Partner B | Total | A % | B % | Total %

    cumulative_total:
      - False (default): Total column = monthly value
      - True: Total column = running cumulative

    Per-person % = c/t and r/t (share of monthly total)
    Total % = month / period grand total (share of period)
    """
    partner_labels = labels(partner_labels)
    grand_total = sum(total_vals)
    parts = ['<table class="overview-table transposed">', "<thead>", "<tr>"]
    parts.append(f'<th class="row-label">{row_label}</th>')
    parts.append(
        f'<th class="num partner-a-col">{escape(partner_labels["partner_a"])}</th>'
    )
    parts.append(
        f'<th class="num partner-b-col">{escape(partner_labels["partner_b"])}</th>'
    )
    parts.append('<th class="num total-col">Total</th>')
    parts.append('<th class="num partner-a-col">A %</th>')
    parts.append('<th class="num partner-b-col">B %</th>')
    parts.append('<th class="num total-col">Total %</th>')
    parts.append("</tr>")
    parts.append("</thead>")
    parts.append("<tbody>")

    running_total = 0.0
    for i, m in enumerate(months):
        c = partner_a_vals[i] or 0
        r = partner_b_vals[i] or 0
        t = total_vals[i] or 0
        if cumulative_total:
            running_total += t
            display_total = running_total
        else:
            display_total = t
        # Per-person %: c/t and r/t
        if t:
            c_pct = c / t * 100
            r_pct = r / t * 100
        else:
            c_pct = r_pct = 0
        # Total %: month / period (always uses raw monthly t, not display_total)
        if grand_total:
            total_pct = t / grand_total * 100
            total_pct_str = f"{total_pct:.1f}%"
        else:
            total_pct_str = "—"
        parts.append("<tr>")
        parts.append(f'<td class="row-label">{m[2:].replace("-", "/")}</td>')
        parts.append(f'<td class="num partner-a-col">{_n(c)}</td>')
        parts.append(f'<td class="num partner-b-col">{_n(r)}</td>')
        parts.append(f'<td class="num total-col"><b>{_n(display_total)}</b></td>')
        parts.append(f'<td class="num partner-a-col">{c_pct:+.1f}%</td>')
        parts.append(f'<td class="num partner-b-col">{r_pct:+.1f}%</td>')
        parts.append(f'<td class="num total-col">{total_pct_str}</td>')
        parts.append("</tr>")

    # Period total row
    c_net = sum(partner_a_vals)
    r_net = sum(partner_b_vals)
    if cumulative_total:
        total_at_total = sum(total_vals)  # net at end of period
    else:
        total_at_total = sum(total_vals)
    if grand_total:
        c_pct_total = c_net / grand_total * 100
        r_pct_total = r_net / grand_total * 100
    else:
        c_pct_total = r_pct_total = 0
    parts.append('<tr class="subtotal-row">')
    parts.append('<td class="row-label"><b>Period total</b></td>')
    parts.append(f'<td class="num partner-a-col"><b>{_n(c_net)}</b></td>')
    parts.append(f'<td class="num partner-b-col"><b>{_n(r_net)}</b></td>')
    parts.append(f'<td class="num total-col"><b>{_n(total_at_total)}</b></td>')
    parts.append(f'<td class="num partner-a-col"><b>{c_pct_total:+.1f}%</b></td>')
    parts.append(f'<td class="num partner-b-col"><b>{r_pct_total:+.1f}%</b></td>')
    parts.append('<td class="num total-col"><b>100.0%</b></td>')
    parts.append("</tr>")

    parts.append("</tbody>")
    parts.append("</table>")
    return "\n".join(parts)


# ============================================================
# CHART: stacked bar showing per-person share per month
# ============================================================


def render_person_share_chart(
    months: List[str],
    partner_a_vals: List[float],
    partner_b_vals: List[float],
    title: str,
) -> str:
    """Render a 100% stacked bar chart showing per-person share per month.

    Two partner series, summing to 100% per month.
    Uses |c| / (|c| + |r|) so it sums to 100% even when one partner withdraws
    while the other saves. Sign of the underlying values is shown by the
    line chart above (Net savings NOK), not here.

    For shared/non-paired categories the absolute split IS the share.
    For reimbursement cats the absolute split shows who's covering the
    gross flow direction-wise.
    """
    absolute_a = [abs(value) for value in partner_a_vals]
    absolute_b = [abs(value) for value in partner_b_vals]
    totals = [a + b for a, b in zip(absolute_a, absolute_b)]
    partner_a_pct = [
        value / total * 100 if total else 50 for value, total in zip(absolute_a, totals)
    ]
    partner_b_pct = [
        value / total * 100 if total else 50 for value, total in zip(absolute_b, totals)
    ]
    # Show one partner label to avoid overlap.
    return render_line_chart(
        months,
        {"Partner A %": partner_a_pct, "Partner B %": partner_b_pct},
        title,
        y_label="%",
        y_min=0,
        y_max=100,
        show_value_labels=True,
    )


def render_chart_data_table(
    months: List[str],
    series: Dict[str, List[Optional[float]]],
    title: str,
    nok_format: bool = True,
) -> str:
    """Render a small data table below a chart, with one column per month.

    Use this to show chart data values as a clean table, instead of overlapping
    data labels on the chart itself.
    """
    parts = [f'<div class="chart-data-table">']
    parts.append(f"<h4>{title}</h4>")
    parts.append('<table class="data-table"><thead><tr>')
    parts.append('<th class="row-label">Series</th>')
    for m in months:
        parts.append(f'<th class="num">{m[2:].replace("-", "/")}</th>')
    parts.append("</tr></thead><tbody>")
    for name, vals in series.items():
        parts.append(f'<tr><td class="row-label">{name}</td>')
        for v in vals:
            if v is None:
                parts.append('<td class="num">—</td>')
            elif nok_format:
                parts.append(f'<td class="num">{_n(v)}</td>')
            else:
                parts.append(f'<td class="num">{v:+.1f}%</td>')
        parts.append("</tr>")
    parts.append("</tbody></table></div>")
    return "\n".join(parts)


# ============================================================
# TABLE: per-cat breakdown with per-month values
# ============================================================


def render_per_cat_table(
    months: List[str],
    cat_data: List[Dict[str, Any]],
    section_label: str = "Category",
) -> str:
    """Render a per-cat per-month table.

    cat_data: list of dicts, each with:
      - 'cat': str (category name)
      - 'values': list of floats (per month)
      - 'is_reimbursement': bool (render differently if so)
    """
    if not cat_data:
        return '<p class="empty">No data for this section.</p>'

    parts = ['<div class="landscape-page">']
    parts.append(f"<h3>{section_label} — per-month detail (landscape)</h3>")
    parts.append('<table class="per-cat-table">')
    parts.append("<thead>")
    parts.append("<tr>")
    parts.append(f"<th>{section_label}</th>")
    for m in months:
        parts.append(f'<th class="num month">{m[2:].replace("-", "/")}</th>')
    parts.append('<th class="num total-col">Total</th>')
    parts.append("</tr>")
    parts.append("</thead>")
    parts.append("<tbody>")

    grand_total = 0
    for cd in cat_data:
        cls = "cat-reimb" if cd.get("is_reimbursement") else "cat-normal"
        parts.append(f'<tr class="{cls}">')
        parts.append(f'<td class="row-label">{cd["cat"]}</td>')
        row_total = 0
        for v in cd["values"]:
            row_total += v if v else 0
            parts.append(f'<td class="num">{_n(v) if v else "—"}</td>')
        grand_total += row_total
        parts.append(f'<td class="num total-col"><b>{_n(row_total)}</b></td>')
        parts.append("</tr>")

    # Subtotal
    parts.append('<tr class="subtotal-row">')
    parts.append('<td class="row-label"><b>Total</b></td>')
    for m in months:
        m_total = sum(cd["values"][months.index(m)] or 0 for cd in cat_data)
        parts.append(f'<td class="num total-col"><b>{_n(m_total)}</b></td>')
    parts.append(f'<td class="num total-col"><b>{_n(grand_total)}</b></td>')
    parts.append("</tr>")
    parts.append("</tbody>")
    parts.append("</table>")
    parts.append("</div>")
    return "\n".join(parts)


def render_per_cat_table_with_pct(
    months: List[str],
    section_label: str,
    cat_data: List[Dict[str, Any]],
) -> str:
    """Per-cat table with % per person per month.

    Each category has its own partner payment split per month.
    """
    if not cat_data:
        return '<p class="empty">No data.</p>'

    parts = ['<div class="landscape-page">']
    parts.append(f"<h3>{section_label} — per-cat with per-person % (landscape)</h3>")
    parts.append('<table class="per-cat-table">')
    parts.append("<thead>")
    parts.append("<tr>")
    parts.append(f"<th>{section_label}</th>")
    # For each month: Partner A, Partner B, and total.
    for m in months:
        parts.append(
            f'<th class="num partner-a-col" colspan="1">{m[2:].replace("-", "/")}</th>'
        )
    parts.append('<th class="num total-col">Total</th>')
    parts.append("</tr>")
    parts.append("<tr>")
    parts.append("<th></th>")  # empty for label column
    for m in months:
        parts.append('<th class="num partner-a-col">Partner A</th>')
        parts.append('<th class="num partner-b-col">Partner B</th>')
        parts.append('<th class="num total-col">Σ</th>')
    parts.append('<th class="num total-col"></th>')
    parts.append("</tr>")
    parts.append("</thead>")
    parts.append("<tbody>")

    grand_partner_a = 0
    grand_partner_b = 0
    grand_total = 0
    for cd in cat_data:
        cls = "cat-reimb" if cd.get("is_reimbursement") else "cat-normal"
        parts.append(f'<tr class="{cls}">')
        parts.append(f'<td class="row-label">{cd["cat"]}</td>')
        cat_partner_a = 0
        cat_partner_b = 0
        for i, m in enumerate(months):
            paid_a = cd.get("partner_a_paid") or []
            paid_b = cd.get("partner_b_paid") or []
            partner_a_value = paid_a[i] if i < len(paid_a) and paid_a[i] else 0
            partner_b_value = paid_b[i] if i < len(paid_b) and paid_b[i] else 0
            tot_v = partner_a_value + partner_b_value
            cat_partner_a += partner_a_value
            cat_partner_b += partner_b_value
            parts.append(
                f'<td class="num partner-a-col">{_n(partner_a_value) if partner_a_value else "—"}</td>'
            )
            parts.append(
                f'<td class="num partner-b-col">{_n(partner_b_value) if partner_b_value else "—"}</td>'
            )
            parts.append(
                f'<td class="num total-col">{_n(tot_v) if tot_v else "—"}</td>'
            )
        cat_total = cat_partner_a + cat_partner_b
        grand_partner_a += cat_partner_a
        grand_partner_b += cat_partner_b
        grand_total += cat_total
        parts.append(f'<td class="num total-col"><b>{_n(cat_total)}</b></td>')
        parts.append("</tr>")

    # Subtotal
    parts.append('<tr class="subtotal-row">')
    parts.append('<td class="row-label"><b>Total</b></td>')
    for i, m in enumerate(months):
        month_partner_a = 0
        month_partner_b = 0
        for cd in cat_data:
            paid_a = cd.get("partner_a_paid") or []
            paid_b = cd.get("partner_b_paid") or []
            month_partner_a += paid_a[i] if i < len(paid_a) and paid_a[i] else 0
            month_partner_b += paid_b[i] if i < len(paid_b) and paid_b[i] else 0
        parts.append(f'<td class="num partner-a-col"><b>{_n(month_partner_a)}</b></td>')
        parts.append(f'<td class="num partner-b-col"><b>{_n(month_partner_b)}</b></td>')
        parts.append(
            f'<td class="num total-col"><b>{_n(month_partner_a + month_partner_b)}</b></td>'
        )
    parts.append(f'<td class="num total-col"><b>{_n(grand_total)}</b></td>')
    parts.append("</tr>")
    parts.append("</tbody>")
    parts.append("</table>")
    parts.append("</div>")
    return "\n".join(parts)
