"""Unit tests — report_builder derived views, stale check, status transitions."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from budget_api.services import report_builder, storage

# --------------------------------------------------------------------------- #
# Test data — mock transactions matching ps_raw shape.
# --------------------------------------------------------------------------- #


def _mock_transactions() -> list[dict]:
    """Two txns — partner_a grocery, partner_b grocery."""
    return [
        {
            "id": 100001,
            "date": "2026-07-03",
            "amount": -450.50,
            "payee": "Rema 1000",
            "note": "Weekly shop",
            "is_transfer": False,
            "account": {"id": "1100001", "name": "FxA Check Nordic Bank"},
            "category": {"id": 2100005, "title": "Supermarket", "parent_id": 2100003},
            "category_hierarchy": [
                {"id": "2100003", "title": "Groceries"},
                {"id": "2100005", "title": "Supermarket"},
            ],
        },
        {
            "id": 100002,
            "date": "2026-07-10",
            "amount": -320.00,
            "payee": "Kiwi",
            "note": None,
            "is_transfer": False,
            "account": {"id": "1100007", "name": "FxB Check Nordic Bank"},
            "category": {"id": 2100005, "title": "Supermarket", "parent_id": 2100003},
            "category_hierarchy": [
                {"id": "2100003", "title": "Groceries"},
                {"id": "2100005", "title": "Supermarket"},
            ],
        },
    ]


def _mock_account_mappings() -> dict:
    """Unified account mapping — partner_id schema (budget_api format)."""
    return {
        "schema_version": 1,
        "partners": {
            "partner_a": {"label": "Fixture A"},
            "partner_b": {"label": "Fixture B"},
        },
        "accounts": {
            "1100001": {
                "name": "FxA Check Nordic Bank",
                "partner_id": "partner_a",
                "type": "checking",
                "excluded": False,
            },
            "1100007": {
                "name": "FxB Check Nordic Bank",
                "partner_id": "partner_b",
                "type": "checking",
                "excluded": False,
            },
        },
    }


def _mock_detailed_section_mapping() -> dict:
    return {
        "account_roles": {},
        "category_sections": {
            "2100003": "common",
            "2100005": "common",
        },
    }


def _mock_category_roles() -> dict:
    return {
        "2100003": "spend",
        "2100005": "spend",
    }


def _mock_category_catalog() -> dict:
    return {
        "start": "2026-07",
        "end": "2026-07",
        "categories": [
            {
                "id": 2100003,
                "title": "Groceries",
                "parent_id": None,
                "children": [
                    {
                        "id": 2100005,
                        "title": "Supermarket",
                        "parent_id": 2100003,
                        "children": [],
                    },
                ],
            },
        ],
    }


@pytest.fixture
def seeded_private_dir(tmp_private_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Seed tmp private dir with all config files + ps_raw."""
    # account_mappings.json
    (tmp_private_dir / "account_mappings.json").write_text(
        json.dumps(_mock_account_mappings()), encoding="utf-8"
    )
    # detailed_section_mapping.json
    (tmp_private_dir / "detailed_section_mapping.json").write_text(
        json.dumps(_mock_detailed_section_mapping()), encoding="utf-8"
    )
    # category_roles.json
    (tmp_private_dir / "category_roles.json").write_text(
        json.dumps(_mock_category_roles()), encoding="utf-8"
    )
    # category_catalog.json
    (tmp_private_dir / "category_catalog.json").write_text(
        json.dumps(_mock_category_catalog()), encoding="utf-8"
    )
    # partner_labels.json — fallback if account_mappings missing.
    (tmp_private_dir / "partner_labels.json").write_text(
        json.dumps({"partner_a": "Fixture A", "partner_b": "Fixture B"}),
        encoding="utf-8",
    )
    # ps_raw — dict format with "transactions" key (data_loader expects this).
    (tmp_private_dir / "2026-07_ps_raw.json").write_text(
        json.dumps({"transactions": _mock_transactions()}), encoding="utf-8"
    )
    return tmp_private_dir


# --------------------------------------------------------------------------- #
# Derived view tests — pure data logic.
# --------------------------------------------------------------------------- #


