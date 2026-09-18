"""Inline SVG donut charts with on-chart % labels. Larger fonts for readability."""

import math
from html import escape

# Color palettes
COLOR_PARTNER_A = "#1f77b4"
COLOR_PARTNER_B = "#ff7f0e"
COLORS = [
    COLOR_PARTNER_A,
    COLOR_PARTNER_B,
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
    "#6b8e23",
    "#4682b4",
    "#d2691e",
    "#a0522d",
    "#708090",
    "#bdb76b",
    "#5f9ea0",
    "#cd5c5c",
    "#8b4513",
    "#2e8b57",
    "#dda0dd",
    "#ff6347",
    "#40e0d0",
    "#ee82ee",
    "#90ee90",
]


def _arc_path(cx, cy, r_outer, r_inner, start_angle, end_angle):
    """Generate an SVG path for an arc segment (donut slice)."""
    a0 = math.radians(start_angle - 90)
    a1 = math.radians(end_angle - 90)
    x0o, y0o = cx + r_outer * math.cos(a0), cy + r_outer * math.sin(a0)
    x1o, y1o = cx + r_outer * math.cos(a1), cy + r_outer * math.sin(a1)
    x0i, y0i = cx + r_inner * math.cos(a0), cy + r_inner * math.sin(a0)
    x1i, y1i = cx + r_inner * math.cos(a1), cy + r_inner * math.sin(a1)
    large_arc = 1 if (end_angle - start_angle) > 180 else 0
    return (
        f"M {x0o:.2f} {y0o:.2f} "
        f"A {r_outer} {r_outer} 0 {large_arc} 1 {x1o:.2f} {y1o:.2f} "
        f"L {x1i:.2f} {y1i:.2f} "
        f"A {r_inner} {r_inner} 0 {large_arc} 0 {x0i:.2f} {y0i:.2f} Z"
    )


def _cos_deg(angle_deg):
    return math.cos(math.radians(angle_deg))


def _sin_deg(angle_deg):
    return math.sin(math.radians(angle_deg))


def render_donut_two_tier(
    outer_data,
    inner_data,
    title="",
    size=600,
    outer_min_pct_label=0.05,
    inner_min_pct_label=0.08,
):
    """Two-tier donut chart (outer ring + inner ring).

    Args:
        outer_data: [(label, value), ...] for outer ring
        inner_data: [(label, value), ...] for inner ring (sub-segments of outer)
        title: title text
        size: SVG size in px
    """
    cx, cy = size // 2, size // 2
    r_outer = size // 2 - 30
    r_mid = int(r_outer * 0.72)
    r_inner = int(r_outer * 0.45)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
    ]
    if title:
        svg.append(
            f'<text x="{cx}" y="34" text-anchor="middle" font-size="20" font-weight="600" fill="#222">{title}</text>'
        )

    outer_total = sum(v for _, v in outer_data)
    inner_total = sum(v for _, v in inner_data)

    if outer_total == 0:
        svg.append(
            f'<text x="{cx}" y="{cy}" text-anchor="middle" font-size="22" fill="#999">No data</text>'
        )
        svg.append("</svg>")
        return "\n".join(svg)

    # Outer ring
    angle = 0
    for i, (label, value) in enumerate(outer_data):
        if value <= 0:
            continue
        sweep = (value / outer_total) * 360
        end_angle = angle + sweep
        path = _arc_path(cx, cy, r_outer, r_mid, angle, end_angle)
        color = COLORS[i % len(COLORS)]
        svg.append(
            f'<path d="{path}" fill="{color}" stroke="white" stroke-width="1.5"/>'
        )
        # On-chart label
        pct = value / outer_total
        if pct >= outer_min_pct_label:
            mid_angle = (angle + end_angle) / 2
            tx = cx + (r_outer * 0.86) * _cos_deg(mid_angle)
            ty = cy + (r_outer * 0.86) * _sin_deg(mid_angle)
            svg.append(
                f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="middle" dominant-baseline="middle" font-size="13" font-weight="600" fill="white">{pct*100:.0f}%</text>'
            )
        angle = end_angle

    # Inner ring
    angle = 0
    for i, (label, value) in enumerate(inner_data):
        if value <= 0:
            continue
        sweep = (value / outer_total) * 360  # inner against outer
        end_angle = angle + sweep
        path = _arc_path(cx, cy, r_mid, r_inner, angle, end_angle)
        color = COLORS[(i + 6) % len(COLORS)]  # different palette
        svg.append(
            f'<path d="{path}" fill="{color}" stroke="white" stroke-width="1.5"/>'
        )
        pct = value / outer_total
        if pct >= inner_min_pct_label:
            mid_angle = (angle + end_angle) / 2
            tx = cx + (r_mid * 0.78) * _cos_deg(mid_angle)
            ty = cy + (r_mid * 0.78) * _sin_deg(mid_angle)
            svg.append(
                f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="middle" dominant-baseline="middle" font-size="11" font-weight="600" fill="white">{pct*100:.0f}%</text>'
            )
        angle = end_angle

    # Center text
    svg.append(
        f'<text x="{cx}" y="{cy - 8}" text-anchor="middle" font-size="14" fill="#666">Total</text>'
    )
    svg.append(
        f'<text x="{cx}" y="{cy + 18}" text-anchor="middle" font-size="24" font-weight="700" fill="#222">{outer_total:,.0f}</text>'
    )

    svg.append("</svg>")
    return "\n".join(svg)


