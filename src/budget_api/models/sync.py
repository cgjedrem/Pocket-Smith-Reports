"""Sync pydantic models — RowCounts, SyncResult, SyncStatus."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class RowCounts(BaseModel):
    """Per-data-type row counts from last sync."""

    transactions: int = 0
    events: int = 0
    budget: int = 0
    categories: int = 0
    accounts: int = 0
    bills_snapshots: int = 0  # F2-BE: bills dashboard snapshots written


class SyncResult(BaseModel):
    """Returned by GET /api/sync on completion."""

    timestamp: str  # ISO 8601
    start_month: str  # YYYY-MM
    end_month: str  # YYYY-MM
    months_synced: int
    row_counts: RowCounts
    errors: list[str]  # empty if success
    duration_ms: int


class SyncStatus(BaseModel):
    """Persisted sync status — read via GET /api/sync/status."""

    status: Literal["running", "success", "failed"]
    last_sync: str  # ISO 8601
    start_month: str
    end_month: str
    months_synced: int
    row_counts: RowCounts
    errors: list[str]
    duration_ms: int
    # F2-BE: bills extension fields. Backward-compatible defaults.
    bills_snapshots_written: int = 0
    bills_warnings: list[str] = []
