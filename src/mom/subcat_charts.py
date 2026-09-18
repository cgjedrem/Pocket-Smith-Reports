"""Sub-category breakdown charts for Personal sections.

Provides:
- render_subcat_stacked_bar (12 months on x-axis, sub-cats stacked as colored segments)
- render_subcat_period_pie (single pie showing each sub-cat's % of personal period total)
"""

from html import escape
from typing import Dict, List, Tuple
import math

# Color palette for sub-categories (max 16 distinct colors)
PALETTE = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
    "#aec7e8",
    "#ffbb78",
    "#98df8a",
    "#ff9896",
    "#c5b0d5",
    "#c49c94",
]


def _format_y(v: float) -> str:
    """Compact number formatting for y-axis labels."""
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    if abs(v) >= 1_000:
        return f"{v/1_000:.0f}k"
    return f"{v:.0f}"


def render_subcat_stacked_bar(
    months: List[str],
    subcat_amounts: Dict[str, List[float]],
    title: str = "Sub-category spend by month",
    width: int = 760,
    height: int = 360,
) -> str:
    """Render a stacked vertical bar chart.

    Args:
        months: list of "YYYY-MM" strings (x-axis labels)
        subcat_amounts: {sub_cat_name -> [amt_per_month]}, all same length as months
        title: chart title
    """
    if not months or not subcat_amounts:
        return '<p class="empty">No data for stacked bar.</p>'

    n = len(months)
    cat_names = list(subcat_amounts.keys())
    m = len(cat_names)

    # Calculate totals
    month_totals = [0.0] * n
    for cat in cat_names:
        vals = subcat_amounts[cat]
        for i in range(n):
            month_totals[i] += vals[i] if i < len(vals) else 0
    y_max = max(month_totals) if month_totals else 1
    y_max = max(y_max, 1)  # avoid 0

    # Layout
    margin = {"top": 50, "right": 30, "bottom": 110, "left": 80}
    inner_w = width - margin["left"] - margin["right"]
    inner_h = height - margin["top"] - margin["bottom"]
    bar_w = inner_w / n * 0.7
    bar_gap = inner_w / n * 0.3

    # SVG
    parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" class="stacked-bar">'
    ]

    # Title
    parts.append(
        f'<text x="{width/2}" y="20" text-anchor="middle" font-size="13" font-weight="bold" fill="#333">{escape(title)}</text>'
    )

    # Y-axis grid + labels
    n_grid = 5
    for i in range(n_grid + 1):
        y_val = y_max * i / n_grid
        y_pos = margin["top"] + inner_h - (y_val / y_max) * inner_h
        parts.append(
            f'<line x1="{margin["left"]}" y1="{y_pos:.1f}" x2="{margin["left"] + inner_w}" y2="{y_pos:.1f}" stroke="#e0e0e0" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{margin["left"] - 5}" y="{y_pos + 4:.1f}" text-anchor="end" font-size="9" fill="#666">{_format_y(y_val)}</text>'
        )

    # Stacked bars
    for i, m_str in enumerate(months):
        x = margin["left"] + i * (inner_w / n) + bar_gap / 2
        y_offset = margin["top"] + inner_h  # bottom of bar
        for j, cat in enumerate(cat_names):
            vals = subcat_amounts[cat]
            v = vals[i] if i < len(vals) and vals[i] else 0
            if v == 0:
                continue
            seg_h = (v / y_max) * inner_h
            color = PALETTE[j % len(PALETTE)]
            y_offset -= seg_h
            parts.append(
                f'<rect x="{x:.1f}" y="{y_offset:.1f}" width="{bar_w:.1f}" height="{seg_h:.1f}" fill="{color}" stroke="white" stroke-width="0.5"/>'
            )
            # Label if segment is big enough
            if seg_h > 14:
                label = _format_y(v)
                text_color = "white" if j % 2 == 0 else "#333"
                parts.append(
                    f'<text x="{x + bar_w/2:.1f}" y="{y_offset + seg_h/2 + 3:.1f}" text-anchor="middle" font-size="8" fill="{text_color}">{escape(label)}</text>'
                )
        # X-axis label (month) — rotate -30deg to fit long names
        x_label = m_str[2:].replace("-", "/") if len(m_str) == 7 else m_str
        # If the label is long (e.g. trip names), rotate it to avoid clipping
        if len(x_label) > 8:
            parts.append(
                f'<text x="{x + bar_w/2:.1f}" y="{margin["top"] + inner_h + 12:.1f}" '
                f'text-anchor="end" font-size="9" fill="#333" '
                f'transform="rotate(-30, {x + bar_w/2:.1f}, {margin["top"] + inner_h + 12:.1f})">{escape(x_label)}</text>'
            )
        else:
            parts.append(
                f'<text x="{x + bar_w/2:.1f}" y="{margin["top"] + inner_h + 14:.1f}" '
                f'text-anchor="middle" font-size="9" fill="#333">{escape(x_label)}</text>'
            )

    # Y-axis label
    parts.append(
        f'<text x="{margin["left"] - 60}" y="{margin["top"] + inner_h/2:.1f}" text-anchor="middle" font-size="10" fill="#666" transform="rotate(-90, {margin["left"] - 60}, {margin["top"] + inner_h/2:.1f})">NOK</text>'
    )

    parts.append("</svg>")

    # Legend
    legend_parts = [
        '<div class="chart-legend" style="margin-top: 10px; font-size: 10px;">'
    ]
    for j, cat in enumerate(cat_names):
        color = PALETTE[j % len(PALETTE)]
        legend_parts.append(
            f'<span style="display: inline-block; margin-right: 12px;"><span style="display: inline-block; width: 10px; height: 10px; background: {color}; margin-right: 4px;"></span>{escape(cat)}</span>'
        )
    legend_parts.append("</div>")

    return "\n".join(parts) + "\n" + "\n".join(legend_parts)


