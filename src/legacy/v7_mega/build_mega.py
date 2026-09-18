#!/usr/bin/env python3
"""build_mega.py — build a single PDF with 8 MoM comparisons + 2 QoQ + 9-month trend."""

import os, sys, time
from datetime import date as D

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from build_compare import qoq_compare
from build_trend import main as run_trend
from compare import _resolve_month_path, compare_periods, trend
from recommendations import generate as gen_recs
from compare_template import (
    render_layout_a,
    render_layout_b,
    render_layout_c,
    render_layout_d,
    _month_name,
)
from trips import detect_trips

OUT = os.environ.get("POCKETSMITH_REPORT_OUTPUT_DIR", os.path.join(SCRIPT_DIR, "out"))
os.makedirs(OUT, exist_ok=True)

# Report periods come from configuration; no household period is tracked here.
months = [
    value.strip()
    for value in os.environ.get("POCKETSMITH_REPORT_MONTHS", "").split(",")
    if value.strip()
]
if len(months) < 2:
    raise ValueError(
        "POCKETSMITH_REPORT_MONTHS must contain at least two YYYY-MM values"
    )
mompairs = []
for i in range(1, len(months)):
    mompairs.append((months[i], months[i - 1]))

# Optional quarter comparisons use semicolon-separated CURRENT:PRIOR pairs.
qoq_pairs = [
    tuple(value.split(":", 1))
    for value in os.environ.get("POCKETSMITH_QOQ_PAIRS", "").split(";")
    if ":" in value
]

trend_rows = trend(None)

