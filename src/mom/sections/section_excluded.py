"""Section 6: raw monthly excluded transaction listing."""

from html import escape
from typing import Any, Dict

from sections.common_render import _n
from sections.context import heading, labels


def render(
    agg: Dict[str, Any],
    partner_labels: dict[str, str] | None = None,
    section_number: int | None = 12,
    section_title: str = "Excluded categories",
) -> str:
    partner_labels = labels(partner_labels)
    parts = [
        f'<h2 class="section-excluded">{heading(section_number, section_title)}</h2>'
    ]
    by_month = agg.get("excluded_transactions", {})
    if not any(by_month.values()):
        return "\n".join(
            parts + ['<p class="empty">No excluded transactions found.</p>']
        )
    for month in agg["months"]:
        transactions = by_month.get(month, [])
        if not transactions:
            continue
        parts.append(f"<h3>{escape(month)}</h3>")
        parts.append(
            '<table class="overview-table transposed"><thead><tr><th>Date</th><th>Description</th><th>Category</th><th>Who</th><th class="num">Amount</th></tr></thead><tbody>'
        )
        subtotal = 0.0
        for transaction in transactions:
            amount = transaction.get("amount", 0) or 0
            subtotal += amount
            who = partner_labels.get(transaction.get("owner"), "Joint")
            parts.append(
                "<tr>"
                + "".join(
                    (
                        f"<td>{escape(str(transaction.get('date', '')))}</td>",
                        f"<td>{escape(str(transaction.get('description', '')))}</td>",
                        f"<td>{escape(str(transaction.get('category', '')))}</td>",
                        f"<td>{escape(who)}</td>",
                        f'<td class="num">{_n(amount)}</td>',
                    )
                )
                + "</tr>"
            )
        parts.append(
            f'<tr class="subtotal-row"><td colspan="4"><b>Month subtotal</b></td><td class="num"><b>{_n(subtotal)}</b></td></tr></tbody></table>'
        )
    return "\n".join(parts)
