"""Unit tests — common-economy split (accounting.py).

Covers net_category_totals (category_id twin of detailed_net_section's
rows), compute_split (netting, sign, empty-sections short-circuit), and
normalize_split_config/load_split_config (100% validation, unknown-section
rejection, missing-file feature-off default).
"""

from __future__ import annotations

import json

import pytest

from accounting import (
    AccountingValidationError,
    compute_split,
    load_split_config,
    net_category_totals,
    normalize_split_config,
)

MAPPING = {
    "category_sections": {
        "c1": "home",
        "c2": "common",
        "c3": "common",
        "c4": "trips",
    },
    "account_roles": {},
}


def _record(
    record_id,
    amount,
    owner,
    category_id,
    date="2026-04-01",
    category_title="Cat",
    is_transfer=False,
):
    return {
        "id": record_id,
        "date": date,
        "amount": amount,
        "payee": None,
        "note": None,
        "account_id": "acc",
        "account_name": None,
        "owner": owner,
        "category_path": [{"id": category_id, "title": category_title}],
        "is_transfer": is_transfer,
    }


# --------------------------------------------------------------------------- #
# net_category_totals — category_id present, same math as detailed_net_section.
# --------------------------------------------------------------------------- #


class TestNetCategoryTotals:
    def test_includes_category_id_and_net_per_partner(self):
        records = [
            _record(1, -600.0, "partner_a", "c2", category_title="Groceries"),
            _record(2, -400.0, "partner_b", "c2", category_title="Groceries"),
        ]
        rows = net_category_totals(records, "common", MAPPING)
        assert rows == [
            {
                "category_id": "c2",
                "category_title": "Groceries",
                "net_partner_a": 600.0,
                "net_partner_b": 400.0,
            }
        ]

    def test_empty_section_is_empty_list(self):
        records = [_record(1, -100.0, "partner_a", "c1")]
        assert net_category_totals(records, "trips", MAPPING) == []

    def test_received_amounts_reduce_net(self):
        records = [
            _record(1, -300.0, "partner_a", "c2"),
            _record(2, 100.0, "partner_a", "c2"),  # reimbursed back
        ]
        rows = net_category_totals(records, "common", MAPPING)
        assert rows[0]["net_partner_a"] == 200.0
        assert rows[0]["net_partner_b"] == 0.0


# --------------------------------------------------------------------------- #
# compute_split — netting, sign, empty-sections.
# --------------------------------------------------------------------------- #


def _nets(section_totals):
    """{section: [(category_id, title, net_a, net_b), ...]} -> compute_split input."""
    return {
        section: [
            {
                "category_id": cid,
                "category_title": title,
                "net_partner_a": net_a,
                "net_partner_b": net_b,
            }
            for cid, title, net_a, net_b in rows
        ]
        for section, rows in section_totals.items()
    }