all_html = []
all_html.append(
    f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>MEGA: 9-Month Household Report</title>
<style>
@page {{ size: A4; margin: 1.6cm; @bottom-right {{ content: counter(page) " / " counter(pages); font-size: 9pt; color: #888; }} }}
body {{ font-family: 'Helvetica','Arial',sans-serif; color: #222; line-height: 1.35; font-size: 9.5pt; }}
h1 {{ color: #1a365d; font-size: 24pt; border-bottom: 3px solid #1a365d; padding-bottom: 6pt; }}
h2 {{ color: #1a365d; font-size: 16pt; margin-top: 18pt; border-bottom: 1px solid #cbd5e0; padding-bottom: 3pt; page-break-before: always; }}
</style></head><body>
<h1>MEGA Report — configured period</h1>
<p>Household report. NOK. Generated {D.today().isoformat()}.</p>
<p>This PDF contains 8 month-on-month comparisons (Layout A), 1 quarter-on-quarter, and 1 9-month trend summary. Each section starts on a new page.</p>
<p>Each MoM is rendered as Layout A (KPI Delta Strip) — the most scannable single-page format. Pick the layout that suits you best and we will use it for the regular monthly brief.</p>
"""
)

# Build a 9-month summary table first
summary = ""
for r in trend_rows:
    summary += f'<tr><td>{r["month"]}</td><td class="num">{r["txn_count"]}</td><td class="num">{r["income"]:,.0f}</td><td class="num">{r["real_spend"]:,.0f}</td><td class="num">{r["net_cash"]:+,.0f}</td><td class="num">{r["savings"]:,.0f}</td></tr>'
tot_inc = sum(r["income"] for r in trend_rows)
tot_spd = sum(r["real_spend"] for r in trend_rows)
tot_net = sum(r["net_cash"] for r in trend_rows)
tot_sav = sum(r["savings"] for r in trend_rows)
summary += f'<tr class="total"><td>TOTAL</td><td class="num">{sum(r["txn_count"] for r in trend_rows)}</td><td class="num">{tot_inc:,.0f}</td><td class="num">{tot_spd:,.0f}</td><td class="num">{tot_net:+,.0f}</td><td class="num">{tot_sav:,.0f}</td></tr>'

all_html.append(f"""
<style>table{{width:100%;border-collapse:collapse;font-size:9pt;margin:6pt 0}}th{{background:#1a365d;color:white;padding:5pt 8pt;text-align:left}}td{{padding:4pt 8pt;border-bottom:0.5pt solid #e2e8f0}}.num{{text-align:right;font-variant-numeric:tabular-nums}}tr.total td{{background:#1a365d;color:white;font-weight:bold;border:none}}</style>
<h2>Configured-period summary</h2>
<table>
<thead><tr><th>Month</th><th class="num">Txns</th><th class="num">Income</th><th class="num">Real spend</th><th class="num">Net cash</th><th class="num">Savings</th></tr></thead>
<tbody>{summary}</tbody>
</table>
<p><strong>Trips total:</strong> derived from the configured data source.</p>
""")

# Now build each MoM
for cur, pri in mompairs:
    cmp = compare_periods(cur, pri)
    recs = gen_recs(cmp)
    meta = {
        "title": f"MoM · {_month_name(cur)} vs {_month_name(pri)}",
        "household": "Household",
        "period": f"{cur} vs {pri}",
        "currency": "NOK",
        "generated_at": D.today().isoformat(),
    }
    # extract just the body of Layout A (skip <html> wrapper)
    full = render_layout_a(cmp, recs, meta)
    # Find <body>...</body>
    body_start = full.find("<body>") + len("<body>")
    body_end = full.rfind("</body>")
    body = full[body_start:body_end]
    all_html.append(f'<div style="page-break-after:always">{body}</div>')

# QoQ
for cur, pri in qoq_pairs:
    cmp = qoq_compare(cur, pri)
    recs = gen_recs(cmp)
    meta = {
        "title": f"QoQ · {cur} vs {pri}",
        "household": "Household",
        "period": f"{cur} vs {pri}",
        "currency": "NOK",
        "generated_at": D.today().isoformat(),
    }
    full = render_layout_a(cmp, recs, meta)
    body_start = full.find("<body>") + len("<body>")
    body_end = full.rfind("</body>")
    body = full[body_start:body_end]
    all_html.append(f'<div style="page-break-after:always">{body}</div>')

# 9-month trend with all 4 layouts
all_html.append(
    '<div style="page-break-before:always"><h2>Trend — All 4 Layouts</h2></div>'
)
paths = [_resolve_month_path(month) for month in months]
all_trips = detect_trips(paths)
last = trend_rows[-1]
first = trend_rows[0]


def delta(k):
    c = last[k]
    p = first[k]
    d = c - p
    pct = (d / abs(p) * 100) if p else None
    return {
        "abs": round(d, 2),
        "pct": round(pct, 1) if pct is not None else None,
        "direction": "up" if d > 0 else ("down" if d < 0 else "flat"),
        "current": c,
        "prior": p,
    }


deltas = {k: delta(k) for k in ["income", "real_spend", "net_cash", "savings"]}
for k in [
    "partner_a_income",
    "partner_a_wallet",
    "partner_a_net",
    "partner_a_savings",
    "partner_b_income",
    "partner_b_wallet",
    "partner_b_net",
    "partner_b_savings",
]:
    deltas[k] = {"abs": 0, "pct": None, "direction": "flat", "current": 0, "prior": 0}
cmp = {
    "current": {
        "month": last["month"],
        "txn_count": last["txn_count"],
        "key_metrics": last,
        "totals": {},
        "wallet": {},
    },
    "prior": {
        "month": first["month"],
        "txn_count": first["txn_count"],
        "key_metrics": first,
        "totals": {},
        "wallet": {},
    },
    "deltas": deltas,
    "category_deltas": [],
    "trips": all_trips,
    "trips_summary": {
        "n": len(all_trips),
        "total": sum(-t["total"] for t in all_trips),
    },
}
recs = gen_recs(cmp, trend_rows)
meta = {
    "title": "Configured-period trend",
    "household": "Household",
    "period": f'{first["month"]} → {last["month"]}',
    "currency": "NOK",
    "generated_at": D.today().isoformat(),
}

for fn_name, fn in [
    ("A", render_layout_a),
    ("B", render_layout_b),
    ("C", lambda c, r, m, t: render_layout_c(c, r, m, trend_rows)),
    ("D", lambda c, r, m, t: render_layout_d(c, r, m, trend_rows)),
]:
    full = (
        fn(cmp, recs, {**meta, "title": meta["title"] + f" · {fn_name}"}, trend_rows)
        if fn_name in ("C", "D")
        else fn(cmp, recs, {**meta, "title": meta["title"] + f" · {fn_name}"})
    )
    body_start = full.find("<body>") + len("<body>")
    body_end = full.rfind("</body>")
    body = full[body_start:body_end]
    all_html.append(f'<div style="page-break-after:always">{body}</div>')

all_html.append("</body></html>")
full_html = "".join(all_html)

html_path = os.path.join(OUT, "MEGA_9month.html")
pdf_path = os.path.join(OUT, "MEGA_9month.pdf")
with open(html_path, "w") as f:
    f.write(full_html)

from weasyprint import HTML

t0 = time.time()
HTML(string=full_html, base_url=OUT).write_pdf(pdf_path)
print(f"OK: {pdf_path} ({time.time()-t0:.1f}s)")
