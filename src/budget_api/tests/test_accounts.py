"""B14 — accounts router tests. AC20-AC24, merge defaults."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# --------------------------------------------------------------------------- #
# AC20 — GET /api/accounts.
# --------------------------------------------------------------------------- #


class TestListAccounts:
    def test_ac20_list_200(self, client, write_mappings, write_catalog):
        resp = client.get("/api/accounts")
        assert resp.status_code == 200
        body = resp.json()
        assert "accounts" in body
        ids = [a["id"] for a in body["accounts"]]
        assert "1100001" in ids
        assert "1100002" in ids
        assert "1100007" in ids

    def test_list_empty_when_no_catalog(self, client, write_mappings):
        resp = client.get("/api/accounts")
        assert resp.status_code == 200
        assert resp.json() == {"accounts": []}

    def test_list_corrupt_catalog_500(self, client, write_mappings, tmp_private_dir):
        (tmp_private_dir / "account_catalog.json").write_text("{bad", encoding="utf-8")
        resp = client.get("/api/accounts")
        assert resp.status_code == 500

    def test_list_corrupt_mappings_500(self, client, write_catalog, tmp_private_dir):
        (tmp_private_dir / "account_mappings.json").write_text("{bad", encoding="utf-8")
        resp = client.get("/api/accounts")
        assert resp.status_code == 500

    def test_merge_unbound_defaults(self, client, write_mappings, tmp_private_dir):
        """Catalog account without mapping → null, null, false."""
        catalog = {
            "start": "2026-07",
            "end": "2026-07",
            "accounts": [
                {"id": 8888888, "name": "Unbound Account"},
            ],
        }
        (tmp_private_dir / "account_catalog.json").write_text(
            json.dumps(catalog), encoding="utf-8"
        )
        resp = client.get("/api/accounts")
        assert resp.status_code == 200
        acc = resp.json()["accounts"][0]
        assert acc["partner_id"] is None
        assert acc["type"] is None
        assert acc["excluded"] is False

    def test_merge_bound_values(self, client, write_mappings, write_catalog):
        resp = client.get("/api/accounts")
        accounts = {a["id"]: a for a in resp.json()["accounts"]}
        acc = accounts["1100001"]
        assert acc["partner_id"] == "partner_a"
        assert acc["type"] == "checking"
        assert acc["excluded"] is False


# --------------------------------------------------------------------------- #
# AC21-AC24 — PUT /api/accounts/{id}/binding.
# --------------------------------------------------------------------------- #


class TestUpdateBinding:
    def test_ac21_valid_binding_200(self, client, write_mappings, write_catalog):
        resp = client.put(
            "/api/accounts/1100001/binding",
            json={"partner_id": "partner_a", "type": "checking", "excluded": False},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "1100001"
        assert body["partner_id"] == "partner_a"
        assert body["type"] == "checking"
        assert body["excluded"] is False

    def test_ac22_invalid_partner_id_400(self, client, write_mappings, write_catalog):
        resp = client.put(
            "/api/accounts/1100001/binding",
            json={"partner_id": "nonexistent", "type": "checking", "excluded": False},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "invalid partner_id"

    def test_ac23_invalid_type_400(self, client, write_mappings, write_catalog):
        resp = client.put(
            "/api/accounts/1100001/binding",
            json={"partner_id": None, "type": "bitcoin", "excluded": False},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "invalid type"

    def test_ac23_type_422_to_400(self, client, write_mappings, write_catalog):
        """Pydantic 422 (wrong type for field) → custom handler → 400."""
        resp = client.put(
            "/api/accounts/1100001/binding",
            json={"partner_id": None, "type": 123, "excluded": False},
        )
        assert resp.status_code == 400

    def test_ac24_nonexistent_account_404(self, client, write_mappings, write_catalog):
        resp = client.put(
            "/api/accounts/9999999/binding",
            json={"partner_id": None, "type": None, "excluded": False},
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "account not found"

    def test_null_partner_id_ok(self, client, write_mappings, write_catalog):
        resp = client.put(
            "/api/accounts/1100001/binding",
            json={"partner_id": None, "type": None, "excluded": True},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["partner_id"] is None
        assert body["type"] is None
        assert body["excluded"] is True

    def test_valid_types_accepted(self, client, write_mappings, write_catalog):
        for valid_type in ("checking", "cc", "savings"):
            resp = client.put(
                "/api/accounts/1100001/binding",
                json={"partner_id": None, "type": valid_type, "excluded": False},
            )
            assert resp.status_code == 200
            assert resp.json()["type"] == valid_type

    def test_full_replace_not_merge(self, client, write_mappings, write_catalog):
        """PUT replaces all fields — omitted fields reset to defaults."""
        # First set partner_id + type.
        client.put(
            "/api/accounts/1100001/binding",
            json={"partner_id": "partner_a", "type": "checking", "excluded": False},
        )
        # Then PUT with only excluded=True, partner_id/type null.
        resp = client.put(
            "/api/accounts/1100001/binding",
            json={"partner_id": None, "type": None, "excluded": True},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["partner_id"] is None
        assert body["type"] is None
        assert body["excluded"] is True

    def test_binding_persists(
        self, client, write_mappings, write_catalog, tmp_private_dir
    ):
        client.put(
            "/api/accounts/1100001/binding",
            json={"partner_id": "partner_b", "type": "savings", "excluded": False},
        )
        raw = json.loads(
            (tmp_private_dir / "account_mappings.json").read_text(encoding="utf-8")
        )
        acc = raw["accounts"]["1100001"]
        assert acc["partner_id"] == "partner_b"
        assert acc["type"] == "savings"

    def test_binding_missing_body_400(self, client, write_mappings, write_catalog):
        """Pydantic 422 → 400."""
        resp = client.put("/api/accounts/1100001/binding", json=None)
        assert resp.status_code == 400

    def test_binding_missing_excluded_defaults_false(
        self, client, write_mappings, write_catalog
    ):
        """excluded has default=False in model — omitted → False."""
        resp = client.put(
            "/api/accounts/1100001/binding",
            json={"partner_id": None, "type": None},
        )
        assert resp.status_code == 200
        assert resp.json()["excluded"] is False
