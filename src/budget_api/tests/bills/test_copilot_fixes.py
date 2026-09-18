"""F2-BE tests for Copilot review fixes â€” 4 issues found in PR #37.

1. CC bill uses prior events (not current month's)
2. Warnings scoped per-month (not shared across months)
3. Events partner-scoped (no duplication across partners)
4. Catalogs fetched before per-month loop (fresh on first run)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from budget_api.services import storage, sync_runner
from budget_api.services.bills_builder import build_bills_snapshot, NoBillsAccountError
from budget_api.services.bills_derivations import compute_estimated_cc_bill
from budget_api.services.ps_client import PSClient, PSClientError

# -- Fixtures ----------------------------------------------------------------

TWO_PARTNER_MAPPINGS = {
    "schema_version": 1,
    "partners": {
        "partner_a": {"label": "Fixture A"},
        "partner_b": {"label": "Fixture B"},
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


def _write_configs(tmp_private_dir: Path):
    (tmp_private_dir / "account_mappings.json").write_text(
        json.dumps(TWO_PARTNER_MAPPINGS), encoding="utf-8"
    )
    (tmp_private_dir / "category_roles.json").write_text(
        json.dumps(CATEGORY_ROLES), encoding="utf-8"
    )
    (tmp_private_dir / "category_catalog.json").write_text(
        json.dumps(
            {"start": "2026-06", "end": "2026-07", "categories": CATEGORY_CATALOG}
        ),
        encoding="utf-8",
    )
    (tmp_private_dir / "account_catalog.json").write_text(
        json.dumps({"start": "2026-06", "end": "2026-07", "accounts": ACCOUNT_CATALOG}),
        encoding="utf-8",
    )


def _setup_mock(mock_ps_client, events=None, transactions=None):
    mock_ps_client.get_me.return_value = {"id": 12345}
    mock_ps_client.get_transactions.return_value = transactions or []
    mock_ps_client.get_events.return_value = events or []
    mock_ps_client.get_budget.return_value = []
    mock_ps_client.get_categories.return_value = CATEGORY_CATALOG
    mock_ps_client.get_transaction_accounts.return_value = ACCOUNT_CATALOG


# -- Fix #1: CC bill uses prior events, not current --------------------------


def test_estimated_cc_bill_future_uses_prior_txns_events_ignored():
    """Future month: estimate = prior-month posted CC spend only. Events are
    budget envelopes, never matched (envelope model, grill-me round 6)."""
    mappings = {
        "accounts": {
            "1100003": {"type": "cc", "excluded": False},
        }
    }
    prior_txns = [
        {"amount": -500, "status": "posted", "transaction_account": {"id": 1100003}},
    ]
    prior_events = [
        {"amount": -200, "transaction_account": {"id": 1100003}},
    ]
    current_events = [
        {
            "amount": -9999,
            "transaction_account": {"id": 1100003},
        },  # should NOT be included
    ]

    result = compute_estimated_cc_bill(
        "Fixture A", prior_txns, prior_events, mappings, month_kind="future"
    )
    # Prior CC spend: 500. Events ignored (envelope model).
    assert result == 500
    # The 9999 from current events is NOT included.
    assert result != 9999 + 500


def test_build_bills_snapshot_m2_estimate_scheduled_buys_only():
    """m+2+ (2026-12 = m+4 under the frozen Aug clock): estimated = the
    month's own scheduled buy envelopes only (user model 2026-09-15).
    m-1 (November) envelopes and posted spend no longer reach forward â€”
    no posted data exists this far out.
    """
    events = [
        {
            "id": "evt-salary",
            "date": "2026-12-25",
            "note": "Salary",
            "category": {"id": 2100013, "title": "Income", "is_transfer": False},
            "transaction_account": {"id": 1100001, "type": "bank"},
            "amount": 42000,
        },
        # December scheduled buys on FxA CC.
        {
            "id": "buy-1",
            "date": "2026-12-05",
            "note": "Laptop",
            "category": {"id": 2100003, "title": "Electronics", "is_transfer": False},
            "transaction_account": {"id": 1100003, "type": "credits"},
            "amount": -5000,
        },
        {
            "id": "buy-2",
            "date": "2026-12-12",
            "note": "Chair",
            "category": {"id": 2100009, "title": "Home", "is_transfer": False},
            "transaction_account": {"id": 1100003, "type": "credits"},
            "amount": -2200,
        },
    ]
    prior_events = [
        {
            "id": "prior-buy",
            "date": "2026-11-15",
            "note": "Laptop",
            "category": {"id": 2100003, "title": "Electronics", "is_transfer": False},
            "transaction_account": {"id": 1100003, "type": "credits"},
            "amount": -5000,
        },
    ]
    prior_txns = [
        {
            "amount": -3000,
            "status": "posted",
            "transaction_account": {"id": 1100003, "type": "credits"},
        },
    ]

    snapshot = build_bills_snapshot(
        month="2026-12",
        events=events,
        transactions=[],
        account_mappings=TWO_PARTNER_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        prior_events=prior_events,
        prior_transactions=prior_txns,
        live_combined=None,
        deltas_per_month=None,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    # December envelopes only: 5,000 + 2,200 = 7,200. November's 5,000
    # envelope and 3,000 posted spend contribute nothing at m+4.
    assert partner_a["estimated_cc_bill"] == 7200


def test_build_bills_snapshot_m2_estimate_excludes_cc_paydown_events():
    """m+2+ (2026-12): scheduled buy envelopes only (user model 2026-09-15).
    A "CC Payment (paired)" event in the month must NOT inflate the
    estimate (regression kept), and m-1 real spend is out of scope this
    far out. December envelopes: Hello Fresh 5,200 + Groceries 3,000.
    """
    events = [
        {
            "id": "evt-salary",
            "date": "2026-12-25",
            "note": "Salary",
            "category": {"id": 2100013, "title": "Income", "is_transfer": False},
            "transaction_account": {"id": 1100001, "type": "bank"},
            "amount": 42000,
        },
        {
            "id": "evt-rent",
            "date": "2026-12-01",
            "note": "Rent",
            "category": {"id": 2100008, "title": "Rent", "is_transfer": False},
            "transaction_account": {"id": 1100001, "type": "bank"},
            "amount": -15500,
        },
        {
            # December envelope on the CC account.
            "id": "buy-hf",
            "date": "2026-12-05",
            "note": "Hello Fresh",
            "category": {"id": 2100007, "title": "Hello Fresh", "is_transfer": False},
            "transaction_account": {"id": 1100003, "type": "credits"},
            "amount": -5200,
        },
        {
            "id": "buy-groc",
            "date": "2026-12-07",
            "note": "Groceries",
            "category": {"id": 2100009, "title": "Groceries", "is_transfer": False},
            "transaction_account": {"id": 1100003, "type": "credits"},
            "amount": -3000,
        },
        {
            # CC Payment (paired) event in December â€” the paydown itself,
            # must NOT inflate the estimate.
            "id": "ccpay",
            "date": "2026-12-20",
            "note": "CC Payment",
            "category": {
                "id": 2100011,
                "title": "CC Payment (paired)",
                "is_transfer": True,
            },
            "transaction_account": {"id": 1100003, "type": "credits"},
            "amount": -30000,
        },
    ]
    prior_events = [
        {
            "id": "buy-hf-nov",
            "date": "2026-11-05",
            "note": "Hello Fresh",
            "category": {"id": 2100007, "title": "Hello Fresh", "is_transfer": False},
            "transaction_account": {"id": 1100003, "type": "credits"},
            "amount": -5200,
        },
    ]
    prior_txns = [
        {
            "amount": -9000,
            "status": "posted",
            "transaction_account": {"id": 1100003, "type": "credits"},
            "category": {"id": 2100007, "title": "Hello Fresh", "is_transfer": False},
        },
    ]

    snapshot = build_bills_snapshot(
        month="2026-12",
        events=events,
        transactions=[],
        account_mappings=TWO_PARTNER_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        prior_events=prior_events,
        prior_transactions=prior_txns,
        live_combined=None,
        deltas_per_month=None,
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    # December buy envelopes: 5,200 + 3,000 = 8,200. The 30,000 CC-paydown
    # event is excluded; November's envelope and 9,000 real spend ignored.
    assert partner_a["estimated_cc_bill"] == 8200


# -- Fix #2: Warnings scoped per-month --------------------------------------


def test_chain_warnings_do_not_leak_into_later_snapshots():
    """Chain build: an uncategorized txn in month 1 must NOT appear in
    month 2's snapshot warnings (PR61 review â€” generated warnings leaked
    through the shared list seeded into later snapshots)."""
    from budget_api.services.bills_builder import build_bills_chain

    months = ["2026-07", "2026-08"]
    uncategorized = {
        "id": 999,
        "amount": -500,
        "status": "posted",
        "date": "2026-07-10",
        "transaction_account": {"id": 1100001, "type": "bank"},
        "category": None,
    }
    events = {m: [] for m in months}
    txns = {"2026-07": [uncategorized], "2026-08": []}

    snapshots = build_bills_chain(
        months,
        events,
        txns,
        account_mappings=TWO_PARTNER_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        warnings=[],
    )

    jul_w = snapshots["2026-07"]["warnings"]
    aug_w = snapshots["2026-08"]["warnings"]
    assert any("Uncategorized txn" in w and "id=999" in w for w in jul_w)
    assert not any("id=999" in w for w in aug_w)


def test_warnings_scoped_per_month_not_shared(
    tmp_private_dir, tmp_env_file, mock_ps_client
):
    """Two-month sync: each snapshot should only have its own warnings, not the other month's."""
    (tmp_env_file).write_text("API_KEY=test-key-123\n", encoding="utf-8")
    _write_configs(tmp_private_dir)

    # Pre-write prior-month cache for 2026-05 so 2026-06 doesn't auto-fetch.
    (tmp_private_dir / "events_2026-05.json").write_text("[]", encoding="utf-8")
    (tmp_private_dir / "2026-05_ps_raw.json").write_text("[]", encoding="utf-8")

    _setup_mock(mock_ps_client, events=[], transactions=[])

    sync_runner.sync_all("2026-06", "2026-07")

    # Both snapshots should exist.
    assert storage.bills_dashboard_path("2026-06").exists()
    assert storage.bills_dashboard_path("2026-07").exists()

    jun = json.loads(
        storage.bills_dashboard_path("2026-06").read_text(encoding="utf-8")
    )
    jul = json.loads(
        storage.bills_dashboard_path("2026-07").read_text(encoding="utf-8")
    )

    # June might have a prior-month auto-fetch warning for 2026-05.
    # But if 2026-05 cache exists, no warning.
    # July's prior month is June â€” cache was just written during sync, so no auto-fetch.
    # Each snapshot should NOT contain the other month's warnings.
    jun_warnings = jun["warnings"]
    jul_warnings = jul["warnings"]
    # No cross-contamination: no "2026-07" in June's warnings.
    assert not any("2026-07" in w for w in jun_warnings)


