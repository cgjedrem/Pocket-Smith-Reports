"""PocketSmith API client — GET-only wrapper over urllib.

Reuses live_sync.py patterns: _NoRedirectHandler, _validated_api_url,
_api_request, _api_open, Link-header pagination, per_page=1000,
MAX_PAGINATION_PAGES=1000, 30s timeout. No httpx.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BASE_URL = "https://api.pocketsmith.com/v2"
MAX_PAGINATION_PAGES = 1_000
PER_PAGE = 1_000
TIMEOUT_SECONDS = 30


class PSClientError(ValueError):
    """PS API call failed — auth, rate limit, timeout, or unexpected response."""


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects so urllib never resends the developer key."""

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _validated_api_url(url: str, expected_path: str) -> str:
    """Allow only one exact PocketSmith API endpoint URL."""
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise PSClientError("PocketSmith API URL is malformed") from error
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.pocketsmith.com"
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != f"/v2{expected_path}"
        or parsed.fragment
    ):
        raise PSClientError("PocketSmith API URL is outside the requested endpoint")
    return url


def _validated_next_url(next_url: str, expected_path: str) -> str:
    """Allow only another page of the requested PocketSmith endpoint."""
    try:
        return _validated_api_url(next_url, expected_path)
    except PSClientError as error:
        raise PSClientError(
            "PocketSmith pagination link is outside the requested API endpoint"
        ) from error


def _api_request(url: str, expected_path: str, api_key: str) -> urllib.request.Request:
    """Build a Request with PS developer key + JSON accept header."""
    _validated_api_url(url, expected_path)
    return urllib.request.Request(
        url, headers={"X-Developer-Key": api_key, "Accept": "application/json"}
    )


def _api_open(request: urllib.request.Request):
    """Open a request with redirect rejection + 30s timeout."""
    return urllib.request.build_opener(_NoRedirectHandler()).open(
        request, timeout=TIMEOUT_SECONDS
    )


def _map_http_error(status: int, body: str) -> PSClientError:
    """Map PS HTTP status codes to clear error messages."""
    if status == 401:
        return PSClientError("PS API auth failed")
    if status == 403:
        return PSClientError("PS API forbidden")
    if status == 429:
        return PSClientError("PS API rate limited")
    if status in (500, 503):
        return PSClientError("PS API unavailable")
    return PSClientError(f"PS API error: {status} {body}")


