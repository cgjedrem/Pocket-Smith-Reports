"""B15 — settings router tests. AC7-AC11b, never returns raw key, .env preserve."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from budget_api.services.ps_client import PSClientError

# --------------------------------------------------------------------------- #
# AC7-AC8 — GET /api/settings/api-key.
# --------------------------------------------------------------------------- #


class TestGetApiKey:
    def test_ac7_key_set_configured_true(self, client, tmp_env_file):
        tmp_env_file.write_text("API_KEY=secret123\n", encoding="utf-8")
        resp = client.get("/api/settings/api-key")
        assert resp.status_code == 200
        assert resp.json() == {"configured": True}

    def test_ac8_key_not_set_configured_false(self, client, tmp_env_file):
        # No .env written.
        resp = client.get("/api/settings/api-key")
        assert resp.status_code == 200
        assert resp.json() == {"configured": False}

    def test_ac8_empty_value_configured_false(self, client, tmp_env_file):
        tmp_env_file.write_text("API_KEY=\n", encoding="utf-8")
        resp = client.get("/api/settings/api-key")
        assert resp.status_code == 200
        assert resp.json() == {"configured": False}

    def test_ac8_whitespace_value_configured_false(self, client, tmp_env_file):
        tmp_env_file.write_text("API_KEY=   \n", encoding="utf-8")
        resp = client.get("/api/settings/api-key")
        assert resp.status_code == 200
        assert resp.json() == {"configured": False}

    def test_get_never_returns_raw_key(self, client, tmp_env_file):
        tmp_env_file.write_text("API_KEY=super-secret-key\n", encoding="utf-8")
        resp = client.get("/api/settings/api-key")
        body = resp.json()
        assert "super-secret-key" not in str(body)
        assert "configured" in body


# --------------------------------------------------------------------------- #
# AC9-AC11b — PUT /api/settings/api-key.
# --------------------------------------------------------------------------- #


class TestUpdateApiKey:
    def test_ac9_valid_key_200(self, client, tmp_env_file, mock_ps_client):
        resp = client.put("/api/settings/api-key", json={"api_key": "valid-key"})
        assert resp.status_code == 200
        assert resp.json() == {"configured": True}
        # Key written to .env.
        content = tmp_env_file.read_text(encoding="utf-8")
        assert "API_KEY=valid-key" in content
        # PS /me called.
        mock_ps_client.get_me.assert_called_once()

    def test_ac10_empty_key_400(self, client, tmp_env_file, mock_ps_client):
        resp = client.put("/api/settings/api-key", json={"api_key": ""})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "api_key is required"
        # PS not called.
        mock_ps_client.get_me.assert_not_called()

    def test_ac10_whitespace_key_400(self, client, tmp_env_file, mock_ps_client):
        resp = client.put("/api/settings/api-key", json={"api_key": "   "})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "api_key is required"

    def test_ac10_missing_field_400(self, client, tmp_env_file, mock_ps_client):
        """Pydantic 422 → custom handler → 400."""
        resp = client.put("/api/settings/api-key", json={})
        assert resp.status_code == 400

    def test_ac11_rejected_key_400(self, client, tmp_env_file, mock_ps_client):
        mock_ps_client.get_me.side_effect = PSClientError("PS API auth failed")
        resp = client.put("/api/settings/api-key", json={"api_key": "bad-key"})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "PS API rejected key"
        # Key still written (no rollback).
        content = tmp_env_file.read_text(encoding="utf-8")
        assert "API_KEY=bad-key" in content

    def test_ac11_forbidden_key_400(self, client, tmp_env_file, mock_ps_client):
        mock_ps_client.get_me.side_effect = PSClientError("PS API forbidden")
        resp = client.put("/api/settings/api-key", json={"api_key": "bad"})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "PS API rejected key"

    def test_ac11b_unreachable_400(self, client, tmp_env_file, mock_ps_client):
        mock_ps_client.get_me.side_effect = PSClientError(
            "PS API network error: refused"
        )
        resp = client.put("/api/settings/api-key", json={"api_key": "x"})
        assert resp.status_code == 400
        assert "unreachable" in resp.json()["detail"]

    def test_ac11b_timeout_400(self, client, tmp_env_file, mock_ps_client):
        mock_ps_client.get_me.side_effect = PSClientError("PS API timeout")
        resp = client.put("/api/settings/api-key", json={"api_key": "x"})
        assert resp.status_code == 400
        assert "unreachable" in resp.json()["detail"]

    def test_ac11b_unavailable_400(self, client, tmp_env_file, mock_ps_client):
        mock_ps_client.get_me.side_effect = PSClientError("PS API unavailable")
        resp = client.put("/api/settings/api-key", json={"api_key": "x"})
        assert resp.status_code == 400
        assert "unreachable" in resp.json()["detail"]

    def test_other_ps_error_400(self, client, tmp_env_file, mock_ps_client):
        mock_ps_client.get_me.side_effect = PSClientError("PS API error: 418 teapot")
        resp = client.put("/api/settings/api-key", json={"api_key": "x"})
        assert resp.status_code == 400
        assert "418" in resp.json()["detail"]

    def test_env_write_preserves_other_lines(
        self, client, tmp_env_file, mock_ps_client
    ):
        tmp_env_file.write_text(
            "OTHER_VAR=keep\nAPI_KEY=old\nANOTHER=also-keep\n",
            encoding="utf-8",
        )
        resp = client.put("/api/settings/api-key", json={"api_key": "new-key"})
        assert resp.status_code == 200
        content = tmp_env_file.read_text(encoding="utf-8")
        assert "OTHER_VAR=keep" in content
        assert "ANOTHER=also-keep" in content
        assert "API_KEY=new-key" in content
        assert "API_KEY=old" not in content

    def test_env_write_creates_if_missing(self, client, tmp_env_file, mock_ps_client):
        assert not tmp_env_file.exists()
        resp = client.put("/api/settings/api-key", json={"api_key": "fresh-key"})
        assert resp.status_code == 200
        content = tmp_env_file.read_text(encoding="utf-8")
        assert "API_KEY=fresh-key" in content

    def test_env_write_strips_key(self, client, tmp_env_file, mock_ps_client):
        resp = client.put("/api/settings/api-key", json={"api_key": "  padded  "})
        assert resp.status_code == 200
        content = tmp_env_file.read_text(encoding="utf-8")
        assert "API_KEY=padded" in content
