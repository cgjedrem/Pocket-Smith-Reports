"""Line chart SVG generator.

Produces a self-contained SVG for a multi-series line chart.
Inputs: x_labels (list of month strings), series (dict of name -> values), title.
Output: SVG string.

Designed to be embedded in the MoM report HTML.
"""

import hashlib
from typing import Dict, List, Optional, Tuple
from html import escape
from uuid import uuid4

# Colors (consistent with v4 charts.py)
COLORS = {
    "partner_a": "#1f77b4",  # blue
    "partner_b": "#ff7f0e",  # orange
    "total": "#2ca02c",  # green
    "grid": "#e0e0e0",
    "axis": "#666",
    "text": "#333",
}


def _auto_y_bounds(
    values_lists: List[List[Optional[float]]], pad_pct: float = 0.1
) -> Tuple[float, float]:
    """Compute y-axis bounds that fit all values with padding."""
    all_vals: List[float] = [v for lst in values_lists for v in lst if v is not None]
    if not all_vals:
        return 0.0, 1.0
    lo, hi = min(all_vals), max(all_vals)
    if lo == hi:
        return (lo * 0.9 if lo else -1.0), ((hi * 1.1 if hi else 1.0) or 1.0)
    pad = (hi - lo) * pad_pct
    return lo - pad, hi + pad


def _format_y(v: float) -> str:
    """Format y-axis value (compact)."""
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    if abs(v) >= 1_000:
        return f"{v/1_000:.0f}k"
    return f"{v:.0f}"


