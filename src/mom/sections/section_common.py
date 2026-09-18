"""Section 4: Common spending.

This module owns ALL common-specific rendering:
- render_common_table (transposed table with running cumulative Total)
- render_common_nok_chart (line chart with cumulative Total series)
- render_common_share_chart (per-person share, 0-100% bound)
"""

from html import escape
from typing import List, Dict, Any
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from line_chart import render_line_chart
from sections.section_home import (
    _section_data,
    _n,
    _common_section_series as _section_series,
    _section_title,
)
from sections.context import heading, labels

# ============================================================
# Common table — running cumulative Total + share_of_monthly % + Total %
# Paired reimbs moved from recipient to sender (matches Home)
# ============================================================


def render_common_table(
    months: List[str],
    partner_a_vals: List[float],
    partner_b_vals: List[float],
    total_vals: List[float],
    partner_labels: dict[str, str] | None = None,
) -> str:
    """Render the per-month table for the Common section.

    Columns: Month | Partner A | Partner B | Monthly net | Cum A | Cum B | Cum T | A % | B % | Total %

    Total column = running cumulative (cumulative common spend)
    Per-person % = c/t and r/t (share of monthly total)
    Total % = month / period (share of period)

    Paired reimbs: e.g. Apr 2026 Common Restaurants ±189+±500
    - Partner A column excludes the reimbursed amount
    - Partner B column includes it
      - Total is net (no double-counting)
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
    parts.append('<th class="num total-col">Monthly net</th>')
    parts.append('<th class="num partner-a-col">Cum A</th>')
    parts.append('<th class="num partner-b-col">Cum B</th>')
    parts.append('<th class="num total-col">Cum T</th>')
    parts.append('<th class="num partner-a-col">A %</th>')
    parts.append('<th class="num partner-b-col">B %</th>')
    parts.append('<th class="num total-col">Total %</th>')
    parts.append("</tr>")
    parts.append("</thead>")
    parts.append("<tbody>")

    running_a = 0.0
    running_b = 0.0
    running_total = 0.0
    for i, m in enumerate(months):
        c = partner_a_vals[i] or 0
        r = partner_b_vals[i] or 0
        t = c + r  # gross (paired reimbs already moved between partners)
        running_a += c
        running_b += r
        running_total += t
        # Per-person %: c/t and r/t
        if t:
            c_pct = c / t * 100
            r_pct = r / t * 100
        else:
            c_pct = r_pct = 0
        # Total %: month / period
        if grand_total:
            total_pct = t / grand_total * 100
            total_pct_str = f"{total_pct:.1f}%"
        else:
            total_pct_str = "—"
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
        parts.append(f'<td class="num total-col">{total_pct_str}</td>')
        parts.append("</tr>")

    # Period total row
    c_net = sum(partner_a_vals)
    r_net = sum(partner_b_vals)
    if grand_total:
        c_pct_total = c_net / grand_total * 100
        r_pct_total = r_net / grand_total * 100
    else:
        c_pct_total = r_pct_total = 0
    parts.append('<tr class="subtotal-row">')
    parts.append('<td class="row-label"><b>Period total</b></td>')
    parts.append(f'<td class="num partner-a-col"><b>{_n(c_net)}</b></td>')
    parts.append(f'<td class="num partner-b-col"><b>{_n(r_net)}</b></td>')
    parts.append(f'<td class="num total-col"><b>{_n(grand_total)}</b></td>')
    parts.append(f'<td class="num partner-a-col"><b>{_n(running_a)}</b></td>')
    parts.append(f'<td class="num partner-b-col"><b>{_n(running_b)}</b></td>')
    parts.append(f'<td class="num total-col"><b>{_n(running_total)}</b></td>')
    parts.append(f'<td class="num partner-a-col"><b>{c_pct_total:+.1f}%</b></td>')
    parts.append(f'<td class="num partner-b-col"><b>{r_pct_total:+.1f}%</b></td>')
    parts.append('<td class="num total-col"><b>100.0%</b></td>')
    parts.append("</tr>")

    parts.append("</tbody>")
    parts.append("</table>")
    return "\n".join(parts)


# ============================================================
# Common NOK chart — line chart with running cumulative Total
# ============================================================


def render_common_nok_chart(
    months: List[str],
    partner_a_vals: List[float],
    partner_b_vals: List[float],
    total_vals: List[float],
) -> str:
    """Render the NOK line chart for Common.

    Total series shows running cumulative (matches table Total column).
    """
    running_total = []
    rt = 0
    for v in total_vals:
        rt += v or 0
        running_total.append(rt)

    return render_line_chart(
        months,
        {
            "Partner A": partner_a_vals,
            "Partner B": partner_b_vals,
            "Total (cumulative)": running_total,
        },
        "Monthly common spend (NOK) — Total is running cumulative",
        y_label="NOK",
    )


# ============================================================
# Common share chart — per-person % using absolute values (sums to 100%)
# ============================================================


def render_common_share_chart(
    months: List[str],
    partner_a_vals: List[float],
    partner_b_vals: List[float],
) -> str:
    """Render the per-person share chart for Common.

    Uses c/t and r/t (both positive, sums to 100%) since common spend
    is always positive (after paired reimbs are moved between partners).
    """
    partner_a_pct = []
    partner_b_pct = []
    for c, r in zip(partner_a_vals, partner_b_vals):
        c = c or 0
        r = r or 0
        t = c + r
        if t:
            partner_a_pct.append(c / t * 100)
            partner_b_pct.append(r / t * 100)
        else:
            partner_a_pct.append(0)
            partner_b_pct.append(0)

    return render_line_chart(
        months,
        {"Partner A %": partner_a_pct, "Partner B %": partner_b_pct},
        "Common spend share by partner (% of monthly total)",
        y_label="%",
        y_min=0,
        y_max=100,
        show_value_labels=True,
    )


# ============================================================
# Section render entry point
# ============================================================


def render(
    agg: Dict[str, Any],
    partner_labels: dict[str, str] | None = None,
    section_number: int | None = 5,
    section_title: str = "Common spending",
) -> str:
    partner_labels = labels(partner_labels)
    months = agg["months"]
    series = _section_series(agg, "common")
    cat_data = _section_data(agg, "common")
    grand_partner_a = sum(series["partner_a_paid"])
    grand_partner_b = sum(series["partner_b_paid"])
    grand_total = sum(series["total"])

    parts = []

    # Wrap h2 + summary + table + chart in single landscape-page div so they
    # all render on the same page. Per THEK 2026-07-23.
    parts.append('<div class="landscape-page">')
    parts.append(
        f'<h2 class="section-common">{heading(section_number, _section_title(agg, "common", section_title))}</h2>'
    )

    parts.append(
        f'<p class="note">Period total: <b>{_n(grand_total)} NOK</b> '
        f"({escape(partner_labels['partner_a'])} paid {_n(grand_partner_a)} | {escape(partner_labels['partner_b'])} paid {_n(grand_partner_b)})</p>"
    )

    parts.append("<h3>Common spend per month (by partner)</h3>")
    parts.append(
        render_common_table(
            months,
            series["partner_a_paid"],
            series["partner_b_paid"],
            series["total"],
            partner_labels,
        )
    )

    # Build running cumulative for chart's Total series
    running_total = []
    rt = 0
    for v in series["total"]:
        rt += v or 0
        running_total.append(rt)

    # Stacked partner bars with cumulative line and percentage labels.
    # Same pattern as Income + Home sections.
    from stacked_bar_line import render_stacked_bar_with_line

    parts.append(
        "<h3>Monthly common spend (stacked by partner) with cumulative line</h3>"
    )
    parts.append(
        render_stacked_bar_with_line(
            months,
            series["partner_a_paid"],
            series["partner_b_paid"],
            running_total,
            title="",
            y_label="NOK",
            width=1000,
            height=220,
            show_pct=True,
            partner_a_label=partner_labels["partner_a"],
            partner_b_label=partner_labels["partner_b"],
        )
    )
    parts.append("</div>")

    for cd in cat_data:
        cat_name = cd["cat"]
        info = agg["cats"].get(cd["category_id"], {})
        if info.get("is_reimbursement"):
            continue
        cat_partner_a = [
            (paid or 0) - (received or 0)
            for paid, received in zip(
                info.get("partner_a_paid", []), info.get("partner_a_received", [])
            )
        ]
        cat_partner_b = [
            (paid or 0) - (received or 0)
            for paid, received in zip(
                info.get("partner_b_paid", []), info.get("partner_b_received", [])
            )
        ]
        cat_total = info.get("total", [])
        if not any(cat_partner_a) and not any(cat_partner_b) and not any(cat_total):
            continue
        parts.append(
            f'<h3 class="subcat">{escape(str(cat_name))} per month (by partner)</h3>'
        )
        parts.append(
            render_common_table(
                months, cat_partner_a, cat_partner_b, cat_total, partner_labels
            )
        )
        parts.append(
            render_stacked_bar_with_line(
                months,
                cat_partner_a,
                cat_partner_b,
                [sum(cat_total[: index + 1]) for index in range(len(months))],
                title="",
                y_label="NOK",
                width=1000,
                height=220,
                show_pct=True,
                partner_a_label=partner_labels["partner_a"],
                partner_b_label=partner_labels["partner_b"],
            )
        )

    return "\n".join(parts)
