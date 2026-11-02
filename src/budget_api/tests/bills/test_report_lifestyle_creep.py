"""Report-mode GETs use synthetic persisted observations, never report/config I/O."""

from copy import deepcopy
from pathlib import Path

import pytest

from budget_api.services import lifestyle_creep, storage
from budget_api.tests.bills.test_economy_history import build, economy_source
from budget_api.tests.bills.test_lifestyle_creep_api import URL, WINDOW, TARGET_MONTH, snapshots


@pytest.fixture
def report_snapshots(snapshots):
    value, context = economy_source()
    history = build(value, context).model_dump()
    for month, record in snapshots.items():
        record["schema_version"] = 7
        record["economy_spend_history"] = deepcopy(history)
        for i, group in enumerate(record["economy_spend_history"]["groups"]):
            group["categories"] = {str(910001 + i): {"title": "Same title", "amount": "100"}}
        storage.atomic_write_json(storage.bills_dashboard_path(month), record)
    return snapshots


def save(records):
    for month, record in records.items():
        storage.atomic_write_json(storage.bills_dashboard_path(month), record)


def get(client, **params):
    return client.get(URL, params={"month": TARGET_MONTH, "grouping": "report"} | params)


def test_fixed_three_groups_and_default_cc_mode_unchanged(client, report_snapshots):
    response = get(client)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["grouping"] == "report" and "partners" not in data
    assert data["window_months"] == WINDOW and data["status"] == "ready"
    assert [g["group_id"] for g in data["groups"]] == ["shared", "personal_partner_a", "personal_partner_b"]
    assert [g["partner_id"] for g in data["groups"]] == [None, "partner_a", "partner_b"]
    assert len({g["categories"][0]["category_id"] for g in data["groups"]}) == 3
    old = client.get(URL, params={"month": TARGET_MONTH}).json()
    assert old["status"] == "ready" and "partners" in old and "groups" not in old
    assert old["partners"][0]["categories"][0]["samples"][0]["amount"] == "0"


@pytest.mark.parametrize("reference,target,threshold,reason,above,growth", [
    (["100", "100", "100"], "120", "20", None, False, "20"),
    (["100", "100", "100"], "120.00000000000000000000000001", "20", None, True, None),
    (["100", "100", "100"], "-20", "20", None, False, "-120"),
    (["-10", "-10", "-10"], "-20", "20", "negative_baseline", False, None),
    (["-10", "0", "10"], "30", "20", "zero_baseline", False, None),
    (["0", "0", "10"], "30", "20", "low_frequency", False, "800"),
    (["0.1", "0.2", "0.3"], "0.24", "20", None, False, "20"),
])
def test_signed_exact_math_and_explicit_nonpositive_suppression(
    client, report_snapshots, reference, target, threshold, reason, above, growth,
):
    for month, amount in zip(WINDOW, reference + [target]):
        group = report_snapshots[month]["economy_spend_history"]["groups"][0]
        group["categories"]["910001"]["amount"] = amount
        group["uncategorized_amount"] = "-1"
    save(report_snapshots)
    result = get(client, threshold_percent=threshold)
    assert result.status_code == 200
    category = result.json()["groups"][0]["categories"][0]
    assert category["is_above_threshold"] is above
    assert category["suppression_reason"] == reason
    assert category["comparison"]["spending_amount"] == target
    if growth is not None or reason in {"negative_baseline", "zero_baseline"}:
        assert category["comparison"]["growth_percent"] == growth
    assert result.json()["groups"][0]["uncategorized_samples"][0]["amount"] == "-1"


@pytest.mark.parametrize("version", [1, 5, 6, 7])
def test_absent_report_evidence_insufficient_for_all_three_no_cc_fallback(client, report_snapshots, version):
    for record in report_snapshots.values():
        record["schema_version"] = version
        del record["economy_spend_history"]
        if version < 6:
            for partner in record["partners"]:
                partner.pop("cc_spend_history")
    save(report_snapshots)
    response = get(client)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "insufficient_history"
    assert len(data["groups"]) == 3
    assert all(g["status"] == "insufficient_history" and g["categories"] == []
               and g["uncategorized_samples"] == [] for g in data["groups"])
    assert {i["code"] for i in data["issues"]} == {"legacy_history"}


