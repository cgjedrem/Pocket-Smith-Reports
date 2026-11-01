"""Merge guards for lifestyle creep beside runway.

Covers route ownership, the shared validation handler, no-store, and storage
independence. Synthetic temp storage only.
"""

import json

import pytest
from fastapi.testclient import TestClient

from budget_api.services import runway, storage
from budget_api.tests.bills.test_lifestyle_creep import MONTHS
from budget_api.tests.bills.test_lifestyle_creep_api import row, snapshots  # noqa: F401
from budget_api.tests.runway.synthetic import NOW, World

LIFESTYLE = "/api/bills/lifestyle-creep"
DASHBOARD = "/api/bills/dashboard"
RESULT = "/api/bills/runway"
SETTINGS = "/api/settings/runway"
RUNWAY_QUERY = {"detail": "Runway endpoints do not accept query parameters."}
RUNWAY_REQUEST = {
    "detail": "Invalid runway request. Provide only liquid_account_ids as unique positive account ID strings."
}
FINITE = "threshold_percent must be a finite decimal between 1 and 100"
RANGE = "threshold_percent must be between 1 and 100"
REPEATED = "month and threshold_percent must not be repeated"


class Spy:
    """ASGI wrapper that records the endpoint routing chose for each request."""

    def __init__(self, app):
        self.app = app
        self.chosen = []

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)
        if scope["type"] == "http":
            endpoint = getattr(scope.get("route"), "endpoint", None)
            self.chosen.append(None if endpoint is None else (endpoint.__module__, endpoint.__name__))


# Fail validation on purpose. Routing picks endpoint before handler body or storage read.
@pytest.mark.parametrize("method,url,kwargs,owner", [
    ("GET", LIFESTYLE + "?month=bad", {}, ("budget_api.routers.bills", "lifestyle_creep_history")),
    ("GET", DASHBOARD, {}, ("budget_api.routers.bills", "dashboard")),
    ("GET", RESULT + "?x=1", {}, ("budget_api.routers.runway", "result")),
    ("GET", SETTINGS + "?x=1", {}, ("budget_api.routers.runway", "settings")),
    ("PUT", SETTINGS, {"json": {}}, ("budget_api.routers.runway", "save")),
])
def test_routing_reaches_the_intended_endpoint(client, method, url, kwargs, owner):
    spy = Spy(client.app)
    response = TestClient(spy).request(method, url, **kwargs)
    assert response.status_code == 400
    assert spy.chosen == [owner]


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_lifestyle_path_is_read_only(client, method):
    response = client.request(method, LIFESTYLE, params={"month": "2026-10"})
    assert response.status_code == 405
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("query,detail", [
    ("", "query -> month: Field required"),
    ("?month=", "invalid month format"),
    ("?month=2026-1", "invalid month format"),
    ("?month=2026-13", "invalid calendar month"),
    ("?month=0001-02", "reference range precedes the earliest representable month"),
    # Deterministic only because the imported `snapshots` fixture freezes the
    # service clock to 2027-01-10; without it "2027-02" would depend on today.
    ("?month=2027-02", "month must not be later than the current month"),
    ("?month=2026-10&month=2026-10", REPEATED),
    ("?month=2026-10&threshold_percent=1&threshold_percent=1", REPEATED),
    ("?month=2026-10&threshold_percent=NaN", FINITE),
    ("?month=2026-10&threshold_percent=true", FINITE),
    ("?month=2026-10&threshold_percent=101", RANGE),
    ("?month=2026-10&threshold_percent=0.5", RANGE),
])
def test_lifestyle_validation_keeps_documented_400_body(client, snapshots, query, detail):
    response = client.get(LIFESTYLE + query)
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"detail": detail}


def test_missing_month_flattens_like_other_bills_routes(client):
    lifestyle, dashboard = client.get(LIFESTYLE), client.get(DASHBOARD)
    assert lifestyle.status_code == dashboard.status_code == 400
    assert lifestyle.json() == dashboard.json()


@pytest.mark.parametrize("query", [
    "?month=RAW-MARKER", "?month=2026-10&threshold_percent=RAW-MARKER",
])
def test_lifestyle_400_has_no_raw_query_and_no_runway_text(client, snapshots, query):
    response = client.get(LIFESTYLE + query)
    assert response.status_code == 400
    assert "RAW-MARKER" not in response.text
    assert "runway" not in response.text.lower()


@pytest.mark.parametrize("query", ["?month=2026-10", "?month=2026-10&threshold_percent=20"])
@pytest.mark.parametrize("path", [RESULT, SETTINGS])
def test_runway_get_keeps_its_own_query_rejection(client, path, query):
    response = client.get(path + query)
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == RUNWAY_QUERY


@pytest.mark.parametrize("body", [
    {}, {"liquid_account_ids": "1100001"},
    {"liquid_account_ids": ["1100001"], "threshold_percent": "20"},
])
def test_runway_put_keeps_its_own_validation_body(client, body):
    response = client.put(SETTINGS, json=body)
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == RUNWAY_REQUEST
    assert "lifestyle" not in response.text.lower()


# Bills snapshot schema versions vs runway config schema: separate version spaces.
VARIANTS = [
    ("schema6", 200, "ready"),
    ("schema5", 200, "insufficient_history"),
    ("schema1", 200, "insufficient_history"),
    ("unversioned", 200, "insufficient_history"),
    ("corrupt", 500, None),
    ("absent", 200, "insufficient_history"),
]


def write_variant(variant):
    for month in MONTHS:
        path = storage.bills_dashboard_path(month)
        value = dict(schema_version=6, month=month, partners=[row()])
        if variant in {"schema5", "schema1", "unversioned"}:
            value["partners"][0].pop("cc_spend_history")
            if variant == "unversioned":
                value.pop("schema_version")
            else:
                value["schema_version"] = int(variant[-1])
        if variant == "absent":
            path.unlink(missing_ok=True)
        elif variant == "corrupt":
            path.write_text("{not json", encoding="utf-8")
        else:
            path.write_text(json.dumps(value), encoding="utf-8")


def files(root):
    return {p.name: p.read_bytes() for p in root.iterdir()}


@pytest.mark.parametrize("variant,code,state", VARIANTS)
def test_runway_and_lifestyle_ignore_each_others_files(
    client, snapshots, tmp_private_dir, monkeypatch, variant, code, state,
):
    monkeypatch.setattr(runway, "local_now", lambda: NOW)
    world = World(tmp_private_dir)
    world.write()
    write_variant("absent")
    baseline = client.get(RESULT)
    assert baseline.status_code == 200

    write_variant(variant)
    before = files(tmp_private_dir)
    runway_result = client.get(RESULT)
    assert runway_result.status_code == 200
    assert runway_result.headers["cache-control"] == "no-store"
    assert runway_result.json() == baseline.json()  # snapshots never feed runway
    with_runway = client.get(LIFESTYLE, params={"month": "2026-10"})
    assert with_runway.status_code == code
    if state:
        assert with_runway.json()["status"] == state
    if variant not in {"corrupt", "absent"}:  # dashboard still serves saved bytes
        for month in MONTHS:
            stored = json.loads(storage.bills_dashboard_path(month).read_text(encoding="utf-8"))
            assert client.get(DASHBOARD, params={"month": month}).json() == stored
    assert files(tmp_private_dir) == before  # neither read path writes

    for name in world.data:
        (tmp_private_dir / name).unlink()
    alone = client.get(LIFESTYLE, params={"month": "2026-10"})
    assert (alone.status_code, alone.json()) == (with_runway.status_code, with_runway.json())