class TestDerivedViews:
    def test_root_totals(self):
        categories = [
            {
                "id": "1",
                "title": "Root",
                "parent_id": None,
                "paid": 100.0,
                "received": 50.0,
                "net": 50.0,
                "count": 3,
            },
            {
                "id": "2",
                "title": "Child",
                "parent_id": "1",
                "paid": 20.0,
                "received": 0.0,
                "net": -20.0,
                "count": 1,
            },
        ]
        totals = report_builder._root_totals(categories)
        assert totals["paid"] == 100.0
        assert totals["received"] == 50.0
        assert totals["net"] == 50.0
        assert totals["count"] == 3

    def test_owner_totals(self):
        categories = [
            {
                "id": "1",
                "title": "Root",
                "parent_id": None,
                "owners": {
                    "partner_a": {"paid": 100.0, "received": 0.0, "net": -100.0},
                    "partner_b": {"paid": 50.0, "received": 10.0, "net": -40.0},
                },
            },
        ]
        totals = report_builder._owner_totals(categories)
        assert totals["partner_a"]["paid"] == 100.0
        assert totals["partner_b"]["paid"] == 50.0
        assert totals["partner_b"]["received"] == 10.0

    def test_partner_panels(self):
        owner_totals = {
            "partner_a": {"paid": 100.0, "received": 50.0, "net": -50.0},
            "partner_b": {"paid": 30.0, "received": 40.0, "net": 10.0},
        }
        labels = {"partner_a": "Fixture A", "partner_b": "Fixture B"}
        panels = report_builder._partner_panels(owner_totals, labels)
        assert panels["partner_a"]["label"] == "Fixture A"
        assert panels["partner_a"]["net_class"] == "neg"
        assert panels["partner_b"]["net_class"] == "pos"


# --------------------------------------------------------------------------- #
# Build report — integration with mock data.
# --------------------------------------------------------------------------- #


class TestBuildReport:
    def test_build_report_success(self, seeded_private_dir):
        """build_report returns full contract + derived views."""
        report = report_builder.build_report("2026-07")
        assert report["month"] == "2026-07"
        assert report["calculation_version"] == report_builder.CALCULATION_VERSION
        assert report["txn_count"] == 2
        assert "root_totals" in report
        assert "owner_totals" in report
        assert "partner_panels" in report
        assert "detailed" in report
        assert "personal_share" in report
        assert "balanced" in report
        assert report["savings_summary"]["total"]["net_saved"] == 0.0
        assert report["partner_labels"]["partner_a"] == "Fixture A"

    def test_build_report_no_data(self, tmp_private_dir):
        """build_report raises FileNotFoundError if no ps_raw."""
        with pytest.raises(FileNotFoundError):
            report_builder.build_report("2026-07")


# --------------------------------------------------------------------------- #
# Stale check.
# --------------------------------------------------------------------------- #


class TestStaleCheck:
    def test_not_stale_with_current_calculation_version(self, tmp_private_dir):
        """Current calculation version + matching txn count is fresh."""
        (tmp_private_dir / "2026-07_ps_raw.json").write_text(
            json.dumps([{"id": 1}, {"id": 2}]), encoding="utf-8"
        )
        report = {
            "calculation_version": report_builder.CALCULATION_VERSION,
            "txn_count": 2,
        }
        assert report_builder.check_stale("2026-07", report) is False

    @pytest.mark.parametrize("calculation_version", [None, 1, 2, 3, 5])
    def test_stale_with_missing_or_old_calculation_version(
        self, tmp_private_dir, calculation_version
    ):
        """Same transaction count cannot reuse older savings KPI semantics."""
        (tmp_private_dir / "2026-07_ps_raw.json").write_text(
            json.dumps([{"id": 1}, {"id": 2}]), encoding="utf-8"
        )
        report = {"txn_count": 2}
        if calculation_version is not None:
            report["calculation_version"] = calculation_version
        assert report_builder.check_stale("2026-07", report) is True

    def test_stale_count_mismatch(self, tmp_private_dir):
        """txn_count != ps_raw count → stale."""
        (tmp_private_dir / "2026-07_ps_raw.json").write_text(
            json.dumps([{"id": 1}, {"id": 2}, {"id": 3}]), encoding="utf-8"
        )
        report = {
            "calculation_version": report_builder.CALCULATION_VERSION,
            "txn_count": 2,
        }
        assert report_builder.check_stale("2026-07", report) is True

    def test_stale_no_ps_raw(self, tmp_private_dir):
        """No ps_raw → stale."""
        report = {
            "calculation_version": report_builder.CALCULATION_VERSION,
            "txn_count": 2,
        }
        assert report_builder.check_stale("2026-07", report) is True


# --------------------------------------------------------------------------- #
# Status transitions — write/read status.
# --------------------------------------------------------------------------- #


