"""Section 6b: CC Paydowns by Card (per CC account)."""

from html import escape
from typing import Dict, List, Any
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from line_chart import render_line_chart
from sections.common_render import _n
from sections.context import heading


def render_cc_stacked_chart(months, series, cumulative):
    """Render monthly per-card bars and cumulative paydowns on separate axes."""
    if not months:
        return '<p class="empty">No CC paydown data.</p>'
    width, height, left, right, top, bottom = 1000, 260, 70, 70, 55, 45
    plot_width, plot_height = width - left - right, height - top - bottom
    monthly_totals = [
        sum(values[index] for values in series.values()) for index in range(len(months))
    ]
    monthly_axis_max = max(1.0, *monthly_totals) * 1.15
    cumulative_axis_max = max(1.0, *cumulative) * 1.05
    colors = ("#1f77b4", "#ff7f0e", "#9467bd", "#8c564b", "#d62728")
    cumulative_color = "#2ca02c"
    parts = [
        f'<svg class="stacked-bar-line cc-paydowns-chart" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Monthly credit-card paydowns by card and cumulative credit-card paydowns, both in NOK">',
        "<title>Monthly credit-card paydowns by card with cumulative credit-card paydowns</title>",
    ]
    for tick in range(6):
        y = top + plot_height - tick / 5 * plot_height
        monthly_value = monthly_axis_max * tick / 5
        cumulative_value = cumulative_axis_max * tick / 5
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" stroke="#e0e0e0" stroke-width="0.5"/>'
            f'<text x="{left - 5}" y="{y + 4:.1f}" text-anchor="end" font-size="10" fill="#666">{monthly_value:.0f}</text>'
            f'<text x="{left + plot_width + 5}" y="{y + 4:.1f}" text-anchor="start" font-size="10" fill="{cumulative_color}">{cumulative_value:.0f}</text>'
        )
    for index, month in enumerate(months):
        x = left + index * plot_width / len(months) + 10
        bar_width = plot_width / len(months) - 20
        y = top + plot_height
        for card_index, (card, values) in enumerate(series.items()):
            value = values[index]
            bar_height = value / monthly_axis_max * plot_height
            y -= bar_height
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" fill="{colors[card_index % len(colors)]}"/>'
            )
        parts.append(
            f'<text x="{x + bar_width / 2:.1f}" y="{height - 15}" text-anchor="middle" font-size="10">{escape(month[2:])}</text>'
        )
    points = " ".join(
        f"{left + (index + .5) * plot_width / len(months):.1f},{top + plot_height - value / cumulative_axis_max * plot_height:.1f}"
        for index, value in enumerate(cumulative)
    )
    parts.append(
        f'<polyline points="{points}" fill="none" stroke="{cumulative_color}" stroke-width="3"/>'
    )
    for index, card in enumerate(series):
        x = left + index * 150
        parts.append(
            f'<rect x="{x}" y="20" width="12" height="12" fill="{colors[index % len(colors)]}"/><text x="{x + 16}" y="30" font-size="10">{escape(card)}</text>'
        )
    parts.append(
        f'<line x1="{left}" y1="46" x2="{left + 20}" y2="46" stroke="{cumulative_color}" stroke-width="3"/><text x="{left + 26}" y="50" font-size="10" fill="{cumulative_color}">Cumulative CC paydowns (right axis)</text>'
    )
    parts.append(
        f'<text x="15" y="{top + plot_height / 2}" text-anchor="middle" font-size="11" fill="#666" transform="rotate(-90 15 {top + plot_height / 2})">Monthly CC paydowns (NOK)</text>'
        f'<text x="{width - 15}" y="{top + plot_height / 2}" text-anchor="middle" font-size="11" fill="{cumulative_color}" transform="rotate(90 {width - 15} {top + plot_height / 2})">Cumulative CC paydowns (NOK)</text>'
        "</svg>"
    )
    return "".join(parts)


