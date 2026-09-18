"""Mega builder unit tests — detail_agg port, stale check, status, list, config bridging."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from budget_api.services import mega_builder, storage

# --------------------------------------------------------------------------- #
# Mock data — minimal valid mega report dict.
# --------------------------------------------------------------------------- #


def _all_months(start: str, end: str) -> list[str]:
    """Generate all YYYY-MM months in range inclusive."""
    from datetime import datetime

    first = datetime.strptime(start, "%Y-%m")
    last = datetime.strptime(end, "%Y-%m")
    months = []
    cur = first
    while cur <= last:
        months.append(cur.strftime("%Y-%m"))
        cur = datetime(cur.year + (cur.month == 12), cur.month % 12 + 1, 1)
    return months


def _mock_mega_report(start: str = "2026-01", end: str = "2026-07") -> dict:
    """Minimal valid mega report dict matching MegaReportResponse shape."""
    months = _all_months(start, end)
    return {
        "start": start,
        "end": end,
        "contract_version": mega_builder.CONTRACT_VERSION,
        "calculation_version": mega_builder.MEGA_CALCULATION_VERSION,
        "txn_counts": {m: 2 for m in months},
        "months": months,
        "partner_labels": {"partner_a": "Fixture A", "partner_b": "Fixture B"},
        "detail_agg": {
            "months": months,
            "cats": {},
            "paired_reimbs": [],
            "cc_paydowns": {},
            "excluded_transactions": {m: [] for m in months},
            "trips": [],
            "series": {
                "income": {
                    "partner_a": [0.0] * len(months),
                    "partner_b": [0.0] * len(months),
                    "total": [0.0] * len(months),
                },
                "savings": {
                    "net_partner_a": [0.0] * len(months),
                    "net_partner_b": [0.0] * len(months),
                    "total": [0.0] * len(months),
                    "investment_net_partner_a": [0.0] * len(months),
                    "investment_net_partner_b": [0.0] * len(months),
                    "investment_net_total": [0.0] * len(months),
                },
                "real_spend": {
                    "partner_a": [0.0] * len(months),
                    "partner_b": [0.0] * len(months),
                    "total": [0.0] * len(months),
                },
                "net_cash": {
                    "partner_a": [0.0] * len(months),
                    "partner_b": [0.0] * len(months),
                    "total": [0.0] * len(months),
                },
            },
            "cumulative": {
                "income": {"partner_a": 0.0, "partner_b": 0.0, "total": 0.0},
                "savings": {
                    "net_partner_a": 0.0,
                    "net_partner_b": 0.0,
                    "total": 0.0,
                    "investment_net_partner_a": 0.0,
                    "investment_net_partner_b": 0.0,
                    "investment_net_total": 0.0,
                },
                "real_spend": {"partner_a": 0.0, "partner_b": 0.0, "total": 0.0},
                "net_cash": {"partner_a": 0.0, "partner_b": 0.0, "total": 0.0},
            },
        },
        "salary_allocation": {"income": 0.0, "entries": [], "unavailable_reason": None},
        "recommendations": None,
        "monthly_kpi_pages": [
            {
                "month": m,
                "kpis": {
                    "partner_a": {
                        "income": 0.0,
                        "real_spend": 0.0,
                        "net_cash": 0.0,
                        "net_savings": 0.0,
                    },
                    "partner_b": {
                        "income": 0.0,
                        "real_spend": 0.0,
                        "net_cash": 0.0,
                        "net_savings": 0.0,
                    },
                    "total": {
                        "income": 0.0,
                        "real_spend": 0.0,
                        "net_cash": 0.0,
                        "net_savings": 0.0,
                    },
                },
            }
            for m in months
        ],
    }


def _mock_context(start: str = "2026-01", end: str = "2026-07") -> dict:
    """Mock build_context return — avoids full pipeline."""
    months = _all_months(start, end)
    return {
        "monthly_results": [
            (
                m,
                {
                    "contract": {"kpis": None, "normalized_transactions": []},
                    "partner_labels": {"partner_a": "Fixture A", "partner_b": "Fixture B"},
                },
            )
            for m in months
        ],
        "accounting": {
            "months": ["2026-01", "2026-07"],
            "categories": {},
            "reconciliation": {},
        },
        "detail_agg": _mock_mega_report(start, end)["detail_agg"],
        "appendix_transactions": {},
        "salary_allocation": {"income": 0.0, "entries": [], "unavailable_reason": None},
        "raw_transactions": {},
        "recommendations": None,
    }


@pytest.fixture
def mega_seeded(tmp_private_dir: Path) -> Path:
    """Seed ps_raw + config files for mega builder tests."""
    for month in _all_months("2026-01", "2026-07"):
        (tmp_private_dir / f"{month}_ps_raw.json").write_text(
            json.dumps([{"id": 1}, {"id": 2}]), encoding="utf-8"
        )
    (tmp_private_dir / "partner_labels.json").write_text(
        json.dumps({"partner_a": "Fixture A", "partner_b": "Fixture B"}), encoding="utf-8"
    )
    (tmp_private_dir / "account_mappings.json").write_text(
        json.dumps({"schema_version": 1, "partners": {}, "accounts": {}}),
        encoding="utf-8",
    )
    (tmp_private_dir / "detailed_section_mapping.json").write_text(
        json.dumps({"account_roles": {}, "category_sections": {}}), encoding="utf-8"
    )
    return tmp_private_dir


# --------------------------------------------------------------------------- #
# build_mega_report — detail_agg port + monthly_kpi_pages + txn_counts.
# --------------------------------------------------------------------------- #


class TestBuildMegaReport:
    def test_build_returns_correct_shape(self, mega_seeded):
        """build_mega_report returns dict matching MegaReportResponse fields."""
        with patch(
            "budget_api.services.mega_builder.build_context",
            return_value=_mock_context(),
        ):
            report = mega_builder.build_mega_report("2026-01", "2026-07")
        assert report["start"] == "2026-01"
        assert report["end"] == "2026-07"
        assert report["calculation_version"] == mega_builder.MEGA_CALCULATION_VERSION
        assert "detail_agg" in report
        assert "salary_allocation" in report
        assert "recommendations" in report
        assert "monthly_kpi_pages" in report
        assert "txn_counts" in report
        assert "partner_labels" in report
        assert "months" in report

    def test_build_txn_counts_per_month(self, mega_seeded):
        """txn_counts has per-month count from ps_raw."""
        with patch(
            "budget_api.services.mega_builder.build_context",
            return_value=_mock_context(),
        ):
            report = mega_builder.build_mega_report("2026-01", "2026-07")
        months = _all_months("2026-01", "2026-07")
        assert report["txn_counts"] == {m: 2 for m in months}

    def test_build_monthly_kpi_pages_fallback(self, mega_seeded):
        """monthly_kpi_pages falls back to agg series when no contract kpis."""
        with patch(
            "budget_api.services.mega_builder.build_context",
            return_value=_mock_context(),
        ):
            report = mega_builder.build_mega_report("2026-01", "2026-07")
        months = _all_months("2026-01", "2026-07")
        assert len(report["monthly_kpi_pages"]) == len(months)
        page = report["monthly_kpi_pages"][0]
        assert page["month"] == months[0]
        assert "partner_a" in page["kpis"]
        assert "partner_b" in page["kpis"]
        assert "total" in page["kpis"]
        assert "income" in page["kpis"]["partner_a"]
        assert "net_savings" in page["kpis"]["partner_a"]

    def test_build_raises_on_missing_month(self, mega_seeded):
        """build_mega_report raises ValueError if month missing ps_raw."""
        (storage.PRIVATE_DATA_DIR / "2026-07_ps_raw.json").unlink()
        with patch(
            "budget_api.services.mega_builder.build_context",
            return_value=_mock_context(),
        ):
            with pytest.raises(ValueError, match="month 2026-07 has no data"):
                mega_builder.build_mega_report("2026-01", "2026-07")


# --------------------------------------------------------------------------- #
# Stale check.
# --------------------------------------------------------------------------- #


class TestCheckMegaStale:
    def test_not_stale_when_version_and_counts_match(self, mega_seeded):
        """stale=false when version + txn_counts match ps_raw."""
        report = _mock_mega_report()
        assert mega_builder.check_mega_stale("2026-01", "2026-07", report) is False

    def test_stale_on_version_mismatch(self, mega_seeded):
        """stale=true when calculation_version differs."""
        report = _mock_mega_report()
        report["calculation_version"] = 999
        assert mega_builder.check_mega_stale("2026-01", "2026-07", report) is True

    def test_stale_on_txn_count_mismatch(self, mega_seeded):
        """stale=true when txn_count differs from ps_raw len."""
        report = _mock_mega_report()
        report["txn_counts"]["2026-01"] = 99
        assert mega_builder.check_mega_stale("2026-01", "2026-07", report) is True

    def test_stale_on_missing_ps_raw(self, mega_seeded):
        """stale=true when ps_raw file missing for a month."""
        (storage.PRIVATE_DATA_DIR / "2026-07_ps_raw.json").unlink()
        report = _mock_mega_report()
        assert mega_builder.check_mega_stale("2026-01", "2026-07", report) is True


# --------------------------------------------------------------------------- #
# Status transitions.
# --------------------------------------------------------------------------- #


class TestStatusTransitions:
    def test_write_and_read_status(self, mega_seeded):
        """write_mega_status + read_mega_status round-trip."""
        status = {
            "status": "generating",
            "errors": [],
            "started_at": "2026-01-01T00:00:00Z",
            "completed_at": None,
        }
        mega_builder.write_mega_status("2026-01", "2026-07", status)
        result = mega_builder.read_mega_status("2026-01", "2026-07")
        assert result == status

    def test_read_status_none_if_missing(self, mega_seeded):
        """read_mega_status returns None if no status file."""
        assert mega_builder.read_mega_status("2026-01", "2026-07") is None

    def test_status_success_transition(self, mega_seeded):
        """Status transitions generating → success."""
        mega_builder.write_mega_status(
            "2026-01",
            "2026-07",
            {
                "status": "generating",
                "errors": [],
                "started_at": "t1",
                "completed_at": None,
            },
        )
        mega_builder.write_mega_status(
            "2026-01",
            "2026-07",
            {
                "status": "success",
                "errors": [],
                "started_at": "t1",
                "completed_at": "t2",
            },
        )
        result = mega_builder.read_mega_status("2026-01", "2026-07")
        assert result["status"] == "success"
        assert result["started_at"] == "t1"
        assert result["completed_at"] == "t2"

    def test_status_failed_transition(self, mega_seeded):
        """Status transitions generating → failed with errors."""
        mega_builder.write_mega_status(
            "2026-01",
            "2026-07",
            {
                "status": "generating",
                "errors": [],
                "started_at": "t1",
                "completed_at": None,
            },
        )
        mega_builder.write_mega_status(
            "2026-01",
            "2026-07",
            {
                "status": "failed",
                "errors": ["boom"],
                "started_at": "t1",
                "completed_at": "t2",
            },
        )
        result = mega_builder.read_mega_status("2026-01", "2026-07")
        assert result["status"] == "failed"
        assert result["errors"] == ["boom"]


# --------------------------------------------------------------------------- #
# list_mega_reports — scan + sort.
# --------------------------------------------------------------------------- #


class TestListMegaReports:
    def test_empty_when_none(self, mega_seeded):
        """list_mega_reports returns [] when no mega report files."""
        assert mega_builder.list_mega_reports() == []

    def test_sorted_newest_first(self, mega_seeded):
        """list_mega_reports sorts by start desc, then end desc."""
        mega_builder.write_mega_report(
            "2026-01", "2026-06", _mock_mega_report("2026-01", "2026-06")
        )
        mega_builder.write_mega_report(
            "2026-01", "2026-07", _mock_mega_report("2026-01", "2026-07")
        )
        mega_builder.write_mega_report(
            "2025-01", "2025-12", _mock_mega_report("2025-01", "2025-12")
        )
        reports = mega_builder.list_mega_reports()
        assert len(reports) == 3
        assert reports[0] == {"start": "2026-01", "end": "2026-07"}
        assert reports[1] == {"start": "2026-01", "end": "2026-06"}
        assert reports[2] == {"start": "2025-01", "end": "2025-12"}


# --------------------------------------------------------------------------- #
# Config bridging — _build_namespace.
# --------------------------------------------------------------------------- #


class TestConfigBridging:
    def test_namespace_has_all_required_fields(self, mega_seeded):
        """_build_namespace returns Namespace with all build_context fields."""
        args = mega_builder._build_namespace("2026-01", "2026-07")
        try:
            assert args.start == "2026-01"
            assert args.end == "2026-07"
            assert args.input_kind == "live"
            assert args.theme == "minimal"
            assert args.only is None
            assert args.exclude_account_id == []
            assert args.savings_account_id is None
            assert hasattr(args, "data_dir")
            assert hasattr(args, "detailed_section_map")
            assert hasattr(args, "category_role_map")
            assert hasattr(args, "account_owner_map")
            assert hasattr(args, "category_catalog")
            assert hasattr(args, "partner_label_map")
            assert hasattr(args, "recommendations_artifact")
        finally:
            mega_builder._cleanup_namespace(args)

    def test_cleanup_removes_temp_owner_map(self, mega_seeded):
        """_cleanup_namespace removes temp account_owner_map file."""
        # Seed account_mappings with accounts so owners dict is non-empty.
        (storage.PRIVATE_DATA_DIR / "account_mappings.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "partners": {},
                    "accounts": {
                        "123": {
                            "name": "Test",
                            "partner_id": "partner_a",
                            "excluded": False,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        args = mega_builder._build_namespace("2026-01", "2026-07")
        tmp_path = getattr(args, "_owner_map_tmp", None)
        assert tmp_path is not None
        assert Path(tmp_path).exists()
        mega_builder._cleanup_namespace(args)
        assert not Path(tmp_path).exists()
