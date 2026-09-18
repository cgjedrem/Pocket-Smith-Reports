"""Unit tests — reports router (months, get, generate async, status, pdf)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from budget_api.models.reports import PairedReimbursementRow, ReportResponse
from budget_api.services import report_builder, storage

# --------------------------------------------------------------------------- #
# Mock data helpers.
# --------------------------------------------------------------------------- #


def _mock_report() -> dict:
    """Minimal valid report dict matching ReportResponse shape."""
    return {
        "month": "2026-07",
        "contract_version": report_builder.CONTRACT_VERSION,
        "calculation_version": report_builder.CALCULATION_VERSION,
        "txn_count": 2,
        "normalized_transactions": [],
        "categories": [],
        "reconciliation": {"source": 0, "report": 0, "difference": 0},
        "detailed_section_mapping": None,
        "kpis": None,
        "root_totals": {"paid": 0, "received": 0, "net": 0, "count": 0},
        "owner_totals": {
            "partner_a": {"paid": 0, "received": 0, "net": 0},
            "partner_b": {"paid": 0, "received": 0, "net": 0},
        },
        "partner_panels": {
            "partner_a": {
                "label": "Fixture A",
                "paid": 0,
                "received": 0,
                "net": 0,
                "net_class": "pos",
            },
            "partner_b": {
                "label": "Fixture B",
                "paid": 0,
                "received": 0,
                "net": 0,
                "net_class": "pos",
            },
        },
        "partner_labels": {"partner_a": "Fixture A", "partner_b": "Fixture B"},
    }


@pytest.fixture
def seeded_ps_raw(tmp_private_dir: Path) -> Path:
    """Seed ps_raw file for 2026-07."""
    (tmp_private_dir / "2026-07_ps_raw.json").write_text(
        json.dumps([{"id": 1}, {"id": 2}]), encoding="utf-8"
    )
    return tmp_private_dir


# --------------------------------------------------------------------------- #
# GET /api/reports/months
# --------------------------------------------------------------------------- #


class TestMonths:
    def test_months_with_data(self, client, seeded_ps_raw):
        """AC1: months synced → 200, sorted descending."""
        # Add another month.
        (tmp_private_dir := storage.PRIVATE_DATA_DIR)
        (tmp_private_dir / "2026-06_ps_raw.json").write_text("[]", encoding="utf-8")
        resp = client.get("/api/reports/months")
        assert resp.status_code == 200
        months = resp.json()["months"]
        assert months == ["2026-07", "2026-06"]

    def test_months_empty(self, client, tmp_private_dir):
        """AC2: no sync → 200, empty list."""
        resp = client.get("/api/reports/months")
        assert resp.status_code == 200
        assert resp.json() == {"months": []}


# --------------------------------------------------------------------------- #
# GET /api/reports/monthly/{month}
# --------------------------------------------------------------------------- #


class TestGetMonthly:
    def test_not_generated_404(self, client, seeded_ps_raw):
        """AC3: no report JSON → 404."""
        resp = client.get("/api/reports/monthly/2026-07")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "no report generated yet"

    def test_generated_not_stale(self, client, seeded_ps_raw):
        """AC4: report exists, txn count matches → 200, stale=false."""
        report_builder.write_report("2026-07", _mock_report())
        resp = client.get("/api/reports/monthly/2026-07")
        assert resp.status_code == 200
        body = resp.json()
        assert body["stale"] is False
        assert body["month"] == "2026-07"

    def test_generated_stale(self, client, seeded_ps_raw):
        """AC5: report exists, txn count mismatch → 200, stale=true."""
        report = _mock_report()
        report["txn_count"] = 99  # mismatch with ps_raw (2 txns)
        report_builder.write_report("2026-07", report)
        resp = client.get("/api/reports/monthly/2026-07")
        assert resp.status_code == 200
        assert resp.json()["stale"] is True

    def test_invalid_month_400(self, client):
        """AC6: invalid format → 400."""
        resp = client.get("/api/reports/monthly/invalid")
        assert resp.status_code == 400
        assert resp.json()["detail"] == "invalid month format"


# --------------------------------------------------------------------------- #
# POST /api/reports/monthly/{month}/generate
# --------------------------------------------------------------------------- #


class TestGenerate:
    def test_generate_202(self, client, seeded_ps_raw, monkeypatch):
        """AC7: POST generate → 202, status=generating."""
        # Mock build_report to avoid full pipeline.
        monkeypatch.setattr(
            report_builder, "build_report", lambda month: _mock_report()
        )
        resp = client.post("/api/reports/monthly/2026-07/generate")
        assert resp.status_code == 202
        assert resp.json()["status"] == "generating"

    def test_generate_already_running_202(self, client, seeded_ps_raw, monkeypatch):
        """AC8: already generating → 202, no new generation."""
        # Pre-set generating status.
        report_builder.write_status(
            "2026-07",
            {
                "status": "generating",
                "errors": [],
                "started_at": "t1",
                "completed_at": None,
            },
        )
        # Add to _generating_months set.
        from budget_api.routers import reports as reports_mod

        reports_mod._generating_months.add("2026-07")
        call_count = {"n": 0}
        monkeypatch.setattr(
            report_builder,
            "build_report",
            lambda month: call_count.__setitem__("n", call_count["n"] + 1)
            or _mock_report(),
        )
        resp = client.post("/api/reports/monthly/2026-07/generate")
        assert resp.status_code == 202
        # build_report NOT called — concurrent guard.
        assert call_count["n"] == 0
        # Cleanup.
        reports_mod._generating_months.discard("2026-07")

    def test_generate_no_ps_raw_404(self, client, tmp_private_dir):
        """AC9: no ps_raw → 404."""
        resp = client.post("/api/reports/monthly/2026-07/generate")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "no data for this month"

    def test_generate_invalid_month_400(self, client):
        """Invalid month → 400."""
        resp = client.post("/api/reports/monthly/invalid/generate")
        assert resp.status_code == 400


# --------------------------------------------------------------------------- #
# GET /api/reports/monthly/{month}/status
# --------------------------------------------------------------------------- #


class TestStatus:
    def test_never_generated_404(self, client, tmp_private_dir):
        """AC10: no status file → 404."""
        resp = client.get("/api/reports/monthly/2026-07/status")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "no generation has been run yet"

    def test_status_generating(self, client, tmp_private_dir):
        """AC11: status=generating → 200."""
        report_builder.write_status(
            "2026-07",
            {
                "status": "generating",
                "errors": [],
                "started_at": "t1",
                "completed_at": None,
            },
        )
        resp = client.get("/api/reports/monthly/2026-07/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "generating"

    def test_status_success(self, client, tmp_private_dir):
        """AC12: status=success → 200."""
        report_builder.write_status(
            "2026-07",
            {
                "status": "success",
                "errors": [],
                "started_at": "t1",
                "completed_at": "t2",
            },
        )
        resp = client.get("/api/reports/monthly/2026-07/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_status_failed(self, client, tmp_private_dir):
        """AC13: status=failed → 200, errors populated."""
        report_builder.write_status(
            "2026-07",
            {
                "status": "failed",
                "errors": ["pipeline error"],
                "started_at": "t1",
                "completed_at": "t2",
            },
        )
        resp = client.get("/api/reports/monthly/2026-07/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"
        assert "pipeline error" in body["errors"]

    def test_status_invalid_month_400(self, client):
        """Invalid month → 400."""
        resp = client.get("/api/reports/monthly/invalid/status")
        assert resp.status_code == 400


# --------------------------------------------------------------------------- #
# POST /api/reports/monthly/{month}/pdf
# --------------------------------------------------------------------------- #


class TestPdf:
    def test_pdf_not_generated_404(self, client, seeded_ps_raw):
        """AC15: no report → 404."""
        resp = client.post("/api/reports/monthly/2026-07/pdf")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "no report generated yet"

    def test_pdf_invalid_month_400(self, client):
        """Invalid month → 400."""
        resp = client.post("/api/reports/monthly/invalid/pdf")
        assert resp.status_code == 400

    def test_pdf_success(self, client, seeded_ps_raw, monkeypatch):
        """AC14: report exists → 200, application/pdf, Content-Disposition."""
        report_builder.write_report("2026-07", _mock_report())
        # Mock generate_pdf — avoid WeasyPrint dependency in tests.
        monkeypatch.setattr(
            "budget_api.routers.reports.report_pdf.generate_pdf",
            lambda month: b"%PDF-1.4 fake pdf bytes",
        )
        resp = client.post("/api/reports/monthly/2026-07/pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "monthly_report_2026-07.pdf" in resp.headers["content-disposition"]
        assert resp.content.startswith(b"%PDF-")

    def test_pdf_generation_failed_500(self, client, seeded_ps_raw, monkeypatch):
        """WeasyPrint error → 500."""
        report_builder.write_report("2026-07", _mock_report())
        monkeypatch.setattr(
            "budget_api.routers.reports.report_pdf.generate_pdf",
            lambda month: (_ for _ in ()).throw(RuntimeError("weasyprint failed")),
        )
        resp = client.post("/api/reports/monthly/2026-07/pdf")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "PDF generation failed"


# --------------------------------------------------------------------------- #
# ReportResponse model compat — stored reports from older layers.
# --------------------------------------------------------------------------- #


class TestReportResponseCompat:
    def test_pr4_era_report_without_normalized_transactions_validates(self):
        """PR4-era stored reports (field dropped) still load → default [],
        so GET renders instead of 500ing before Regenerate is reachable."""
        report = _mock_report()
        del report["normalized_transactions"]
        report["stale"] = False
        validated = ReportResponse.model_validate(report)
        assert validated.normalized_transactions == []

    def test_pre_numeric_paired_row_defaults_partner_fields(self):
        """PR2-era paired rows (partner_a_display strings, no signed
        numerics) validate with defaults instead of 500ing — the report is
        stale (calculation_version) and regenerates on user action."""
        row = PairedReimbursementRow.model_validate(
            {
                "category_title": "Home",
                "partner_a_display": "+45.00",
                "partner_b_display": "-45.00",
                "total": 0.0,
                "total_class": "zero",
            }
        )
        assert row.partner_a == 0.0
        assert row.partner_a_class == "zero"
        assert row.partner_b == 0.0
        assert row.partner_b_class == "zero"
