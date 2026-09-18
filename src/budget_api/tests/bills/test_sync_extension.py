"""F2-BE sync extension integration tests — bills snapshot written during sync.

Mocks PSClient. Uses tmp_private_dir. Asserts bills_dashboard_*.json is written.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from budget_api.services import storage, sync_runner
from budget_api.services.ps_client import PSClientError
from budget_api.services.bills_builder import NoBillsAccountError

# -- Fixtures ----------------------------------------------------------------

GOOD_MAPPINGS = {
    "schema_version": 1,
    "partners": {
        "partner_a": {"label": "Fixture A"},
    },
    "accounts": {
        "4110210": {
            "name": "FxA Check",
            "partner_id": "partner_a",
            "type": "checking",
            "excluded": False,
        },
        "4110213": {
            "name": "FxA Savings",
            "partner_id": "partner_a",
            "type": "savings",
            "excluded": False,
        },
        "4110216": {
            "name": "FxA CC",
            "partner_id": "partner_a",
            "type": "cc",
            "excluded": False,
        },
    },
}

GOOD_ROLES = {
    "34025485": "income",
    "34025245": "spend",
    "34025235": "savings",
}

GOOD_CATEGORY_CATALOG = {
    "start": "2026-06",
    "end": "2026-07",
    "categories": [
        {"id": 34025245, "title": "Common", "children": []},
        {"id": 34025235, "title": "Savings", "children": []},
        {
            "id": 34025240,
            "title": "Transfers",
            "children": [
                {"id": 34025345, "title": "CC Payment (paired)", "children": []},
            ],
        },
    ],
}

GOOD_ACCOUNT_CATALOG = {
    "start": "2026-06",
    "end": "2026-07",
    "accounts": [
        {
            "id": 4110210,
            "name": "FxA Check",
            "type": "bank",
            "current_balance": 9886.31,
            "starting_balance": 97740.37,
        },
        {
            "id": 4110213,
            "name": "FxA Savings",
            "type": "bank",
            "current_balance": 32000,
            "starting_balance": 28000,
        },
        {
            "id": 4110216,
            "name": "FxA CC",
            "type": "credits",
            "current_balance": 27657.91,
            "starting_balance": 26837.2,
        },
    ],
}


def _write_config(tmp_private_dir: Path):
    """Write mappings + roles + catalogs to tmp dir."""
    (tmp_private_dir / "account_mappings.json").write_text(
        json.dumps(GOOD_MAPPINGS), encoding="utf-8"
    )
    (tmp_private_dir / "category_roles.json").write_text(
        json.dumps(GOOD_ROLES), encoding="utf-8"
    )
    (tmp_private_dir / "category_catalog.json").write_text(
        json.dumps(GOOD_CATEGORY_CATALOG), encoding="utf-8"
    )
    (tmp_private_dir / "account_catalog.json").write_text(
        json.dumps(GOOD_ACCOUNT_CATALOG), encoding="utf-8"
    )


def _setup_mock_ps_client(mock_ps_client, events=None, transactions=None):
    """Configure mock PS client with sensible defaults."""
    mock_ps_client.get_me.return_value = {"id": 12345}
    mock_ps_client.get_transactions.return_value = transactions or []
    mock_ps_client.get_events.return_value = events or []
    mock_ps_client.get_budget.return_value = []
    mock_ps_client.get_categories.return_value = GOOD_CATEGORY_CATALOG["categories"]
    mock_ps_client.get_transaction_accounts.return_value = GOOD_ACCOUNT_CATALOG[
        "accounts"
    ]


# -- Tests -------------------------------------------------------------------


def test_sync_writes_bills_dashboard_for_month(
    tmp_private_dir, tmp_env_file, mock_ps_client
):
    """Sync produces bills_dashboard_YYYY-MM.json."""
    (tmp_env_file).write_text("API_KEY=test-key-123\n", encoding="utf-8")
    _write_config(tmp_private_dir)

    events = [
        {
            "id": "evt-1",
            "date": "2026-07-25",
            "note": "Salary",
            "category": {"id": 34025485, "title": "Income", "is_transfer": False},
            "transaction_account": {"id": 4110210, "type": "bank"},
            "amount": 42000,
        },
    ]
    _setup_mock_ps_client(mock_ps_client, events=events, transactions=[])

    result = sync_runner.sync_all("2026-07", "2026-07")

    snapshot_path = storage.bills_dashboard_path("2026-07")
    assert snapshot_path.exists(), "bills_dashboard_2026-07.json was not written"

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["month"] == "2026-07"
    assert len(snapshot["partners"]) == 1
    assert snapshot["partners"][0]["partner"] == "Fixture A"
    assert snapshot["partners"][0]["salary"] == 42000


def test_sync_status_includes_bills_counts(
    tmp_private_dir, tmp_env_file, mock_ps_client
):
    """Sync status includes bills_snapshots_written + bills_warnings."""
    (tmp_env_file).write_text("API_KEY=test-key-123\n", encoding="utf-8")
    _write_config(tmp_private_dir)

    _setup_mock_ps_client(mock_ps_client, events=[], transactions=[])

    sync_runner.sync_all("2026-07", "2026-07")

    status = storage.read_sync_status()
    assert "bills_snapshots_written" in status
    assert "bills_warnings" in status
    assert status["bills_snapshots_written"] >= 1


def test_no_bills_account_appends_warning_sync_continues(
    tmp_private_dir, tmp_env_file, mock_ps_client
):
    """No checking account → bills snapshot skipped, warning appended, sync succeeds."""
    (tmp_env_file).write_text("API_KEY=test-key-123\n", encoding="utf-8")

    # Mappings with no checking account.
    bad_mappings = json.loads(json.dumps(GOOD_MAPPINGS))
    del bad_mappings["accounts"]["4110210"]
    (tmp_private_dir / "account_mappings.json").write_text(
        json.dumps(bad_mappings), encoding="utf-8"
    )
    (tmp_private_dir / "category_roles.json").write_text(
        json.dumps(GOOD_ROLES), encoding="utf-8"
    )
    (tmp_private_dir / "category_catalog.json").write_text(
        json.dumps(GOOD_CATEGORY_CATALOG), encoding="utf-8"
    )
    (tmp_private_dir / "account_catalog.json").write_text(
        json.dumps(GOOD_ACCOUNT_CATALOG), encoding="utf-8"
    )

    _setup_mock_ps_client(mock_ps_client, events=[], transactions=[])

    result = sync_runner.sync_all("2026-07", "2026-07")

    # Sync should succeed (existing steps still work).
    assert result.errors == []

    # Bills snapshot NOT written.
    assert not storage.bills_dashboard_path("2026-07").exists()

    # Warning appended.
    status = storage.read_sync_status()
    assert any("no bills/checking account" in w for w in status["bills_warnings"])


def test_sync_prior_month_auto_fetch_appends_warning(
    tmp_private_dir, tmp_env_file, mock_ps_client
):
    """Prior-month auto-fetch appends a warning."""
    (tmp_env_file).write_text("API_KEY=test-key-123\n", encoding="utf-8")
    _write_config(tmp_private_dir)

    _setup_mock_ps_client(mock_ps_client, events=[], transactions=[])

    # No prior-month cache files on disk.
    assert not (tmp_private_dir / "events_2026-06.json").exists()

    sync_runner.sync_all("2026-07", "2026-07")

    # Prior-month cache should now exist.
    assert (tmp_private_dir / "events_2026-06.json").exists()

    # Warning about auto-fetch.
    status = storage.read_sync_status()
    assert any("auto-fetched" in w for w in status["bills_warnings"])
