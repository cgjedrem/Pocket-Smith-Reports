"""Regression: _main_category_spend catalog errors must name the offending txn.

Bug: "Category catalog has no category ID 'x'" gave zero txn context, so
users couldn't find/fix the bad data. Fixed to append id/date/payee/amount.
"""

import pytest

from mega.build_mega import MegaValidationError, _main_category_spend


def _record(record_id, amount, category_id, payee):
    return {
        "id": record_id,
        "date": "2030-04-01",
        "amount": amount,
        "payee": payee,
        "category_path": [{"id": category_id, "title": "Groceries"}],
    }


def test_main_category_spend_missing_catalog_entry_surfaces_transaction():
    records = [_record(55, -20.0, "groceries", "Alex's Grocer")]
    category_roles = {"groceries": "spend"}
    category_parents = {}  # catalog missing "groceries" entirely
    with pytest.raises(MegaValidationError) as exc:
        _main_category_spend(
            records, category_roles, category_parents, category_titles={}
        )
    message = str(exc.value)
    assert "Category catalog has no category ID 'groceries'" in message
    assert "id=55" in message
    assert "date='2030-04-01'" in message
    assert "Alex's Grocer" in message
    assert "amount=-20.0" in message


def test_main_category_spend_uncategorized_hint():
    records = [_record(56, -5.0, "uncategorized", "Sam's Diner")]
    category_roles = {"uncategorized": "spend"}
    category_parents = {}
    with pytest.raises(MegaValidationError) as exc:
        _main_category_spend(
            records, category_roles, category_parents, category_titles={}
        )
    message = str(exc.value)
    assert (
        "category ID 'uncategorized' = transaction has no category assigned "
        "in PocketSmith" in message
    )
    assert "id=56" in message
    assert "Sam's Diner" in message
