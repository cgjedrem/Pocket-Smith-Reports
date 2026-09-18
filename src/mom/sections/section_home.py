"""Section 3: Home.

This module owns ALL home-specific rendering:
- render_home_table (transposed table with running cumulative Total)
- render_home_nok_chart (line chart with cumulative Total series)
- render_home_share_chart (per-person share, 0-100% bound)
"""

from typing import List, Dict, Any
from html import escape
import sys
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parents[1]
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))
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


def _section_data(agg, section):
    """Extract per-cat data for a given section, sorted by total spend desc."""
    out = []
    for category_id, info in agg["cats"].items():
        if info.get("section") != section:
            continue
        out.append(
            {
                "category_id": category_id,
                "cat": info.get("title", category_id),
                "partner_a_paid": info.get("partner_a_paid", []),
                "partner_b_paid": info.get("partner_b_paid", []),
                "partner_a_received": info.get("partner_a_received", []),
                "partner_b_received": info.get("partner_b_received", []),
                "total": info.get("total", []),
                "is_reimbursement": info.get("is_reimbursement", False),
            }
        )
    out.sort(key=lambda x: -sum(t or 0 for t in x["total"]))
    return out


def _section_title(agg, section, title):
    categories = sorted(
        info.get("title", category_id)
        for category_id, info in agg["cats"].items()
        if info.get("section") == section
    )
    return f"{title} ({', '.join(categories)})" if categories else title


def _section_series(agg, section):
    """Sum per-month partner paid values and net totals for a section."""
    months = agg["months"]
    cats = _section_data(agg, section)
    partner_a_col = [0.0] * len(months)
    partner_b_col = [0.0] * len(months)
    total = [0.0] * len(months)
    n = len(months)
    for cd in cats:
        info = agg["cats"].get(cd.get("category_id"), {})
        partner_a_paid = info.get("partner_a_paid") or []
        partner_b_paid = info.get("partner_b_paid") or []
        partner_a_received = info.get("partner_a_received") or []
        partner_b_received = info.get("partner_b_received") or []
        tt = info.get("total") or []
        for i in range(n):
            a_paid = (
                partner_a_paid[i]
                if i < len(partner_a_paid) and partner_a_paid[i]
                else 0
            )
            b_paid = (
                partner_b_paid[i]
                if i < len(partner_b_paid) and partner_b_paid[i]
                else 0
            )
            a_received = (
                partner_a_received[i]
                if i < len(partner_a_received) and partner_a_received[i]
                else 0
            )
            b_received = (
                partner_b_received[i]
                if i < len(partner_b_received) and partner_b_received[i]
                else 0
            )
            partner_a_col[i] += a_paid - a_received
            partner_b_col[i] += b_paid - b_received
            total[i] += tt[i] if i < len(tt) and tt[i] else 0
    return {
        "partner_a_paid": partner_a_col,
        "partner_b_paid": partner_b_col,
        "partner_a_net": partner_a_col,
        "partner_b_net": partner_b_col,
        "total": total,
    }


def _common_section_series(agg, section="common"):
    """Sum per-month partner paid values and totals for the Common section."""
    months = agg["months"]
    n = len(months)
    partner_a_col = [0.0] * n
    partner_b_col = [0.0] * n
    total = [0.0] * n

    # Per-cat spend (Common family, exclude reimbs)
    for cat_name, info in agg["cats"].items():
        if info.get("section") != section:
            continue
        if info.get("is_reimbursement"):
            continue
        partner_a_paid = info.get("partner_a_paid") or []
        partner_b_paid = info.get("partner_b_paid") or []
        partner_a_received = info.get("partner_a_received") or []
        partner_b_received = info.get("partner_b_received") or []
        tt = info.get("total") or []
        for i in range(n):
            a_paid = (
                partner_a_paid[i]
                if i < len(partner_a_paid) and partner_a_paid[i]
                else 0
            )
            b_paid = (
                partner_b_paid[i]
                if i < len(partner_b_paid) and partner_b_paid[i]
                else 0
            )
            a_received = (
                partner_a_received[i]
                if i < len(partner_a_received) and partner_a_received[i]
                else 0
            )
            b_received = (
                partner_b_received[i]
                if i < len(partner_b_received) and partner_b_received[i]
                else 0
            )
            partner_a_col[i] += a_paid - a_received
            partner_b_col[i] += b_paid - b_received
            total[i] += tt[i] if i < len(tt) and tt[i] else 0

    # Add paired reimbs (move money between partner columns; Total unchanged).
    actors = sorted(
        {
            actor
            for event in agg.get("paired_reimbs", [])
            for actor in (event.get("sender", ""), event.get("recipient", ""))
            if actor
        }
    )
    if len(actors) != 2:
        return {
            "partner_a_paid": partner_a_col,
            "partner_b_paid": partner_b_col,
            "total": total,
        }
    partner_a, partner_b = actors
    for e in agg.get("paired_reimbs", []):
        if e.get("section") != section:
            continue
        month_str = e.get("month")
        if month_str not in months:
            continue
        i = months.index(month_str)
        amt = e.get("amount", 0) or 0
        sender = e.get("sender", "")
        recipient = e.get("recipient", "")
        if recipient == partner_a and sender == partner_b:
            # Partner B paid for Partner A.
            partner_a_col[i] -= amt
            partner_b_col[i] += amt
        elif recipient == partner_b and sender == partner_a:
            # Partner A paid for Partner B.
            partner_a_col[i] += amt
            partner_b_col[i] -= amt
        # Total is unchanged (reimb is not new spend)

    return {
        "partner_a_paid": partner_a_col,
        "partner_b_paid": partner_b_col,
        "total": total,
    }


