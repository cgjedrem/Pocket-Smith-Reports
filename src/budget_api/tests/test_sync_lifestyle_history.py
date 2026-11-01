"""Fake acquisitions and isolated publication. Never use real source/storage."""

from datetime import datetime
import json
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlsplit

import pytest

from budget_api.services import bills_builder, ps_client, storage, sync_runner
from budget_api.services.ps_client import PSClientError
from budget_api.tests.bills.test_cc_spend_history import complete, source, txn
from budget_api.tests.test_ps_client import _fake_response


@pytest.fixture
def fake_sync(tmp_private_dir, monkeypatch):
    value = source()
    storage.atomic_write_json(storage.ACCOUNT_MAPPING_PATH, value["account_mappings"])
    storage.atomic_write_json(storage.CATEGORY_ROLES_PATH, value["category_roles"])
    client = MagicMock()
    client.get_me.return_value = {"id": 1100099}
    client.get_transaction_accounts.return_value = value["account_catalog"]
    client.get_categories.return_value = value["category_catalog"]
    client.get_transactions.return_value = []
    client.get_events.return_value = []
    client.get_budget.return_value = []
    monkeypatch.setattr(sync_runner, "_read_api_key", lambda: "synthetic-key")
    monkeypatch.setattr(sync_runner, "PSClient", MagicMock(return_value=client))
    monkeypatch.setattr(sync_runner, "ensure_prior_month", lambda *args: ([], []))

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 8, 1, tzinfo=tz)

    monkeypatch.setattr(sync_runner, "datetime", Clock)
    return client


def test_successful_empty_closed_fetch_certifies_zero(fake_sync):
    result = sync_runner.sync_all("2026-07", "2026-07")
    assert result.errors == []
    snapshot = storage.read_json(storage.bills_dashboard_path("2026-07"))
    assert snapshot["schema_version"] == 7
    for partner in snapshot["partners"]:
        assert partner["cc_spend_history"]["status"] == "complete"
        assert partner["cc_spend_history"]["categories"] == {}
        assert partner["cc_spend_history"]["uncategorized_amount"] == "0"
    fake_sync.get_transactions.assert_called_once_with("1100099", "2026-07-01", "2026-07-31")


def test_fetch_start_before_close_never_promotes_on_build(fake_sync, monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 7, 31, 23, 59, tzinfo=tz)
    monkeypatch.setattr(sync_runner, "datetime", Clock)
    result = sync_runner.sync_all("2026-07", "2026-07")
    assert result.errors == []
    path = storage.bills_dashboard_path("2026-07")
    assert storage.read_json(path)["partners"][0]["cc_spend_history"]["status"] == "partial"
    monkeypatch.setattr(Clock, "now", classmethod(lambda cls, tz=None: cls(2026, 8, 1, tzinfo=tz)))
    assert sync_runner.sync_all("2026-07", "2026-07").errors == []
    assert storage.read_json(path)["partners"][0]["cc_spend_history"]["status"] == "complete"


@pytest.mark.parametrize("bad", [None, {}, [None], [{"status": "pending"}]])
def test_invalid_supplied_input_never_publishes_complete(fake_sync, bad):
    fake_sync.get_transactions.return_value = bad
    result = sync_runner.sync_all("2026-07", "2026-07")
    snapshot = storage.read_json(storage.bills_dashboard_path("2026-07"))
    assert result.errors or snapshot["partners"][0]["cc_spend_history"]["reason"] == "invalid_source"
    if snapshot:
        assert all(p["cc_spend_history"]["status"] != "complete" for p in snapshot["partners"])


def test_later_transaction_fetch_failure_publishes_no_bills(fake_sync):
    prior = {}
    for month in ["2026-06", "2026-07"]:
        path = storage.bills_dashboard_path(month)
        history = complete(status="partial", reason="open_month", categories=None, uncategorized_amount=None)
        if month == "2026-07":
            history.update(status="unavailable", reason="missing_source_context", scope_key=None)
        storage.atomic_write_json(path, {"schema_version": 6, "month": month, "partners": [
            {"partner_id": "partner_a", "cc_spend_history": history}]})
        prior[month] = path.read_bytes()
    fake_sync.get_transactions.side_effect = [[], PSClientError("synthetic failure")]
    result = sync_runner.sync_all("2026-06", "2026-07")
    assert result.errors
    assert result.row_counts.bills_snapshots == 0
    for month, saved in prior.items():
        assert storage.bills_dashboard_path(month).read_bytes() == saved


