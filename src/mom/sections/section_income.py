"""Section 1: Income."""

from typing import Dict, List, Any
from html import escape
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from line_chart import render_line_chart
from sections.common_render import (
    _n,
    _pct,
    render_person_share_chart,
    render_income_table,
)
from sections.context import heading, labels


def render(
    agg: Dict[str, Any],
    partner_labels: dict[str, str] | None = None,
    section_number: int | None = 1,
    section_title: str = "Income",
) -> str:
    partner_labels = labels(partner_labels)
    months = agg["months"]
    series = agg["series"]
    cum = agg["cumulative"]
    income_total = cum["income"]["total"]
    partner_a_pct = (
        cum["income"]["partner_a"] / income_total * 100 if income_total else 0.0
    )
    partner_b_pct = (
        cum["income"]["partner_b"] / income_total * 100 if income_total else 0.0
    )
    parts = []

    # Wrap h2 + summary + table + chart in a single landscape page so the
    # heading, KPI summary, table, and chart all render on the same page.
    # Per THEK 2026-07-23: h2 must be on the same page as table+chart.
    parts.append('<div class="landscape-page income-print-safe">')
    parts.append(
        f'<h2 class="section-income">{heading(section_number, section_title)}</h2>'
    )

    # KPI summary (stays with heading)
    parts.append('<div class="kpi-section-summary">')
    parts.append(
        f'<p class="note">Period total: <b>{_n(income_total)} NOK</b> '
        f'({escape(partner_labels["partner_a"])} {_n(cum["income"]["partner_a"])} = '
        f"{partner_a_pct:.1f}% | "
        f'{escape(partner_labels["partner_b"])} {_n(cum["income"]["partner_b"])} = '
        f"{partner_b_pct:.1f}%)</p>"
    )
    parts.append("</div>")

    # Per-month table — TRANSPOSED (months as rows, metrics as columns)
    # Total column = running cumulative
    # Wrap table + stacked bar chart in a single landscape page so they render together
    parts.append("<h3>Income per month (with per-person %)</h3>")
    parts.append(
        render_income_table(
            months,
            series["income"]["partner_a"],
            series["income"]["partner_b"],
            series["income"]["total"],
            cumulative_total=True,
            partner_labels=partner_labels,
        )
    )

    # Build running cumulative for the chart's Total series
    running_total = []
    rt = 0
    for v in series["income"]["total"]:
        rt += v or 0
        running_total.append(rt)

    # Stacked partner bars with a cumulative line.
    # Dual y-axis: left = monthly NOK, right = cumulative NOK (independent scales).
    from stacked_bar_line import render_stacked_bar_with_line

    parts.append("<h3>Monthly income (stacked by partner) with cumulative line</h3>")
    parts.append(
        render_stacked_bar_with_line(
            months,
            series["income"]["partner_a"],
            series["income"]["partner_b"],
            running_total,
            title="",
            y_label="NOK",
            width=1000,
            height=220,
            show_pct=True,
            partner_a_label=partner_labels["partner_a"],
            partner_b_label=partner_labels["partner_b"],
            accessibility_id="income",
        )
    )
    parts.append("</div>")

    # Per-person share chart removed (THEK 2026-07-23) — % is now shown
    # directly on the bar segments in the stacked chart above.

    return "\n".join(parts)
