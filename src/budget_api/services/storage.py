"""Atomic JSON storage helpers — reuse live_sync._atomic_write pattern."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

# budget_api/services/storage.py → parents[3] = repo root
# (parents[0]=services, [1]=budget_api, [2]=src, [3]=repo)
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PRIVATE_DATA_DIR = REPOSITORY_ROOT / "data" / "private"

PARTNERS_PATH = PRIVATE_DATA_DIR / "partners.json"
# Match live_sync.py constant name (singular) — same file, avoids confusion.
ACCOUNT_MAPPING_PATH = PRIVATE_DATA_DIR / "account_mappings.json"
ACCOUNT_CATALOG_PATH = PRIVATE_DATA_DIR / "account_catalog.json"
CATEGORY_CATALOG_PATH = PRIVATE_DATA_DIR / "category_catalog.json"
SYNC_STATUS_PATH = PRIVATE_DATA_DIR / ".sync_status.json"

# F1.2 report paths — monthly report JSON + status + config files
CATEGORY_ROLES_PATH = PRIVATE_DATA_DIR / "category_roles.json"
DETAILED_SECTION_MAPPING_PATH = PRIVATE_DATA_DIR / "detailed_section_mapping.json"
PARTNER_LABELS_PATH = PRIVATE_DATA_DIR / "partner_labels.json"

# Shared SCSS — CLI + React both read. parents[4] = repo root (services→budget_api→src→repo).
SHARED_SCSS_PATH = REPOSITORY_ROOT / "client" / "src" / "styles" / "report-shared.scss"


def monthly_report_path(month: str) -> Path:
    """{month}_monthly_report.json — generated report JSON."""
    return PRIVATE_DATA_DIR / f"{month}_monthly_report.json"


def monthly_report_status_path(month: str) -> Path:
    """{month}_monthly_report_status.json — generate status."""
    return PRIVATE_DATA_DIR / f"{month}_monthly_report_status.json"


def monthly_ps_raw_path(month: str) -> Path:
    """{month}_ps_raw.json — raw sync data (from F1.1)."""
    return PRIVATE_DATA_DIR / f"{month}_ps_raw.json"


def mega_report_path(start: str, end: str) -> Path:
    """{start}_{end}_mega_report.json — mega report JSON."""
    return PRIVATE_DATA_DIR / f"{start}_{end}_mega_report.json"


def mega_report_status_path(start: str, end: str) -> Path:
    """{start}_{end}_mega_report_status.json — mega generate status."""
    return PRIVATE_DATA_DIR / f"{start}_{end}_mega_report_status.json"


def bills_dashboard_path(month: str) -> Path:
    """bills_dashboard_YYYY-MM.json — per-month bills dashboard snapshot."""
    return PRIVATE_DATA_DIR / f"bills_dashboard_{month}.json"


def atomic_write_json(path: Path, value: Any) -> None:
    """Write JSON atomically — temp file + replace. indent=2, ensure_ascii=False, trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as temporary:
        json.dump(value, temporary, indent=2, ensure_ascii=False)
        temporary.write("\n")
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def read_json(path: Path) -> Any:
    """Read JSON file. Returns None if missing. Raises on invalid JSON."""
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_sync_status(status: dict) -> None:
    """Write sync status atomically to .sync_status.json."""
    atomic_write_json(SYNC_STATUS_PATH, status)


def read_sync_status() -> dict | None:
    """Read sync status. Returns None if never synced."""
    return read_json(SYNC_STATUS_PATH)


def clear_stale_sync_status() -> None:
    """Delete .sync_status.json only when it records a non-terminal state.

    A persisted 'running' can only be stale (this process is not mid-sync at
    startup); terminal success/failed statuses are kept so the sync history
    and last-sync timestamp survive restarts. Unparseable files are dropped
    as stale.
    """
    if not SYNC_STATUS_PATH.exists():
        return
    try:
        record = read_json(SYNC_STATUS_PATH)
    except (OSError, ValueError):
        record = None
    if not isinstance(record, dict) or record.get("status") == "running":
        SYNC_STATUS_PATH.unlink(missing_ok=True)
