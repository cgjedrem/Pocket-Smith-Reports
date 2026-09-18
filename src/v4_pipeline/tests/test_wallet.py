"""Neutral wallet contract tests."""

from tally import compute as tally_compute
from wallet import compute as wallet_compute


def test_wallet_uses_partner_keys_and_total():
    transactions = [
        {
            "amount": 8,
            "__partner": "partner_a",
            "category": {"title": "Income (Partner A)"},
        },
        {
            "amount": -3,
            "__partner": "partner_a",
            "category": {"title": "Shared Essentials"},
        },
        {
            "amount": -2,
            "__partner": "partner_b",
            "category": {"title": "Shared Essentials"},
        },
    ]
    wallet = wallet_compute(tally_compute(transactions), transactions)
    for summary in ("income", "savings", "wallets", "net_cash"):
        assert set(wallet[summary]) >= {"partner_a", "partner_b", "total"}
    assert wallet["wallets"] == {"partner_a": 3, "partner_b": 2, "total": 5}
    assert wallet["net_cash"] == {"partner_a": 5, "partner_b": -2, "total": 3}
