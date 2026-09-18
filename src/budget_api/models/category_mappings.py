"""Category mapping models — KPI roles, detailed sections, CRUD models."""

from __future__ import annotations

from pydantic import BaseModel

# KPI roles (category_roles.json) — 6 values
KPI_ROLES = {"income", "savings", "spend", "personal_spend", "investment", "exclude"}

# Detailed section mapping (detailed_section_mapping.json) — 10 values
DETAILED_CATEGORY_SECTIONS = {
    "income_salary",
    "income_third_party",
    "savings",
    "home",
    "common",
    "personal_partner_a",
    "personal_partner_b",
    "trips",
    "cc_payments",
    "excluded",
}


class CategoryMapping(BaseModel):
    """One category — id, title, kpi_role, detailed_section."""

    category_id: str
    category_title: str
    kpi_role: str | None
    detailed_section: str | None


class CategoryMappingList(BaseModel):
    """GET /api/category-mappings — merged list."""

    categories: list[CategoryMapping]


class CategoryMappingUpdate(BaseModel):
    """PUT /api/category-mappings/{id} — update both role + section."""

    kpi_role: str
    detailed_section: str
