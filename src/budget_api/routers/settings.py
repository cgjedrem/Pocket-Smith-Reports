"""Settings router — GET/PUT /api/settings/api-key, GET/PUT /api/settings/split."""

from __future__ import annotations

import json
import math

from fastapi import APIRouter, HTTPException, status

from budget_api.models.settings import (
    DEFAULT_SPLIT_SECTIONS,
    DEFAULT_SPLIT_SHARES,
    SPLIT_ELIGIBLE_SECTIONS,
    ApiKeyStatus,
    ApiKeyUpdate,
    SplitConfig,
    SplitConfigResponse,
    SplitConfigUpdate,
    SplitShares,
)
from budget_api.services import env_writer
from budget_api.services.ps_client import PSClient, PSClientError
from budget_api.services import storage
from budget_api.services.report_builder import _load_partner_labels

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


# --------------------------------------------------------------------------- #
# Common-economy split — GET/PUT /api/settings/split.
# --------------------------------------------------------------------------- #


def _validate_shares(shares: SplitShares) -> None:
    """0..100 each -> 400; sum != 100 (tolerance 1e-6) -> 422 (design doc:
    'must sum to exactly 100% — PUT rejects otherwise, 422').

    NaN/Inf fail every range/sum comparison below silently (NaN < 0 is
    False, NaN > 100 is False, abs(NaN - 100) > 1e-6 is False) — pydantic's
    plain `float` field accepts them (JSON NaN/Infinity literals parse fine
    via stdlib json), so reject non-finite explicitly first, before any
    range/sum math runs.
    """
    for name, value in (("partner_a", shares.partner_a), ("partner_b", shares.partner_b)):
        if not math.isfinite(value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"shares.{name} must be a finite number",
            )
        if value < 0 or value > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"shares.{name} must be between 0 and 100",
            )
    total = shares.partner_a + shares.partner_b
    if abs(total - 100.0) > 1e-6:
        # Literal 422 — HTTP_422_UNPROCESSABLE_ENTITY is deprecated in this
        # Starlette version (renamed …_CONTENT); avoid the warning noise.
        raise HTTPException(
            status_code=422,
            detail="shares must sum to exactly 100",
        )


def _validate_sections(sections: list[str]) -> None:
    """Unknown section key -> 400."""
    invalid = sorted({s for s in sections if s not in SPLIT_ELIGIBLE_SECTIONS})
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid section(s): {', '.join(invalid)}",
        )


@router.get("/split", response_model=SplitConfigResponse)
def get_split_config() -> SplitConfigResponse:
    """Default (feature off, candidate sections pre-filled) when the config
    file is absent — never written to disk, just returned for the UI.

    Additive `labels` — real partner display names resolved the same way
    report_builder does (partner_labels.json, else account_mappings.json
    partners block via the sorted-slot map, else placeholders). Display-
    only: synthesized here on every GET, never written into
    split_config.json (the persisted shape stays enabled/shares/sections).
    """
    try:
        raw = storage.read_json(storage.SPLIT_CONFIG_PATH)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="split_config.json is corrupt",
        )
    labels, _label_warnings = _load_partner_labels()
    if not isinstance(raw, dict):
        return SplitConfigResponse(
            enabled=False,
            shares=SplitShares(**DEFAULT_SPLIT_SHARES),
            sections=list(DEFAULT_SPLIT_SECTIONS),
            labels=labels,
        )
    return SplitConfigResponse(**raw, labels=labels)


@router.put("/split", response_model=SplitConfig)
def update_split_config(update: SplitConfigUpdate) -> SplitConfig:
    """Validate + atomic-write split_config.json. Always re-validates shares/
    sections regardless of `enabled` — a later enable-toggle doesn't need a
    second round of validation on data already known-good."""
    _validate_shares(update.shares)
    _validate_sections(update.sections)
    config = SplitConfig(
        enabled=update.enabled, shares=update.shares, sections=update.sections
    )
    storage.atomic_write_json(storage.SPLIT_CONFIG_PATH, config.model_dump())
    return config
