"""Regression tests: reimbursement pairing is not report policy."""

from tally import compute as tally_compute
from wallet import compute as wallet_compute


def test_opposite_sign_category_movements_remain_unpaired():
    transactions = [
        {
            "amount": -100,
            "__partner": "partner_a",
            "category": {"title": "Shared Service"},
        },
        {
            "amount": 100,
            "__partner": "partner_b",
            "category": {"title": "Shared Service"},
        },
    ]

    wallet = wallet_compute(tally_compute(transactions), transactions)
    category = wallet["cats"]["Shared Service"]
    assert wallet["paired_reimb_events"] == []
    assert category["partner_a_net"] == 100
    assert category["partner_b_net"] == -100


def _make_transaction(date, amount, category, account):
    return {
        "id": 1,
        "date": date,
        "amount": amount,
        "payee": "test",
        "category": {"id": 1, "title": category},
        "transaction_account": {"id": 1, "name": account},
        "account": {"id": 1, "name": account},
    }


def _wallet_for(transactions):
    return wallet_compute(tally_compute(transactions), transactions)


def test_synthetic_internal_reimbursement_does_not_create_pair(wallet):
    assert wallet["paired_reimb_events"] == []


def test_synthetic_shared_service_movements_do_not_create_pair(wallet):
    assert wallet["paired_reimb_events"] == []


def test_same_account_opposite_movements_do_not_create_pair():
    transactions = [
        _make_transaction("2026-04-01", -3000, "Shopping", "Fixture A Checking"),
        _make_transaction("2026-04-01", 3000, "Shopping", "Fixture A Checking"),
    ]

    assert _wallet_for(transactions)["paired_reimb_events"] == []


def test_different_categories_do_not_create_pair():
    transactions = [
        _make_transaction("2026-04-01", -1000, "Groceries", "Fixture A Checking"),
        _make_transaction(
            "2026-04-01", 1000, "Different Category", "Fixture B Checking"
        ),
    ]

    assert _wallet_for(transactions)["paired_reimb_events"] == []


def test_same_partner_movements_do_not_create_pair():
    transactions = [
        _make_transaction("2026-04-01", -1000, "Groceries", "Fixture A Checking"),
        _make_transaction("2026-04-01", 1000, "Groceries", "Fixture A Credit"),
    ]

    assert _wallet_for(transactions)["paired_reimb_events"] == []


def test_personal_category_movements_do_not_create_pair():
    transactions = [
        _make_transaction(
            "2026-04-01", -1000, "Personal-Partner A", "Fixture A Checking"
        ),
        _make_transaction(
            "2026-04-01", 1000, "Personal-Partner A", "Fixture B Checking"
        ),
    ]

    assert _wallet_for(transactions)["paired_reimb_events"] == []


def test_savings_category_movements_do_not_create_pair():
    transactions = [
        _make_transaction(
            "2026-04-01", -5000, "Savings (Partner A)", "Fixture A Checking"
        ),
        _make_transaction(
            "2026-04-01", 5000, "Savings (Partner A)", "Fixture A Savings"
        ),
    ]

    assert _wallet_for(transactions)["paired_reimb_events"] == []


def test_opposite_movements_four_days_apart_do_not_create_pair():
    transactions = [
        _make_transaction("2026-04-01", -1000, "Groceries", "Fixture A Checking"),
        _make_transaction("2026-04-05", 1000, "Groceries", "Fixture B Checking"),
    ]

    assert _wallet_for(transactions)["paired_reimb_events"] == []


def test_opposite_movements_three_days_apart_do_not_create_pair():
    transactions = [
        _make_transaction("2026-04-01", -1000, "Groceries", "Fixture A Checking"),
        _make_transaction("2026-04-04", 1000, "Groceries", "Fixture B Checking"),
    ]

    assert _wallet_for(transactions)["paired_reimb_events"] == []


def test_opposite_partner_movements_do_not_create_direction_event():
    transactions = [
        _make_transaction("2026-04-01", -1000, "Groceries", "Fixture B Checking"),
        _make_transaction("2026-04-01", 1000, "Groceries", "Fixture A Checking"),
    ]

    assert _wallet_for(transactions)["paired_reimb_events"] == []
