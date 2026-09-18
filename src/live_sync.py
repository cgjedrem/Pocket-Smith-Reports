#!/usr/bin/env python3
"""Staged PocketSmith sync for ignored local live-report data."""

from __future__ import annotations

import argparse
import calendar
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from input_contract import monthly_filename
from v4_pipeline.accounting import (
    AccountingValidationError,
    load_unified_account_mapping,
)

BASE_URL = "https://api.pocketsmith.com/v2"
MAX_PAGINATION_PAGES = 1_000
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DATA_DIR = REPOSITORY_ROOT / "data" / "private"
ACCOUNT_CATALOG_PATH = PRIVATE_DATA_DIR / "account_catalog.json"
CATEGORY_CATALOG_PATH = PRIVATE_DATA_DIR / "category_catalog.json"
ACCOUNT_MAPPING_PATH = PRIVATE_DATA_DIR / "account_mappings.json"
ENV_PATH = REPOSITORY_ROOT / ".env"


class LiveSyncError(ValueError):
    """Raised when staged live data cannot safely publish."""


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects before urllib can resend credentials."""

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _validated_api_url(url: str, expected_path: str) -> str:
    """Allow only one exact PocketSmith API endpoint URL."""
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise LiveSyncError("PocketSmith API URL is malformed") from error
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.pocketsmith.com"
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != f"/v2{expected_path}"
        or parsed.fragment
    ):
        raise LiveSyncError("PocketSmith API URL is outside the requested endpoint")
    return url


def _api_open(request: urllib.request.Request):
    return urllib.request.build_opener(_NoRedirectHandler()).open(request, timeout=30)


def _api_request(url: str, expected_path: str, api_key: str) -> urllib.request.Request:
    _validated_api_url(url, expected_path)
    return urllib.request.Request(
        url, headers={"X-Developer-Key": api_key, "Accept": "application/json"}
    )


def requested_months(start: str, end: str) -> list[str]:
    """Return inclusive exact YYYY-MM period."""
    try:
        start_month = datetime.strptime(start, "%Y-%m")
        end_month = datetime.strptime(end, "%Y-%m")
    except ValueError as error:
        raise LiveSyncError("Period must use YYYY-MM") from error
    if start_month.strftime("%Y-%m") != start or end_month.strftime("%Y-%m") != end:
        raise LiveSyncError("Period must use YYYY-MM")
    if start_month > end_month:
        raise LiveSyncError("Period start must not be after end")
    months = []
    current = start_month
    while current <= end_month:
        months.append(current.strftime("%Y-%m"))
        year = current.year + (current.month == 12)
        month = 1 if current.month == 12 else current.month + 1
        current = current.replace(year=year, month=month)
    return months


def _month_dates(month: str) -> tuple[str, str]:
    year, month_number = map(int, month.split("-"))
    last_day = calendar.monthrange(year, month_number)[1]
    return f"{month}-01", f"{month}-{last_day:02d}"


def _read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LiveSyncError(f"{label} is missing or unreadable") from error


def _atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as temporary:
        json.dump(value, temporary, indent=2, ensure_ascii=False)
        temporary.write("\n")
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def _read_env_api_key() -> str:
    try:
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise LiveSyncError("Local .env is missing or unreadable") from error
    for line in lines:
        key, separator, value = line.partition("=")
        if key.strip() == "API_KEY" and separator and value.strip():
            return value.strip()
    raise LiveSyncError("API_KEY is missing from local environment file")


def ps_get(path: str, api_key: str, params: dict[str, str] | None = None) -> Any:
    url = f"{BASE_URL}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = _api_request(url, path, api_key)
    with _api_open(request) as response:
        return json.loads(response.read())


def _validated_next_url(next_url: str, expected_path: str) -> str:
    """Allow only another page of the requested PocketSmith endpoint."""
    try:
        return _validated_api_url(next_url, expected_path)
    except LiveSyncError as error:
        raise LiveSyncError(
            "PocketSmith pagination link is outside the requested API endpoint"
        ) from error


def ps_get_paginated(
    path: str, params: dict[str, str], api_key: str
) -> list[dict[str, Any]]:
    url = f"{BASE_URL}{path}?{urllib.parse.urlencode(params)}"
    items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    page_count = 0
    while url:
        if url in seen_urls:
            raise LiveSyncError("PocketSmith pagination link repeats a prior page")
        if page_count >= MAX_PAGINATION_PAGES:
            raise LiveSyncError("PocketSmith pagination exceeded the page limit")
        seen_urls.add(url)
        request = _api_request(url, path, api_key)
        with _api_open(request) as response:
            page = json.loads(response.read())
            if not isinstance(page, list):
                raise LiveSyncError("PocketSmith transactions response must be a list")
            items.extend(page)
            match = re.search(
                r'<([^>]+)>;\s*rel="next"', response.headers.get("link", "")
            )
            page_count += 1
            url = _validated_next_url(match.group(1), path) if match else ""
    return items


def _current_user_id(api_key: str) -> str:
    user = ps_get("/me", api_key)
    if not isinstance(user, dict) or user.get("id") is None:
        raise LiveSyncError("PocketSmith did not return a current user ID")
    return str(user["id"])


def _accounts(api_key: str, user_id: str) -> list[dict[str, Any]]:
    accounts = ps_get(f"/users/{user_id}/transaction_accounts", api_key)
    if not isinstance(accounts, list) or any(
        not isinstance(account, dict) or account.get("id") is None
        for account in accounts
    ):
        raise LiveSyncError("PocketSmith account catalog is invalid")
    return accounts


def _normalize_transactions(
    transactions: list[dict[str, Any]], account: dict[str, Any]
) -> list[dict[str, Any]]:
    account_id = str(account["id"])
    account_name = account.get("name", "?")
    normalized = []
    for transaction in transactions:
        if not isinstance(transaction, dict):
            raise LiveSyncError("PocketSmith transaction is invalid")
        item = dict(transaction)
        item["_account_id"] = account_id
        item["_account_name"] = account_name
        source_account = item.get("account")
        item["account"] = (
            dict(source_account) if isinstance(source_account, dict) else {}
        )
        item["account"].setdefault("id", account_id)
        item["account"].setdefault("name", account_name)
        category = item.get("category")
        if category is not None and not isinstance(category, dict):
            raise LiveSyncError("PocketSmith transaction category is invalid")
        item["category"] = dict(category) if category else None
        item["_cat_id"] = item["category"].get("id") if item["category"] else None
        item["_cat_title"] = (
            item["category"].get("title") if item["category"] else "(uncategorized)"
        )
        normalized.append(item)
    return normalized


def run_accounts_stage(
    start: str, end: str, api_key: str, user_id: str
) -> dict[str, Any]:
    """Publish active-account metadata after all activity probes succeed."""
    months = requested_months(start, end)
    accounts = _accounts(api_key, user_id)
    active_ids: set[str] = set()
    for month in months:
        start_date, end_date = _month_dates(month)
        for account in accounts:
            transactions = ps_get_paginated(
                f"/transaction_accounts/{account['id']}/transactions",
                {"start_date": start_date, "end_date": end_date},
                api_key,
            )
            if transactions:
                active_ids.add(str(account["id"]))
    catalog = {
        "start": start,
        "end": end,
        "accounts": [
            account for account in accounts if str(account["id"]) in active_ids
        ],
    }
    _atomic_write(ACCOUNT_CATALOG_PATH, catalog)
    return catalog


def run_categories_stage(
    start: str, end: str, api_key: str, user_id: str
) -> dict[str, Any]:
    """Publish category metadata catalog."""
    requested_months(start, end)
    categories = ps_get(f"/users/{user_id}/categories", api_key)
    if not isinstance(categories, list) or any(
        not isinstance(category, dict) for category in categories
    ):
        raise LiveSyncError("PocketSmith category catalog is invalid")
    catalog = {"start": start, "end": end, "categories": categories}
    _atomic_write(CATEGORY_CATALOG_PATH, catalog)
    return catalog


def _load_catalog(
    path: Path, label: str, start: str, end: str, key: str
) -> list[dict[str, Any]]:
    catalog = _read_json(path, label)
    if (
        not isinstance(catalog, dict)
        or catalog.get("start") != start
        or catalog.get("end") != end
    ):
        raise LiveSyncError(f"{label} does not match requested period")
    values = catalog.get(key)
    if not isinstance(values, list) or any(
        not isinstance(value, dict) or value.get("id") is None for value in values
    ):
        raise LiveSyncError(f"{label} is invalid")
    return values


def _load_account_maps(
    accounts: list[dict[str, Any]],
) -> tuple[dict[str, str], dict[str, bool], dict[str, str]]:
    catalog_id_list = [str(account["id"]) for account in accounts]
    catalog_ids = set(catalog_id_list)
    if len(catalog_ids) != len(catalog_id_list):
        raise LiveSyncError("Account catalog contains duplicate account IDs")
    try:
        owners, labels, mapping_accounts = load_unified_account_mapping(
            ACCOUNT_MAPPING_PATH
        )
    except AccountingValidationError as error:
        raise LiveSyncError(str(error)) from error
    if set(mapping_accounts) != catalog_ids:
        raise LiveSyncError(
            "Unified account mapping must cover exactly the active account catalog"
        )
    for account in accounts:
        account_id = str(account["id"])
        if (
            not isinstance(account.get("name"), str)
            or mapping_accounts[account_id]["name"] != account["name"]
        ):
            raise LiveSyncError(
                "Unified account mapping account names must match the active account catalog"
            )
    return (
        owners,
        {
            account_id: account["excluded"]
            for account_id, account in mapping_accounts.items()
        },
        labels,
    )


def _prepare_transactions_stage(
    start: str, end: str
) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate all local transaction-stage inputs before credentials or HTTP."""
    months = requested_months(start, end)
    accounts = _load_catalog(
        ACCOUNT_CATALOG_PATH, "Account catalog", start, end, "accounts"
    )
    categories = _load_catalog(
        CATEGORY_CATALOG_PATH, "Category catalog", start, end, "categories"
    )
    _owners, exclusions, _labels = _load_account_maps(accounts)
    return (
        months,
        categories,
        [account for account in accounts if not exclusions[str(account["id"])]],
    )


