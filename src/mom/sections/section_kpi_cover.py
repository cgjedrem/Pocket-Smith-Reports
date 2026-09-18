"""Section 0: KPI Cover (page 1)."""

from typing import Dict, List, Any
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sections.common_render import _n
from sections.context import heading, labels


def _pct(num, den) -> str:
    if not den:
        return "0.0%"
    return f"{num / den * 100:.1f}%"


def render(
    agg: Dict[str, Any],
    partner_labels: dict[str, str] | None = None,
    section_heading: str | None = None,
) -> str:
    partner_labels = labels(partner_labels)
    partner_a_label = partner_labels["partner_a"]
    partner_b_label = partner_labels["partner_b"]
    cum = agg["cumulative"]
    inc = cum["income"]["total"]
    spend = cum["real_spend"]["total"]
    nc = cum["net_cash"]["total"]
    sav = cum["savings"]["total"]
    inc_partner_a = cum["income"]["partner_a"]
    inc_partner_b = cum["income"]["partner_b"]
    spend_partner_a = cum["real_spend"]["partner_a"]
    spend_partner_b = cum["real_spend"]["partner_b"]
    nc_partner_a = cum["net_cash"]["partner_a"]
    nc_partner_b = cum["net_cash"]["partner_b"]
    sav_partner_a = cum["savings"]["net_partner_a"]
    sav_partner_b = cum["savings"]["net_partner_b"]

    by_sec = agg.get("cumulative_by_section", {})
    home = by_sec.get("home", {"partner_a": 0, "partner_b": 0, "total": 0})
    common = by_sec.get("common", {"partner_a": 0, "partner_b": 0, "total": 0})
    p_partner_a = by_sec.get(
        "personal_partner_a", {"partner_a": 0, "partner_b": 0, "total": 0}
    )
    p_partner_b = by_sec.get(
        "personal_partner_b", {"partner_a": 0, "partner_b": 0, "total": 0}
    )

    parts = ['<div class="kpi-cover">']
    parts.append(
        f"<h1>{section_heading or heading(None, 'Household Financial Report — Month-on-Month')}</h1>"
    )
    parts.append(
        f'<p class="subtitle">Period: <b>{agg["months"][0]}</b> → <b>{agg["months"][-1]}</b> ({len(agg["months"])} months)</p>'
    )

    # 6 top-level KPI cards (4 household + 2 section totals)
    parts.append('<div class="kpi-grid">')
    parts.append(
        _kpi_card("kpi-income", "Total Income", _n(inc), inc_partner_a, inc_partner_b)
    )
    parts.append(
        _kpi_card(
            "kpi-spend", "Real Spend", _n(spend), spend_partner_a, spend_partner_b
        )
    )
    parts.append(_kpi_card("kpi-cash", "Net Cash", _n(nc), nc_partner_a, nc_partner_b))
    parts.append(
        _kpi_card(
            "kpi-saved",
            "Net Savings",
            _n(sav),
            sav_partner_a,
            sav_partner_b,
            show_pct=False,
        )
    )
    parts.append(
        _kpi_card(
            "kpi-home",
            "Home Total",
            _n(home["total"]),
            home["partner_a"],
            home["partner_b"],
        )
    )
    parts.append(
        _kpi_card(
            "kpi-common",
            "Common Total",
            _n(common["total"]),
            common["partner_a"],
            common["partner_b"],
        )
    )
    parts.append("</div>")

    # Per-partner boxes — each box has the personal card nested under it
    # Personal total = owner's outflow into personal categories.
    # Owner paid = same number (% of total household real spend)
    # Partner paid = what the other partner covered.
    parts.append('<div class="partner-grid">')
    parts.append(
        _partner_box(
            "partner-a",
            partner_a_label,
            {
                "Income": inc_partner_a,
                "Real spend": spend_partner_a,
                "Net cash": nc_partner_a,
                "Net saved": sav_partner_a,
            },
            personal_card=_personal_card(
                "kpi-partner-a",
                f"{partner_a_label} personal spend",
                p_partner_a["partner_a"],
                pct_of_real_spend=(
                    p_partner_a["partner_a"] / spend * 100 if spend else 0
                ),
                partner_name=partner_b_label,
                partner_paid=p_partner_a["partner_b"],
            ),
        )
    )
    parts.append(
        _partner_box(
            "partner-b",
            partner_b_label,
            {
                "Income": inc_partner_b,
                "Real spend": spend_partner_b,
                "Net cash": nc_partner_b,
                "Net saved": sav_partner_b,
            },
            personal_card=_personal_card(
                "kpi-partner-b",
                f"{partner_b_label} personal spend",
                p_partner_b["partner_b"],
                pct_of_real_spend=(
                    p_partner_b["partner_b"] / spend * 100 if spend else 0
                ),
                partner_name=partner_a_label,
                partner_paid=p_partner_b["partner_a"],
            ),
        )
    )
    parts.append("</div>")
    parts.append("</div>")
    return "\n".join(parts)


def _kpi_card(
    cls: str,
    label: str,
    value: str,
    partner_a_value: float,
    partner_b_value: float,
    show_pct: bool = True,
) -> str:
    parts = [
        f'<div class="kpi-card {cls}">',
        f'<div class="kpi-label">{label}</div>',
        f'<div class="kpi-value">{value}</div>',
    ]
    if show_pct:
        total = partner_a_value + partner_b_value
        partner_a_pct = _pct(partner_a_value, total)
        partner_b_pct = _pct(partner_b_value, total)
        parts.append(
            f'<div class="kpi-pct">'
            f'<span class="partner-a">Partner A {partner_a_pct}</span> &nbsp;|&nbsp; '
            f'<span class="partner-b">Partner B {partner_b_pct}</span>'
            f"</div>"
        )
    parts.append("</div>")
    return "".join(parts)


def _personal_card(
    cls: str,
    label: str,
    owner_paid: float,
    pct_of_real_spend: float,
    partner_name: str,
    partner_paid: float,
) -> str:
    """Personal-spend mini-card shown inside a partner box.

    Shows the owner's outflow into their personal categories. This is the real number the owner
    spent from their own accounts on their own stuff.

    Args:
        owner_paid: how much the owner actually paid from their own accounts
        pct_of_real_spend: owner_paid as a % of total household real spend
        partner_name: the other partner
        partner_paid: how much the other partner paid toward this owner's cats
    """
    return (
        f'<div class="personal-card {cls}">'
        f'<div class="personal-card-label">{label}</div>'
        f'<div class="personal-card-total">{_n(owner_paid)} NOK</div>'
        f'<div class="personal-card-rows">'
        f'<div class="personal-row"><span>Owner paid (out of pocket)</span>'
        f"<span><b>{pct_of_real_spend:.1f}%</b> of household real spend</span></div>"
        f"</div>"
        f"</div>"
    )


def _partner_box(
    who: str, name: str, rows: Dict[str, float], personal_card: str = ""
) -> str:
    parts = [
        f'<div class="partner-box {who}">',
        f'<div class="partner-title">{name}</div>',
    ]
    for label, val in rows.items():
        v = _n(val)
        cls = "negative" if val < 0 else ""
        parts.append(
            f'<div class="partner-row"><span class="label">{label}</span>'
            f'<span class="value {cls}">{v}</span></div>'
        )
    if personal_card:
        parts.append(personal_card)
    parts.append("</div>")
    return "\n".join(parts)
