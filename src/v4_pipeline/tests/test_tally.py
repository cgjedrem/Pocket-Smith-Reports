"""Neutral tally contract tests."""

from tally import _section, compute


def test_sections_use_neutral_partner_labels():
    assert _section("Income (Partner A)") == "income"
    assert _section("Income (Partner B)") == "income"
    assert _section("Personal-Partner A") == "personal_partner_a"
    assert _section("Personal-Partner B") == "personal_partner_b"


def test_excluded_amounts_are_attributed_to_neutral_partner_keys():
    totals = compute(
        [
            {
                "amount": -3,
                "__partner": "partner_a",
                "category": {"title": "Internal Card Transfer"},
            },
            {
                "amount": -4,
                "__partner": "partner_b",
                "category": {"title": "Internal Card Transfer"},
            },
        ]
    )
    assert totals["excluded"]["Internal Card Transfer"] == {
        "total": 7,
        "partner_a_paid": 3,
        "partner_b_paid": 4,
    }


def test_internal_transfer_categories_are_excluded_not_home():
    totals = compute(
        [
            {
                "amount": -3,
                "__partner": "partner_a",
                "category": {"title": "Internal Card Transfer"},
            },
            {
                "amount": -4,
                "__partner": "partner_b",
                "category": {"title": "Internal Reimbursement"},
            },
        ]
    )

    assert set(totals["excluded"]) == {
        "Internal Card Transfer",
        "Internal Reimbursement",
    }
    assert "Internal Reimbursement" not in totals["home"]