def render_donut_single(
    data, title="", size=600, min_pct_label=0.04, center_label="", center_value=""
):
    """Single-tier donut chart."""
    cx, cy = size // 2, size // 2
    r_outer = size // 2 - 30
    r_inner = int(r_outer * 0.50)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
    ]
    if title:
        svg.append(
            f'<text x="{cx}" y="34" text-anchor="middle" font-size="20" font-weight="600" fill="#222">{title}</text>'
        )

    total = sum(v for _, v in data)
    if total == 0:
        svg.append(
            f'<text x="{cx}" y="{cy}" text-anchor="middle" font-size="22" fill="#999">No data</text>'
        )
        svg.append("</svg>")
        return "\n".join(svg)

    angle = 0
    for i, (label, value) in enumerate(data):
        if value <= 0:
            continue
        sweep = (value / total) * 360
        end_angle = angle + sweep
        path = _arc_path(cx, cy, r_outer, r_inner, angle, end_angle)
        color = COLORS[i % len(COLORS)]
        svg.append(
            f'<path d="{path}" fill="{color}" stroke="white" stroke-width="1.5"/>'
        )
        pct = value / total
        if pct >= min_pct_label:
            mid_angle = (angle + end_angle) / 2
            tx = cx + (r_outer * 0.75) * _cos_deg(mid_angle)
            ty = cy + (r_outer * 0.75) * _sin_deg(mid_angle)
            svg.append(
                f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="middle" dominant-baseline="middle" font-size="14" font-weight="600" fill="white">{pct*100:.0f}%</text>'
            )
        angle = end_angle

    # Center text
    if center_label:
        svg.append(
            f'<text x="{cx}" y="{cy - 12}" text-anchor="middle" font-size="14" fill="#666">{center_label}</text>'
        )
    if center_value:
        svg.append(
            f'<text x="{cx}" y="{cy + 16}" text-anchor="middle" font-size="26" font-weight="700" fill="#222">{center_value}</text>'
        )
    else:
        svg.append(
            f'<text x="{cx}" y="{cy + 8}" text-anchor="middle" font-size="26" font-weight="700" fill="#222">{total:,.0f}</text>'
        )

    svg.append("</svg>")
    return "\n".join(svg)


def render_legend(items, size=12):
    """Render a color legend (label only, color in a swatch)."""
    parts = []
    for label, color in items:
        parts.append(
            f'<span style="display:inline-flex;align-items:center;margin-right:14px;margin-bottom:4px;">'
            f'<span style="display:inline-block;width:{size}px;height:{size}px;background:{color};margin-right:6px;border-radius:2px;"></span>'
            f'<span style="font-size:13px;">{label}</span></span>'
        )
    return '<div style="line-height:1.6;">' + " ".join(parts) + "</div>"