def test_prior_month_acquisition_failure_also_prevents_bills_publication(fake_sync, monkeypatch):
    def fail(*args):
        raise PSClientError("synthetic prior transaction failure")
    monkeypatch.setattr(sync_runner, "ensure_prior_month", fail)
    result = sync_runner.sync_all("2026-07", "2026-07")
    assert result.errors
    assert result.row_counts.bills_snapshots == 0
    assert not storage.bills_dashboard_path("2026-07").exists()


@pytest.fixture
def paginated_sync(fake_sync, monkeypatch):
    """Use real pagination; fake only HTTP responses and credentials."""
    monkeypatch.setattr(sync_runner, "PSClient", ps_client.PSClient)
    monkeypatch.setattr(sync_runner, "ensure_prior_month", bills_builder.ensure_prior_month)
    controls = {"capped": None, "pages": 1, "calls": []}
    catalogs = {
        "/me": fake_sync.get_me.return_value,
        "/users/1100099/transaction_accounts": fake_sync.get_transaction_accounts.return_value,
        "/users/1100099/categories": fake_sync.get_categories.return_value,
        "/users/1100099/budget": [],
    }

    def fake_open(request):
        parsed = urlsplit(request.full_url)
        if parsed.path.removeprefix("/v2") in catalogs:
            return _fake_response(json.dumps(catalogs[parsed.path.removeprefix("/v2")]).encode())
        endpoint = parsed.path.rsplit("/", 1)[-1]
        assert endpoint in {"transactions", "events"}
        query = parse_qs(parsed.query)
        month = query["start_date"][0][:7]
        assert (query["start_date"][0], query["end_date"][0]) == sync_runner._month_dates(month)
        page = int(query.get("page", ["1"])[0])
        controls["calls"].append((month, endpoint, page))
        row = txn(-100 * page, date=month + "-12")
        if endpoint == "events":
            row = {
                "id": f"event-{page}", "date": month + "-12", "amount": -10,
                "category": {"id": 910001, "title": "Synthetic bill", "is_transfer": False},
                "transaction_account": {"id": 1100001, "type": "bank"},
            }
        next_page = page < controls["pages"] or (month, endpoint) == controls["capped"]
        link = f'<{request.full_url}&page={page + 1}>; rel="next"' if next_page else ""
        return _fake_response(json.dumps([row]).encode(), {"link": link})

    monkeypatch.setattr(ps_client, "_api_open", fake_open)
    return controls


@pytest.mark.parametrize("month,endpoint", [
    ("2026-07", "transactions"), ("2026-07", "events"),
    ("2026-04", "transactions"), ("2026-04", "events"),
], ids=["transactions", "events", "prior-transactions", "prior-events"])
def test_capped_acquisition_publishes_no_bills(paginated_sync, monkeypatch, month, endpoint):
    monkeypatch.setattr(ps_client, "MAX_PAGINATION_PAGES", 1)
    paginated_sync["capped"] = (month, endpoint)
    prior = {}
    for saved_month, history in [
        ("2026-06", complete(status="partial", reason="open_month",
                            categories=None, uncategorized_amount=None)),
        ("2026-07", complete(status="unavailable", reason="missing_source_context",
                            scope_key=None, categories=None, uncategorized_amount=None)),
    ]:
        path = storage.bills_dashboard_path(saved_month)
        storage.atomic_write_json(path, {
            "schema_version": 6, "month": saved_month,
            "partners": [{"partner_id": "partner_a", "cc_spend_history": history}],
        })
        prior[saved_month] = path.read_bytes()
    result = sync_runner.sync_all("2026-05", "2026-07")
    # All publication assertions run, even when cap wrongly reports success.
    assert (
        result.row_counts.bills_snapshots == 0,
        not storage.bills_dashboard_path("2026-05").exists(),
        all(storage.bills_dashboard_path(m).read_bytes() == saved for m, saved in prior.items()),
    ) == (True, True, True)
    assert len(result.errors) == 1 and "pagination cap" in result.errors[0]
    assert storage.read_sync_status()["status"] == "failed"
    assert (month, endpoint, 1) in paginated_sync["calls"]
    assert all(page == 1 for _, _, page in paginated_sync["calls"])


