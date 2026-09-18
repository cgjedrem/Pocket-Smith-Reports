"""Category mappings router — GET (merge 3 files), PUT (update 2 files)."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, status

from budget_api.models.category_mappings import (
    DETAILED_CATEGORY_SECTIONS,
    KPI_ROLES,
    CategoryMapping,
    CategoryMappingList,
    CategoryMappingUpdate,
)
from budget_api.services import storage

router = APIRouter()


def _flatten_titles(nodes: list[dict[str, Any]], out: dict[str, str]) -> None:
    """Recursive flatten — id → title."""
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id"))
        title = str(node.get("title", ""))
        out[node_id] = title
        children = node.get("children")
        if isinstance(children, list):
            _flatten_titles(children, out)


def _load_category_titles() -> dict[str, str]:
    """Read category_catalog.json → id→title map. Empty if missing."""
    if not storage.CATEGORY_CATALOG_PATH.exists():
        return {}
    try:
        raw = storage.read_json(storage.CATEGORY_CATALOG_PATH)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="category_catalog.json is corrupt",
        )
    if not isinstance(raw, dict):
        return {}
    categories = raw.get("categories")
    if not isinstance(categories, list):
        return {}
    titles: dict[str, str] = {}
    _flatten_titles(categories, titles)
    return titles


@router.get("/category-mappings", response_model=CategoryMappingList)
def list_category_mappings() -> CategoryMappingList:
    """Merge category_roles + detailed_section_mapping + category_catalog.

    404 if no categories (catalog missing).
    """
    if not storage.CATEGORY_CATALOG_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no categories — run sync first",
        )

    titles = _load_category_titles()
    if not titles:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no categories — run sync first",
        )

    # Load KPI roles — category_id → role.
    roles: dict[str, str] = {}
    if storage.CATEGORY_ROLES_PATH.exists():
        raw_roles = storage.read_json(storage.CATEGORY_ROLES_PATH)
        if isinstance(raw_roles, dict):
            roles = {str(k): str(v) for k, v in raw_roles.items()}

    # Load detailed sections — nested {category_sections, account_roles}.
    sections: dict[str, str] = {}
    if storage.DETAILED_SECTION_MAPPING_PATH.exists():
        raw_sections = storage.read_json(storage.DETAILED_SECTION_MAPPING_PATH)
        if isinstance(raw_sections, dict):
            cat_sections = raw_sections.get("category_sections", {})
            if isinstance(cat_sections, dict):
                sections = {str(k): str(v) for k, v in cat_sections.items()}

    # Merge — all categories from catalog, attach role + section if present.
    mappings = []
    for cat_id, title in sorted(titles.items(), key=lambda item: item[1]):
        mappings.append(
            CategoryMapping(
                category_id=cat_id,
                category_title=title,
                kpi_role=roles.get(cat_id),
                detailed_section=sections.get(cat_id),
            )
        )
    return CategoryMappingList(categories=mappings)


@router.put("/category-mappings/{category_id}", response_model=CategoryMapping)
def update_category_mapping(
    category_id: str, update: CategoryMappingUpdate
) -> CategoryMapping:
    """Update KPI role + detailed section for one category.

    Validates role + section. Writes to category_roles.json + detailed_section_mapping.json.
    Preserves nested structure {category_sections, account_roles}.
    """
    # Validate role.
    if update.kpi_role not in KPI_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid kpi_role",
        )
    # Validate section.
    if update.detailed_section not in DETAILED_CATEGORY_SECTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid detailed_section",
        )

    # 404 if category not in catalog.
    titles = _load_category_titles()
    if category_id not in titles:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="category not found",
        )

    # Update category_roles.json — load, update, write.
    roles: dict[str, str] = {}
    if storage.CATEGORY_ROLES_PATH.exists():
        raw_roles = storage.read_json(storage.CATEGORY_ROLES_PATH)
        if isinstance(raw_roles, dict):
            roles = {str(k): str(v) for k, v in raw_roles.items()}
    roles[category_id] = update.kpi_role
    storage.atomic_write_json(storage.CATEGORY_ROLES_PATH, roles)

    # Update detailed_section_mapping.json — preserve nested structure.
    sections_data: dict[str, Any] = {"account_roles": {}, "category_sections": {}}
    if storage.DETAILED_SECTION_MAPPING_PATH.exists():
        raw_sections = storage.read_json(storage.DETAILED_SECTION_MAPPING_PATH)
        if isinstance(raw_sections, dict):
            sections_data = raw_sections
    # Ensure both keys present.
    if "account_roles" not in sections_data:
        sections_data["account_roles"] = {}
    if "category_sections" not in sections_data:
        sections_data["category_sections"] = {}
    sections_data["category_sections"][category_id] = update.detailed_section
    storage.atomic_write_json(storage.DETAILED_SECTION_MAPPING_PATH, sections_data)

    return CategoryMapping(
        category_id=category_id,
        category_title=titles[category_id],
        kpi_role=update.kpi_role,
        detailed_section=update.detailed_section,
    )
