"""Error pydantic model — unified ErrorResponse."""

from __future__ import annotations

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """All non-2xx responses return {"detail": "message"}."""

    detail: str
