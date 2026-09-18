"""B14b — categories router tests. AC39-AC42, tree flatten, parent_path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# --------------------------------------------------------------------------- #
# AC39-AC40 — GET /api/categories.
# --------------------------------------------------------------------------- #


class TestListCategories:
    def test_ac39_list_after_sync_200(self, client, write_categories):
        resp = client.get("/api/categories")
        assert resp.status_code == 200
        body = resp.json()
        assert "categories" in body
        ids = [c["id"] for c in body["categories"]]
        # Root + children + grandchild all flattened.
        assert "100" in ids
        assert "110" in ids
        assert "111" in ids
        assert "120" in ids
        assert "200" in ids

    def test_ac40_never_synced_404(self, client, tmp_private_dir):
        resp = client.get("/api/categories")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "no categories — run sync first"

    def test_corrupt_catalog_500(self, client, tmp_private_dir):
        (tmp_private_dir / "category_catalog.json").write_text("{bad", encoding="utf-8")
        resp = client.get("/api/categories")
        assert resp.status_code == 500

    def test_tree_flatten_parent_ids(self, client, write_categories):
        resp = client.get("/api/categories")
        cats = {c["id"]: c for c in resp.json()["categories"]}
        # Root → parent_id None.
        assert cats["100"]["parent_id"] is None
        assert cats["200"]["parent_id"] is None
        # Child → parent_id = root id.
        assert cats["110"]["parent_id"] == "100"
        assert cats["120"]["parent_id"] == "100"
        # Grandchild → parent_id = child id.
        assert cats["111"]["parent_id"] == "110"

    def test_tree_flatten_count(self, client, write_categories):
        resp = client.get("/api/categories")
        # 2 roots + 2 children + 1 grandchild = 5.
        assert len(resp.json()["categories"]) == 5

    def test_empty_catalog_list(self, client, tmp_private_dir):
        (tmp_private_dir / "category_catalog.json").write_text(
            json.dumps({"start": "2026-07", "end": "2026-07", "categories": []}),
            encoding="utf-8",
        )
        resp = client.get("/api/categories")
        assert resp.status_code == 200
        assert resp.json() == {"categories": []}


# --------------------------------------------------------------------------- #
# AC41-AC42 — GET /api/categories/{id}.
# --------------------------------------------------------------------------- #


class TestGetCategory:
    def test_ac41_detail_with_children_and_path(self, client, write_categories):
        # Get child 110 — parent_path=[root 100], children=[grandchild 111].
        resp = client.get("/api/categories/110")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "110"
        assert body["title"] == "Child A1"
        # Direct children.
        assert len(body["children"]) == 1
        assert body["children"][0]["id"] == "111"
        # Parent path = root only.
        assert len(body["parent_path"]) == 1
        assert body["parent_path"][0]["id"] == "100"

    def test_ac41_root_detail(self, client, write_categories):
        resp = client.get("/api/categories/100")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "100"
        # Root has 2 direct children.
        assert len(body["children"]) == 2
        child_ids = [c["id"] for c in body["children"]]
        assert "110" in child_ids
        assert "120" in child_ids
        # Root parent_path empty.
        assert body["parent_path"] == []

    def test_ac41_grandchild_detail(self, client, write_categories):
        # Grandchild 111 — parent_path = [root 100, child 110].
        resp = client.get("/api/categories/111")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "111"
        assert len(body["parent_path"]) == 2
        assert body["parent_path"][0]["id"] == "100"
        assert body["parent_path"][1]["id"] == "110"
        # No children.
        assert body["children"] == []

    def test_ac42_not_found_404(self, client, write_categories):
        resp = client.get("/api/categories/999999")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "category not found"

    def test_detail_never_synced_404(self, client, tmp_private_dir):
        resp = client.get("/api/categories/100")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "no categories — run sync first"

    def test_parent_path_chain_titles(self, client, write_categories):
        resp = client.get("/api/categories/111")
        path = resp.json()["parent_path"]
        titles = [c["title"] for c in path]
        assert titles == ["Root A", "Child A1"]

    def test_parent_path_parent_ids(self, client, write_categories):
        """parent_path entries have correct parent_id chain."""
        resp = client.get("/api/categories/111")
        path = resp.json()["parent_path"]
        # Root → parent_id None. Child → parent_id = root id.
        assert path[0]["parent_id"] is None
        assert path[1]["parent_id"] == "100"
