"""Settings router — GET/PUT /api/settings/api-key."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from budget_api.models.settings import ApiKeyStatus, ApiKeyUpdate
from budget_api.services import env_writer
from budget_api.services.ps_client import PSClient, PSClientError

router = APIRouter()


@router.get("/api-key", response_model=ApiKeyStatus)
def get_api_key_status() -> ApiKeyStatus:
    """Configured flag only. Never returns raw key."""
    return ApiKeyStatus(configured=env_writer.read_api_key_configured())


@router.put("/api-key", response_model=ApiKeyStatus)
def update_api_key(body: ApiKeyUpdate) -> ApiKeyStatus:
    """Write key atomically, validate via PS /me. No rollback — clean cut."""
    # Manual validation — pydantic no longer constrains (Fix 2/3).
    if not body.api_key or not body.api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="api_key is required",
        )
    key_value = body.api_key.strip()
    try:
        env_writer.write_api_key(key_value)
    except OSError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to write .env",
        )

    # Validate via PS /me.
    try:
        client = PSClient(key_value)
        client.get_me()
        return ApiKeyStatus(configured=True)
    except PSClientError as error:
        message = str(error)
        # Auth rejection.
        if "auth failed" in message or "forbidden" in message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PS API rejected key",
            )
        # Unreachable / network / timeout.
        if (
            "network error" in message
            or "timeout" in message
            or "unavailable" in message
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PS API unreachable — cannot validate key",
            )
        # Other PS errors — surface message.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )
