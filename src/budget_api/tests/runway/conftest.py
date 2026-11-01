"""Synthetic fixtures. Guard first; app imported only after path isolation."""

from __future__ import annotations

import pytest

from budget_api.tests.isolated_run import guarded
from budget_api.tests.runway.synthetic import World, NOW


@pytest.fixture(autouse=True)
def isolated(tmp_private_dir, tmp_env_file, monkeypatch):
    monkeypatch.delenv("POCKET_SMITH_API_KEY_FILE", raising=False)
    assert tmp_private_dir.parent == tmp_env_file.parent
    with guarded(tmp_private_dir.parent):
        yield


@pytest.fixture
def world(tmp_private_dir):
    return World(tmp_private_dir)


@pytest.fixture
def runway_client(world, monkeypatch, client):
    from budget_api.services import runway
    monkeypatch.setattr(runway, "local_now", lambda: NOW)
    world.write()
    return client
