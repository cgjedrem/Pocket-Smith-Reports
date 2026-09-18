"""F1.2 acceptance tests — AC1-AC22 (backend report + category mappings)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from budget_api.services import report_builder, storage

# --------------------------------------------------------------------------- #
# Mock data — report dict + config files.
# --------------------------------------------------------------------------- #


def _mock_report() -> dict:
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


def _mock_catalog() -> dict:
    return {
        "start": "2026-07",
        "end": "2026-07",
        "categories": [
            {"id": 100, "title": "Groceries", "parent_id": None, "children": []},
            {"id": 200, "title": "Income", "parent_id": None, "children": []},
        ],
    }


@pytest.fixture
def f12_seeded(tmp_private_dir: Path) -> Path:
    """Seed ps_raw + catalog + roles + sections for F1.2 tests."""
    (tmp_private_dir / "2026-07_ps_raw.json").write_text(
        json.dumps([{"id": 1}, {"id": 2}]), encoding="utf-8"
    )
    (tmp_private_dir / "category_catalog.json").write_text(
        json.dumps(_mock_catalog()), encoding="utf-8"
    )
    (tmp_private_dir / "category_roles.json").write_text(
        json.dumps({"100": "spend"}), encoding="utf-8"
    )
    (tmp_private_dir / "detailed_section_mapping.json").write_text(
        json.dumps({"account_roles": {}, "category_sections": {"100": "common"}}),
        encoding="utf-8",
    )
    return tmp_private_dir


# --------------------------------------------------------------------------- #
# AC1-AC6 — Reports: months + get monthly.
# --------------------------------------------------------------------------- #


class TestReportAcceptance:
    def test_ac1_months_synced(self, client, f12_seeded):
        """AC1: GET /months (months synced) → 200, sorted descending."""
        (storage.PRIVATE_DATA_DIR / "2026-06_ps_raw.json").write_text(
            "[]", encoding="utf-8"
        )
        resp = client.get("/api/reports/months")
        assert resp.status_code == 200
        months = resp.json()["months"]
        assert months == ["2026-07", "2026-06"]

    def test_ac2_months_empty(self, client, tmp_private_dir):
        """AC2: GET /months (no sync) → 200, empty list."""
        resp = client.get("/api/reports/months")
        assert resp.status_code == 200
        assert resp.json() == {"months": []}

    def test_ac3_not_generated_404(self, client, f12_seeded):
        """AC3: GET /monthly/{month} (not generated) → 404."""
        resp = client.get("/api/reports/monthly/2026-07")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "no report generated yet"

    def test_ac4_generated_not_stale(self, client, f12_seeded):
        """AC4: GET /monthly/{month} (generated, not stale) → 200, stale=false."""
        report_builder.write_report("2026-07", _mock_report())
        resp = client.get("/api/reports/monthly/2026-07")
        assert resp.status_code == 200
        assert resp.json()["stale"] is False

    def test_ac5_generated_stale(self, client, f12_seeded):
        """AC5: GET /monthly/{month} (generated, stale) → 200, stale=true."""
        report = _mock_report()
        report["txn_count"] = 99
        report_builder.write_report("2026-07", report)
        resp = client.get("/api/reports/monthly/2026-07")
        assert resp.status_code == 200
        assert resp.json()["stale"] is True

    def test_ac6_invalid_month_400(self, client):
        """AC6: GET /monthly/invalid → 400."""
        resp = client.get("/api/reports/monthly/invalid")
        assert resp.status_code == 400
        assert resp.json()["detail"] == "invalid month format"


# --------------------------------------------------------------------------- #
# AC7-AC13 — Generate + status.
# --------------------------------------------------------------------------- #


class TestGenerateAcceptance:
    def test_ac7_generate_202(self, client, f12_seeded, monkeypatch):
        """AC7: POST /generate → 202, status=generating."""
        monkeypatch.setattr(report_builder, "build_report", lambda m: _mock_report())
        resp = client.post("/api/reports/monthly/2026-07/generate")
        assert resp.status_code == 202
        assert resp.json()["status"] == "generating"

    def test_ac8_already_generating_202(self, client, f12_seeded, monkeypatch):
        """AC8: POST /generate (already generating) → 202, no new generation."""
        report_builder.write_status(
            "2026-07",
            {
                "status": "generating",
                "errors": [],
                "started_at": "t1",
                "completed_at": None,
            },
        )
        from budget_api.routers import reports as reports_mod

        reports_mod._generating_months.add("2026-07")
        called = {"n": 0}
        monkeypatch.setattr(
            report_builder,
            "build_report",
            lambda m: called.__setitem__("n", called["n"] + 1) or _mock_report(),
        )
        resp = client.post("/api/reports/monthly/2026-07/generate")
        assert resp.status_code == 202
        assert called["n"] == 0
        reports_mod._generating_months.discard("2026-07")

    def test_ac9_no_ps_raw_404(self, client, tmp_private_dir):
        """AC9: POST /generate (no ps_raw) → 404."""
        resp = client.post("/api/reports/monthly/2026-07/generate")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "no data for this month"

    def test_ac10_status_never_404(self, client, f12_seeded):
        """AC10: GET /status (never generated) → 404."""
        resp = client.get("/api/reports/monthly/2026-07/status")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "no generation has been run yet"

    def test_ac11_status_generating(self, client, f12_seeded):
        """AC11: GET /status (generating) → 200."""
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

    def test_ac12_status_success(self, client, f12_seeded):
        """AC12: GET /status (success) → 200."""
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

    def test_ac13_status_failed(self, client, f12_seeded):
        """AC13: GET /status (failed) → 200, errors populated."""
        report_builder.write_status(
            "2026-07",
            {
                "status": "failed",
                "errors": ["error1"],
                "started_at": "t1",
                "completed_at": "t2",
            },
        )
        resp = client.get("/api/reports/monthly/2026-07/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"
        assert "error1" in body["errors"]


# --------------------------------------------------------------------------- #
# AC14-AC15 — PDF export.
# --------------------------------------------------------------------------- #


class TestPdfAcceptance:
    def test_ac14_pdf_generated(self, client, f12_seeded, monkeypatch):
        """AC14: POST /pdf (generated) → 200, application/pdf, Content-Disposition."""
        report_builder.write_report("2026-07", _mock_report())
        monkeypatch.setattr(
            "budget_api.routers.reports.report_pdf.generate_pdf",
            lambda m: b"%PDF-1.4 fake",
        )
        resp = client.post("/api/reports/monthly/2026-07/pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "monthly_report_2026-07.pdf" in resp.headers["content-disposition"]

    def test_ac15_pdf_not_generated_404(self, client, f12_seeded):
        """AC15: POST /pdf (not generated) → 404."""
        resp = client.post("/api/reports/monthly/2026-07/pdf")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "no report generated yet"


# --------------------------------------------------------------------------- #
# AC16-AC22 — Category mappings.
# --------------------------------------------------------------------------- #


class TestCategoryMappingsAcceptance:
    def test_ac16_list_with_data(self, client, f12_seeded):
        """AC16: GET /category-mappings (synced) → 200, list with titles + roles."""
        resp = client.get("/api/category-mappings")
        assert resp.status_code == 200
        cats = resp.json()["categories"]
        assert len(cats) == 2
        cat100 = next(c for c in cats if c["category_id"] == "100")
        assert cat100["category_title"] == "Groceries"
        assert cat100["kpi_role"] == "spend"
        assert cat100["detailed_section"] == "common"

    def test_ac17_no_categories_404(self, client, tmp_private_dir):
        """AC17: GET /category-mappings (no categories) → 404."""
        resp = client.get("/api/category-mappings")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "no categories — run sync first"

    def test_ac18_update_success(self, client, f12_seeded):
        """AC18: PUT valid → 200, updated mapping."""
        resp = client.put(
            "/api/category-mappings/100",
            json={"kpi_role": "income", "detailed_section": "income_salary"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["kpi_role"] == "income"
        assert body["detailed_section"] == "income_salary"

    def test_ac19_invalid_kpi_role_400(self, client, f12_seeded):
        """AC19: PUT invalid kpi_role → 400."""
        resp = client.put(
            "/api/category-mappings/100",
            json={"kpi_role": "invalid", "detailed_section": "common"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "invalid kpi_role"

    def test_ac20_invalid_section_400(self, client, f12_seeded):
        """AC20: PUT invalid detailed_section → 400."""
        resp = client.put(
            "/api/category-mappings/100",
            json={"kpi_role": "income", "detailed_section": "invalid"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "invalid detailed_section"

    def test_ac21_category_not_found_404(self, client, f12_seeded):
        """AC21: PUT nonexistent category → 404."""
        resp = client.put(
            "/api/category-mappings/999",
            json={"kpi_role": "income", "detailed_section": "income_salary"},
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "category not found"

    def test_ac22_generate_then_status_success(self, client, f12_seeded, monkeypatch):
        """AC22 (status transition): generate → background task → status=success."""
        monkeypatch.setattr(report_builder, "build_report", lambda m: _mock_report())
        resp = client.post("/api/reports/monthly/2026-07/generate")
        assert resp.status_code == 202
        # TestClient runs background tasks synchronously after response.
        status_resp = client.get("/api/reports/monthly/2026-07/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "success"