def render_vertical_bar(
    data,
    title="",
    width=560,
    height=400,
    bar_width=120,
    gap=60,
    show_values=True,
    show_pct=True,
    value_fmt=",.0f",
    color_map=None,
    y_axis_label="",
):
    """Vertical bar chart with on-bar value labels. Good for 2-3 series side by side.

    Args:
        data: list of (label, value) or (label, value, color) tuples
        title: chart title (above)
        width: total SVG width
        height: total SVG height
        bar_width: width of each bar
        gap: gap between bars
        show_values: show numeric value above each bar
        show_pct: show percentage after numeric value
        color_map: dict mapping label -> color
    """
    # Don't sort — keep input order
    total = sum(v for _, v, *_ in data)
    if total == 0:
        title_markup = (
            f'<text x="{width//2}" y="30" text-anchor="middle" font-size="20" font-weight="700" fill="#222">{escape(str(title))}</text>'
            if title
            else ""
        )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 90" width="{width}">'
            f'{title_markup}<text x="{width//2}" y="72" text-anchor="middle" font-size="16" fill="#999">No data</text></svg>'
        )

    n = len(data)
    # Reserve top space for title + value labels
    title_h = 50 if title else 10
    value_h = 40
    chart_top = title_h + value_h
    chart_bottom = height - 50  # leave room for x-axis labels
    chart_h = chart_bottom - chart_top

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">'
    ]

    if title:
        svg.append(
            f'<text x="{width//2}" y="30" text-anchor="middle" font-size="20" font-weight="700" fill="#222">{escape(str(title))}</text>'
        )

    # Compute bar positions (centered)
    total_bars_w = n * bar_width + (n - 1) * gap
    start_x = (width - total_bars_w) // 2

    max_val = max(v for _, v, *_ in data)
    # Y-axis: scale to max
    y_scale = chart_h / max_val if max_val > 0 else 1

    for i, item in enumerate(data):
        if len(item) == 3:
            label, value, color = item
        else:
            label, value = item
            if color_map and label in color_map:
                color = color_map[label]
            else:
                color = COLORS[i % len(COLORS)]
        if value <= 0:
            continue
        x = start_x + i * (bar_width + gap)
        bar_h = value * y_scale
        bar_y = chart_bottom - bar_h
        # Bar
        svg.append(
            f'<rect x="{x}" y="{bar_y:.1f}" width="{bar_width}" height="{bar_h:.1f}" fill="{color}" rx="4"/>'
        )
        # Value above bar
        if show_values:
            txt = f"{value:{value_fmt}}"
            if show_pct and total > 0:
                txt += f"\n({value/total*100:.1f}%)"
            # Split txt on newline for multi-line text
            lines = txt.split("\n")
            for li, line in enumerate(lines):
                font_size = 22 if li == 0 else 18
                weight = 800 if li == 0 else 600
                svg.append(
                    f'<text x="{x + bar_width/2:.1f}" y="{bar_y - 12 - (len(lines) - 1 - li) * 22}" text-anchor="middle" font-size="{font_size}" font-weight="{weight}" fill="#222">{line}</text>'
                )
        # X-axis label
        svg.append(
            f'<text x="{x + bar_width/2:.1f}" y="{chart_bottom + 22}" text-anchor="middle" font-size="18" font-weight="700" fill="#222">{escape(str(label))}</text>'
        )
        # Y-axis label on the left
        if i == 0 and y_axis_label:
            svg.append(
                f'<text x="10" y="{chart_top + chart_h/2}" text-anchor="middle" font-size="14" fill="#666" transform="rotate(-90 10 {chart_top + chart_h/2})">{escape(str(y_axis_label))}</text>'
            )

    # Y-axis line
    svg.append(
        f'<line x1="{start_x - 20}" y1="{chart_bottom}" x2="{width - start_x + 20}" y2="{chart_bottom}" stroke="#666" stroke-width="1.5"/>'
    )
    # Y-axis tick at top (max value)
    svg.append(
        f'<text x="{start_x - 24}" y="{chart_top + 6}" text-anchor="end" font-size="13" fill="#666">{max_val:,.0f}</text>'
    )
    svg.append(
        f'<text x="{start_x - 24}" y="{chart_bottom + 4}" text-anchor="end" font-size="13" fill="#666">0</text>'
    )

    svg.append("</svg>")
    return "\n".join(svg)
    """Render a color legend (label only, color in a swatch)."""
    parts = []
    for label, color in items:
        parts.append(
            f'<span style="display:inline-flex;align-items:center;margin-right:14px;margin-bottom:4px;">'
            f'<span style="display:inline-block;width:{size}px;height:{size}px;background:{color};margin-right:6px;border-radius:2px;"></span>'
            f'<span style="font-size:13px;">{label}</span></span>'
        )
    return '<div style="line-height:1.6;">' + " ".join(parts) + "</div>"


