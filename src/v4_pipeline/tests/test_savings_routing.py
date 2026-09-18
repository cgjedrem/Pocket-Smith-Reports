"""Regression tests for shared savings summary semantics."""

from accounting import build_month_contract
from accounting_html import render

OWNERS = {
    "account-a": "partner_a",
    "source-account": "partner_a",
}

DETAILED_SECTION_MAPPING = {
    "category_sections": {"income": "income_salary", "savings": "savings"},
    "account_roles": {"account-a": "savings_partner_a"},
}


def _transaction(transaction_id, amount, category, account_id):
    return {
        "id": transaction_id,
        "date": "2030-04-01",
        "amount": amount,
        "account": {"id": account_id},
        "category": category,
    }


def _render(contract):
    return render(
        contract,
        "2030-04",
        {"partner_a": "Fixture A", "partner_b": "Fixture B"},
    )


def test_august_savings_summary_drives_kpi_and_table():
    savings = {"id": "savings", "title": "Savings"}
    home = {"id": "home", "title": "Home"}
    mapping = {
        "category_sections": {"savings": "savings", "home": "home"},
        "account_roles": {"account-a": "savings_partner_a"},
    }
    transactions = [
        _transaction(1, 10000.0, home, "account-a"),
        _transaction(2, 5000.0, home, "account-a"),
        _transaction(3, -1000.0, savings, "account-a"),
        _transaction(4, -10000.0, home, "account-a"),
        _transaction(5, -5000.0, home, "account-a"),
    ]
    for transaction in transactions:
        transaction["date"] = "2025-08-15"

    contract = build_month_contract(
        transactions,
        OWNERS,
        {"savings": "savings", "home": "spend"},
        detailed_section_mapping=mapping,
    )
    assert contract["savings_summary"]["partner_a"] == {
        "to_savings": 16000.0,
        "from_savings": 16000.0,
        "kron_net": -1000.0,
        "net_saved": 0.0,
    }
    assert contract["kpis"]["partner_a"]["net_savings"] == 0.0
    assert contract["kpis"]["total"]["net_savings"] == 0.0
    assert (
        "<td>Household</td><td>16,000.00</td><td>16,000.00</td><td>0.00</td>"
        in _render(contract)
    )


def test_multiple_kron_values_net_once_before_absolute_value():
    kron = {"id": "kron", "title": "Kron"}
    contract = build_month_contract(
        [
            _transaction(1, -1000.0, kron, "source-account"),
            _transaction(2, 400.0, kron, "source-account"),
        ],
        OWNERS,
        {"kron": "investment"},
        detailed_section_mapping={
            "category_sections": {"kron": "savings"},
            "account_roles": {},
        },
    )

    assert contract["savings_summary"]["partner_a"]["to_savings"] == 600.0
    assert contract["savings_summary"]["partner_a"]["net_saved"] == 600.0


def test_positive_kron_overlap_counts_kron_and_savings_account_transfers():
    kron = {"id": "kron", "title": "Kron"}
    contract = build_month_contract(
        [_transaction(1, 1000.0, kron, "account-a")],
        OWNERS,
        {"kron": "investment"},
        detailed_section_mapping={
            "category_sections": {"kron": "savings"},
            "account_roles": {"account-a": "savings_partner_a"},
        },
    )

    assert contract["savings_summary"]["partner_a"] == {
        "to_savings": 2000.0,
        "from_savings": 0.0,
        "kron_net": 1000.0,
        "net_saved": 2000.0,
    }