def _chart_accessibility(
    title: str,
    x_labels: List[str],
    series: Dict[str, List[Optional[float]]],
    y_label: str,
    accessibility_id: Optional[str],
) -> Tuple[str, str, str, str]:
    """Return DOM-unique SVG accessibility IDs and descriptive text."""
    accessible_title = title.strip() or "Line chart"
    source = "|".join(
        [accessibility_id or accessible_title, y_label, *x_labels]
        + [f"{name}:{values}" for name, values in series.items()]
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
    title_id = f"line-chart-{prefix}-{digest}-{instance_id}-title"
    description_id = f"line-chart-{prefix}-{digest}-{instance_id}-description"
    description = (
        f"Line chart of {', '.join(series) or 'values'} by {y_label} across "
        f"{len(x_labels)} month{'s' if len(x_labels) != 1 else ''}."
    )
    return title_id, description_id, accessible_title, description


def render_line_chart(
    x_labels: List[str],
    series: Dict[str, List[Optional[float]]],
    title: str,
    y_label: str = "NOK",
    width: int = 760,
    height: int = 260,
    y_min: Optional[float] = None,
    y_max: Optional[float] = None,
    show_value_labels: bool = True,
    show_value_labels_for: Optional[set] = None,
    accessibility_id: Optional[str] = None,
) -> str:
    """Render a line chart as SVG.

    show_value_labels: master switch
    show_value_labels_for: optional set of series names to label (overrides
        show_value_labels for individual series; None = all, empty set = none)

    Args:
        x_labels: e.g. ['2025-08', '2025-09', ...]
        series: e.g. {'Partner A': [43000, 45000, ...], 'Partner B': [40000, ...]}
        title: chart title
        y_label: y-axis label
        width, height: SVG dimensions
        y_min, y_max: optional y-axis bounds (auto if None)
        show_value_labels: if True, show value above each data point
        show_value_labels_for: optional set of series names to label
        accessibility_id: optional stable context for SVG metadata ID prefixes
    """
    if not x_labels or not series:
        return '<p class="empty">No data for line chart.</p>'

    n = len(x_labels)
    # Extra top margin to fit legend + value labels above data points
    # Extra bottom margin to fit staggered labels below data points
    margin = {"top": 100, "right": 30, "bottom": 90, "left": 80}
    plot_w = width - margin["left"] - margin["right"]
    plot_h = height - margin["top"] - margin["bottom"]

    # x positions (evenly spaced)
    x_positions = [margin["left"] + (plot_w * i / max(n - 1, 1)) for i in range(n)]

    # y bounds — pad to make room for value labels above max
    all_vals = []
    for vals in series.values():
        all_vals.extend(v for v in vals if v is not None)
    if y_min is None or y_max is None:
        y_min_auto, y_max_auto = _auto_y_bounds(list(series.values()))
        # Add 8% headroom for value labels
        if y_max is None and y_max_auto > 0:
            y_max_auto = y_max_auto * 1.08
        if y_min is None and y_min_auto < 0:
            y_min_auto = y_min_auto * 1.08
        if y_min is None:
            y_min = y_min_auto
        if y_max is None:
            y_max = y_max_auto

    def y_pos(v: float) -> float:
        if y_max == y_min:
            return margin["top"] + plot_h / 2
        return margin["top"] + plot_h * (1 - (v - y_min) / (y_max - y_min))

    title_id, description_id, accessible_title, description = _chart_accessibility(
        title, x_labels, series, y_label, accessibility_id
    )
    svg_parts = [
        f'<svg class="line-chart" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-labelledby="{title_id} {description_id}" style="font-family:sans-serif;">',
        f'<title id="{title_id}">{escape(accessible_title)}</title>',
        f'<desc id="{description_id}">{escape(description)}</desc>',
    ]
    # Title (top, above legend)
    svg_parts.append(
        f'<text x="{width/2}" y="18" text-anchor="middle" '
        f'font-size="14" font-weight="bold" fill="{COLORS["text"]}">{escape(title)}</text>'
    )

    # Grid lines (5 horizontal)
    n_grid = 5
    for i in range(n_grid + 1):
        y = margin["top"] + plot_h * i / n_grid
        v = y_max - (y_max - y_min) * i / n_grid
        svg_parts.append(
            f'<line x1="{margin["left"]}" y1="{y:.1f}" x2="{margin["left"] + plot_w}" y2="{y:.1f}" '
            f'stroke="{COLORS["grid"]}" stroke-width="0.5"/>'
        )
        # Y-axis tick labels — right-aligned to left margin
        svg_parts.append(
            f'<text x="{margin["left"] - 8}" y="{y + 4:.1f}" text-anchor="end" '
            f'font-size="10" fill="{COLORS["axis"]}">{_format_y(v)}</text>'
        )

    # X-axis labels (below the plot)
    for i, label in enumerate(x_labels):
        short = label[2:].replace("-", "/") if len(label) >= 7 else label
        rotation = -30 if n > 6 else 0
        x = x_positions[i]
        y_text = margin["top"] + plot_h + 18
        if rotation:
            svg_parts.append(
                f'<text x="{x:.1f}" y="{y_text:.1f}" text-anchor="end" font-size="10" '
                f'fill="{COLORS["axis"]}" transform="rotate({rotation} {x:.1f} {y_text:.1f})">{short}</text>'
            )
        else:
            svg_parts.append(
                f'<text x="{x:.1f}" y="{y_text:.1f}" text-anchor="middle" font-size="10" '
                f'fill="{COLORS["axis"]}">{short}</text>'
            )

    # Y-axis label (rotated, far left, separate from tick labels)
    y_label_x = 15
    y_label_y = margin["top"] + plot_h / 2
    svg_parts.append(
        f'<text x="{y_label_x}" y="{y_label_y:.1f}" text-anchor="middle" '
        f'font-size="11" fill="{COLORS["axis"]}" '
        f'transform="rotate(-90 {y_label_x} {y_label_y:.1f})">{y_label}</text>'
    )

    # Color palette for series
    palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

    # Series lines + dots + value labels
    for idx, (name, vals) in enumerate(series.items()):
        color = palette[idx % len(palette)]
        # Build path
        path_parts = []
        for i, v in enumerate(vals):
            if v is None:
                continue
            x = x_positions[i]
            y = y_pos(v)
            if not path_parts:
                path_parts.append(f"M {x:.1f} {y:.1f}")
            else:
                path_parts.append(f"L {x:.1f} {y:.1f}")
        if path_parts:
            svg_parts.append(
                f'<path d="{" ".join(path_parts)}" fill="none" '
                f'stroke="{color}" stroke-width="2"/>'
            )
        # Dots + value labels
        for i, v in enumerate(vals):
            if v is None:
                continue
            x = x_positions[i]
            y = y_pos(v)
            svg_parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"/>'
            )
            # Value label above the point (small, in series color)
            # show_value_labels_for overrides per-series: only show labels
            # for series in the set (if set is provided)
            show_this_label = show_value_labels
            if show_value_labels_for is not None:
                show_this_label = name in show_value_labels_for
            if show_this_label:
                # Format as compact: 45k for 45000, 8.2M for 8200000
                label = _format_y(v)
                # Stagger labels with large offsets so 3 series at same x
                # don't overlap even when their y values are similar.
                if idx == 0:
                    label_y = y - 12  # above (Partner A)
                elif idx == 1:
                    label_y = y + 24  # below (Partner B)
                else:  # idx 2+
                    label_y = y - 36  # far above (Total)
                svg_parts.append(
                    f'<text x="{x:.1f}" y="{label_y:.1f}" text-anchor="middle" '
                    f'font-size="8" fill="{color}" font-weight="bold">{label}</text>'
                )

    # Legend (top, below title, horizontal layout)
    legend_y = 38
    legend_items = list(series.keys())
    # Calculate legend width
    legend_total_w = sum(max(70, len(name) * 7 + 30) for name in legend_items)
    legend_x = (width - legend_total_w) / 2
    cur_x = legend_x
    for idx, name in enumerate(legend_items):
        color = palette[idx % len(palette)]
        item_w = max(70, len(name) * 7 + 30)
        svg_parts.append(
            f'<rect x="{cur_x:.1f}" y="{legend_y - 9}" width="12" height="10" fill="{color}"/>'
        )
        svg_parts.append(
            f'<text x="{cur_x + 16:.1f}" y="{legend_y}" font-size="10" fill="{COLORS["text"]}">{escape(name)}</text>'
        )
        cur_x += item_w

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)
