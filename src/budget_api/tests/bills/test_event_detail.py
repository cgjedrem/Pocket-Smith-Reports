"""F2-BE bills dashboard event detail endpoint â€” 20 acceptance tests.

Covers L4 contracts + edge cases per `docs/design/f2-bills-dashboard.md` sub-feature 4.
Reuses helpers from `test_events.py` (copy = isolation, no cross-file import).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from budget_api.services import storage

# -- Helpers (copied from test_events.py for isolation) ---------------------


def _valid_event(
    *,
    id: str = "evt-1",  # noqa: A002
    date: str = "2026-07-15",
    day: int = 15,
    title: str | None = None,  # legacy: callers pass `category=` instead
    type: str = "bill",  # noqa: A002
    category: str = "Bills",
    account: str = "FxA Check",
    partner: str = "Fixture A",
    amount: float = 100.0,
    is_cc_payment: bool = False,
    is_matched: bool | None = None,
) -> dict:
    """Minimal valid BillsEvent-shaped dict.

    New contract: title=category, account=bank name. The `category` kwarg
    stays for backward-compat with existing call sites.
    """
    return {
        "id": id,
        "date": date,
        "day": day,
        "title": title if title is not None else category,
        "type": type,
        "account": account,
        "partner": partner,
        "amount": amount,
        "is_cc_payment": is_cc_payment,
        "is_matched": is_matched,
    }


def _valid_snapshot_with_events(
    month: str,
    events_by_partner: dict[str, list[dict]] | None = None,
) -> dict:
    """Snapshot with events. `events_by_partner = {"Fixture A": [evt, ...]}`."""
    if events_by_partner is None:
        events_by_partner = {}
    partners = []
    for partner_name, evts in events_by_partner.items():
        partners.append(
            {
                "partner": partner_name,
                "salary": 0.0,
                "bills": 0.0,
                "planned_cc_buys": 0,
                "everyday_budget": 0,
                "savings_transfer": 0.0,
                "savings_delta": 0.0,
                "savings_balance": 0.0,
                "estimated_cc_bill": None,
                "real_cc_bill": None,
                "real_bills": None,
                "cc_usage": 0.0,
                "budget_usage": 0.0,
                "net": 0.0,
                "status": "covered",
                "events": evts,
            }
        )
    return {
        "schema_version": 3,
        "month": month,
        "month_label": "Test",
        "is_past": False,
        "is_current": True,
        "is_future": False,
        "synced_at": "2026-08-02T12:00:00Z",
        "bills_count": 0,
        "buys_count": 0,
        "warnings": [],
        "partners": partners,
        "source_counts": {
            "ps_events_fetched": 0,
            "ps_transactions_fetched": 0,
            "events_kept_after_filter": 0,
        },
    }


def _write_snapshot(tmp_private_dir, month: str, payload: dict) -> None:
    """Atomic-write a snapshot into tmp private dir."""
    storage.atomic_write_json(storage.bills_dashboard_path(month), payload)


def _default_5_events() -> dict[str, list[dict]]:
    """Default 5-event fixture (3 Fixture A, 2 Fixture B, mixed types/dates)."""
    return {
        "Fixture A": [
            _valid_event(
                id="c1",
                date="2026-07-10",
                type="bill",
                category="Bills",
                partner="Fixture A",
            ),
            _valid_event(
                id="c2",
                date="2026-07-15",
                type="salary",
                category="Income",
                partner="Fixture A",
            ),
            _valid_event(
                id="c3",
                date="2026-07-20",
                type="buy",
                category="Groceries",
                partner="Fixture A",
            ),
        ],
        "Fixture B": [
            _valid_event(
                id="r1",
                date="2026-07-12",
                type="savings",
                category="Savings",
                partner="Fixture B",
            ),
            _valid_event(
                id="r2",
                date="2026-07-18",
                type="bill",
                category="Bills",
                partner="Fixture B",
            ),
        ],
    }


# -- Tests -------------------------------------------------------------------


# 1
def test_event_detail_happy_path(client, tmp_private_dir):
    """200 + bare event with id=c1."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/event",
        params={"id": "c1", "month": "2026-07"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "c1"
    # No envelope â€” bare event dict, no `event` wrapper.
    assert "events" not in body
    assert "total" not in body


# 2
def test_event_detail_full_event_body(client, tmp_private_dir):
    """200 + all 10 BillsEvent fields asserted."""
    full_event = _valid_event(
        id="full-evt",
        date="2026-07-15",
        day=15,
        category="Salary",
        type="salary",
        account="FxA Check Nordic Bank",
        partner="Fixture A",
        amount=42000.0,
        is_cc_payment=False,
        is_matched=None,
    )
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", {"Fixture A": [full_event]}),
    )

    response = client.get(
        "/api/bills/dashboard/event",
        params={"id": "full-evt", "month": "2026-07"},
    )

    assert response.status_code == 200
    body = response.json()
    # All 10 fields present, exact values.
    assert body == full_event
    assert body["id"] == "full-evt"
    assert body["date"] == "2026-07-15"
    assert body["day"] == 15
    assert body["title"] == "Salary"
    assert body["type"] == "salary"
    assert body["account"] == "FxA Check Nordic Bank"
    assert body["partner"] == "Fixture A"
    assert body["amount"] == 42000.0
    assert body["is_cc_payment"] is False
    assert body["is_matched"] is None


