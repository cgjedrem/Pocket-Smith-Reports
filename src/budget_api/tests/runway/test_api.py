from copy import deepcopy
import json

import pytest

from budget_api.tests.runway.synthetic import A, CARD, MONTHS, pocketsmith_month


RESULT = "/api/bills/runway"
SETTINGS = "/api/settings/runway"


@pytest.mark.parametrize("defect", ["identity_conflict", "list_title", "object_title"])
def test_invalid_transaction_evidence_is_explicit_on_result_route(runway_client, world, defect):
    july = world.data["2026-07_ps_raw.json"]["transactions"][0]
    if defect == "identity_conflict":
        world.data["2026-08_ps_raw.json"]["transactions"][0]["id"] = july["id"]
    else:
        july["category"] = {
            "id": 2100099,
            "title": ["cc payment"] if defect == "list_title" else {"text": "cc payment"},
        }
    world.write()
    response = runway_client.get(RESULT)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    assert result["observations"][0]["coverage"] == "invalid"
    assert result["included_month_count"] == (1 if defect == "identity_conflict" else 2)
    assert result["owners"][0]["runway_display"] == (None if defect == "identity_conflict" else "2.6")


@pytest.mark.parametrize("cross_month", [False, True])
@pytest.mark.parametrize("malformed_first", [False, True])
def test_fingerprint_amount_array_conflict_on_result_route(runway_client, world, cross_month, malformed_first):
    july = world.data["2026-07_ps_raw.json"]["transactions"]
    july[0]["amount"] = -100.0
    copy = deepcopy(july[0])
    copy["amount"] = ["decimal", "-100.0"]
    if cross_month:
        if malformed_first:
            july[0]["amount"], copy["amount"] = copy["amount"], july[0]["amount"]
        world.data["2026-08_ps_raw.json"]["transactions"].append(copy)
    elif malformed_first:
        july.insert(0, copy)
    else:
        july.append(copy)
    world.write()
    before = {p.name: p.read_bytes() for p in world.root.iterdir()}
    response = runway_client.get(RESULT)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    assert result["included_months"] == (MONTHS[2:] if cross_month else MONTHS[1:])
    for row in result["observations"][:2 if cross_month else 1]:
        assert (row["status"], row["coverage"]) == ("excluded", "invalid")
        assert row["household_spending"] is None
        assert all(owner["spending"] is None for owner in row["owners"])
        assert "invalid_source" in {issue["code"] for issue in row["issues"]}
    assert result["household"]["runway_months"] == (None if cross_month else 1.2)
    assert before == {p.name: p.read_bytes() for p in world.root.iterdir()}


def test_pocketsmith_shaped_months_with_null_transfer_flags_on_result_route(runway_client, world):
    for index, month in enumerate(MONTHS):
        world.data[f"{month}_ps_raw.json"] = pocketsmith_month(month, index)  # bare list. null/true/false flags
    world.write()
    response = runway_client.get(RESULT)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    assert result["included_months"] == MONTHS
    assert [row["coverage"] for row in result["observations"]] == ["unverified"] * 3
    assert "invalid_source" not in {issue["code"] for row in result["observations"] for issue in row["issues"]}
    assert "invalid_source" not in {issue["code"] for issue in result["issues"]}
    assert [owner["runway_display"] for owner in result["owners"]] == ["172.6", "164.8"]
    assert result["household"]["runway_display"] == "170.6"
    assert result["household"]["status"] == "qualified"


def assert_error(response, status):
    assert response.status_code == status
    assert response.headers["cache-control"] == "no-store"
    assert set(response.json()) == {"detail"}


def test_absent_and_empty_settings_never_default_select(runway_client, world):
    world.remove("runway_config.json")
    for path in [SETTINGS, RESULT]:
        response = runway_client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["selection_status"] == "unconfigured"
    assert not (world.root / "runway_config.json").exists()
    response = runway_client.put(SETTINGS, json={"liquid_account_ids": []})
    assert response.status_code == 200
    assert response.json()["selection_status"] == "empty"
    assert runway_client.get(RESULT).json()["household"]["reserves"] is None


