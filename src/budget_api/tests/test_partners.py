"""B13 — partners router tests. AC12-AC19, slugify, collision."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# --------------------------------------------------------------------------- #
# AC12 — GET /api/partners.
# --------------------------------------------------------------------------- #


class TestListPartners:
    def test_ac12_list_200(self, client, write_mappings):
        resp = client.get("/api/partners")
        assert resp.status_code == 200
        body = resp.json()
        assert "partners" in body
        labels = [p["label"] for p in body["partners"]]
        assert "Fixture A" in labels
        assert "Fixture B" in labels

    def test_list_empty_when_no_file(self, client, tmp_private_dir):
        resp = client.get("/api/partners")
        assert resp.status_code == 200
        assert resp.json() == {"partners": []}

    def test_list_corrupt_file_500(self, client, tmp_private_dir):
        (tmp_private_dir / "account_mappings.json").write_text(
            "{bad json", encoding="utf-8"
        )
        resp = client.get("/api/partners")
        assert resp.status_code == 500


# --------------------------------------------------------------------------- #
# AC13 — POST /api/partners.
# --------------------------------------------------------------------------- #


class TestCreatePartner:
    def test_ac13_create_201(self, client, write_mappings):
        resp = client.post("/api/partners", json={"label": "Test"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["label"] == "Test"
        assert body["id"] == "test"

    def test_ac14_empty_label_400(self, client, write_mappings):
        resp = client.post("/api/partners", json={"label": ""})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "label is required"

    def test_ac14_whitespace_label_400(self, client, write_mappings):
        resp = client.post("/api/partners", json={"label": "   "})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "label is required"

    def test_ac14_no_alnum_400(self, client, write_mappings):
        resp = client.post("/api/partners", json={"label": "!!!"})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "label must contain alphanumeric characters"

    def test_ac14_missing_label_field_400(self, client, write_mappings):
        # Pydantic 422 → custom handler → 400.
        resp = client.post("/api/partners", json={})
        assert resp.status_code == 400

    def test_slugify_lowercase(self, client, write_mappings):
        # Use label not in sample_mappings to avoid collision suffix.
        resp = client.post("/api/partners", json={"label": "Bob"})
        assert resp.status_code == 201
        assert resp.json()["id"] == "bob"

    def test_slugify_hyphens(self, client, write_mappings):
        resp = client.post("/api/partners", json={"label": "Test Partner"})
        assert resp.status_code == 201
        assert resp.json()["id"] == "test-partner"

    def test_slugify_special_chars(self, client, write_mappings):
        resp = client.post("/api/partners", json={"label": "A.B/C!D"})
        assert resp.status_code == 201
        assert resp.json()["id"] == "a-b-c-d"

    def test_slug_collision_suffix(self, client, write_mappings):
        # fixture-a doesn't exist yet (partner_a is the existing ID, not fixture-a)
        # so the first POST gets "fixture-a" without suffix. Trailing punctuation
        # keeps the label distinct from the seeded "Fixture A" (T042 duplicate
        # rejection) while slugifying identically.
        resp = client.post("/api/partners", json={"label": "Fixture A."})
        assert resp.status_code == 201
        assert resp.json()["id"] == "fixture-a"

    def test_slug_collision_double(self, client, write_mappings):
        # First POST gets "fixture-a"
        client.post("/api/partners", json={"label": "Fixture A."})
        # Second POST collides with first, gets "fixture-a-1"
        resp = client.post("/api/partners", json={"label": "Fixture A!"})
        assert resp.status_code == 201
        assert resp.json()["id"] == "fixture-a-1"

    def test_reserved_placeholder_label_400(self, client, write_mappings):
        """T042: label literally equal to a reserved placeholder is hard-invalid."""
        for reserved in ("Partner A", "Partner B", "partner a"):
            resp = client.post("/api/partners", json={"label": reserved})
            assert resp.status_code == 400
            assert "reserved placeholder" in resp.json()["detail"]

    def test_duplicate_label_400(self, client, write_mappings):
        """T042: case-insensitive duplicate of another partner's label → 400."""
        resp = client.post("/api/partners", json={"label": "fixture A"})
        assert resp.status_code == 400
        assert "duplicates" in resp.json()["detail"]

    def test_create_persists_to_file(self, client, write_mappings, tmp_private_dir):
        resp = client.post("/api/partners", json={"label": "New Partner"})
        assert resp.status_code == 201
        raw = json.loads(
            (tmp_private_dir / "account_mappings.json").read_text(encoding="utf-8")
        )
        assert "new-partner" in raw["partners"]
        assert raw["partners"]["new-partner"]["label"] == "New Partner"


# --------------------------------------------------------------------------- #
# AC15-AC16 — PUT /api/partners/{id}.
# --------------------------------------------------------------------------- #


class TestUpdatePartner:
    def test_ac15_update_200(self, client, write_mappings):
        resp = client.put("/api/partners/partner_a", json={"label": "Fixture Alpha"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "partner_a"
        assert body["label"] == "Fixture Alpha"

    def test_ac16_nonexistent_404(self, client, write_mappings):
        resp = client.put("/api/partners/nonexistent", json={"label": "X"})
        assert resp.status_code == 404
        assert resp.json()["detail"] == "partner not found"

    def test_update_duplicate_label_400(self, client, write_mappings):
        """T042: PUT renaming partner_a to partner_b's label → 400."""
        resp = client.put("/api/partners/partner_a", json={"label": "Fixture B"})
        assert resp.status_code == 400
        assert "duplicates" in resp.json()["detail"]

    def test_update_own_label_unchanged_ok(self, client, write_mappings):
        """Re-PUTting the same label is not a self-duplicate."""
        resp = client.put("/api/partners/partner_a", json={"label": "Fixture A"})
        assert resp.status_code == 200

    def test_update_empty_label_400(self, client, write_mappings):
        resp = client.put("/api/partners/partner_a", json={"label": ""})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "label is required"

    def test_update_no_alnum_400(self, client, write_mappings):
        resp = client.put("/api/partners/partner_a", json={"label": "!!!"})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "label must contain alphanumeric characters"

    def test_update_missing_label_field_400(self, client, write_mappings):
        resp = client.put("/api/partners/partner_a", json={})
        assert resp.status_code == 400

    def test_update_persists(self, client, write_mappings, tmp_private_dir):
        client.put("/api/partners/partner_a", json={"label": "Fixture Alpha"})
        raw = json.loads(
            (tmp_private_dir / "account_mappings.json").read_text(encoding="utf-8")
        )
        assert raw["partners"]["partner_a"]["label"] == "Fixture Alpha"


# --------------------------------------------------------------------------- #
# AC17-AC19 — DELETE /api/partners/{id}.
# --------------------------------------------------------------------------- #


class TestDeletePartner:
    def test_ac17_bound_accounts_409(self, client, write_mappings):
        # partner_a has bound accounts in sample_mappings.
        resp = client.delete("/api/partners/partner_a")
        assert resp.status_code == 409
        assert "accounts still bound" in resp.json()["detail"]

    def test_ac18_no_accounts_204(self, client, write_mappings):
        # partner_b has bound accounts in sample_mappings (5376190 = partner_b)
        # Create a new partner with no accounts.
        client.post("/api/partners", json={"label": "Lonely"})
        resp = client.delete("/api/partners/lonely")
        assert resp.status_code == 204

    def test_ac19_last_partner_409(self, client, tmp_private_dir):
        # Seed single partner.
        mappings = {
            "schema_version": 1,
            "partners": {"only": {"label": "Only"}},
            "accounts": {},
        }
        (tmp_private_dir / "account_mappings.json").write_text(
            json.dumps(mappings), encoding="utf-8"
        )
        resp = client.delete("/api/partners/only")
        assert resp.status_code == 409
        assert "last partner" in resp.json()["detail"]

    def test_delete_nonexistent_404(self, client, write_mappings):
        resp = client.delete("/api/partners/nonexistent")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "partner not found"

    def test_delete_persists(self, client, write_mappings, tmp_private_dir):
        client.post("/api/partners", json={"label": "Temp"})
        resp = client.delete("/api/partners/temp")
        assert resp.status_code == 204
        raw = json.loads(
            (tmp_private_dir / "account_mappings.json").read_text(encoding="utf-8")
        )
        assert "temp" not in raw["partners"]

    def test_bound_check_before_last_check(self, client, tmp_private_dir):
        """Bound accounts guard fires before last-partner guard."""
        mappings = {
            "schema_version": 1,
            "partners": {"only": {"label": "Only"}},
            "accounts": {"1": {"partner_id": "only", "type": None, "excluded": False}},
        }
        (tmp_private_dir / "account_mappings.json").write_text(
            json.dumps(mappings), encoding="utf-8"
        )
        resp = client.delete("/api/partners/only")
        # Bound accounts → 409 with accounts message, not last-partner.
        assert resp.status_code == 409
        assert "accounts still bound" in resp.json()["detail"]
