"""Unit tests — category_mappings router (list, update, validation, 404)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from budget_api.services import storage


def _mock_catalog() -> dict:
    """Category catalog with 3 categories."""
    return {
        "start": "2026-07",
        "end": "2026-07",
        "categories": [
            {
                "id": 100,
                "title": "Groceries",
                "parent_id": None,
                "children": [
                    {
                        "id": 110,
                        "title": "Supermarket",
                        "parent_id": 100,
                        "children": [],
                    },
                ],
            },
            {
                "id": 200,
                "title": "Income",
                "parent_id": None,
                "children": [],
            },
        ],
    }


def _mock_roles() -> dict:
    return {"100": "spend", "110": "spend"}


def _mock_sections() -> dict:
    return {
        "account_roles": {},
        "category_sections": {"100": "common", "110": "common"},
    }


@pytest.fixture
def seeded_mappings(tmp_private_dir: Path) -> Path:
    """Seed catalog + roles + sections."""
    (tmp_private_dir / "category_catalog.json").write_text(
        json.dumps(_mock_catalog()), encoding="utf-8"
    )
    (tmp_private_dir / "category_roles.json").write_text(
        json.dumps(_mock_roles()), encoding="utf-8"
    )
    (tmp_private_dir / "detailed_section_mapping.json").write_text(
        json.dumps(_mock_sections()), encoding="utf-8"
    )
    return tmp_private_dir


# --------------------------------------------------------------------------- #
# GET /api/category-mappings
# --------------------------------------------------------------------------- #


class TestListMappings:
    def test_list_with_data(self, client, seeded_mappings):
        """AC16: categories synced → 200, list with titles + roles."""
        resp = client.get("/api/category-mappings")
        assert resp.status_code == 200
        cats = resp.json()["categories"]
        assert len(cats) == 3
        # Check merge — title from catalog, role from roles.
        cat100 = next(c for c in cats if c["category_id"] == "100")
        assert cat100["category_title"] == "Groceries"
        assert cat100["kpi_role"] == "spend"
        assert cat100["detailed_section"] == "common"

    def test_list_no_catalog_404(self, client, tmp_private_dir):
        """AC17: no categories → 404."""
        resp = client.get("/api/category-mappings")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "no categories — run sync first"

    def test_list_no_roles_file(self, client, tmp_private_dir):
        """Catalog exists but no roles file → 200, roles=None."""
        (tmp_private_dir / "category_catalog.json").write_text(
            json.dumps(_mock_catalog()), encoding="utf-8"
        )
        resp = client.get("/api/category-mappings")
        assert resp.status_code == 200
        cats = resp.json()["categories"]
        assert all(c["kpi_role"] is None for c in cats)


# --------------------------------------------------------------------------- #
# PUT /api/category-mappings/{id}
# --------------------------------------------------------------------------- #


class TestUpdateMapping:
    def test_update_success(self, client, seeded_mappings):
        """AC18: valid update → 200, updated mapping."""
        resp = client.put(
            "/api/category-mappings/100",
            json={"kpi_role": "income", "detailed_section": "income_salary"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["category_id"] == "100"
        assert body["kpi_role"] == "income"
        assert body["detailed_section"] == "income_salary"

        # Verify files written.
        roles = json.loads(
            (storage.PRIVATE_DATA_DIR / "category_roles.json").read_text(
                encoding="utf-8"
            )
        )
        assert roles["100"] == "income"
        sections = json.loads(
            (storage.DETAILED_SECTION_MAPPING_PATH).read_text(encoding="utf-8")
        )
        assert sections["category_sections"]["100"] == "income_salary"
        # Nested structure preserved.
        assert "account_roles" in sections

    def test_update_invalid_kpi_role_400(self, client, seeded_mappings):
        """AC19: invalid kpi_role → 400."""
        resp = client.put(
            "/api/category-mappings/100",
            json={"kpi_role": "invalid", "detailed_section": "common"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "invalid kpi_role"

    def test_update_invalid_section_400(self, client, seeded_mappings):
        """AC20: invalid detailed_section → 400."""
        resp = client.put(
            "/api/category-mappings/100",
            json={"kpi_role": "income", "detailed_section": "invalid"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "invalid detailed_section"

    def test_update_category_not_found_404(self, client, seeded_mappings):
        """AC21: nonexistent category → 404."""
        resp = client.put(
            "/api/category-mappings/999",
            json={"kpi_role": "income", "detailed_section": "income_salary"},
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "category not found"

    def test_update_preserves_nested_structure(self, client, seeded_mappings):
        """PUT preserves account_roles in detailed_section_mapping.json."""
        # Add account_roles to sections.
        sections = _mock_sections()
        sections["account_roles"] = {"4110213": "savings_partner_a"}
        (storage.DETAILED_SECTION_MAPPING_PATH).write_text(
            json.dumps(sections), encoding="utf-8"
        )
        resp = client.put(
            "/api/category-mappings/100",
            json={"kpi_role": "savings", "detailed_section": "savings"},
        )
        assert resp.status_code == 200
        updated = json.loads(
            (storage.DETAILED_SECTION_MAPPING_PATH).read_text(encoding="utf-8")
        )
        # account_roles preserved.
        assert updated["account_roles"]["4110213"] == "savings_partner_a"
        assert updated["category_sections"]["100"] == "savings"

    def test_update_no_existing_roles_file(self, client, tmp_private_dir):
        """Update creates roles file if it doesn't exist."""
        (tmp_private_dir / "category_catalog.json").write_text(
            json.dumps(_mock_catalog()), encoding="utf-8"
        )
        resp = client.put(
            "/api/category-mappings/100",
            json={"kpi_role": "income", "detailed_section": "income_salary"},
        )
        assert resp.status_code == 200
        roles = json.loads((storage.CATEGORY_ROLES_PATH).read_text(encoding="utf-8"))
        assert roles["100"] == "income"