def _publish_transaction_snapshots(snapshots: dict[str, dict[str, Any]]) -> None:
    """Publish all monthly snapshots or restore every prior snapshot."""
    targets = [
        PRIVATE_DATA_DIR / monthly_filename(month, "live") for month in snapshots
    ]
    with tempfile.TemporaryDirectory(
        prefix=".live-sync-stage-", dir=PRIVATE_DATA_DIR
    ) as stage:
        stage_dir = Path(stage)
        staged_paths: dict[Path, Path] = {}
        for month, snapshot in snapshots.items():
            target = PRIVATE_DATA_DIR / monthly_filename(month, "live")
            staged = stage_dir / target.name
            staged.write_text(
                json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            staged_paths[target] = staged

        recovery_dir = PRIVATE_DATA_DIR / f".live-sync-recovery-{uuid.uuid4().hex}"
        recovery_dir.mkdir()
        backed_up: list[Path] = []
        published: list[Path] = []
        try:
            for target in targets:
                if target.exists():
                    os.replace(target, recovery_dir / target.name)
                    backed_up.append(target)
            for target in targets:
                os.replace(staged_paths[target], target)
                published.append(target)
        except OSError as publish_error:
            rollback_errors: list[OSError] = []
            for target in published:
                try:
                    target.unlink(missing_ok=True)
                except OSError as rollback_error:
                    rollback_errors.append(rollback_error)
            for target in backed_up:
                try:
                    os.replace(recovery_dir / target.name, target)
                except OSError as rollback_error:
                    rollback_errors.append(rollback_error)
            if rollback_errors:
                raise LiveSyncError(
                    "Live snapshot publish failed and rollback failed; prior snapshots retained at "
                    f"{recovery_dir}"
                ) from publish_error
            shutil.rmtree(recovery_dir, ignore_errors=True)
            raise LiveSyncError(
                "Live snapshot publish failed; prior snapshots restored"
            ) from publish_error
        shutil.rmtree(recovery_dir, ignore_errors=True)


def run_transactions_stage(
    start: str,
    end: str,
    api_key: str,
    _unused_user_id: str | None = None,
    *,
    prepared: (
        tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]] | None
    ) = None,
) -> dict[str, dict[str, Any]]:
    """Fetch all allowed months before publishing canonical transaction snapshots."""
    months, categories, allowed_accounts = prepared or _prepare_transactions_stage(
        start, end
    )
    snapshots: dict[str, dict[str, Any]] = {}
    for month in months:
        start_date, end_date = _month_dates(month)
        transactions: list[dict[str, Any]] = []
        active_accounts: list[dict[str, Any]] = []
        for account in allowed_accounts:
            fetched = ps_get_paginated(
                f"/transaction_accounts/{account['id']}/transactions",
                {"start_date": start_date, "end_date": end_date},
                api_key,
            )
            normalized = _normalize_transactions(fetched, account)
            transactions.extend(normalized)
            if normalized:
                active_accounts.append(account)
        year, month_number = map(int, month.split("-"))
        snapshots[month] = {
            "year": year,
            "month": month_number,
            "accounts": active_accounts,
            "categories": categories,
            "transactions": transactions,
        }
    _publish_transaction_snapshots(snapshots)
    return snapshots


