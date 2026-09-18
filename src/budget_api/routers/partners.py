"""Partners router — CRUD on account_mappings.json["partners"]."""

from __future__ import annotations

import json
import re
from typing import Any

from fastapi import APIRouter, HTTPException, status

from budget_api.models.partners import (
    Partner,
    PartnerCreate,
    PartnerList,
    PartnerUpdate,
)
from budget_api.services import storage
from budget_api.services.report_builder import validate_partner_labels

router = APIRouter()


def _slugify(label: str) -> str:
    """Label → slug id. Lowercase, non-alnum → hyphen, strip leading/trailing hyphens."""
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return slug


def _load_mappings() -> dict[str, Any]:
    """Read account_mappings.json. Return normalized dict (empty structure if missing)."""
    try:
        raw = storage.read_json(storage.ACCOUNT_MAPPING_PATH)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="account_mappings.json is corrupt",
        )
    if not isinstance(raw, dict):
        return {"schema_version": 1, "partners": {}, "accounts": {}}
    raw.setdefault("partners", {})
    raw.setdefault("accounts", {})
    if not isinstance(raw["partners"], dict):
        raw["partners"] = {}
    if not isinstance(raw["accounts"], dict):
        raw["accounts"] = {}
    return raw


def _save_mappings(mappings: dict[str, Any]) -> None:
    """Atomic write account_mappings.json."""
    storage.atomic_write_json(storage.ACCOUNT_MAPPING_PATH, mappings)


def _partners_dict(mappings: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Partners sub-dict (id → {label})."""
    return mappings["partners"]  # type: ignore[no-any-return]


def _accounts_bound_to(mappings: dict[str, Any], partner_id: str) -> list[str]:
    """Account ids bound to given partner."""
    accounts = mappings["accounts"]
    bound: list[str] = []
    for account_id, entry in accounts.items():
        if isinstance(entry, dict) and entry.get("partner_id") == partner_id:
            bound.append(account_id)
    return bound


def _validate_label_or_400(
    label: str, partners: dict[str, dict[str, str]], exclude_id: str | None = None
) -> None:
    """Hard-invalid label checks on the settings write path (T042).

    Uses the canonical validator's rules: a label that is the reserved
    placeholder value (literally "Partner A/B") or a case-insensitive
    duplicate of another partner's label is rejected with 400 rather than
    silently degraded on the read path.
    """
    probe = {"partner_a": "~distinct-probe-value~", "partner_b": label}
    _, warnings = validate_partner_labels(probe)
    rejected = [w for w in warnings if "'partner_b'" in w]
    if rejected:
        # The validator's read-path message says "truncated"; on the write
        # path the label is rejected outright, so say so.
        detail = rejected[0].replace("; truncated", "; rejected")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid partner label: {detail}",
        )
    for pid, entry in partners.items():
        if pid == exclude_id or not isinstance(entry, dict):
            continue
        if str(entry.get("label", "")).strip().lower() == label.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="label duplicates another partner's label",
            )


@router.get("/partners", response_model=PartnerList)
def list_partners() -> PartnerList:
    """List all partners."""
    mappings = _load_mappings()
    partners = _partners_dict(mappings)
    items = [
        Partner(id=str(pid), label=str(entry.get("label", "")))
        for pid, entry in partners.items()
        if isinstance(entry, dict)
    ]
    return PartnerList(partners=items)


@router.post(
    "/partners",
    response_model=Partner,
    status_code=status.HTTP_201_CREATED,
)
def create_partner(body: PartnerCreate) -> Partner:
    """Create partner. Slugify label → id. 400 if label empty/whitespace or no alnum."""
    if not body.label or not body.label.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="label is required",
        )
    label = body.label.strip()
    mappings = _load_mappings()
    partners = _partners_dict(mappings)
    _validate_label_or_400(label, partners)
    partner_id = _slugify(label)
    if not partner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="label must contain alphanumeric characters",
        )
    # Idempotent-ish: if slug exists, append numeric suffix to avoid collision.
    base = partner_id
    suffix = 1
    while partner_id in partners:
        partner_id = f"{base}-{suffix}"
        suffix += 1
    partners[partner_id] = {"label": label}
    _save_mappings(mappings)
    return Partner(id=partner_id, label=label)


@router.put("/partners/{partner_id}", response_model=Partner)
def update_partner(partner_id: str, body: PartnerUpdate) -> Partner:
    """Update partner label. 404 if not found. 400 if label empty/whitespace or no alnum."""
    if not body.label or not body.label.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="label is required",
        )
    label = body.label.strip()
    if not _slugify(label):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="label must contain alphanumeric characters",
        )
    mappings = _load_mappings()
    partners = _partners_dict(mappings)
    if partner_id not in partners:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="partner not found",
        )
    _validate_label_or_400(label, partners, exclude_id=partner_id)
    partners[partner_id]["label"] = label
    _save_mappings(mappings)
    return Partner(id=partner_id, label=label)


@router.delete("/partners/{partner_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_partner(partner_id: str) -> None:
    """Delete partner. 404 if not found. 409 if accounts bound or last partner."""
    mappings = _load_mappings()
    partners = _partners_dict(mappings)
    if partner_id not in partners:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="partner not found",
        )
    # Fix 5 — bound accounts guard FIRST, then last-partner guard.
    if _accounts_bound_to(mappings, partner_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="cannot delete partner — accounts still bound",
        )
    if len(partners) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="cannot delete last partner",
        )
    del partners[partner_id]
    _save_mappings(mappings)
