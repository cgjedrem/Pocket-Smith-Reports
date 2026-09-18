"""F2-BE bills dashboard read endpoint — 17 acceptance tests.

Covers L4 contracts + edge cases per `designs/f2-bills-dashboard.md`.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date

from budget_api.services import storage

# -- Helpers -----------------------------------------------------------------


def _valid_snapshot(
    month: str = "2026-07",
    *,
    is_past: bool = False,
    is_current: bool = True,
    is_future: bool = False,
    with_warnings: bool = False,
) -> dict:
    """Minimal valid BillsSnapshot-shaped dict for tests."""
    return {
        "schema_version": 3,
        "month": month,
        "month_label": "July 2026",
        "is_past": is_past,
        "is_current": is_current,
        "is_future": is_future,
        "synced_at": "2026-08-02T12:00:00Z",
        "bills_count": 12,
        "buys_count": 3,
        "warnings": ["Prior month auto-fetched"] if with_warnings else [],
        "partners": [
            {
                "partner": "Fixture A",
                "salary": 42000,
                "bills": 15500,
                "planned_cc_buys": 0,
                "everyday_budget": 8200,
                "savings_transfer": 5000,
                "savings_delta": 2000,
                "savings_balance": 32000,
                "estimated_cc_bill": 9800,
                "real_cc_bill": None,
                "real_bills": None,
                "cc_usage": 4200,
                "budget_usage": 4200,
                "net": 16700,
                "status": "covered",
                "events": [],
            }
        ],
        "source_counts": {
            "ps_events_fetched": 142,
            "ps_transactions_fetched": 38,
            "events_kept_after_filter": 22,
        },
    }


def _write_snapshot(tmp_private_dir, month: str, payload: dict) -> None:
    """Atomic-write a snapshot into tmp private dir."""
    storage.atomic_write_json(storage.bills_dashboard_path(month), payload)


# -- Tests -------------------------------------------------------------------


# 1
def test_dashboard_happy_path(client, tmp_private_dir):
    """200 + body matches file content, with kind flags re-derived at read
    time (PR65 review — sync-stamped kind goes stale at month flip)."""
    payload = _valid_snapshot("2026-07")
    _write_snapshot(tmp_private_dir, "2026-07", payload)

    response = client.get("/api/bills/dashboard", params={"month": "2026-07"})

    assert response.status_code == 200
    body = response.json()
    # 2026-07 < current month → re-derived as past regardless of the
    # is_current=true stamped in the file.
    assert body["is_past"] is True
    assert body["is_current"] is False
    assert body["is_future"] is False
    # Everything else verbatim.
    expected = {**payload, "is_past": True, "is_current": False, "is_future": False}
    assert body == expected


# 2
def test_dashboard_past_month(client, tmp_private_dir):
    """200 + is_past: true."""
    payload = _valid_snapshot("2026-05", is_past=True, is_current=False)
    _write_snapshot(tmp_private_dir, "2026-05", payload)

    response = client.get("/api/bills/dashboard", params={"month": "2026-05"})

    assert response.status_code == 200
    assert response.json()["is_past"] is True


# 3
def test_dashboard_future_month(client, tmp_private_dir):
    """200 + is_future: true."""
    # The endpoint re-derives is_past/is_current/is_future from the live
    # clock at read time, so a hard-coded "future" month eventually becomes
    # current and this test rots. Compute a month that's always future.
    today = date.today()
    future = f"{today.year + (1 if today.month == 12 else 0):04d}-{(today.month % 12) + 1:02d}"
    payload = _valid_snapshot(future, is_current=False, is_future=True)
    _write_snapshot(tmp_private_dir, future, payload)

    response = client.get("/api/bills/dashboard", params={"month": future})

    assert response.status_code == 200
    assert response.json()["is_future"] is True


# 4
def test_dashboard_warnings_in_body(client, tmp_private_dir):
    """200 + warnings array present and non-empty."""
    payload = _valid_snapshot("2026-07", with_warnings=True)
    _write_snapshot(tmp_private_dir, "2026-07", payload)

    response = client.get("/api/bills/dashboard", params={"month": "2026-07"})

    assert response.status_code == 200
    body = response.json()
    assert "warnings" in body
    assert body["warnings"] == ["Prior month auto-fetched"]


# 5
def test_dashboard_missing_snapshot(client, tmp_private_dir):
    """404 with sync URL hint."""
    response = client.get("/api/bills/dashboard", params={"month": "2026-03"})

    assert response.status_code == 404
    assert response.json() == {
        "detail": (
            "No snapshot for 2026-03. "
            "Run GET /api/sync?start_month=2026-03&end_month=2026-03 to generate one."
        )
    }


# 6
def test_dashboard_invalid_month_format_foo(client, tmp_private_dir):
    """400 — month=foo."""
    response = client.get("/api/bills/dashboard", params={"month": "foo"})

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid month format"


# 7
def test_dashboard_invalid_month_format_short(client, tmp_private_dir):
    """400 — month=2026-7 (single-digit month)."""
    response = client.get("/api/bills/dashboard", params={"month": "2026-7"})

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid month format"


# 8
def test_dashboard_empty_month(client, tmp_private_dir):
    """400 — month= (empty). FastAPI treats empty as missing required."""
    response = client.get("/api/bills/dashboard", params={"month": ""})

    # Empty value → FastAPI validation 422 → main.py rewrites to 400.
    assert response.status_code == 400


# 9
def test_dashboard_missing_month(client, tmp_private_dir):
    """400 — no month param at all."""
    response = client.get("/api/bills/dashboard")

    # Missing required query param → 422 → main.py rewrites to 400.
    assert response.status_code == 400


# 10
def test_dashboard_path_traversal(client, tmp_private_dir):
    """400 — month=../../etc/passwd fails regex."""
    response = client.get("/api/bills/dashboard", params={"month": "../../etc/passwd"})

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid month format"


# 11
def test_dashboard_invalid_calendar(client, tmp_private_dir):
    """404 — month=2026-13 passes regex, file not found."""
    response = client.get("/api/bills/dashboard", params={"month": "2026-13"})

    # Regex matches \d{4}-\d{2}. file doesn't exist → 404.
    assert response.status_code == 404
    assert "2026-13" in response.json()["detail"]


# 12
def test_dashboard_corrupt_json_500(client, tmp_private_dir, capsys):
    """500 + stderr traceback on invalid JSON."""
    path = storage.bills_dashboard_path("2026-07")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json{", encoding="utf-8")

    response = client.get("/api/bills/dashboard", params={"month": "2026-07"})

    assert response.status_code == 500
    assert response.json() == {"detail": "internal error reading snapshot"}
    captured = capsys.readouterr()
    assert "Traceback" in captured.err


# 13
def test_dashboard_empty_file_500(client, tmp_private_dir, capsys):
    """500 + stderr traceback on empty file (JSONDecodeError)."""
    path = storage.bills_dashboard_path("2026-07")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")

    response = client.get("/api/bills/dashboard", params={"month": "2026-07"})

    assert response.status_code == 500
    assert response.json() == {"detail": "internal error reading snapshot"}
    captured = capsys.readouterr()
    assert "Traceback" in captured.err


# 14
def test_dashboard_concurrent_reads(client, tmp_private_dir):
    """10 parallel reads all return 200."""
    _write_snapshot(tmp_private_dir, "2026-07", _valid_snapshot("2026-07"))

    def _fetch() -> int:
        return client.get(
            "/api/bills/dashboard", params={"month": "2026-07"}
        ).status_code

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _: _fetch(), range(10)))

    assert results == [200] * 10


# 15
def test_dashboard_cache_control_header(client, tmp_private_dir):
    """200 + Cache-Control: no-store."""
    _write_snapshot(tmp_private_dir, "2026-07", _valid_snapshot("2026-07"))

    response = client.get("/api/bills/dashboard", params={"month": "2026-07"})

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"


# 16
def test_dashboard_returns_full_snapshot(client, tmp_private_dir):
    """Body shape sanity — all top-level fields present."""
    payload = _valid_snapshot("2026-07")
    _write_snapshot(tmp_private_dir, "2026-07", payload)

    response = client.get("/api/bills/dashboard", params={"month": "2026-07"})
    body = response.json()

    assert body["schema_version"] == 3
    assert body["month"] == "2026-07"
    assert body["month_label"] == "July 2026"
    assert body["bills_count"] == 12
    assert body["buys_count"] == 3
    assert isinstance(body["partners"], list)
    assert len(body["partners"]) == 1
    partner = body["partners"][0]
    assert partner["partner"] == "Fixture A"
    # All 14 derived fields present.
    for field in (
        "salary",
        "bills",
        "planned_cc_buys",
        "everyday_budget",
        "savings_transfer",
        "savings_delta",
        "savings_balance",
        "estimated_cc_bill",
        "real_cc_bill",
        "real_bills",
        "cc_usage",
        "budget_usage",
        "net",
        "status",
    ):
        assert field in partner


# 17
def test_dashboard_source_counts_in_body(client, tmp_private_dir):
    """source_counts present in body."""
    payload = _valid_snapshot("2026-07")
    _write_snapshot(tmp_private_dir, "2026-07", payload)

    response = client.get("/api/bills/dashboard", params={"month": "2026-07"})
    body = response.json()

    assert "source_counts" in body
    sc = body["source_counts"]
    assert sc["ps_events_fetched"] == 142
    assert sc["ps_transactions_fetched"] == 38
    assert sc["events_kept_after_filter"] == 22