class PSClient:
    """PocketSmith API client — GET-only, urllib-based, paginated where supported.

    All methods return raw decoded JSON (dict or list[dict]).
    Raises PSClientError on any auth/network/shape failure.
    """

    def __init__(self, api_key: str) -> None:
        if not api_key or not api_key.strip():
            raise PSClientError("PS API key is empty")
        self._api_key = api_key.strip()

    # -- single GET -------------------------------------------------------

    def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        """Single GET endpoint. Returns decoded JSON."""
        url = f"{BASE_URL}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        request = _api_request(url, path, self._api_key)
        try:
            with _api_open(request) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            body = ""
            try:
                body = error.read().decode("utf-8", errors="replace")
            except OSError:
                pass
            raise _map_http_error(error.code, body) from error
        except urllib.error.URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise PSClientError("PS API timeout") from error
            raise PSClientError(f"PS API network error: {error.reason}") from error
        except TimeoutError as error:
            raise PSClientError("PS API timeout") from error

    def _get_paginated(self, path: str, params: dict[str, str]) -> list[dict[str, Any]]:
        """Paginated GET — follow Link rel=next header. Cap at MAX_PAGINATION_PAGES."""
        url = f"{BASE_URL}{path}?{urllib.parse.urlencode(params)}"
        items: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        page_count = 0
        while url:
            if url in seen_urls:
                raise PSClientError("PocketSmith pagination link repeats a prior page")
            if page_count >= MAX_PAGINATION_PAGES:
                print(
                    f"PSClient: pagination cap hit at {MAX_PAGINATION_PAGES} pages "
                    f"for {path} — results truncated"
                )
                break
            seen_urls.add(url)
            request = _api_request(url, path, self._api_key)
            try:
                with _api_open(request) as response:
                    page = json.loads(response.read())
                    if not isinstance(page, list):
                        raise PSClientError(
                            f"PocketSmith {path} response must be a list"
                        )
                    items.extend(page)
                    match = re.search(
                        r'<([^>]+)>;\s*rel="next"', response.headers.get("link", "")
                    )
                    page_count += 1
                    url = _validated_next_url(match.group(1), path) if match else ""
            except urllib.error.HTTPError as error:
                body = ""
                try:
                    body = error.read().decode("utf-8", errors="replace")
                except OSError:
                    pass
                raise _map_http_error(error.code, body) from error
            except urllib.error.URLError as error:
                if isinstance(error.reason, TimeoutError):
                    raise PSClientError("PS API timeout") from error
                raise PSClientError(f"PS API network error: {error.reason}") from error
            except TimeoutError as error:
                raise PSClientError("PS API timeout") from error
        return items

    # -- endpoints --------------------------------------------------------

    def get_me(self) -> dict:
        """GET /me — current user. Must return dict with id."""
        user = self._get("/me")
        if not isinstance(user, dict) or user.get("id") is None:
            raise PSClientError("PocketSmith did not return a current user ID")
        return user

    def get_accounts(self, user_id: str) -> list[dict]:
        """GET /users/{id}/accounts — institution-level accounts."""
        accounts = self._get(f"/users/{user_id}/accounts")
        if not isinstance(accounts, list) or any(
            not isinstance(a, dict) or a.get("id") is None for a in accounts
        ):
            raise PSClientError("PocketSmith accounts response is invalid")
        return accounts

    def get_transaction_accounts(self, user_id: str) -> list[dict]:
        """GET /users/{id}/transaction_accounts — transaction-level accounts."""
        accounts = self._get(f"/users/{user_id}/transaction_accounts")
        if not isinstance(accounts, list) or any(
            not isinstance(a, dict) or a.get("id") is None for a in accounts
        ):
            raise PSClientError("PocketSmith transaction_accounts response is invalid")
        return accounts

    def get_transactions(
        self, user_id: str, start_date: str, end_date: str
    ) -> list[dict]:
        """GET /users/{id}/transactions — paginated, filtered by date range."""
        return self._get_paginated(
            f"/users/{user_id}/transactions",
            {
                "start_date": start_date,
                "end_date": end_date,
                "per_page": str(PER_PAGE),
            },
        )

    def get_transactions_for_account(
        self, account_id: str, start_date: str, end_date: str
    ) -> list[dict]:
        """GET /transaction_accounts/{id}/transactions — paginated, per-account."""
        return self._get_paginated(
            f"/transaction_accounts/{account_id}/transactions",
            {
                "start_date": start_date,
                "end_date": end_date,
                "per_page": str(PER_PAGE),
            },
        )

    def get_events(self, user_id: str, start_date: str, end_date: str) -> list[dict]:
        """GET /users/{id}/events — start_date+end_date required. Paginated
        (PS caps at 30/page — single _get silently dropped page 2+)."""
        events = self._get_paginated(
            f"/users/{user_id}/events",
            {"start_date": start_date, "end_date": end_date, "per_page": "100"},
        )
        if not isinstance(events, list):
            raise PSClientError("PocketSmith events response must be a list")
        return events

    def get_budget(self, user_id: str) -> list[dict]:
        """GET /users/{id}/budget — roll_up=false snapshot, no date param."""
        budget = self._get(f"/users/{user_id}/budget", {"roll_up": "false"})
        if not isinstance(budget, list):
            raise PSClientError("PocketSmith budget response must be a list")
        return budget

    def get_categories(self, user_id: str) -> list[dict]:
        """GET /users/{id}/categories — category tree."""
        categories = self._get(f"/users/{user_id}/categories")
        if not isinstance(categories, list) or any(
            not isinstance(c, dict) for c in categories
        ):
            raise PSClientError("PocketSmith categories response is invalid")
        return categories
