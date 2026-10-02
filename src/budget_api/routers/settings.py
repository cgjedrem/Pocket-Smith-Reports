"""Settings router — GET/PUT /api/settings/api-key, GET/PUT /api/settings/split."""

from __future__ import annotations

import json
import math

from fastapi import APIRouter, HTTPException, status

from budget_api.models.settings import (
    DEFAULT_SPLIT_CATEGORIES,
    DEFAULT_SPLIT_SHARES,
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

# report_builder (imported above) already put v4_pipeline on sys.path.
from accounting import (  # noqa: E402
    derive_split_sections,
    load_category_parents,
    load_detailed_section_mapping,
    migrate_legacy_split_sections,
)

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


def _validate_categories(categories: list[str], valid_category_ids: set[str] | None) -> None:
    """Unknown category ID -> 400. valid_category_ids=None (no catalog file
    on disk) skips the check — nothing to validate against, same
    permissive stance accounting.normalize_split_config takes."""
    if valid_category_ids is None:
        return
    invalid = sorted({c for c in categories if c not in valid_category_ids})
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid category id(s): {', '.join(invalid)}",
        )


def _load_catalog_context() -> tuple[dict[str, str | None] | None, dict | None]:
    """(category_parents, detailed_section_mapping) — None each when the
    backing private file doesn't exist yet (fresh install), mirroring the
    permissive load pattern used elsewhere (report_builder, mega_builder)."""
    category_parents = None
    if storage.CATEGORY_CATALOG_PATH.exists():
        category_parents = load_category_parents(storage.CATEGORY_CATALOG_PATH)
    detailed_section_mapping = None
    if storage.DETAILED_SECTION_MAPPING_PATH.exists():
        detailed_section_mapping = load_detailed_section_mapping(
            storage.DETAILED_SECTION_MAPPING_PATH
        )
    return category_parents, detailed_section_mapping


@router.get("/split", response_model=SplitConfigResponse)
def get_split_config() -> SplitConfigResponse:
    """Default (feature off, no categories preselected) when the config
    file is absent — never written to disk, just returned for the UI.

    `sections` is ALWAYS server-recomputed from `categories` on every GET
    (never trusted verbatim from disk) — categories is the source of
    truth, sections is a derived display field only. A legacy on-disk
    config with only `sections` (no `categories` key) is translated via
    accounting.migrate_legacy_split_sections (leaf-mapping translation,
    not catalog-tree expansion) before the same derive step runs, so the
    response always has both fields in the new shape regardless of what's
    stored on disk.

    Additive `labels` — real partner display names resolved the same way
    report_builder does (partner_labels.json, else account_mappings.json
    partners block via the sorted-slot map, else placeholders). Display-
    only: synthesized here on every GET, never written into
    split_config.json.

    Additive `warning` — set only when an on-disk legacy sections-only
    config can't be translated because detailed_section_mapping.json is
    missing. GET must never data-loss the user's saved selection (settings
    page silently showing an empty pick-list would look like the user's
    choice got wiped) — so in that case `sections` is returned AS-IS from
    disk and `categories` stays empty, with `warning` explaining why,
    instead of silently translating to []. Report-build time
    (accounting.normalize_split_config) intentionally does NOT mirror this
    leniency — it raises for the same missing-mapping condition, because
    that path computes real settlement numbers from the translation; a
    silent empty-categories there would be a silent miscalculation, not
    just a display gap.
    """
    try:
        raw = storage.read_json(storage.SPLIT_CONFIG_PATH)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="split_config.json is corrupt",
        )
    labels, _label_warnings = _load_partner_labels()
    category_parents, detailed_section_mapping = _load_catalog_context()
    if not isinstance(raw, dict):
        return SplitConfigResponse(
            enabled=False,
            shares=SplitShares(**DEFAULT_SPLIT_SHARES),
            categories=list(DEFAULT_SPLIT_CATEGORIES),
            sections=[],
            labels=labels,
        )
    warning: str | None = None
    if "categories" in raw:
        categories = list(raw.get("categories") or [])
        sections = derive_split_sections(
            categories, detailed_section_mapping, category_parents
        )
    elif "sections" in raw:
        legacy_sections = list(raw.get("sections") or [])
        if detailed_section_mapping is None:
            # Mapping sidecar missing/stale — can't translate leaf IDs.
            # Show the saved legacy sections as-is (no data-loss on GET),
            # categories stays empty (we genuinely don't know the IDs).
            categories = []
            sections = legacy_sections
            warning = (
                "detailed_section_mapping.json is missing — this legacy "
                "sections-only split config could not be translated to "
                "categories; showing the saved sections as-is. Report "
                "builds using this config will fail until the mapping "
                "file is restored."
            )
        else:
            # Legacy on-disk shape — translate once, on read.
            categories = migrate_legacy_split_sections(
                legacy_sections, detailed_section_mapping
            )
            sections = derive_split_sections(
                categories, detailed_section_mapping, category_parents
            )
    else:
        categories = list(DEFAULT_SPLIT_CATEGORIES)
        sections = derive_split_sections(
            categories, detailed_section_mapping, category_parents
        )
    return SplitConfigResponse(
        enabled=bool(raw.get("enabled", False)),
        shares=raw.get("shares", DEFAULT_SPLIT_SHARES),
        categories=categories,
        sections=sections,
        labels=labels,
        warning=warning,
    )


@router.put("/split", response_model=SplitConfig)
def update_split_config(update: SplitConfigUpdate) -> SplitConfig:
    """Validate + atomic-write split_config.json. Always re-validates
    shares/categories regardless of `enabled` — a later enable-toggle
    doesn't need a second round of validation on data already known-good.

    `sections` is server-computed from `categories` here and persisted
    alongside it (never accepted from the client — SplitConfigUpdate has
    no sections field)."""
    _validate_shares(update.shares)
    category_parents, detailed_section_mapping = _load_catalog_context()
    valid_category_ids = set(category_parents) if category_parents is not None else None
    # Dedupe, tolerated per design (order-preserving).
    categories = list(dict.fromkeys(update.categories))
    _validate_categories(categories, valid_category_ids)
    sections = derive_split_sections(
        categories, detailed_section_mapping, category_parents
    )
    config = SplitConfig(
        enabled=update.enabled,
        shares=update.shares,
        categories=categories,
        sections=sections,
    )
    storage.atomic_write_json(storage.SPLIT_CONFIG_PATH, config.model_dump())
    return config
