"""Sections 5a/5b: personal spending by partner.

Each sub-section has its own self-contained renderers:
- render_personal_table (transposed table with running cumulative Total)
- render_personal_nok_chart (line chart with cumulative Total)
- render_personal_subcat_stacked_bar (stacked bar by sub-cat, 12 months)
- render_personal_subcat_pie (period pie chart of sub-cat % of personal)
"""

from typing import List, Dict, Any
from html import escape
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from line_chart import render_line_chart
from sections.section_home import _section_data, _n
from subcat_charts import render_subcat_stacked_bar, render_subcat_period_pie


# ============================================================
# Personal table — running cumulative Total + share_of_monthly % + Total %
# ============================================================


def render_personal_table(
    months: List[str],
    partner_a_vals: List[float],
    partner_b_vals: List[float],
    total_vals: List[float],
    label: str = "Partner A",
    owner: str = "partner_a",
    household_total: List[float] = None,
) -> str:
    """Render the per-month table for a Personal sub-section.

    Columns: Month | <owner> | Total | <owner> % of household | Total % of household

    For Personal sections, only the owner pays (the other partner's column is 0).
    Personal sections don't need a 2nd partner column.

    Total column = running cumulative
    Owner % = owner_v / household_real_spend_for_that_month (% of total household)
    Total % = section_t / household_real_spend_for_that_month (% of total household)

    If household_total is None, falls back to owner_v / section_t (within section).
    """
    grand_total = sum(total_vals)
    # Determine which values to use based on owner
    if owner == "partner_a":
        owner_vals = partner_a_vals
    else:
        owner_vals = partner_b_vals
    owner_label = escape(label)

    parts = ['<table class="overview-table transposed">', "<thead>", "<tr>"]
    parts.append('<th class="row-label">Month</th>')
    parts.append(f'<th class="num owner-col">{owner_label}</th>')
    parts.append('<th class="num total-col">Running total</th>')
    parts.append(f'<th class="num owner-col">{owner_label} % of total spend</th>')
    parts.append('<th class="num total-col">Total %</th>')
    parts.append("</tr>")
    parts.append("</thead>")
    parts.append("<tbody>")

    running_total = 0.0
    for i, m in enumerate(months):
        owner_v = owner_vals[i] or 0
        t = total_vals[i] or 0
        running_total += t
        # Owner % of total household spend (this month)
        if (
            household_total is not None
            and i < len(household_total)
            and household_total[i]
        ):
            owner_pct = owner_v / household_total[i] * 100
            owner_pct_str = f"{owner_pct:+.1f}%"
        elif t:
            # Fallback: % within section
            owner_pct_str = f"{owner_v / t * 100:+.1f}%"
        else:
            owner_pct_str = "—"
        # Total %: month / period (back to original — % of section period total)
        if grand_total:
            total_pct = t / grand_total * 100
            total_pct_str = f"{total_pct:.1f}%"
        else:
            total_pct_str = "—"
        parts.append("<tr>")
        parts.append(f'<td class="row-label">{m[2:].replace("-", "/")}</td>')
        parts.append(f'<td class="num owner-col">{_n(owner_v)}</td>')
        parts.append(f'<td class="num total-col"><b>{_n(running_total)}</b></td>')
        parts.append(f'<td class="num owner-col">{owner_pct_str}</td>')
        parts.append(f'<td class="num total-col">{total_pct_str}</td>')
        parts.append("</tr>")

    # Period total row
    owner_net = sum(owner_vals)
    if grand_total:
        # Owner % of total household spend (period)
        if household_total is not None:
            hh_period = sum(household_total)
            owner_pct_total = owner_net / hh_period * 100 if hh_period else 0
            owner_pct_total_str = f"{owner_pct_total:+.1f}%"
        else:
            owner_pct_total_str = f"{owner_net / grand_total * 100:+.1f}%"
        total_pct_total_str = (
            "100.0%"  # Period total row: section total = 100% of itself
        )
    else:
        owner_pct_total_str = "—"
        total_pct_total_str = "—"
    parts.append('<tr class="subtotal-row">')
    parts.append('<td class="row-label"><b>Period total</b></td>')
    parts.append(f'<td class="num owner-col"><b>{_n(owner_net)}</b></td>')
    parts.append(f'<td class="num total-col"><b>{_n(grand_total)}</b></td>')
    parts.append(f'<td class="num owner-col"><b>{owner_pct_total_str}</b></td>')
    parts.append(f'<td class="num total-col"><b>{total_pct_total_str}</b></td>')
    parts.append("</tr>")

    parts.append("</tbody>")
    parts.append("</table>")
    return "\n".join(parts)


# ============================================================
# Personal NOK chart — line chart with running cumulative Total
# ============================================================


