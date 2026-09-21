"""F2-BE bills dashboard events endpoint — 42 acceptance tests.

Covers L4 contracts + edge cases per `docs/design/f2-bills-dashboard.md` sub-feature 3.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from budget_api.services import storage

# -- Helpers -----------------------------------------------------------------


def _valid_event(
    *,
    id: str = "evt-1",
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
    stays for backward-compat with all the existing call sites that
    pass `category="Income"` etc.
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


# Default 5-event fixture (mix of partners, types, dates).
def _default_5_events() -> dict[str, list[dict]]:
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
def test_events_happy_path_all_events(client, tmp_private_dir):
    """200, 5 events, total=5 — no filters."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get("/api/bills/dashboard/events", params={"month": "2026-07"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert len(body["events"]) == 5


# 2
def test_events_no_filters_default_order_asc(client, tmp_private_dir):
    """Default sort: (date, partner, id) asc."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get("/api/bills/dashboard/events", params={"month": "2026-07"})

    assert response.status_code == 200
    body = response.json()
    keys = [(e["date"], e["partner"], e["id"]) for e in body["events"]]
    assert keys == sorted(keys)
    # First by date: c1 on 2026-07-10.
    assert body["events"][0]["id"] == "c1"


# 3
def test_events_order_desc_reverses_date_first(client, tmp_private_dir):
    """?order=desc → date desc, partner/id still asc as tiebreakers."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "order": "desc"},
    )

    assert response.status_code == 200
    body = response.json()
    # First by date desc: c3 on 2026-07-20.
    assert body["events"][0]["id"] == "c3"
    # Date order is desc overall.
    dates = [e["date"] for e in body["events"]]
    assert dates == sorted(dates, reverse=True)


# 3b — regression guard for Copilot review: same-date events must keep
# partner/id ascending tiebreaker even when ?order=desc.
def test_events_order_desc_same_date_partner_asc(client, tmp_private_dir):
    """Same-date events: ?order=desc flips date only, partner/id stay asc."""
    events_by_partner = {
        "Fixture A": [
            _valid_event(
                id="a1",
                date="2026-07-15",
                partner="Fixture A",
                type="bill",
                category="Utilities",
            ),
            _valid_event(
                id="a2",
                date="2026-07-15",
                partner="Fixture A",
                type="buy",
                category="Groceries",
            ),
            _valid_event(
                id="c1",
                date="2026-07-10",
                partner="Fixture A",
                type="salary",
                category="Income",
            ),
            _valid_event(
                id="c2",
                date="2026-07-10",
                partner="Fixture A",
                type="salary",
                category="Income",
            ),
        ],
        "Stine": [
            _valid_event(
                id="b1",
                date="2026-07-15",
                partner="Stine",
                type="bill",
                category="Utilities",
            ),
        ],
    }
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", events_by_partner),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "order": "desc"},
    )

    assert response.status_code == 200
    body = response.json()
    # Date desc: 2026-07-15 (3 events) then 2026-07-10 (2 events).
    assert [e["date"] for e in body["events"]] == [
        "2026-07-15",
        "2026-07-15",
        "2026-07-15",
        "2026-07-10",
        "2026-07-10",
    ]
    # Within 2026-07-15: Fixture A before Stine (partner asc), then id asc.
    same_date = [e for e in body["events"] if e["date"] == "2026-07-15"]
    assert [(e["partner"], e["id"]) for e in same_date] == [
        ("Fixture A", "a1"),
        ("Fixture A", "a2"),
        ("Stine", "b1"),
    ]
    # Within 2026-07-10: id asc.
    same_date2 = [e for e in body["events"] if e["date"] == "2026-07-10"]
    assert [e["id"] for e in same_date2] == ["c1", "c2"]


# 4
def test_events_filter_partner(client, tmp_private_dir):
    """?partner=Fixture A → only Fixture A's events."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "partner": "Fixture A"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert {e["partner"] for e in body["events"]} == {"Fixture A"}


# 5
def test_events_filter_partner_no_match(client, tmp_private_dir):
    """?partner=Nobody → 200, empty, total=0."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "partner": "Nobody"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["events"] == []