def main() -> None:
    parser = argparse.ArgumentParser(description="Staged PocketSmith live-data sync")
    parser.add_argument("stage", choices=("accounts", "categories", "transactions"))
    parser.add_argument("--start", required=True, help="Inclusive YYYY-MM")
    parser.add_argument("--end", required=True, help="Inclusive YYYY-MM")
    args = parser.parse_args()
    try:
        if args.stage == "accounts":
            api_key = _read_env_api_key()
            user_id = _current_user_id(api_key)
            result = run_accounts_stage(args.start, args.end, api_key, user_id)
            print(
                f"Published {len(result['accounts'])} active account metadata records"
            )
        elif args.stage == "categories":
            api_key = _read_env_api_key()
            user_id = _current_user_id(api_key)
            result = run_categories_stage(args.start, args.end, api_key, user_id)
            print(f"Published {len(result['categories'])} category metadata records")
        else:
            prepared = _prepare_transactions_stage(args.start, args.end)
            api_key = _read_env_api_key()
            result = run_transactions_stage(
                args.start, args.end, api_key, prepared=prepared
            )
            print(f"Published {len(result)} complete monthly transaction snapshots")
    except (
        LiveSyncError,
        OSError,
        urllib.error.URLError,
        json.JSONDecodeError,
    ) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