# -- Fix #3: Events partner-scoped (no duplication) --------------------------


def test_events_not_duplicated_across_parters():
    """Events on Fixture A's accounts should NOT appear in Fixture B's events[]."""
    events = [
        {
            "id": "evt-chr-salary",
            "date": "2026-07-25",
            "note": "Salary",
            "category": {"id": 2100013, "title": "Income", "is_transfer": False},
            "transaction_account": {
                "id": 1100001,
                "type": "bank",
            },  # Fixture A's checking
            "amount": 42000,
        },
        {
            "id": "evt-fxb-salary",
            "date": "2026-07-25",
            "note": "Salary",
            "category": {"id": 2100013, "title": "Income", "is_transfer": False},
            "transaction_account": {"id": 1100007, "type": "bank"},  # Fixture B's checking
            "amount": 38000,
        },
        {
            "id": "evt-chr-bill",
            "date": "2026-07-10",
            "note": "Rent",
            "category": {"id": 2100003, "title": "Common", "is_transfer": False},
            "transaction_account": {
                "id": 1100001,
                "type": "bank",
            },  # Fixture A's checking
            "amount": -15500,
        },
    ]

    snapshot = build_bills_snapshot(
        month="2026-12",
        events=events,
        transactions=[],
        account_mappings=TWO_PARTNER_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined=None,
        deltas_per_month=None,
    )

    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    partner_b = next(p for p in snapshot["partners"] if p["partner"] == "Fixture B")

    # Fixture A should have 2 events (salary + bill), not 3.
    assert len(partner_a["events"]) == 2
    # Fixture B should have 1 event (her salary), not 3.
    assert len(partner_b["events"]) == 1
    # Fixture A's salary = 42000, not 42000 + 38000.
    assert partner_a["salary"] == 42000
    # Fixture B's salary = 38000.
    assert partner_b["salary"] == 38000
    # Fixture A's bills = 15500, not 15500 + anything from Fixture B.
    assert partner_a["bills"] == 15500
    # Fixture B's bills = 0 (no bills events on her accounts).
    assert partner_b["bills"] == 0