class TestComputeSplit:
    def test_no_sections_selected_returns_none(self):
        nets = _nets({"home": [("c1", "Home", 1000.0, 0.0)]})
        assert compute_split(nets, {"partner_a": 50.0, "partner_b": 50.0}, []) is None

    def test_even_split_zero_delta_no_settlement(self):
        """Partner A paid the whole 1000 category but shares are 50/50 —
        fair share is 500 each, so delta_a = 500 (A overpaid by 500)."""
        nets = _nets({"home": [("c1", "Home", 1000.0, 0.0)]})
        result = compute_split(nets, {"partner_a": 50.0, "partner_b": 50.0}, ["home"])
        assert result["rows"] == [
            {"category_id": "c1", "label": "Home", "actual": 1000.0, "fair": 500.0, "delta": 500.0}
        ]
        assert result["settlement"] == {
            "from_partner": "partner_b",
            "to_partner": "partner_a",
            "amount": 500.0,
        }

    def test_actual_matches_fair_share_no_settlement(self):
        """Partner A paid exactly their 70% fair share — nothing owed."""
        nets = _nets({"home": [("c1", "Home", 700.0, 300.0)]})
        result = compute_split(nets, {"partner_a": 70.0, "partner_b": 30.0}, ["home"])
        assert result["rows"][0]["delta"] == 0.0
        assert result["settlement"] is None

    def test_settlement_direction_flips_when_b_overpays(self):
        nets = _nets({"home": [("c1", "Home", 0.0, 1000.0)]})
        result = compute_split(nets, {"partner_a": 50.0, "partner_b": 50.0}, ["home"])
        assert result["settlement"] == {
            "from_partner": "partner_a",
            "to_partner": "partner_b",
            "amount": 500.0,
        }

    def test_settlement_nets_across_multiple_categories_and_sections(self):
        """One category favors A, another favors B — settlement is the
        single netted total, not a per-category transfer."""
        nets = _nets(
            {
                "home": [("c1", "Home", 1000.0, 0.0)],  # A overpays 500 @ 50/50
                "common": [("c2", "Groceries", 0.0, 1000.0)],  # B overpays 500
            }
        )
        result = compute_split(
            nets, {"partner_a": 50.0, "partner_b": 50.0}, ["home", "common"]
        )
        assert len(result["rows"]) == 2
        assert result["settlement"] is None  # deltas cancel out exactly

    def test_only_enabled_sections_contribute(self):
        """trips has data but isn't in `sections` — excluded from rows/settlement."""
        nets = _nets(
            {
                "home": [("c1", "Home", 1000.0, 0.0)],
                "trips": [("c4", "Trip", 5000.0, 0.0)],
            }
        )
        result = compute_split(nets, {"partner_a": 50.0, "partner_b": 50.0}, ["home"])
        assert [row["category_id"] for row in result["rows"]] == ["c1"]

    def test_shares_and_sections_echoed_back(self):
        nets = _nets({"home": [("c1", "Home", 100.0, 100.0)]})
        result = compute_split(nets, {"partner_a": 60.0, "partner_b": 40.0}, ["home"])
        assert result["shares"] == {"partner_a": 60.0, "partner_b": 40.0}
        assert result["sections"] == ["home"]

    def test_balanced_multi_category_nonround_shares_no_fabricated_settlement(self):
        """Regression (iteration 4 CRITICAL fix): float-equality (`!= 0`)
        fabricated a spurious ~0.00 settlement once a genuinely balanced
        split with non-round shares (33.33/66.67-style) accumulates float
        noise across 10+ categories. Here the raw delta sum is ~5e-13 —
        nonzero bit-for-bit, but well inside the 1e-6 tolerance (same
        convention as the shares-sum check) — must resolve to None, never a
        fabricated transfer."""
        totals = [
            300.0, 600.0, 150.0, 900.0, 450.0, 1200.0,
            75.0, 2100.0, 330.0, 990.0, 60.0, 1770.0,
        ]
        rows = [
            (f"c{i}", f"Cat{i}", total / 3.0, total - total / 3.0)
            for i, total in enumerate(totals)
        ]
        nets = _nets({"common": rows})
        shares = {"partner_a": 100 / 3, "partner_b": 200 / 3}
        result = compute_split(nets, shares, ["common"])
        assert len(result["rows"]) == len(totals)
        total_delta = sum(row["delta"] for row in result["rows"])
        # Proves the fixture actually exercises float noise, not a trivially
        # exact-zero case — the pre-fix `!= 0` check would have fabricated
        # a settlement here.
        assert total_delta != 0.0
        assert abs(total_delta) < 1e-6
        assert result["settlement"] is None


# --------------------------------------------------------------------------- #
# normalize_split_config / load_split_config — validation + missing-file.
# --------------------------------------------------------------------------- #


