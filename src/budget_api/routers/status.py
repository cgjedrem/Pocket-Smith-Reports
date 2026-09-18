"""Status router — GET /api/sync/status."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, status

from budget_api.models.sync import SyncStatus
from budget_api.services import storage

router = APIRouter()


@router.get("/status", response_model=SyncStatus)
def get_status() -> SyncStatus:
    """Last sync status. 404 if never synced. 500 if status file corrupt."""
    try:
        raw = storage.read_sync_status()
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="sync status file is corrupt",
        )
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no sync has been run yet",
        )
    return SyncStatus.model_validate(raw)
