"""Stacked bar + cumulative line combo chart SVG generator.

For Income section: stacked vertical bars per month (Partner A + Partner B) with a line on
top showing cumulative running total. Per THEK 2026-07-23 request.
"""

import hashlib
from html import escape
from typing import List, Optional
from uuid import uuid4

COLORS = {
    "partner_a": "#1f77b4",
    "partner_b": "#ff7f0e",
    "cumulative": "#2ca02c",
    "grid": "#e0e0e0",
    "axis": "#666",
    "text": "#333",
    "bar_label": "#fff",
}


def _format_y(v: float) -> str:
    """Compact number formatting for axis labels."""
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    if abs(v) >= 1_000:
        return f"{v/1_000:.0f}k"
    return f"{v:.0f}"


def _chart_accessibility(
    title: str,
    months: List[str],
    partner_a_vals: List[float],
    partner_b_vals: List[float],
    cumulative_vals: List[float],
    y_label: str,
    accessibility_id: Optional[str],
) -> tuple[str, str, str, str]:
    """Return DOM-unique SVG accessibility IDs and descriptive text."""
    accessible_title = title.strip() or "Stacked bar chart with cumulative line"
    source = "|".join(
        map(
            str,
            [
                accessibility_id or accessible_title,
                y_label,
                months,
                partner_a_vals,
                partner_b_vals,
                cumulative_vals,
            ],
        )
    )
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]
    prefix = (
        "".join(
            character.lower() if character.isalnum() else "-"
            for character in (accessibility_id or accessible_title)
        ).strip("-")
        or "chart"
    )
    prefix = prefix[:40]
    instance_id = uuid4().hex
    title_id = f"stacked-bar-line-{prefix}-{digest}-{instance_id}-title"
    description_id = f"stacked-bar-line-{prefix}-{digest}-{instance_id}-description"
    description = (
        f"Stacked monthly bars for two partners and a cumulative line in {y_label} "
        f"across {len(months)} month{'s' if len(months) != 1 else ''}."
    )
    return title_id, description_id, accessible_title, description