# 3
def test_event_detail_first_match_wins(client, tmp_private_dir):
    """Duplicate id across partners â†’ first (in file order) wins."""
    dup_event_partner_a = _valid_event(
        id="dup", date="2026-07-10", partner="Fixture A", amount=100.0
    )
    dup_event_partner_b = _valid_event(
        id="dup", date="2026-07-20", partner="Fixture B", amount=200.0
    )
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events(
            "2026-07",
            {"Fixture A": [dup_event_partner_a], "Fixture B": [dup_event_partner_b]},
        ),
    )

    response = client.get(
        "/api/bills/dashboard/event",
        params={"id": "dup", "month": "2026-07"},
    )

    assert response.status_code == 200
    body = response.json()
    # First match in snapshot order = Fixture A's version.
    assert body["partner"] == "Fixture A"
    assert body["amount"] == 100.0


# 4
def test_event_detail_not_found_404(client, tmp_private_dir):
    """404 with distinct `Event {id} not found in {month}` body."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/event",
        params={"id": "nonexistent", "month": "2026-07"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Event nonexistent not found in 2026-07"}


# 5
def test_event_detail_snapshot_missing_404(client, tmp_private_dir):
    """404 with sync-URL body â€” same shape as sub-features 2 + 3."""
    response = client.get(
        "/api/bills/dashboard/event",
        params={"id": "c1", "month": "2026-03"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": (
            "No snapshot for 2026-03. "
            "Run GET /api/sync?start_month=2026-03&end_month=2026-03 to generate one."
        )
    }


# 6
def test_event_detail_missing_id_400(client, tmp_private_dir):
    """Missing `id` query param â†’ 400 from FastAPI auto-gen."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/event",
        params={"month": "2026-07"},
    )

    # FastAPI 422 â†’ main.py 400 rewrite.
    assert response.status_code == 400
    body = response.json()
    assert "id" in body["detail"].lower() or "field required" in body["detail"].lower()


# 7
def test_event_detail_missing_month_400(client, tmp_private_dir):
    """Missing `month` query param â†’ 400 from FastAPI auto-gen."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/event",
        params={"id": "c1"},
    )

    assert response.status_code == 400
    body = response.json()
    assert (
        "month" in body["detail"].lower() or "field required" in body["detail"].lower()
    )


# 8
def test_event_detail_empty_id_400(client, tmp_private_dir):
    """Empty `id` â†’ 400 (regex requires >=1 char)."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/event",
        params={"id": "", "month": "2026-07"},
    )

    # Empty â†’ FastAPI 422 â†’ main.py 400 rewrite (same as test_dashboard_empty_month).
    assert response.status_code == 400


# 9
def test_event_detail_path_traversal_id_400(client, tmp_private_dir):
    """Path-traversal chars in `id` â†’ 400 (regex rejects)."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    for bad_id in ("a/b", "a.c", "a\nb", "a\\b"):
        response = client.get(
            "/api/bills/dashboard/event",
            params={"id": bad_id, "month": "2026-07"},
        )
        # URL-encodable chars go through; \n may 400 on its own. All bad.
        assert response.status_code in (
            400,
        ), f"id={bad_id!r} expected 400, got {response.status_code}"


# 10
def test_event_detail_id_too_long_400(client, tmp_private_dir):
    """`id` length 65 â†’ 400 (regex caps at 64)."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/event",
        params={"id": "a" * 65, "month": "2026-07"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": ["invalid event id format"]}


# 11
def test_event_detail_bad_month_400(client, tmp_private_dir):
    """`month=foo` â†’ 400 with custom month message."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/event",
        params={"id": "c1", "month": "foo"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": ["invalid month format"]}


# 12
def test_event_detail_multi_error_alphabetical(client, tmp_private_dir):
    """Both `id` and `month` bad â†’ 400 list-detail, alphabetical (id, month)."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/event",
        params={"id": "", "month": "foo"},
    )

    # id bad (empty) + month bad (foo). id checked first by handler.
    assert response.status_code == 400
    detail = response.json()["detail"]
    # Both must be in the list; order = handler order (id, month) = alphabetical.
    assert "invalid event id format" in detail
    assert "invalid month format" in detail
    assert detail.index("invalid event id format") < detail.index(
        "invalid month format"
    )


