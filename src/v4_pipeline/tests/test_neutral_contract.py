"""Focused neutral partner contract tests."""

import json

from data_loader import load
from tally import compute as tally_compute
from wallet import compute as wallet_compute


def test_loader_mapping_and_excluded_payer_attribution(tmp_path):
    data_path = tmp_path / "fixture.json"
    data_path.write_text(
        json.dumps(
            {
                "transactions": [
                    {
                        "id": 1,
                        "date": "2026-04-01",
                        "amount": -11,
                        "account": {"name": "Fixture A Checking"},
                        "category": {"title": "Internal Card Transfer"},
                    },
                    {
                        "id": 2,
                        "date": "2026-04-01",
                        "amount": -7,
                        "account": {"name": "Fixture B Checking"},
                        "category": {"title": "Internal Account Transfer"},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    transactions = load("2026-04", str(data_path))
    assert [transaction["__partner"] for transaction in transactions] == [
        "partner_a",
        "partner_b",
    ]

    excluded = tally_compute(transactions)["excluded"]
    assert excluded["Internal Card Transfer"] == {
        "total": 11,
        "partner_a_paid": 11,
        "partner_b_paid": 0,
    }
    assert excluded["Internal Account Transfer"] == {
        "total": 7,
        "partner_a_paid": 0,
        "partner_b_paid": 7,
    }


def test_wallet_uses_neutral_partner_keys():
    transactions = [
        {
            "id": 1,
            "date": "2026-04-01",
            "amount": -5,
            "__partner": "partner_a",
            "account": {"name": "Fixture A Checking"},
            "category": {"title": "Shared Essentials"},
        }
    ]
    wallet = wallet_compute(tally_compute(transactions), transactions)
    assert set(wallet["wallets"]) == {"partner_a", "partner_b", "total"}
    assert wallet["wallets"]["partner_a"] == 5
