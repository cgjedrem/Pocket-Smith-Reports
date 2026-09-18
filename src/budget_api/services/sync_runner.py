"""Sync orchestrator — fetches PS data, writes catalogs + snapshots, updates status.

Entry point: sync_all(start_month, end_month) -> SyncResult.
Background-task semantics: catches all exceptions, writes failed status,
returns SyncResult with errors populated. Does NOT re-raise.
"""

from __future__ import annotations

import calendar
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from typing import Any

from budget_api.models.sync import RowCounts, SyncResult
from budget_api.services import env_writer, storage
from budget_api.services.ps_client import PSClient, PSClientError
from budget_api.services.bills_builder import (
    NoBillsAccountError,
    build_bills_chain,
    ensure_prior_month,
)
from input_contract import monthly_filename


def _month_dates(month: str) -> tuple[str, str]:
    """Return (first_day, last_day) ISO dates for a YYYY-MM month."""
    year, month_number = map(int, month.split("-"))
    last_day = calendar.monthrange(year, month_number)[1]
    return f"{month}-01", f"{month}-{last_day:02d}"


def _requested_months(start: str, end: str) -> list[str]:
    """Inclusive YYYY-MM list. Validates format + start<=end."""
    try:
        start_month = datetime.strptime(start, "%Y-%m")
        end_month = datetime.strptime(end, "%Y-%m")
    except ValueError as error:
        raise ValueError(f"Period must use YYYY-MM: {start!r}..{end!r}") from error
    if start_month.strftime("%Y-%m") != start or end_month.strftime("%Y-%m") != end:
        raise ValueError(f"Period must use YYYY-MM: {start!r}..{end!r}")
    if start_month > end_month:
        raise ValueError(f"Period start must not be after end: {start} > {end}")
    months: list[str] = []
    current = start_month
    while current <= end_month:
        months.append(current.strftime("%Y-%m"))
        year = current.year + (current.month == 12)
        month = 1 if current.month == 12 else current.month + 1
        current = current.replace(year=year, month=month)
    return months


