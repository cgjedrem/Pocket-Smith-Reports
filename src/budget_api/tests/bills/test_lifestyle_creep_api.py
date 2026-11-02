"""Bounded in-process GET tests over synthetic snapshots."""

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from budget_api.services import lifestyle_creep as service, storage
from budget_api.tests.bills.test_cc_spend_history import complete

URL = "/api/bills/lifestyle-creep"
ERROR = {"detail": "internal error reading lifestyle creep history"}
REFERENCE_MONTHS = ["2026-07", "2026-08", "2026-09"]
TARGET_MONTH = "2026-10"
WINDOW = REFERENCE_MONTHS + [TARGET_MONTH]


def row(pid="partner_a", amount="0", **changes):
    history = complete(categories={"910001": {"title": "Category A", "amount": amount}})
    return dict(partner_id=pid, partner_slot="a", partner="Partner A",
                cc_spend_history=history) | changes


def save(month, partners=None):
    storage.atomic_write_json(storage.bills_dashboard_path(month), dict(
        schema_version=6, month=month,
        partners=[row()] if partners is None else partners,
    ))


@pytest.fixture
def snapshots(tmp_private_dir, monkeypatch):
    class Clock(date):
        @classmethod
        def today(cls):
            return cls(2027, 1, 10)
    monkeypatch.setattr(service, "date", Clock, raising=False)
    payloads = {month: dict(schema_version=6, month=month, partners=[row()])
                for month in WINDOW}
    for month, data in payloads.items():
        storage.atomic_write_json(storage.bills_dashboard_path(month), data)
    return payloads