def render_horizontal_bar(
    data,
    title="",
    width=540,
    bar_height=44,
    gap=10,
    show_values=True,
    show_pct=True,
    value_fmt=",.0f",
    color_map=None,
    ink="#222",
    track="#f0f0f0",
):
    """Horizontal bar chart with on-bar value labels.

    Args:
        data: list of (label, value) or (label, value, color) tuples
        title: chart title (above)
        width: total SVG width
        bar_height: height of each bar
        gap: gap between bars
        show_values: show numeric value at end of each bar
        show_pct: show percentage after numeric value
        color_map: dict mapping label to color.
    """
    # Sort by value descending
    data = sorted(data, key=lambda x: -x[1])
    total = sum(v for _, v, *_ in data)
    if total == 0:
        title_markup = (
            f'<text x="{width//2}" y="30" text-anchor="middle" font-size="22" font-weight="700" fill="{ink}">{escape(title)}</text>'
            if title
            else ""
        )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 90" width="{width}">'
            f'{title_markup}<text x="{width//2}" y="72" text-anchor="middle" font-size="16" fill="#999">No data</text></svg>'
        )

    label_w = 300  # width for label column
    value_w = 220  # width for value column on the right
    bar_w = width - label_w - value_w - 20

    n = len(data)
    chart_h = n * (bar_height + gap) + 10
    svg_h = chart_h + (55 if title else 10)
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {svg_h}" width="{width}" height="{svg_h}">'
    ]

    if title:
        svg.append(
            f'<text x="{width//2}" y="32" text-anchor="middle" font-size="22" font-weight="700" fill="{ink}">{escape(title)}</text>'
        )

    y0 = 55 if title else 10
    for i, item in enumerate(data):
        if len(item) == 3:
            label, value, color = item
        else:
            label, value = item
            if color_map and label in color_map:
                color = color_map[label]
            else:
                color = COLORS[i % len(COLORS)]
        if value <= 0:
            continue
        y = y0 + i * (bar_height + gap)
        # Label (right-aligned, vertically centered in bar)
        svg.append(
            f'<text x="{label_w - 12}" y="{y + bar_height/2 + 8}" text-anchor="end" font-size="22" font-weight="700" fill="{ink}">{escape(str(label))}</text>'
        )
        # Bar background
        svg.append(
            f'<rect x="{label_w}" y="{y}" width="{bar_w}" height="{bar_height}" fill="{track}" rx="4"/>'
        )
        # Bar fill
        bar_fill_w = (value / total) * bar_w
        svg.append(
            f'<rect x="{label_w}" y="{y}" width="{bar_fill_w:.1f}" height="{bar_height}" fill="{color}" rx="4"/>'
        )
        # Value + pct on right
        if show_values:
            txt = f"{value:{value_fmt}}"
            if show_pct and total > 0:
                txt += f"    ({value/total*100:.1f}%)"
            svg.append(
                f'<text x="{label_w + bar_w + 12}" y="{y + bar_height/2 + 8}" font-size="22" font-weight="800" fill="{ink}">{txt}</text>'
            )

    svg.append("</svg>")
    return "\n".join(svg)


def render_partner_comparison_bars(data, title="", width=720):
    """Render a fixed-order two-person KPI comparison chart."""
    row_height = 52
    top = 60
    height = top + len(data) * row_height + 18
    track_x = 220
    track_width = 260
    value_x = 510
    share_x = 676
    scale = max((abs(value) for _, value, *_ in data), default=0) or 1
    share_total = sum(abs(value) for _, value, *_ in data)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">'
    ]
    if title:
        svg.append(
            f'<text x="28" y="34" font-size="21" font-weight="700" fill="#17324d">{escape(title)}</text>'
        )
        svg.append(
            f'<line x1="28" y1="46" x2="{width - 28}" y2="46" stroke="#d8e3ec" stroke-width="1"/>'
        )

    for index, item in enumerate(data):
        if len(item) == 3:
            label, value, color = item
        else:
            label, value = item
            color = COLORS[index % len(COLORS)]
        y = top + index * row_height
        fill_width = abs(value) / scale * track_width
        share = abs(value) / share_total * 100 if share_total else 0.0
        value_text = f"{value:,.0f}"

        svg.append(
            f'<circle cx="36" cy="{y + 10}" r="6" fill="{color}"/>'
            f'<text x="52" y="{y + 16}" font-size="17" font-weight="700" fill="#19303d">{escape(str(label))}</text>'
        )
        svg.append(
            f'<rect x="{track_x}" y="{y}" width="{track_width}" height="20" rx="10" fill="#e7eef3"/>'
            f'<rect x="{track_x}" y="{y}" width="{fill_width:.1f}" height="20" rx="10" fill="{color}"/>'
        )
        svg.append(
            f'<text x="{value_x}" y="{y + 16}" font-size="17" font-weight="700" fill="#19303d">{value_text}</text>'
            f'<text x="{share_x}" y="{y + 16}" text-anchor="end" font-size="15" font-weight="700" fill="#5d6c75">{share:.1f}%</text>'
        )

    svg.append("</svg>")
    return "\n".join(svg)