def test_scope_and_identity_change_block_entire_file_window(client, report_snapshots):
    report_snapshots[WINDOW[0]]["economy_spend_history"]["scope_key"] = "economy-spend-v1:" + "f" * 64
    save(report_snapshots)
    assert {i["code"] for i in get(client).json()["issues"]} == {"scope_changed"}
    for record in report_snapshots.values():
        record["economy_spend_history"]["scope_key"] = "economy-spend-v1:" + "a" * 64
    report_snapshots[WINDOW[0]]["economy_spend_history"]["groups"][1]["partner_id"] = "other"
    save(report_snapshots)
    data = get(client).json()
    assert data["status"] == "insufficient_history"
    assert {i["code"] for i in data["issues"]} == {"scope_changed"}
    assert all(not g["categories"] for g in data["groups"])


@pytest.mark.parametrize("change", [
    lambda r: r.update(schema_version=8),
    lambda r: r.update(schema_version=6),
    lambda r: r["economy_spend_history"]["groups"].pop(),
    lambda r: r["economy_spend_history"]["groups"][0]["categories"]["910001"].update(amount="-0"),
    lambda r: r["economy_spend_history"]["groups"][1].update(partner_id="partner_b"),
    lambda r: r["economy_spend_history"]["groups"][1].update(
        categories={"910001": {"title": "Duplicate", "amount": "1"}}),
])
def test_corrupt_evidence_generic_error_no_partial_verdict(client, report_snapshots, change):
    change(report_snapshots[WINDOW[0]])
    save(report_snapshots)
    response = get(client)
    assert response.status_code == 500
    assert response.json() == {"detail": "internal error reading lifestyle creep history"}
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("query", [
    "?month=2026-10&grouping=unknown",
    "?month=2026-10&grouping=report&grouping=report",
    "?month=2026-10&grouping=report&reference_start=2026-09",
    "?month=2026-10&grouping=report&reference_start=2026-09&reference_end=2026-09",
    "?month=2026-10&grouping=report&threshold_percent=0",
    "?month=2027-02&grouping=report",
])
def test_validation_precedes_all_path_resolution(client, report_snapshots, monkeypatch, query):
    monkeypatch.setattr(storage, "bills_dashboard_path", lambda *a: pytest.fail("unexpected path access"))
    response = client.get(URL + query)
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"


def test_api_clock_guard_no_data_reads_and_exact_three_groups(client, report_snapshots, monkeypatch):
    monkeypatch.setattr(storage, "bills_dashboard_path", lambda *a: pytest.fail("open month read"))
    data = get(client, month="2027-01").json()
    assert data["status"] == "insufficient_history"
    assert len(data["groups"]) == 3
    assert data["issues"][0]["reason"] == "open_month"


@pytest.mark.parametrize("count", [2, 24])
def test_exact_bounded_reads_no_config_raw_reports_network_or_writes(
    client, report_snapshots, monkeypatch, count,
):
    selection = lifestyle_creep.validate_selection(
        "2026-10", reference_start="2026-08" if count == 2 else "2024-10",
        reference_end="2026-09",
    )
    template = report_snapshots[TARGET_MONTH]
    for month in selection.window_months:
        record = deepcopy(template) | {"month": month}
        storage.atomic_write_json(storage.bills_dashboard_path(month), record)
    expected = [storage.bills_dashboard_path(m) for m in selection.window_months]
    original = Path.read_text
    reads = []
    def read(path, *args, **kwargs):
        assert path in expected
        reads.append(path)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setattr(storage, "read_json", lambda *a: pytest.fail("config read"))
    monkeypatch.setattr(storage, "atomic_write_json", lambda *a: pytest.fail("write"))
    monkeypatch.setattr(Path, "glob", lambda *a: pytest.fail("scan"))
    monkeypatch.setattr(Path, "iterdir", lambda *a: pytest.fail("scan"))
    response = get(client, reference_start=selection.reference_start, reference_end=selection.reference_end)
    assert response.status_code == 200 and response.json()["status"] == "ready"
    assert reads == expected and len(reads) == count + 1


def test_missing_or_unavailable_month_never_exposes_partial_money(client, report_snapshots):
    storage.bills_dashboard_path(WINDOW[0]).unlink()
    data = get(client).json()
    assert data["status"] == "insufficient_history"
    assert data["issues"][0]["code"] == "missing_snapshot"
    assert all(g["categories"] == [] for g in data["groups"])
    save(report_snapshots)
    report_snapshots[WINDOW[0]]["economy_spend_history"] = dict(
        status="unavailable", reason="missing_source_context", scope_key=None, groups=None,
    )
    save(report_snapshots)
    assert get(client).json()["issues"][0]["reason"] == "missing_source_context"


def test_category_moving_groups_without_scope_change_is_invalid(client, report_snapshots):
    groups = report_snapshots[WINDOW[0]]["economy_spend_history"]["groups"]
    groups[1]["categories"]["910001"] = groups[0]["categories"].pop("910001")
    save(report_snapshots)
    assert get(client).status_code == 500
