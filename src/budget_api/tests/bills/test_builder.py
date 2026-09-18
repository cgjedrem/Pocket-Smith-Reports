"""F2-BE bills builder tests Ã¢â‚¬â€ build_bills_snapshot + ensure_prior_month."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from budget_api.services.bills_builder import (
    NoBillsAccountError,
    _back_walk_past_balances,
    _bills_account_id,
    _current_month,
    _filter_posted,
    _partner_slot_map,
    _past_month_cash_flow,
    _savings_account_ids,
    build_bills_snapshot,
    ensure_prior_month,
)
from budget_api.services.ps_client import PSClient

# -- Fixtures ----------------------------------------------------------------

# These fixtures were authored in Aug 2026 and assume "2026-08" is the
# current month and "2026-09" is future. Pin the builder clock so the suite
# stays deterministic across calendar rollover (CI broke on 2026-09-01 when
# August became a past month).
PINNED_NOW = date(2026, 8, 30)

ACCOUNT_MAPPINGS = {
    "partners": {
        "partner_a": {"label": "Fixture A", "savings_category_id": 2100014},
        "partner_b": {"label": "Fixture B", "savings_category_id": 2100010},
    },
    "accounts": {
        "1100001": {
            "name": "FxA Check",
            "partner_id": "partner_a",
            "type": "checking",
            "excluded": False,
        },
        "1100002": {
            "name": "FxA Savings",
            "partner_id": "partner_a",
            "type": "savings",
            "excluded": False,
        },
        "1100003": {
            "name": "FxA CC",
            "partner_id": "partner_a",
            "type": "cc",
            "excluded": False,
        },
        "1100007": {
            "name": "FxB Check",
            "partner_id": "partner_b",
            "type": "checking",
            "excluded": False,
        },
        "1100006": {
            "name": "FxB Savings",
            "partner_id": "partner_b",
            "type": "savings",
            "excluded": False,
        },
        "1100008": {
            "name": "Fixture B CC",
            "partner_id": "partner_b",
            "type": "cc",
            "excluded": False,
        },
    },
}

CATEGORY_ROLES = {
    "2100013": "income",
    "2100003": "spend",
    "2100001": "savings",
    "2100011": "spend",
    # Per-partner savings categories â€“ these override is_transfer exclusion.
    "2100014": "spend",  # Sparekonto (Fixture A) â€“ real PS uses "spend" role
    "2100010": "spend",  # Sparekonto (Fixture B)
}

CATEGORY_CATALOG = [
    {"id": 2100003, "title": "Common", "children": []},
    {"id": 2100001, "title": "Savings", "children": []},
    {
        "id": 2100002,
        "title": "Transfers",
        "children": [
            {"id": 2100011, "title": "CC Payment (paired)", "children": []},
        ],
    },
]

ACCOUNT_CATALOG = [
    {"id": 1100001, "current_balance": 9886.31, "starting_balance": 97740.37},
    {"id": 1100002, "current_balance": 32000, "starting_balance": 28000},
    {"id": 1100003, "current_balance": 27657.91, "starting_balance": 26837.2},
    {"id": 1100007, "current_balance": 5000, "starting_balance": 4000},
    {"id": 1100006, "current_balance": 61000, "starting_balance": 55000},
    {"id": 1100008, "current_balance": 3000, "starting_balance": 2000},
]


def _ps_events():
    return [
        {
            "id": "evt-1",
            "date": "2026-07-25",
            "note": "Salary",
            "category": {"id": 2100013, "title": "Income", "is_transfer": False},
            "transaction_account": {"id": 1100001, "type": "bank"},
            "amount": 42000,
        },
        {
            "id": "evt-2",
            "date": "2026-07-10",
            "note": "Rent",
            "category": {"id": 2100003, "title": "Common", "is_transfer": False},
            "transaction_account": {"id": 1100001, "type": "bank"},
            "amount": -15500,
        },
        {
            "id": "evt-3",
            "date": "2026-07-15",
            "note": "New laptop",
            "category": {"id": 2100003, "title": "Electronics", "is_transfer": False},
            "transaction_account": {"id": 1100003, "type": "credits"},
            "amount": -5000,
        },
    ]


def _ps_transactions():
    return [
        {
            "id": 1,
            "date": "2026-07-15",
            "amount": -500,
            "status": "posted",
            "category": {"id": 2100003, "title": "Common", "is_transfer": False},
            "transaction_account": {"id": 1100003, "type": "credits"},
        },
        {
            "id": 2,
            "date": "2026-07-10",
            "amount": -5000,
            "status": "posted",
            "category": {
                "id": 2100011,
                "title": "CC Payment (paired)",
                "is_transfer": False,
            },
            "transaction_account": {"id": 1100001, "type": "bank"},
        },
    ]


# -- build_bills_snapshot tests ----------------------------------------------


def test_back_walk_past_balances_single_month():
    # one step back from anchor
    result = _back_walk_past_balances(13917.02, {"2026-07": 8920.61})
    assert result == {"2026-07": pytest.approx(4996.41)}


def test_back_walk_past_balances_multiple_months_chain():
    # each month chains off the previous back-walk result, newest first
    deltas = {"2026-05": 2000.0, "2026-07": 8920.61, "2026-06": -11872.68}
    result = _back_walk_past_balances(13917.02, deltas)
    assert result["2026-07"] == pytest.approx(13917.02 - 8920.61)
    assert result["2026-06"] == pytest.approx(result["2026-07"] + 11872.68)
    assert result["2026-05"] == pytest.approx(result["2026-06"] - 2000.0)
    assert len(result) == 3


def test_build_bills_snapshot_returns_valid_dict():
    snapshot = build_bills_snapshot(
        month="2026-07",
        events=_ps_events(),
        transactions=_ps_transactions(),
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined=None,
        deltas_per_month=None,
    )
    assert snapshot["month"] == "2026-07"
    assert snapshot["month_label"] == "July 2026"
    assert "partners" in snapshot
    assert len(snapshot["partners"]) == 2


def test_build_bills_snapshot_validates_with_pydantic():
    snapshot = build_bills_snapshot(
        month="2026-07",
        events=_ps_events(),
        transactions=_ps_transactions(),
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined=None,
        deltas_per_month=None,
    )
    # If it doesn't raise, validation passed.
    from budget_api.models.bills import BillsSnapshot

    BillsSnapshot.model_validate(snapshot)


def test_build_bills_snapshot_raises_no_bills_account_error():
    # Remove Fixture A's checking account.
    bad_mappings = json.loads(json.dumps(ACCOUNT_MAPPINGS))
    del bad_mappings["accounts"]["1100001"]

    with pytest.raises(NoBillsAccountError, match="Fixture A"):
        build_bills_snapshot(
            month="2026-07",
            events=_ps_events(),
            transactions=_ps_transactions(),
            account_mappings=bad_mappings,
            category_roles=CATEGORY_ROLES,
            category_catalog=CATEGORY_CATALOG,
            account_catalog=ACCOUNT_CATALOG,
            live_combined=None,
            deltas_per_month=None,
        )


def test_build_bills_snapshot_aggregates_multiple_cc_accounts():
    # Add a second CC account for Fixture A.
    mappings = json.loads(json.dumps(ACCOUNT_MAPPINGS))
    mappings["accounts"]["1100004"] = {
        "name": "FxA CC Bank C",
        "partner_id": "partner_a",
        "type": "cc",
        "excluded": False,
    }
    account_catalog = list(ACCOUNT_CATALOG) + [
        {"id": 1100004, "current_balance": 1000, "starting_balance": 800},
    ]
    events = _ps_events() + [
        {
            "id": "evt-4",
            "date": "2026-07-20",
            "note": "Headphones",
            "category": {"id": 2100003, "title": "Electronics", "is_transfer": False},
            "transaction_account": {"id": 1100004, "type": "bank"},
            "amount": -2000,
        },
    ]

    snapshot = build_bills_snapshot(
        month="2026-07",
        events=events,
        transactions=_ps_transactions(),
        account_mappings=mappings,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=account_catalog,
        live_combined=None,
        deltas_per_month=None,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    # Both CC events should appear in events.
    cc_events = [e for e in partner_a["events"] if e["type"] == "buy"]
    assert len(cc_events) == 2


def test_build_bills_snapshot_includes_planned_cc_buys():
    """Snapshot's partners[].planned_cc_buys = sum of type=buy events for
    that partner. Independent of real_cc_bill / estimated_cc_bill (realized
    card spend)."""
    # _ps_events() has evt-3: a 5000 buy on 1100003 (FxA CC) classified as
    # type=buy for Fixture A. Expected planned_cc_buys = 5000 for Fixture A,
    # 0 for Fixture B.
    snapshot = build_bills_snapshot(
        month="2026-07",
        events=_ps_events(),
        transactions=_ps_transactions(),
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined=None,
        deltas_per_month=None,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    partner_b = next(p for p in snapshot["partners"] if p["partner"] == "Fixture B")
    assert partner_a["planned_cc_buys"] == 5000
    assert partner_b["planned_cc_buys"] == 0


def test_build_bills_snapshot_schema_version_is_5():
    """schema-5: additive partner_id + partner_slot on events/partners (T043).
    v4 snapshots still load (both fields default "")."""
    snapshot = build_bills_snapshot(
        month="2026-07",
        events=_ps_events(),
        transactions=_ps_transactions(),
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined=None,
        deltas_per_month=None,
    )
    assert snapshot["schema_version"] == 5


def test_build_bills_snapshot_emits_partner_id_and_slot():
    """T043: partner_id is a pure passthrough of the mappings key; slot is
    deterministic sorted-partner_id order (identity-neutral)."""
    snapshot = build_bills_snapshot(
        month="2026-07",
        events=_ps_events(),
        transactions=_ps_transactions(),
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined=None,
        deltas_per_month=None,
    )
    by_id = {p["partner_id"]: p for p in snapshot["partners"]}
    assert set(by_id) == {"partner_a", "partner_b"}
    assert by_id["partner_a"]["partner_slot"] == "a"
    assert by_id["partner_b"]["partner_slot"] == "b"
    for block in snapshot["partners"]:
        for event in block["events"]:
            assert event["partner_id"] == block["partner_id"]
            assert event["partner_slot"] == block["partner_slot"]


def test_build_bills_snapshot_includes_warnings():
    warnings = ["Prior month 2026-06 auto-fetched during sync"]
    snapshot = build_bills_snapshot(
        month="2026-07",
        events=_ps_events(),
        transactions=_ps_transactions(),
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        warnings=warnings,
        live_combined=None,
        deltas_per_month=None,
    )
    assert snapshot["warnings"] == warnings


def test_build_bills_snapshot_title_is_category_account_is_bank_name():
    """Contract: event.title = category, event.account = bank account name.

    PS /users/{id}/events has no payee/note for scheduled events. The
    primary label in the UI is the category (e.g. "Mortgage", "Salary"),
    and the subtitle is the bank account (from scenario.title).
    """
    real_shape_events = [
        {
            "id": "salary-c",
            "date": "2026-08-12",
            "amount": 48111,
            "scenario": {
                "account_id": 4004538,
                "title": "FxA Check Nordic Bank",
            },
            "category": {
                "id": 2100013,
                "title": "Salary (Fixture A)",
                "is_transfer": False,
            },
        },
        {
            "id": "mort-r1",
            "date": "2026-08-17",
            "amount": -15000,
            "scenario": {
                "account_id": 5245490,
                "title": "FxB Check Nordic Bank",
            },
            "category": {"id": 2100003, "title": "Mortgage", "is_transfer": False},
        },
    ]

    catalog = [
        {**a, "account_id": {1100001: 4004538, 1100007: 5245490}.get(a["id"])}
        for a in ACCOUNT_CATALOG
    ]

    snapshot = build_bills_snapshot(
        month="2026-08",
        events=real_shape_events,
        transactions=[],
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=catalog,
        live_combined=None,
        deltas_per_month=None,
    )

    all_events = [e for p in snapshot["partners"] for e in p["events"]]
    by_id = {e["id"]: e for e in all_events}
    assert by_id["salary-c"]["title"] == "Salary (Fixture A)"
    assert by_id["salary-c"]["account"] == "FxA Check Nordic Bank"
    assert by_id["mort-r1"]["title"] == "Mortgage"
    assert by_id["mort-r1"]["account"] == "FxB Check Nordic Bank"
    # category key no longer exists.
    assert "category" not in by_id["salary-c"]


def test_build_bills_snapshot_handles_real_ps_event_shape():
    """Regression: real PS /users/{id}/events uses scenario.account_id
    (bank id), not transaction_account.id. Snapshot must still keep them.

    Repro of bills-events-empty bug (Aug 2026): 5 events fetched, 0 kept.
    """
    # Catalog with bank_id Ã¢â€ â€™ transaction_account.id mapping.
    catalog = list(ACCOUNT_CATALOG) + [
        # FxA Check: bank=4004538, txn_acct=1100001
        # FxB Check: bank=5245490, txn_acct=1100007
    ]
    # Patch the catalog entries with account_id (bank) so resolve works.
    catalog = [
        {**a, "account_id": {1100001: 4004538, 1100007: 5245490}.get(a["id"])}
        for a in catalog
    ]

    real_shape_events = [
        # 2 salary events (Fixture A + Fixture B checking)
        {
            "id": "salary-c",
            "date": "2026-08-12",
            "amount": 48111,
            "scenario": {"account_id": 4004538, "title": "FxA Check"},
            "category": {"id": 2100013, "title": "Salary", "is_transfer": False},
        },
        {
            "id": "salary-r",
            "date": "2026-08-12",
            "amount": 40814,
            "scenario": {"account_id": 5245490, "title": "FxB Check"},
            "category": {"id": 2100013, "title": "Salary", "is_transfer": False},
        },
        # 3 mortgage events (Fixture AÃ—2 + Fixture BÃ—1)
        {
            "id": "mort-c1",
            "date": "2026-08-17",
            "amount": -15000,
            "scenario": {"account_id": 4004538, "title": "FxA Check"},
            "category": {"id": 2100003, "title": "Mortgage", "is_transfer": False},
        },
        {
            "id": "mort-c2",
            "date": "2026-08-17",
            "amount": -4000,
            "scenario": {"account_id": 4004538, "title": "FxA Check"},
            "category": {"id": 2100003, "title": "Mortgage", "is_transfer": False},
        },
        {
            "id": "mort-r1",
            "date": "2026-08-17",
            "amount": -15000,
            "scenario": {"account_id": 5245490, "title": "FxB Check"},
            "category": {"id": 2100003, "title": "Mortgage", "is_transfer": False},
        },
    ]

    snapshot = build_bills_snapshot(
        month="2026-08",
        events=real_shape_events,
        transactions=[],
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=catalog,
        live_combined=None,
        deltas_per_month=None,
    )

    # All 5 events kept (was 0 before fix).
    assert snapshot["source_counts"]["ps_events_fetched"] == 5
    assert snapshot["source_counts"]["events_kept_after_filter"] == 5

    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    partner_b = next(p for p in snapshot["partners"] if p["partner"] == "Fixture B")

    # 1 salary + 2 mortgage for Fixture A.
    assert len(partner_a["events"]) == 3
    assert sum(1 for e in partner_a["events"] if e["type"] == "salary") == 1
    assert sum(1 for e in partner_a["events"] if e["type"] == "bill") == 2

    # 1 salary + 1 mortgage for Fixture B.
    assert len(partner_b["events"]) == 2
    assert sum(1 for e in partner_b["events"] if e["type"] == "salary") == 1
    assert sum(1 for e in partner_b["events"] if e["type"] == "bill") == 1

    # Salary + bills surface in derived fields.
    assert snapshot["bills_count"] == 3  # 2 + 1 mortgage
    assert snapshot["buys_count"] == 0


def test_month_flags_uses_local_time_not_utc():
    """Regression: at local month boundary, current-month flag must follow
    local date, not UTC. Otherwise a user in UTC+offset sees next month
    marked `is_past` until UTC rolls over.

    Stub `_current_month` directly Ã¢â‚¬â€ safer than patching stdlib `datetime.now`,
    which is used by other call sites in the same process.
    """
    from budget_api.services import bills_builder

    # Simulate: local clock says 2026-09-01 00:30 (just rolled into Sep),
    # but UTC clock would still say 2026-08-31 22:30 (the bug).
    real_current = bills_builder._current_month
    bills_builder._current_month = lambda: "2026-09"
    try:
        # Sep must NOT be flagged past.
        is_past, is_current, is_future = bills_builder._month_flags("2026-09")
        assert (is_past, is_current, is_future) == (False, True, False)
        # Aug must be past, not current.
        is_past, is_current, is_future = bills_builder._month_flags("2026-08")
        assert (is_past, is_current, is_future) == (True, False, False)
        # Oct must be future.
        is_past, is_current, is_future = bills_builder._month_flags("2026-10")
        assert (is_past, is_current, is_future) == (False, False, True)
    finally:
        bills_builder._current_month = real_current


def test_build_bills_snapshot_real_cc_bill_differs_per_partner():
    """Regression: real_cc_bill must differ per partner (was identical before).

    July 2026 scenario Ã¢â‚¬â€ Fixture A: 3 CC-side payments, Fixture B: 1.
    CC-side = positive amount on the CC account (what was charged to the
    card), NOT the bills-side (negative on checking, the paydown transfer).
    """
    # 1100003 = FxA CC, 1100008 = FxB CC.
    cc_payment_cat = 2100011
    posted_txns = [
        # Fixture A: 3 CC-side payments to FxA CC.
        {
            "amount": 1000,
            "status": "posted",
            "transaction_account": {"id": 1100003},
            "category": {"id": cc_payment_cat},
        },
        {
            "amount": 2500,
            "status": "posted",
            "transaction_account": {"id": 1100003},
            "category": {"id": cc_payment_cat},
        },
        {
            "amount": 500,
            "status": "posted",
            "transaction_account": {"id": 1100003},
            "category": {"id": cc_payment_cat},
        },
        # Fixture B: 1 CC-side payment to FxB CC.
        {
            "amount": 1500,
            "status": "posted",
            "transaction_account": {"id": 1100008},
            "category": {"id": cc_payment_cat},
        },
        # Bills-side paired txn (negative on checking) Ã¢â‚¬â€ must be excluded
        # because the formula now targets the CC account, not checking.
        {
            "amount": -1500,
            "status": "posted",
            "transaction_account": {"id": 1100001},
            "category": {"id": cc_payment_cat},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-07",  # past month
        events=[],
        transactions=posted_txns,
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined=None,
        deltas_per_month=None,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    partner_b = next(p for p in snapshot["partners"] if p["partner"] == "Fixture B")

    # Fixture A: 1000 + 2500 + 500 = 4000 (only FxA CC CC-payments).
    assert partner_a["real_cc_bill"] == 4000
    # Fixture B: 1500.
    assert partner_b["real_cc_bill"] == 1500
    # Distinct values, not the same number.
    assert partner_a["real_cc_bill"] != partner_b["real_cc_bill"]


def test_build_bills_snapshot_estimated_cc_bill_differs_per_partner():
    """Regression: estimated_cc_bill must differ per partner (was identical).

    Aug 2026 (current) Ã¢â‚¬â€ mÃ¢Ë†â€™1 proxy: the current month's estimate is the
    PRIOR month's (July) CC spend Ã¢â‚¬â€ the statement being paid in August.
    Posted July CC txns per partner Ã¢â€ â€™ distinct estimates per partner.
    """
    prior_txns = [
        # Fixture A CC-spend (July): 800 on FxA CC (1100003).
        {"amount": -800, "status": "posted", "transaction_account": {"id": 1100003}},
        # Fixture B CC-spend (July): 300 on FxB CC (1100008).
        {"amount": -300, "status": "posted", "transaction_account": {"id": 1100008}},
    ]
    snapshot = build_bills_snapshot(
        month="2026-08",  # current month Ã¢â€ â€™ estimated = July (mÃ¢Ë†â€™1) proxy
        events=[],
        transactions=[],
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        prior_transactions=prior_txns,
        prior_events=[],
        live_combined=None,
        deltas_per_month=None,
        today=PINNED_NOW,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    partner_b = next(p for p in snapshot["partners"] if p["partner"] == "Fixture B")

    # Fixture A: 800 (July proxy). Fixture B: 300 (July proxy).
    assert partner_a["estimated_cc_bill"] == 800
    assert partner_b["estimated_cc_bill"] == 300
    assert partner_a["estimated_cc_bill"] != partner_b["estimated_cc_bill"]


def test_build_bills_snapshot_estimated_cc_bill_ignores_buys_for_future():
    """m+2 and beyond (2026-12 = m+4 under the frozen Aug clock): estimate
    = the month's own scheduled buy envelopes only (user model 2026-09-15).
    No posted data or prior-month baseline exists this far out Ã¢â‚¬â€ December
    posted txns are impossible, and mÃ¢Ë†â€™1 (November) data no longer reaches
    forward."""
    events = [
        # December scheduled buys on FxA CC.
        {
            "id": "buy-1",
            "date": "2026-12-05",
            "amount": -1200,
            "transaction_account": {"id": 1100003, "type": "credits"},
            "category": {"id": 2100003, "title": "Hello Fresh", "is_transfer": False},
        },
        {
            "id": "buy-2",
            "date": "2026-12-12",
            "amount": -300,
            "transaction_account": {"id": 1100003, "type": "credits"},
            "category": {"id": 2100003, "title": "Memberships", "is_transfer": False},
        },
    ]
    prior_txns = [
        {"amount": -800, "status": "posted", "transaction_account": {"id": 1100003}},
    ]
    prior_events = [
        {
            "id": "prior-buy",
            "date": "2026-11-05",
            "amount": -200,
            "transaction_account": {"id": 1100003, "type": "credits"},
            "category": {"id": 2100003, "title": "Hello Fresh", "is_transfer": False},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-12",  # m+4 Ã¢â€ â€™ scheduled buy envelopes only
        events=events,
        transactions=[],
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        prior_transactions=prior_txns,
        prior_events=prior_events,
        live_combined=None,
        deltas_per_month=None,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    # December envelopes 1200 + 300 = 1500. The 800 Nov posted spend and
    # the 200 Nov envelope contribute nothing this far out.
    assert partner_a["estimated_cc_bill"] == 1500


# -- ensure_prior_month tests ------------------------------------------------


def test_ensure_prior_month_reads_from_disk_if_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PRIVATE_DATA_DIR", tmp_path)

    prior_month = "2026-06"
    events_path = tmp_path / f"events_{prior_month}.json"
    txns_path = tmp_path / f"{prior_month}_ps_raw.json"
    events_path.write_text('[{"id": "prior-evt"}]')
    txns_path.write_text('[{"id": "prior-txn"}]')

    client = MagicMock(spec=PSClient)
    warnings: list[str] = []

    prior_events, prior_txns = ensure_prior_month(client, "user-1", "2026-07", warnings)

    assert prior_events == [{"id": "prior-evt"}]
    assert prior_txns == [{"id": "prior-txn"}]
    assert warnings == []  # no warning when reading from disk
    client.get_events.assert_not_called()


def test_ensure_prior_month_auto_fetches_if_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PRIVATE_DATA_DIR", tmp_path)

    client = MagicMock(spec=PSClient)
    client.get_events.return_value = [{"id": "fetched-evt"}]
    client.get_transactions.return_value = [{"id": "fetched-txn"}]
    warnings: list[str] = []

    prior_events, prior_txns = ensure_prior_month(client, "user-1", "2026-07", warnings)

    assert prior_events == [{"id": "fetched-evt"}]
    assert prior_txns == [{"id": "fetched-txn"}]
    assert len(warnings) == 1
    assert "auto-fetched" in warnings[0]
    client.get_events.assert_called_once()
    client.get_transactions.assert_called_once()


# Need to import storage for monkeypatching.
from budget_api.services import storage  # noqa: E402

# -- Savings balance end-to-end (per Q4-Q11) --------------------------------


def test_build_bills_snapshot_past_savings_balance_uses_real_end_balances(
    tmp_path, monkeypatch
):
    """Past month savings_balance = back-walk from live anchor.

    Anchor (live combined) = 15000 (bills 7000 + savings 8000 from catalog).
    delta[2026-05] = 3000 (one posted +3000 on savings during the month).
    Back-walk: balance[2026-05] = 15000 - 3000 = 12000.
    Savings delta = sum of this-month posted txns on partner bills+savings
    accounts (real cash flow during the month) = 3000.

    Sandbox PRIVATE_DATA_DIR so disk-resident raw files don't leak in.
    """
    monkeypatch.setattr(storage, "PRIVATE_DATA_DIR", tmp_path)

    mappings = {
        "partners": {
            "partner_a": {
                "label": "Fixture A",
                "savings_category_id": 2100014,
            }
        },
        "accounts": {
            "1100001": {  # FxA Check
                "name": "FxA Check",
                "partner_id": "partner_a",
                "type": "checking",
                "excluded": False,
            },
            "1100002": {  # FxA Savings
                "name": "FxA Savings",
                "partner_id": "partner_a",
                "type": "savings",
                "excluded": False,
            },
        },
    }
    catalog = [
        {
            "id": 1100001,
            "account_id": 1100001,
            "current_balance": 7000,
            "starting_balance": 10000,
        },
        {
            "id": 1100002,
            "account_id": 1100002,
            "current_balance": 8000,
            "starting_balance": 5000,
        },
    ]
    events = [
        {
            "id": "sal-1",
            "date": "2026-05-15",
            "amount": 5000,
            "scenario": {"account_id": 1100001, "title": "FxA Check"},
            "category": {"id": 2100013, "is_transfer": False},
        },
        {
            "id": "bill-1",
            "date": "2026-05-20",
            "amount": -8000,
            "scenario": {"account_id": 1100001, "title": "FxA Check"},
            "category": {"id": 2100003, "is_transfer": False},
        },
    ]
    posted_txns = [
        {
            "amount": 3000,
            "date": "2026-05-15",
            "status": "posted",
            "transaction_account": {"id": 1100002},
            "category": {"id": 2100014, "is_transfer": False},
        },
        # CC txn on a non-partner account Ã¢â‚¬â€ must NOT count toward delta
        # (delta is real cash flow on partner's bills+savings only).
        {
            "amount": -800,
            "date": "2026-05-10",
            "status": "posted",
            "transaction_account": {"id": 1100003},  # FxA CC
            "category": {"id": 2100003, "is_transfer": False},
        },
        # Out-of-month txn on a partner savings account Ã¢â‚¬â€ must NOT count
        # toward delta (date filter). Use non-savings category so it
        # doesn't pollute scheduled_savings (which is the all-time sum of
        # the savings category, not month-bounded).
        {
            "amount": 9999,
            "date": "2026-04-15",
            "status": "posted",
            "transaction_account": {"id": 1100002},
            "category": {"id": 2100003, "is_transfer": False},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-05",
        events=events,
        transactions=posted_txns,
        account_mappings=mappings,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=catalog,
        live_combined={"partner_a": 15000.0},
        deltas_per_month={"partner_a": {"2026-05": 3000.0}},
    )
    partner_a = snapshot["partners"][0]
    # Back-walk from live anchor: 15000 - delta(3000) = 12000.
    assert partner_a["savings_balance"] == 12000
    # Delta = sum of 2026-05 posted txns on partner SAVINGS = 3000
    # (CC + April savings txn excluded by account_id / date filter;
    #  any checking txn would also be excluded Ã¢â‚¬â€ savings-only rule).
    assert partner_a["savings_delta"] == 3000
    assert partner_a["savings_transfer"] == 1500


def test_build_bills_snapshot_savings_event_buckets_correctly():
    """Savings event in UI list with type=savings (not excluded)."""
    mappings = {
        "partners": {
            "partner_a": {
                "label": "Fixture A",
                "savings_category_id": 2100014,
            }
        },
        "accounts": {
            "1100001": {  # FxA Check
                "name": "FxA Check",
                "partner_id": "partner_a",
                "type": "checking",
                "excluded": False,
            },
            "1100002": {  # FxA Savings
                "name": "FxA Savings",
                "partner_id": "partner_a",
                "type": "savings",
                "excluded": False,
            },
        },
    }
    catalog = [
        {
            "id": 1100001,
            "account_id": 1100001,
            "current_balance": 0,
            "starting_balance": 0,
        },
        {
            "id": 1100002,
            "account_id": 1100002,
            "current_balance": 0,
            "starting_balance": 0,
        },
    ]
    events = [
        {
            "id": "savings-evt-1",
            "date": "2026-09-15",
            "amount": -2000,
            "scenario": {"account_id": 1100001, "title": "FxA Check"},
            "category": {
                "id": 2100014,
                "title": "Sparekonto (Fixture A)",
                "is_transfer": False,
            },
        }
    ]
    snapshot = build_bills_snapshot(
        month="2026-09",  # future
        events=events,
        transactions=[],
        account_mappings=mappings,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=catalog,
        live_combined=None,
        deltas_per_month=None,
    )
    partner_a = snapshot["partners"][0]
    # Event landed in events list with type=savings.
    savings_events = [e for e in partner_a["events"] if e["type"] == "savings"]
    assert len(savings_events) == 1
    assert savings_events[0]["id"] == "savings-evt-1"
    # Raw amount preserved (UI converts to abs for display).
    assert savings_events[0]["amount"] == -2000


# -- real_bills / planned-vs-actual (past-month contract) -------------------
#
# Past month now populates real_bills (posted checking debits minus CC-paydown,
# transfers, exclude-role categories). Current/future months leave it None.
# Past months also populate estimated_cc_bill (NEW contract Ã¢â‚¬â€ was None before).
# 2026-07 is past (current local month is 2026-08).


def test_build_bills_snapshot_real_bills_populated_for_past():
    """Past month: real_bills is the sum of posted checking debits.

    Setup: 4 posted debits on FxA checking 1100001.
      - Mortgage -15000 (cat 2100003, real bill) Ã¢â€ â€™ kept
      - Mortgage -4000 (cat 2100003, real bill) Ã¢â€ â€™ kept
      - CC paydown -5000 (cat 2100011, transfer) Ã¢â€ â€™ excluded
      - Personal Transfer -200 (cat 2100016, exclude role) Ã¢â€ â€™ excluded
    Expected real_bills = 19000.
    """
    posted_txns = [
        {
            "amount": -15000,
            "status": "posted",
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100003, "is_transfer": False},
        },
        {
            "amount": -4000,
            "status": "posted",
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100003, "is_transfer": False},
        },
        {
            "amount": -5000,
            "status": "posted",
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100011, "is_transfer": False},  # CC paydown
        },
        {
            "amount": -200,
            "status": "posted",
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100016, "is_transfer": False},  # exclude
        },
    ]
    # Category roles with exclude entry.
    category_roles_with_exclude = dict(CATEGORY_ROLES)
    category_roles_with_exclude["2100016"] = "exclude"
    snapshot = build_bills_snapshot(
        month="2026-07",  # past
        events=[],
        transactions=posted_txns,
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=category_roles_with_exclude,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined=None,
        deltas_per_month=None,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    assert partner_a["real_bills"] == 19000


def test_build_bills_snapshot_real_bills_none_for_current_and_future():
    """Current/future months: real_bills is None (no past data to draw from)."""
    # Current month (2026-08).
    snapshot_cur = build_bills_snapshot(
        month="2026-08",
        events=[],
        transactions=[],
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined=None,
        deltas_per_month=None,
        today=PINNED_NOW,
    )
    assert snapshot_cur["partners"][0]["real_bills"] is None

    # Future month (2026-12).
    snapshot_fut = build_bills_snapshot(
        month="2026-12",
        events=[],
        transactions=[],
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined=None,
        deltas_per_month=None,
    )
    assert snapshot_fut["partners"][0]["real_bills"] is None


# -- cc_usage_by_category (per-category-title real CC spend) -----------------
#
# New PartnerBills field: posted CC spend keyed by category title, same
# filters/gate as cc_usage. Past + current months populate it; future and
# no-CC-activity months are None (FE hides the free-budget section on null).


def test_build_bills_snapshot_cc_usage_by_category_populated_for_past():
    """Past month: cc_usage_by_category groups posted FxA-CC spend by title.

    Setup: posted debits on FxA CC 1100003.
      - Groceries -500 + Groceries -300 (cat 2100003) Ã¢â€ â€™ 800
      - Dining -1200 (new cat, no role) Ã¢â€ â€™ 1200
      - CC paydown -5000 (cat 2100011) Ã¢â€ â€™ excluded
      - Groceries -777 on FxB CC 1100008 Ã¢â€ â€™ stays Fixture B-side only

    Note: no per-bill actuals exist Ã¢â‚¬â€ this is card spend only.
    """
    posted_txns = [
        {
            "amount": -500,
            "status": "posted",
            "transaction_account": {"id": 1100003, "type": "credits"},
            "category": {"id": 2100003, "title": "Groceries", "is_transfer": False},
        },
        {
            "amount": -300,
            "status": "posted",
            "transaction_account": {"id": 1100003, "type": "credits"},
            "category": {"id": 2100003, "title": "Groceries", "is_transfer": False},
        },
        {
            "amount": -1200,
            "status": "posted",
            "transaction_account": {"id": 1100003, "type": "credits"},
            "category": {"id": 2100017, "title": "Dining", "is_transfer": False},
        },
        {
            "amount": -5000,
            "status": "posted",
            "transaction_account": {"id": 1100003, "type": "credits"},
            "category": {"id": 2100011, "title": "CC Payment (paired)", "is_transfer": False},
        },
        # Not posted Ã¢â€ â€™ excluded.
        {
            "amount": -9999,
            "status": "pending",
            "transaction_account": {"id": 1100003, "type": "credits"},
            "category": {"id": 2100003, "title": "Groceries", "is_transfer": False},
        },
        # Other partner's CC Ã¢â€ â€™ excluded from Fixture A's map.
        {
            "amount": -777,
            "status": "posted",
            "transaction_account": {"id": 1100008, "type": "credits"},
            "category": {"id": 2100003, "title": "Groceries", "is_transfer": False},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-07",  # past
        events=[],
        transactions=posted_txns,
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined=None,
        deltas_per_month=None,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    partner_b = next(p for p in snapshot["partners"] if p["partner"] == "Fixture B")
    assert partner_a["cc_usage_by_category"] == {"Groceries": 800, "Dining": 1200}
    # Same filters as cc_usage Ã¢â€ â€™ totals match.
    assert sum(partner_a["cc_usage_by_category"].values()) == partner_a["cc_usage"]
    # Fixture B's CC txn lands in HER map only (partner scoping).
    assert partner_b["cc_usage_by_category"] == {"Groceries": 777}


def test_build_bills_snapshot_cc_usage_by_category_none_for_future():
    """Future months never have real CC txns Ã¢â€ â€™ None, not an empty dict."""
    snapshot_fut = build_bills_snapshot(
        month="2026-12",
        events=[],
        transactions=[],
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined=None,
        deltas_per_month=None,
    )
    for partner in snapshot_fut["partners"]:
        assert partner["cc_usage_by_category"] is None


def test_build_bills_snapshot_estimated_cc_bill_populated_for_past_months():
    """NEW contract: past months also get estimated_cc_bill (from m-1 prior data).

    Before this change, the past-month branch forced estimated_cc_bill=None
    (only real_cc_bill was set). Now both fields are populated so the
    FE planned-vs-actual row pair can render.
    """
    # Prior-month (June) CC txns for current July past-month build.
    prior_txns = [
        {
            "amount": -800,
            "status": "posted",
            "transaction_account": {"id": 1100003, "type": "credits"},
        },
    ]
    prior_events = [
        {
            "amount": -200,
            "transaction_account": {"id": 1100003, "type": "credits"},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-07",  # past
        events=[],
        transactions=[],
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        prior_transactions=prior_txns,
        prior_events=prior_events,
        live_combined=None,
        deltas_per_month=None,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    # Past uses include_buys=False Ã¢â€ â€™ only the spend side, not the events.
    assert partner_a["estimated_cc_bill"] == 800
    # real_cc_bill still populated for past (CC-side payments on the card).
    # 0 because there are no posted CC-payments on 1100003 in the test.
    assert partner_a["real_cc_bill"] == 0


# -- savings_balance chain + savings_delta savings-only flow -----------------
#
# Current month now chains from prior-month snapshot (was: backward-walked
# start). Past-month savings_delta is sum of this-month posted txns on the
# partner's SAVINGS accounts only (user decision 2026-08-28 Ã¢â‚¬â€ checking
# noise never counts; was combined bills+savings cash flow).


def test_build_bills_snapshot_current_savings_balance_chains_from_prior(
    tmp_path, monkeypatch
):
    """Current month savings_balance = live combined (anchor).

    Live anchor beats the lag model when provided: the current month
    shows what the bank shows. This month's own events affect
    savings_delta (the flow) but not the anchored stock.
    """
    monkeypatch.setattr(storage, "PRIVATE_DATA_DIR", tmp_path)
    import json

    prior_snap = {
        "schema_version": 4,
        "month": "2026-07",
        "month_label": "July 2026",
        "partners": [
            {
                "partner": "Fixture A",
                "salary": 0,
                "bills": 0,
                "savings_balance": 37000,  # prior chain base
                "savings_delta": 3000,  # prior delta Ã¢â€ â€™ adds to base
            }
        ],
    }
    (tmp_path / "bills_dashboard_2026-07.json").write_text(json.dumps(prior_snap))

    # salary - bills = 42000 - 15000 = 27000 (event-derived flow this
    # month). savings_balance under lag model: 37000 + 3000 = 40000.
    # Custom catalog with `type` so the classifier accepts events.
    # `account_id` field matches `scenario.account_id` for resolution.
    current_catalog = [
        {
            "id": 1100001,
            "account_id": 1100001,
            "type": "bank",
            "current_balance": 7000,
            "starting_balance": 0,
        },
        {
            "id": 1100002,
            "account_id": 1100002,
            "type": "bank",
            "current_balance": 8000,
            "starting_balance": 0,
        },
        {
            "id": 1100003,
            "account_id": 1100003,
            "type": "credits",
            "current_balance": 0,
            "starting_balance": 0,
        },
        {
            "id": 1100007,
            "account_id": 1100007,
            "type": "bank",
            "current_balance": 5000,
            "starting_balance": 0,
        },
        {
            "id": 1100006,
            "account_id": 1100006,
            "type": "bank",
            "current_balance": 61000,
            "starting_balance": 0,
        },
        {
            "id": 1100008,
            "account_id": 1100008,
            "type": "credits",
            "current_balance": 3000,
            "starting_balance": 0,
        },
    ]
    posted_txns = [
        {
            "amount": -6000,
            "date": "2026-08-15",
            "status": "posted",
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100014, "is_transfer": False},
        },
    ]
    events = [
        {
            "id": "sal-1",
            "date": "2026-08-25",
            "amount": 42000,
            "scenario": {"account_id": 1100001, "title": "FxA Check"},
            "category": {"id": 2100013, "is_transfer": False},
        },
        {
            "id": "bill-1",
            "date": "2026-08-10",
            "amount": -15000,
            "scenario": {"account_id": 1100001, "title": "FxA Check"},
            "category": {"id": 2100003, "is_transfer": False},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-08",  # current (local)
        events=events,
        transactions=posted_txns,
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=current_catalog,
        live_combined={"partner_a": 15000.0, "partner_b": 66000.0},
        deltas_per_month={"partner_a": {"2026-07": 3000.0}, "partner_b": {}},
        today=PINNED_NOW,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    # Live anchor wins: savings_balance = live combined (15000), NOT the
    # lag model (prior 37000 + 3000 = 40000).
    assert partner_a["savings_balance"] == 15000
    # savings_delta = savings-accounts-only posted flow. The -6000 txn is
    # on CHECKING (1100001) Ã¢â€ â€™ checking noise, never counts. No savings
    # txns posted Ã¢â€ â€™ 0.0 (correct: nothing saved).
    assert partner_a["savings_delta"] == 0.0
    # savings_planned is the event plan: salary - bills = 42000 - 15000.
    assert partner_a["savings_planned"] == 27000
    assert partner_a["savings_transfer"] == 3000


def test_build_bills_snapshot_current_savings_balance_lag_model(tmp_path, monkeypatch):
    """Current month savings_balance = prior.balance + prior.delta (lag model).

    Current month does NOT include this month's own events. Stock lags
    one month: we don't know what the balance will be at end of month
    until the month becomes past and gets re-synced. Matches the
    production Fixture A August 2026 number (18838).
    """
    monkeypatch.setattr(storage, "PRIVATE_DATA_DIR", tmp_path)
    import json

    prior_snap = {
        "schema_version": 4,
        "month": "2026-07",
        "month_label": "July 2026",
        "partners": [
            {
                "partner": "Fixture A",
                "salary": 0,
                "bills": 0,
                "savings_balance": 9917,  # prior chain base
                "savings_delta": 8921,  # prior delta Ã¢â€ â€™ adds to base
            }
        ],
    }
    (tmp_path / "bills_dashboard_2026-07.json").write_text(json.dumps(prior_snap))

    # Current month events: salary 50000, bills 10000 Ã¢â€ â€™ delta = 40000
    # (the flow this month). But savings_balance (the stock) uses the
    # lag model Ã¢â€ â€™ 9917 + 8921 = 18838. savings_delta is still the
    # current-month flow.
    current_catalog = [
        {
            "id": 1100001,
            "account_id": 1100001,
            "type": "bank",
            "current_balance": 7000,
            "starting_balance": 0,
        },
        {
            "id": 1100002,
            "account_id": 1100002,
            "type": "bank",
            "current_balance": 8000,
            "starting_balance": 0,
        },
        {
            "id": 1100003,
            "account_id": 1100003,
            "type": "credits",
            "current_balance": 0,
            "starting_balance": 0,
        },
        {
            "id": 1100007,
            "account_id": 1100007,
            "type": "bank",
            "current_balance": 5000,
            "starting_balance": 0,
        },
        {
            "id": 1100006,
            "account_id": 1100006,
            "type": "bank",
            "current_balance": 61000,
            "starting_balance": 0,
        },
        {
            "id": 1100008,
            "account_id": 1100008,
            "type": "credits",
            "current_balance": 3000,
            "starting_balance": 0,
        },
    ]
    posted_txns: list[dict] = []
    events = [
        {
            "id": "sal-1",
            "date": "2026-08-25",
            "amount": 50000,
            "scenario": {"account_id": 1100001, "title": "FxA Check"},
            "category": {"id": 2100013, "is_transfer": False},
        },
        {
            "id": "bill-1",
            "date": "2026-08-10",
            "amount": -10000,
            "scenario": {"account_id": 1100001, "title": "FxA Check"},
            "category": {"id": 2100003, "is_transfer": False},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-08",  # current
        events=events,
        transactions=posted_txns,
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=current_catalog,
        live_combined=None,
        deltas_per_month=None,
        today=PINNED_NOW,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    # Lag model: prior.balance (9917) + prior.delta (8921) = 18838.
    assert partner_a["savings_balance"] == 18838
    # savings_delta: no anchor (standalone call) Ã¢â€ â€™ honest None.
    assert partner_a["savings_delta"] is None
    # savings_planned is the event plan: salary - bills = 40000.
    assert partner_a["savings_planned"] == 40000


def test_build_bills_snapshot_current_savings_balance_uses_prior_delta_partner_a_august(
    tmp_path, monkeypatch
):
    """Fixture A August 2026 production scenario â€“ live anchor.

    Live combined (bills + savings current_balance) = 13917.02. Current
    month anchors on it directly â€“ no lag. Flow unchanged: -12902.95.
    """
    monkeypatch.setattr(storage, "PRIVATE_DATA_DIR", tmp_path)
    import json

    prior_snap = {
        "schema_version": 4,
        "month": "2026-07",
        "month_label": "July 2026",
        "partners": [
            {
                "partner": "Fixture A",
                "salary": 0,
                "bills": 0,
                "savings_balance": 9917,
                "savings_delta": 8921,
            }
        ],
    }
    (tmp_path / "bills_dashboard_2026-07.json").write_text(json.dumps(prior_snap))

    # Aug 2026 events on FxA Check (1100001). Same shape as
    # test_build_bills_snapshot_current_savings_delta_matches_net_partner_a_august.
    bank_events = [
        ("2026-08-15", -15000.0),
        ("2026-08-15", -2000.0),
        ("2026-08-15", 48111.0),
        ("2026-08-17", -608.0),
        ("2026-08-20", -2790.0),
        ("2026-08-20", -233.0),
    ]
    events: list[dict] = []
    for i, (d, amt) in enumerate(bank_events):
        is_salary = amt > 0
        events.append(
            {
                "id": f"bank-{i}",
                "date": d,
                "amount": amt,
                "transaction_account": {"id": 1100001, "type": "bank"},
                "category": {
                    "id": 2100013 if is_salary else 2100003,
                    "is_transfer": False,
                },
            }
        )
    # July (m-1) posted CC spend drives the current-month estimate:
    # est_cc_bill = 40382.95 Ã¢â‚¬â€ the statement being paid in August.
    prior_txns = [
        {
            "amount": -40382.95,
            "status": "posted",
            "transaction_account": {"id": 1100003, "type": "credits"},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-08",
        events=events,
        transactions=[],
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        prior_transactions=prior_txns,
        prior_events=[],
        live_combined={"partner_a": 13917.02, "partner_b": 50679.76},
        deltas_per_month={"partner_a": {"2026-07": 8921.0}, "partner_b": {}},
        today=PINNED_NOW,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    # Live anchor: 13917.02 (production live combined for Fixture A).
    assert partner_a["savings_balance"] == pytest.approx(13917.02, abs=0.01)
    # savings_delta = savings-accounts-only posted flow (2026-08-28 rule).
    # No savings txns in this fixture Ã¢â€ â€™ 0.0 (nothing saved). The old
    # anchor-minus-month-start number (8921) was checking noise.
    assert partner_a["savings_delta"] == 0.0
    # Plan unchanged: 48111 - 20631 - 40382.95 = -12902.95.
    assert partner_a["savings_planned"] == pytest.approx(-12902.95, abs=0.01)


def test_build_bills_snapshot_future_savings_balance_lag_model(tmp_path, monkeypatch):
    """Future month savings_balance = prior.balance + prior.delta (lag model).

    Mirrors the current-month lag test. Future month does NOT add
    this month's own events to the stock. Each row's savings_balance
    is the END of that row's month, built from PRIOR month's data only.
    Avoids double-counting. Matches user-verified Fixture A September
    2026: 9917 (Jul bal) + 8921 (Jul delta) = 18838, then 18838 + (-12902.95)
    = 5935.01 â‰ˆ 5935.
    """
    monkeypatch.setattr(storage, "PRIVATE_DATA_DIR", tmp_path)

    # July 2026 (past) snapshot.
    july_snap = {
        "schema_version": 4,
        "month": "2026-07",
        "month_label": "July 2026",
        "partners": [
            {
                "partner": "Fixture A",
                "salary": 0,
                "bills": 0,
                "savings_balance": 9917,
                "savings_delta": 8921,
            }
        ],
    }
    (tmp_path / "bills_dashboard_2026-07.json").write_text(json.dumps(july_snap))
    # August 2026 (current) snapshot Ã¢â‚¬â€ used as the prior for September.
    aug_snap = {
        "schema_version": 4,
        "month": "2026-08",
        "month_label": "August 2026",
        "partners": [
            {
                "partner": "Fixture A",
                "salary": 48111,
                "bills": 20631,
                "savings_balance": 18838,  # 9917 + 8921 (current-month lag)
                "savings_delta": -12902.95,  # Aug flow
            }
        ],
    }
    (tmp_path / "bills_dashboard_2026-08.json").write_text(json.dumps(aug_snap))

    # Sep events: salary 50000, bills 10000. Flow this month: 40000.
    # But the STOCK (savings_balance) uses the lag model: 18838 + (-12902.95)
    # = 5935.01. Prior-month derived from August's snapshot.
    sep_events = [
        {
            "id": "sal-sep",
            "date": "2026-09-25",
            "amount": 50000,
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100013, "is_transfer": False},
        },
        {
            "id": "bill-sep",
            "date": "2026-09-10",
            "amount": -10000,
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100003, "is_transfer": False},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-09",  # future
        events=sep_events,
        transactions=[],
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined={"partner_a": 99999.0, "partner_b": None},
        deltas_per_month={"partner_a": {}, "partner_b": {}},
        today=PINNED_NOW,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    # Lag model: prior.balance (18838) + prior.delta (-12902.95) = 5935.05.
    # Live anchor is IGNORED for future months Ã¢â‚¬â€ lag only.
    assert partner_a["savings_balance"] == pytest.approx(5935.05, abs=0.01)
    # Future: no reality exists Ã¢â€ â€™ savings_delta is None.
    assert partner_a["savings_delta"] is None
    # savings_planned is the event plan: salary (50000) - bills (10000) = 40000.
    assert partner_a["savings_planned"] == pytest.approx(40000, abs=0.01)


def test_build_bills_snapshot_future_savings_balance_uses_prior_delta_partner_a_september(
    tmp_path,
    monkeypatch,
):
    """Fixture A September 2026 production number under lag model.

    Lag chain: Jul bal 9917 + Jul delta 8921 = Aug bal 18838.
               Aug bal 18838 + Aug delta (-12902.95) = Sep bal 5935.05.
    Locks the contract that the user verified against PocketSmith.
    """
    monkeypatch.setattr(storage, "PRIVATE_DATA_DIR", tmp_path)
    july = {
        "schema_version": 4,
        "month": "2026-07",
        "month_label": "July 2026",
        "partners": [
            {
                "partner": "Fixture A",
                "salary": 0,
                "bills": 0,
                "savings_balance": 9917,
                "savings_delta": 8921,
            }
        ],
    }
    august = {
        "schema_version": 4,
        "month": "2026-08",
        "month_label": "August 2026",
        "partners": [
            {
                "partner": "Fixture A",
                "salary": 48111,
                "bills": 20631,
                "savings_balance": 18838,
                "savings_delta": -12902.95,
            }
        ],
    }
    (tmp_path / "bills_dashboard_2026-07.json").write_text(json.dumps(july))
    (tmp_path / "bills_dashboard_2026-08.json").write_text(json.dumps(august))
    snapshot = build_bills_snapshot(
        month="2026-09",
        events=[],
        transactions=[],
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined={"partner_a": 99999.0, "partner_b": None},
        deltas_per_month={"partner_a": {}, "partner_b": {}},
        today=PINNED_NOW,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    # production Fixture A September 2026 number.
    assert partner_a["savings_balance"] == pytest.approx(5935.05, abs=0.01)


def test_build_bills_snapshot_future_savings_delta_includes_cc_bill_partner_a_september(
    tmp_path,
    monkeypatch,
):
    """Fixture A September 2026 (future): savings_delta includes CC bill.

    Pre-fix: salary (48111) - bills (20631) = 27480. Missed the 6919.35
    CC bill projection. Post-fix: salary - bills - est_cc_bill = 20560.65.
    Same formula as current month Ã¢â‚¬â€ no reason to treat the future CC
    projection as free money.

    Sep is m+1 under the frozen Aug clock: est_cc_bill = posted-so-far
    (Aug: none posted) + remaining scheduled August buys — the statement
    paid in September is August's card activity (wiring corrected
    2026-09-18). The 6919.35 Hello Fresh envelope dated 2026-08-31
    (after the frozen today 2026-08-30) carries the projection.
    """
    monkeypatch.setattr(storage, "PRIVATE_DATA_DIR", tmp_path)
    aug = {
        "schema_version": 4,
        "month": "2026-08",
        "month_label": "August 2026",
        "partners": [
            {
                "partner": "Fixture A",
                "salary": 48111,
                "bills": 20631,
                "savings_balance": 18838,
                "savings_delta": -12902.95,
            }
        ],
    }
    (tmp_path / "bills_dashboard_2026-08.json").write_text(json.dumps(aug))
    # Sep 2026 events on FxA Check (1100001): salary 48111 + 5 bills 20631.
    events: list[dict] = []
    bank = [
        ("2026-09-15", -15000.0),  # Mortgage
        ("2026-09-15", -2000.0),  # Mortgage
        ("2026-09-15", 48111.0),  # Salary
        ("2026-09-17", -608.0),  # Electricity
        ("2026-09-20", -2790.0),  # Home Maintenance
        ("2026-09-20", -233.0),  # Insurance
    ]
    for i, (d, amt) in enumerate(bank):
        is_salary = amt > 0
        events.append(
            {
                "id": f"bank-{i}",
                "date": d,
                "amount": amt,
                "transaction_account": {"id": 1100001, "type": "bank"},
                "category": {
                    "id": 2100013 if is_salary else 2100003,
                    "is_transfer": False,
                },
            }
        )
    # m+1 estimate = posted-so-far (Aug: none) + remaining scheduled
    # August buys. The 6919.35 CC-buy envelope on 2026-08-31 (after
    # the frozen today 2026-08-30) is the estimate.
    prior_events = [
        {
            "id": "cc-buy-1",
            "date": "2026-08-31",
            "amount": -6919.35,
            "transaction_account": {"id": 1100003, "type": "credits"},
            "category": {"id": 2100003, "title": "Hello Fresh", "is_transfer": False},
        }
    ]
    snapshot = build_bills_snapshot(
        month="2026-09",
        events=events,
        transactions=[],
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        prior_events=prior_events,
        live_combined=None,
        deltas_per_month=None,
        today=PINNED_NOW,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    # Pre-fix: 48111 - 20631 = 27480. Post-fix: 48111 - 20631 - 6919.35 = 20560.65.
    assert partner_a["estimated_cc_bill"] == pytest.approx(6919.35, abs=0.01)
    assert partner_a["salary"] == 48111.0
    assert partner_a["bills"] == 20631.0
    # Future: savings_delta is None Ã¢â‚¬â€ the CC-inclusive plan moved to
    # savings_planned.
    assert partner_a["savings_delta"] is None
    assert partner_a["savings_planned"] == pytest.approx(20560.65, abs=0.01)
    # Contract: savings_planned == net for future month.
    assert partner_a["savings_planned"] == pytest.approx(partner_a["net"], abs=0.01)


def test_build_bills_snapshot_current_savings_delta_includes_cc_bill():
    """Current-month savings plan must include the CC bill in the subtrahend.

    CC spend is real money out the door, even though it hits the card
    not the checking account. Without it, the formula silently double-
    counts: salary - bills overstates cash saved because the CC bill
    gets spent later in the month.

    Contract: savings_planned = salary - (bills + estimated_cc_bill) for
    current month Ã¢â‚¬â€ estimated being the m-1 (July) proxy here, the
    statement paid this month. Same as `net` (compute_net = salary -
    bills - cc).
    """
    # Set up: current month has salary + bills events on Fixture A's
    # checking; July posted CC spend on his CC account feeds the m-1
    # estimate proxy (800).
    prior_txns = [
        # 800 in July posted CC charges on FxA CC (1100003).
        {
            "amount": -800,
            "status": "posted",
            "transaction_account": {"id": 1100003, "type": "credits"},
        },
    ]
    events = [
        {
            "id": "sal-1",
            "date": "2026-08-25",
            "amount": 42000,
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100013, "is_transfer": False},
        },
        {
            "id": "bill-1",
            "date": "2026-08-10",
            "amount": -15000,
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100003, "is_transfer": False},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-08",  # current
        events=events,
        transactions=[],
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        prior_transactions=prior_txns,
        prior_events=[],
        live_combined=None,
        deltas_per_month=None,
        today=PINNED_NOW,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    # salary (42000) - bills (15000) - cc_bill (800 m-1 proxy) = 26200.
    # The naive salary-bills = 27000 (off by the 800 CC bill).
    assert partner_a["estimated_cc_bill"] == 800
    # savings_planned carries the event-plan formula.
    assert partner_a["savings_planned"] == 26200
    # savings_delta is actual-so-far: no anchor here Ã¢â€ â€™ honest None.
    assert partner_a["savings_delta"] is None
    # Equals net for current month: salary - bills - cc_bill.
    assert partner_a["savings_planned"] == partner_a["net"]


def test_build_bills_snapshot_current_savings_delta_matches_net_partner_a_august():
    """Fixture A August 2026 fixture: savings_delta must equal `net`.

    Locks the production number Ã¢â‚¬â€ `-12902.95` for Fixture A. Pre-fix
    gave 27480 (salary - bills only), which overstates saved cash by
    the full estimated_cc_bill (40382.95). After: savings_delta == net
    for the current month, every time.

    Uses the same fixture shape as the on-disk August snapshot so any
    drift in the real data surfaces here.
    """
    # Aug 2026 events on FxA Check (1100001) + FxA CC (1100003).
    # Salary 48111 + 5 mortgage/utility bills = 20631 + 6 planned buys
    # = 5786. Matches the on-disk August snapshot's salary/bills/buys.
    bank_events = [
        ("2026-08-15", -15000.0),  # Mortgage
        ("2026-08-15", -2000.0),  # Mortgage
        ("2026-08-15", 48111.0),  # Salary
        ("2026-08-17", -608.0),  # Electricity
        ("2026-08-20", -2790.0),  # Home Maintenance
        ("2026-08-20", -233.0),  # Insurance
    ]
    cc_buys = [
        ("2026-08-01", -218.0),  # Memberships (Household)
        ("2026-08-05", -1300.0),  # Hello Fresh
        ("2026-08-12", -1300.0),  # Hello Fresh
        ("2026-08-18", -269.0),  # Memberships (Household)
        ("2026-08-19", -1300.0),  # Hello Fresh
        ("2026-08-25", -99.0),  # Memberships
        ("2026-08-26", -1300.0),  # Hello Fresh
    ]
    events: list[dict] = []
    for i, (d, amt) in enumerate(bank_events):
        is_salary = amt > 0
        events.append(
            {
                "id": f"bank-{i}",
                "date": d,
                "amount": amt,
                "transaction_account": {"id": 1100001, "type": "bank"},
                "category": {
                    "id": 2100013 if is_salary else 2100003,
                    "title": "Salary (Fixture A)" if is_salary else "Bills",
                    "is_transfer": False,
                },
            }
        )
    for i, (d, amt) in enumerate(cc_buys):
        events.append(
            {
                "id": f"cc-{i}",
                "date": d,
                "amount": amt,
                "transaction_account": {"id": 1100003, "type": "credits"},
                "category": {
                    "id": 2100003,
                    "title": (
                        "Memberships"
                        if "Membership" in str(amt) or amt > -1000
                        else "Hello Fresh"
                    ),
                    "is_transfer": False,
                },
            }
        )
    # July (m-1) posted CC spend on FxA CC: 40382.95 Ã¢â€ â€™ the current-month
    # estimate proxy (the statement being paid in August). No prior events
    # Ã¢â€ â€™ the m-1 max formula returns the plain posted sum.
    prior_txns = [
        {
            "amount": -40382.95,
            "status": "posted",
            "transaction_account": {"id": 1100003, "type": "credits"},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-08",
        events=events,
        transactions=[],
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        prior_transactions=prior_txns,
        prior_events=[],
        live_combined=None,
        deltas_per_month=None,
        today=PINNED_NOW,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    # Lock the production number. Pre-fix: 48111 - 20631 = 27480.
    # Post-fix: 48111 - 20631 - 40382.95 = -12902.95.
    assert partner_a["estimated_cc_bill"] == 40382.95
    assert partner_a["salary"] == 48111.0
    assert partner_a["bills"] == 20631.0
    # The CC-inclusive plan moved to savings_planned; savings_delta is
    # actual-so-far (None here Ã¢â‚¬â€ no anchor in this standalone call).
    assert partner_a["savings_planned"] == pytest.approx(-12902.95, abs=0.01)
    assert partner_a["net"] == pytest.approx(-12902.95, abs=0.01)
    assert partner_a["savings_delta"] is None
    # Contract: savings_planned == net for the current month.
    assert partner_a["savings_planned"] == pytest.approx(partner_a["net"], abs=0.01)


def test_build_bills_snapshot_past_last_month_uses_real_cash_flow(
    tmp_path, monkeypatch
):
    """Last past month Ã¢â‚¬â€ back-walk from live anchor, delta savings-only.

    Balance: anchor 15000 - delta 3000 = 12000 (back-walk from the chain's
    combined-flow delta Ã¢â‚¬â€ internal plumbing, keeps the invariant). Delta
    FIELD: sum(this-month posted txns on partner SAVINGS accounts only)
    = -2000 (the +5000 checking txn never counts Ã¢â‚¬â€ user decision
    2026-08-28). Independent of any later-month data Ã¢â€ â€™ works for the
    last past month.
    """
    monkeypatch.setattr(storage, "PRIVATE_DATA_DIR", tmp_path)
    # No next-month snapshot on disk Ã¢â€ â€™ old fallback path triggered.
    # Live current_balance (15000) would be polluted; new formula uses
    # posted txns only.

    mappings = {
        "partners": {
            "partner_a": {
                "label": "Fixture A",
                "savings_category_id": 2100014,
            }
        },
        "accounts": {
            "1100001": {
                "name": "FxA Check",
                "partner_id": "partner_a",
                "type": "checking",
                "excluded": False,
            },
            "1100002": {
                "name": "FxA Savings",
                "partner_id": "partner_a",
                "type": "savings",
                "excluded": False,
            },
        },
    }
    catalog = [
        {"id": 1100001, "current_balance": 7000, "starting_balance": 0},
        {"id": 1100002, "current_balance": 8000, "starting_balance": 0},
    ]
    posted_txns = [
        {
            "amount": 5000,
            "date": "2026-07-10",
            "status": "posted",
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100003, "is_transfer": False},
        },
        {
            "amount": -2000,
            "date": "2026-07-15",
            "status": "posted",
            "transaction_account": {"id": 1100002, "type": "savings"},
            "category": {"id": 2100014, "is_transfer": False},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-07",  # past (current local = 2026-08)
        events=[],
        transactions=posted_txns,
        account_mappings=mappings,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=catalog,
        live_combined={"partner_a": 15000.0},
        deltas_per_month={"partner_a": {"2026-07": 3000.0}},
    )
    partner_a = snapshot["partners"][0]
    # Back-walk: anchor (15000) - delta (3000) = 12000. The chain delta
    # (3000, combined bills+savings) stays internal Ã¢â‚¬â€ the displayed
    # savings_delta is savings-accounts-only.
    assert partner_a["savings_balance"] == 12000
    # savings_delta = sum(2026-07 posted txns on partner SAVINGS) = -2000.
    # The +5000 checking txn is checking noise Ã¢â‚¬â€ never counts.
    assert partner_a["savings_delta"] == -2000


def test_build_bills_snapshot_past_delta_excludes_cc_paydown():
    """Past-month savings_delta must EXCLUDE CC-paydown posted txns.

    CC paydown is checking noise (cash out of bills to the card) Ã¢â‚¬â€ never
    counts toward savings (user decision 2026-08-28). savings_delta sums
    posted txns on the partner's SAVINGS accounts only; the paydown sits
    on the bills account Ã¢â€ â€™ excluded.
    """
    mappings = {
        "partners": {
            "partner_a": {
                "label": "Fixture A",
                "savings_category_id": 2100014,
            }
        },
        "accounts": {
            "1100001": {  # FxA Check
                "name": "FxA Check",
                "partner_id": "partner_a",
                "type": "checking",
                "excluded": False,
            },
            "1100002": {  # FxA Savings
                "name": "FxA Savings",
                "partner_id": "partner_a",
                "type": "savings",
                "excluded": False,
            },
        },
    }
    catalog = [
        {"id": 1100001, "current_balance": 10000, "starting_balance": 0},
        {"id": 1100002, "current_balance": 5000, "starting_balance": 0},
    ]
    # One CC-paydown posted txn on the bills account: -5000.
    # Category id 2100011 = "CC Payment (paired)" Ã¢â‚¬â€ the bills-side
    # of a CC paydown (cash out of checking to pay the card).
    posted_txns = [
        {
            "amount": -5000,
            "date": "2026-06-20",
            "status": "posted",
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {
                "id": 2100011,
                "title": "CC Payment (paired)",
                "is_transfer": False,
            },
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-06",
        events=[],
        transactions=posted_txns,
        account_mappings=mappings,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=catalog,
        live_combined=None,
        deltas_per_month=None,
    )
    partner_a = snapshot["partners"][0]
    # savings_delta sums posted txns on partner SAVINGS accounts only.
    # The CC-paydown sits on the bills account Ã¢â€ â€™ excluded Ã¢â€ â€™ 0.0 (nothing
    # saved). Old combined-flow semantics gave -5000 Ã¢â‚¬â€ that was the leak.
    assert partner_a["savings_delta"] == 0.0


# Append-only file Ã¢â‚¬â€ concatenated onto test_builder.py via a script.


def test_build_bills_snapshot_current_cc_payment_on_checking_with_is_transfer_still_overrides():
    """Finding 2 regression: CC-paydown on checking acct with is_transfer=True.

    Classifier drops checking-account CC-paydown events as "excluded" (the
    is_transfer rule), so the old override (which read `classified`) would
    miss the very case it is meant to catch Ã¢â‚¬â€ cash leaving the checking
    account to pay down the card. The new override walks raw `events` and
    filters on (account belongs to partner) + (category.id == cat_id),
    so it fires even when the classifier would have excluded the event.

    Fixture: Fixture A August 2026 (current), CC-paydown event on FxA
    Check (1100001) with is_transfer=True. The m-1 (July) proxy estimate
    stays at 40382.95; the override only sets real_cc_bill = 12500, and
    savings_planned picks real over estimated.
    """
    events = [
        {
            "id": "sal-1",
            "date": "2026-08-25",
            "amount": 48111.0,
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100013, "is_transfer": False},
        },
        {
            "id": "bill-1",
            "date": "2026-08-15",
            "amount": -15000.0,
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100003, "is_transfer": False},
        },
        {
            "id": "cc-pay-1",
            "date": "2026-08-20",
            "amount": -12500,
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {
                "id": 2100011,
                "title": "CC Payment (paired)",
                "is_transfer": True,
            },
        },
    ]
    prior_txns = [
        {
            "amount": -40382.95,
            "status": "posted",
            "transaction_account": {"id": 1100003, "type": "credits"},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-08",
        events=events,
        transactions=[],
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        prior_transactions=prior_txns,
        prior_events=[],
        live_combined=None,
        deltas_per_month=None,
        today=PINNED_NOW,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    # estimated = July (m-1) proxy; the paydown override sets real only.
    assert partner_a["estimated_cc_bill"] == 40382.95
    assert partner_a["real_cc_bill"] == 12500
    # savings_planned picks real: 48111 - 15000 - 12500 = 20611.
    assert partner_a["savings_planned"] == pytest.approx(20611, abs=0.01)
    # savings_delta is actual-so-far: no anchor here Ã¢â€ â€™ honest None.
    assert partner_a["savings_delta"] is None
    assert partner_a["bills"] == 15000
    assert partner_a["planned_cc_buys"] == 0


def test_build_bills_snapshot_current_cc_payment_zero_amount_does_not_override():
    """Finding 2 edge case: CC-paydown event with amount=0 must not override.

    Override contract: `_cc_payment_event_sum` returns the sum of abs
    amounts. If that sum is 0, the override does not fire: the estimate
    stays the m-1 (July) proxy and real_cc_bill stays None. Real shape:
    PS can emit a 0-amount event for a planned/cleared paydown (the bank
    booked it as 0 pending reconciliation). Should not be treated as
    "CC paid in full this month".

    Fixture: Fixture A August 2026 (current), one 0-amount CC-pay event
    on FxA Check. 800 July posted spend on FxA CC Ã¢â€ â€™ est_cc_bill = 800.
    """
    events = [
        {
            "id": "sal-1",
            "date": "2026-08-25",
            "amount": 42000,
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100013, "is_transfer": False},
        },
        {
            "id": "bill-1",
            "date": "2026-08-10",
            "amount": -15000,
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100003, "is_transfer": False},
        },
        {
            "id": "cc-pay-zero",
            "date": "2026-08-20",
            "amount": 0,
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {
                "id": 2100011,
                "title": "CC Payment (paired)",
                "is_transfer": True,
            },
        },
    ]
    prior_txns = [
        {
            "amount": -800,
            "status": "posted",
            "transaction_account": {"id": 1100003, "type": "credits"},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-08",
        events=events,
        transactions=[],
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        prior_transactions=prior_txns,
        prior_events=[],
        live_combined=None,
        deltas_per_month=None,
        today=PINNED_NOW,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    assert partner_a["estimated_cc_bill"] == 800
    assert partner_a["real_cc_bill"] is None
    assert partner_a["savings_planned"] == 26200
    # savings_delta is actual-so-far: no anchor here Ã¢â€ â€™ honest None.
    assert partner_a["savings_delta"] is None


# -- savings anchor (live combined) + back-walk chain ------------------------


def test_build_bills_snapshot_past_savings_balance_back_walk_from_anchor(
    tmp_path, monkeypatch
):
    """Past m balance = anchor Ã¢Ë†â€™ ÃŽÂ£ delta(m+1..current).

    Anchor 20000, deltas: 2026-07=+5000, 2026-06=-3000.
      balance[2026-07] = 20000 - 5000 = 15000
      balance[2026-06] = 15000 - (-3000) = 18000
    """
    monkeypatch.setattr(storage, "PRIVATE_DATA_DIR", tmp_path)
    deltas = {"partner_a": {"2026-07": 5000.0, "2026-06": -3000.0}, "partner_b": {}}
    live = {"partner_a": 20000.0, "partner_b": 66000.0}

    snap_jul = build_bills_snapshot(
        month="2026-07",
        events=[],
        transactions=[],
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined=live,
        deltas_per_month=deltas,
    )
    snap_jun = build_bills_snapshot(
        month="2026-06",
        events=[],
        transactions=[],
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined=live,
        deltas_per_month=deltas,
    )
    fxa_jul = next(p for p in snap_jul["partners"] if p["partner"] == "Fixture A")
    fxa_jun = next(p for p in snap_jun["partners"] if p["partner"] == "Fixture A")
    assert fxa_jul["savings_balance"] == pytest.approx(15000.0)
    assert fxa_jun["savings_balance"] == pytest.approx(18000.0)
    # invariant both directions: balance[m+1] - balance[m] == delta[m]
    assert fxa_jul["savings_balance"] - fxa_jun["savings_balance"] == pytest.approx(
        deltas["partner_a"]["2026-06"], abs=0.01
    )
    assert 20000.0 - fxa_jul["savings_balance"] == pytest.approx(
        deltas["partner_a"]["2026-07"], abs=0.01
    )


def test_build_bills_snapshot_current_savings_balance_equals_live_combined():
    """Current savings_balance = sum of current_balance for bills + savings.

    ACCOUNT_CATALOG: FxA Check 9886.31 + FxA Savings 32000 = 41886.31.
    """
    from budget_api.services.bills_derivations import compute_savings_balance_current

    live = {
        pid: compute_savings_balance_current(pid, ACCOUNT_MAPPINGS, ACCOUNT_CATALOG)
        for pid in ("partner_a", "partner_b")
    }
    snapshot = build_bills_snapshot(
        month="2026-08",  # current
        events=[],
        transactions=[],
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined=live,
        deltas_per_month={"partner_a": {}, "partner_b": {}},
        today=PINNED_NOW,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    partner_b = next(p for p in snapshot["partners"] if p["partner"] == "Fixture B")
    assert partner_a["savings_balance"] == pytest.approx(9886.31 + 32000)
    assert partner_b["savings_balance"] == pytest.approx(5000 + 61000)


def test_build_bills_snapshot_falls_back_to_lag_when_live_unavailable(
    tmp_path, monkeypatch
):
    """Live missing for partner Ã¢â€ â€™ current month uses lag + warning."""
    monkeypatch.setattr(storage, "PRIVATE_DATA_DIR", tmp_path)
    prior_snap = {
        "schema_version": 4,
        "month": "2026-07",
        "month_label": "July 2026",
        "partners": [
            {
                "partner": "Fixture A",
                "salary": 0,
                "bills": 0,
                "savings_balance": 9917,
                "savings_delta": 8921,
            }
        ],
    }
    (tmp_path / "bills_dashboard_2026-07.json").write_text(json.dumps(prior_snap))

    warnings: list[str] = []
    snapshot = build_bills_snapshot(
        month="2026-08",  # current
        events=[],
        transactions=[],
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        warnings=warnings,
        live_combined={"partner_a": None, "partner_b": None},
        deltas_per_month={"partner_a": {}, "partner_b": {}},
        today=PINNED_NOW,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    # lag: 9917 + 8921 = 18838
    assert partner_a["savings_balance"] == 18838
    assert any("live balance unavailable" in w for w in warnings)


def test_build_bills_chain_full_re_sync_consistent(tmp_path, monkeypatch):
    """5-month chain (2 past + current + 2 future) Ã¢â‚¬â€ internally consistent.

    Fixture A deltas: 2026-06 = +3000, 2026-07 = -2000.
    Live anchor = 9886.31 + 32000 = 41886.31.
      balance[2026-07] = 41886.31 + 2000 = 43886.31
      balance[2026-06] = 43886.31 - 3000 = 40886.31
      balance[2026-08] = 41886.31 (anchor)
      balance[2026-09] = 41886.31 + delta[2026-08] (lag, in-memory)
      balance[2026-10] = balance[2026-09] + delta[2026-09]
    Invariant: balance[m+1] - balance[m] Ã¢â€°Ë† savings_delta[m] for all pairs.
    """
    monkeypatch.setattr(storage, "PRIVATE_DATA_DIR", tmp_path)
    months = ["2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]
    events_per_month: dict[str, list[dict]] = {m: [] for m in months}
    transactions_per_month: dict[str, list[dict]] = {m: [] for m in months}
    transactions_per_month["2026-06"] = [
        {
            "amount": 3000,
            "date": "2026-06-15",
            "status": "posted",
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100003, "is_transfer": False},
        },
    ]
    transactions_per_month["2026-07"] = [
        {
            "amount": -2000,
            "date": "2026-07-10",
            "status": "posted",
            "transaction_account": {"id": 1100002, "type": "savings"},
            "category": {"id": 2100003, "is_transfer": False},
        },
    ]

    from budget_api.services.bills_builder import build_bills_chain

    warnings: list[str] = []
    snapshots = build_bills_chain(
        months=months,
        events_per_month=events_per_month,
        transactions_per_month=transactions_per_month,
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        warnings=warnings,
    )
    assert sorted(snapshots) == months

    def bal(month: str, partner: str) -> float:
        p = next(x for x in snapshots[month]["partners"] if x["partner"] == partner)
        return p["savings_balance"]

    def delta(month: str, partner: str) -> float:
        p = next(x for x in snapshots[month]["partners"] if x["partner"] == partner)
        return p["savings_delta"]

    # anchor: current month = live combined
    assert bal("2026-08", "Fixture A") == pytest.approx(41886.31, abs=0.01)
    assert bal("2026-08", "Fixture B") == pytest.approx(66000.0, abs=0.01)
    # back-walk
    assert bal("2026-07", "Fixture A") == pytest.approx(43886.31, abs=0.01)
    assert bal("2026-06", "Fixture A") == pytest.approx(40886.31, abs=0.01)
    # invariant across every adjacent pair, both partners.
    # balance[m+1] - balance[m] == delta[m] when delta[m] is real.
    # EXCEPTION (2026-08-28): the DISPLAYED savings_delta is savings-only
    # flow, but the chain invariant holds on the CHAIN's COMBINED
    # bills+savings delta (internal plumbing Ã¢â‚¬â€ combined balances demand
    # combined flow). So for past pairs the expected flow is the combined
    # cash flow (recomputed here exactly like build_bills_chain does);
    # for the pair into the current month the same combined delta is what
    # the back-walk consumed (balance[cur] = anchor). Future months still
    # lag off the prior month's delta/planned (displayed values). Pinned
    # explicitly by test_chain_back_walk_deltas_stay_combined.
    months_set = set(months)

    def combined_delta(month: str, partner_id: str) -> float:
        bills_id = str(_bills_account_id(ACCOUNT_MAPPINGS, partner_id))
        sav_ids = set(map(str, _savings_account_ids(ACCOUNT_MAPPINGS, partner_id)))
        posted = _filter_posted(transactions_per_month[month])
        return _past_month_cash_flow(posted, month, {bills_id, *sav_ids})

    current = _current_month()
    for partner, partner_id in (("Fixture A", "partner_a"), ("Fixture B", "partner_b")):
        for m, m_next in zip(months, months[1:]):
            p = next(x for x in snapshots[m]["partners"] if x["partner"] == partner)
            if m in months_set and m < current:
                # Past month: chain invariant = combined bills+savings flow.
                flow = combined_delta(m, partner_id)
            else:
                # Current/future lag pair: displayed delta, else planned.
                flow = (
                    p["savings_delta"]
                    if p["savings_delta"] is not None
                    else p["savings_planned"]
                )
            assert bal(m_next, partner) - bal(m, partner) == pytest.approx(
                flow, abs=0.01
            ), f"{partner} {m}->{m_next}"


# -- everyday_budget (F2 Ã‚Â§8) ---------------------------------------------------
# everyday_budget(m) = salary(m+1) Ã¢Ë†â€™ bills(m+1) Ã¢Ë†â€™ scheduledCcBuys(m), per
# partner (buys = month m's own envelopes Ã¢â‚¬â€ paid with m+1's income).
# None when m+1 data missing (last window month / standalone call).


def _next_month_events():
    """m+1 events: salary 42000 + rent 15500 (Fixture A checking), laptop 5000
    (Fixture A CC buy). Fixture B: nothing."""
    return [
        {
            "id": "nxt-1",
            "date": "2026-08-25",
            "note": "Salary",
            "category": {"id": 2100013, "title": "Income", "is_transfer": False},
            "transaction_account": {"id": 1100001, "type": "bank"},
            "amount": 42000,
        },
        {
            "id": "nxt-2",
            "date": "2026-08-10",
            "note": "Rent",
            "category": {"id": 2100003, "title": "Common", "is_transfer": False},
            "transaction_account": {"id": 1100001, "type": "bank"},
            "amount": -15500,
        },
        {
            "id": "nxt-3",
            "date": "2026-08-15",
            "note": "New laptop",
            "category": {"id": 2100003, "title": "Electronics", "is_transfer": False},
            "transaction_account": {"id": 1100003, "type": "credits"},
            "amount": -5000,
        },
    ]


def test_build_bills_snapshot_everyday_budget_from_next_month():
    """next_events given Ã¢â€ â€™ salary(m+1) Ã¢Ë†â€™ bills(m+1) Ã¢Ë†â€™ ccBuys(m+1), exact."""
    snapshot = build_bills_snapshot(
        month="2026-07",
        events=_ps_events(),
        transactions=_ps_transactions(),
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        next_events=_next_month_events(),
        live_combined=None,
        deltas_per_month=None,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    partner_b = next(p for p in snapshot["partners"] if p["partner"] == "Fixture B")
    # 42000 - 15500 - 5000
    assert partner_a["everyday_budget"] == 21500
    # Fixture B has no m+1 events for her accounts Ã¢â€ â€™ 0.0, not None.
    assert partner_b["everyday_budget"] == 0.0


def test_build_bills_snapshot_everyday_budget_none_without_next_events():
    """Last window month / standalone call Ã¢â€ â€™ everyday_budget is None."""
    snapshot = build_bills_snapshot(
        month="2026-07",
        events=_ps_events(),
        transactions=_ps_transactions(),
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined=None,
        deltas_per_month=None,
    )
    for partner in snapshot["partners"]:
        assert partner["everyday_budget"] is None


def test_build_bills_snapshot_everyday_budget_no_cc_payment_category_configured():
    """cc_payment_cat_id None (catalog lacks the category) must NOT empty the
    m+1 events Ã¢â‚¬â€ PR62 review: the old conjunction dropped every event, making
    the budget salary-only."""
    import copy

    no_ccpay_catalog = [
        c for c in copy.deepcopy(CATEGORY_CATALOG) if "CC Payment" not in c.get("title", "")
    ]
    for c in no_ccpay_catalog:
        c["children"] = [
            ch for ch in c.get("children", []) if "CC Payment" not in ch.get("title", "")
        ]
    snapshot = build_bills_snapshot(
        month="2026-07",
        events=_ps_events(),
        transactions=_ps_transactions(),
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=no_ccpay_catalog,
        account_catalog=ACCOUNT_CATALOG,
        next_events=_next_month_events(),
        live_combined=None,
        deltas_per_month=None,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    # All m+1 events kept: 42000 - 15500 - 5000, same as the exclusion test.
    assert partner_a["everyday_budget"] == 21500


def test_build_bills_snapshot_everyday_budget_excludes_cc_payment_events():
    """m+1 CC-payment event must not double-count into bills/ccBuys terms."""
    next_events = _next_month_events() + [
        {
            "id": "nxt-4",
            "date": "2026-08-28",
            "note": "CC paydown",
            "category": {
                "id": 2100011,
                "title": "CC Payment (paired)",
                "is_transfer": True,
            },
            "transaction_account": {"id": 1100003, "type": "credits"},
            "amount": -9800,
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-07",
        events=_ps_events(),
        transactions=_ps_transactions(),
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        next_events=next_events,
        live_combined=None,
        deltas_per_month=None,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    # CC-payment event excluded Ã¢â€ â€™ same as without it: 42000 - 15500 - 5000.
    assert partner_a["everyday_budget"] == 21500


def test_build_bills_snapshot_everyday_budget_zero_when_next_month_empty():
    """m+1 exists but holds no events Ã¢â€ â€™ 0 Ã¢Ë†â€™ 0 Ã¢Ë†â€™ ccBuys(m). The buys term is
    month m's own envelopes (5,000 laptop), so Ã¢Ë†â€™5,000 Ã¢â‚¬â€ not a null gate."""
    snapshot = build_bills_snapshot(
        month="2026-07",
        events=_ps_events(),
        transactions=_ps_transactions(),
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        next_events=[],
        live_combined=None,
        deltas_per_month=None,
    )
    for partner in snapshot["partners"]:
        if partner["partner"] == "Fixture A":
            # 0 salary(m+1) Ã¢Ë†â€™ 0 bills(m+1) Ã¢Ë†â€™ 5,000 buys(m).
            assert partner["everyday_budget"] == -5000
        else:
            assert partner["everyday_budget"] == 0.0


