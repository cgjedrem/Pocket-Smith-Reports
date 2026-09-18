"""Unit tests — PR2 detailed-section builders in accounting.py.

Covers `_paired_reimbursements` edge cases (moved from accounting_html.py),
sign-class boundaries (±0.0 -> "zero"), and pct div-by-zero guards
(income == 0 -> None, never 0). Section builders operate on already-
normalized record dicts, so tests build those directly rather than routing
through the full normalize_transactions pipeline.
"""

from __future__ import annotations

from accounting import (
    _paired_reimbursements,
    _safe_pct,
    _sign_class,
    detailed_income_section,
    detailed_savings_section,
    has_income_records,
)

MAPPING = {
    "category_sections": {
        "3": "income_salary",
        "4": "income_third_party",
    },
    "account_roles": {},
}


class TestHasIncomeRecords:
    def test_no_records_is_false(self):
        assert not has_income_records([], MAPPING)

    def test_non_income_category_is_false(self):
        mapping = {"category_sections": {"9": "home"}, "account_roles": {}}
        assert not has_income_records([_record(1, 100.0, "partner_a", category_id="9")], mapping)

    def test_income_transfer_routes_to_excluded(self):
        """Transfers route to excluded — an income-categorized transfer does
        not count as income (mirrors detailed_income_section routing)."""
        assert not has_income_records(
            [_record(1, 100.0, "partner_a", is_transfer=True)], MAPPING
        )

    def test_salary_and_third_party_both_count(self):
        assert has_income_records([_record(1, 100.0, "partner_a", category_id="3")], MAPPING)
        assert has_income_records([_record(2, 100.0, "partner_a", category_id="4")], MAPPING)


def _record(record_id, amount, owner, date="2026-04-01", category_id="3", is_transfer=False):
    return {
        "id": record_id,
        "date": date,
        "amount": amount,
        "payee": None,
        "note": None,
        "account_id": "acc",
        "account_name": None,
        "owner": owner,
        "category_path": [{"id": category_id, "title": "Cat"}],
        "is_transfer": is_transfer,
    }


def _group(records):
    return {"title": "Cat", "records": records}


# --------------------------------------------------------------------------- #
# _paired_reimbursements — moved from accounting_html.py.
# --------------------------------------------------------------------------- #


class TestPairedReimbursements:
    def test_same_owner_not_paired(self):
        """Opposite amounts, same owner — never pairs."""
        records = [
            _record(1, 100.0, "partner_a"),
            _record(2, -100.0, "partner_a"),
        ]
        assert _paired_reimbursements(_group(records)) == []

    def test_zero_amount_skipped(self):
        """Zero amounts never pair, even opposite-owner with amount == -amount."""
        records = [
            _record(1, 0.0, "partner_a"),
            _record(2, 0.0, "partner_b"),
        ]
        assert _paired_reimbursements(_group(records)) == []

    def test_date_id_tie_break_sort(self):
        """Same date — sorted by id before pairing, so matches follow (date, id) order."""
        records = [
            _record("b", -100.0, "partner_b", date="2026-04-01"),
            _record("a", 100.0, "partner_a", date="2026-04-01"),
        ]
        pairs = _paired_reimbursements(_group(records))
        assert len(pairs) == 1
        first, second = pairs[0]
        # Sorted by (date, id) first -> "a" (partner_a, +100) then "b" (partner_b, -100).
        assert first["id"] == "a"
        assert second["id"] == "b"

    def test_missing_and_numeric_id_tie_break_no_typeerror(self):
        """Normalized records allow id=None while upstream ids are numeric.

        (date, id) sort must never compare "" against int — PR#54 review.
        """
        records = [
            _record(7, -100.0, "partner_b", date="2026-04-01"),
            _record(None, 100.0, "partner_a", date="2026-04-01"),
        ]
        pairs = _paired_reimbursements(_group(records))
        assert len(pairs) == 1
        first, second = pairs[0]
        assert first["id"] is None and second["id"] == 7

    def test_greedy_first_match_order(self):
        """Greedy: earliest unused record pairs with the first eligible match, not the best one."""
        records = [
            _record(1, 100.0, "partner_a", date="2026-04-01"),
            _record(2, -100.0, "partner_b", date="2026-04-02"),
            _record(3, -100.0, "partner_b", date="2026-04-03"),
        ]
        pairs = _paired_reimbursements(_group(records))
        assert len(pairs) == 1
        first, second = pairs[0]
        # Record 1 greedily pairs with record 2 (first eligible), leaving 3 unpaired.
        assert (first["id"], second["id"]) == (1, 2)

    def test_non_zero_but_unequal_amounts_not_paired(self):
        records = [
            _record(1, 100.0, "partner_a"),
            _record(2, -50.0, "partner_b"),
        ]
        assert _paired_reimbursements(_group(records)) == []


# --------------------------------------------------------------------------- #
# Sign-class boundaries.
# --------------------------------------------------------------------------- #


class TestSignClass:
    def test_positive_zero_is_zero_class(self):
        assert _sign_class(0.0) == "zero"

    def test_negative_zero_is_zero_class(self):
        assert _sign_class(-0.0) == "zero"

    def test_positive_value_is_pos_class(self):
        assert _sign_class(0.01) == "pos"

    def test_negative_value_is_neg_class(self):
        assert _sign_class(-0.01) == "neg"


# --------------------------------------------------------------------------- #
# Pct div-by-zero guard.
# --------------------------------------------------------------------------- #


class TestSafePct:
    def test_zero_denominator_is_none(self):
        assert _safe_pct(50.0, 0.0) is None

    def test_nonzero_denominator_computes_pct(self):
        assert _safe_pct(50.0, 200.0) == 25.0


class TestIncomeSectionZeroGuards:
    def test_income_zero_gives_null_percentages(self):
        """No income records at all -> every pct field is None, not 0."""
        section = detailed_income_section([], MAPPING)
        assert section["salary"]["row_pct_partner_a"] is None
        assert section["salary"]["row_pct_partner_b"] is None
        assert section["salary"]["household_pct"] is None
        assert section["third_party"]["household_pct"] is None
        assert section["total_income"] == 0.0
        assert section["total_income_class"] == "zero"

    def test_one_side_zero_still_computes_other_row(self):
        records = [_record(1, 100.0, "partner_a", category_id="3")]
        section = detailed_income_section(records, MAPPING)
        assert section["salary"]["row_pct_partner_a"] == 100.0
        assert section["salary"]["row_pct_partner_b"] == 0.0
        # third_party row_total is 0 but total_income (100) is nonzero ->
        # household_pct is a real 0.0, not None (only the row's own 0/0 nulls).
        assert section["third_party"]["household_pct"] == 0.0
        assert section["third_party"]["row_pct_partner_a"] is None


class TestSavingsSectionZeroIncome:
    def test_zero_income_gives_null_rate(self):
        savings_summary = {
            "partner_a": {"to_savings": 0.0, "from_savings": 0.0, "net_saved": 0.0},
            "partner_b": {"to_savings": 0.0, "from_savings": 0.0, "net_saved": 0.0},
            "total": {"to_savings": 0.0, "from_savings": 0.0, "net_saved": 0.0},
        }
        section = detailed_savings_section([], savings_summary, MAPPING)
        assert section["partner_a"]["rate"] is None
        assert section["partner_b"]["rate"] is None
        assert section["household"]["rate"] is None

    def test_none_savings_summary_gives_none_section(self):
        assert detailed_savings_section([], None, MAPPING) is None
