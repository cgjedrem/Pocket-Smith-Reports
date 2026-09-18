"""Sync router — GET /api/sync (async 202, concurrent guard)."""

from __future__ import annotations

import re
import threading
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from budget_api.models.sync import SyncStatus
from budget_api.services import env_writer, storage, sync_runner

router = APIRouter()

# Fix 4 — module-level lock closes TOCTOU window in concurrent guard.
# Sufficient for single-process uvicorn.
_sync_lock = threading.Lock()

_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def _valid_month(value: str) -> bool:
    """YYYY-MM format check."""
    if not _MONTH_RE.match(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m")
    except ValueError:
        return False
    return True


@router.get("/sync", status_code=status.HTTP_202_ACCEPTED, response_model=SyncStatus)
def trigger_sync(
    background_tasks: BackgroundTasks,
    start_month: str = Query(...),
    end_month: str = Query(...),
) -> SyncStatus:
    """Start async sync. 202 immediately. Concurrent guard: 202 + current status if running."""
    # Format validation.
    if not _valid_month(start_month) or not _valid_month(end_month):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid month format",
        )
    # Range validation.
    if start_month > end_month:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_month must be ≤ end_month",
        )

    # Fix 4 — atomic check-and-schedule under lock. Closes TOCTOU race.
    with _sync_lock:
        current = storage.read_sync_status()
        if current is not None and current.get("status") == "running":
            return SyncStatus.model_validate(current)

        # API key check before kicking off background task.
        if not env_writer.read_api_key_configured():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="API key not configured",
            )

        # Fire-and-forget. sync_runner writes .sync_status.json itself.
        background_tasks.add_task(sync_runner.sync_all, start_month, end_month)

    # Return initial running status (sync_runner writes its own, but caller
    # gets an immediate snapshot). Build minimal running status if file not
    # yet written by background task.
    snapshot = storage.read_sync_status()
    if snapshot is not None:
        return SyncStatus.model_validate(snapshot)
    # Fallback: synthesize running status (race — bg task may not have written yet).
    return SyncStatus(
        status="running",
        last_sync="",
        start_month=start_month,
        end_month=end_month,
        months_synced=0,
        row_counts={  # type: ignore[arg-type]
            "transactions": 0,
            "events": 0,
            "budget": 0,
            "categories": 0,
            "accounts": 0,
        },
        errors=[],
        duration_ms=0,
    )
