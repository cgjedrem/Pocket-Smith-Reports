#!/usr/bin/env python3
"""render_mega_v7.py — assemble the v7 mega report.

Builds ONE PDF with these sections (top → bottom):
  1. Cover / summary numbers
    2. Income + spend MoM line chart
    3. Cumulative real-spend line
    4. Partner A / Partner B share MoM
  5. Per-category MoM grid (top 15 categories, mini sparkline each)
  6. Top repeating merchants (top 10, cumulative lines)
    7. Trips for the configured period
  8. Per-trip drilldown tables
  9. Methodology + caveats

Output: configured report output directory.
"""

import os
import sys
import json
import html as H
from datetime import date as D

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from trend11 import (
    compute_all,
    real_spend_series,
    income_series,
    savings_series,
    per_category_series,
    per_merchant_series,
    pct_partner_shares,
    MONTHS,
    per_parent_category_series,
)
from trips import detect_trips, trips_summary
from compare import _resolve_month_path


def _esc(s):
    return H.escape(str(s))


# ============================================================
# SVG chart helpers
# ============================================================


def _svg_line_chart(
    labels, series, title, y_label="NOK", colors=None, width=900, height=320
):
    """Multi-line chart, x=months, y=value. series = list of (name, values, color)."""
    if not series:
        return f'<div class="empty">{_esc(title)}: no data</div>'
    n = len(labels)
    if colors is None:
        colors = [
            "#1f77b4",
            "#ff7f0e",
            "#2ca02c",
            "#d62728",
            "#9467bd",
            "#8c564b",
            "#e377c2",
            "#7f7f7f",
        ]

    # Compute scales
    all_vals = [v for _, vals, _ in series for v in vals if v is not None]
    if not all_vals:
        return f'<div class="empty">{_esc(title)}: no data</div>'
    ymin = min(all_vals)
    ymax = max(all_vals)
    if ymin == ymax:
        ymin, ymax = ymin - 1, ymax + 1
    pad_y = (ymax - ymin) * 0.1
    ymin -= pad_y
    ymax += pad_y

    pad_l, pad_r, pad_t, pad_b = 70, 20, 30, 60
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    xstep = plot_w / max(n - 1, 1)

    def xpos(i):
        return pad_l + i * xstep

    def ypos(v):
        return pad_t + plot_h - ((v - ymin) / (ymax - ymin) * plot_h)

    parts = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" class="chart">'
    ]
    # title
    parts.append(
        f'<text x="{width/2}" y="20" text-anchor="middle" font-size="14" font-weight="bold" fill="#1a202c">{_esc(title)}</text>'
    )
    # gridlines (5 horizontal)
    for i in range(6):
        gy = pad_t + (plot_h * i / 5)
        gv = ymax - (ymax - ymin) * i / 5
        parts.append(
            f'<line x1="{pad_l}" y1="{gy}" x2="{pad_l+plot_w}" y2="{gy}" stroke="#e2e8f0" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{pad_l-8}" y="{gy+4}" text-anchor="end" font-size="10" fill="#718096">{_fmt_nok(gv)}</text>'
        )
    # y-axis label
    parts.append(
        f'<text x="15" y="{pad_t+plot_h/2}" transform="rotate(-90 15 {pad_t+plot_h/2})" text-anchor="middle" font-size="11" fill="#4a5568">{_esc(y_label)}</text>'
    )
    # x labels
    for i, lbl in enumerate(labels):
        parts.append(
            f'<text x="{xpos(i)}" y="{pad_t+plot_h+18}" text-anchor="middle" font-size="10" fill="#4a5568" transform="rotate(-30 {xpos(i)} {pad_t+plot_h+18})">{_esc(lbl)}</text>'
        )
    # zero line if range crosses 0
    if ymin < 0 < ymax:
        zy = ypos(0)
        parts.append(
            f'<line x1="{pad_l}" y1="{zy}" x2="{pad_l+plot_w}" y2="{zy}" stroke="#a0aec0" stroke-width="1" stroke-dasharray="4,3"/>'
        )
    # series
    for idx, (name, vals, color) in enumerate(series):
        pts = []
        for i, v in enumerate(vals):
            if v is None:
                continue
            pts.append(f"{xpos(i):.1f},{ypos(v):.1f}")
        if not pts:
            continue
        parts.append(
            f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="2.5"/>'
        )
        # dots
        for i, v in enumerate(vals):
            if v is None:
                continue
            parts.append(
                f'<circle cx="{xpos(i):.1f}" cy="{ypos(v):.1f}" r="3.5" fill="{color}"/>'
            )
    # legend
    leg_x = pad_l + 10
    leg_y = pad_t + 5
    for idx, (name, _, color) in enumerate(series):
        lx = leg_x + (idx % 2) * 200
        ly = leg_y + (idx // 2) * 18
        parts.append(
            f'<rect x="{lx}" y="{ly-9}" width="12" height="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{lx+18}" y="{ly-5}" font-size="10" fill="#1a202c">{_esc(name)}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def _svg_sparkline(
    values, color="#1f77b4", width=160, height=40, label="", val_label=None
):
    """Single line sparkline with optional endpoint label."""
    vals = [v for v in values if v is not None]
    if not vals:
        return f'<div class="empty">{_esc(label or "")}: no data</div>'
    ymin, ymax = min(vals), max(vals)
    if ymin == ymax:
        ymin, ymax = ymin - 1, ymax + 1
    n = len(values)
    pad_l, pad_r, pad_t, pad_b = 4, 4, 6, 12
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    def xpos(i):
        return pad_l + i * (plot_w / max(n - 1, 1))

    def ypos(v):
        return pad_t + plot_h - ((v - ymin) / (ymax - ymin) * plot_h)

    pts = []
    for i, v in enumerate(values):
        if v is None:
            continue
        pts.append(f"{xpos(i):.1f},{ypos(v):.1f}")
    parts = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" class="spark">'
    ]
    if label:
        parts.append(
            f'<text x="{width/2}" y="9" text-anchor="middle" font-size="8" fill="#4a5568">{_esc(label)}</text>'
        )
    if pts:
        parts.append(
            f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1.5"/>'
        )
        # last dot
        last_v = next((v for v in reversed(values) if v is not None), None)
        if last_v is not None:
            li = len(values) - 1 - [v for v in reversed(values)].index(last_v)
            parts.append(
                f'<circle cx="{xpos(li):.1f}" cy="{ypos(last_v):.1f}" r="2.5" fill="{color}"/>'
            )
            if val_label is not None:
                parts.append(
                    f'<text x="{width-2}" y="{height-1}" text-anchor="end" font-size="7" fill="#2d3748">{_esc(val_label)}</text>'
                )
    parts.append("</svg>")
    return "\n".join(parts)