# 6
def test_events_filter_type_bill(client, tmp_private_dir):
    """?type=bill → only bills."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "type": "bill"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2  # c1 + r2
    assert {e["type"] for e in body["events"]} == {"bill"}


# 7
def test_events_filter_type_invalid(client, tmp_private_dir):
    """?type=income → 400, ["invalid type: income"]."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "type": "income"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": ["invalid type: income"]}


# 8
def test_events_filter_category_income(client, tmp_private_dir):
    """?category=Income → only Income category."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "category": "Income"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["events"][0]["title"] == "Income"
    assert body["events"][0]["account"] == "FxA Check"


# 9
def test_events_filter_category_case_sensitive(client, tmp_private_dir):
    """?category=income (lowercase) → empty (case-sensitive)."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "category": "income"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["events"] == []


# 10
def test_events_filter_date_range_inclusive(client, tmp_private_dir):
    """?from=2026-07-15&to=2026-07-20 → window [15, 20] inclusive."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "from": "2026-07-15", "to": "2026-07-20"},
    )

    assert response.status_code == 200
    body = response.json()
    # In window: c2 (15), r1 (12 NO), c3 (20), r2 (18) → c2, c3, r2.
    assert body["total"] == 3
    assert {e["id"] for e in body["events"]} == {"c2", "c3", "r2"}


# 11
def test_events_filter_date_same_day(client, tmp_private_dir):
    """?from=2026-07-15&to=2026-07-15 → that day only."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "from": "2026-07-15", "to": "2026-07-15"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["events"][0]["id"] == "c2"


# 12
def test_events_filter_date_from_greater_than_to(client, tmp_private_dir):
    """?from=2026-07-20&to=2026-07-15 → 200, empty, total=0 (no error)."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "from": "2026-07-20", "to": "2026-07-15"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["events"] == []


# 13
def test_events_filter_date_invalid_format(client, tmp_private_dir):
    """?from=foo → 400, ["invalid from date: foo"]."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "from": "foo"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": ["invalid from date: foo"]}


# 14
def test_events_filter_date_invalid_calendar(client, tmp_private_dir):
    """?from=2026-13-99 → 400, ["invalid from date: 2026-13-99"]."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "from": "2026-13-99"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": ["invalid from date: 2026-13-99"]}


# 15
def test_events_filter_date_invalid_feb_30(client, tmp_private_dir):
    """?to=2026-02-30 → 400, ["invalid to date: 2026-02-30"]."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "to": "2026-02-30"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": ["invalid to date: 2026-02-30"]}


# 16
def test_events_limit_first_n(client, tmp_private_dir):
    """?limit=2 → 2 events, total=5 (pre-clamp)."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "limit": "2"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert len(body["events"]) == 2


# 17
def test_events_limit_zero(client, tmp_private_dir):
    """?limit=0 → 400, ["limit must be >= 1"]."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "limit": "0"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": ["limit must be >= 1"]}


# 18
def test_events_limit_negative(client, tmp_private_dir):
    """?limit=-1 → 400, ["limit must be >= 1"]."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "limit": "-1"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": ["limit must be >= 1"]}


# 19
def test_events_limit_non_numeric(client, tmp_private_dir):
    """?limit=abc → 400, ["invalid limit: abc"]."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "limit": "abc"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": ["invalid limit: abc"]}


# 20
def test_events_limit_clamp_silently(client, tmp_private_dir):
    """?limit=10000 → first 1000 events (use 1100+ in fixture), total=full count."""
    events_big = [
        _valid_event(id=f"e{i:04d}", date=f"2026-07-{(i % 28) + 1:02d}")
        for i in range(1100)
    ]
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", {"Fixture A": events_big}),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "limit": "10000"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1100  # pre-clamp
    assert len(body["events"]) == 1000  # clamped to cap