def test_build_bills_snapshot_everyday_budget_negative_passes_through():
    """No clamping: salary(m+1) < bills(m+1) + ccBuys(m+1) Ã¢â€ â€™ negative as-is."""
    snapshot = build_bills_snapshot(
        month="2026-07",
        events=_ps_events(),
        transactions=_ps_transactions(),
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        next_events=[
            {
                "id": "nxt-neg-1",
                "date": "2026-08-25",
                "note": "Salary",
                "category": {"id": 2100013, "title": "Income", "is_transfer": False},
                "transaction_account": {"id": 1100001, "type": "bank"},
                "amount": 10000,
            },
        ]
        + _next_month_events()[1:],  # rent 15500 + laptop 5000, no extra salary
        live_combined=None,
        deltas_per_month=None,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    # 10000 - 15500 - 5000 = -10500, returned unclamped.
    assert partner_a["everyday_budget"] == -10500


def test_build_bills_chain_everyday_budget_plumbs_next_month():
    """Chain: each month's everyday_budget reads m+1's events; last = None."""
    from budget_api.services.bills_builder import build_bills_chain

    months = ["2026-06", "2026-07", "2026-08"]
    events_per_month: dict[str, list[dict]] = {m: [] for m in months}
    transactions_per_month: dict[str, list[dict]] = {m: [] for m in months}
    events_per_month["2026-08"] = _next_month_events()

    snapshots = build_bills_chain(
        months=months,
        events_per_month=events_per_month,
        transactions_per_month=transactions_per_month,
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        warnings=[],
    )

    def budget(month: str, partner: str):
        p = next(x for x in snapshots[month]["partners"] if x["partner"] == partner)
        return p["everyday_budget"]

    # 2026-07's budget: salary(08) 42000 Ã¢Ë†â€™ bills(08) 15500 Ã¢Ë†â€™ buys(07) 0
    # (Jul events are empty here Ã¢â‚¬â€ buys come from month m itself).
    assert budget("2026-07", "Fixture A") == 26500
    # 2026-06: next-month (07) events empty and Jun buys 0 Ã¢â€ â€™ 0.0.
    assert budget("2026-06", "Fixture A") == 0.0
    # Last window month Ã¢â€ â€™ None.
    assert budget("2026-08", "Fixture A") is None


# -- savings_planned vs savings_delta (F2 Ã‚Â§13 revised) ------------------------
# savings_planned = salary - bills - cc_bill (static plan, all month kinds).
# savings_delta = actual-so-far, SAVINGS-ACCOUNTS-ONLY posted flow (user
# decision 2026-08-28): current AND past. Future: None. The chain's
# internal back-walk deltas stay combined bills+savings (invariant).


def test_savings_planned_current_month_delta_savings_accounts_only(tmp_path, monkeypatch):
    """Current month, chain kwargs: delta = savings-accounts-only posted flow.

    Fixture A: anchor 41886.31 (catalog live combined), Jul chain delta
    -2000 Ã¢â€ â€™ balance[Jul] = 43886.31 (back-walk unchanged Ã¢â‚¬â€ chain deltas
    stay combined). savings_delta = sum(2026-08 posted txns on FxA
    Savings) = -2000. Chain invariant: balance[Aug] = 41886.31 (anchor)
    = balance[Jul] + delta[Aug] = 43886.31 + (-2000).
    """
    monkeypatch.setattr(storage, "PRIVATE_DATA_DIR", tmp_path)
    # In-month savings-account txn: cash pulled from savings (-2000).
    posted_txns = [
        {
            "amount": -2000,
            "date": "2026-08-10",
            "status": "posted",
            "transaction_account": {"id": 1100002, "type": "savings"},
            "category": {"id": 2100014, "is_transfer": False},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-08",  # current
        events=[],
        transactions=posted_txns,
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined={"partner_a": 41886.31, "partner_b": 66000.0},
        deltas_per_month={"partner_a": {"2026-07": -2000.0}, "partner_b": {"2026-07": 0.0}},
        today=PINNED_NOW,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    # savings-only posted flow Ã¢â‚¬â€ NOT anchor-minus-month-start (old rule).
    assert partner_a["savings_delta"] == pytest.approx(-2000.0, abs=0.01)
    # Chain invariant restored at current month.
    balance_at_month_start = 41886.31 - (-2000.0)  # back-walked end of July
    assert partner_a["savings_balance"] == pytest.approx(
        balance_at_month_start + partner_a["savings_delta"], abs=0.01
    )


def test_savings_planned_current_month_chain_kwargs_missing_delta_null_with_warning(
    tmp_path, monkeypatch
):
    """Current month, chain kwargs absent: delta None + warning; planned still right."""
    monkeypatch.setattr(storage, "PRIVATE_DATA_DIR", tmp_path)
    warnings: list[str] = []
    # Keep the pin on the savings chain, not on CC math this test doesn't
    # own: strip the shared fixture's CC-buy event (planned_cc_buys noise)
    # and its posted 5,000 CC-paydown (real current-month truth now Ã¢â‚¬â€ it
    # would replace the estimate in savings_planned via real ?? est).
    events_no_buys = [
        e for e in _ps_events() if e["transaction_account"]["type"] != "credits"
    ]
    txns_no_cc_pay = [
        t
        for t in _ps_transactions()
        if (t.get("category") or {}).get("id") != 2100011
    ]
    snapshot = build_bills_snapshot(
        month="2026-08",  # current
        events=events_no_buys,
        transactions=txns_no_cc_pay,
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        warnings=warnings,
        live_combined=None,
        deltas_per_month=None,
        today=PINNED_NOW,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    # Honest null Ã¢â‚¬â€ never a silent 0, never plan posing as actual.
    assert partner_a["savings_delta"] is None
    assert any(
        "savings_delta unavailable" in w and "Fixture A" in w for w in warnings
    )
    # Plan unaffected: salary (42000) - bills (15500) - est_cc_bill (0 Ã¢â‚¬â€
    # no paydown posted and no July/m-1 prior data in this fixture; the
    # m-1 proxy is the current-month estimate now).
    assert partner_a["savings_planned"] == pytest.approx(26500, abs=0.01)


def test_savings_planned_future_month_delta_null(tmp_path, monkeypatch):
    """Future month: delta None; planned = salary - bills - est_cc_bill."""
    monkeypatch.setattr(storage, "PRIVATE_DATA_DIR", tmp_path)
    # Prior-month (Aug) CC spend Ã¢â€ â€™ est_cc_bill = 500 for September.
    prior_txns = [
        {
            "amount": -500,
            "status": "posted",
            "transaction_account": {"id": 1100003, "type": "credits"},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-09",  # future
        events=_ps_events(),
        transactions=_ps_transactions(),
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        prior_transactions=prior_txns,
        prior_events=[],
        live_combined=None,
        deltas_per_month=None,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    assert partner_a["savings_delta"] is None
    # All-mÃ¢Ë†â€™1 formula: Aug (prior_events=[]) has no envelopes; real Aug CC
    # spend = 500 Ã¢â€ â€™ est 500. savings_planned = 42000 Ã¢Ë†â€™ 15500 Ã¢Ë†â€™ 500 = 26000.
    assert partner_a["estimated_cc_bill"] == pytest.approx(500, abs=0.01)
    assert partner_a["savings_planned"] == pytest.approx(26000, abs=0.01)


def test_savings_planned_past_month_uses_real_cc_bill(tmp_path, monkeypatch):
    """Past month: planned = salary - bills - real_cc_bill; delta savings-only.

    Posted July txns: CC-side paydown -3000 on FxA CC Ã¢â€ â€™ real_cc_bill = 3000.
    Fixture A's savings account (1100002) moved +26500 during July (salary
    in, then leftover transferred to savings). The +42000/-15500 checking
    activity is checking noise Ã¢â‚¬â€ never counts (user decision 2026-08-28).
    Events: salary 42000 + bill 15500 on checking.
    planned = 42000 - 15500 - 3000 = 23500.
    delta = savings-accounts-only posted flow = 26500.
    """
    monkeypatch.setattr(storage, "PRIVATE_DATA_DIR", tmp_path)
    events = [
        {
            "id": "sal-jul",
            "date": "2026-07-25",
            "amount": 42000,
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100013, "is_transfer": False},
        },
        {
            "id": "bill-jul",
            "date": "2026-07-10",
            "amount": -15500,
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100003, "is_transfer": False},
        },
    ]
    posted_txns = [
        # Savings-account flow: salary leftover transferred in.
        {
            "amount": 26500,
            "date": "2026-07-28",
            "status": "posted",
            "transaction_account": {"id": 1100002, "type": "savings"},
            "category": {"id": 2100014, "is_transfer": False},
        },
        # Checking noise Ã¢â‚¬â€ salary in / bills out. Must NOT pollute delta.
        {
            "amount": 42000,
            "date": "2026-07-25",
            "status": "posted",
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100013, "is_transfer": False},
        },
        {
            "amount": -15500,
            "date": "2026-07-10",
            "status": "posted",
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100003, "is_transfer": False},
        },
        {
            "amount": -3000,
            "date": "2026-07-20",
            "status": "posted",
            "transaction_account": {"id": 1100003, "type": "credits"},
            "category": {
                "id": 2100011,
                "title": "CC Payment (paired)",
                "is_transfer": True,
            },
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-07",  # past
        events=events,
        transactions=posted_txns,
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined=None,
        deltas_per_month=None,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    assert partner_a["salary"] == 42000
    assert partner_a["bills"] == 15500
    assert partner_a["real_cc_bill"] == 3000
    assert partner_a["savings_planned"] == pytest.approx(23500, abs=0.01)
    # Past delta: savings-accounts-only posted flow. The checking
    # salary/bills txns are noise Ã¢â‚¬â€ only the +26500 savings transfer counts.
    assert partner_a["savings_delta"] == pytest.approx(26500, abs=0.01)


def test_savings_planned_chain_future_lag_uses_planned(tmp_path, monkeypatch):
    """Chain: future month 1 lags off REAL current delta; month 2+ off planned.

    Fixture A: anchor 41886.31. Jul combined-flow delta +2000 (the chain's
    internal plumbing Ã¢â‚¬â€ one +2000 posted on FxA Savings). Current (Aug)
    savings_delta = savings-only posted flow = 0.0 (no Aug savings txns).
    Sep events salary 10000, bills 4000 Ã¢â€ â€™ planned 6000. Oct no events
    Ã¢â€ â€™ planned 0.
      bal[Jul] = 41886.31 - 2000 = 39886.31  (back-walk, combined delta)
      bal[Aug] = 41886.31 (anchor)
      bal[Sep] = 41886.31 + 0 = 41886.31   (REAL current savings delta)
      bal[Oct] = 41886.31 + 6000 = 47886.31 (prior planned, delta null)
    """
    monkeypatch.setattr(storage, "PRIVATE_DATA_DIR", tmp_path)
    from budget_api.services.bills_builder import build_bills_chain

    months = ["2026-07", "2026-08", "2026-09", "2026-10"]
    events_per_month: dict[str, list[dict]] = {m: [] for m in months}
    transactions_per_month: dict[str, list[dict]] = {m: [] for m in months}
    transactions_per_month["2026-07"] = [
        {
            "amount": 2000,
            "date": "2026-07-10",
            "status": "posted",
            "transaction_account": {"id": 1100002, "type": "savings"},
            "category": {"id": 2100003, "is_transfer": False},
        },
    ]
    events_per_month["2026-09"] = [
        {
            "id": "sal-sep",
            "date": "2026-09-25",
            "amount": 10000,
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100013, "is_transfer": False},
        },
        {
            "id": "bill-sep",
            "date": "2026-09-10",
            "amount": -4000,
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100003, "is_transfer": False},
        },
    ]

    snapshots = build_bills_chain(
        months=months,
        events_per_month=events_per_month,
        transactions_per_month=transactions_per_month,
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        warnings=[],
        today=PINNED_NOW,
    )

    def partner(month: str) -> dict:
        return next(
            x for x in snapshots[month]["partners"] if x["partner"] == "Fixture A"
        )

    aug = partner("2026-08")
    sep = partner("2026-09")
    oct_ = partner("2026-10")
    # Current month: real savings-only delta Ã¢â‚¬â€ no Aug savings txns Ã¢â€ â€™ 0.0.
    # (Old anchor-minus-month-start rule gave +2000 Ã¢â‚¬â€ that was the leak:
    # it equated combined-checking movement with savings growth.)
    assert aug["savings_balance"] == pytest.approx(41886.31, abs=0.01)
    assert aug["savings_delta"] == pytest.approx(0.0, abs=0.01)
    # Future month 1 lags off the REAL current delta.
    assert sep["savings_delta"] is None
    assert sep["savings_planned"] == pytest.approx(6000.0, abs=0.01)
    assert sep["savings_balance"] == pytest.approx(
        aug["savings_balance"] + aug["savings_delta"], abs=0.01
    )
    # Future month 2+ lags off the prior month's PLANNED (delta is null).
    assert oct_["savings_delta"] is None
    assert oct_["savings_planned"] == pytest.approx(0.0, abs=0.01)
    assert oct_["savings_balance"] == pytest.approx(
        sep["savings_balance"] + sep["savings_planned"], abs=0.01
    )


# -- savings_delta: savings-accounts-only (user decision 2026-08-28) ----------
# Current AND past: signed net of posted txns on the partner's savings
# accounts. Checking noise (salary timing, CC paydowns, overdraft recovery,
# reimbursements) never counts. Chain back-walk deltas stay combined.


def test_savings_delta_current_excludes_checking_noise(tmp_path, monkeypatch):
    """Current delta = savings-only sum; mortgage/salary/CC-paydown ignored.

    Fixture mimics August noise: salary +42000 in, mortgage -15000 out, CC
    paydown -12500 out -- all on CHECKING (1100001). Only the -28 on FxA
    Savings (1100002) counts. Verified ground truth 2026-08: Fixture A's
    savings account moved -28.00.
    """
    monkeypatch.setattr(storage, "PRIVATE_DATA_DIR", tmp_path)
    posted_txns = [
        {
            "amount": 42000,
            "date": "2026-08-15",
            "status": "posted",
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100013, "is_transfer": False},
        },
        {
            "amount": -15000,
            "date": "2026-08-15",
            "status": "posted",
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100003, "is_transfer": False},
        },
        {
            "amount": -12500,
            "date": "2026-08-20",
            "status": "posted",
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {
                "id": 2100011,
                "title": "CC Payment (paired)",
                "is_transfer": True,
            },
        },
        # The only savings-account movement this month.
        {
            "amount": -28,
            "date": "2026-08-12",
            "status": "posted",
            "transaction_account": {"id": 1100002, "type": "savings"},
            "category": {"id": 2100014, "is_transfer": False},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-08",  # current
        events=[],
        transactions=posted_txns,
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined={"partner_a": 41886.31, "partner_b": 66000.0},
        deltas_per_month={
            "partner_a": {"2026-07": -2000.0},
            "partner_b": {"2026-07": 0.0},
        },
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    # Checking noise (+42000-15000-12500 = 14500 net) must NOT pollute
    # savings. Only the -28 savings-account txn counts.
    assert partner_a["savings_delta"] == pytest.approx(-28.0, abs=0.01)


def test_savings_delta_past_excludes_checking_noise(tmp_path, monkeypatch):
    """Past delta = savings-only sum; in-month checking flow ignored.

    July: +1000 into savings, plus checking noise (+42000/-41500).
    Delta = 1000. Combined-flow (old rule) would have said 1500.
    """
    monkeypatch.setattr(storage, "PRIVATE_DATA_DIR", tmp_path)
    posted_txns = [
        {
            "amount": 42000,
            "date": "2026-07-25",
            "status": "posted",
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100013, "is_transfer": False},
        },
        {
            "amount": -41500,
            "date": "2026-07-26",
            "status": "posted",
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100003, "is_transfer": False},
        },
        {
            "amount": 1000,
            "date": "2026-07-28",
            "status": "posted",
            "transaction_account": {"id": 1100002, "type": "savings"},
            "category": {"id": 2100014, "is_transfer": False},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-07",  # past
        events=[],
        transactions=posted_txns,
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined=None,
        deltas_per_month=None,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    assert partner_a["savings_delta"] == pytest.approx(1000.0, abs=0.01)


def test_savings_delta_zero_when_no_savings_txns(tmp_path, monkeypatch):
    """Savings accounts resolve, no savings txns -> 0.0, NOT None.

    0.0 is the honest value: savings accounts exist, nothing moved into
    them this month. None is reserved for "cannot compute" (no savings
    accounts mapped / chain kwargs absent).
    """
    monkeypatch.setattr(storage, "PRIVATE_DATA_DIR", tmp_path)
    posted_txns = [
        # Checking-only activity -- savings untouched.
        {
            "amount": 42000,
            "date": "2026-08-15",
            "status": "posted",
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100013, "is_transfer": False},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-08",  # current
        events=[],
        transactions=posted_txns,
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined={"partner_a": 41886.31, "partner_b": 66000.0},
        deltas_per_month={
            "partner_a": {"2026-07": 0.0},
            "partner_b": {"2026-07": 0.0},
        },
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    assert partner_a["savings_delta"] == 0.0
    assert partner_a["savings_delta"] is not None


def test_chain_back_walk_deltas_stay_combined(tmp_path, monkeypatch):
    """PIN: chain deltas_per_month stays combined; displayed delta savings-only.

    One +3000 on CHECKING, one -2000 on SAVINGS during July 2026.
      chain delta[2026-07] (internal, combined) = 3000 + (-2000) = 1000
      -> balance[2026-07] = anchor - 1000 = 41886.31 - 1000 = 40886.31
      savings_delta[2026-07] (field, savings-only) = -2000
    If the chain delta accidentally went savings-only, the balance would
    come out 43886.31 -- this test catches that invariant break.
    """
    monkeypatch.setattr(storage, "PRIVATE_DATA_DIR", tmp_path)
    from budget_api.services.bills_builder import build_bills_chain

    months = ["2026-07", "2026-08"]
    events_per_month: dict[str, list[dict]] = {m: [] for m in months}
    transactions_per_month: dict[str, list[dict]] = {m: [] for m in months}
    transactions_per_month["2026-07"] = [
        {
            "amount": 3000,
            "date": "2026-07-10",
            "status": "posted",
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100003, "is_transfer": False},
        },
        {
            "amount": -2000,
            "date": "2026-07-11",
            "status": "posted",
            "transaction_account": {"id": 1100002, "type": "savings"},
            "category": {"id": 2100014, "is_transfer": False},
        },
    ]
    snapshots = build_bills_chain(
        months=months,
        events_per_month=events_per_month,
        transactions_per_month=transactions_per_month,
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        warnings=[],
    )
    jul = next(
        p for p in snapshots["2026-07"]["partners"] if p["partner"] == "Fixture A"
    )
    # Back-walk used the COMBINED delta (1000), not the savings-only one.
    assert jul["savings_balance"] == pytest.approx(41886.31 - 1000, abs=0.01)
    # Displayed delta is savings-only.
    assert jul["savings_delta"] == pytest.approx(-2000.0, abs=0.01)

# -- current-month CC payments: posted truth vs m-1 estimate -----------------
# Regression 2026-09-15: the status bar showed only the scheduled CC-Payment
# event (32 806) while a second posted eFaktura paydown (1 933.04) was
# invisible - and Fixture B had NO event at all, silently falling back to the
# estimate. real_cc_bill now takes max(event_sum, posted_sum) on the
# CC-payment category, while estimated_cc_bill stays the m-1 (prior-month)
# proxy so plan-vs-actual remains visible in the table. savings_planned
# picks real ?? estimated, mirroring the past-month rule.


def test_build_bills_snapshot_current_cc_unscheduled_posted_counts():
    """Fixture A (current month): schedule event 32 806 + posted paydowns
    32 806.89 + 1 933.04 -> real = 34 739.93 (posted truth wins the max).
    Estimated stays the m-1 proxy (July spend 5 000) so the table still
    shows the plan behind the real bill."""
    events = [
        {
            "id": "sal-1",
            "date": "2026-08-25",
            "amount": 49490,
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100013, "is_transfer": False},
        },
        {
            "id": "cc-evt",
            "date": "2026-08-15",
            "amount": -32806.0,
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {
                "id": 2100011,
                "title": "CC Payment (paired)",
                "is_transfer": True,
            },
        },
    ]
    txns = [
        {
            "amount": -32806.89,
            "date": "2026-08-15",
            "status": "posted",
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100011},
        },
        {
            "amount": -1933.04,
            "date": "2026-08-15",
            "status": "posted",
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100011},
        },
    ]
    prior_txns = [
        {
            "amount": -5000,
            "status": "posted",
            "transaction_account": {"id": 1100003, "type": "credits"},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-08",
        events=events,
        transactions=txns,
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        prior_transactions=prior_txns,
        prior_events=[],
        live_combined=None,
        deltas_per_month=None,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    assert partner_a["real_cc_bill"] == pytest.approx(34739.93, abs=0.01)
    assert partner_a["estimated_cc_bill"] == pytest.approx(5000, abs=0.01)
    # savings_planned picks real: 49490 - 0 bills - 34739.93.
    assert partner_a["savings_planned"] == pytest.approx(14750.07, abs=0.01)


def test_build_bills_snapshot_current_cc_no_event_posted_only():
    """Fixture B (current month): posted 11 022.21 paydown, NO CC-Payment event
    -> real_cc_bill = 11 022.21 (not null). Estimated stays the m-1 proxy
    (July spend 8 000) Ã¢â‚¬â€ plan-vs-actual remains visible."""
    events = [
        {
            "id": "sal-b",
            "date": "2026-08-25",
            "amount": 40814,
            "transaction_account": {"id": 1100007, "type": "bank"},
            "category": {"id": 2100013, "is_transfer": False},
        },
    ]
    txns = [
        {
            "amount": -11022.21,
            "date": "2026-08-15",
            "status": "posted",
            "transaction_account": {"id": 1100007, "type": "bank"},
            "category": {"id": 2100011},
        },
    ]
    prior_txns = [
        {
            "amount": -8000,
            "status": "posted",
            "transaction_account": {"id": 1100008, "type": "credits"},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-08",
        events=events,
        transactions=txns,
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        prior_transactions=prior_txns,
        prior_events=[],
        live_combined=None,
        deltas_per_month=None,
    )
    partner_b = next(p for p in snapshot["partners"] if p["partner"] == "Fixture B")
    assert partner_b["real_cc_bill"] == pytest.approx(11022.21, abs=0.01)
    assert partner_b["estimated_cc_bill"] == pytest.approx(8000, abs=0.01)


def test_build_bills_snapshot_current_cc_event_only_legacy_path():
    """Current month: CC-Payment event, NO posted paydown yet -> real =
    the scheduled event (12 500), preserving legacy behaviour for a planned
    but unposted payment. Estimated stays the m-1 proxy (July 9 000)."""
    events = [
        {
            "id": "sal-1",
            "date": "2026-08-25",
            "amount": 49490,
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100013, "is_transfer": False},
        },
        {
            "id": "cc-evt",
            "date": "2026-08-20",
            "amount": -12500,
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {
                "id": 2100011,
                "title": "CC Payment (paired)",
                "is_transfer": True,
            },
        },
    ]
    prior_txns = [
        {
            "amount": -9000,
            "status": "posted",
            "transaction_account": {"id": 1100003, "type": "credits"},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-08",
        events=events,
        transactions=[],
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        prior_transactions=prior_txns,
        prior_events=[],
        live_combined=None,
        deltas_per_month=None,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    assert partner_a["real_cc_bill"] == 12500
    assert partner_a["estimated_cc_bill"] == 9000


def test_build_bills_snapshot_m1_estimate_posted_plus_scheduled():
    """m+1 (2026-09 under the frozen Aug clock): estimated = posted-so-far
    in August + remaining scheduled August buys - the statement paid in
    September is August's card activity (wiring corrected 2026-09-18; the
    old code read September's own, empty pre-month-start data and dropped
    real current-month spend). real stays None."""
    events = [
        {
            "id": "sal-1",
            "date": "2026-09-25",
            "amount": 42000,
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100013, "is_transfer": False},
        },
    ]
    prior_events = [
        {
            # Remaining scheduled August buy: dated after the frozen today
            # (Aug 30) but still inside August.
            "id": "cc-buy-1",
            "date": "2026-08-31",
            "amount": -500,
            "transaction_account": {"id": 1100003, "type": "credits"},
            "category": {"id": 2100003, "title": "Hello Fresh", "is_transfer": False},
        },
    ]
    prior_txns = [
        {
            "amount": -200,
            "date": "2026-08-02",
            "status": "posted",
            "transaction_account": {"id": 1100003, "type": "credits"},
            "category": {"id": 2100003, "title": "Groceries", "is_transfer": False},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-09",
        events=events,
        transactions=[],
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        prior_transactions=prior_txns,
        prior_events=prior_events,
        live_combined=None,
        deltas_per_month=None,
        today=PINNED_NOW,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    # posted-so-far (Aug) 200 + remaining envelope (Aug, post-today) 500 = 700.
    assert partner_a["estimated_cc_bill"] == 700
    assert partner_a["real_cc_bill"] is None


def test_build_bills_snapshot_m1_classification_uses_injected_today():
    """PR76 review: the m+1 branch must follow the same clock as _month_flags.

    Injected today=2026-09-15 makes 2026-10 the m+1 month even though the
    frozen wall clock still sits in August. Buggy code compared month against
    the wall-clock m+1 (2026-09) and took the m+2+ scheduled-only path (500).
    Correct behavior: September's card activity (posted 200 + remaining
    September envelope 500) feeds the October estimate -> 700. A September
    event dated on/before today (300) is ignored: posted already carries it.
    """
    events = [
        {
            "id": "sal-1",
            "date": "2026-10-25",
            "amount": 42000,
            "transaction_account": {"id": 1100001, "type": "bank"},
            "category": {"id": 2100013, "is_transfer": False},
        },
    ]
    prior_events = [
        {
            "id": "cc-buy-1",
            "date": "2026-09-20",
            "amount": -500,
            "transaction_account": {"id": 1100003, "type": "credits"},
            "category": {"id": 2100003, "title": "Hello Fresh", "is_transfer": False},
        },
        {
            # Dated <= injected today: must NOT add to the remaining envelope.
            "id": "cc-buy-past",
            "date": "2026-09-10",
            "amount": -300,
            "transaction_account": {"id": 1100003, "type": "credits"},
            "category": {"id": 2100003, "title": "Hello Fresh", "is_transfer": False},
        },
    ]
    prior_txns = [
        {
            "amount": -200,
            "date": "2026-09-02",
            "status": "posted",
            "transaction_account": {"id": 1100003, "type": "credits"},
            "category": {"id": 2100003, "title": "Groceries", "is_transfer": False},
        },
    ]
    snapshot = build_bills_snapshot(
        month="2026-10",
        events=events,
        transactions=[],
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        prior_transactions=prior_txns,
        prior_events=prior_events,
        live_combined=None,
        deltas_per_month=None,
        today=date(2026, 9, 15),
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    # m+1: posted-so-far (Sep) 200 + remaining Sep envelope (09-20) 500 = 700.
    assert partner_a["estimated_cc_bill"] == 700
    assert partner_a["real_cc_bill"] is None


def test_partner_slot_map_caps_slots_at_two_partners():
    """Contract union is "a"|"b"|"" — a 3rd+ partner degrades to the neutral
    slot "" (still keyed by partner_id; renders with neutral styling)."""
    mappings = {
        "partners": {
            "partner_a": {"label": "Fixture A"},
            "partner_b": {"label": "Fixture B"},
            "partner_c": {"label": "Fixture C"},
        }
    }
    assert _partner_slot_map(mappings) == {
        "partner_a": "a",
        "partner_b": "b",
        "partner_c": "",
    }
