"""Settings pydantic models — ApiKeyStatus, ApiKeyUpdate, split config."""

from __future__ import annotations

from pydantic import BaseModel


class ApiKeyStatus(BaseModel):
    """GET /api/settings/api-key — configured flag only, never raw key."""

    configured: bool


class ApiKeyUpdate(BaseModel):
    """PUT /api/settings/api-key body — api_key validated manually in router."""

    api_key: str


# --------------------------------------------------------------------------- #
# Common-economy split — global % config (design doc "common economy split"
# Gate 1). One global partner_a/partner_b % pair (sums to 100) + which
# category sections participate. Slot-keyed (partner_a/partner_b), not real
# partner IDs — settlement resolves real labels one layer up (report_builder).
# --------------------------------------------------------------------------- #

# Candidate sections today. Subset of
# budget_api.models.category_mappings.DETAILED_CATEGORY_SECTIONS: only
# sections shaped like a NetSection (per-category paid/received per partner)
# can feed compute_split. Twin of accounting.SPLIT_ELIGIBLE_SECTIONS (keep in
# sync — v4_pipeline cannot import budget_api, so this is not import-shared).
SPLIT_ELIGIBLE_SECTIONS = {"home", "common", "trips"}

# Missing split_config.json default — feature off, sections default to all
# 3 candidates once the user enables (hard constraint 5).
DEFAULT_SPLIT_SHARES = {"partner_a": 50.0, "partner_b": 50.0}
DEFAULT_SPLIT_SECTIONS = ["home", "common", "trips"]


class SplitShares(BaseModel):
    """Global per-partner percentage pair — must sum to exactly 100."""

    partner_a: float
    partner_b: float


class SplitConfig(BaseModel):
    """GET/PUT /api/settings/split — global split config.

    enabled=False means the feature is off (detailed.split stays None on
    monthly/mega reports) regardless of what shares/sections hold.
    """

    enabled: bool
    shares: SplitShares
    sections: list[str]


class SplitConfigUpdate(BaseModel):
    """PUT /api/settings/split body — same shape as SplitConfig, validated
    in the router (shares sum to 100 -> 422, unknown section -> 400)."""

    enabled: bool
    shares: SplitShares
    sections: list[str]


class SplitConfigResponse(SplitConfig):
    """GET /api/settings/split response — SplitConfig + display-only real
    partner labels for slot->name resolution in the settings UI.

    labels: {partner_a: <real label>, partner_b: <real label>} resolved via
    the same _partner_slot_map + label loader path report_builder uses
    (report_builder._load_partner_labels). Display-only — never persisted
    to split_config.json (SplitConfig/SplitConfigUpdate stay unchanged, so
    the write path can't leak this field into the stored file).
    """

    labels: dict[str, str]
