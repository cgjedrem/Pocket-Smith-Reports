"""Settings pydantic models — ApiKeyStatus, ApiKeyUpdate."""

from __future__ import annotations

from pydantic import BaseModel


class ApiKeyStatus(BaseModel):
    """GET /api/settings/api-key — configured flag only, never raw key."""

    configured: bool


class ApiKeyUpdate(BaseModel):
    """PUT /api/settings/api-key body — api_key validated manually in router."""

    api_key: str
