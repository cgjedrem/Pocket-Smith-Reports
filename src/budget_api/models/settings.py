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
# Gate 1, category-level selection Gate 2). One global partner_a/partner_b %
# pair (sums to 100) + which CATEGORY IDs participate (any catalog tree
# level — a selected parent expands to its descendants at report-build
# time). Slot-keyed (partner_a/partner_b), not real partner IDs — settlement
# resolves real labels one layer up (report_builder).
# --------------------------------------------------------------------------- #

# Legacy candidate sections (Gate 1) — no longer an eligibility restriction
# on `categories` (the split picker lists every catalog category). Kept for
# migrating an old sections-only split_config.json and for the derived
# `sections` display field's known-good vocabulary. Twin of
# accounting.SPLIT_ELIGIBLE_SECTIONS (keep in sync — v4_pipeline cannot
# import budget_api, so this is not import-shared).
SPLIT_ELIGIBLE_SECTIONS = {"home", "common", "trips"}

# Missing split_config.json default — feature off, no categories preselected
# (with every catalog category eligible there's no sensible default subset;
# the user picks explicitly once they enable the feature).
DEFAULT_SPLIT_SHARES = {"partner_a": 50.0, "partner_b": 50.0}
DEFAULT_SPLIT_CATEGORIES: list[str] = []


class SplitShares(BaseModel):
    """Global per-partner percentage pair — must sum to exactly 100."""

    partner_a: float
    partner_b: float


class SplitConfig(BaseModel):
    """GET/PUT /api/settings/split — global split config.

    enabled=False means the feature is off (detailed.split stays None on
    monthly/mega reports) regardless of what shares/categories hold.

    categories: source of truth — any catalog category ID, any tree level
    (parent selection implies its descendants at report-build time).
    sections: derived/back-compat field — the distinct
    home/common/trips/personal_*/... sections `categories` maps to, server-
    computed (never client-supplied) and persisted alongside `categories`
    for readers that still expect a sections list.
    """

    enabled: bool
    shares: SplitShares
    categories: list[str]
    sections: list[str] = []


class SplitConfigUpdate(BaseModel):
    """PUT /api/settings/split body — categories is the write contract;
    sections is NOT accepted from the client (router computes + persists it
    from categories). Validated in the router (shares sum to 100 -> 422,
    unknown category ID -> 400)."""

    enabled: bool
    shares: SplitShares
    categories: list[str]


class SplitConfigResponse(SplitConfig):
    """GET /api/settings/split response — SplitConfig + display-only real
    partner labels for slot->name resolution in the settings UI.

    labels: {partner_a: <real label>, partner_b: <real label>} resolved via
    the same _partner_slot_map + label loader path report_builder uses
    (report_builder._load_partner_labels). Display-only — never persisted
    to split_config.json (SplitConfig/SplitConfigUpdate stay unchanged, so
    the write path can't leak this field into the stored file).

    warning: additive, machine-readable, None in the normal case. Set when
    an on-disk legacy sections-only config can't be translated to
    categories because detailed_section_mapping.json is missing —
    settings-page GET must never data-loss the user's saved selection just
    because a sidecar file is stale/absent (iteration 4, finding 2). Report
    build (accounting.normalize_split_config) intentionally keeps the
    stricter behavior and RAISES in this same situation instead — that path
    computes real numbers from the translation, a silent/best-effort result
    there would be a silent miscalculation, not just a display gap.
    """

    labels: dict[str, str]
    warning: str | None = None