def render_personal_nok_chart(
    months: List[str],
    partner_a_vals: List[float],
    partner_b_vals: List[float],
    total_vals: List[float],
    label: str = "Partner A",
) -> str:
    """Render the NOK line chart for Personal.

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
            "Partner A paid": partner_a_vals,
            "Partner B paid": partner_b_vals,
            "Total (cumulative)": running_total,
        },
        f"Monthly {label} personal spend (NOK) — Total is running cumulative",
        y_label="NOK",
    )


# ============================================================
# Personal share chart — per-person % using absolute values (sums to 100%)
# ============================================================


def render_personal_share_chart(
    months: List[str],
    partner_a_vals: List[float],
    partner_b_vals: List[float],
    label: str = "Partner A",
) -> str:
    """Render the per-person share chart for Personal.

    Uses c/t and r/t (both positive, sums to 100%) since personal spend
    is always positive.
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
        f"{label} personal spend share by partner (% of monthly total)",
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
    partner: str,
    partner_labels: dict[str, str],
    section_number: int,
    section_title: str,
) -> str:
    """Render a registry personal section; keys are already normalized."""
    months = agg["months"]
    from sections.section_home import _section_series

    normalized_section = partner
    owner = "partner_a" if partner == "personal_partner_a" else "partner_b"
    label = partner_labels[owner]
    series = _section_series(agg, normalized_section)
    cat_data = _section_data(agg, normalized_section)
    grand_total = sum(series["total"])
    if not grand_total:
        return f'<h2 class="section-{partner}">{section_number}. {escape(section_title)}</h2><p class="empty">No data for this section.</p>'

    color_class = partner

    parts = [
        f'<h2 class="section-{color_class}">{section_number}. {escape(section_title)}</h2>'
    ]

    parts.append(
        f'<p class="note">Period total: <b>{_n(grand_total)} NOK</b> '
        f'({escape(label)} paid {_n(sum(series["partner_a_paid"] if owner == "partner_a" else series["partner_b_paid"]))})</p>'
    )

    # Get per-month household total spend (real_spend)
    household_total = agg.get("series", {}).get("real_spend", {}).get("total", [])

    parts.append(
        render_personal_table(
            months,
            series["partner_a_net"],
            series["partner_b_net"],
            series["total"],
            label=label,
            owner=owner,
            household_total=household_total,
        )
    )

    # Stacked bar (right under the table) + period pie (own page)
    subcat_amounts = {}
    n = len(months)
    for cd in cat_data:
        cat_name = (
            str(cd["cat"])
            .replace("Partner A", partner_labels["partner_a"])
            .replace("Partner B", partner_labels["partner_b"])
        )
        info = agg["cats"].get(cd["category_id"], {})
        if info.get("is_reimbursement"):
            continue
        cp = info.get("partner_a_paid") or []
        rp = info.get("partner_b_paid") or []
        cr = info.get("partner_a_received") or []
        rr = info.get("partner_b_received") or []
        # For personal sections, only the owner pays
        if owner == "partner_a":
            vals = []
            for i in range(n):
                cp_v = cp[i] if i < len(cp) and cp[i] else 0
                cr_v = cr[i] if i < len(cr) and cr[i] else 0
                vals.append(cp_v - cr_v)
        else:
            vals = []
            for i in range(n):
                rp_v = rp[i] if i < len(rp) and rp[i] else 0
                rr_v = rr[i] if i < len(rr) and rr[i] else 0
                vals.append(rp_v - rr_v)
        if sum(vals) > 0:
            subcat_amounts[cat_name] = vals
    if subcat_amounts:
        parts.append(
            f'<h3 class="subcat">{escape(label)} sub-category spend by month (stacked, NOK)</h3>'
        )
        parts.append(
            render_subcat_stacked_bar(
                months,
                subcat_amounts,
                title=f"{label} sub-category spend by month (stacked, NOK)",
            )
        )

    # Page break: pie chart on its own page (fills the page)
    if subcat_amounts:
        parts.append('<div style="page-break-before: always;"></div>')
        parts.append(
            render_subcat_period_pie(
                subcat_amounts,
                title=f"{label} sub-category % of personal period total",
                width=900,
                height=700,
            )
        )

    # Per-sub-category breakdown using the same table format
    # Pack 2 sub-cats per page (side-by-side) using .two-col CSS class
    subcat_blocks = []  # (cat_name, html_for_this_subcat)
    for cd in cat_data:
        cat_name = (
            str(cd["cat"])
            .replace("Partner A", partner_labels["partner_a"])
            .replace("Partner B", partner_labels["partner_b"])
        )
        info = agg["cats"].get(cd["category_id"], {})
        cp = info.get("partner_a_paid") or []
        rp = info.get("partner_b_paid") or []
        cr = info.get("partner_a_received") or []
        rr = info.get("partner_b_received") or []
        tt = info.get("total") or []
        n = len(months)
        cat_partner_a = []
        cat_partner_b = []
        cat_total = []
        for i in range(n):
            c_paid = cp[i] if i < len(cp) and cp[i] else 0
            r_paid = rp[i] if i < len(rp) and rp[i] else 0
            c_recv = cr[i] if i < len(cr) and cr[i] else 0
            r_recv = rr[i] if i < len(rr) and rr[i] else 0
            cat_partner_a.append(c_paid - c_recv)
            cat_partner_b.append(r_paid - r_recv)
            cat_total.append(tt[i] if i < len(tt) and tt[i] else 0)
        if sum(cat_total) == 0 and sum(cat_partner_a) == 0 and sum(cat_partner_b) == 0:
            continue
        if info.get("is_reimbursement"):
            continue
        block_html = (
            f"<div>"
            f'<h3 class="subcat">{escape(str(cat_name))} per month ({escape(label)} only)</h3>'
            + render_personal_table(
                months,
                cat_partner_a,
                cat_partner_b,
                cat_total,
                label=label,
                owner=owner,
                household_total=household_total,
            )
            + "</div>"
        )
        subcat_blocks.append(block_html)

    # Wrap pairs in .two-col div
    for i in range(0, len(subcat_blocks), 2):
        pair = subcat_blocks[i : i + 2]
        if len(pair) == 2:
            parts.append('<div class="two-col">' + "".join(pair) + "</div>")
        else:
            parts.append(pair[0])

    return "\n".join(parts)
