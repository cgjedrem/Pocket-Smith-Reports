"""Categories router — GET /api/categories (flat list), GET /api/categories/{id} (detail)."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, status

from budget_api.models.categories import Category, CategoryDetail, CategoryList
from budget_api.services import storage

router = APIRouter()


def _flatten(node: dict[str, Any], parent_id: str | None, out: list[Category]) -> None:
    """Recursive flatten — extract id (str), title, parent_id."""
    node_id = str(node.get("id"))
    title = str(node.get("title", ""))
    out.append(Category(id=node_id, title=title, parent_id=parent_id))
    children = node.get("children")
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                _flatten(child, node_id, out)


def _load_tree() -> list[dict[str, Any]]:
    """Read category_catalog.json → list of root category dicts. Empty if missing."""
    try:
        raw = storage.read_json(storage.CATEGORY_CATALOG_PATH)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="category_catalog.json is corrupt",
        )
    if not isinstance(raw, dict):
        return []
    categories = raw.get("categories")
    if not isinstance(categories, list):
        return []
    return [c for c in categories if isinstance(c, dict)]


def _find_node(nodes: list[dict[str, Any]], target_id: str) -> dict[str, Any] | None:
    """DFS search for node by id (str compare)."""
    for node in nodes:
        if str(node.get("id")) == target_id:
            return node
        children = node.get("children")
        if isinstance(children, list):
            found = _find_node([c for c in children if isinstance(c, dict)], target_id)
            if found is not None:
                return found
    return None


def _find_parent(
    nodes: list[dict[str, Any]], target_id: str, path: list[dict[str, Any]]
) -> list[dict[str, Any]] | None:
    """Return path (root..parent) for node with target_id. None if not found."""
    for node in nodes:
        if str(node.get("id")) == target_id:
            return path
        children = node.get("children")
        if isinstance(children, list):
            result = _find_parent(
                [c for c in children if isinstance(c, dict)], target_id, path + [node]
            )
            if result is not None:
                return result
    return None


@router.get("/categories", response_model=CategoryList)
def list_categories() -> CategoryList:
    """Flat category list. 404 if catalog missing."""
    if not storage.CATEGORY_CATALOG_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no categories — run sync first",
        )
    tree = _load_tree()
    out: list[Category] = []
    for root in tree:
        _flatten(root, None, out)
    return CategoryList(categories=out)


@router.get("/categories/{category_id}", response_model=CategoryDetail)
def get_category(category_id: str) -> CategoryDetail:
    """Category detail — self + direct children + parent path. 404 if not found."""
    if not storage.CATEGORY_CATALOG_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no categories — run sync first",
        )
    tree = _load_tree()
    node = _find_node(tree, category_id)
    if node is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="category not found",
        )

    # Direct children → Category list.
    children: list[Category] = []
    raw_children = node.get("children")
    if isinstance(raw_children, list):
        for child in raw_children:
            if isinstance(child, dict):
                children.append(
                    Category(
                        id=str(child.get("id")),
                        title=str(child.get("title", "")),
                        parent_id=str(node.get("id")),
                    )
                )

    # Parent path — root..parent, excluding self.
    # parent_path: derive parent_id from path position, not raw node field.
    # PS nodes are nested — parent_id field may be absent or unreliable.
    parent_chain = _find_parent(tree, category_id, [])
    parent_path: list[Category] = []
    if parent_chain is not None:
        for idx, ancestor in enumerate(parent_chain):
            # First ancestor = root → parent_id None. Others → previous ancestor's id.
            ancestor_parent_id = (
                str(parent_chain[idx - 1].get("id")) if idx > 0 else None
            )
            parent_path.append(
                Category(
                    id=str(ancestor.get("id")),
                    title=str(ancestor.get("title", "")),
                    parent_id=ancestor_parent_id,
                )
            )

    parent_id_raw = node.get("parent_id")
    return CategoryDetail(
        id=str(node.get("id")),
        title=str(node.get("title", "")),
        parent_id=str(parent_id_raw) if parent_id_raw is not None else None,
        children=children,
        parent_path=parent_path,
    )
