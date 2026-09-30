"""Common-economy split wiring — report_builder.build_report(month).

Uses the same public synthetic fixture as the golden-baseline test (no real
identifiers — LG-002). Covers: no config => split None (regression already
covered by golden baseline, re-asserted here for clarity), enabled config
=> populated split with resolved settlement labels, disabled config =>
None, malformed on-disk config => AccountingValidationError with month
context, unknown section written directly to disk (bypassing the API
validation layer) => still rejected defensively.
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
                "sections": ["home"],
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
                "sections": ["home", "common", "trips"],
            },
        )
        report = report_builder.build_report(MONTH)
        split = report["detailed"]["split"]
        assert split is not None
        assert split["shares"] == {"partner_a": 60.0, "partner_b": 40.0}
        assert split["sections"] == ["home", "common", "trips"]
        assert isinstance(split["rows"], list)
        # Default partner labels — no partner_labels.json seeded.
        if split["settlement"] is not None:
            assert split["settlement"]["from_partner"] in ("Partner A", "Partner B")
            assert split["settlement"]["to_partner"] in ("Partner A", "Partner B")
            assert split["settlement"]["amount"] > 0

        # Rows sum to the same net totals accounting.detailed_net_section
        # reports for each enabled section — parity check (partner_a side).
        home = report["detailed"]["home"]
        common = report["detailed"]["common"]
        trips = report["detailed"]["trips"]
        expected_total_a = (
            home["total_partner_a"] + common["total_partner_a"] + trips["total_partner_a"]
        )
        assert sum(row["actual"] for row in split["rows"]) == pytest.approx(
            expected_total_a
        )

    def test_section_subset_only_sums_selected_sections(self, seeded_dir: Path):
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
        home_total_a = report["detailed"]["home"]["total_partner_a"]
        assert sum(row["actual"] for row in split["rows"]) == pytest.approx(
            home_total_a
        )

    def test_malformed_config_raises_with_month_context(self, seeded_dir: Path):
        from accounting import AccountingValidationError

        _write_split_config(
            seeded_dir,
            {
                "enabled": True,
                "shares": {"partner_a": 70.0, "partner_b": 40.0},
                "sections": ["home"],
            },
        )
        with pytest.raises(AccountingValidationError, match=MONTH):
            report_builder.build_report(MONTH)

    def test_unknown_section_on_disk_rejected_defensively(self, seeded_dir: Path):
        """API layer blocks unknown sections at write time; this proves the
        report-build-time re-validation also catches a hand-edited file."""
        from accounting import AccountingValidationError

        _write_split_config(
            seeded_dir,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "sections": ["not_a_real_section"],
            },
        )
        with pytest.raises(AccountingValidationError):
            report_builder.build_report(MONTH)

    def test_calculation_version_is_9(self, seeded_dir: Path):
        report = report_builder.build_report(MONTH)
        assert report["calculation_version"] == 9
