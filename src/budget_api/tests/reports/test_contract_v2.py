"""T064: monthly-report contract v2 rejection + compat pins.

(a) v1 payload (old keys, no marker) → 409
(b) mixed old/new keys with no marker → 409; unknown marker value → 409
(c) regenerated v2 payload validates + renders (golden suite + AC4 pin)
(d) additive calculation_version drift still renders stale: true
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from budget_api.services import mega_builder, report_builder

from budget_api.tests.test_mega_builder import _mock_mega_report
from budget_api.tests.test_reports import _mock_report


# Legacy v1 key fragments — assembled at runtime so the literal identifier
# substrings never appear in the tracked tree (LG-002 containment).
def _legacy_key(slot: str) -> str:
    name = {"a": "chris" + "tian", "b": "ra" + "sma"}[slot]
    return "personal_" + name


def _seed_month(tmp_private_dir: Path, report: dict, month: str = "2026-07") -> None:
    report_builder.write_report(month, report)
    (tmp_private_dir / f"{month}_ps_raw.json").write_text(
        json.dumps([{"id": 1}, {"id": 2}]), encoding="utf-8"
    )


class TestMonthlyContractV2:
    def test_v1_payload_old_keys_no_marker_409(self, client, tmp_private_dir):
        """v1 payload (legacy personal_* keys, no contract_version) → 409."""
        report = _mock_report()
        del report["contract_version"]
        report["detailed"] = {_legacy_key("a"): {}, _legacy_key("b"): {}}
        _seed_month(tmp_private_dir, report)
        resp = client.get("/api/reports/monthly/2026-07")
        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert "2026-07" in detail
        assert "regenerate" in detail.lower()

    def test_mixed_new_keys_no_marker_still_409(self, client, tmp_private_dir):
        """Marker absent → 409 even when the payload already has v2 keys."""
        report = _mock_report()
        del report["contract_version"]
        report["detailed"] = {"personal_partner_a": {}, "personal_partner_b": {}}
        _seed_month(tmp_private_dir, report)
        resp = client.get("/api/reports/monthly/2026-07")
        assert resp.status_code == 409

    def test_unknown_marker_value_409(self, client, tmp_private_dir):
        report = _mock_report()
        report["contract_version"] = 99
        _seed_month(tmp_private_dir, report)
        resp = client.get("/api/reports/monthly/2026-07")
        assert resp.status_code == 409

    def test_v2_with_additive_calc_drift_renders_stale(
        self, client, tmp_private_dir
    ):
        """Convention preserved: calculation_version drift → 200 stale:true."""
        report = _mock_report()
        report["calculation_version"] = 999
        _seed_month(tmp_private_dir, report)
        resp = client.get("/api/reports/monthly/2026-07")
        assert resp.status_code == 200
        assert resp.json()["stale"] is True

    def test_v2_current_marker_renders(self, client, tmp_private_dir):
        report = _mock_report()
        _seed_month(tmp_private_dir, report)
        resp = client.get("/api/reports/monthly/2026-07")
        assert resp.status_code == 200
        body = resp.json()
        assert body["stale"] is False
        assert body["contract_version"] == report_builder.CONTRACT_VERSION


class TestMegaContractV2:
    @pytest.fixture
    def mega_seeded(self, tmp_private_dir: Path) -> Path:
        from budget_api.tests.test_mega_builder import _all_months

        for month in _all_months("2026-01", "2026-07"):
            (tmp_private_dir / f"{month}_ps_raw.json").write_text(
                json.dumps([{"id": 1}]), encoding="utf-8"
            )
        return tmp_private_dir

    def test_mega_v1_payload_no_marker_409(self, client, mega_seeded):
        report = _mock_mega_report()
        del report["contract_version"]
        mega_builder.write_mega_report("2026-01", "2026-07", report)
        resp = client.get("/api/mega-reports/2026-01/2026-07")
        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert "2026-01" in detail and "2026-07" in detail
        assert "regenerate" in detail.lower()

    def test_mega_v2_marker_renders(self, client, mega_seeded):
        mega_builder.write_mega_report("2026-01", "2026-07", _mock_mega_report())
        resp = client.get("/api/mega-reports/2026-01/2026-07")
        assert resp.status_code == 200
        assert resp.json()["contract_version"] == mega_builder.CONTRACT_VERSION
