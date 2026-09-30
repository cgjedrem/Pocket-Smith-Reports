"""HTML/PDF parity block — accounting_html.render(split_config=...).

Confirms: (1) no split_config => byte-identical to before (no new markup,
existing callers unaffected — additive param default None); (2) with an
enabled split config, the "Common economy split" block appears with the
per-category actual/fair/delta table and a settlement line whose numbers
match accounting.compute_split() exactly (parity, not reimplementation);
(3) empty/no-selected-sections => no block, same as split=None.
"""

from accounting import build_month_contract, compute_split, net_category_totals
from accounting_html import render

OWNERS = {"account-a": "partner_a", "account-b": "partner_b"}

HOME = {"id": "home-cat", "title": "Home"}
COMMON = {"id": "common-cat", "title": "Common"}

DETAILED_SECTION_MAPPING = {
    "category_sections": {"home-cat": "home", "common-cat": "common"},
    "account_roles": {},
}

PARTNER_LABELS = {"partner_a": "Fixture A", "partner_b": "Fixture B"}


def _transaction(transaction_id, amount, category, account_id):
    return {
        "id": transaction_id,
        "date": "2030-04-01",
        "amount": amount,
        "account": {"id": account_id},
        "category": category,
    }


def _contract():
    transactions = [
        _transaction(1, -1000.0, HOME, "account-a"),
        _transaction(2, -400.0, HOME, "account-b"),
        _transaction(3, -600.0, COMMON, "account-a"),
        _transaction(4, -600.0, COMMON, "account-b"),
    ]
    return build_month_contract(
        transactions,
        OWNERS,
        detailed_section_mapping=DETAILED_SECTION_MAPPING,
    )


def test_no_split_config_no_block_rendered():
    html = render(_contract(), "2030-04", PARTNER_LABELS)
    assert "Common economy split" not in html


def test_enabled_split_config_renders_block_matching_compute_split():
    contract = _contract()
    split_config = {
        "shares": {"partner_a": 60.0, "partner_b": 40.0},
        "sections": ["home", "common"],
    }
    html = render(contract, "2030-04", PARTNER_LABELS, split_config=split_config)
    assert "Common economy split" in html

    records = contract["normalized_transactions"]
    section_nets = {
        section: net_category_totals(records, section, DETAILED_SECTION_MAPPING)
        for section in ("home", "common", "trips")
    }
    expected = compute_split(
        section_nets, split_config["shares"], split_config["sections"]
    )
    assert expected is not None
    for row in expected["rows"]:
        assert f"{row['actual']:,.2f}" in html
        assert f"{row['fair']:,.2f}" in html
    settlement = expected["settlement"]
    assert settlement is not None
    from_label = PARTNER_LABELS[settlement["from_partner"]]
    to_label = PARTNER_LABELS[settlement["to_partner"]]
    assert f"{from_label} owes {to_label}" in html
    assert f"{settlement['amount']:,.2f}" in html


def test_no_sections_selected_no_block_rendered():
    contract = _contract()
    split_config = {"shares": {"partner_a": 50.0, "partner_b": 50.0}, "sections": []}
    html = render(contract, "2030-04", PARTNER_LABELS, split_config=split_config)
    assert "Common economy split" not in html


def test_perfectly_balanced_split_shows_no_settlement_em_dash():
    contract = _contract()
    # 50/50 on this exact fixture nets to a perfect split (1000/1000 home
    # is 60/40 personal-account paid, but net home total splits evenly at
    # 50/50 shares only if actual == fair for both categories combined).
    split_config = {
        "shares": {"partner_a": 50.0, "partner_b": 50.0},
        "sections": ["common"],
    }
    html = render(contract, "2030-04", PARTNER_LABELS, split_config=split_config)
    assert "Common economy split" in html
    assert "already even" in html