def render_subcat_period_pie(
    subcat_amounts: Dict[str, List[float]],
    title: str = "Sub-category % of personal period total",
    width: int = 400,
    height: int = 320,
) -> str:
    """Render a pie chart for the period total per sub-category.

    Args:
        subcat_amounts: {sub_cat_name -> [amt_per_month]}
    """
    if not subcat_amounts:
        return '<p class="empty">No data for pie chart.</p>'

    # Sum each cat over all months
    cat_totals = {}
    for cat, vals in subcat_amounts.items():
        cat_totals[cat] = sum(v or 0 for v in vals)
    grand = sum(cat_totals.values())
    if grand == 0:
        return '<p class="empty">No data for pie chart.</p>'

    # Sort cats by total desc
    sorted_cats = sorted(cat_totals.items(), key=lambda x: -x[1])
    cat_names = [c for c, _ in sorted_cats]

    # Pie geometry
    cx = width / 2
    cy = height / 2 + 10
    r = min(width, height) / 2 - 30

    # Build SVG
    parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" class="pie-chart">'
    ]

    # Title
    parts.append(
        f'<text x="{width/2}" y="20" text-anchor="middle" font-size="13" font-weight="bold" fill="#333">{escape(title)}</text>'
    )

    # Pie slices
    start_angle = -math.pi / 2  # start at top
    for j, (cat, total) in enumerate(sorted_cats):
        angle = (total / grand) * 2 * math.pi
        end_angle = start_angle + angle
        color = PALETTE[cat_names.index(cat) % len(PALETTE)]

        # Arc path
        x1 = cx + r * math.cos(start_angle)
        y1 = cy + r * math.sin(start_angle)
        x2 = cx + r * math.cos(end_angle)
        y2 = cy + r * math.sin(end_angle)
        large_arc = 1 if angle > math.pi else 0
        d = f"M {cx},{cy} L {x1:.2f},{y1:.2f} A {r},{r} 0 {large_arc} 1 {x2:.2f},{y2:.2f} Z"
        parts.append(f'<path d="{d}" fill="{color}" stroke="white" stroke-width="1"/>')

        # Label (if slice is big enough)
        if angle > 0.15:  # > ~8.6%
            label_angle = (start_angle + end_angle) / 2
            label_r = r * 0.65
            lx = cx + label_r * math.cos(label_angle)
            ly = cy + label_r * math.sin(label_angle)
            pct = total / grand * 100
            parts.append(
                f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" font-size="9" fill="white" font-weight="bold">{pct:.0f}%</text>'
            )

        start_angle = end_angle

    parts.append("</svg>")

    # Legend
    legend_parts = [
        '<div class="chart-legend" style="font-size: 10px; margin-top: 4px;">'
    ]
    for cat, total in sorted_cats:
        pct = total / grand * 100
        color = PALETTE[cat_names.index(cat) % len(PALETTE)]
        legend_parts.append(
            f'<div style="margin: 2px 0;"><span style="display: inline-block; width: 10px; height: 10px; background: {color}; margin-right: 4px;"></span>{escape(cat)}: {_format_y(total)} ({pct:.1f}%)</div>'
        )
    legend_parts.append("</div>")

    return "\n".join(parts) + "\n" + "\n".join(legend_parts)