def test_save_atomic_only_config_no_balances_in_picker(runway_client, world):
    before = {p.name: p.read_bytes() for p in world.root.iterdir() if p.name != "runway_config.json"}
    response = runway_client.put(SETTINGS, json={"liquid_account_ids": [A]})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["liquid_account_ids"] == [A]
    assert all("balance" not in option for option in response.json()["accounts"])
    assert json.loads((world.root / "runway_config.json").read_text()) == {"schema_version": 1, "liquid_account_ids": [A]}
    assert before == {p.name: p.read_bytes() for p in world.root.iterdir() if p.name != "runway_config.json"}
    assert runway_client.get(RESULT).json()["household"]["reserves"] == 90000


@pytest.mark.parametrize("body", [
    {}, {"liquid_account_ids": None}, {"liquid_account_ids": A},
    {"liquid_account_ids": [A, A]}, {"liquid_account_ids": [int(A)]},
    {"liquid_account_ids": [True]}, {"liquid_account_ids": [" " + A]},
    {"liquid_account_ids": ["0"]}, {"liquid_account_ids": ["../bad"]},
    {"liquid_account_ids": ["1199999"]}, {"liquid_account_ids": [CARD]},
    {"liquid_account_ids": [A], "schema_version": 1},
    {"liquid_account_ids": [A], "balance": 123456.78},
])
def test_invalid_put_preserves_previous_bytes(runway_client, world, body):
    path = world.root / "runway_config.json"
    before = path.read_bytes()
    response = runway_client.put(SETTINGS, json=body)
    assert_error(response, 400)
    assert "123456.78" not in response.text
    assert path.read_bytes() == before


@pytest.mark.parametrize("method,path", [("get", RESULT), ("get", SETTINGS), ("put", SETTINGS)])
def test_unsupported_query_rejected(runway_client, method, path):
    kwargs = {"json": {"liquid_account_ids": []}} if method == "put" else {}
    assert_error(getattr(runway_client, method)(path + "?month=2020-01", **kwargs), 400)


@pytest.mark.parametrize("raw", ['{bad', '{"schema_version":99,"liquid_account_ids":[]}', 'null', '{"schema_version":true,"liquid_account_ids":[]}'])
def test_corrupt_config_is_not_empty(runway_client, world, raw):
    (world.root / "runway_config.json").write_text(raw, encoding="utf-8")
    assert_error(runway_client.get(SETTINGS), 500)
    result = runway_client.get(RESULT)
    assert result.status_code == 200
    assert result.json()["selection_status"] == "invalid_settings"
    assert result.json()["selected_account_ids"] is None
    assert result.json()["household"]["runway_months"] is None


@pytest.mark.parametrize("change", [{"excluded": True}, {"partner_id": None}, {"type": "cc"}, {"type": "investment"}])
def test_selection_drift_retained_and_put_rejected(runway_client, world, change):
    world.data["account_mappings.json"]["accounts"][A].update(change)
    world.write()
    assert_error(runway_client.put(SETTINGS, json={"liquid_account_ids": [A]}), 400)
    result = runway_client.get(RESULT).json()
    assert result["selection_status"] == "invalid"
    assert result["selected_accounts"][0]["id"] == A
    assert result["household"]["reserves"] is None


def test_missing_selected_balance_blocks_household_not_other_owner(runway_client, world):
    world.data["account_catalog.json"]["accounts"][0].pop("current_balance")
    world.write()
    result = runway_client.get(RESULT).json()
    assert result["selected_accounts"][0]["balance"] is None
    assert result["household"]["reserves"] is None
    assert result["owners"][1]["runway_months"] == 0.5


def test_atomic_failure_safe_error_and_prior_file(runway_client, world, monkeypatch):
    from budget_api.services import storage
    before = (world.root / "runway_config.json").read_bytes()

    def fail(*args):
        raise OSError("Synthetic sensitive error 123456.78")

    monkeypatch.setattr(storage, "atomic_write_json", fail)
    response = runway_client.put(SETTINGS, json={"liquid_account_ids": [A]})
    assert_error(response, 500)
    assert "123456.78" not in response.text
    assert (world.root / "runway_config.json").read_bytes() == before


