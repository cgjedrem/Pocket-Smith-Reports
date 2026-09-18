"""Category pydantic models — Category, CategoryDetail, CategoryList."""

from __future__ import annotations

from pydantic import BaseModel


class Category(BaseModel):
    """Flat category — id str, title, parent_id (None=root)."""

    id: str
    title: str
    parent_id: str | None


class CategoryDetail(BaseModel):
    """GET /api/categories/{id} — self + direct children + parent chain."""

    id: str
    title: str
    parent_id: str | None
    children: list[Category]
    parent_path: list[Category]


class CategoryList(BaseModel):
    """GET /api/categories — flat list, tree built client-side via parent_id."""

    categories: list[Category]