class TestStatusTransitions:
    def test_write_read_status(self, tmp_private_dir):
        """write_status → read_status roundtrip."""
        status = {
            "status": "generating",
            "errors": [],
            "started_at": "2026-07-28T00:00:00Z",
            "completed_at": None,
        }
        report_builder.write_status("2026-07", status)
        read = report_builder.read_status("2026-07")
        assert read == status

    def test_read_status_missing(self, tmp_private_dir):
        """read_status returns None if no file."""
        assert report_builder.read_status("2026-07") is None

    def test_status_success_transition(self, tmp_private_dir):
        """generating → success transition."""
        report_builder.write_status(
            "2026-07",
            {
                "status": "generating",
                "errors": [],
                "started_at": "t1",
                "completed_at": None,
            },
        )
        report_builder.write_status(
            "2026-07",
            {
                "status": "success",
                "errors": [],
                "started_at": "t1",
                "completed_at": "t2",
            },
        )
        assert report_builder.read_status("2026-07")["status"] == "success"

    def test_status_failed_transition(self, tmp_private_dir):
        """generating → failed transition with errors."""
        report_builder.write_status(
            "2026-07",
            {
                "status": "failed",
                "errors": ["pipeline error"],
                "started_at": "t1",
                "completed_at": "t2",
            },
        )
        status = report_builder.read_status("2026-07")
        assert status["status"] == "failed"
        assert "pipeline error" in status["errors"]


# --------------------------------------------------------------------------- #
# list_months — scan ps_raw files.
# --------------------------------------------------------------------------- #


class TestListMonths:
    def test_list_months_sorted_desc(self, tmp_private_dir):
        """Months sorted descending."""
        for month in ("2026-05", "2026-07", "2026-06"):
            (tmp_private_dir / f"{month}_ps_raw.json").write_text(
                "[]", encoding="utf-8"
            )
        months = report_builder.list_months()
        assert months == ["2026-07", "2026-06", "2026-05"]

    def test_list_months_empty(self, tmp_private_dir):
        """No ps_raw files → empty list."""
        assert report_builder.list_months() == []

    def test_list_months_ignores_non_ps_raw(self, tmp_private_dir):
        """Only *_ps_raw.json files counted."""
        (tmp_private_dir / "2026-07_ps_raw.json").write_text("[]", encoding="utf-8")
        (tmp_private_dir / "events_2026-07.json").write_text("[]", encoding="utf-8")
        (tmp_private_dir / "category_catalog.json").write_text("{}", encoding="utf-8")
        months = report_builder.list_months()
        assert months == ["2026-07"]


# --------------------------------------------------------------------------- #
# Write/read report.
# --------------------------------------------------------------------------- #


class TestReportStorage:
    def test_write_read_report(self, tmp_private_dir):
        """write_report → read_report roundtrip."""
        report = {
            "month": "2026-07",
            "contract_version": report_builder.CONTRACT_VERSION,
            "calculation_version": report_builder.CALCULATION_VERSION,
            "txn_count": 5,
            "categories": [],
        }
        report_builder.write_report("2026-07", report)
        read = report_builder.read_report("2026-07")
        assert read == report

    def test_read_report_missing(self, tmp_private_dir):
        """read_report returns None if no file."""
        assert report_builder.read_report("2026-07") is None


class TestPartnerLabelRobustness:
    """Label configuration degrades visibly, never crashes the build."""

    def test_malformed_partner_labels_json_degrades_to_placeholders(
        self, seeded_private_dir
    ):
        """Unparseable partner_labels.json -> defaults + read-path warning."""
        (seeded_private_dir / "partner_labels.json").write_text(
            "{ not valid json", encoding="utf-8"
        )
        report = report_builder.build_report("2026-07")
        assert report["partner_labels"] == {
            "partner_a": "Partner A",
            "partner_b": "Partner B",
        }
        assert any("could not be parsed" in w for w in report["warnings"])

    def test_label_warnings_are_logged(self, seeded_private_dir, caplog):
        """Monthly builder logs validation warnings like mega/PDF builders."""
        import logging

        (seeded_private_dir / "partner_labels.json").write_text(
            json.dumps({"partner_a": "Shared", "partner_b": "Shared"}),
            encoding="utf-8",
        )
        with caplog.at_level(
            logging.WARNING, logger="budget_api.services.report_builder"
        ):
            report = report_builder.build_report("2026-07")
        assert any(
            "partner-label validation:" in record.getMessage()
            for record in caplog.records
        )
        assert report["warnings"]
