"""Bar chart SVG generator (horizontal bars).

Used for trips, per-cat rankings, and similar comparisons.
"""

from typing import Dict, List, Tuple, Optional

COLORS = {
    "partner-a": "#1f77b4",
    "partner-b": "#ff7f0e",
    "total": "#2ca02c",
    "grid": "#e0e0e0",
    "axis": "#666",
    "text": "#333",
}


def _format_y(v: float) -> str:
    """Compact number formatting."""
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    if abs(v) >= 1_000:
        return f"{v/1_000:.0f}k"
    return f"{v:.0f}"


def render_bar_chart(
    labels: List[str],
    values: List[float],
    title: str,
    x_label: str = "NOK",
    width: int = 720,
    height: Optional[int] = None,
) -> str:
    """Render a horizontal bar chart as SVG.

    Args:
        labels: bar labels (left side)
        values: bar values (length)
        title: chart title
        x_label: x-axis label
        width: SVG width
        height: SVG height (auto-calculated if None)
    """
    if not labels or not values or len(labels) != len(values):
        return '<p class="empty">No data for bar chart.</p>'

    n = len(labels)
    if height is None:
        height = max(200, 40 * n + 80)

    margin = {"top": 50, "right": 20, "bottom": 30, "left": 200}
    plot_w = width - margin["left"] - margin["right"]
    plot_h = height - margin["top"] - margin["bottom"]

    max_val = max(values)
    min_val = min(values)
    if max_val == 0:
        max_val = 1
    if min_val == 0:
        min_val = 0

    bar_h = plot_h / n * 0.7
    bar_gap = plot_h / n * 0.3

    def x_for(v: float) -> float:
        # Bar from 0 (or min_val if negative) to v
        if max_val == 0:
            return margin["left"]
        return margin["left"] + (v / max_val) * plot_w

    svg_parts = [
        f'<svg class="bar-chart" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" style="font-family:sans-serif;">'
    ]
    # Title
    svg_parts.append(
        f'<text x="{width/2}" y="20" text-anchor="middle" '
        f'font-size="14" font-weight="bold" fill="{COLORS["text"]}">{title}</text>'
    )

    # X-axis at the bottom — ticks
    n_ticks = 5
    for i in range(n_ticks + 1):
        x = margin["left"] + plot_w * i / n_ticks
        v = max_val * i / n_ticks
        svg_parts.append(
            f'<line x1="{x:.1f}" y1="{margin["top"]}" x2="{x:.1f}" y2="{margin["top"] + plot_h}" '
            f'stroke="{COLORS["grid"]}" stroke-width="0.5"/>'
        )
        svg_parts.append(
            f'<text x="{x:.1f}" y="{margin["top"] + plot_h + 15}" text-anchor="middle" '
            f'font-size="10" fill="{COLORS["axis"]}">{_format_y(v)}</text>'
        )

    # Bars + labels
    for i, (label, val) in enumerate(zip(labels, values)):
        y = margin["top"] + i * (bar_h + bar_gap) + bar_gap / 2
        x0 = margin["left"]
        x1 = x_for(val)
        bar_w = x1 - x0
        svg_parts.append(
            f'<text x="{margin["left"] - 8}" y="{y + bar_h/2 + 4}" text-anchor="end" '
            f'font-size="11" fill="{COLORS["text"]}">{label[:30]}</text>'
        )
        # Bar
        svg_parts.append(
            f'<rect x="{x0:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
            f'fill="{COLORS["total"]}" opacity="0.8"/>'
        )
        # Value at end of bar
        label_text = _format_y(val)
        svg_parts.append(
            f'<text x="{x1 + 5:.1f}" y="{y + bar_h/2 + 4}" text-anchor="start" '
            f'font-size="10" fill="{COLORS["text"]}" font-weight="bold">{label_text}</text>'
        )

    # X-axis label
    svg_parts.append(
        f'<text x="{margin["left"] + plot_w/2}" y="{height - 5}" text-anchor="middle" '
        f'font-size="11" fill="{COLORS["axis"]}">{x_label}</text>'
    )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)