def test_bills_count_does_not_double_count_across_parters():
    """bills_count at month level should count each event once, not once per partner."""
    events = [
        {
            "id": "evt-1",
            "date": "2026-12-10",
            "note": "Rent",
            "category": {"id": 2100003, "title": "Common", "is_transfer": False},
            "transaction_account": {"id": 1100001, "type": "bank"},
            "amount": -15500,
        },
        {
            "id": "evt-2",
            "date": "2026-12-15",
            "note": "Laptop",
            "category": {"id": 2100003, "title": "Electronics", "is_transfer": False},
            "transaction_account": {"id": 1100008, "type": "credits"},
            "amount": -5000,
        },
    ]

    snapshot = build_bills_snapshot(
        month="2026-12",
        events=events,
        transactions=[],
        account_mappings=TWO_PARTNER_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined=None,
        deltas_per_month=None,
    )

    # 1 bill (Fixture A's rent) + 1 buy (Fixture B's laptop) = 1 + 1.
    assert snapshot["bills_count"] == 1
    assert snapshot["buys_count"] == 1


# -- Fix #4: Catalogs fetched before per-month loop --------------------------


def test_catalogs_fetched_before_per_month_loop_on_fresh_run(
    tmp_private_dir, tmp_env_file, mock_ps_client
):
    """On a fresh run (no existing catalog files), bills snapshots should still
    have correct account balances because catalogs are fetched before the loop."""
    (tmp_env_file).write_text("API_KEY=test-key-123\n", encoding="utf-8")

    # Only write mappings + roles. Do NOT write catalog files.
    (tmp_private_dir / "account_mappings.json").write_text(
        json.dumps(TWO_PARTNER_MAPPINGS), encoding="utf-8"
    )
    (tmp_private_dir / "category_roles.json").write_text(
        json.dumps(CATEGORY_ROLES), encoding="utf-8"
    )

    # Pre-write prior-month cache to avoid auto-fetch noise.
    (tmp_private_dir / "events_2026-06.json").write_text("[]", encoding="utf-8")
    (tmp_private_dir / "2026-06_ps_raw.json").write_text("[]", encoding="utf-8")

    events = [
        {
            "id": "evt-1",
            "date": "2026-07-25",
            "note": "Salary",
            "category": {"id": 2100013, "title": "Income", "is_transfer": False},
            "transaction_account": {"id": 1100001, "type": "bank"},
            "amount": 42000,
        },
    ]
    _setup_mock(mock_ps_client, events=events, transactions=[])

    # Before sync: catalog files should NOT exist.
    assert not (tmp_private_dir / "account_catalog.json").exists()
    assert not (tmp_private_dir / "category_catalog.json").exists()

    sync_runner.sync_all("2026-07", "2026-07")

    # After sync: catalog files should exist (fetched before loop).
    assert (tmp_private_dir / "account_catalog.json").exists()
    assert (tmp_private_dir / "category_catalog.json").exists()

    # Bills snapshot should exist with correct salary.
    snapshot = json.loads(
        storage.bills_dashboard_path("2026-07").read_text(encoding="utf-8")
    )
    partner_a = next(p for p in snapshot["partners"] if p["partner"] == "Fixture A")
    assert partner_a["salary"] == 42000