class TestNormalizeSplitConfig:
    def test_disabled_returns_none(self):
        assert normalize_split_config(
            {"enabled": False, "shares": {"partner_a": 50.0, "partner_b": 50.0}, "sections": []}
        ) is None

    def test_valid_enabled_config_normalizes(self):
        result = normalize_split_config(
            {
                "enabled": True,
                "shares": {"partner_a": 60.0, "partner_b": 40.0},
                "sections": ["home", "common"],
            }
        )
        assert result == {
            "shares": {"partner_a": 60.0, "partner_b": 40.0},
            "sections": ["home", "common"],
        }

    def test_shares_not_summing_to_100_raises(self):
        with pytest.raises(AccountingValidationError, match="sum to 100"):
            normalize_split_config(
                {
                    "enabled": True,
                    "shares": {"partner_a": 60.0, "partner_b": 30.0},
                    "sections": ["home"],
                }
            )

    def test_shares_sum_within_tolerance_passes(self):
        result = normalize_split_config(
            {
                "enabled": True,
                "shares": {"partner_a": 50.0000001, "partner_b": 49.9999999},
                "sections": [],
            }
        )
        assert result["sections"] == []

    def test_unknown_section_rejected(self):
        with pytest.raises(AccountingValidationError, match="unknown section"):
            normalize_split_config(
                {
                    "enabled": True,
                    "shares": {"partner_a": 50.0, "partner_b": 50.0},
                    "sections": ["home", "personal_partner_a"],
                }
            )

    def test_share_out_of_range_rejected(self):
        with pytest.raises(AccountingValidationError, match="between 0 and 100"):
            normalize_split_config(
                {
                    "enabled": True,
                    "shares": {"partner_a": 150.0, "partner_b": -50.0},
                    "sections": [],
                }
            )

    def test_nan_share_rejected(self):
        """Regression (iteration 4 CRITICAL fix): NaN compares false in
        every range/sum check (`NaN < 0` is False, `NaN > 100` is False,
        `abs(NaN + x - 100) > 1e-6` is False) — a bare range check lets
        `float("nan")` sail through and get persisted. Must raise before
        those comparisons run."""
        with pytest.raises(AccountingValidationError, match="finite"):
            normalize_split_config(
                {
                    "enabled": True,
                    "shares": {"partner_a": float("nan"), "partner_b": 50.0},
                    "sections": [],
                }
            )

    def test_infinity_share_rejected(self):
        with pytest.raises(AccountingValidationError, match="finite"):
            normalize_split_config(
                {
                    "enabled": True,
                    "shares": {"partner_a": float("inf"), "partner_b": 50.0},
                    "sections": [],
                }
            )

    def test_negative_infinity_share_rejected(self):
        with pytest.raises(AccountingValidationError, match="finite"):
            normalize_split_config(
                {
                    "enabled": True,
                    "shares": {"partner_a": float("-inf"), "partner_b": 50.0},
                    "sections": [],
                }
            )

    def test_missing_share_key_rejected(self):
        with pytest.raises(AccountingValidationError, match="partner_a and partner_b"):
            normalize_split_config(
                {"enabled": True, "shares": {"partner_a": 100.0}, "sections": []}
            )

    def test_duplicate_sections_deduped_preserving_order(self):
        result = normalize_split_config(
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "sections": ["common", "home", "common"],
            }
        )
        assert result["sections"] == ["common", "home"]

    def test_not_an_object_rejected(self):
        with pytest.raises(AccountingValidationError):
            normalize_split_config([1, 2, 3])


class TestLoadSplitConfig:
    def test_missing_file_returns_none(self, tmp_path):
        assert load_split_config(tmp_path / "nope.json") is None

    def test_reads_and_normalizes_file(self, tmp_path):
        path = tmp_path / "split_config.json"
        path.write_text(
            json.dumps(
                {
                    "enabled": True,
                    "shares": {"partner_a": 55.0, "partner_b": 45.0},
                    "sections": ["home"],
                }
            ),
            encoding="utf-8",
        )
        assert load_split_config(path) == {
            "shares": {"partner_a": 55.0, "partner_b": 45.0},
            "sections": ["home"],
        }

    def test_disabled_file_returns_none(self, tmp_path):
        path = tmp_path / "split_config.json"
        path.write_text(json.dumps({"enabled": False}), encoding="utf-8")
        assert load_split_config(path) is None

    def test_corrupt_json_raises(self, tmp_path):
        path = tmp_path / "split_config.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(AccountingValidationError, match="unreadable"):
            load_split_config(path)
