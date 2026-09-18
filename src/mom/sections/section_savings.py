"""Section 2: Savings — table and chart renderers.

This module owns ALL savings-specific rendering:
- render_savings_table (transposed table with running cumulative Total)
- render_savings_nok_chart (line chart with cumulative Total series)
- render_savings_share_chart (per-person share with absolute %)
"""

from typing import List, Dict, Any
from html import escape
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from line_chart import render_line_chart
from sections.context import heading, labels


def _n(x):
    """Format number with thousands separator."""
    if x is None:
        return "—"
    if isinstance(x, str):
        return x
    if x == 0:
        return "0"
    return f"{x:,.0f}"


# ============================================================
# Savings table — running cumulative Total + share_of_period % + Δ MoM
# ============================================================


def render_savings_table(
    months: List[str],
    partner_a_vals: List[float],
    partner_b_vals: List[float],
    total_vals: List[float],
    row_label: str = "Month",
    partner_labels: dict[str, str] | None = None,
) -> str:
    """Render the per-month table for the Savings section.

    Columns: <row_label> | Partner A | Partner B | Total | A % | B % | Δ MoM

    Total column = running cumulative (running savings balance)
    Per-person % = |value| / (|Partner A| + |Partner B|), sign follows each partner's net
    Δ MoM = current month total / prior cumulative
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
    parts.append('<th class="num partner-a-col">Cum A</th>')
    parts.append('<th class="num partner-b-col">Cum B</th>')
    parts.append('<th class="num total-col">Cum T</th>')
    parts.append('<th class="num partner-a-col">A %</th>')
    parts.append('<th class="num partner-b-col">B %</th>')
    parts.append('<th class="num total-col">Δ MoM</th>')
    parts.append("</tr>")
    parts.append("</thead>")
    parts.append("<tbody>")

    running_a = 0.0
    running_b = 0.0
    running_total = 0.0
    for i, m in enumerate(months):
        c = partner_a_vals[i] or 0
        r = partner_b_vals[i] or 0
        t = total_vals[i] or 0
        running_a += c
        running_b += r
        running_total += t
        # Per-person %: c / (|c| + |r|), sign follows c
        abs_t = abs(c) + abs(r)
        if abs_t:
            c_pct = c / abs_t * 100
            r_pct = r / abs_t * 100
        else:
            c_pct = r_pct = 0
        # Δ MoM: current / prior cumulative
        prior_cum = sum(total_vals[:i])
        if i == 0 or prior_cum == 0:
            mom_pct_str = "—"
        else:
            mom_pct = t / prior_cum * 100
            mom_pct_str = f"{mom_pct:+.1f}%"
        parts.append("<tr>")
        parts.append(f'<td class="row-label">{m[2:].replace("-", "/")}</td>')
        parts.append(f'<td class="num partner-a-col">{_n(c)}</td>')
        parts.append(f'<td class="num partner-b-col">{_n(r)}</td>')
        parts.append(f'<td class="num total-col"><b>{_n(t)}</b></td>')
        parts.append(f'<td class="num partner-a-col">{_n(running_a)}</td>')
        parts.append(f'<td class="num partner-b-col">{_n(running_b)}</td>')
        parts.append(f'<td class="num total-col"><b>{_n(running_total)}</b></td>')
        parts.append(f'<td class="num partner-a-col">{c_pct:+.1f}%</td>')
        parts.append(f'<td class="num partner-b-col">{r_pct:+.1f}%</td>')
        parts.append(f'<td class="num total-col">{mom_pct_str}</td>')
        parts.append("</tr>")

    # Period total row
    c_net = sum(partner_a_vals)
    r_net = sum(partner_b_vals)
    abs_total = abs(c_net) + abs(r_net)
    if abs_total:
        c_pct_abs = c_net / abs_total * 100
        r_pct_abs = r_net / abs_total * 100
    else:
        c_pct_abs = r_pct_abs = 0
    parts.append('<tr class="subtotal-row">')
    parts.append('<td class="row-label"><b>Net</b></td>')
    parts.append(f'<td class="num partner-a-col"><b>{_n(c_net)}</b></td>')
    parts.append(f'<td class="num partner-b-col"><b>{_n(r_net)}</b></td>')
    parts.append(f'<td class="num total-col"><b>{_n(grand_total)}</b></td>')
    parts.append(f'<td class="num partner-a-col"><b>{_n(running_a)}</b></td>')
    parts.append(f'<td class="num partner-b-col"><b>{_n(running_b)}</b></td>')
    parts.append(f'<td class="num total-col"><b>{_n(running_total)}</b></td>')
    parts.append(f'<td class="num partner-a-col"><b>{c_pct_abs:+.1f}%</b></td>')
    parts.append(f'<td class="num partner-b-col"><b>{r_pct_abs:+.1f}%</b></td>')
    parts.append('<td class="num total-col"><b>—</b></td>')
    parts.append("</tr>")

    parts.append("</tbody>")
    parts.append("</table>")
    return "\n".join(parts)


# ============================================================
# Savings NOK chart — line chart with running cumulative Total
# ============================================================


def render_savings_nok_chart(
    months: List[str],
    partner_a_vals: List[float],
    partner_b_vals: List[float],
    total_vals: List[float],
    partner_labels: dict[str, str] | None = None,
) -> str:
    """Render the NOK line chart for Savings.

    Total series shows running cumulative (matches table Total column).
    Staggered data labels for all 3 series.
    """
    partner_labels = labels(partner_labels)
    running_total = []
    rt = 0
    for v in total_vals:
        rt += v or 0
        running_total.append(rt)

    return render_line_chart(
        months,
        {
            partner_labels["partner_a"]: partner_a_vals,
            partner_labels["partner_b"]: partner_b_vals,
            "Total (cumulative)": running_total,
        },
        "Monthly net savings (NOK) — Total is running cumulative",
        y_label="NOK",
    )


# ============================================================
# Savings share chart — per-person % using absolute values (sums to 100%)
# ============================================================


def render_savings_share_chart(
    months: List[str],
    partner_a_vals: List[float],
    partner_b_vals: List[float],
    partner_labels: dict[str, str] | None = None,
) -> str:
    """Render the per-person share chart for Savings.

    Uses |c|/(|c|+|r|) so values always sum to 100%, even for mixed-sign months
    (one partner saves, other withdraws).
    """
    partner_labels = labels(partner_labels)
    partner_a_pct = []
    partner_b_pct = []
    for c, r in zip(partner_a_vals, partner_b_vals):
        c = c or 0
        r = r or 0
        abs_sum = abs(c) + abs(r)
        if abs_sum:
            # Signed %: c / (|c| + |r|), sign follows c (matches table)
            partner_a_pct.append(c / abs_sum * 100)
            partner_b_pct.append(r / abs_sum * 100)
        else:
            partner_a_pct.append(0)
            partner_b_pct.append(0)

    return render_line_chart(
        months,
        {
            f'{partner_labels["partner_a"]} %': partner_a_pct,
            f'{partner_labels["partner_b"]} %': partner_b_pct,
        },
        "Net savings share by partner (%) — signed (matches table)",
        y_label="%",
        show_value_labels=True,
    )


# ============================================================
# Investment contribution table using sign-aware monthly net movement.
# ============================================================


def render_investment_net_table(
    months: List[str],
    partner_a_vals: List[float],
    partner_b_vals: List[float],
    total_vals: List[float],
    partner_labels: dict[str, str] | None = None,
) -> str:
    """Render the investment net per-month table.

    Columns: Month | Partner A | Partner B | Total

    Net equals classified investment-account movement for the month. Transfer
    status does not cancel a movement; the mapped account side determines it.
    """
    partner_labels = labels(partner_labels)
    grand_total = sum(total_vals)
    parts = ['<table class="overview-table transposed">', "<thead>", "<tr>"]
    parts.append('<th class="row-label">Month</th>')
    parts.append(
        f'<th class="num partner-a-col">{escape(partner_labels["partner_a"])}</th>'
    )
    parts.append(
        f'<th class="num partner-b-col">{escape(partner_labels["partner_b"])}</th>'
    )
    parts.append('<th class="num total-col">Total</th>')
    parts.append("</tr>")
    parts.append("</thead>")
    parts.append("<tbody>")

    for i, m in enumerate(months):
        c = partner_a_vals[i] or 0
        r = partner_b_vals[i] or 0
        t = total_vals[i] or 0
        parts.append("<tr>")
        parts.append(f'<td class="row-label">{m[2:].replace("-", "/")}</td>')
        parts.append(f'<td class="num partner-a-col">{_n(c)}</td>')
        parts.append(f'<td class="num partner-b-col">{_n(r)}</td>')
        parts.append(f'<td class="num total-col"><b>{_n(t)}</b></td>')
        parts.append("</tr>")

    parts.append('<tr class="subtotal-row">')
    parts.append('<td class="row-label"><b>Net</b></td>')
    parts.append(f'<td class="num partner-a-col"><b>{_n(sum(partner_a_vals))}</b></td>')
    parts.append(f'<td class="num partner-b-col"><b>{_n(sum(partner_b_vals))}</b></td>')
    parts.append(f'<td class="num total-col"><b>{_n(grand_total)}</b></td>')
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
    section_number: int | None = 3,
    section_title: str = "Savings",
) -> str:
    partner_labels = labels(partner_labels)
    months = agg["months"]
    series = agg["series"]
    cum = agg["cumulative"]
    parts = [
        f'<h2 class="section-savings">{heading(section_number, section_title)}</h2>'
    ]

    parts.append('<div class="kpi-section-summary">')
    parts.append(
        f'<p class="note">Period net savings: <b>{_n(cum["savings"]["total"])} NOK</b> '
        f'({escape(partner_labels["partner_a"])} {_n(cum["savings"]["net_partner_a"])} | '
        f'{escape(partner_labels["partner_b"])} {_n(cum["savings"]["net_partner_b"])})</p>'
    )
    investment_cum = cum["savings"].get("investment_net_total", 0)
    investment_partner_a_cum = cum["savings"].get("investment_net_partner_a", 0)
    investment_partner_b_cum = cum["savings"].get("investment_net_partner_b", 0)
    parts.append(
        f'<p class="note">Investment net: <b>{_n(investment_cum)} NOK</b> '
        f"({escape(partner_labels['partner_a'])} {_n(investment_partner_a_cum)} | {escape(partner_labels['partner_b'])} {_n(investment_partner_b_cum)})</p>"
    )
    parts.append(
        '<p class="note-small">Per-partner % = partner / sum of absolute partner values, sign follows own net. '
        "Total column = running cumulative. "
        "Δ MoM = current month total / prior cumulative.</p>"
    )
    parts.append("</div>")

    parts.append("<h3>Net savings per month (by partner)</h3>")
    parts.append(
        render_savings_table(
            months,
            series["savings"]["net_partner_a"],
            series["savings"]["net_partner_b"],
            series["savings"]["total"],
            partner_labels=partner_labels,
        )
    )

    investment_partner_a = series["savings"].get("investment_net_partner_a", [])
    investment_partner_b = series["savings"].get("investment_net_partner_b", [])
    investment_total = series["savings"].get("investment_net_total", [])
    parts.append("<h3>Investment net per month</h3>")
    parts.append(
        render_investment_net_table(
            months,
            investment_partner_a,
            investment_partner_b,
            investment_total,
            partner_labels,
        )
    )

    parts.append(
        render_savings_nok_chart(
            months,
            series["savings"]["net_partner_a"],
            series["savings"]["net_partner_b"],
            series["savings"]["total"],
            partner_labels=partner_labels,
        )
    )

    parts.append(
        render_savings_share_chart(
            months,
            series["savings"]["net_partner_a"],
            series["savings"]["net_partner_b"],
            partner_labels=partner_labels,
        )
    )

    return "\n".join(parts)