# ============================================================
# Home table — running cumulative Total + share_of_monthly % + Total %
# ============================================================


def render_home_table(
    months: List[str],
    partner_a_vals: List[float],
    partner_b_vals: List[float],
    total_vals: List[float],
    partner_labels: dict[str, str] | None = None,
) -> str:
    """Render the per-month table for the Home section.

    Columns: Month | Partner A net | Partner B net | Total | A % | B % | Total %

    Total column = running cumulative (cumulative home spend)
    Per-person % = c/t and r/t (share of monthly total)
    Total % = month / period (share of period)
    """
    partner_labels = labels(partner_labels)
    # Partner values are net paid minus received. Percentages use the net total.
    grand_total = sum(
        (partner_a_vals[i] or 0) + (partner_b_vals[i] or 0) for i in range(len(months))
    )
    parts = ['<table class="overview-table transposed">', "<thead>", "<tr>"]
    parts.append('<th class="row-label">Month</th>')
    parts.append(
        f'<th class="num partner-a-col">{escape(partner_labels["partner_a"])} net (paid minus received)</th>'
    )
    parts.append(
        f'<th class="num partner-b-col">{escape(partner_labels["partner_b"])} net (paid minus received)</th>'
    )
    parts.append('<th class="num total-col">Total</th>')
    parts.append('<th class="num partner-a-col">Cum A</th>')
    parts.append('<th class="num partner-b-col">Cum B</th>')
    parts.append('<th class="num total-col">Cum T</th>')
    parts.append(
        f'<th class="num partner-a-col">{escape(partner_labels["partner_a"])} net % (paid minus received)</th>'
    )
    parts.append(
        f'<th class="num partner-b-col">{escape(partner_labels["partner_b"])} net % (paid minus received)</th>'
    )
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
        t = c + r  # gross, includes paired reimbs so per-person % sums to 100%
        running_a += c
        running_b += r
        running_total += t
        # Per-person %: c/t and r/t (single-month gross)
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
# Home NOK chart — line chart with running cumulative Total
# ============================================================


def render_home_nok_chart(
    months: List[str],
    partner_a_vals: List[float],
    partner_b_vals: List[float],
    total_vals: List[float],
) -> str:
    """Render the NOK line chart for Home.

    Total series shows running cumulative (matches table Total column).
    Staggered data labels for all 3 series.
    """
    running_total = []
    rt = 0
    for v in total_vals:
        rt += v or 0
        running_total.append(rt)

    return render_line_chart(
        months,
        {
            "Partner A net (paid minus received)": partner_a_vals,
            "Partner B net (paid minus received)": partner_b_vals,
            "Total (cumulative)": running_total,
        },
        "Monthly home net spend (paid minus received, NOK) — Total is running cumulative",
        y_label="NOK",
    )


# ============================================================
# Home share chart — per-person % using absolute values (sums to 100%)
# ============================================================


def render_home_share_chart(
    months: List[str],
    partner_a_vals: List[float],
    partner_b_vals: List[float],
) -> str:
    """Render the per-person share chart for Home.

    Uses c/t and r/t (both positive, sums to 100%) since home spend
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
        {
            "Partner A net share": partner_a_pct,
            "Partner B net share": partner_b_pct,
        },
        "Home net spend share by partner (% of monthly total)",
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
    section_number: int | None = 4,
    section_title: str = "Home",
) -> str:
    partner_labels = labels(partner_labels)
    months = agg["months"]
    series = _section_series(agg, "home")
    grand_partner_a = sum(series["partner_a_net"])
    grand_partner_b = sum(series["partner_b_net"])
    grand_total = sum(series["total"])

    parts = []

    # Wrap h2 + summary + table + chart in single landscape-page div so they
    # all render on the same page.
    parts.append('<div class="landscape-page">')
    parts.append(
        f'<h2 class="section-home">{heading(section_number, _section_title(agg, "home", section_title))}</h2>'
    )

    parts.append(
        f'<p class="note">Period total: <b>{_n(grand_total)} NOK</b> '
        f"({escape(partner_labels['partner_a'])} net (paid minus received) {_n(grand_partner_a)} | {escape(partner_labels['partner_b'])} net (paid minus received) {_n(grand_partner_b)})</p>"
    )

    parts.append("<h3>Home net spend per month (paid minus received, by partner)</h3>")
    parts.append(
        render_home_table(
            months,
            series["partner_a_net"],
            series["partner_b_net"],
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
    # Same pattern as Income section.
    from stacked_bar_line import render_stacked_bar_with_line

    parts.append(
        "<h3>Monthly home net spend (paid minus received) by partner with cumulative line</h3>"
    )
    parts.append(
        render_stacked_bar_with_line(
            months,
            series["partner_a_net"],
            series["partner_b_net"],
            running_total,
            title="",
            y_label="NOK",
            width=1000,
            height=220,
            show_pct=True,
            partner_a_label=f'{partner_labels["partner_a"]} net (paid minus received)',
            partner_b_label=f'{partner_labels["partner_b"]} net (paid minus received)',
            accessibility_id="home-net-spend",
        )
    )
    parts.append("</div>")

    return "\n".join(parts)