def test_default_compares_one_completed_target_to_prior_three_month_mean(client, snapshots):
    response = client.get(URL, params={"month": TARGET_MONTH, "unknown": "ignored"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["month"] == TARGET_MONTH
    assert data["reference_start"] == REFERENCE_MONTHS[0]
    assert data["reference_end"] == REFERENCE_MONTHS[-1]
    assert data["window_months"] == WINDOW
    assert data["evaluation_months"] == [TARGET_MONTH]
    assert data["baseline_months"] == 3
    assert data["threshold_percent"] == "20"
    assert data["status"] == "ready"
    category = data["partners"][0]["categories"][0]
    assert category["comparison"]["month"] == TARGET_MONTH
    assert category["comparison"]["baseline_months"] == REFERENCE_MONTHS


@pytest.mark.parametrize("query", [
    "", "?month=", "?month=2026-1", "?month=0000-12", "?month=2026-13",
    "?month=2027-02", "?month=２０２６-10", "?month=../bad",
    "?month=2026-10&month=2026-10",
    "?month=2026-10&threshold_percent=20&threshold_percent=20",
    *[f"?month=2026-10&threshold_percent={value}" for value in
      ["", " ", "true", "false", "null", "NaN", "Infinity", "-Infinity",
       "0", "0.99999999999999999999", "100.00000000000000001", "101", "1_0", "2,0"]],
])
def test_invalid_selection_before_paths(client, snapshots, monkeypatch, query):
    def forbidden(*args):
        pytest.fail("invalid selection resolved storage path")
    monkeypatch.setattr(storage, "bills_dashboard_path", forbidden)
    response = client.get(URL + query)
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert isinstance(response.json()["detail"], str)


@pytest.mark.parametrize("threshold,canonical", [
    ("1", "1"), ("20.5", "20.5"), ("30", "30"), ("100", "100"),
    ("020.50", "20.5"), ("2e1", "20"), ("+2E+1", "20"), ("1.", "1"),
    (".1e2", "10"), ("99.99999999999999999999", "99.99999999999999999999"),
])
def test_threshold_grammar_exact_canonical_echo(client, snapshots, threshold, canonical):
    response = client.get(URL, params={"month": TARGET_MONTH, "threshold_percent": threshold})
    assert response.status_code == 200
    assert response.json()["threshold_percent"] == canonical


def test_reference_average_threshold_and_mom_contract(client, snapshots):
    for month, amount in zip(REFERENCE_MONTHS + [TARGET_MONTH], ["100", "200", "300", "240"]):
        snapshots[month]["partners"][0]["cc_spend_history"]["categories"]["910001"]["amount"] = amount
        storage.atomic_write_json(storage.bills_dashboard_path(month), snapshots[month])
    data = client.get(URL, params={"month": TARGET_MONTH}).json()
    category = data["partners"][0]["categories"][0]
    assert category["comparison"] == {
        "month": TARGET_MONTH,
        "baseline_months": REFERENCE_MONTHS,
        "baseline_amount": "200",
        "spending_amount": "240",
        "change_amount": "40",
        "growth_percent": "20",
    }
    assert category["is_above_threshold"] is False
    assert category["latest_month_over_month_percent"] == "-20"
    data = client.get(URL, params={"month": TARGET_MONTH, "threshold_percent": "19.9"}).json()
    assert data["partners"][0]["categories"][0]["is_above_threshold"] is True


@pytest.mark.parametrize("mutation,code,reason", [
    ("missing", "missing_snapshot", None), ("legacy", "legacy_history", None),
    ("partial", "partial_month", "open_month"),
    ("unavailable", "unavailable_history", "no_cc_accounts"),
    ("missing_partner", "missing_partner", None),
])
def test_readiness_gaps_not_zero(client, snapshots, mutation, code, reason):
    month = REFERENCE_MONTHS[1]
    path = storage.bills_dashboard_path(month)
    if mutation == "missing":
        path.unlink()
    else:
        value = snapshots[month]
        if mutation == "legacy":
            value["schema_version"] = 5
            del value["partners"][0]["cc_spend_history"]
        elif mutation == "missing_partner":
            value["partners"] = []
        else:
            value["partners"][0]["cc_spend_history"] = complete(
                status=mutation, reason=reason, categories=None, uncategorized_amount=None,
                scope_key=complete()["scope_key"] if mutation == "partial" else None,
            )
        storage.atomic_write_json(path, value)
    data = client.get(URL, params={"month": TARGET_MONTH}).json()
    assert data["status"] == "insufficient_history"
    assert data["partners"][0]["categories"] == []
    assert data["partners"][0]["uncategorized_samples"] == []
    assert data["issues"] == [dict(
        month=month, partner_id=None if mutation == "missing" else "partner_a",
        code=code, reason=reason,
    )]


def test_missing_target_snapshot_blocks_category_conclusion(client, snapshots):
    storage.bills_dashboard_path(TARGET_MONTH).unlink()
    data = client.get(URL, params={"month": TARGET_MONTH}).json()
    assert data["status"] == "insufficient_history"
    assert data["partners"][0]["categories"] == []
    assert data["partners"][0]["uncategorized_samples"] == []
    assert data["issues"] == [dict(
        month=TARGET_MONTH, partner_id=None, code="missing_snapshot", reason=None,
    )]


def test_scope_mismatch_blocks_partner_for_all_window_months(client, snapshots):
    month = REFERENCE_MONTHS[0]
    snapshots[month]["partners"][0]["cc_spend_history"]["scope_key"] = "cc-spend-v1:" + "b" * 64
    storage.atomic_write_json(storage.bills_dashboard_path(month), snapshots[month])
    data = client.get(URL, params={"month": TARGET_MONTH}).json()
    assert data["status"] == "insufficient_history"
    assert [issue["month"] for issue in data["issues"]] == WINDOW
    assert {issue["code"] for issue in data["issues"]} == {"scope_changed"}


@pytest.mark.parametrize("raw", [
    "null", "[]", "{", '{"schema_version":6,"schema_version":6}', '{"bad":NaN}',
    '{"bad":Infinity}', '{"month":"2026-08","partners":{}}',
])
def test_corrupt_json_never_partial_success(client, snapshots, raw):
    storage.bills_dashboard_path(REFERENCE_MONTHS[1]).write_text(raw, encoding="utf-8")
    response = client.get(URL, params={"month": TARGET_MONTH})
    assert response.status_code == 500
    assert response.json() == ERROR
    assert response.headers["cache-control"] == "no-store"


def test_error_then_retry_after_repair(client, snapshots):
    path = storage.bills_dashboard_path(REFERENCE_MONTHS[1])
    path.write_bytes(b"\xff")
    assert client.get(URL, params={"month": TARGET_MONTH}).status_code == 500
    storage.atomic_write_json(path, snapshots[REFERENCE_MONTHS[1]])
    assert client.get(URL, params={"month": TARGET_MONTH}).json()["status"] == "ready"


@pytest.mark.parametrize("reason", [
    "future_month", "no_cc_accounts", "missing_source_context", "invalid_source",
])
def test_unavailable_reason_is_preserved(client, snapshots, reason):
    month = REFERENCE_MONTHS[0]
    value = snapshots[month]
    value["partners"][0]["cc_spend_history"] = complete(
        status="unavailable", reason=reason, scope_key=None,
        categories=None, uncategorized_amount=None,
    )
    storage.atomic_write_json(storage.bills_dashboard_path(month), value)
    assert client.get(URL, params={"month": TARGET_MONTH}).json()["issues"][0]["reason"] == reason


def test_exact_bounded_reads_do_not_read_adjacent_month(client, snapshots, monkeypatch):
    reads = []
    original = Path.read_text

    def read(path, *args, **kwargs):
        assert path.parent == storage.PRIVATE_DATA_DIR
        assert path.name in {f"bills_dashboard_{month}.json" for month in WINDOW}
        reads.append(path.name)
        return original(path, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("unbounded detector side effect")
    monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setattr(Path, "glob", forbidden)
    monkeypatch.setattr(Path, "rglob", forbidden)
    monkeypatch.setattr(storage, "read_json", forbidden)
    monkeypatch.setattr(storage, "atomic_write_json", forbidden)
    from budget_api.services import sync_runner, ps_client
    monkeypatch.setattr(sync_runner, "sync_all", forbidden)
    monkeypatch.setattr(ps_client, "PSClient", forbidden)
    assert client.get(URL, params={"month": TARGET_MONTH}).status_code == 200
    assert reads == [f"bills_dashboard_{month}.json" for month in WINDOW]


def test_explicit_two_and_24_month_reference_ranges_read_exact_files(client, snapshots, monkeypatch):
    months = [f"{2024 + i // 12:04d}-{i % 12 + 1:02d}" for i in range(24)]
    target = "2026-01"
    for month in months + [target]:
        save(month, [row(amount="100")])
    original = Path.read_text
    for count in (2, 24):
        selected = months[:count]
        reads = []

        def read(path, *args, **kwargs):
            reads.append(path.name)
            return original(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read)
        response = client.get(URL, params={
            "month": target,
            "reference_start": selected[0],
            "reference_end": selected[-1],
        })
        assert response.status_code == 200
        data = response.json()
        assert data["window_months"] == selected + [target]
        assert data["baseline_months"] == count
        assert data["evaluation_months"] == [target]
        assert reads == [f"bills_dashboard_{month}.json" for month in selected + [target]]
        assert data["partners"][0]["categories"][0]["comparison"]["baseline_months"] == selected


def test_nonadjacent_reference_end_disables_mom_without_extra_month_read(
    client, snapshots, monkeypatch,
):
    target = "2026-10"
    save("2026-06")
    reads = []
    original = Path.read_text

    def read(path, *args, **kwargs):
        reads.append(path.name)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    data = client.get(URL, params={
        "month": target, "reference_start": "2026-06", "reference_end": "2026-08",
    }).json()
    assert data["status"] == "ready"
    assert data["window_months"] == ["2026-06", "2026-07", "2026-08", target]
    assert data["partners"][0]["categories"][0]["latest_month_over_month_percent"] is None
    assert reads == [
        "bills_dashboard_2026-06.json", "bills_dashboard_2026-07.json",
        "bills_dashboard_2026-08.json", "bills_dashboard_2026-10.json",
    ]


@pytest.mark.parametrize("query", [
    "month=2026-10&reference_start=2026-08",
    "month=2026-10&reference_end=2026-09",
    "month=2026-10&reference_start=&reference_end=",
    "month=2026-10&reference_start=2026-09&reference_end=2026-08",
    "month=2026-10&reference_start=2026-07&reference_end=2026-10",
    "month=2026-10&reference_start=2026-07&reference_end=2026-11",
    "month=2026-10&reference_start=2024-09&reference_end=2026-09",
    "month=2026-10&reference_start=2026-08&reference_end=2026-09&reference_start=2026-08",
    "month=2026-10&reference_start=2026-08&reference_end=2026-09&reference_end=2026-09",
    "month=2026-10&month=2026-10&reference_start=2026-08&reference_end=2026-09",
    "month=2026-10&reference_start=2026-08&reference_end=2026-09&threshold_percent=20&threshold_percent=20",
    "month=2026-10&reference_start=2026-08&reference_end=2026-09&threshold_percent=NaN",
    "month=2027-02&reference_start=2026-10&reference_end=2026-12",
    "month=2027-01&reference_start=2026-12&reference_end=2027-01",
    "month=2027-01&threshold_percent=NaN",
    "month=0001-02&reference_start=0001-01&reference_end=0001-01",
    "month=2026-10&reference_start=2026-07&reference_end=2026-07",
    *[f"month=2026-10&reference_start={start}&reference_end=2026-09"
      for start in ["2026-1", "0000-12", "2026-00", "2026-13", "２０２６-08", "../bad"]],
])
def test_invalid_reference_selection_before_path(client, snapshots, monkeypatch, query):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid selection resolved storage")
    monkeypatch.setattr(storage, "bills_dashboard_path", forbidden)
    response = client.get(URL + "?" + query)
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert isinstance(response.json()["detail"], str)


def test_earliest_target_has_two_representable_reference_months(client, snapshots, monkeypatch):
    reads = []
    original = storage.bills_dashboard_path

    def resolve(month):
        reads.append(month)
        return original(month)
    monkeypatch.setattr(storage, "bills_dashboard_path", resolve)
    response = client.get(URL, params={
        "month": "0001-03", "reference_start": "0001-01", "reference_end": "0001-02",
    })
    assert response.status_code == 200
    assert reads == ["0001-01", "0001-02", "0001-03"]
    assert response.json()["window_months"] == reads


@pytest.mark.parametrize("target", ["2026-10", "2026-12"])
@pytest.mark.parametrize("explicit_reference", [False, True])
@pytest.mark.parametrize("saved_status", ["complete", "partial", "unavailable", "missing"])
def test_browser_ahead_target_is_insufficient_without_any_history_read(
    client, snapshots, monkeypatch, target, explicit_reference, saved_status,
):
    class Clock(date):
        @classmethod
        def today(cls):
            return cls.fromisoformat(target + "-01")

    monkeypatch.setattr(service, "date", Clock)
    if saved_status == "missing":
        storage.bills_dashboard_path(target).unlink(missing_ok=True)
    else:
        history = (complete() if saved_status == "complete" else complete(
            status=saved_status,
            reason="open_month" if saved_status == "partial" else "invalid_source",
            scope_key=complete()["scope_key"] if saved_status == "partial" else None,
            categories=None, uncategorized_amount=None,
        ))
        save(target, [row(cc_spend_history=history)])

    def forbidden(*args, **kwargs):
        pytest.fail("open month request touched history")

    monkeypatch.setattr(storage, "bills_dashboard_path", forbidden)
    monkeypatch.setattr(service, "_read_month", forbidden)
    monkeypatch.setattr(service, "evaluate_partner", forbidden)
    query = {"month": target, "threshold_percent": "20.5"}
    if explicit_reference:
        query |= {"reference_start": "2026-07", "reference_end": "2026-09"}
    response = client.get(URL, params=query)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    references = (REFERENCE_MONTHS if explicit_reference or target == "2026-10"
                  else ["2026-09", "2026-10", "2026-11"])
    assert data["month"] == target
    assert data["evaluation_months"] == [target]
    assert data["window_months"] == references + [target]
    assert data["reference_start"] == references[0]
    assert data["reference_end"] == references[-1]
    assert data["baseline_months"] == 3
    assert data["threshold_percent"] == "20.5"
    assert data["status"] == "insufficient_history"
    assert data["partners"] == []
    assert data["issues"] == [dict(
        month=target, partner_id=None, code="partial_month", reason="open_month",
    )]


def test_closed_target_rechecks_api_clock_before_reading_history(snapshots, monkeypatch):
    selection = service.validate_selection(TARGET_MONTH)

    class Clock(date):
        @classmethod
        def today(cls):
            return cls(2026, 9, 30)

    def forbidden(*args, **kwargs):
        pytest.fail("clock rollback exposed open or future history")

    monkeypatch.setattr(service, "date", Clock)
    monkeypatch.setattr(service, "_read_month", forbidden)
    data = service.read_lifestyle_creep(selection).model_dump(mode="json")
    assert data["status"] == "insufficient_history"
    assert data["partners"] == []
    assert data["issues"] == [
        dict(month="2026-09", partner_id=None, code="partial_month", reason="open_month"),
        dict(month=TARGET_MONTH, partner_id=None, code="unavailable_history", reason="future_month"),
    ]


@pytest.mark.parametrize("saved_status", ["complete", "partial"])
def test_retry_after_api_month_closes_still_requires_complete_saved_evidence(
    client, snapshots, monkeypatch, saved_status,
):
    class Clock(date):
        current = date(2026, 10, 31)

        @classmethod
        def today(cls):
            return cls.current

    monkeypatch.setattr(service, "date", Clock)
    if saved_status == "partial":
        save(TARGET_MONTH, [row(cc_spend_history=complete(
            status="partial", reason="open_month",
            categories=None, uncategorized_amount=None,
        ))])
    before = client.get(URL, params={"month": TARGET_MONTH}).json()
    assert before["status"] == "insufficient_history"
    assert before["partners"] == []
    Clock.current = date(2026, 11, 1)
    response = client.get(URL, params={"month": TARGET_MONTH})
    assert response.status_code == 200
    after = response.json()
    if saved_status == "complete":
        assert after["status"] == "ready"
        assert after["partners"][0]["categories"]
    else:
        assert after["status"] == "insufficient_history"
        assert after["partners"][0]["categories"] == []
        assert after["partners"][0]["uncategorized_samples"] == []
        assert after["issues"] == [dict(
            month=TARGET_MONTH, partner_id="partner_a", code="partial_month", reason="open_month",
        )]


def test_finite_read_error_is_generic_and_no_store(client, snapshots, monkeypatch):
    def fail(*args, **kwargs):
        raise PermissionError("synthetic private path")
    monkeypatch.setattr(Path, "read_text", fail)
    response = client.get(URL, params={"month": TARGET_MONTH})
    assert response.status_code == 500
    assert response.json() == ERROR
    assert response.headers["cache-control"] == "no-store"
