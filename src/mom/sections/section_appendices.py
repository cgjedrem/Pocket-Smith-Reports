"""Appendices: full per-section category transaction tables.

Structure: Section → Main category → Subcategory → Table

Each subcategory in the reporting period gets its own table with:
  Date | Payee | Account | Amount
  + Subtotal row at the bottom
"""

from typing import Dict, List, Any
from collections import defaultdict
from html import escape
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sections.common_render import _n


def render(
    agg: Dict[str, Any],
    all_txns_by_month: Dict[str, List[Dict]],
    partner_labels: Dict[str, str] | None = None,
    section_number: int | None = None,
    section_title: str = "Appendices",
) -> str:
    partner_labels = partner_labels or {}
    heading = (
        f"{section_number}. {section_title}"
        if section_number is not None
        else section_title
    )
    partner_a = partner_labels.get("partner_a", "Partner A")
    partner_b = partner_labels.get("partner_b", "Partner B")
    parts = [f"<h2>{escape(heading)} — full transaction detail</h2>"]

    sections = [
        ("income", "Income"),
        ("savings", "Savings"),
        ("home", "Home"),
        ("common", "Common"),
        (
            "personal_partner_a",
            f"Personal — {partner_a}",
        ),
        (
            "personal_partner_b",
            f"Personal — {partner_b}",
        ),
        ("trips", "Trips"),
    ]

    for sec_id, sec_label in sections:
        parts.append(f'<h3 class="appendix-section">{escape(sec_label)}</h3>')
        txns = [
            transaction
            for month_transactions in all_txns_by_month.values()
            for transaction in month_transactions
            if transaction.get("_detailed_section") == sec_id
        ]
        by_main_category: Dict[tuple[str, str], List[Dict]] = defaultdict(list)
        for transaction in txns:
            main_category = transaction.get("_main_category") or {}
            main_id = str(main_category.get("id", ""))
            main_title = str(main_category.get("title") or "Uncategorized")
            by_main_category[(main_id, main_title)].append(transaction)

        for (_main_id, main_title), main_txns in sorted(
            by_main_category.items(), key=lambda item: (item[0][1], item[0][0])
        ):
            parts.append(
                f'<h4 class="appendix-main-category">{escape(main_title)}</h4>'
            )
            by_subcategory: Dict[tuple[str, str] | None, List[Dict]] = defaultdict(list)
            for transaction in main_txns:
                subcategory = transaction.get("_subcategory")
                subcategory_key = (
                    (
                        str(subcategory.get("id", "")),
                        str(subcategory.get("title") or "Uncategorized"),
                    )
                    if isinstance(subcategory, dict)
                    else None
                )
                by_subcategory[subcategory_key].append(transaction)
            for subcategory, sub_txns in sorted(
                by_subcategory.items(),
                key=lambda item: (item[0] is not None, item[0] or ("", "")),
            ):
                if subcategory is not None:
                    parts.append(
                        f'<h5 class="appendix-subcat">{escape(subcategory[1])}</h5>'
                    )
                parts.extend(
                    _render_table(
                        sub_txns, subcategory[1] if subcategory else main_title
                    )
                )

    return "\n".join(parts)


def _render_table(transactions: List[Dict], category_title: str) -> List[str]:
    transactions.sort(
        key=lambda transaction: (
            str(transaction.get("date", "")),
            str(transaction.get("id", "")),
        )
    )
    total = sum(transaction.get("amount", 0) or 0 for transaction in transactions)
    parts = ['<table class="appendix-table">']
    parts.append(
        "<thead><tr><th>Date</th><th>Payee</th><th>Account</th>"
        '<th class="num">Amount</th></tr></thead><tbody>'
    )
    for transaction in transactions:
        parts.append("<tr>")
        parts.append(f'<td>{escape(str(transaction.get("date", "")))}</td>')
        parts.append(f'<td>{escape(str((transaction.get("payee") or "")[:45]))}</td>')
        parts.append(
            f'<td>{escape(str(((transaction.get("account") or {}).get("name") or "")[:25]))}</td>'
        )
        parts.append(f'<td class="num">{_n(transaction.get("amount", 0))}</td>')
        parts.append("</tr>")
    parts.append(
        f'<tr class="subtotal-row"><td colspan="3"><i>Subtotal: {escape(category_title)}</i></td>'
        f'<td class="num"><i>{_n(total)}</i></td></tr>'
    )
    parts.append("</tbody></table>")
    return parts
