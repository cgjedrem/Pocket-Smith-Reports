"""F1.3 acceptance tests — AC1-AC18 (backend mega reports)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from budget_api.services import mega_builder, storage

from .test_mega_builder import _mock_mega_report


@pytest.fixture
def mega_acceptance_seeded(tmp_private_dir: Path) -> Path:
    """Seed ps_raw + config for acceptance tests."""
    for month in (
        "2026-01",
        "2026-02",
        "2026-03",
        "2026-04",
        "2026-05",
        "2026-06",
        "2026-07",
    ):
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


class TestMegaReportAcceptance:
    """AC1-AC18 — backend mega report acceptance criteria."""

    def test_ac1_list_with_reports(self, client, mega_acceptance_seeded):
        """AC1: GET /api/mega-reports (reports generated) → 200, sorted newest first."""
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

    def test_ac2_list_empty(self, client, mega_acceptance_seeded):
        """AC2: GET /api/mega-reports (none) → 200, {"reports": []}."""
        resp = client.get("/api/mega-reports")
        assert resp.status_code == 200
        assert resp.json() == {"reports": []}

    def test_ac3_get_not_generated_404(self, client, mega_acceptance_seeded):
        """AC3: GET /mega-reports/2026-01/2026-07 (not generated) → 404."""
        resp = client.get("/api/mega-reports/2026-01/2026-07")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "no report generated yet"

    def test_ac4_get_generated_not_stale(self, client, mega_acceptance_seeded):
        """AC4: GET (generated, not stale) → 200, stale=false."""
        mega_builder.write_mega_report("2026-01", "2026-07", _mock_mega_report())
        resp = client.get("/api/mega-reports/2026-01/2026-07")
        assert resp.status_code == 200
        assert resp.json()["stale"] is False

    def test_ac5_get_generated_stale(self, client, mega_acceptance_seeded):
        """AC5: GET (generated, stale) → 200, stale=true."""
        report = _mock_mega_report()
        report["calculation_version"] = 999
        mega_builder.write_mega_report("2026-01", "2026-07", report)
        resp = client.get("/api/mega-reports/2026-01/2026-07")
        assert resp.status_code == 200
        assert resp.json()["stale"] is True

    def test_ac6_get_start_after_end_400(self, client, mega_acceptance_seeded):
        """AC6: GET /mega-reports/2026-07/2026-01 (start > end) → 400."""
        resp = client.get("/api/mega-reports/2026-07/2026-01")
        assert resp.status_code == 400
        assert resp.json()["detail"] == "start must be before or equal to end"

    def test_ac7_get_invalid_month_400(self, client, mega_acceptance_seeded):
        """AC7: GET /mega-reports/invalid/2026-07 → 400, invalid month format."""
        resp = client.get("/api/mega-reports/invalid/2026-07")
        assert resp.status_code == 400
        assert resp.json()["detail"] == "invalid month format"

    def test_ac8_get_month_missing_400(self, client, mega_acceptance_seeded):
        """AC8: GET (month missing ps_raw) → 400, sync it first."""
        (storage.PRIVATE_DATA_DIR / "2026-07_ps_raw.json").unlink()
        resp = client.get("/api/mega-reports/2026-01/2026-07")
        assert resp.status_code == 400
        assert "has no data" in resp.json()["detail"]

    def test_ac9_generate_202(self, client, mega_acceptance_seeded):
        """AC9: POST /generate → 202, status=generating."""
        with patch(
            "budget_api.services.mega_builder.build_mega_report",
            return_value=_mock_mega_report(),
        ):
            resp = client.post("/api/mega-reports/2026-01/2026-07/generate")
        assert resp.status_code == 202
        assert resp.json()["status"] == "generating"

    def test_ac10_generate_already_generating_202(self, client, mega_acceptance_seeded):
        """AC10: POST /generate (already generating) → 202, current status."""
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

    def test_ac11_generate_month_missing_400(self, client, mega_acceptance_seeded):
        """AC11: POST /generate (month missing) → 400."""
        (storage.PRIVATE_DATA_DIR / "2026-07_ps_raw.json").unlink()
        resp = client.post("/api/mega-reports/2026-01/2026-07/generate")
        assert resp.status_code == 400
        assert "has no data" in resp.json()["detail"]

    def test_ac12_status_never_generated_404(self, client, mega_acceptance_seeded):
        """AC12: GET /status (never generated) → 404."""
        resp = client.get("/api/mega-reports/2026-01/2026-07/status")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "no generation has been run yet"

    def test_ac13_status_generating_200(self, client, mega_acceptance_seeded):
        """AC13: GET /status (generating) → 200, status=generating."""
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

    def test_ac14_status_success_200(self, client, mega_acceptance_seeded):
        """AC14: GET /status (success) → 200, status=success."""
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

    def test_ac15_status_failed_200(self, client, mega_acceptance_seeded):
        """AC15: GET /status (failed) → 200, errors populated."""
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

    def test_ac16_pdf_generated_200(self, client, mega_acceptance_seeded):
        """AC16: POST /pdf (generated) → 200, application/pdf, Content-Disposition."""
        mega_builder.write_mega_report("2026-01", "2026-07", _mock_mega_report())
        with patch(
            "budget_api.services.mega_pdf.generate_pdf", return_value=b"%PDF-1.4 fake"
        ):
            resp = client.post("/api/mega-reports/2026-01/2026-07/pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "mega_report_2026-01_2026-07.pdf" in resp.headers["content-disposition"]

    def test_ac17_pdf_not_generated_404(self, client, mega_acceptance_seeded):
        """AC17: POST /pdf (not generated) → 404."""
        resp = client.post("/api/mega-reports/2026-01/2026-07/pdf")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "no report generated yet"

    def test_ac18_cli_standalone_import(self, mega_acceptance_seeded):
        """AC18: CLI standalone — build_mega import works without React.

        Verifies the mega CLI module is importable and build_context
        function exists. Full CLI run requires real data — not run here.
        """
        import sys

        # Ensure mega is importable.
        src_dir = str(Path(__file__).resolve().parents[2])
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        from mega.build_mega import build_context, assemble_html, main

        assert callable(build_context)
        assert callable(assemble_html)
        assert callable(main)
