"""Partner pydantic models — Partner, PartnerCreate, PartnerUpdate, PartnerList."""

from __future__ import annotations

from pydantic import BaseModel


class Partner(BaseModel):
    """Stored partner — id slugified from label."""

    id: str
    label: str


class PartnerCreate(BaseModel):
    """POST /api/partners body — label validated manually in router."""

    label: str


class PartnerUpdate(BaseModel):
    """PUT /api/partners/{id} body — label validated manually in router."""

    label: str


class PartnerList(BaseModel):
    """GET /api/partners response."""

    partners: list[Partner]