def render_stacked_bar_with_line(
    months: List[str],
    partner_a_vals: List[float],
    partner_b_vals: List[float],
    cumulative_vals: List[float],
    title: str = "Monthly income (stacked) with cumulative line",
    y_label: str = "NOK",
    width: int = 760,
    height: int = 380,
    show_value_labels: bool = True,
    show_pct: bool = False,
    partner_a_label: str = "Partner A",
    partner_b_label: str = "Partner B",
    accessibility_id: Optional[str] = None,
) -> str:
    """Render a vertical stacked-bar chart (Partner A + Partner B) per month with a line
    series on top showing the running cumulative value.

    Args:
        months: month labels (e.g. ['2025-08', '2025-09', ...])
        partner_a_vals: per-month Partner A value (stack segment bottom)
        partner_b_vals: per-month Partner B value (stack segment top)
        cumulative_vals: per-month cumulative running total (line)
        title: chart title
        y_label: y-axis label
        width/height: SVG dimensions
        show_value_labels: if True, label each bar segment with its value
                          and each line point with its value
        accessibility_id: optional stable context for SVG metadata ID prefixes
    """
    n = len(months)
    if (
        n == 0
        or len(partner_a_vals) != n
        or len(partner_b_vals) != n
        or len(cumulative_vals) != n
    ):
        return '<p class="empty">No data for stacked bar chart.</p>'

    margin = {"top": 70, "right": 60, "bottom": 60, "left": 70}
    plot_w = width - margin["left"] - margin["right"]
    plot_h = height - margin["top"] - margin["bottom"]

    # Both axes include zero so owner credits render below the baseline.
    bar_values = [value or 0 for value in partner_a_vals + partner_b_vals]
    line_values = [value or 0 for value in cumulative_vals]
    bar_min = min(0, min(bar_values, default=0))
    bar_max = max(0, max(bar_values, default=0))
    line_min = min(0, min(line_values, default=0))
    line_max = max(0, max(line_values, default=0))

    def padded_bounds(low: float, high: float) -> tuple[float, float]:
        span = high - low
        if span == 0:
            return -1.0, 1.0
        return low - span * 0.08, high + span * 0.08

    y_min_bar, y_max_bar = padded_bounds(bar_min, bar_max)
    y_min_line, y_max_line = padded_bounds(line_min, line_max)

    def y_bar(v: float) -> float:
        return (
            margin["top"]
            + plot_h
            - ((v - y_min_bar) / (y_max_bar - y_min_bar)) * plot_h
        )

    def y_line(v: float) -> float:
        return (
            margin["top"]
            + plot_h
            - ((v - y_min_line) / (y_max_line - y_min_line)) * plot_h
        )

    bar_w = plot_w / n * 0.7
    bar_gap = plot_w / n * 0.3

    title_id, description_id, accessible_title, description = _chart_accessibility(
        title,
        months,
        partner_a_vals,
        partner_b_vals,
        cumulative_vals,
        y_label,
        accessibility_id,
    )
    svg = [
        f'<svg class="stacked-bar-line" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-labelledby="{title_id} {description_id}" style="font-family:sans-serif;">',
        f'<title id="{title_id}">{escape(accessible_title)}</title>',
        f'<desc id="{description_id}">{escape(description)}</desc>',
        # Title
        f'<text x="{width/2}" y="20" text-anchor="middle" font-size="14" '
        f'font-weight="bold" fill="{COLORS["text"]}">{escape(title)}</text>',
    ]

    # Left Y-axis grid + labels (for bars)
    n_ticks = 5
    for i in range(n_ticks + 1):
        y = margin["top"] + plot_h - (i / n_ticks) * plot_h
        v = y_min_bar + (y_max_bar - y_min_bar) * i / n_ticks
        svg.append(
            f'<line x1="{margin["left"]}" y1="{y:.1f}" x2="{margin["left"]+plot_w}" y2="{y:.1f}" '
            f'stroke="{COLORS["grid"]}" stroke-width="0.5"/>'
        )
        svg.append(
            f'<text x="{margin["left"]-5:.1f}" y="{y+4:.1f}" text-anchor="end" '
            f'font-size="10" fill="{COLORS["axis"]}">{_format_y(v)}</text>'
        )
    svg.append(
        f'<line class="zero-baseline" x1="{margin["left"]}" y1="{y_bar(0):.1f}" '
        f'x2="{margin["left"]+plot_w}" y2="{y_bar(0):.1f}" '
        f'stroke="{COLORS["axis"]}" stroke-width="1"/>'
    )

    # Bars (left axis scale)
    for i, m in enumerate(months):
        c = partner_a_vals[i] or 0
        r = partner_b_vals[i] or 0
        x = margin["left"] + i * (bar_w + bar_gap) + bar_gap / 2
        positive_stack = 0.0
        negative_stack = 0.0
        if c >= 0:
            c_start, c_end = positive_stack, positive_stack + c
            positive_stack = c_end
        else:
            c_start, c_end = negative_stack, negative_stack + c
            negative_stack = c_end
        if r >= 0:
            r_start, r_end = positive_stack, positive_stack + r
            positive_stack = r_end
        else:
            r_start, r_end = negative_stack, negative_stack + r
            negative_stack = r_end
        c_y_start, c_y_end = y_bar(c_start), y_bar(c_end)
        r_y_start, r_y_end = y_bar(r_start), y_bar(r_end)
        partner_a_h = abs(c_y_end - c_y_start)
        partner_b_h = abs(r_y_end - r_y_start)
        partner_a_y = min(c_y_start, c_y_end)
        partner_b_y = min(r_y_start, r_y_end)
        svg.append(
            f'<rect x="{x:.1f}" y="{partner_a_y:.1f}" width="{bar_w:.1f}" height="{partner_a_h:.1f}" '
            f'fill="{COLORS["partner_a"]}" opacity="0.85"/>'
        )
        svg.append(
            f'<rect x="{x:.1f}" y="{partner_b_y:.1f}" width="{bar_w:.1f}" height="{partner_b_h:.1f}" '
            f'fill="{COLORS["partner_b"]}" opacity="0.85"/>'
        )
        if show_value_labels:
            # Compute partner shares for this month.
            total_here = abs(c) + abs(r)
            partner_a_pct = abs(c) / total_here * 100 if total_here else 0
            partner_b_pct = abs(r) / total_here * 100 if total_here else 0
            if partner_a_h > 18:
                partner_a_value_label = (
                    f"{partner_a_pct:.0f}%" if show_pct else f"{_format_y(c)}"
                )
                svg.append(
                    f'<text x="{x + bar_w/2:.1f}" y="{partner_a_y + partner_a_h/2 + 3:.1f}" '
                    f'text-anchor="middle" font-size="9" fill="{COLORS["bar_label"]}">'
                    f"{partner_a_value_label}</text>"
                )
            if partner_b_h > 18:
                partner_b_value_label = (
                    f"{partner_b_pct:.0f}%" if show_pct else f"{_format_y(r)}"
                )
                svg.append(
                    f'<text x="{x + bar_w/2:.1f}" y="{partner_b_y + partner_b_h/2 + 3:.1f}" '
                    f'text-anchor="middle" font-size="9" fill="{COLORS["bar_label"]}">'
                    f"{partner_b_value_label}</text>"
                )
        # X-axis tick label (month short)
        svg.append(
            f'<text x="{x + bar_w/2:.1f}" y="{margin["top"] + plot_h + 15:.1f}" '
            f'text-anchor="middle" font-size="9" fill="{COLORS["axis"]}" '
            f'transform="rotate(-45 {x + bar_w/2:.1f} {margin["top"] + plot_h + 15:.1f})">'
            f'{escape(m[2:].replace("-", "/"))}</text>'
        )

    # Right Y-axis labels (for cumulative line)
    for i in range(n_ticks + 1):
        y = margin["top"] + plot_h - (i / n_ticks) * plot_h
        v = y_min_line + (y_max_line - y_min_line) * i / n_ticks
        svg.append(
            f'<text x="{margin["left"]+plot_w+5:.1f}" y="{y+4:.1f}" text-anchor="start" '
            f'font-size="10" fill="{COLORS["cumulative"]}">{_format_y(v)}</text>'
        )

    # Cumulative line + points (right axis scale)
    points = []
    for i, cv in enumerate(cumulative_vals):
        x = margin["left"] + i * (bar_w + bar_gap) + bar_gap / 2 + bar_w / 2
        y = y_line(cv or 0)
        points.append(f"{x:.1f},{y:.1f}")
    svg.append(
        f'<polyline points="{" ".join(points)}" fill="none" stroke="{COLORS["cumulative"]}" '
        f'stroke-width="2"/>'
    )
    if show_value_labels:
        for i, cv in enumerate(cumulative_vals):
            x = margin["left"] + i * (bar_w + bar_gap) + bar_gap / 2 + bar_w / 2
            y = y_line(cv or 0)
            svg.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{COLORS["cumulative"]}"/>'
            )
            # Cumulative data labels go just under the x-axis dates, not next
            # to the line points (which overlap bars). Per THEK 2026-07-23.
            label_y = margin["top"] + plot_h + 45
            svg.append(
                f'<text x="{x:.1f}" y="{label_y:.1f}" text-anchor="middle" font-size="9" '
                f'fill="{COLORS["cumulative"]}" font-weight="bold">{_format_y(cv)}</text>'
            )

    # Left Y-axis label (bars)
    svg.append(
        f'<text x="{15}" y="{margin["top"] + plot_h/2}" text-anchor="middle" '
        f'font-size="11" fill="{COLORS["axis"]}" '
        f'transform="rotate(-90 15 {margin["top"] + plot_h/2})">{escape(y_label)} (monthly)</text>'
    )
    # Right Y-axis label (cumulative)
    svg.append(
        f'<text x="{width-15}" y="{margin["top"] + plot_h/2}" text-anchor="middle" '
        f'font-size="11" fill="{COLORS["cumulative"]}" '
        f'transform="rotate(90 {width-15} {margin["top"] + plot_h/2})">Cumulative (NOK)</text>'
    )

    # Legend
    legend_y = margin["top"] - 35
    legend_x = margin["left"]
    svg.append(
        f'<rect x="{legend_x}" y="{legend_y}" width="12" height="12" '
        f'fill="{COLORS["partner_a"]}" opacity="0.85"/>'
    )
    svg.append(
        f'<text x="{legend_x+18}" y="{legend_y+10}" font-size="10" fill="{COLORS["text"]}">{escape(partner_a_label)}</text>'
    )
    legend_x += 90
    svg.append(
        f'<rect x="{legend_x}" y="{legend_y}" width="12" height="12" '
        f'fill="{COLORS["partner_b"]}" opacity="0.85"/>'
    )
    svg.append(
        f'<text x="{legend_x+18}" y="{legend_y+10}" font-size="10" fill="{COLORS["text"]}">{escape(partner_b_label)}</text>'
    )
    legend_x += 70
    svg.append(
        f'<line x1="{legend_x}" y1="{legend_y+6}" x2="{legend_x+20}" y2="{legend_y+6}" '
        f'stroke="{COLORS["cumulative"]}" stroke-width="2"/>'
    )
    svg.append(
        f'<circle cx="{legend_x+10}" cy="{legend_y+6}" r="3" fill="{COLORS["cumulative"]}"/>'
    )
    svg.append(
        f'<text x="{legend_x+26}" y="{legend_y+10}" font-size="10" fill="{COLORS["text"]}">Cumulative</text>'
    )

    svg.append("</svg>")
    return "\n".join(svg)