# 13
def test_event_detail_corrupt_json_500(client, tmp_private_dir, capsys):
    """Corrupt JSON â†’ 500 generic + stderr traceback."""
    path = storage.bills_dashboard_path("2026-07")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json{", encoding="utf-8")

    response = client.get(
        "/api/bills/dashboard/event",
        params={"id": "c1", "month": "2026-07"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "internal error reading snapshot"}
    captured = capsys.readouterr()
    assert "Traceback" in captured.err


# 14
def test_event_detail_empty_file_500(client, tmp_private_dir, capsys):
    """Empty file â†’ 500 generic + stderr traceback."""
    path = storage.bills_dashboard_path("2026-07")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")

    response = client.get(
        "/api/bills/dashboard/event",
        params={"id": "c1", "month": "2026-07"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "internal error reading snapshot"}
    captured = capsys.readouterr()
    assert "Traceback" in captured.err


# 15
def test_event_detail_shape_missing_partners_500(client, tmp_private_dir):
    """Snapshot has no `partners` key â†’ 500 with shape suffix."""
    _write_snapshot(
        tmp_private_dir, "2026-07", {"schema_version": 1, "month": "2026-07"}
    )

    response = client.get(
        "/api/bills/dashboard/event",
        params={"id": "c1", "month": "2026-07"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "internal error reading snapshot: missing partners"
    }


# 16
def test_event_detail_shape_events_not_list_500(client, tmp_private_dir):
    """partners[].events not a list â†’ 500 with shape suffix."""
    snapshot = {
        "schema_version": 1,
        "month": "2026-07",
        "partners": [
            {
                "partner": "Fixture A",
                "events": "not-a-list",  # shape error
            }
        ],
    }
    _write_snapshot(tmp_private_dir, "2026-07", snapshot)

    response = client.get(
        "/api/bills/dashboard/event",
        params={"id": "c1", "month": "2026-07"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "internal error reading snapshot: events is not a list"
    }


# 17
def test_event_detail_shape_partner_block_not_dict_500(client, tmp_private_dir):
    """partners[i] is not a dict â†’ 500 with shape suffix."""
    snapshot = {
        "schema_version": 1,
        "month": "2026-07",
        "partners": ["not-a-dict"],  # shape error
    }
    _write_snapshot(tmp_private_dir, "2026-07", snapshot)

    response = client.get(
        "/api/bills/dashboard/event",
        params={"id": "c1", "month": "2026-07"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "internal error reading snapshot: partner block is not a dict"
    }


# 18
def test_event_detail_concurrent_reads(client, tmp_private_dir):
    """10 parallel reads all return 200."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    def _fetch() -> int:
        return client.get(
            "/api/bills/dashboard/event",
            params={"id": "c1", "month": "2026-07"},
        ).status_code

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _: _fetch(), range(10)))

    assert results == [200] * 10


# 19
def test_event_detail_cache_control_on_200(client, tmp_private_dir):
    """Cache-Control: no-store on 200."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/event",
        params={"id": "c1", "month": "2026-07"},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"


# 20
@pytest.mark.parametrize(
    "params,expected_status",
    [
        # 400 (invalid id format)
        ({"id": "a" * 65, "month": "2026-07"}, 400),
        # 404 (event not found)
        ({"id": "nonexistent", "month": "2026-07"}, 404),
        # 500 (corrupt json)
        ({"id": "c1", "month": "2026-07"}, 500),
    ],
)
def test_event_detail_cache_control_on_errors(
    client, tmp_private_dir, capsys, params, expected_status
):
    """Cache-Control: no-store on 400 / 404 / 500."""
    if expected_status == 500:
        # Set up corrupt file for the 500 case.
        path = storage.bills_dashboard_path("2026-07")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json{", encoding="utf-8")
    else:
        _write_snapshot(
            tmp_private_dir,
            "2026-07",
            _valid_snapshot_with_events("2026-07", _default_5_events()),
        )

    response = client.get("/api/bills/dashboard/event", params=params)

    assert response.status_code == expected_status
    assert response.headers["cache-control"] == "no-store"
    if expected_status == 500:
        # Stderr still logs traceback (no regression on logging).
        captured = capsys.readouterr()
        assert "Traceback" in captured.err
