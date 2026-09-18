"""T050: partner labels containing HTML/JS must be escaped in rendered output.

The same `render()` output feeds both the v4 CLI HTML report and the
budget_api PDF source (report_pdf calls render with theme "minimal"), so one
render assertion covers the PDF-source surface; the second call pins it.
"""

from accounting import build_month_contract
from accounting_html import render

XSS_LABEL = "<img src=x onerror=alert(1)>"
XSS_ESCAPED = "&lt;img src=x onerror=alert(1)&gt;"

_OWNERS = {"account-a": "partner_a", "account-b": "partner_b"}


def _txn(tid, amount, category, account_id="account-a"):
    return {
        "id": tid,
        "date": "2030-04-01",
        "amount": amount,
        "account": {"id": account_id},
        "category": category,
    }


def _contract():
    return build_month_contract(
        [
            _txn(1, 100, {"id": "income", "title": "Income"}),
            _txn(2, -25, {"id": "personal_a", "title": "Personal A"}),
            _txn(3, -25, {"id": "personal_b", "title": "Personal B"}, "account-b"),
        ],
        _OWNERS,
        detailed_section_mapping={
            "category_sections": {
                "income": "income_salary",
                "personal_a": "personal_partner_a",
                "personal_b": "personal_partner_b",
            },
            "account_roles": {},
        },
    )


def test_xss_label_escaped_in_rendered_html():
    html = render(
        _contract(),
        "2030-04",
        {"partner_a": XSS_LABEL, "partner_b": "Fixture B"},
    )
    assert XSS_ESCAPED in html
    assert XSS_LABEL not in html


def test_xss_label_escaped_in_pdf_source_html():
    """report_pdf renders with theme 'minimal' — this IS the PDF source."""
    html = render(
        _contract(),
        "2030-04",
        {"partner_a": XSS_LABEL, "partner_b": "Fixture B"},
        "minimal",
    )
    assert XSS_ESCAPED in html
    assert XSS_LABEL not in html