def test_running_sync_conflict_and_result_unavailable(runway_client, world):
    (world.root / ".sync_status.json").write_text('{"status":"running"}')
    assert_error(runway_client.get(SETTINGS), 409)
    assert_error(runway_client.put(SETTINGS, json={"liquid_account_ids": []}), 409)
    result = runway_client.get(RESULT)
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    assert result.json()["household"]["runway_months"] is None
    assert "sources_changing" in {i["code"] for i in result.json()["issues"]}


def test_corrupt_raw_and_invalid_classification_fail_closed(runway_client, world):
    (world.root / "2026-07_ps_raw.json").write_text('{"transactions": [')
    result = runway_client.get(RESULT).json()
    assert result["included_months"] == ["2026-08", "2026-09"]
    (world.root / "category_roles.json").write_text('[]')
    assert runway_client.get(RESULT).json()["included_months"] == []


def test_legacy_bills_untouched_missing_current_snapshot_independent(runway_client, world):
    legacy = {"schema_version": 5, "month": "2026-07", "partners": [], "synthetic_observed": -15}
    path = world.root / "bills_dashboard_2026-07.json"
    path.write_text(json.dumps(legacy))
    before = path.read_bytes()
    assert runway_client.get("/api/bills/dashboard?month=2026-07").json() == legacy
    assert runway_client.get("/api/bills/dashboard?month=2026-10").status_code == 404
    assert runway_client.get(RESULT).json()["household"]["runway_months"] is not None
    assert path.read_bytes() == before


def test_result_and_issues_do_not_leak_payees_or_unselected_money(runway_client, world):
    world.data["account_catalog.json"]["accounts"][3]["current_balance"] = 7654321.98
    world.write()
    response = runway_client.get(RESULT)
    assert "7654321.98" not in response.text
    assert "Synthetic purchase" not in response.text
    for issue in response.json()["issues"]:
        assert set(issue) == {"code", "severity", "month", "account_id", "partner_id"}


def test_unexpected_service_error_no_store_safe(runway_client, monkeypatch):
    from budget_api.services import runway

    def fail():
        raise RuntimeError("Synthetic private details 123456.78")

    monkeypatch.setattr(runway, "calculate_runway", fail)
    response = runway_client.get(RESULT)
    assert_error(response, 500)
    assert "123456.78" not in response.text


@pytest.mark.parametrize("path", [RESULT, SETTINGS])
def test_get_body_rejected(runway_client, path):
    assert_error(runway_client.request("GET", path, json={"month": "2026-01"}), 400)


def test_duplicate_json_keys_rejected_not_silently_repaired(runway_client, world):
    response = runway_client.put(
        SETTINGS, content='{"liquid_account_ids":["1100001"],"liquid_account_ids":[]}',
        headers={"content-type": "application/json"},
    )
    assert_error(response, 400)


def test_save_changed_source_preserves_config(runway_client, world, monkeypatch):
    from budget_api.services import runway
    before = (world.root / "runway_config.json").read_bytes()
    monkeypatch.setattr(runway, "_stable", lambda bundle: False)
    assert_error(runway_client.put(SETTINGS, json={"liquid_account_ids": [A]}), 409)
    assert (world.root / "runway_config.json").read_bytes() == before


def test_atomic_replace_failure_leaves_previous_file(runway_client, world, monkeypatch):
    from pathlib import Path
    original = Path.replace
    before = (world.root / "runway_config.json").read_bytes()

    def fail(source, target):
        if target.name == "runway_config.json":
            raise OSError("Synthetic replace failure")
        return original(source, target)

    monkeypatch.setattr(Path, "replace", fail)
    assert_error(runway_client.put(SETTINGS, json={"liquid_account_ids": [A]}), 500)
    assert (world.root / "runway_config.json").read_bytes() == before


def test_duplicate_persisted_key_invalid_settings(runway_client, world):
    (world.root / "runway_config.json").write_text(
        '{"schema_version":1,"liquid_account_ids":["1100001"],"liquid_account_ids":[]}'
    )
    assert_error(runway_client.get(SETTINGS), 500)


def test_extra_field_name_not_echoed_as_financial_error(runway_client):
    response = runway_client.put(SETTINGS, json={"liquid_account_ids": [], "123456.78": 1})
    assert_error(response, 400)
    assert "123456.78" not in response.text