def _svg_stacked_pct(
    labels, partner_a_pct, partner_b_pct, title, width=900, height=280
):
    """Partner A / Partner B stacked 100% bar chart per month."""
    n = len(labels)
    pad_l, pad_r, pad_t, pad_b = 60, 20, 30, 60
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    bar_w = plot_w / n * 0.65
    parts = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" class="chart">'
    ]
    parts.append(
        f'<text x="{width/2}" y="20" text-anchor="middle" font-size="14" font-weight="bold" fill="#1a202c">{_esc(title)}</text>'
    )
    # gridlines (0/25/50/75/100)
    for i, pct in enumerate([0, 25, 50, 75, 100]):
        gy = pad_t + plot_h - (pct / 100 * plot_h)
        parts.append(
            f'<line x1="{pad_l}" y1="{gy}" x2="{pad_l+plot_w}" y2="{gy}" stroke="#e2e8f0" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{pad_l-8}" y="{gy+4}" text-anchor="end" font-size="10" fill="#718096">{pct}%</text>'
        )
    # bars
    for i, lbl in enumerate(labels):
        cx = pad_l + (i + 0.5) * (plot_w / n)
        x = cx - bar_w / 2
        pc = partner_a_pct[i] if partner_a_pct[i] is not None else 0
        pr = partner_b_pct[i] if partner_b_pct[i] is not None else 0
        # Partner A bottom
        height_partner_a = plot_h * pc / 100
        height_partner_b = plot_h * pr / 100
        parts.append(
            f'<rect x="{x:.1f}" y="{pad_t+plot_h-height_partner_a:.1f}" width="{bar_w:.1f}" height="{height_partner_a:.1f}" fill="#1f77b4"/>'
        )
        parts.append(
            f'<rect x="{x:.1f}" y="{pad_t+plot_h-height_partner_a-height_partner_b:.1f}" width="{bar_w:.1f}" height="{height_partner_b:.1f}" fill="#ff7f0e"/>'
        )
        # pct labels
        if pc >= 5:
            parts.append(
                f'<text x="{cx:.1f}" y="{pad_t+plot_h-height_partner_a/2+4:.1f}" text-anchor="middle" font-size="9" fill="white" font-weight="bold">{pc:.0f}%</text>'
            )
        if pr >= 5:
            parts.append(
                f'<text x="{cx:.1f}" y="{pad_t+plot_h-height_partner_a-height_partner_b/2+4:.1f}" text-anchor="middle" font-size="9" fill="white" font-weight="bold">{pr:.0f}%</text>'
            )
        # x label
        parts.append(
            f'<text x="{cx:.1f}" y="{pad_t+plot_h+18}" text-anchor="middle" font-size="10" fill="#4a5568" transform="rotate(-30 {cx:.1f} {pad_t+plot_h+18})">{_esc(lbl)}</text>'
        )
    # legend
    parts.append(
        f'<rect x="{pad_l+10}" y="{pad_t+5}" width="12" height="12" fill="#1f77b4"/>'
    )
    parts.append(
        f'<text x="{pad_l+28}" y="{pad_t+15}" font-size="11" fill="#1a202c">Partner A</text>'
    )
    parts.append(
        f'<rect x="{pad_l+110}" y="{pad_t+5}" width="12" height="12" fill="#ff7f0e"/>'
    )
    parts.append(
        f'<text x="{pad_l+128}" y="{pad_t+15}" font-size="11" fill="#1a202c">Partner B</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def _fmt_nok(n):
    if n is None:
        return "n/a"
    return f"{n:,.0f}"


def _configured_export_paths():
    """Return every configured monthly source path or fail before render."""
    return [_resolve_month_path(yyyy_mm) for yyyy_mm, _, _ in MONTHS]


# ============================================================
# HTML sections
# ============================================================

CSS = """
@page { size: A4; margin: 18mm 14mm; }
body { font-family: 'Helvetica', sans-serif; color: #1a202c; font-size: 10pt; line-height: 1.4; }
h1 { font-size: 22pt; margin: 0 0 4pt 0; color: #1a202c; }
h2 { font-size: 14pt; margin: 14pt 0 6pt 0; color: #2b6cb0; border-bottom: 2px solid #bee3f8; padding-bottom: 3pt; }
h3 { font-size: 11pt; margin: 8pt 0 4pt 0; color: #2c5282; }
.meta { font-size: 9pt; color: #718096; margin-bottom: 8pt; }
.kpi-row { display: flex; gap: 10pt; margin: 8pt 0; }
.kpi-box { flex: 1; border: 1px solid #cbd5e0; border-radius: 4pt; padding: 6pt 8pt; background: #f7fafc; }
.kpi-box .label { font-size: 8pt; color: #718096; text-transform: uppercase; letter-spacing: 0.5pt; }
.kpi-box .value { font-size: 18pt; font-weight: bold; color: #1a202c; margin-top: 2pt; }
.kpi-box .sub { font-size: 8pt; color: #4a5568; margin-top: 1pt; }
table { border-collapse: collapse; width: 100%; margin: 4pt 0; }
th, td { padding: 3pt 5pt; text-align: left; border-bottom: 1px solid #e2e8f0; font-size: 9pt; }
th { background: #edf2f7; font-weight: 600; color: #2d3748; }
tr:hover td { background: #f7fafc; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.empty { color: #a0aec0; font-style: italic; padding: 4pt; }
.spark-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 4pt; margin: 4pt 0; }
.merchant-row { display: flex; align-items: center; gap: 6pt; margin: 3pt 0; padding: 3pt 5pt; border-bottom: 1px solid #f0f0f0; }
.merchant-row .name { width: 220pt; font-size: 9pt; font-weight: 500; }
.merchant-row .stats { font-size: 8pt; color: #4a5568; min-width: 130pt; }
.merchant-row .spark { flex: 1; }
.trip-card { border: 1px solid #cbd5e0; border-radius: 4pt; padding: 6pt 8pt; margin: 4pt 0; background: #f7fafc; }
.trip-card .head { display: flex; justify-content: space-between; align-items: center; }
.trip-card .name { font-size: 12pt; font-weight: bold; color: #1a202c; }
.trip-card .total { font-size: 14pt; font-weight: bold; color: #c53030; }
details { margin: 4pt 0; }
summary { cursor: pointer; padding: 2pt 0; font-weight: 500; color: #2b6cb0; }
.method { background: #f7fafc; border-left: 3pt solid #3182ce; padding: 6pt 8pt; margin: 6pt 0; font-size: 9pt; color: #2d3748; }
.warn { color: #c53030; font-weight: 600; }
"""


def render_mega_v7():
    print("[v7] loading configured series...")
    series = compute_all()
    months_loaded = sum(1 for _, t, _, _ in series if t is not None)
    labels = [s[0] for s in series]
    print(f"[v7] {months_loaded}/{len(series)} months loaded")

    # Metrics
    inc = income_series(series)
    rs = real_spend_series(series)
    sv = savings_series(series)
    pc, pr = pct_partner_shares(series)

    # Net cash
    net = []
    for i, m in enumerate(series):
        if inc[i] is None or rs[i] is None:
            net.append(None)
        else:
            net.append(inc[i] - rs[i])

    # Cumulative
    cum_rs = []
    s = 0
    for v in rs:
        if v is None:
            cum_rs.append(None)
        else:
            s += v
            cum_rs.append(s)

    # Per-category top 15
    pcats = per_category_series(series, top_n=15)
    # Per-parent-category top 12 (v8 fix 2026-07-22 — shows parent cats
    # with paired reimbursements visible)
    ppcats = per_parent_category_series(series, top_n=12)
    # Per-merchant top 10 (>=3 mo)
    pmrcs = per_merchant_series(series, min_months=3, top_n=10)

    # Trips use only exports in the configured report period.
    print("[v7] detecting trips across configured months...")
    paths = _configured_export_paths()
    trips = detect_trips(paths)
    trips_sum = trips_summary(trips)
    print(f'[v7] {len(trips)} trips, {trips_sum["total"]:,.0f} NOK total')

    # === BUILD HTML ===
    period = f"{labels[0]} → {labels[-1]}" if labels else "configured period"
    html = [
        '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Finance Mega Report v7</title>'
    ]
    html.append(f"<style>{CSS}</style></head><body>")

    # 1. Cover / summary
    loaded = sum(1 for v in rs if v is not None)
    tot_inc = sum(v for v in inc if v is not None)
    tot_rs = sum(v for v in rs if v is not None)
    avg_inc = tot_inc / loaded if loaded else 0
    avg_rs = tot_rs / loaded if loaded else 0
    cum_n = (
        cum_rs[
            next(
                (i for i in range(len(cum_rs) - 1, -1, -1) if cum_rs[i] is not None), 0
            )
        ]
        or 0
    )
    avg_partner_a_pct = sum(v for v in pc if v is not None) / max(
        sum(1 for v in pc if v is not None), 1
    )

    html.append("<h1>Finance Mega Report v7</h1>")
    html.append(
        f'<div class="meta">{period} · {loaded}/{len(labels)} months loaded · NOK · generated {D.today().isoformat()}</div>'
    )

    html.append('<div class="kpi-row">')
    html.append(
        f'<div class="kpi-box"><div class="label">Avg Income / mo</div><div class="value">{avg_inc:,.0f}</div><div class="sub">NOK · across {loaded} months</div></div>'
    )
    html.append(
        f'<div class="kpi-box"><div class="label">Avg Real Spend / mo</div><div class="value">{avg_rs:,.0f}</div><div class="sub">NOK · excl savings+mortgage</div></div>'
    )
    html.append(
        f'<div class="kpi-box"><div class="label">Cumulative Spend</div><div class="value">{cum_n:,.0f}</div><div class="sub">NOK · sum across {loaded} months</div></div>'
    )
    html.append(
        f'<div class="kpi-box"><div class="label">Trips</div><div class="value">{len(trips)}</div><div class="sub">{trips_sum["total"]:,.0f} NOK total</div></div>'
    )
    html.append("</div>")

    html.append('<div class="kpi-row">')
    html.append(
        f'<div class="kpi-box"><div class="label">Avg % Partner A (cash share)</div><div class="value">{avg_partner_a_pct:.1f}%</div><div class="sub">Partner B = {100-avg_partner_a_pct:.1f}%</div></div>'
    )
    html.append(
        f'<div class="kpi-box"><div class="label">Total Income (period)</div><div class="value">{tot_inc:,.0f}</div><div class="sub">NOK</div></div>'
    )
    html.append(
        f'<div class="kpi-box"><div class="label">Total Real Spend (period)</div><div class="value">{tot_rs:,.0f}</div><div class="sub">NOK</div></div>'
    )
    html.append(
        f'<div class="kpi-box"><div class="label">Net Cash (period)</div><div class="value">{tot_inc-tot_rs:,.0f}</div><div class="sub">NOK · income − spend</div></div>'
    )
    html.append("</div>")

    # 2. Income + spend MoM line
    html.append("<h2>1. Income & Real Spend — Month on Month</h2>")
    html.append(
        _svg_line_chart(
            labels,
            [
                ("Real Spend", rs, "#d62728"),
                ("Income", inc, "#1f77b4"),
                ("Net Cash", net, "#2ca02c"),
            ],
            title=f"Income, Real Spend, Net Cash — {period}",
            y_label="NOK",
        )
    )

    # table under chart
    html.append(
        "<table><tr><th>Month</th>"
        + "".join(f'<th class="num">{lbl}</th>' for lbl in labels)
        + "</tr>"
    )
    html.append(
        "<tr><td>Income</td>"
        + "".join(f'<td class="num">{_fmt_nok(v)}</td>' for v in inc)
        + "</tr>"
    )
    html.append(
        "<tr><td>Real Spend</td>"
        + "".join(f'<td class="num">{_fmt_nok(v)}</td>' for v in rs)
        + "</tr>"
    )
    html.append(
        "<tr><td>Net Cash</td>"
        + "".join(f'<td class="num">{_fmt_nok(v)}</td>' for v in net)
        + "</tr>"
    )
    html.append(
        "<tr><td>Savings</td>"
        + "".join(f'<td class="num">{_fmt_nok(v)}</td>' for v in sv)
        + "</tr>"
    )
    html.append("</table>")

    # 3. Cumulative spend
    html.append("<h2>2. Cumulative Real Spend</h2>")
    html.append(
        _svg_line_chart(
            labels,
            [
                ("Cumulative Real Spend (NOK)", cum_rs, "#d62728"),
            ],
            title="Cumulative Real Spend over time",
            y_label="NOK",
        )
    )

    # 4. Partner A / Partner B
    html.append("<h2>3. Partner A / Partner B — Cash Share per Month</h2>")
    html.append(
        '<div class="method">Each partner\'s actual cash paid / total household cash paid (real spend). Excludes savings and mortgage. No assumed 50/50 split.</div>'
    )
    html.append(
        _svg_stacked_pct(labels, pc, pr, "Partner A / Partner B cash share per month")
    )
    # line version
    html.append(
        _svg_line_chart(
            labels,
            [
                ("% Partner A", pc, "#1f77b4"),
                ("% Partner B", pr, "#ff7f0e"),
            ],
            title="Partner A / Partner B — line view",
            y_label="% of household cash",
        )
    )

    # 5. Per-category MoM grid (top 15)
    html.append("<h2>4. Categories — Month on Month (top 15 by total spend)</h2>")
    html.append(
        '<div class="method">Mini-sparkline per category. End value = total in last loaded month. Categories ranked by 11-month total spend.</div>'
    )
    html.append('<div class="spark-grid">')
    for name, vals in pcats:
        last_v = next((v for v in reversed(vals) if v is not None), None)
        total_v = sum(v for v in vals if v is not None)
        html.append(f'<div class="merchant-row">')
        html.append(f'<div class="name">{_esc(name)}</div>')
        html.append(
            f'<div class="stats">total {total_v:,.0f} · last {_fmt_nok(last_v)}</div>'
        )
        html.append(
            f'<div class="spark">{_svg_sparkline(vals, width=280, height=36, color="#2b6cb0")}</div>'
        )
        html.append("</div>")
    html.append("</div>")

    # 5b. Per-category MoM table
    html.append("<h3>Per-category table (NOK, absolute spend)</h3>")
    html.append(
        "<table><tr><th>Category</th>"
        + "".join(f'<th class="num">{lbl}</th>' for lbl in labels)
        + '<th class="num">Total</th></tr>'
    )
    for name, vals in pcats:
        html.append(f"<tr><td>{_esc(name)}</td>")
        for v in vals:
            html.append(f'<td class="num">{_fmt_nok(v)}</td>')
        html.append(
            f'<td class="num"><b>{sum(v for v in vals if v is not None):,.0f}</b></td></tr>'
        )
    html.append("</table>")

    # 5c. Per-parent-category table (v8 fix 2026-07-22)
    # Renders parent cats ("Home", "Groceries", etc.) with the
    # paired-reimbursement legs visible. Each parent row shows:
    #   gross (real spend) + paired reimbursement
    # Sub-cat rows shown indented below if any sub-cats exist.
    html.append(
        "<h3>Per-parent-category table — gross spend + paired reimbursements</h3>"
    )
    html.append(
        '<div class="method">Parent cat = top-level grouping. Paired reimbursement rows are net 0 across paired legs, but visible here. Real spend = gross sub-category totals.</div>'
    )
    html.append(
        "<table><tr><th>Parent / Sub / Paired</th>"
        + "".join(f'<th class="num">{lbl}</th>' for lbl in labels)
        + '<th class="num">Total</th></tr>'
    )
    for p in ppcats:
        parent = p["parent"]
        gross = p["gross_per_month"]
        paired = p["paired_reimb_per_month"]
        paired_count = p["paired_reimb_count_per_month"]
        # Parent row
        parent_total = sum(v for v in gross if v is not None)
        html.append(
            f'<tr style="background:#edf2f7;font-weight:600"><td>{_esc(parent)} (parent)</td>'
        )
        for v in gross:
            html.append(f'<td class="num"><b>{_fmt_nok(v)}</b></td>')
        html.append(f'<td class="num"><b>{parent_total:,.0f}</b></td></tr>')
        # Paired reimbursement row (if any)
        if any(c > 0 for c in paired_count):
            paired_avg = [g / 2 if c > 0 else 0 for g, c in zip(paired, paired_count)]
            paired_total = sum(paired_avg)
            html.append(
                f'<tr style="background:#fef5e7"><td>↳ Paired reimbursement (net 0)</td>'
            )
            for v in paired_avg:
                # Show signed: +X (reimb in) and -X (paired out)
                if v > 0:
                    html.append(
                        f'<td class="num" style="color:#38a169">±{_fmt_nok(v)}</td>'
                    )
                else:
                    html.append(f'<td class="num">—</td>')
            html.append(
                f'<td class="num" style="color:#38a169"><b>±{paired_total:,.0f}</b></td></tr>'
            )
        # Sub-cat rows
        for sub_name, sub_vals in p["sub_cats"].items():
            sub_total = sum(v for v in sub_vals if v is not None)
            html.append(
                f'<tr><td style="padding-left:24px;color:#4a5568">↳ {_esc(sub_name)}</td>'
            )
            for v in sub_vals:
                html.append(f'<td class="num">{_fmt_nok(v)}</td>')
            html.append(f'<td class="num">{sub_total:,.0f}</td></tr>')
    html.append("</table>")

    # 6. Top repeating merchants
    html.append("<h2>5. Top Repeating Merchants — Cumulative Spend</h2>")
    html.append(
        '<div class="method">Merchants appearing in ≥3 months, ranked by cumulative absolute spend across 11 months. End dot = spend in last loaded month.</div>'
    )
    if not pmrcs:
        html.append('<div class="empty">No repeating merchants found.</div>')
    else:
        for name, vals in pmrcs:
            cum = sum(v for v in vals if v is not None)
            n_months = sum(1 for v in vals if v is not None and v > 0)
            last = next((v for v in reversed(vals) if v is not None), 0)
            html.append(f'<div class="merchant-row">')
            html.append(f'<div class="name">{_esc(name[:48])}</div>')
            html.append(
                f'<div class="stats">{n_months} mo · cum {cum:,.0f} · last {_fmt_nok(last)}</div>'
            )
            html.append(
                f'<div class="spark">{_svg_sparkline(vals, width=400, height=36, color="#c53030")}</div>'
            )
            html.append("</div>")
        # table
        html.append("<h3>Per-merchant table (NOK, absolute spend)</h3>")
        html.append(
            "<table><tr><th>Merchant</th>"
            + "".join(f'<th class="num">{lbl}</th>' for lbl in labels)
            + '<th class="num">Total</th></tr>'
        )
        for name, vals in pmrcs:
            html.append(f"<tr><td>{_esc(name[:48])}</td>")
            for v in vals:
                html.append(f'<td class="num">{_fmt_nok(v)}</td>')
            html.append(
                f'<td class="num"><b>{sum(v for v in vals if v is not None):,.0f}</b></td></tr>'
            )
        html.append("</table>")

    # 7. Trips
    html.append("<h2>6. Trips — configured period</h2>")
    html.append(
        '<div class="method">Trips use configured trip categories. Detection: transport-keyword anchor OR large transaction → date cluster → orphan merge → same-country merge. Multi-month trips are preserved.</div>'
    )
    html.append('<div class="kpi-row">')
    html.append(
        f'<div class="kpi-box"><div class="label">Trips</div><div class="value">{len(trips)}</div><div class="sub">total across {months_loaded} mo</div></div>'
    )
    html.append(
        f'<div class="kpi-box"><div class="label">Total Trip Spend</div><div class="value">{trips_sum["total"]:,.0f}</div><div class="sub">NOK</div></div>'
    )
    if trips_sum.get("longest"):
        lt = trips_sum["longest"]
        html.append(
            f'<div class="kpi-box"><div class="label">Longest Trip</div><div class="value">{lt["days"]}d</div><div class="sub">{_esc(lt["location"])} · {lt["start"]} → {lt["end"]}</div></div>'
        )
    if trips_sum.get("costliest_per_day"):
        ct = trips_sum["costliest_per_day"]
        html.append(
            f'<div class="kpi-box"><div class="label">Costliest / day</div><div class="value">{abs(ct["per_day"]):,.0f}</div><div class="sub">{_esc(ct["location"])} · {abs(ct["total"]):,.0f} over {ct["days"]}d</div></div>'
        )
    html.append("</div>")

    # trip summary table
    html.append(
        '<table><tr><th>#</th><th>Location</th><th>Start</th><th>End</th><th class="num">Days</th><th class="num">Months</th><th class="num">Txns</th><th class="num">Total NOK</th><th class="num">/day</th></tr>'
    )
    for t in trips:
        html.append(
            f'<tr><td>T{t["idx"]}</td><td>{_esc(t["location"])}</td><td>{t["start"]}</td><td>{t["end"]}</td><td class="num">{t["days"]}</td><td class="num">{t["txn_count"]}</td><td class="num">{t["txn_count"]}</td><td class="num">{t["total"]:,.0f}</td><td class="num">{t["per_day"]:,.0f}</td></tr>'
        )
    html.append(
        f'<tr><td colspan="7"><b>GRAND TOTAL</b></td><td class="num"><b>{trips_sum["total"]:,.0f}</b></td><td class="num"><b>{trips_sum["avg_per_day"]:,.0f}</b></td></tr>'
    )
    html.append("</table>")

    # trip drilldowns
    html.append("<h3>Per-trip drilldown</h3>")
    for t in trips:
        html.append(
            f'<details><summary><b>T{t["idx"]} {_esc(t["location"])}</b> · {t["start"]} → {t["end"]} · {t["days"]}d · {t["total"]:,.0f} NOK ({t["per_day"]:,.0f}/d)</summary>'
        )
        html.append(
            '<table><tr><th>Date</th><th>Payee</th><th>Category</th><th>Account</th><th class="num">Amount</th></tr>'
        )
        for x in t["txns"]:
            html.append(
                f'<tr><td>{x["date"]}</td><td>{_esc(x["payee"][:50])}</td><td>{_esc(x["cat"])}</td><td>{_esc(x["account"])}</td><td class="num">{x["amount"]:,.0f}</td></tr>'
            )
        html.append("</table>")
        # by account
        if t.get("by_account"):
            html.append('<table><tr><th>By Account</th><th class="num">Total</th></tr>')
            for a, v in sorted(t["by_account"].items(), key=lambda kv: -abs(kv[1])):
                html.append(f'<tr><td>{_esc(a)}</td><td class="num">{v:,.0f}</td></tr>')
            html.append("</table>")
        html.append("</details>")

    # 8. Methodology + caveats
    html.append("<h2>7. Methodology & Caveats</h2>")
    html.append('<div class="method">')
    html.append(
        "<b>Data source</b>: local PocketSmith-compatible exports from the configured data directory."
    )
    html.append(
        "<br><b>Pipeline</b>: v5-month-pdf <code>data_loader → tally → wallet</code>, then trend11 aggregation."
    )
    html.append(
        "<br><b>Real Spend</b> = Common + personal categories (absolute). Excludes savings transfers and mortgage."
    )
    html.append("<br><b>Net Cash</b> = Income − Real Spend (per month).")
    html.append(
        "<br><b>Cumulative</b> = running sum of Real Spend across loaded months."
    )
    html.append(
        "<br><b>Partner share</b> = each partner's actual cash paid / total household cash. <b>No assumed 50/50 split.</b>"
    )
    html.append(
        "<br><b>Per-category ranking</b>: top 15 by 11-month total absolute spend."
    )
    html.append(
        '<br><b>Per-merchant ranking</b>: payee appears in ≥3 months, top 10 by cumulative. Payees normalized (stripped "Fra:", "Betalt:" prefixes, uppercased).'
    )
    html.append(
        "<br><b>Trips</b>: tag-based via 3 PS categories; anchor detection (transport keyword OR |amount|≥2k); ±10 day cluster; orphan merge 6-day gap; 8-day pre-split for sub-stays; same-country merge."
    )
    html.append(
        f"<br><b>Coverage</b>: {months_loaded}/{len(labels)} configured months loaded."
    )
    html.append("</div>")

    # section 8: TODO
    html.append("<h2>8. Known Gaps & Next Iter</h2>")
    html.append("<ul>")
    html.append(
        "<li>Configure report months and provide matching local exports before rendering</li>"
    )
    html.append(
        "<li>PS exports have no <code>tags</code> field — using category as proxy. If PS API returns labels, switch</li>"
    )
    html.append(
        "<li>Per-merchant top 10 may be noisy; tighten normalization regex</li>"
    )
    html.append("<li>Add trip vs non-trip spend split per month</li>")
    html.append("<li>Add MoM per-category Δ% heatmap</li>")
    html.append("</ul>")

    html.append("</body></html>")

    out_html = "\n".join(html)
    output_dir = os.environ.get(
        "POCKETSMITH_REPORT_OUTPUT_DIR", os.path.join(SCRIPT_DIR, "out")
    )
    os.makedirs(output_dir, exist_ok=True)
    out_html_path = os.path.join(output_dir, "mega_v7.html")
    with open(out_html_path, "w") as f:
        f.write(out_html)
    print(f"[v7] HTML written: {out_html_path} ({len(out_html):,} chars)")

    # render PDF
    print("[v7] rendering PDF via WeasyPrint...")
    from weasyprint import HTML

    out_pdf = os.path.join(output_dir, "mega_v7.pdf")
    HTML(string=out_html).write_pdf(out_pdf)
    size = os.path.getsize(out_pdf)
    print(f"[v7] PDF written: {out_pdf} ({size:,} bytes)")

    # page count
    import subprocess

    info = subprocess.run(["pdfinfo", out_pdf], capture_output=True, text=True).stdout
    pages = [l for l in info.split("\n") if "Pages" in l]
    print(f'[v7] {pages[0] if pages else "?"}')

    return out_pdf


if __name__ == "__main__":
    render_mega_v7()
