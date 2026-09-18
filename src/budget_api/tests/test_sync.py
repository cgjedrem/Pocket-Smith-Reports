"""B12 — sync_runner tests. Mock PSClient, tmp dirs. AC: status, merge, migration, validation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from budget_api.models.sync import RowCounts
from budget_api.services import env_writer, storage, sync_runner
from budget_api.services.ps_client import PSClientError

# --------------------------------------------------------------------------- #
# Month validation.
# --------------------------------------------------------------------------- #


class TestMonthValidation:
    def test_valid_single_month(self):
        months = sync_runner._requested_months("2026-07", "2026-07")
        assert months == ["2026-07"]

    def test_valid_range(self):
        months = sync_runner._requested_months("2026-01", "2026-03")
        assert months == ["2026-01", "2026-02", "2026-03"]

    def test_cross_year_boundary(self):
        months = sync_runner._requested_months("2025-11", "2026-02")
        assert months == ["2025-11", "2025-12", "2026-01", "2026-02"]

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="YYYY-MM"):
            sync_runner._requested_months("invalid", "2026-07")

    def test_invalid_format_end_raises(self):
        with pytest.raises(ValueError, match="YYYY-MM"):
            sync_runner._requested_months("2026-07", "2026-13")

    def test_start_after_end_raises(self):
        with pytest.raises(ValueError, match="start must not be after end"):
            sync_runner._requested_months("2026-07", "2025-01")

    def test_month_dates(self):
        start, end = sync_runner._month_dates("2026-07")
        assert start == "2026-07-01"
        assert end == "2026-07-31"

    def test_month_dates_february_leap(self):
        start, end = sync_runner._month_dates("2024-02")
        assert start == "2024-02-01"
        assert end == "2024-02-29"

    def test_month_dates_february_nonleap(self):
        start, end = sync_runner._month_dates("2026-02")
        assert end == "2026-02-28"


# --------------------------------------------------------------------------- #
# Owner → partner_id migration.
# --------------------------------------------------------------------------- #


class TestOwnerMigration:
    def test_migrates_owner_to_partner_id(self, sample_old_mappings):
        changed = sync_runner._migrate_owner_to_partner_id(sample_old_mappings)
        assert changed is True
        acc = sample_old_mappings["accounts"]["4110210"]
        assert "owner" not in acc
        assert acc["partner_id"] == "partner_a"

    def test_idempotent_on_rerun(self, sample_mappings):
        changed = sync_runner._migrate_owner_to_partner_id(sample_mappings)
        assert changed is False

    def test_no_accounts_key(self):
        mappings = {"schema_version": 1, "partners": {}}
        changed = sync_runner._migrate_owner_to_partner_id(mappings)
        assert changed is False

    def test_skips_non_dict_entries(self):
        mappings = {"accounts": {"bad": "not a dict"}}
        changed = sync_runner._migrate_owner_to_partner_id(mappings)
        assert changed is False


# --------------------------------------------------------------------------- #
# Account merge — new, existing, gone.
# --------------------------------------------------------------------------- #


class TestAccountMerge:
    def test_new_account_added_unbound(self, sample_mappings):
        ps_accounts = [
            {"id": 4110210, "name": "FxA Check Updated"},
            {"id": 9999999, "name": "New Bank Account"},
        ]
        sync_runner._merge_accounts_into_mappings(ps_accounts, sample_mappings)
        new = sample_mappings["accounts"]["9999999"]
        assert new["partner_id"] is None
        assert new["type"] is None
        assert new["excluded"] is False
        assert new["name"] == "New Bank Account"

    def test_existing_account_preserved(self, sample_mappings):
        ps_accounts = [{"id": 4110210, "name": "FxA Check New Name"}]
        sync_runner._merge_accounts_into_mappings(ps_accounts, sample_mappings)
        acc = sample_mappings["accounts"]["4110210"]
        assert acc["partner_id"] == "partner_a"
        assert acc["type"] == "checking"
        assert acc["name"] == "FxA Check New Name"

    def test_gone_account_excluded(self, sample_mappings):
        # 4110213 not in fresh PS catalog → excluded.
        ps_accounts = [{"id": 4110210, "name": "FxA Check"}]
        sync_runner._merge_accounts_into_mappings(ps_accounts, sample_mappings)
        gone = sample_mappings["accounts"]["4110213"]
        assert gone["excluded"] is True
        # Binding preserved.
        assert gone["partner_id"] == "partner_a"

    def test_reactivated_account(self, sample_mappings):
        # Mark excluded, then re-merge with PS catalog including it.
        sample_mappings["accounts"]["4110210"]["excluded"] = True
        ps_accounts = [{"id": 4110210, "name": "FxA Check"}]
        sync_runner._merge_accounts_into_mappings(ps_accounts, sample_mappings)
        # Merge does NOT auto-unexclude — preserves existing excluded flag.
        # (Existing entry updated name only, excluded stays as-is.)
        acc = sample_mappings["accounts"]["4110210"]
        assert acc["name"] == "FxA Check"

    def test_empty_ps_accounts_all_excluded(self, sample_mappings):
        sync_runner._merge_accounts_into_mappings([], sample_mappings)
        for entry in sample_mappings["accounts"].values():
            assert entry["excluded"] is True

    def test_skips_invalid_ps_account(self, sample_mappings):
        ps_accounts = [
            {"id": 4110210, "name": "ok"},
            {"no_id": True},
            "not a dict",
        ]
        sync_runner._merge_accounts_into_mappings(ps_accounts, sample_mappings)
        assert "4110210" in sample_mappings["accounts"]


# --------------------------------------------------------------------------- #
# sync_all — success, failure, status transitions.
# --------------------------------------------------------------------------- #


class TestSyncAll:
    def _setup_env_key(self, tmp_env_file: Path):
        """Write API_KEY to tmp .env."""
        tmp_env_file.write_text("API_KEY=test-key-123\n", encoding="utf-8")

    def test_success_writes_files_and_status(
        self, tmp_private_dir, tmp_env_file, mock_ps_client
    ):
        self._setup_env_key(tmp_env_file)
        result = sync_runner.sync_all("2026-07", "2026-07")

        assert result.errors == []
        assert result.months_synced == 1
        assert result.row_counts.transactions == 1
        assert result.row_counts.events == 1
        assert result.row_counts.budget == 1
        assert result.row_counts.categories == 1
        assert result.row_counts.accounts == 2

        # Status file written.
        status = storage.read_sync_status()
        assert status["status"] == "success"
        assert status["months_synced"] == 1

        # Monthly files written.
        assert (tmp_private_dir / "2026-07_ps_raw.json").exists()
        assert (tmp_private_dir / "events_2026-07.json").exists()
        assert (tmp_private_dir / "budget_snapshot.json").exists()
        assert (tmp_private_dir / "category_catalog.json").exists()
        assert (tmp_private_dir / "account_catalog.json").exists()

    def test_failure_sets_failed_status(
        self, tmp_private_dir, tmp_env_file, mock_ps_client
    ):
        self._setup_env_key(tmp_env_file)
        mock_ps_client.get_me.side_effect = PSClientError("PS API auth failed")

        result = sync_runner.sync_all("2026-07", "2026-07")

        assert result.errors == ["PS API auth failed"]
        assert result.months_synced == 0
        status = storage.read_sync_status()
        assert status["status"] == "failed"
        assert "PS API auth failed" in status["errors"]

    def test_partial_months_synced_on_failure(
        self, tmp_private_dir, tmp_env_file, mock_ps_client
    ):
        """Fail on 2nd month — months_synced=1 preserved."""
        self._setup_env_key(tmp_env_file)
        # First month ok, second month's get_transactions fails.
        # F2 chain: prior-month auto-fetch now happens AFTER the per-month
        # loop, so the failure hits before any prior fetch.
        mock_ps_client.get_transactions.side_effect = [
            [{"id": "tx1"}],  # 2026-06 (first month)
            PSClientError("PS API rate limited"),  # 2026-07 (second month)
        ]
        mock_ps_client.get_events.side_effect = [
            [{"id": "ev1"}],  # 2026-06
        ]
        result = sync_runner.sync_all("2026-06", "2026-07")

        assert result.months_synced == 1
        assert result.errors == ["PS API rate limited"]
        status = storage.read_sync_status()
        assert status["status"] == "failed"
        assert status["months_synced"] == 1

    def test_invalid_period_no_ps_call(
        self, tmp_private_dir, tmp_env_file, mock_ps_client
    ):
        self._setup_env_key(tmp_env_file)
        result = sync_runner.sync_all("invalid", "2026-07")

        assert result.errors != []
        assert result.months_synced == 0
        # PS client never constructed.
        mock_ps_client.get_me.assert_not_called()
        status = storage.read_sync_status()
        assert status["status"] == "failed"

    def test_start_after_end_no_ps_call(
        self, tmp_private_dir, tmp_env_file, mock_ps_client
    ):
        self._setup_env_key(tmp_env_file)
        result = sync_runner.sync_all("2026-07", "2025-01")

        assert result.months_synced == 0
        mock_ps_client.get_me.assert_not_called()
        status = storage.read_sync_status()
        assert status["status"] == "failed"

    def test_no_api_key_raises_in_result(
        self, tmp_private_dir, tmp_env_file, mock_ps_client
    ):
        """No API_KEY in .env → error in result, failed status."""
        # Don't write key.
        result = sync_runner.sync_all("2026-07", "2026-07")

        assert result.errors != []
        assert any("API_KEY" in e or "missing" in e for e in result.errors)
        status = storage.read_sync_status()
        assert status["status"] == "failed"

    def test_running_status_written_before_ps_call(
        self, tmp_private_dir, tmp_env_file, mock_ps_client
    ):
        """Status=running written before first PS call."""
        self._setup_env_key(tmp_env_file)
        call_statuses = []

        def spy_get_me():
            status = storage.read_sync_status()
            call_statuses.append(status["status"] if status else None)
            return {"id": 12345}

        mock_ps_client.get_me.side_effect = spy_get_me

        sync_runner.sync_all("2026-07", "2026-07")
        assert call_statuses == ["running"]

    def test_corrupt_mappings_raises_value_error(
        self, tmp_private_dir, tmp_env_file, mock_ps_client
    ):
        self._setup_env_key(tmp_env_file)
        # Write corrupt mappings file.
        (tmp_private_dir / "account_mappings.json").write_text(
            "{not valid json", encoding="utf-8"
        )
        result = sync_runner.sync_all("2026-07", "2026-07")
        assert any("corrupt" in e for e in result.errors)
        status = storage.read_sync_status()
        assert status["status"] == "failed"

    def test_multi_month_success(self, tmp_private_dir, tmp_env_file, mock_ps_client):
        self._setup_env_key(tmp_env_file)
        mock_ps_client.get_transactions.return_value = [{"id": "tx1"}]
        mock_ps_client.get_events.return_value = [{"id": "ev1"}]

        result = sync_runner.sync_all("2026-01", "2026-03")
        assert result.errors == []
        assert result.months_synced == 3
        assert result.row_counts.transactions == 3
        assert result.row_counts.events == 3

        for month in ("2026-01", "2026-02", "2026-03"):
            assert (tmp_private_dir / f"{month}_ps_raw.json").exists()
            assert (tmp_private_dir / f"events_{month}.json").exists()

    def test_merges_accounts_on_sync(
        self, tmp_private_dir, tmp_env_file, mock_ps_client
    ):
        """sync_all merges transaction_accounts into mappings."""
        self._setup_env_key(tmp_env_file)
        # Pre-seed mappings with one account.
        mappings = {
            "schema_version": 1,
            "partners": {"partner_a": {"label": "Fixture A"}},
            "accounts": {
                "4110210": {
                    "name": "old name",
                    "partner_id": "partner_a",
                    "type": "checking",
                    "excluded": False,
                }
            },
        }
        (tmp_private_dir / "account_mappings.json").write_text(
            json.dumps(mappings), encoding="utf-8"
        )

        sync_runner.sync_all("2026-07", "2026-07")

        updated = json.loads(
            (tmp_private_dir / "account_mappings.json").read_text(encoding="utf-8")
        )
        # Existing preserved + new added.
        assert "4110210" in updated["accounts"]
        assert updated["accounts"]["4110210"]["partner_id"] == "partner_a"
        assert "4110213" in updated["accounts"]
        assert updated["accounts"]["4110213"]["partner_id"] is None

    def test_migrates_owner_on_sync(
        self, tmp_private_dir, tmp_env_file, mock_ps_client
    ):
        """sync_all migrates old owner→partner_id schema."""
        self._setup_env_key(tmp_env_file)
        old = {
            "schema_version": 1,
            "partners": {"partner_a": {"label": "Fixture A"}},
            "accounts": {
                "4110210": {"name": "old", "owner": "partner_a", "excluded": False}
            },
        }
        (tmp_private_dir / "account_mappings.json").write_text(
            json.dumps(old), encoding="utf-8"
        )

        sync_runner.sync_all("2026-07", "2026-07")

        updated = json.loads(
            (tmp_private_dir / "account_mappings.json").read_text(encoding="utf-8")
        )
        acc = updated["accounts"]["4110210"]
        assert "owner" not in acc
        assert acc["partner_id"] == "partner_a"



# --------------------------------------------------------------------------- #
# App startup — stale sync-status cleanup.
# --------------------------------------------------------------------------- #


class TestStartupClearsSyncStatus:
    def test_startup_deletes_stale_status_file(self, tmp_private_dir):
        """A crashed sync left 'running' on disk; startup must remove it."""
        from fastapi.testclient import TestClient

        from budget_api.main import app

        storage.write_sync_status(
            {
                "status": "running",
                "last_sync": "2026-09-15T14:52:38Z",
                "start_month": "2026-06",
                "end_month": "2027-09",
                "months_synced": 0,
                "row_counts": {},
                "errors": [],
                "duration_ms": 0,
            }
        )
        assert storage.SYNC_STATUS_PATH.exists()

        with TestClient(app):
            assert not storage.SYNC_STATUS_PATH.exists()

    def test_startup_ok_without_status_file(self, tmp_private_dir):
        from fastapi.testclient import TestClient

        from budget_api.main import app

        with TestClient(app):
            assert not storage.SYNC_STATUS_PATH.exists()

    def test_stale_running_gone_after_restart_flow(self, tmp_private_dir):
        """End-to-end: seed stuck status -> restart -> GET returns 404."""
        from fastapi.testclient import TestClient

        from budget_api.main import app

        storage.write_sync_status({"status": "running", "last_sync": "stale"})

        with TestClient(app) as client:
            response = client.get("/api/sync/status")
        assert response.status_code == 404

    def test_startup_preserves_terminal_success_status(self, tmp_private_dir):
        """A successful sync's record survives a restart (sync history)."""
        from fastapi.testclient import TestClient

        from budget_api.main import app

        storage.write_sync_status(
            {
                "status": "success",
                "last_sync": "2026-09-17T13:00:00Z",
                "start_month": "2026-06",
                "end_month": "2027-09",
                "months_synced": 28,
                "row_counts": {},
                "errors": [],
                "duration_ms": 4200,
            }
        )

        with TestClient(app) as client:
            response = client.get("/api/sync/status")
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert response.json()["months_synced"] == 28

    def test_startup_preserves_terminal_failed_status_and_drops_malformed(
        self, tmp_private_dir
    ):
        """'failed' survives (terminal); an unparseable file is stale."""
        from fastapi.testclient import TestClient

        from budget_api.main import app

        storage.write_sync_status(
            {
                "status": "failed",
                "last_sync": "2026-09-17T13:00:00Z",
                "start_month": "2026-06",
                "end_month": "2027-09",
                "months_synced": 0,
                "row_counts": {},
                "errors": ["boom"],
                "duration_ms": 10,
            }
        )
        with TestClient(app) as client:
            assert client.get("/api/sync/status").status_code == 200

        storage.SYNC_STATUS_PATH.write_text("{ not json", encoding="utf-8")
        with TestClient(app) as client:
            assert client.get("/api/sync/status").status_code == 404