# 21
def test_events_order_invalid(client, tmp_private_dir):
    """?order=foo → 400, ["invalid order: foo"]."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "order": "foo"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": ["invalid order: foo"]}


# 22
def test_events_combined_filters(client, tmp_private_dir):
    """All filters valid → 200, AND of all."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={
            "month": "2026-07",
            "partner": "Fixture A",
            "type": "bill",
            "category": "Bills",
            "from": "2026-07-01",
            "to": "2026-07-31",
            "order": "asc",
            "limit": "10",
        },
    )

    assert response.status_code == 200
    body = response.json()
    # Only c1 matches: Fixture A + bill + Bills + in date range.
    assert body["total"] == 1
    assert body["events"][0]["id"] == "c1"


# 23
def test_events_multi_error_collection(client, tmp_private_dir):
    """3 errors in alphabetical order: from, limit, type."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "type": "income", "limit": "0", "from": "bad"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": [
            "invalid from date: bad",
            "limit must be >= 1",
            "invalid type: income",
        ]
    }


# 24
def test_events_multi_error_month_and_type(client, tmp_private_dir):
    """?month=foo&type=bar → alphabetical: month before type."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "foo", "type": "bar"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": ["invalid month format", "invalid type: bar"]}


# 25
def test_events_snapshot_missing_404(client, tmp_private_dir):
    """No snapshot → 404 with sync URL hint."""
    response = client.get("/api/bills/dashboard/events", params={"month": "2026-03"})

    assert response.status_code == 404
    assert response.json() == {
        "detail": (
            "No snapshot for 2026-03. "
            "Run GET /api/sync?start_month=2026-03&end_month=2026-03 to generate one."
        )
    }


