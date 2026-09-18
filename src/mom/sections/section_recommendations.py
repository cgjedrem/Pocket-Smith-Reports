"""Sections 8 + 9: Observations + Actionable saving tips."""

from typing import Dict, List, Any
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recommendations import generate_observations, generate_actions


def _render_list(items: List[str], css_class: str) -> str:
    if not items:
        return '<p class="empty">No items.</p>'
    parts = []
    for item in items:
        if item and item[0].isdigit():
            num, _, rest = item.partition(". ")
            parts.append(
                f'<div class="{css_class}"><span class="num">{num}.</span> {rest}</div>'
            )
        else:
            parts.append(f'<div class="{css_class}">{item}</div>')
    return "\n".join(parts)


def render_observations(agg: Dict[str, Any]) -> str:
    obs = generate_observations(agg)
    parts = [
        '<h2 class="section-observations">8. Observations (data-driven findings)</h2>'
    ]
    parts.append(
        '<p class="note">Facts extracted directly from the data — observed patterns '
        "and outlier detection. No narrative, no recommendations.</p>"
    )
    parts.append(_render_list(obs, "recommendation"))
    return "\n".join(parts)


def render_actions(agg: Dict[str, Any]) -> str:
    actions = generate_actions(agg)
    parts = ['<h2 class="section-actions">9. Actionable saving tips</h2>']
    parts.append(
        '<p class="note">Concrete actions to reduce expenses, derived from the data above. '
        "Each shows the estimated annual savings in NOK.</p>"
    )
    parts.append(_render_list(actions, "action"))
    return "\n".join(parts)