def render(
    agg: Dict[str, Any],
    partner_labels: dict[str, str] | None = None,
    section_number: int | None = 9,
    section_title: str = "Credit-card paydowns",
) -> str:
    months = agg["months"]
    cc = agg.get("cc_paydowns", {})
    parts = [
        f'<h2 class="section-cc_paydowns">{heading(section_number, section_title)}</h2>'
    ]

    if not cc:
        return "\n".join(parts + ['<p class="empty">No CC paydowns found.</p>'])

    # Sort by total descending
    totals = {a: sum(cc[a].values()) for a in cc}
    sorted_accts = sorted(cc.keys(), key=lambda a: -totals[a])
    grand_total = sum(totals.values())

    # Overview summary table (portrait)
    parts.append("<h3>CC paydowns overview</h3>")
    parts.append('<table class="per-cat-table">')
    parts.append(
        "<thead><tr>"
        "<th>CC Card</th>"
        '<th class="num">Months with paydown</th>'
        '<th class="num">Total paydown</th>'
        '<th class="num">Avg / month</th>'
        '<th class="num">% of all paydowns</th>'
        "</tr></thead><tbody>"
    )
    for acct in sorted_accts:
        months_with = sum(1 for m in months if cc[acct].get(m, 0) > 0)
        total = totals[acct]
        avg = total / len(months) if months else 0
        pct = total / grand_total * 100 if grand_total else 0
        parts.append(
            f"<tr><td>{escape(str(acct))}</td>"
            f'<td class="num">{months_with}</td>'
            f'<td class="num"><b>{_n(total)}</b></td>'
            f'<td class="num">{_n(avg)}</td>'
            f'<td class="num">{pct:.1f}%</td></tr>'
        )
    parts.append(
        '<tr class="subtotal-row">'
        f"<td><b>Total</b></td><td></td>"
        f'<td class="num"><b>{_n(grand_total)}</b></td>'
        f'<td class="num"><b>{_n(grand_total/len(months)) if months else 0}</b></td>'
        f'<td class="num">100.0%</td></tr>'
    )
    parts.append("</tbody></table>")

    # Stacked card bars with a cumulative household line.
    series = {acct: [cc[acct].get(m, 0) for m in months] for acct in sorted_accts}
    cumulative = []
    running_total = 0.0
    for month in months:
        running_total += sum(cc[acct].get(month, 0) for acct in sorted_accts)
        cumulative.append(running_total)
    parts.append('<div class="landscape-page">')
    parts.append("<h3>CC paydowns by card with cumulative total</h3>")
    parts.append(
        render_cc_stacked_chart(
            months,
            series,
            cumulative,
        )
    )

    # Per-month table (landscape)
    parts.append("<h3>CC paydowns per month (per card, NOK)</h3>")
    parts.append('<table class="per-cat-table">')
    parts.append("<thead><tr><th>CC Card</th>")
    for m in months:
        parts.append(f'<th class="num">{m[2:].replace("-", "/")}</th>')
    parts.append('<th class="num">Total</th></tr></thead><tbody>')
    for acct in sorted_accts:
        parts.append(f"<tr><td>{escape(str(acct))}</td>")
        row_total = 0
        for m in months:
            v = cc[acct].get(m, 0)
            row_total += v
            parts.append(f'<td class="num">{_n(v) if v else "—"}</td>')
        parts.append(f'<td class="num"><b>{_n(row_total)}</b></td></tr>')
    parts.append('<tr class="subtotal-row"><td><b>Total</b></td>')
    for m in months:
        m_total = sum(cc[a].get(m, 0) for a in sorted_accts)
        parts.append(f'<td class="num"><b>{_n(m_total)}</b></td>')
    parts.append(f'<td class="num"><b>{_n(grand_total)}</b></td></tr>')
    parts.append("</tbody></table>")
    parts.append("</div>")  # close landscape-page

    return "\n".join(parts)