def _iso_now() -> str:
    """Current UTC time in ISO 8601."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _migrate_owner_to_partner_id(mappings: dict[str, Any]) -> bool:
    """One-time owner→partner_id migration. Idempotent. Returns True if changed."""
    accounts = mappings.get("accounts")
    if not isinstance(accounts, dict):
        return False
    changed = False
    for account_id, entry in accounts.items():
        if not isinstance(entry, dict):
            continue
        if "owner" in entry and "partner_id" not in entry:
            entry["partner_id"] = entry.pop("owner")
            changed = True
    return changed


def _merge_accounts_into_mappings(
    ps_accounts: list[dict[str, Any]],
    mappings: dict[str, Any],
) -> None:
    """Merge fresh PS account catalog into account_mappings.json.

    - Existing: preserve partner_id/type/excluded, update name from PS.
    - New PS account: add entry partner_id=null, type=null, excluded=false.
    - Local account not in fresh PS catalog: set excluded=true (preserve binding).
    """
    accounts_map = mappings.setdefault("accounts", {})
    if not isinstance(accounts_map, dict):
        accounts_map = {}
        mappings["accounts"] = accounts_map

    ps_ids: set[str] = set()
    for account in ps_accounts:
        if not isinstance(account, dict) or account.get("id") is None:
            continue
        account_id = str(account["id"])
        ps_ids.add(account_id)
        ps_name = account.get("name", "")
        existing = accounts_map.get(account_id)
        if isinstance(existing, dict):
            # Preserve binding, update name from PS.
            existing["name"] = ps_name
            existing.setdefault("partner_id", None)
            existing.setdefault("type", None)
            existing.setdefault("excluded", False)
        else:
            accounts_map[account_id] = {
                "name": ps_name,
                "partner_id": None,
                "type": None,
                "excluded": False,
            }

    # Local accounts missing from PS → exclude (preserve binding).
    for account_id, entry in accounts_map.items():
        if account_id not in ps_ids and isinstance(entry, dict):
            entry["excluded"] = True


def _write_failed_status(
    start_month: str,
    end_month: str,
    errors: list[str],
    duration_ms: int,
    timestamp: str,
    months_synced: int,
    row_counts: RowCounts,
) -> None:
    """Write failed sync status — status file is source of truth for background tasks."""
    storage.write_sync_status(
        {
            "status": "failed",
            "last_sync": timestamp,
            "start_month": start_month,
            "end_month": end_month,
            "months_synced": months_synced,
            "row_counts": row_counts.model_dump(),
            "errors": errors,
            "duration_ms": duration_ms,
        }
    )


def sync_all(start_month: str, end_month: str) -> SyncResult:
    """Run full PS sync. Background-task safe — catches all errors, never re-raises."""
    started = time.monotonic()
    timestamp = _iso_now()
    errors: list[str] = []

    # Validate period before any PS call.
    try:
        months = _requested_months(start_month, end_month)
    except ValueError as error:
        errors.append(str(error))
        duration_ms = int((time.monotonic() - started) * 1000)
        _write_failed_status(
            start_month, end_month, errors, duration_ms, timestamp, 0, RowCounts()
        )
        return SyncResult(
            timestamp=timestamp,
            start_month=start_month,
            end_month=end_month,
            months_synced=0,
            row_counts=RowCounts(),
            errors=errors,
            duration_ms=duration_ms,
        )

    # Write running status before first PS call.
    storage.write_sync_status(
        {
            "status": "running",
            "last_sync": timestamp,
            "start_month": start_month,
            "end_month": end_month,
            "months_synced": 0,
            "row_counts": RowCounts().model_dump(),
            "errors": [],
            "duration_ms": 0,
        }
    )

    row_counts = RowCounts()
    months_synced = 0
    bills_snapshots_written = 0
    bills_warnings: list[str] = []

    try:
        api_key = _read_api_key()
        client = PSClient(api_key)
        user = client.get_me()
        user_id = str(user["id"])

        # --- F2-BE: fetch catalogs BEFORE the per-month loop so bills
        #     derivations have fresh data from the start. ---
        transaction_accounts = client.get_transaction_accounts(user_id)
        storage.atomic_write_json(
            storage.ACCOUNT_CATALOG_PATH,
            {"start": start_month, "end": end_month, "accounts": transaction_accounts},
        )
        row_counts.accounts = len(transaction_accounts)

        categories = client.get_categories(user_id)
        storage.atomic_write_json(
            storage.CATEGORY_CATALOG_PATH,
            {"start": start_month, "end": end_month, "categories": categories},
        )
        row_counts.categories = len(categories)

        # Merge accounts into mappings (needed before bills step reads it).
        try:
            mappings = storage.read_json(storage.ACCOUNT_MAPPING_PATH)
        except json.JSONDecodeError as error:
            raise ValueError(
                "account_mappings.json is corrupt — back up and remove to re-sync"
            ) from error
        if not isinstance(mappings, dict):
            mappings = {"schema_version": 1, "partners": {}, "accounts": {}}
        _migrate_owner_to_partner_id(mappings)
        _merge_accounts_into_mappings(transaction_accounts, mappings)
        storage.atomic_write_json(storage.ACCOUNT_MAPPING_PATH, mappings)

        # --- Per-month: transactions + events (collected for the chain) ---
        events_per_month: dict[str, list[dict]] = {}
        transactions_per_month: dict[str, list[dict]] = {}
        for month in months:
            start_date, end_date = _month_dates(month)
            transactions = client.get_transactions(user_id, start_date, end_date)
            storage.atomic_write_json(
                storage.PRIVATE_DATA_DIR / monthly_filename(month, "live"),
                transactions,
            )
            row_counts.transactions += len(transactions)

            events = client.get_events(user_id, start_date, end_date)
            storage.atomic_write_json(
                storage.PRIVATE_DATA_DIR / f"events_{month}.json",
                events,
            )
            row_counts.events += len(events)
            months_synced += 1

            events_per_month[month] = events
            transactions_per_month[month] = transactions

        # --- F2-BE: bills chain — one pass, anchor on live combined ---
        try:
            account_mappings = storage.read_json(storage.ACCOUNT_MAPPING_PATH) or {}
            category_roles = storage.read_json(storage.CATEGORY_ROLES_PATH) or {}
            cat_catalog_raw = storage.read_json(storage.CATEGORY_CATALOG_PATH) or {}
            category_catalog = (
                cat_catalog_raw.get("categories", [])
                if isinstance(cat_catalog_raw, dict)
                else []
            )
            acct_catalog_raw = storage.read_json(storage.ACCOUNT_CATALOG_PATH) or {}
            account_catalog = (
                acct_catalog_raw.get("accounts", [])
                if isinstance(acct_catalog_raw, dict)
                else []
            )
        except json.JSONDecodeError as error:
            raise ValueError(
                "account_mappings.json is corrupt — back up and remove to re-sync"
            ) from error

        # earliest month needs m-1 on disk for estimated_cc_bill
        if months:
            try:
                ensure_prior_month(client, user_id, months[0], bills_warnings)
            except PSClientError as e:
                bills_warnings.append(
                    f"Bills chain: prior month fetch for {months[0]} failed: {e}"
                )

        try:
            snapshots = build_bills_chain(
                months=months,
                events_per_month=events_per_month,
                transactions_per_month=transactions_per_month,
                account_mappings=account_mappings,
                category_roles=category_roles,
                category_catalog=category_catalog,
                account_catalog=account_catalog,
                warnings=bills_warnings,
            )
            for month in sorted(snapshots):
                storage.atomic_write_json(
                    storage.bills_dashboard_path(month), snapshots[month]
                )
                bills_snapshots_written += 1
                row_counts.bills_snapshots += 1
        except NoBillsAccountError as e:
            bills_warnings.append(f"Bills snapshots skipped: {e}")

        # --- Budget snapshot (single, no date param) ---
        budget = client.get_budget(user_id)
        storage.atomic_write_json(
            storage.PRIVATE_DATA_DIR / "budget_snapshot.json",
            {"timestamp": timestamp, "budget": budget},
        )
        row_counts.budget = len(budget)

    except (PSClientError, ValueError, OSError) as error:
        errors.append(str(error))
    except Exception as error:  # noqa: BLE001 — background task must not crash caller
        errors.append(f"Unexpected error: {error}")
        print(traceback.format_exc(), file=sys.stderr)

    duration_ms = int((time.monotonic() - started) * 1000)

    if errors:
        _write_failed_status(
            start_month,
            end_month,
            errors,
            duration_ms,
            timestamp,
            months_synced,
            row_counts,
        )
    else:
        storage.write_sync_status(
            {
                "status": "success",
                "last_sync": timestamp,
                "start_month": start_month,
                "end_month": end_month,
                "months_synced": months_synced,
                "row_counts": row_counts.model_dump(),
                "errors": [],
                "duration_ms": duration_ms,
                "bills_snapshots_written": bills_snapshots_written,
                "bills_warnings": bills_warnings,
            }
        )

    return SyncResult(
        timestamp=timestamp,
        start_month=start_month,
        end_month=end_month,
        months_synced=months_synced,
        row_counts=row_counts,
        errors=errors,
        duration_ms=duration_ms,
    )


def _read_api_key() -> str:
    """Read API_KEY from .env via env_writer. Raises if missing."""
    value = env_writer.read_api_key_value()
    if not value:
        raise PSClientError("API_KEY is missing from local .env")
    return value