@pytest.mark.parametrize("page_count", [1, 2])
def test_complete_real_pagination_still_publishes_history(paginated_sync, monkeypatch, page_count):
    monkeypatch.setattr(ps_client, "MAX_PAGINATION_PAGES", page_count)
    paginated_sync["pages"] = page_count
    result = sync_runner.sync_all("2026-07", "2026-07")
    assert result.errors == []
    assert result.row_counts.bills_snapshots == 1
    assert storage.read_sync_status()["status"] == "success"
    snapshot = storage.read_json(storage.bills_dashboard_path("2026-07"))
    histories = {p["partner_id"]: p["cc_spend_history"] for p in snapshot["partners"]}
    assert all(h["status"] == "complete" for h in histories.values())
    assert histories["partner_a"]["categories"]["910001"]["amount"] == str(
        sum(100 * page for page in range(1, page_count + 1))
    )
    assert histories["partner_b"]["categories"] == {}
    assert len(paginated_sync["calls"]) == 4 * page_count


@pytest.mark.parametrize("in_catalog", [True, False], ids=["present", "removed"])
def test_excluded_unassigned_mapping_survives_repeated_sync(fake_sync, in_catalog):
    mappings = storage.read_json(storage.ACCOUNT_MAPPING_PATH)
    mappings["accounts"]["1100099"] = {
        "partner_id": None, "type": None, "excluded": True,
    }
    storage.atomic_write_json(storage.ACCOUNT_MAPPING_PATH, mappings)
    fake_sync.get_transactions.return_value = [txn()]
    if in_catalog:
        fake_sync.get_transaction_accounts.return_value.append({"id": 1100099})
        fake_sync.get_transactions.return_value.append(txn(-999, account=1100099))
    prior_histories = None
    for _ in range(2):
        result = sync_runner.sync_all("2026-07", "2026-07")
        assert result.errors == []
        assert result.row_counts.bills_snapshots == 1
        snapshot = storage.read_json(storage.bills_dashboard_path("2026-07"))
        histories = {p["partner_id"]: p["cc_spend_history"] for p in snapshot["partners"]}
        assert all(h["status"] == "complete" for h in histories.values())
        assert histories["partner_a"]["categories"]["910001"]["amount"] == "100"
        assert histories["partner_b"]["categories"] == {}
        if prior_histories is not None:
            assert histories == prior_histories
        prior_histories = histories
        saved = storage.read_json(storage.ACCOUNT_MAPPING_PATH)["accounts"]["1100099"]
        assert saved["partner_id"] is None and saved["type"] is None and saved["excluded"] is True


def test_synthetic_uncategorized_role_key_survives_sync(fake_sync):
    # Found on real data: stored roles hold a non-ID "uncategorized" key.
    roles = storage.read_json(storage.CATEGORY_ROLES_PATH) | {"uncategorized": "spend"}
    storage.atomic_write_json(storage.CATEGORY_ROLES_PATH, roles)
    fake_sync.get_transactions.return_value = [txn(), txn(-5, None)]
    result = sync_runner.sync_all("2026-07", "2026-07")
    assert result.errors == []
    snapshot = storage.read_json(storage.bills_dashboard_path("2026-07"))
    histories = {p["partner_id"]: p["cc_spend_history"] for p in snapshot["partners"]}
    assert all(h["status"] == "complete" for h in histories.values())
    assert histories["partner_a"]["categories"]["910001"]["amount"] == "100"
    assert histories["partner_a"]["uncategorized_amount"] == "5"
    assert histories["partner_b"]["categories"] == {}


@pytest.mark.parametrize("binding", [
    None, {"partner_id": None, "type": None, "excluded": False},
    {"partner_id": None, "type": "cc", "excluded": False},
    {"partner_id": "partner_a", "type": None, "excluded": False},
], ids=["missing", "unassigned", "missing-owner", "missing-type"])
def test_included_ambiguous_mapping_never_certifies_sync(fake_sync, binding):
    fake_sync.get_transaction_accounts.return_value.append({"id": 1100099})
    if binding is not None:
        mappings = storage.read_json(storage.ACCOUNT_MAPPING_PATH)
        mappings["accounts"]["1100099"] = binding
        storage.atomic_write_json(storage.ACCOUNT_MAPPING_PATH, mappings)
    result = sync_runner.sync_all("2026-07", "2026-07")
    snapshot = storage.read_json(storage.bills_dashboard_path("2026-07"))
    assert result.errors or all(
        p["cc_spend_history"]["reason"] == "invalid_source" for p in snapshot["partners"]
    )
