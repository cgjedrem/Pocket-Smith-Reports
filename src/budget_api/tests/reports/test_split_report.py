"""Common-economy split wiring — report_builder.build_report(month),
category-level selection (Gate 2 evolution).

Uses the same public synthetic fixture as the golden-baseline test (no real
identifiers — LG-002). Covers: no config => split None (regression already
covered by golden baseline, re-asserted here for clarity), enabled config
=> populated split with resolved settlement labels, disabled config =>
None, malformed on-disk config => AccountingValidationError with month
context, unknown category ID written directly to disk (bypassing the API
validation layer, but only checked when a category catalog exists) => still
rejected defensively, and a parent-category selection expanding to its
descendant leaves via the real category catalog fixture.

Category IDs used here ("1".."11") are the real leaf category IDs from
data/sample_apr_2026_detailed_section_mapping.json (home=["6"],
common=["1","2"], trips=["9"]) — translated once via
accounting.migrate_legacy_split_sections so this file doesn't hardcode a
copy that could drift from the fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from budget_api.services import report_builder

REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURE_PATH = REPO_ROOT / "data" / "sample_apr_2026.json"
MAPPING_PATH = REPO_ROOT / "data" / "sample_apr_2026_detailed_section_mapping.json"
MONTH = "2026-04"

_DETAILED_SECTION_MAPPING = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))


def _categories_for_sections(*sections: str) -> list[str]:
    from accounting import migrate_legacy_split_sections

    return migrate_legacy_split_sections(list(sections), _DETAILED_SECTION_MAPPING)


HOME_CATEGORIES = _categories_for_sections("home")
COMMON_CATEGORIES = _categories_for_sections("common")
TRIPS_CATEGORIES = _categories_for_sections("trips")
ALL_THREE_CATEGORIES = _categories_for_sections("home", "common", "trips")


@pytest.fixture
def seeded_dir(tmp_private_dir: Path) -> Path:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    (tmp_private_dir / "2026-04_ps_raw.json").write_text(
        json.dumps(fixture), encoding="utf-8"
    )
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    (tmp_private_dir / "detailed_section_mapping.json").write_text(
        json.dumps(mapping), encoding="utf-8"
    )
    return tmp_private_dir


def _write_split_config(private: Path, config: dict) -> None:
    (private / "split_config.json").write_text(json.dumps(config), encoding="utf-8")


class TestSplitWiring:
    def test_no_config_file_split_is_none(self, seeded_dir: Path):
        report = report_builder.build_report(MONTH)
        assert report["detailed"]["split"] is None

    def test_disabled_config_split_is_none(self, seeded_dir: Path):
        _write_split_config(
            seeded_dir,
            {
                "enabled": False,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": HOME_CATEGORIES,
            },
        )
        report = report_builder.build_report(MONTH)
        assert report["detailed"]["split"] is None

    def test_enabled_config_populates_split_with_real_labels(self, seeded_dir: Path):
        _write_split_config(
            seeded_dir,
            {
                "enabled": True,
                "shares": {"partner_a": 60.0, "partner_b": 40.0},
                "categories": ALL_THREE_CATEGORIES,
            },
        )
        report = report_builder.build_report(MONTH)
        split = report["detailed"]["split"]
        assert split is not None
        assert split["shares"] == {"partner_a": 60.0, "partner_b": 40.0}
        assert split["sections"] == ["home", "common", "trips"]
        assert isinstance(split["rows"], list)
        assert all("section" in row for row in split["rows"])
        # b-side additive fields present on every row, exact complement
        # (fair + fair_b == actual + actual_b == category total; can't
        # independently recompute "total" here, so assert the two
        # invariants that hold regardless: delta_b == -delta, and
        # fair_a + fair_b == actual_a + actual_b).
        for row in split["rows"]:
            assert row["delta_b"] == pytest.approx(-row["delta"])
            assert row["fair"] + row["fair_b"] == pytest.approx(
                row["actual"] + row["actual_b"]
            )
        # Default partner labels — no partner_labels.json seeded.
        if split["settlement"] is not None:
            assert split["settlement"]["from_partner"] in ("Partner A", "Partner B")
            assert split["settlement"]["to_partner"] in ("Partner A", "Partner B")
            assert split["settlement"]["amount"] > 0

        # Rows sum to the same net totals accounting.detailed_net_section
        # reports for each selected section — parity check (partner_a side).
        home = report["detailed"]["home"]
        common = report["detailed"]["common"]
        trips = report["detailed"]["trips"]
        expected_total_a = (
            home["total_partner_a"] + common["total_partner_a"] + trips["total_partner_a"]
        )
        assert sum(row["actual"] for row in split["rows"]) == pytest.approx(
            expected_total_a
        )

    def test_category_subset_only_sums_selected_categories(self, seeded_dir: Path):
        _write_split_config(
            seeded_dir,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": HOME_CATEGORIES,
            },
        )
        report = report_builder.build_report(MONTH)
        split = report["detailed"]["split"]
        assert split["sections"] == ["home"]
        home_total_a = report["detailed"]["home"]["total_partner_a"]
        assert sum(row["actual"] for row in split["rows"]) == pytest.approx(
            home_total_a
        )

    def test_empty_categories_selected_still_populates_split_empty(
        self, seeded_dir: Path
    ):
        """Design decision: enabled=true + zero categories selected is
        ALLOWED — split stays a non-None dict (empty rows, settlement
        None, sections [])."""
        _write_split_config(
            seeded_dir,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": [],
            },
        )
        report = report_builder.build_report(MONTH)
        split = report["detailed"]["split"]
        assert split == {
            "shares": {"partner_a": 50.0, "partner_b": 50.0},
            "sections": [],
            "rows": [],
            "settlement": None,
        }

    def test_categories_outside_home_common_trips_included(self, seeded_dir: Path):
        """No section-eligibility restriction any more — a
        personal_partner_a-mapped category participates like any other."""
        personal_categories = _categories_for_sections("personal_partner_a")
        _write_split_config(
            seeded_dir,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": personal_categories,
            },
        )
        report = report_builder.build_report(MONTH)
        split = report["detailed"]["split"]
        assert split["sections"] == ["personal_partner_a"]

    def test_malformed_config_raises_with_month_context(self, seeded_dir: Path):
        from accounting import AccountingValidationError

        _write_split_config(
            seeded_dir,
            {
                "enabled": True,
                "shares": {"partner_a": 70.0, "partner_b": 40.0},
                "categories": HOME_CATEGORIES,
            },
        )
        with pytest.raises(AccountingValidationError, match=MONTH):
            report_builder.build_report(MONTH)

    def test_legacy_sections_only_config_on_disk_still_loads(self, seeded_dir: Path):
        """Pre-category-picker on-disk file (only `sections`) is still
        auto-translated at report-build time via the detailed section
        mapping — no crash, no manual migration needed."""
        _write_split_config(
            seeded_dir,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "sections": ["home"],
            },
        )
        report = report_builder.build_report(MONTH)
        split = report["detailed"]["split"]
        assert split["sections"] == ["home"]

    def test_unknown_category_id_on_disk_rejected_defensively_with_catalog(
        self, seeded_dir: Path, write_categories: Path
    ):
        """API layer blocks unknown category IDs at write time; this
        proves the report-build-time re-validation also catches a
        hand-edited file, when a category catalog exists to validate
        against."""
        from accounting import AccountingValidationError

        _write_split_config(
            seeded_dir,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["not-a-real-category-id"],
            },
        )
        with pytest.raises(AccountingValidationError):
            report_builder.build_report(MONTH)

    def test_calculation_version_is_10(self, seeded_dir: Path):
        report = report_builder.build_report(MONTH)
        assert report["calculation_version"] == 10
