"""Accounts router — GET /api/accounts (merge), PUT /api/accounts/{id}/binding."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, status

from budget_api.models.accounts import Account, AccountBindingUpdate, AccountList
from budget_api.services import storage

router = APIRouter()

# Fix 3 — allow-list for manual type validation (pydantic Literal removed).
_VALID_TYPES = ("checking", "cc", "savings")


def _load_mappings() -> dict[str, Any]:
    """Read account_mappings.json. Normalize structure."""
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


def _load_catalog_accounts() -> list[dict[str, Any]]:
    """Read account_catalog.json → list of PS account dicts (id, name)."""
    try:
        raw = storage.read_json(storage.ACCOUNT_CATALOG_PATH)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="account_catalog.json is corrupt",
        )
    if not isinstance(raw, dict):
        return []
    accounts = raw.get("accounts")
    if not isinstance(accounts, list):
        return []
    return [a for a in accounts if isinstance(a, dict) and a.get("id") is not None]


@router.get("/accounts", response_model=AccountList)
def list_accounts() -> AccountList:
    """Merge PS catalog + local bindings. Unbound → partner_id=null, type=null, excluded=false."""
    catalog_accounts = _load_catalog_accounts()
    mappings = _load_mappings()
    bindings = mappings["accounts"]

    out: list[Account] = []
    for ps_account in catalog_accounts:
        account_id = str(ps_account["id"])
        name = str(ps_account.get("name", ""))
        binding = bindings.get(account_id)
        if isinstance(binding, dict):
            partner_id = binding.get("partner_id")
            account_type = binding.get("type")
            excluded = bool(binding.get("excluded", False))
        else:
            partner_id = None
            account_type = None
            excluded = False
        out.append(
            Account(
                id=account_id,
                name=name,
                partner_id=partner_id if isinstance(partner_id, str) else None,
                type=account_type if isinstance(account_type, str) else None,
                excluded=excluded,
            )
        )
    return AccountList(accounts=out)


@router.put("/accounts/{account_id}/binding", response_model=Account)
def update_binding(account_id: str, body: AccountBindingUpdate) -> Account:
    """Full-replace binding. Validate partner_id + account existence."""
    mappings = _load_mappings()
    partners = mappings["partners"]
    accounts = mappings["accounts"]

    # Validate partner_id exists (if not null).
    if body.partner_id is not None and body.partner_id not in partners:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid partner_id",
        )
    # Fix 3 — manual type validation (pydantic Literal removed).
    if body.type is not None and body.type not in _VALID_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid type",
        )

    # Account must exist in PS catalog.
    catalog_accounts = _load_catalog_accounts()
    catalog_ids = {str(a["id"]) for a in catalog_accounts}
    if account_id not in catalog_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="account not found",
        )

    # Full replace — preserve name from existing binding or catalog.
    existing = accounts.get(account_id)
    if isinstance(existing, dict):
        name = str(existing.get("name", ""))
    else:
        name = ""
        for a in catalog_accounts:
            if str(a["id"]) == account_id:
                name = str(a.get("name", ""))
                break

    accounts[account_id] = {
        "name": name,
        "partner_id": body.partner_id,
        "type": body.type,
        "excluded": body.excluded,
    }
    _save_mappings(mappings)

    return Account(
        id=account_id,
        name=name,
        partner_id=body.partner_id,
        type=body.type,
        excluded=body.excluded,
    )
