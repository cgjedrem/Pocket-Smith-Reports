"""Internal reimbursement routing tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tally import compute as tally_compute
from wallet import compute as wallet_compute


def _txn(tid, amount, partner, title="Internal Reimbursement"):
    return {
        "id": tid,
        "amount": amount,
        "category": {"title": title},
        "__partner": partner,
        "__account_name": f"Fixture {'A' if partner == 'partner_a' else 'B'} Checking",
    }


def test_internal_reimbursement_is_excluded_not_a_wallet_category():
    txns = [
        _txn(100001, -400, "partner_a"),
        _txn(100011, -400, "partner_b"),
    ]
    totals = tally_compute(txns)
    wallet = wallet_compute(totals, txns)

    assert totals["excluded"]["Internal Reimbursement"] == {
        "total": 800,
        "partner_a_paid": 400,
        "partner_b_paid": 400,
    }
    assert "Internal Reimbursement" not in wallet["cats"]
