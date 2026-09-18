"""Shared fixtures — tmp dirs, mock PS, FastAPI TestClient. Isolated, no real fs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from budget_api.services import env_writer, storage

# --------------------------------------------------------------------------- #
# Path isolation — every test gets fresh tmp private dir + tmp .env.
# --------------------------------------------------------------------------- #


@pytest.fixture
def tmp_private_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Monkeypatch storage.PRIVATE_DATA_DIR + derived paths to tmp_path/private."""
    private = tmp_path / "private"
    private.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(storage, "PRIVATE_DATA_DIR", private)
    monkeypatch.setattr(storage, "PARTNERS_PATH", private / "partners.json")
    monkeypatch.setattr(
        storage, "ACCOUNT_MAPPING_PATH", private / "account_mappings.json"
    )
    monkeypatch.setattr(
        storage, "ACCOUNT_CATALOG_PATH", private / "account_catalog.json"
    )
    monkeypatch.setattr(
        storage, "CATEGORY_CATALOG_PATH", private / "category_catalog.json"
    )
    monkeypatch.setattr(storage, "SYNC_STATUS_PATH", private / ".sync_status.json")
    # F1.2 report paths
    monkeypatch.setattr(storage, "CATEGORY_ROLES_PATH", private / "category_roles.json")
    monkeypatch.setattr(
        storage,
        "DETAILED_SECTION_MAPPING_PATH",
        private / "detailed_section_mapping.json",
    )
    monkeypatch.setattr(storage, "PARTNER_LABELS_PATH", private / "partner_labels.json")
    return private


@pytest.fixture
def tmp_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Monkeypatch env_writer.ENV_PATH to tmp_path/.env."""
    env_path = tmp_path / ".env"
    monkeypatch.setattr(env_writer, "ENV_PATH", env_path)
    return env_path


# --------------------------------------------------------------------------- #
# Sample data — shapes mirror data/private/*.json.
# --------------------------------------------------------------------------- #


@pytest.fixture
def sample_mappings() -> dict[str, Any]:
    """Two partners + three accounts (owner→partner_id already migrated)."""
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
            "1100002": {
                "name": "FxA Savings Nordic Bank",
                "partner_id": "partner_a",
                "type": "savings",
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


@pytest.fixture
def sample_old_mappings() -> dict[str, Any]:
    """Pre-migration schema — owner field, no partner_id."""
    return {
        "schema_version": 1,
        "partners": {
            "partner_a": {"label": "Fixture A"},
            "partner_b": {"label": "Fixture B"},
        },
        "accounts": {
            "1100001": {
                "name": "FxA Check",
                "owner": "partner_a",
                "excluded": False,
            },
        },
    }


@pytest.fixture
def sample_catalog() -> dict[str, Any]:
    """account_catalog.json shape — accounts list with PS ids matching mappings."""
    return {
        "start": "2026-07",
        "end": "2026-07",
        "accounts": [
            {"id": 1100001, "name": "FxA Check Nordic Bank"},
            {"id": 1100002, "name": "FxA Savings Nordic Bank"},
            {"id": 1100007, "name": "FxB Check Nordic Bank"},
        ],
    }


@pytest.fixture
def sample_categories() -> dict[str, Any]:
    """Nested category tree — root + child + grandchild."""
    return {
        "start": "2026-07",
        "end": "2026-07",
        "categories": [
            {
                "id": 100,
                "title": "Root A",
                "parent_id": None,
                "children": [
                    {
                        "id": 110,
                        "title": "Child A1",
                        "parent_id": 100,
                        "children": [
                            {
                                "id": 111,
                                "title": "Grandchild A1a",
                                "parent_id": 110,
                                "children": [],
                            },
                        ],
                    },
                    {
                        "id": 120,
                        "title": "Child A2",
                        "parent_id": 100,
                        "children": [],
                    },
                ],
            },
            {
                "id": 200,
                "title": "Root B",
                "parent_id": None,
                "children": [],
            },
        ],
    }


@pytest.fixture
def write_mappings(tmp_private_dir: Path, sample_mappings: dict[str, Any]) -> Path:
    """Pre-seed account_mappings.json in tmp private dir."""
    path = tmp_private_dir / "account_mappings.json"
    path.write_text(json.dumps(sample_mappings), encoding="utf-8")
    return path


@pytest.fixture
def write_catalog(tmp_private_dir: Path, sample_catalog: dict[str, Any]) -> Path:
    """Pre-seed account_catalog.json in tmp private dir."""
    path = tmp_private_dir / "account_catalog.json"
    path.write_text(json.dumps(sample_catalog), encoding="utf-8")
    return path


@pytest.fixture
def write_categories(tmp_private_dir: Path, sample_categories: dict[str, Any]) -> Path:
    """Pre-seed category_catalog.json in tmp private dir."""
    path = tmp_private_dir / "category_catalog.json"
    path.write_text(json.dumps(sample_categories), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Mock PSClient — canned responses, no network.
# --------------------------------------------------------------------------- #


@pytest.fixture
def mock_ps_client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Patch PSClient class in sync_runner + settings routers. Returns mock instance."""
    mock_instance = MagicMock()
    mock_instance.get_me.return_value = {"id": 12345}
    mock_instance.get_accounts.return_value = [{"id": 1, "name": "Acc1"}]
    mock_instance.get_transaction_accounts.return_value = [
        {"id": 1100001, "name": "FxA Check"},
        {"id": 1100002, "name": "FxA Savings"},
    ]
    mock_instance.get_transactions.return_value = [{"id": "tx1"}]
    mock_instance.get_transactions_for_account.return_value = []
    mock_instance.get_events.return_value = [{"id": "ev1"}]
    mock_instance.get_budget.return_value = [{"id": "b1"}]
    mock_instance.get_categories.return_value = [
        {"id": 100, "title": "Root", "children": []}
    ]

    mock_class = MagicMock(return_value=mock_instance)

    # Patch where imported.
    from budget_api.services import sync_runner as sync_runner_mod
    from budget_api.routers import settings as settings_mod

    monkeypatch.setattr(sync_runner_mod, "PSClient", mock_class)
    monkeypatch.setattr(settings_mod, "PSClient", mock_class)
    return mock_instance


# --------------------------------------------------------------------------- #
# FastAPI TestClient — app from main.py.
# --------------------------------------------------------------------------- #


@pytest.fixture
def client(tmp_private_dir: Path, tmp_env_file: Path) -> TestClient:
    """TestClient with isolated fs paths. Tmp private + tmp .env pre-applied."""
    from budget_api.main import app

    return TestClient(app)
