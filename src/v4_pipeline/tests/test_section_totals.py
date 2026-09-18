"""Neutral section contract tests."""


def test_category_entries_use_neutral_partner_fields(wallet):
    for category in wallet["cats"].values():
        assert {
            "partner_a_paid",
            "partner_b_paid",
            "partner_a_received",
            "partner_b_received",
            "partner_a_net",
            "partner_b_net",
        } <= category.keys()
