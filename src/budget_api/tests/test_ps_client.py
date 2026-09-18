"""B11 — PSClient tests. Mock urllib, no network. AC: error mapping, pagination, URL validation."""

from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

import pytest
import urllib.error

from budget_api.services.ps_client import (
    BASE_URL,
    MAX_PAGINATION_PAGES,
    PSClient,
    PSClientError,
    _NoRedirectHandler,
    _validated_api_url,
)

# --------------------------------------------------------------------------- #
# Helpers — fake urllib response + opener.
# --------------------------------------------------------------------------- #


def _fake_response(body: bytes, headers: dict[str, str] | None = None):
    """Build a context-manager-like fake HTTP response."""
    mock = MagicMock()
    mock.read.return_value = body
    mock.headers = {}
    if headers:
        # urllib response headers object — use dict-like.
        hdr = MagicMock()
        hdr.get = lambda key, default="": headers.get(key, default)
        mock.headers = hdr
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    return mock


def _patch_open(monkeypatch, responses):
    """Patch _api_open to pop responses in order. responses = list of fake_response or Exception."""
    calls = {"count": 0}

    def fake_open(request, timeout=None):
        idx = calls["count"]
        calls["count"] += 1
        resp = responses[idx]
        if isinstance(resp, Exception):
            raise resp
        return resp

    monkeypatch.setattr("budget_api.services.ps_client._api_open", fake_open)
    return calls


# --------------------------------------------------------------------------- #
# Init + key validation.
# --------------------------------------------------------------------------- #


class TestPSClientInit:
    def test_empty_key_raises(self):
        with pytest.raises(PSClientError, match="empty"):
            PSClient("")

    def test_whitespace_key_raises(self):
        with pytest.raises(PSClientError, match="empty"):
            PSClient("   ")

    def test_strips_key(self):
        client = PSClient("  abc123  ")
        assert client._api_key == "abc123"


# --------------------------------------------------------------------------- #
# Single GET — get_me, get_accounts, get_transaction_accounts, get_events, get_budget, get_categories.
# --------------------------------------------------------------------------- #


