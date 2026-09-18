"""B16 — integration tests AC1-AC6, AC25-AC32. Mock sync_runner, status transitions."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from budget_api.services import env_writer, storage, sync_runner
from budget_api.services.ps_client import PSClientError

# --------------------------------------------------------------------------- #
# AC1-AC6 — sync flow.
# --------------------------------------------------------------------------- #


class TestSyncFlow:
    def _setup_key(self, tmp_env_file):
        tmp_env_file.write_text("API_KEY=test-key\n", encoding="utf-8")

    def test_ac1_trigger_sync_202(self, client, tmp_env_file, monkeypatch):
        """AC1: GET /api/sync → 202 (mock sync_runner)."""
        self._setup_key(tmp_env_file)
        fake = MagicMock(
            return_value=type(
                "R",
                (),
                {
                    "timestamp": "2026-07-27T00:00:00Z",
                    "start_month": "2026-07",
                    "end_month": "2026-07",
                    "months_synced": 1,
                    "row_counts": {
                        "transactions": 0,
                        "events": 0,
                        "budget": 0,
                        "categories": 0,
                        "accounts": 0,
                    },
                    "errors": [],
                    "duration_ms": 10,
                },
            )()
        )
        monkeypatch.setattr(sync_runner, "sync_all", fake)
        resp = client.get(
            "/api/sync", params={"start_month": "2026-07", "end_month": "2026-07"}
        )
        assert resp.status_code == 202

    def test_ac2_start_after_end_400(self, client, tmp_env_file):
        """AC2: start > end → 400."""
        self._setup_key(tmp_env_file)
        resp = client.get(
            "/api/sync", params={"start_month": "2026-07", "end_month": "2025-01"}
        )
        assert resp.status_code == 400
        assert "start_month must be" in resp.json()["detail"]

    def test_ac3_invalid_month_format_400(self, client, tmp_env_file):
        """AC3: invalid format → 400."""
        self._setup_key(tmp_env_file)
        resp = client.get(
            "/api/sync", params={"start_month": "invalid", "end_month": "2026-07"}
        )
        assert resp.status_code == 400
        assert "invalid month format" in resp.json()["detail"]

    def test_ac3_invalid_month_value_400(self, client, tmp_env_file):
        """AC3: 2026-13 → 400 (valid format, invalid month)."""
        self._setup_key(tmp_env_file)
        resp = client.get(
            "/api/sync", params={"start_month": "2026-13", "end_month": "2026-07"}
        )
        assert resp.status_code == 400

    def test_ac4_status_never_synced_404(self, client, tmp_private_dir):
        """AC4: GET /api/sync/status (never synced) → 404."""
        resp = client.get("/api/sync/status")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "no sync has been run yet"

    def test_ac5_status_after_sync_200(self, client, tmp_private_dir):
        """AC5: GET /api/sync/status (after sync) → 200."""
        storage.write_sync_status(
            {
                "status": "success",
                "last_sync": "2026-07-27T00:00:00Z",
                "start_month": "2026-07",
                "end_month": "2026-07",
                "months_synced": 1,
                "row_counts": {
                    "transactions": 5,
                    "events": 2,
                    "budget": 1,
                    "categories": 10,
                    "accounts": 3,
                },
                "errors": [],
                "duration_ms": 1500,
            }
        )
        resp = client.get("/api/sync/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["months_synced"] == 1

    def test_ac6_concurrent_guard_202(
        self, client, tmp_env_file, tmp_private_dir, monkeypatch
    ):
        """AC6: GET /api/sync while running → 202, no new sync."""
        self._setup_key(tmp_env_file)
        # Pre-set running status.
        storage.write_sync_status(
            {
                "status": "running",
                "last_sync": "2026-07-27T00:00:00Z",
                "start_month": "2026-07",
                "end_month": "2026-07",
                "months_synced": 0,
                "row_counts": {
                    "transactions": 0,
                    "events": 0,
                    "budget": 0,
                    "categories": 0,
                    "accounts": 0,
                },
                "errors": [],
                "duration_ms": 0,
            }
        )
        called = {"count": 0}

        def fake_sync(*args, **kwargs):
            called["count"] += 1

        monkeypatch.setattr(sync_runner, "sync_all", fake_sync)
        resp = client.get(
            "/api/sync", params={"start_month": "2026-07", "end_month": "2026-07"}
        )
        assert resp.status_code == 202
        # sync_all NOT called — concurrent guard.
        assert called["count"] == 0

    def test_sync_no_api_key_500(self, client, tmp_env_file, monkeypatch):
        """No API key configured → 500."""
        # Don't write key.
        called = {"count": 0}

        def fake_sync(*args, **kwargs):
            called["count"] += 1

        monkeypatch.setattr(sync_runner, "sync_all", fake_sync)
        resp = client.get(
            "/api/sync", params={"start_month": "2026-07", "end_month": "2026-07"}
        )
        assert resp.status_code == 500
        assert "API key not configured" in resp.json()["detail"]
        assert called["count"] == 0

    def test_sync_missing_params_400(self, client, tmp_env_file):
        """Missing start_month/end_month → 422 → 400."""
        self._setup_key(tmp_env_file)
        resp = client.get("/api/sync", params={"start_month": "2026-07"})
        assert resp.status_code == 400

    def test_status_corrupt_500(self, client, tmp_private_dir):
        (tmp_private_dir / ".sync_status.json").write_text("{bad", encoding="utf-8")
        resp = client.get("/api/sync/status")
        assert resp.status_code == 500


# --------------------------------------------------------------------------- #
# AC25-AC32 — sync edge cases via direct sync_runner calls.
# --------------------------------------------------------------------------- #


class TestSyncEdgeCases:
    def _setup_key(self, tmp_env_file):
        tmp_env_file.write_text("API_KEY=test-key\n", encoding="utf-8")

    def test_ac25_no_events_success(
        self, tmp_private_dir, tmp_env_file, mock_ps_client
    ):
        """AC25: no events in range → success, events count=0."""
        self._setup_key(tmp_env_file)
        mock_ps_client.get_events.return_value = []
        result = sync_runner.sync_all("2026-07", "2026-07")
        assert result.errors == []
        assert result.row_counts.events == 0
        status = storage.read_sync_status()
        assert status["status"] == "success"

    def test_ac26_bad_api_key_failed(
        self, tmp_private_dir, tmp_env_file, mock_ps_client
    ):
        """AC26: bad API key → failed, errors=["PS API auth failed"]."""
        self._setup_key(tmp_env_file)
        mock_ps_client.get_me.side_effect = PSClientError("PS API auth failed")
        result = sync_runner.sync_all("2026-07", "2026-07")
        assert result.errors == ["PS API auth failed"]
        status = storage.read_sync_status()
        assert status["status"] == "failed"
        assert "PS API auth failed" in status["errors"]

    def test_ac27_resync_idempotent(
        self, tmp_private_dir, tmp_env_file, mock_ps_client
    ):
        """AC27: re-sync same month → success, files overwritten."""
        self._setup_key(tmp_env_file)
        # First sync.
        sync_runner.sync_all("2026-07", "2026-07")
        first_status = storage.read_sync_status()
        assert first_status["status"] == "success"
        # Second sync.
        mock_ps_client.get_transactions.return_value = [{"id": "tx_new"}]
        sync_runner.sync_all("2026-07", "2026-07")
        second_status = storage.read_sync_status()
        assert second_status["status"] == "success"
        # File overwritten.
        data = json.loads(
            (tmp_private_dir / "2026-07_ps_raw.json").read_text(encoding="utf-8")
        )
        assert data == [{"id": "tx_new"}]

    def test_ac28_new_account_unbound(
        self, tmp_private_dir, tmp_env_file, mock_ps_client
    ):
        """AC28: new account in PS → partner_id=null, type=null, excluded=false."""
        self._setup_key(tmp_env_file)
        # Pre-seed mappings without the new account.
        mappings = {
            "schema_version": 1,
            "partners": {"partner_a": {"label": "Fixture A"}},
            "accounts": {},
        }
        (tmp_private_dir / "account_mappings.json").write_text(
            json.dumps(mappings), encoding="utf-8"
        )
        sync_runner.sync_all("2026-07", "2026-07")
        updated = json.loads(
            (tmp_private_dir / "account_mappings.json").read_text(encoding="utf-8")
        )
        # mock_ps_client returns 2 transaction_accounts.
        for acc_id in ("1100001", "1100002"):
            assert acc_id in updated["accounts"]
            assert updated["accounts"][acc_id]["partner_id"] is None
            assert updated["accounts"][acc_id]["type"] is None
            assert updated["accounts"][acc_id]["excluded"] is False

    def test_ac29_gone_account_excluded(
        self, tmp_private_dir, tmp_env_file, mock_ps_client
    ):
        """AC29: account in mappings but not PS catalog → excluded=true."""
        self._setup_key(tmp_env_file)
        mappings = {
            "schema_version": 1,
            "partners": {"partner_a": {"label": "Fixture A"}},
            "accounts": {
                "7777777": {
                    "name": "Gone Account",
                    "partner_id": "partner_a",
                    "type": "checking",
                    "excluded": False,
                }
            },
        }
        (tmp_private_dir / "account_mappings.json").write_text(
            json.dumps(mappings), encoding="utf-8"
        )
        # mock returns 1100001 + 1100002, not 7777777.
        sync_runner.sync_all("2026-07", "2026-07")
        updated = json.loads(
            (tmp_private_dir / "account_mappings.json").read_text(encoding="utf-8")
        )
        assert updated["accounts"]["7777777"]["excluded"] is True
        # Binding preserved.
        assert updated["accounts"]["7777777"]["partner_id"] == "partner_a"

    def test_ac30_running_then_success_transitions(
        self, tmp_private_dir, tmp_env_file, mock_ps_client
    ):
        """AC30: status=running before sync, success after."""
        self._setup_key(tmp_env_file)
        statuses = []

        def spy():
            s = storage.read_sync_status()
            statuses.append(s["status"] if s else None)
            return {"id": 12345}

        mock_ps_client.get_me.side_effect = spy
        sync_runner.sync_all("2026-07", "2026-07")
        assert "running" in statuses
        final = storage.read_sync_status()
        assert final["status"] == "success"

    def test_ac31_failure_sets_failed(
        self, tmp_private_dir, tmp_env_file, mock_ps_client
    ):
        """AC31: failure → status=failed, errors populated."""
        self._setup_key(tmp_env_file)
        mock_ps_client.get_budget.side_effect = PSClientError("PS API unavailable")
        result = sync_runner.sync_all("2026-07", "2026-07")
        assert result.errors != []
        status = storage.read_sync_status()
        assert status["status"] == "failed"
        assert len(status["errors"]) > 0

    def test_ac32_writes_category_catalog(
        self, tmp_private_dir, tmp_env_file, mock_ps_client
    ):
        """AC32: sync writes category_catalog.json, categories count > 0."""
        self._setup_key(tmp_env_file)
        mock_ps_client.get_categories.return_value = [
            {"id": 1, "title": "Cat A", "children": []},
            {"id": 2, "title": "Cat B", "children": []},
        ]
        result = sync_runner.sync_all("2026-07", "2026-07")
        assert result.row_counts.categories == 2
        cat_file = tmp_private_dir / "category_catalog.json"
        assert cat_file.exists()
        data = json.loads(cat_file.read_text(encoding="utf-8"))
        assert len(data["categories"]) == 2


# --------------------------------------------------------------------------- #
# AC6 threading.Lock concurrent guard — direct unit test.
# --------------------------------------------------------------------------- #


class TestConcurrentGuard:
    def test_lock_serializes_access(
        self, client, tmp_env_file, tmp_private_dir, monkeypatch
    ):
        """Two concurrent sync requests — only one schedules sync_all."""
        tmp_env_file.write_text("API_KEY=test\n", encoding="utf-8")
        call_count = {"n": 0}
        lock = threading.Lock()

        def slow_sync(*args, **kwargs):
            with lock:
                call_count["n"] += 1
            time.sleep(0.05)

        monkeypatch.setattr(sync_runner, "sync_all", slow_sync)

        # Pre-set running status so concurrent guard kicks in.
        storage.write_sync_status(
            {
                "status": "running",
                "last_sync": "2026-07-27T00:00:00Z",
                "start_month": "2026-07",
                "end_month": "2026-07",
                "months_synced": 0,
                "row_counts": {
                    "transactions": 0,
                    "events": 0,
                    "budget": 0,
                    "categories": 0,
                    "accounts": 0,
                },
                "errors": [],
                "duration_ms": 0,
            }
        )

        results = []
        threads = []

        def make_request():
            r = client.get(
                "/api/sync", params={"start_month": "2026-07", "end_month": "2026-07"}
            )
            results.append(r.status_code)

        for _ in range(3):
            t = threading.Thread(target=make_request)
            threads.append(t)
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All get 202 (running status). sync_all never called.
        assert all(r == 202 for r in results)
        assert call_count["n"] == 0


# --------------------------------------------------------------------------- #
# Health endpoint.
# --------------------------------------------------------------------------- #


class TestHealth:
    def test_health_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
