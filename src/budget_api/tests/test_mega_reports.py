"""Mega reports router unit tests — list, get, generate, status, pdf, validation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from budget_api.services import mega_builder, storage

from .test_mega_builder import _mock_mega_report


@pytest.fixture
def mega_router_seeded(tmp_private_dir: Path) -> Path:
    """Seed ps_raw + config for router tests."""
    from .test_mega_builder import _all_months

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


class TestListMegaReports:
    def test_list_empty(self, client, mega_router_seeded):
        """GET /mega-reports (none) → 200, empty list."""
        resp = client.get("/api/mega-reports")
        assert resp.status_code == 200
        assert resp.json() == {"reports": []}

    def test_list_with_reports(self, client, mega_router_seeded):
        """GET /mega-reports (reports generated) → 200, sorted newest first."""
        mega_builder.write_mega_report("2026-01", "2026-07", _mock_mega_report())
        mega_builder.write_mega_report(
            "2025-01", "2025-12", _mock_mega_report("2025-01", "2025-12")
        )
        resp = client.get("/api/mega-reports")
        assert resp.status_code == 200
        reports = resp.json()["reports"]
        assert len(reports) == 2
        assert reports[0] == {"start": "2026-01", "end": "2026-07"}
        assert reports[1] == {"start": "2025-01", "end": "2025-12"}


class TestGetMegaReport:
    def test_404_not_generated(self, client, mega_router_seeded):
        """GET /mega-reports/{start}/{end} (not generated) → 404."""
        resp = client.get("/api/mega-reports/2026-01/2026-07")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "no report generated yet"

    def test_200_not_stale(self, client, mega_router_seeded):
        """GET (generated, not stale) → 200, stale=false."""
        mega_builder.write_mega_report("2026-01", "2026-07", _mock_mega_report())
        resp = client.get("/api/mega-reports/2026-01/2026-07")
        assert resp.status_code == 200
        assert resp.json()["stale"] is False

    def test_200_stale_version(self, client, mega_router_seeded):
        """GET (generated, stale version) → 200, stale=true."""
        report = _mock_mega_report()
        report["calculation_version"] = 999
        mega_builder.write_mega_report("2026-01", "2026-07", report)
        resp = client.get("/api/mega-reports/2026-01/2026-07")
        assert resp.status_code == 200
        assert resp.json()["stale"] is True

    def test_400_start_after_end(self, client, mega_router_seeded):
        """GET (start > end) → 400."""
        resp = client.get("/api/mega-reports/2026-07/2026-01")
        assert resp.status_code == 400
        assert resp.json()["detail"] == "start must be before or equal to end"

    def test_400_invalid_month_format(self, client, mega_router_seeded):
        """GET (invalid month) → 400."""
        resp = client.get("/api/mega-reports/invalid/2026-07")
        assert resp.status_code == 400
        assert resp.json()["detail"] == "invalid month format"

    def test_400_month_missing_ps_raw(self, client, mega_router_seeded):
        """GET (month missing ps_raw) → 400."""
        (storage.PRIVATE_DATA_DIR / "2026-07_ps_raw.json").unlink()
        resp = client.get("/api/mega-reports/2026-01/2026-07")
        assert resp.status_code == 400
        assert "has no data" in resp.json()["detail"]


class TestGenerateMegaReport:
    def test_202_generate_starts(self, client, mega_router_seeded):
        """POST /generate → 202, status=generating."""
        with patch(
            "budget_api.services.mega_builder.build_mega_report",
            return_value=_mock_mega_report(),
        ):
            resp = client.post("/api/mega-reports/2026-01/2026-07/generate")
        assert resp.status_code == 202
        assert resp.json()["status"] == "generating"

    def test_202_already_generating(self, client, mega_router_seeded):
        """POST /generate (already generating) → 202, current status."""
        from budget_api.routers import mega_reports

        mega_reports._generating_ranges.add(("2026-01", "2026-07"))
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
        try:
            resp = client.post("/api/mega-reports/2026-01/2026-07/generate")
            assert resp.status_code == 202
            assert resp.json()["status"] == "generating"
        finally:
            mega_reports._generating_ranges.discard(("2026-01", "2026-07"))

    def test_400_generate_month_missing(self, client, mega_router_seeded):
        """POST /generate (month missing) → 400."""
        (storage.PRIVATE_DATA_DIR / "2026-07_ps_raw.json").unlink()
        resp = client.post("/api/mega-reports/2026-01/2026-07/generate")
        assert resp.status_code == 400
        assert "has no data" in resp.json()["detail"]

    def test_400_generate_start_after_end(self, client, mega_router_seeded):
        """POST /generate (start > end) → 400."""
        resp = client.post("/api/mega-reports/2026-07/2026-01/generate")
        assert resp.status_code == 400
        assert resp.json()["detail"] == "start must be before or equal to end"


class TestGenerateStatus:
    def test_404_never_generated(self, client, mega_router_seeded):
        """GET /status (never generated) → 404."""
        resp = client.get("/api/mega-reports/2026-01/2026-07/status")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "no generation has been run yet"

    def test_200_generating(self, client, mega_router_seeded):
        """GET /status (generating) → 200."""
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
        resp = client.get("/api/mega-reports/2026-01/2026-07/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "generating"

    def test_200_success(self, client, mega_router_seeded):
        """GET /status (success) → 200."""
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
        resp = client.get("/api/mega-reports/2026-01/2026-07/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_200_failed_with_errors(self, client, mega_router_seeded):
        """GET /status (failed) → 200, errors populated."""
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
        resp = client.get("/api/mega-reports/2026-01/2026-07/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"
        assert resp.json()["errors"] == ["boom"]


class TestExportPdf:
    def test_200_pdf_generated(self, client, mega_router_seeded):
        """POST /pdf (generated) → 200, application/pdf."""
        mega_builder.write_mega_report("2026-01", "2026-07", _mock_mega_report())
        with patch(
            "budget_api.services.mega_pdf.generate_pdf", return_value=b"%PDF-1.4 fake"
        ):
            resp = client.post("/api/mega-reports/2026-01/2026-07/pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "mega_report_2026-01_2026-07.pdf" in resp.headers["content-disposition"]

    def test_404_pdf_not_generated(self, client, mega_router_seeded):
        """POST /pdf (not generated) → 404."""
        resp = client.post("/api/mega-reports/2026-01/2026-07/pdf")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "no report generated yet"

    def test_500_pdf_generation_fails(self, client, mega_router_seeded):
        """POST /pdf (WeasyPrint fails) → 500."""
        mega_builder.write_mega_report("2026-01", "2026-07", _mock_mega_report())
        with patch(
            "budget_api.services.mega_pdf.generate_pdf",
            side_effect=RuntimeError("boom"),
        ):
            resp = client.post("/api/mega-reports/2026-01/2026-07/pdf")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "PDF generation failed"
