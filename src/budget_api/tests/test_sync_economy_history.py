"""Use fake acquisitions and real report config loading in isolated storage."""

from datetime import datetime
from decimal import Decimal

import pytest

from budget_api.services import report_builder, storage, sync_runner
from budget_api.tests.test_sync_lifestyle_history import fake_sync
from budget_api.tests.bills.test_cc_spend_history import txn


@pytest.fixture
def report_sync(fake_sync):
    storage.atomic_write_json(storage.PRIVATE_DATA_DIR / "detailed_section_mapping.json", {
        "category_sections": {"910001": "common", "910002": "common",
                              "910003": "excluded", "910004": "cc_payments", "910005": "excluded"},
        "account_roles": {},
    })
    storage.atomic_write_json(storage.CATEGORY_ROLES_PATH, {
        "910001": "spend", "910003": "exclude", "910004": "exclude", "910005": "exclude",
    })
    return fake_sync


def test_sync_acquires_once_and_persists_exact_report_population(report_sync):
    transactions = [txn(-10.1), txn(-0.2), txn(2.3), txn(-99, 910004), txn(99, 910004)]
    report_sync.get_transactions.return_value = transactions
    result = sync_runner.sync_all("2026-07", "2026-07")
    assert result.errors == []
    snapshot = storage.read_json(storage.bills_dashboard_path("2026-07"))
    assert snapshot["schema_version"] == 7
    history = snapshot["economy_spend_history"]
    assert history["status"] == "complete"
    assert history["groups"][0]["categories"]["910001"]["amount"] == "8"
    assert snapshot["partners"][0]["cc_spend_history"]["categories"]["910001"]["amount"] == "10.3"
    assert len(history["groups"]) == 3
    report_sync.get_transactions.assert_called_once_with("1100099", "2026-07-01", "2026-07-31")
    # Supply the report's supported wrapped shape, avoiding its legacy list-file bridge.
    storage.atomic_write_json(storage.monthly_ps_raw_path("2026-07"), {"transactions": transactions})
    report = report_builder.build_report("2026-07")
    assert report["detailed"]["common"]["total"] == pytest.approx(8)
    assert report["detailed"]["home"]["total"] == 0
    assert sum(Decimal(c["amount"]) for c in history["groups"][0]["categories"].values()) == 8
    assert [g["categories"] for g in history["groups"][1:]] == [{}, {}]


def test_sync_empty_closed_month_is_zero_only_with_valid_report_config(report_sync):
    assert sync_runner.sync_all("2026-07", "2026-07").errors == []
    history = storage.read_json(storage.bills_dashboard_path("2026-07"))["economy_spend_history"]
    assert history["status"] == "complete"
    assert all(g["categories"] == {} and g["uncategorized_amount"] == "0" for g in history["groups"])
    storage.atomic_write_json(storage.PRIVATE_DATA_DIR / "detailed_section_mapping.json", {
        "category_sections": {"910001": "not-a-section"}, "account_roles": {},
    })
    assert sync_runner.sync_all("2026-07", "2026-07").errors == []
    snapshot = storage.read_json(storage.bills_dashboard_path("2026-07"))
    assert snapshot["economy_spend_history"]["status"] == "unavailable"
    assert snapshot["economy_spend_history"]["groups"] is None
    assert snapshot["partners"][0]["cc_spend_history"]["status"] == "complete"


def test_sync_acquisition_start_controls_report_month_closure(report_sync, monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 7, 31, 23, 59, tzinfo=tz)
    monkeypatch.setattr(sync_runner, "datetime", Clock)
    assert sync_runner.sync_all("2026-07", "2026-07").errors == []
    history = storage.read_json(storage.bills_dashboard_path("2026-07"))["economy_spend_history"]
    assert history["status"] == "partial" and history["reason"] == "open_month"
    assert history["groups"] is None


def test_missing_report_mapping_does_not_invent_complete_zeros(fake_sync):
    assert sync_runner.sync_all("2026-07", "2026-07").errors == []
    history = storage.read_json(storage.bills_dashboard_path("2026-07"))["economy_spend_history"]
    assert history["status"] == "unavailable" and history["reason"] == "missing_source_context"
