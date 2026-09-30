"""Mega common-economy split coverage — mega_builder._split_section_nets +
build_mega_report split_summary wiring.

IMPORTANT fix (iteration 4, finding 4): this wiring had zero test coverage.
Covers: _split_section_nets grouping/summing detail_agg["cats"] across the
mega window (incl. netting sections not eligible for split), split_summary
populated from detail_agg cats when config enabled, null when disabled/
missing, aggregation math across months, and real-label resolution in the
settlement (mirrors report_pdf-style _load_partner_labels custom-ID
resolution already covered for monthly reports in
tests/reports/test_split_report.py).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from budget_api.services import mega_builder

from .test_mega_builder import _all_months, _mock_context, _mock_mega_report

START = "2026-01"
END = "2026-02"  # 2-month window — keeps per-category lists short + explicit.


@pytest.fixture
def mega_split_seeded(tmp_private_dir: Path) -> Path:
    """Seed ps_raw + config files for mega split tests (2-month window)."""
    for month in _all_months(START, END):
        (tmp_private_dir / f"{month}_ps_raw.json").write_text(
            json.dumps([{"id": 1}, {"id": 2}]), encoding="utf-8"
        )
    (tmp_private_dir / "account_mappings.json").write_text(
        json.dumps({"schema_version": 1, "partners": {}, "accounts": {}}),
        encoding="utf-8",
    )
    (tmp_private_dir / "detailed_section_mapping.json").write_text(
        json.dumps({"account_roles": {}, "category_sections": {}}), encoding="utf-8"
    )
    return tmp_private_dir


def _cats() -> dict[str, dict]:
    """Two split-eligible categories (home, common) across 2 months + one
    ineligible category (income_salary) that must never leak into split
    sections."""
    return {
        "c_rent": {
            "title": "Rent",
            "section": "home",
            "partner_a_net": [1000.0, 1000.0],
            "partner_b_net": [0.0, 0.0],
        },
        "c_groceries": {
            "title": "Groceries",
            "section": "common",
            "partner_a_net": [200.0, 300.0],
            "partner_b_net": [100.0, 50.0],
        },
        "c_salary": {
            "title": "Salary",
            "section": "income_salary",
            "partner_a_net": [5000.0, 5000.0],
            "partner_b_net": [0.0, 0.0],
        },
    }


def _write_split_config(private: Path, config: dict) -> None:
    (private / "split_config.json").write_text(json.dumps(config), encoding="utf-8")


# --------------------------------------------------------------------------- #
# _split_section_nets — grouping + summing across months, section filtering.
# --------------------------------------------------------------------------- #


class TestSplitSectionNets:
    def test_groups_by_eligible_section_only(self):
        result = mega_builder._split_section_nets(_cats())
        assert set(result) == {"home", "common"}  # income_salary excluded

    def test_sums_partner_nets_across_all_months(self):
        result = mega_builder._split_section_nets(_cats())
        assert result["home"] == [
            {
                "category_id": "c_rent",
                "category_title": "Rent",
                "net_partner_a": 2000.0,
                "net_partner_b": 0.0,
            }
        ]
        assert result["common"] == [
            {
                "category_id": "c_groceries",
                "category_title": "Groceries",
                "net_partner_a": 500.0,
                "net_partner_b": 150.0,
            }
        ]

    def test_empty_cats_returns_empty_dict(self):
        assert mega_builder._split_section_nets({}) == {}

    def test_section_with_no_categories_absent_from_result(self):
        """trips has no data in these cats — key absent, not an empty list
        (matches net_category_totals()'s per-section-list convention one
        layer up in compute_split, which uses .get(section, [])."""
        result = mega_builder._split_section_nets(_cats())
        assert "trips" not in result

    def test_multiple_categories_same_section_both_included(self):
        cats = _cats()
        cats["c_utilities"] = {
            "title": "Utilities",
            "section": "home",
            "partner_a_net": [50.0, 60.0],
            "partner_b_net": [50.0, 40.0],
        }
        result = mega_builder._split_section_nets(cats)
        ids = {row["category_id"] for row in result["home"]}
        assert ids == {"c_rent", "c_utilities"}


# --------------------------------------------------------------------------- #
# build_mega_report — split_summary wiring end-to-end.
# --------------------------------------------------------------------------- #


class TestBuildMegaReportSplitWiring:
    def _build_with_cats(self, cats: dict) -> dict:
        context = _mock_context(START, END)
        context["detail_agg"]["cats"] = cats
        with patch(
            "budget_api.services.mega_builder.build_context", return_value=context
        ):
            return mega_builder.build_mega_report(START, END)

    def test_no_config_file_split_summary_is_none(self, mega_split_seeded: Path):
        report = self._build_with_cats(_cats())
        assert report["split_summary"] is None

    def test_disabled_config_split_summary_is_none(self, mega_split_seeded: Path):
        _write_split_config(
            mega_split_seeded,
            {
                "enabled": False,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "sections": ["home", "common"],
            },
        )
        report = self._build_with_cats(_cats())
        assert report["split_summary"] is None

    def test_enabled_config_populates_split_summary_from_detail_agg_cats(
        self, mega_split_seeded: Path
    ):
        _write_split_config(
            mega_split_seeded,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "sections": ["home", "common"],
            },
        )
        report = self._build_with_cats(_cats())
        summary = report["split_summary"]
        assert summary is not None
        assert summary["shares"] == {"partner_a": 50.0, "partner_b": 50.0}
        assert summary["sections"] == ["home", "common"]
        # rows are the mega-window-summed net_category_totals()-shaped rows,
        # not per-month — one row per split-eligible category (2 here).
        rows_by_id = {row["category_id"]: row for row in summary["rows"]}
        assert set(rows_by_id) == {"c_rent", "c_groceries"}
        # Rent: total 2000.0 across 2 months, 50/50 fair share => 1000
        # actual vs 1000 fair => delta 1000 (A fronted the whole rent).
        assert rows_by_id["c_rent"]["actual"] == 2000.0
        assert rows_by_id["c_rent"]["fair"] == 1000.0
        assert rows_by_id["c_rent"]["delta"] == 1000.0
        # Groceries: actual_a 500 (200+300), total 650, fair 325, delta 175.
        assert rows_by_id["c_groceries"]["actual"] == 500.0
        assert rows_by_id["c_groceries"]["fair"] == 325.0
        assert rows_by_id["c_groceries"]["delta"] == 175.0

    def test_aggregation_nets_correctly_across_months_into_settlement(
        self, mega_split_seeded: Path
    ):
        """Single netted settlement across the whole mega window — not a
        per-month or per-category transfer. Total delta_a = 1000 + 175 =
        1175 (A overpaid) => B owes A 1175."""
        _write_split_config(
            mega_split_seeded,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "sections": ["home", "common"],
            },
        )
        report = self._build_with_cats(_cats())
        settlement = report["split_summary"]["settlement"]
        assert settlement is not None
        assert settlement["amount"] == pytest.approx(1175.0)
        # Default placeholder labels (no partner_labels.json/custom mappings
        # seeded by mega_split_seeded) — real-label resolution below.
        assert settlement["from_partner"] == "Partner B"
        assert settlement["to_partner"] == "Partner A"

    def test_only_enabled_sections_contribute_to_mega_split(
        self, mega_split_seeded: Path
    ):
        """common has data but isn't in `sections` — excluded from rows and
        the settlement math."""
        _write_split_config(
            mega_split_seeded,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "sections": ["home"],
            },
        )
        report = self._build_with_cats(_cats())
        summary = report["split_summary"]
        assert [row["category_id"] for row in summary["rows"]] == ["c_rent"]
        assert summary["settlement"]["amount"] == pytest.approx(1000.0)

    def test_real_partner_labels_resolved_in_settlement_custom_ids(
        self, mega_split_seeded: Path
    ):
        """Regression: mega settlement must resolve real display labels for
        custom partner IDs too (alex/sam), not just the default-slot path —
        same _load_partner_labels + _partner_slot_map resolution
        report_builder uses for monthly reports (LG-002 neutral fixture
        IDs: alex sorts before sam -> partner_a)."""
        (mega_split_seeded / "account_mappings.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "partners": {
                        "alex": {"label": "Alex"},
                        "sam": {"label": "Sam"},
                    },
                    "accounts": {},
                }
            ),
            encoding="utf-8",
        )
        _write_split_config(
            mega_split_seeded,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "sections": ["home", "common"],
            },
        )
        report = self._build_with_cats(_cats())
        settlement = report["split_summary"]["settlement"]
        assert settlement["from_partner"] == "Sam"
        assert settlement["to_partner"] == "Alex"
        assert report["partner_labels"] == {"partner_a": "Alex", "partner_b": "Sam"}

    def test_balanced_split_settlement_is_none(self, mega_split_seeded: Path):
        """Even split of an even category — no settlement fabricated."""
        _write_split_config(
            mega_split_seeded,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "sections": ["home"],
            },
        )
        cats = {
            "c_rent": {
                "title": "Rent",
                "section": "home",
                "partner_a_net": [500.0, 500.0],
                "partner_b_net": [500.0, 500.0],
            }
        }
        report = self._build_with_cats(cats)
        assert report["split_summary"]["settlement"] is None

    def test_malformed_config_raises_with_range_context(
        self, mega_split_seeded: Path
    ):
        from accounting import AccountingValidationError

        _write_split_config(
            mega_split_seeded,
            {
                "enabled": True,
                "shares": {"partner_a": 70.0, "partner_b": 40.0},
                "sections": ["home"],
            },
        )
        with pytest.raises(AccountingValidationError, match=f"{START}..{END}"):
            self._build_with_cats(_cats())