def render_partner_kpi_matrix(series, colors, width=720, style="rail"):
    """Render three fixed-position KPI comparisons in one themed chart."""
    column_width = (width - 56) / len(series)
    bar_width = column_width - 32
    height = 225
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">'
    ]

    if style == "pulse":
        svg.append(
            '<defs><filter id="neon"><feGaussianBlur stdDeviation="2" result="blur"/>'
            '<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>'
        )

    for column, (title, data) in enumerate(series):
        left = 28 + column * column_width
        scale = max((abs(value) for _, value, *_ in data), default=0) or 1
        share_total = sum(abs(value) for _, value, *_ in data)
        svg.append(
            f'<text x="{left:.1f}" y="30" font-size="17" font-weight="700" fill="{colors["ink"]}">{escape(title)}</text>'
            f'<line x1="{left:.1f}" y1="42" x2="{left + column_width - 18:.1f}" y2="42" stroke="{colors["rule"]}" stroke-width="1"/>'
        )
        for index, (label, value, color) in enumerate(data):
            y = 60 + index * 72
            share = abs(value) / share_total * 100 if share_total else 0.0
            fill_width = abs(value) / scale * bar_width
            if style == "pulse":
                segment_count = 10
                segment_gap = 4
                segment_width = (
                    bar_width - segment_gap * (segment_count - 1)
                ) / segment_count
                active_segments = round(abs(value) / scale * segment_count)
                svg.append(
                    f'<text x="{left:.1f}" y="{y + 10}" font-size="13" font-weight="700" fill="{colors["ink"]}">{escape(str(label)).upper()}</text>'
                )
                for segment in range(segment_count):
                    x = left + segment * (segment_width + segment_gap)
                    fill = color if segment < active_segments else colors["track"]
                    glow = ' filter="url(#neon)"' if segment < active_segments else ""
                    svg.append(
                        f'<rect x="{x:.1f}" y="{y + 22}" width="{segment_width:.1f}" height="16" rx="2" fill="{fill}"{glow}/>'
                    )
            elif style == "banner":
                banner_points = (
                    f"{left:.1f},{y + 22} {left + fill_width - 9:.1f},{y + 22} "
                    f"{left + fill_width:.1f},{y + 29} {left + fill_width - 9:.1f},{y + 36} {left:.1f},{y + 36}"
                )
                svg.append(
                    f'<circle cx="{left + 8:.1f}" cy="{y + 5}" r="8" fill="{color}"/>'
                    f'<text x="{left + 22:.1f}" y="{y + 10}" font-size="13" font-weight="700" fill="{colors["ink"]}">{escape(str(label))}</text>'
                    f'<rect x="{left:.1f}" y="{y + 22}" width="{bar_width:.1f}" height="14" rx="2" fill="{colors["track"]}"/>'
                    f'<polygon points="{banner_points}" fill="{color}"/>'
                )
            elif style == "seal":
                radius = 22
                circumference = 2 * math.pi * radius
                dash = abs(value) / scale * circumference
                center_x = left + 27
                center_y = y + 29
                svg.append(
                    f'<circle cx="{center_x:.1f}" cy="{center_y}" r="{radius}" fill="none" stroke="{colors["track"]}" stroke-width="7"/>'
                    f'<circle cx="{center_x:.1f}" cy="{center_y}" r="{radius}" fill="none" stroke="{color}" stroke-width="7" stroke-linecap="round" stroke-dasharray="{dash:.1f} {circumference:.1f}" transform="rotate(-90 {center_x:.1f} {center_y})"/>'
                    f'<text x="{left + 62:.1f}" y="{y + 23}" font-size="13" font-weight="700" fill="{colors["ink"]}">{escape(str(label))}</text>'
                )
            else:
                svg.append(
                    f'<circle cx="{left + 5:.1f}" cy="{y + 5}" r="5" fill="{color}"/>'
                    f'<text x="{left + 17:.1f}" y="{y + 10}" font-size="13" font-weight="700" fill="{colors["ink"]}">{escape(str(label))}</text>'
                    f'<rect x="{left:.1f}" y="{y + 22}" width="{bar_width:.1f}" height="14" rx="7" fill="{colors["track"]}"/>'
                    f'<rect x="{left:.1f}" y="{y + 22}" width="{fill_width:.1f}" height="14" rx="7" fill="{color}"/>'
                )
            value_x = left + 62 if style == "seal" else left
            svg.append(
                f'<text x="{value_x:.1f}" y="{y + 57}" font-size="15" font-weight="700" fill="{colors["ink"]}">{value:,.0f}</text>'
                f'<text x="{left + bar_width:.1f}" y="{y + 57}" text-anchor="end" font-size="13" font-weight="700" fill="{colors["muted"]}">{share:.1f}%</text>'
            )

    svg.append("</svg>")
    return "\n".join(svg)