class TestSingleGet:
    def test_get_me_ok(self, monkeypatch):
        body = json.dumps({"id": 12345}).encode()
        _patch_open(monkeypatch, [_fake_response(body)])
        client = PSClient("key")
        result = client.get_me()
        assert result == {"id": 12345}

    def test_get_me_missing_id_raises(self, monkeypatch):
        body = json.dumps({"name": "no id"}).encode()
        _patch_open(monkeypatch, [_fake_response(body)])
        client = PSClient("key")
        with pytest.raises(PSClientError, match="current user ID"):
            client.get_me()

    def test_get_me_not_dict_raises(self, monkeypatch):
        body = json.dumps([1, 2, 3]).encode()
        _patch_open(monkeypatch, [_fake_response(body)])
        client = PSClient("key")
        with pytest.raises(PSClientError, match="current user ID"):
            client.get_me()

    def test_get_accounts_ok(self, monkeypatch):
        body = json.dumps([{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]).encode()
        _patch_open(monkeypatch, [_fake_response(body)])
        client = PSClient("key")
        result = client.get_accounts("123")
        assert len(result) == 2

    def test_get_accounts_missing_id_raises(self, monkeypatch):
        body = json.dumps([{"id": 1}, {"name": "no id"}]).encode()
        _patch_open(monkeypatch, [_fake_response(body)])
        client = PSClient("key")
        with pytest.raises(PSClientError, match="accounts response is invalid"):
            client.get_accounts("123")

    def test_get_transaction_accounts_ok(self, monkeypatch):
        body = json.dumps([{"id": 10, "name": "ta"}]).encode()
        _patch_open(monkeypatch, [_fake_response(body)])
        client = PSClient("key")
        result = client.get_transaction_accounts("123")
        assert result == [{"id": 10, "name": "ta"}]

    def test_get_events_ok(self, monkeypatch):
        body = json.dumps([{"id": "e1"}]).encode()
        _patch_open(monkeypatch, [_fake_response(body)])
        client = PSClient("key")
        result = client.get_events("123", "2026-07-01", "2026-07-31")
        assert len(result) == 1

    def test_get_events_not_list_raises(self, monkeypatch):
        body = json.dumps({"id": "e1"}).encode()
        _patch_open(monkeypatch, [_fake_response(body)])
        client = PSClient("key")
        with pytest.raises(PSClientError, match="events response must be a list"):
            client.get_events("123", "2026-07-01", "2026-07-31")

    def test_get_budget_ok(self, monkeypatch):
        body = json.dumps([{"id": "b1"}]).encode()
        _patch_open(monkeypatch, [_fake_response(body)])
        client = PSClient("key")
        result = client.get_budget("123")
        assert len(result) == 1

    def test_get_budget_not_list_raises(self, monkeypatch):
        body = json.dumps({"id": "b1"}).encode()
        _patch_open(monkeypatch, [_fake_response(body)])
        client = PSClient("key")
        with pytest.raises(PSClientError, match="budget response must be a list"):
            client.get_budget("123")

    def test_get_categories_ok(self, monkeypatch):
        body = json.dumps([{"id": 1, "title": "cat"}]).encode()
        _patch_open(monkeypatch, [_fake_response(body)])
        client = PSClient("key")
        result = client.get_categories("123")
        assert len(result) == 1

    def test_get_categories_not_list_raises(self, monkeypatch):
        body = json.dumps({"id": 1}).encode()
        _patch_open(monkeypatch, [_fake_response(body)])
        client = PSClient("key")
        with pytest.raises(PSClientError, match="categories response is invalid"):
            client.get_categories("123")


# --------------------------------------------------------------------------- #
# Pagination — Link header, cap, repeat detection.
# --------------------------------------------------------------------------- #


class TestPagination:
    def _paginated_responses(self, pages: list[list]) -> list:
        out = []
        for i, page in enumerate(pages):
            link = ""
            if i < len(pages) - 1:
                link = f'<{BASE_URL}/users/1/transactions?per_page=1000&page={i+2}>; rel="next"'
            out.append(
                _fake_response(
                    json.dumps(page).encode(),
                    headers={"link": link} if link else {},
                )
            )
        return out

    def test_multi_page_follows_link(self, monkeypatch):
        responses = self._paginated_responses(
            [
                [{"id": "tx1"}],
                [{"id": "tx2"}, {"id": "tx3"}],
            ]
        )
        _patch_open(monkeypatch, responses)
        client = PSClient("key")
        result = client.get_transactions("1", "2026-07-01", "2026-07-31")
        assert len(result) == 3
        assert [t["id"] for t in result] == ["tx1", "tx2", "tx3"]

    def test_single_page_no_link(self, monkeypatch):
        responses = self._paginated_responses([[{"id": "tx1"}]])
        _patch_open(monkeypatch, responses)
        client = PSClient("key")
        result = client.get_transactions("1", "2026-07-01", "2026-07-31")
        assert len(result) == 1

    def test_pagination_cap(self, monkeypatch):
        # Build MAX+1 pages — should cap at MAX.
        pages = [[{"id": f"tx{i}"}] for i in range(MAX_PAGINATION_PAGES + 1)]
        responses = self._paginated_responses(pages)
        _patch_open(monkeypatch, responses)
        client = PSClient("key")
        result = client.get_transactions("1", "2026-07-01", "2026-07-31")
        assert len(result) == MAX_PAGINATION_PAGES

    def test_repeated_url_raises(self, monkeypatch):
        # Same next URL twice → repeat detected.
        link = f'<{BASE_URL}/users/1/transactions?per_page=1000&page=2>; rel="next"'
        resp1 = _fake_response(
            json.dumps([{"id": "tx1"}]).encode(), headers={"link": link}
        )
        resp2 = _fake_response(
            json.dumps([{"id": "tx2"}]).encode(), headers={"link": link}
        )
        _patch_open(monkeypatch, [resp1, resp2])
        client = PSClient("key")
        with pytest.raises(PSClientError, match="repeats a prior page"):
            client.get_transactions("1", "2026-07-01", "2026-07-31")

    def test_next_url_wrong_path_raises(self, monkeypatch):
        link = f'<{BASE_URL}/users/1/accounts>; rel="next"'
        resp = _fake_response(
            json.dumps([{"id": "tx1"}]).encode(), headers={"link": link}
        )
        _patch_open(monkeypatch, [resp])
        client = PSClient("key")
        with pytest.raises(PSClientError, match="pagination link is outside"):
            client.get_transactions("1", "2026-07-01", "2026-07-31")

    def test_non_list_paginated_raises(self, monkeypatch):
        resp = _fake_response(json.dumps({"id": "not list"}).encode(), headers={})
        _patch_open(monkeypatch, [resp])
        client = PSClient("key")
        with pytest.raises(PSClientError, match="response must be a list"):
            client.get_transactions("1", "2026-07-01", "2026-07-31")

    def test_get_transactions_for_account_ok(self, monkeypatch):
        link = ""
        resp = _fake_response(
            json.dumps([{"id": "tx1"}]).encode(), headers={"link": link}
        )
        _patch_open(monkeypatch, [resp])
        client = PSClient("key")
        result = client.get_transactions_for_account("999", "2026-07-01", "2026-07-31")
        assert len(result) == 1


# --------------------------------------------------------------------------- #
# Error mapping — HTTP status → message.
# --------------------------------------------------------------------------- #


class TestErrorMapping:
    def _http_error(self, code: int) -> urllib.error.HTTPError:
        return urllib.error.HTTPError(
            url=f"{BASE_URL}/me",
            code=code,
            msg=f"HTTP {code}",
            hdrs=None,
            fp=io.BytesIO(b"error body"),
        )

    def test_401_auth_failed(self, monkeypatch):
        _patch_open(monkeypatch, [self._http_error(401)])
        client = PSClient("key")
        with pytest.raises(PSClientError, match="PS API auth failed"):
            client.get_me()

    def test_403_forbidden(self, monkeypatch):
        _patch_open(monkeypatch, [self._http_error(403)])
        client = PSClient("key")
        with pytest.raises(PSClientError, match="PS API forbidden"):
            client.get_me()

    def test_429_rate_limited(self, monkeypatch):
        _patch_open(monkeypatch, [self._http_error(429)])
        client = PSClient("key")
        with pytest.raises(PSClientError, match="PS API rate limited"):
            client.get_me()

    def test_500_unavailable(self, monkeypatch):
        _patch_open(monkeypatch, [self._http_error(500)])
        client = PSClient("key")
        with pytest.raises(PSClientError, match="PS API unavailable"):
            client.get_me()

    def test_503_unavailable(self, monkeypatch):
        _patch_open(monkeypatch, [self._http_error(503)])
        client = PSClient("key")
        with pytest.raises(PSClientError, match="PS API unavailable"):
            client.get_me()

    def test_other_status_generic(self, monkeypatch):
        _patch_open(monkeypatch, [self._http_error(418)])
        client = PSClient("key")
        with pytest.raises(PSClientError, match="PS API error: 418"):
            client.get_me()

    def test_timeout(self, monkeypatch):
        err = urllib.error.URLError(TimeoutError("timed out"))
        _patch_open(monkeypatch, [err])
        client = PSClient("key")
        with pytest.raises(PSClientError, match="PS API timeout"):
            client.get_me()

    def test_network_error(self, monkeypatch):
        err = urllib.error.URLError(ConnectionRefusedError("refused"))
        _patch_open(monkeypatch, [err])
        client = PSClient("key")
        with pytest.raises(PSClientError, match="PS API network error"):
            client.get_me()

    def test_bare_timeout_error(self, monkeypatch):
        _patch_open(monkeypatch, [TimeoutError("bare timeout")])
        client = PSClient("key")
        with pytest.raises(PSClientError, match="PS API timeout"):
            client.get_me()


# --------------------------------------------------------------------------- #
# URL validation — reject non-PS, http, credentials, wrong path.
# --------------------------------------------------------------------------- #


class TestUrlValidation:
    def test_valid_url_ok(self):
        url = f"{BASE_URL}/me"
        assert _validated_api_url(url, "/me") == url

    def test_http_rejected(self):
        with pytest.raises(PSClientError, match="outside the requested endpoint"):
            _validated_api_url("http://api.pocketsmith.com/v2/me", "/me")

    def test_wrong_host_rejected(self):
        with pytest.raises(PSClientError, match="outside the requested endpoint"):
            _validated_api_url("https://evil.com/v2/me", "/me")

    def test_credentials_in_url_rejected(self):
        with pytest.raises(PSClientError, match="outside the requested endpoint"):
            _validated_api_url("https://user:pass@api.pocketsmith.com/v2/me", "/me")

    def test_wrong_path_rejected(self):
        with pytest.raises(PSClientError, match="outside the requested endpoint"):
            _validated_api_url(f"{BASE_URL}/users/1", "/me")

    def test_fragment_rejected(self):
        with pytest.raises(PSClientError, match="outside the requested endpoint"):
            _validated_api_url(f"{BASE_URL}/me#frag", "/me")

    def test_nonstandard_port_rejected(self):
        with pytest.raises(PSClientError, match="outside the requested endpoint"):
            _validated_api_url("https://api.pocketsmith.com:8080/v2/me", "/me")

    def test_non_url_rejected(self):
        # urlsplit parses plain text as path — scheme empty → outside endpoint.
        with pytest.raises(PSClientError, match="outside the requested endpoint"):
            _validated_api_url("not a url at all", "/me")


# --------------------------------------------------------------------------- #
# Redirect rejection — _NoRedirectHandler returns None.
# --------------------------------------------------------------------------- #


class TestNoRedirectHandler:
    def test_redirect_request_returns_none(self):
        handler = _NoRedirectHandler()
        result = handler.redirect_request(
            request=MagicMock(),
            fp=MagicMock(),
            code=302,
            msg="Found",
            headers=MagicMock(),
            newurl="https://evil.com/redirect",
        )
        assert result is None