# 26
def test_events_corrupt_json_500(client, tmp_private_dir, capsys):
    """Garbage JSON → 500, generic, stderr traceback."""
    path = storage.bills_dashboard_path("2026-07")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json{", encoding="utf-8")

    response = client.get("/api/bills/dashboard/events", params={"month": "2026-07"})

    assert response.status_code == 500
    assert response.json() == {"detail": "internal error reading snapshot"}
    captured = capsys.readouterr()
    assert "Traceback" in captured.err


# 27
def test_events_empty_file_500(client, tmp_private_dir, capsys):
    """Empty file → 500, generic, stderr traceback."""
    path = storage.bills_dashboard_path("2026-07")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")

    response = client.get("/api/bills/dashboard/events", params={"month": "2026-07"})

    assert response.status_code == 500
    assert response.json() == {"detail": "internal error reading snapshot"}
    captured = capsys.readouterr()
    assert "Traceback" in captured.err


# 28
def test_events_shape_missing_partners_500(client, tmp_private_dir):
    """Valid JSON, no `partners` key → 500, "missing partners"."""
    _write_snapshot(
        tmp_private_dir, "2026-07", {"schema_version": 1, "month": "2026-07"}
    )

    response = client.get("/api/bills/dashboard/events", params={"month": "2026-07"})

    assert response.status_code == 500
    assert response.json() == {
        "detail": "internal error reading snapshot: missing partners"
    }


# 29
def test_events_shape_events_not_list_500(client, tmp_private_dir):
    """partners[].events is not a list → 500, "events is not a list"."""
    snapshot = {
        "schema_version": 1,
        "month": "2026-07",
        "partners": [
            {
                "partner": "Fixture A",
                "salary": 0.0,
                "planned_cc_buys": 0,
                "bills": 0.0,
                "everyday_budget": 0,
                "savings_transfer": 0.0,
                "savings_delta": 0.0,
                "savings_balance": 0.0,
                "estimated_cc_bill": None,
                "real_cc_bill": None,
                "cc_usage": 0.0,
                "budget_usage": 0.0,
                "net": 0.0,
                "status": "covered",
                "events": "not-a-list",  # shape error
            }
        ],
    }
    _write_snapshot(tmp_private_dir, "2026-07", snapshot)

    response = client.get("/api/bills/dashboard/events", params={"month": "2026-07"})

    assert response.status_code == 500
    assert response.json() == {
        "detail": "internal error reading snapshot: events is not a list"
    }


# 30
def test_events_repeated_10x(client, tmp_private_dir):
    """10 sequential reads all 200 (test client is sync, not parallel)."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    def _fetch() -> int:
        return client.get(
            "/api/bills/dashboard/events", params={"month": "2026-07"}
        ).status_code

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _: _fetch(), range(10)))

    assert results == [200] * 10


# 31
def test_events_cache_control_on_200(client, tmp_private_dir):
    """Cache-Control: no-store on 200."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get("/api/bills/dashboard/events", params={"month": "2026-07"})

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"


# 32
def test_events_cache_control_on_400(client, tmp_private_dir):
    """Cache-Control: no-store on 400."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "type": "income"},
    )

    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"


# 33
def test_events_cache_control_on_404(client, tmp_private_dir):
    """Cache-Control: no-store on 404."""
    response = client.get("/api/bills/dashboard/events", params={"month": "2026-03"})

    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


# 34
def test_events_empty_partner_value(client, tmp_private_dir):
    """?partner= → 200, no filter applied (all 5 events)."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "partner": ""},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5


# 35
def test_events_empty_category_value(client, tmp_private_dir):
    """?category= → 200, no filter applied (all 5 events)."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "category": ""},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5


# 36
def test_events_empty_type_value(client, tmp_private_dir):
    """?type= → 200, no validation, no filter (all 5 events)."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "type": ""},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5


# 37
def test_events_total_reflects_pre_clamp(client, tmp_private_dir):
    """Filter 100 events, ?limit=10 → total=100, events.length=10."""
    events_100 = [
        _valid_event(id=f"e{i:04d}", date=f"2026-07-{(i % 28) + 1:02d}")
        for i in range(100)
    ]
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", {"Fixture A": events_100}),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "limit": "10"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 100
    assert len(body["events"]) == 10


# 38
def test_events_default_limit_500(client, tmp_private_dir):
    """No limit param → max 500 events (use 600-event fixture, expect 500)."""
    events_600 = [
        _valid_event(id=f"e{i:04d}", date=f"2026-07-{(i % 28) + 1:02d}")
        for i in range(600)
    ]
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", {"Fixture A": events_600}),
    )

    response = client.get("/api/bills/dashboard/events", params={"month": "2026-07"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 600  # pre-clamp
    assert len(body["events"]) == 500  # default limit


# 39
def test_events_empty_from_value(client, tmp_private_dir):
    """?from= → 200, no filter applied (all 5 events)."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "from": ""},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5


# 40
def test_events_empty_to_value(client, tmp_private_dir):
    """?to= → 200, no filter applied (all 5 events)."""
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", _default_5_events()),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "to": ""},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5


# 41
def test_events_empty_limit_value(client, tmp_private_dir):
    """?limit= → 200, default 500 limit applied."""
    events_600 = [
        _valid_event(id=f"e{i:04d}", date=f"2026-07-{(i % 28) + 1:02d}")
        for i in range(600)
    ]
    _write_snapshot(
        tmp_private_dir,
        "2026-07",
        _valid_snapshot_with_events("2026-07", {"Fixture A": events_600}),
    )

    response = client.get(
        "/api/bills/dashboard/events",
        params={"month": "2026-07", "limit": ""},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 600  # pre-clamp
    assert len(body["events"]) == 500  # default limit (empty → None → default)


# 42
def test_events_cache_control_on_500(client, tmp_private_dir, capsys):
    """Cache-Control: no-store on 500 (corrupt JSON)."""
    path = storage.bills_dashboard_path("2026-07")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json{", encoding="utf-8")

    response = client.get("/api/bills/dashboard/events", params={"month": "2026-07"})

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    # Stderr still logs traceback (no regression on logging).
    captured = capsys.readouterr()
    assert "Traceback" in captured.err
