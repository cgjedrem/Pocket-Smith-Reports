"""F2-BE bills derivations tests â€” per-field math functions."""

from __future__ import annotations

import pytest

from datetime import date

from budget_api.services.bills_derivations import (
    compute_bills,
    compute_budget_usage,
    compute_cc_usage,
    compute_cc_usage_by_category,
    compute_current_cc_bill_posted,
    compute_estimated_cc_bill,
    compute_future_estimated_cc_bill,
    compute_net,
    compute_planned_cc_buys,
    compute_real_bills,
    compute_real_cc_bill,
    compute_real_cc_spend,
    compute_scheduled_cc_bill,
    compute_salary,
    compute_savings_balance_current,
    compute_savings_balance_past,
    compute_status,
)

# -- Fixtures ----------------------------------------------------------------

ACCOUNT_MAPPINGS = {
    "accounts": {
        "4110210": {"type": "checking", "excluded": False},  # FxA Check
        "4110216": {"type": "cc", "excluded": False},  # FxA CC
        "4110213": {"type": "savings", "excluded": False},  # FxA Savings
        "5376190": {"type": "checking", "excluded": False},  # FxB Check
    },
}

# Constants used across compute_real_cc_spend + compute_cc_usage new tests.
CC_PAYMENT_CAT_CC = 34025345
EXCLUDE_CAT_CC = 34028575  # Personal Transfer (Fixture A)
GROCERIES_CAT = 34025250
DINING_CAT = 34025260


def _classified_events(partner="Fixture A"):
    return [
        {"type": "salary", "partner": partner, "amount": 42000},
        {"type": "bill", "partner": partner, "amount": -15500},
        {"type": "buy", "partner": partner, "amount": -5000},
        {"type": "buy", "partner": partner, "amount": -1200},
        {"type": "bill", "partner": partner, "amount": -3000},
    ]


# -- compute_salary ----------------------------------------------------------


def test_compute_salary_sums_income_events():
    events = _classified_events()
    assert compute_salary(events, "Fixture A") == 42000


def test_compute_salary_falls_back_to_zero_on_missing():
    assert compute_salary([], "Fixture A") == 0


# -- compute_bills -----------------------------------------------------------


def test_compute_bills_sums_spend_events():
    events = _classified_events()
    assert compute_bills(events, "Fixture A") == 18500


# -- compute_planned_cc_buys ------------------------------------------------


def test_compute_planned_cc_buys_sums_buy_events():
    # _classified_events has 2 buy events: 5000 + 1200 = 6200 (absolute).
    assert compute_planned_cc_buys(_classified_events(), "Fixture A") == 6200


def test_compute_planned_cc_buys_filters_by_partner():
    events = [
        {"type": "buy", "partner": "Fixture A", "amount": -1000},
        {"type": "buy", "partner": "Fixture B", "amount": -2000},
    ]
    # Fixture A only – 1000.
    assert compute_planned_cc_buys(events, "Fixture A") == 1000
    # Fixture B only – 2000.
    assert compute_planned_cc_buys(events, "Fixture B") == 2000


def test_compute_planned_cc_buys_ignores_bill_and_salary_events():
    """Planned buys = buy bucket only. Bills and salary must not leak in."""
    events = [
        {"type": "buy", "partner": "Fixture A", "amount": -500},
        {"type": "bill", "partner": "Fixture A", "amount": -1000},
        {"type": "salary", "partner": "Fixture A", "amount": 42000},
        {"type": "savings", "partner": "Fixture A", "amount": -5000},
    ]
    assert compute_planned_cc_buys(events, "Fixture A") == 500


def test_compute_planned_cc_buys_falls_back_to_zero():
    assert compute_planned_cc_buys([], "Fixture A") == 0


# -- compute_savings_balance_current ----------------------------------------

MAPPINGS_WITH_PARTNERS = {
    "accounts": {
        "4110210": {"partner_id": "partner_a", "type": "checking", "excluded": False},
        "4110213": {"partner_id": "partner_a", "type": "savings", "excluded": False},
        "4716715": {"partner_id": "partner_a", "type": "savings", "excluded": False},
        "4110216": {"partner_id": "partner_a", "type": "cc", "excluded": False},
        "5376190": {"partner_id": "partner_b", "type": "checking", "excluded": False},
    },
}

CATALOG_LIVE = [
    {"id": 4110210, "current_balance": 13886.31},
    {"id": 4110213, "current_balance": 2.0},
    {"id": 4716715, "current_balance": 28.71},
    {"id": 4110216, "current_balance": -5000.0},  # cc â€” must not count
    {"id": 5376190, "current_balance": 32148.76},
]


def test_compute_savings_balance_current_returns_none_when_no_bills():
    # partner with no checking account mapped â†’ None (caller falls back to lag)
    mappings = {
        "accounts": {
            "4110213": {
                "partner_id": "partner_a",
                "type": "savings",
                "excluded": False,
            },
        },
    }
    assert compute_savings_balance_current("partner_a", mappings, CATALOG_LIVE) is None


def test_compute_savings_balance_current_sums_bills_and_savings():
    # checking + both savings, cc excluded
    result = compute_savings_balance_current(
        "partner_a", MAPPINGS_WITH_PARTNERS, CATALOG_LIVE
    )
    assert result == pytest.approx(13886.31 + 2.0 + 28.71)


def test_compute_savings_balance_current_handles_no_savings_accounts():
    # bills only, no savings mapped â†’ bills balance, NOT None
    result = compute_savings_balance_current(
        "partner_b", MAPPINGS_WITH_PARTNERS, CATALOG_LIVE
    )
    assert result == pytest.approx(32148.76)


# -- compute_savings_balance_past -------------------------------------------


def test_compute_savings_balance_past_subtracts_delta():
    # single back-walk step: balance[m] = balance[m+1] - delta[m]
    deltas = {"2026-07": 8920.61, "2026-06": -11872.68}
    assert compute_savings_balance_past(13917.02, "2026-07", deltas) == pytest.approx(
        4996.41
    )
    assert compute_savings_balance_past(4996.41, "2026-06", deltas) == pytest.approx(
        16869.09
    )


# -- compute_estimated_cc_bill -----------------------------------------------
#
# Envelope model (F2 Â§9 revised, grill-me round 6): scheduled CC buys are
# budget envelopes, never matched to transactions. Future month = prior
# month's posted CC spend only (events ignored). Current month =
# posted-so-far (this month's CC txns) + remaining envelope (CC-account
# events dated > today).


def test_compute_estimated_cc_bill_future_ignores_events():
    """Future month: prior posted CC spend only. Events with the SAME
    amounts as posted txns must NOT change the result â€” the old bug shape
    (Sep 2026: estimate 44,095 vs real ~30,620)."""
    prior_txns = [
        {"amount": -500, "status": "posted", "transaction_account": {"id": 4110216}},
        {"amount": -300, "status": "posted", "transaction_account": {"id": 4110216}},
        {"amount": -100, "status": "pending", "transaction_account": {"id": 4110216}},
    ]
    events = [
        {"amount": -500, "date": "2026-08-05", "transaction_account": {"id": 4110216}},
        {"amount": -200, "date": "2026-08-20", "transaction_account": {"id": 4110216}},
    ]
    result = compute_estimated_cc_bill(
        "Fixture A",
        prior_txns,
        events,
        ACCOUNT_MAPPINGS,
        month_kind="future",
        today=date(2026, 9, 1),
    )
    # Posted only: 500 + 300 = 800. Pending skipped. Events ignored.
    assert result == 800


def test_compute_estimated_cc_bill_current_posted_plus_remaining_envelope():
    """Current month: posted-so-far + remaining envelope (events > today).

    today=2026-08-15. Posted CC charges 10,000. Buys dated 08-10 (1,000 â€”
    past, ignored) and 08-20 (1,500 â€” future, counts) â†’ 11,500.
    """
    this_month_txns = [
        {
            "amount": -10000,
            "date": "2026-08-09",
            "status": "posted",
            "transaction_account": {"id": 4110216},
        },
    ]
    events = [
        {"amount": -1000, "date": "2026-08-10", "transaction_account": {"id": 4110216}},
        {"amount": -1500, "date": "2026-08-20", "transaction_account": {"id": 4110216}},
    ]
    result = compute_estimated_cc_bill(
        "Fixture A",
        this_month_txns,
        events,
        ACCOUNT_MAPPINGS,
        month_kind="current",
        today=date(2026, 8, 15),
    )
    assert result == 11500


def test_compute_estimated_cc_bill_current_no_future_events():
    """Current month with no future-dated events â†’ posted-so-far exactly."""
    this_month_txns = [
        {
            "amount": -10000,
            "date": "2026-08-09",
            "status": "posted",
            "transaction_account": {"id": 4110216},
        },
    ]
    events = [
        # Past + today-dated: both ignored (<= today).
        {"amount": -1000, "date": "2026-08-10", "transaction_account": {"id": 4110216}},
        {"amount": -500, "date": "2026-08-15", "transaction_account": {"id": 4110216}},
    ]
    result = compute_estimated_cc_bill(
        "Fixture A",
        this_month_txns,
        events,
        ACCOUNT_MAPPINGS,
        month_kind="current",
        today=date(2026, 8, 15),
    )
    assert result == 10000


# -- compute_real_cc_bill ----------------------------------------------------


def test_compute_real_cc_bill_from_cc_payment_events():
    """Sum CC-payment transactions on this partner's CC account.

    The CC-side amount is what the card was actually charged (positive in
    PS). The bills-side (negative on checking) is the paydown transfer â€”
    same flow, different account, NOT counted.
    """
    CC_PAYMENT_CAT = 34025345
    txns = [
        {
            "amount": 5000,  # positive on CC side
            "status": "posted",
            "transaction_account": {"id": 4110216},  # CC account
            "category": {"id": CC_PAYMENT_CAT},
        },
        {
            "amount": -3000,  # not CC payment category
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": 34025245},
        },
        {
            # Bills-side paired txn (negative on checking) â€” must be excluded
            # because it's on a checking account, not a CC account.
            "amount": -5000,
            "status": "posted",
            "transaction_account": {"id": 4110210},
            "category": {"id": CC_PAYMENT_CAT},
        },
    ]
    result = compute_real_cc_bill("Fixture A", txns, ACCOUNT_MAPPINGS, CC_PAYMENT_CAT)
    # Only the first txn matches CC account + CC payment category.
    assert result == 5000


def test_compute_real_cc_bill_handles_null_category():
    """PS can send category=null â€” must not crash with NoneType.get().

    Regression: sync failed with 'NoneType' object has no attribute 'get'
    because .get("category", {}) returns None (not {}) when key exists
    with explicit null value.
    """
    CC_PAYMENT_CAT = 34025345
    txns = [
        {
            "amount": 5000,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": None,  # PS sends explicit null
        },
        {
            "amount": 3000,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": CC_PAYMENT_CAT},
        },
    ]
    # null-category txn skipped (no id match), CC-payment txn counted.
    result = compute_real_cc_bill("Fixture A", txns, ACCOUNT_MAPPINGS, CC_PAYMENT_CAT)
    assert result == 3000


# -- compute_cc_usage --------------------------------------------------------


def test_compute_cc_usage_current_month_only():
    """Posted-only filter: pending txns dropped, posted summed to total.

    Helper requires category on each txn; data without category is
    dropped (returns None, not raw total).
    """
    txns = [
        {
            "amount": -500,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": GROCERIES_CAT, "is_transfer": False},
        },
        {
            "amount": -300,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": GROCERIES_CAT, "is_transfer": False},
        },
        {
            "amount": -100,
            "status": "pending",
            "transaction_account": {"id": 4110216},
            "category": {"id": GROCERIES_CAT, "is_transfer": False},
        },
    ]
    result = compute_cc_usage("Fixture A", txns, ACCOUNT_MAPPINGS)
    # Only posted: 500 + 300 = 800.
    assert result == 800


# -- compute_real_cc_spend (new helper) -------------------------------------
#
# Per-partner, per-category map of posted CC-account spend.
# Backing helper for compute_cc_usage (returns sum of its values). Filters:
# - partner_account_ids (None â†’ all CC accounts, legacy path)
# - status=posted
# - account.type=cc, not excluded
# - category != cc_payment_category_id
# - category.is_transfer != True
# - category id not in exclude_category_ids (KPI role "exclude")


def test_compute_real_cc_spend_empty_when_no_cc_txns():
    """No txns â†’ empty map."""
    assert (
        compute_real_cc_spend(
            "Fixture A", [], ACCOUNT_MAPPINGS, {"4110216"}, CC_PAYMENT_CAT_CC
        )
        == {}
    )


def test_compute_real_cc_spend_groups_by_category():
    """Multi-category spend collapses to {cat_id: abs_total}."""
    txns = [
        {
            "amount": -500,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": GROCERIES_CAT, "is_transfer": False},
        },
        {
            "amount": -300,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": GROCERIES_CAT, "is_transfer": False},
        },
        {
            "amount": -1200,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": DINING_CAT, "is_transfer": False},
        },
    ]
    result = compute_real_cc_spend(
        "Fixture A", txns, ACCOUNT_MAPPINGS, {"4110216"}, CC_PAYMENT_CAT_CC
    )
    assert result == {GROCERIES_CAT: 800, DINING_CAT: 1200}


def test_compute_real_cc_spend_excludes_is_transfer():
    """is_transfer=true on the category is dropped."""
    txns = [
        {
            "amount": -500,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": GROCERIES_CAT, "is_transfer": True},
        },
        {
            "amount": -1000,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": DINING_CAT, "is_transfer": False},
        },
    ]
    result = compute_real_cc_spend(
        "Fixture A", txns, ACCOUNT_MAPPINGS, {"4110216"}, CC_PAYMENT_CAT_CC
    )
    # Only dining counts.
    assert result == {DINING_CAT: 1000}


def test_compute_real_cc_spend_excludes_exclude_role_category():
    """exclude_category_ids set drops KPI-noise category ids."""
    txns = [
        {
            "amount": -500,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": EXCLUDE_CAT_CC, "is_transfer": False},
        },
        {
            "amount": -1000,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": DINING_CAT, "is_transfer": False},
        },
    ]
    result = compute_real_cc_spend(
        "Fixture A",
        txns,
        ACCOUNT_MAPPINGS,
        {"4110216"},
        CC_PAYMENT_CAT_CC,
        exclude_category_ids={EXCLUDE_CAT_CC},
    )
    # Only dining.
    assert result == {DINING_CAT: 1000}


def test_compute_real_cc_spend_excludes_cc_payment_category():
    """CC-paydown category (bills-side) is a transfer, not card spend."""
    txns = [
        {
            "amount": -5000,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": CC_PAYMENT_CAT_CC, "is_transfer": False},
        },
        {
            "amount": -800,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": GROCERIES_CAT, "is_transfer": False},
        },
    ]
    result = compute_real_cc_spend(
        "Fixture A", txns, ACCOUNT_MAPPINGS, {"4110216"}, CC_PAYMENT_CAT_CC
    )
    assert result == {GROCERIES_CAT: 800}


def test_compute_real_cc_spend_is_partner_scoped():
    """With partner_account_ids set, only txns on those accounts are summed.

    FxA CC 4110216 vs FxB CC 5376195 – both type=cc. Fixture A helper
    must NOT see Fixture B's txns.
    """
    two_partner_mappings = {
        "accounts": {
            "4110216": {"type": "cc", "excluded": False},
            "5376195": {"type": "cc", "excluded": False},
        },
    }
    txns = [
        {
            "amount": -800,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": GROCERIES_CAT, "is_transfer": False},
        },
        {
            "amount": -500,
            "status": "posted",
            "transaction_account": {"id": 5376195},
            "category": {"id": DINING_CAT, "is_transfer": False},
        },
    ]
    result = compute_real_cc_spend(
        "Fixture A", txns, two_partner_mappings, {"4110216"}, CC_PAYMENT_CAT_CC
    )
    # Only FxA CC, only groceries.
    assert result == {GROCERIES_CAT: 800}


# -- compute_cc_usage (total real posted CC spend) -------------------------
#
# cc_usage = sum(real_spend.values()) â€” the full posted CC total, NOT the
# per-category overage vs planned (2026-08-28 decision). No flooring:
# a category with real < planned still contributes its full real amount.
# Returns None when no real CC txns in window.


def test_compute_cc_usage_planned_covers_real_still_returns_full_real():
    """Planned buys present â†’ real total returned anyway (no subtraction)."""
    txns = [
        {
            "amount": -500,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": GROCERIES_CAT, "is_transfer": False},
        },
    ]
    result = compute_cc_usage(
        "Fixture A",
        txns,
        ACCOUNT_MAPPINGS,
        {"4110216"},
        CC_PAYMENT_CAT_CC,
    )
    assert result == 500.0


def test_compute_cc_usage_august_shape_returns_full_total():
    """August shape: planned 13,475 + unplanned spend â†’ full 30,620 total,
    not the per-category overage (was 18,231)."""
    planned = 13_475
    total = 30_620
    txns = [
        # Planned-category spend: contributes full real (no flooring at 0).
        {
            "amount": -planned,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": GROCERIES_CAT, "is_transfer": False},
        },
        # Unplanned-category spend: also full real.
        {
            "amount": -(total - planned),
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": DINING_CAT, "is_transfer": False},
        },
    ]
    result = compute_cc_usage(
        "Fixture A",
        txns,
        ACCOUNT_MAPPINGS,
        {"4110216"},
        CC_PAYMENT_CAT_CC,
    )
    assert result == 30_620.0


def test_compute_cc_usage_no_real_txns_returns_none():
    """No real CC activity in window â†’ None (not 0, not raw 0)."""
    result = compute_cc_usage(
        "Fixture A",
        [],
        ACCOUNT_MAPPINGS,
        {"4110216"},
        CC_PAYMENT_CAT_CC,
    )
    assert result is None


def test_compute_cc_usage_partner_scoped_ignores_other_partner_cc_txns():
    """FxA CC txns must not leak into Fixture B's cc_usage."""
    two_partner_mappings = {
        "accounts": {
            "4110216": {"type": "cc", "excluded": False},  # FxA CC
            "5376195": {"type": "cc", "excluded": False},  # FxB CC
        },
    }
    txns = [
        # FxA real: 1000 groceries.
        {
            "amount": -1000,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": GROCERIES_CAT, "is_transfer": False},
        },
        # FxB real: 500 dining (must NOT count for Fixture A).
        {
            "amount": -500,
            "status": "posted",
            "transaction_account": {"id": 5376195},
            "category": {"id": DINING_CAT, "is_transfer": False},
        },
    ]
    result = compute_cc_usage(
        "Fixture A",
        txns,
        two_partner_mappings,
        {"4110216"},
        CC_PAYMENT_CAT_CC,
    )
    # FxA total: 1000. Fixture B's 500 excluded.
    assert result == 1000.0


def test_compute_cc_usage_excludes_cc_payment_from_real_spend():
    """CC-paydown category txn must not show up as real spend."""
    txns = [
        {
            "amount": -5000,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": CC_PAYMENT_CAT_CC, "is_transfer": False},
        },
        {
            "amount": -300,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": GROCERIES_CAT, "is_transfer": False},
        },
    ]
    result = compute_cc_usage(
        "Fixture A",
        txns,
        ACCOUNT_MAPPINGS,
        {"4110216"},
        CC_PAYMENT_CAT_CC,
    )
    # Only groceries (300) counts; CC-paydown (5000) excluded.
    assert result == 300.0


# -- compute_cc_usage_by_category (per-category-title real CC spend) ---------
#
# Same filters + population as compute_cc_usage, keyed by category TITLE
# (event.title mapping). Values must sum to the cc_usage total. None when
# no real CC txns (same gate); id-keyed str() fallback keeps spend visible
# when a txn's category object carries no title.


def test_compute_cc_usage_by_category_no_real_txns_returns_none():
    """No real CC activity in window â†’ None (same gate as cc_usage)."""
    result = compute_cc_usage_by_category(
        "Fixture A",
        [],
        ACCOUNT_MAPPINGS,
        {"4110216"},
        CC_PAYMENT_CAT_CC,
    )
    assert result is None


def test_compute_cc_usage_by_category_groups_by_title():
    """Multi-category spend collapses to {title: abs_total}; sum == cc_usage."""
    txns = [
        {
            "amount": -500,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": GROCERIES_CAT, "title": "Groceries", "is_transfer": False},
        },
        {
            "amount": -300,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": GROCERIES_CAT, "title": "Groceries", "is_transfer": False},
        },
        {
            "amount": -1200,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": DINING_CAT, "title": "Dining", "is_transfer": False},
        },
    ]
    kwargs = {
        "account_mappings": ACCOUNT_MAPPINGS,
        "partner_account_ids": {"4110216"},
        "cc_payment_category_id": CC_PAYMENT_CAT_CC,
    }
    result = compute_cc_usage_by_category("Fixture A", txns, **kwargs)
    assert result == {"Groceries": 800, "Dining": 1200}
    # Same population as cc_usage â†’ totals must match.
    assert sum(result.values()) == compute_cc_usage("Fixture A", txns, **kwargs)


def test_compute_cc_usage_by_category_applies_same_filters():
    """CC-paydown, is_transfer and exclude-role txns are dropped identically."""
    txns = [
        {
            "amount": -5000,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": CC_PAYMENT_CAT_CC, "title": "CC Payment (paired)", "is_transfer": False},
        },
        {
            "amount": -700,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": GROCERIES_CAT, "title": "Groceries", "is_transfer": True},
        },
        {
            "amount": -200,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": EXCLUDE_CAT_CC, "title": "Personal Transfer", "is_transfer": False},
        },
        {
            "amount": -800,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": GROCERIES_CAT, "title": "Groceries", "is_transfer": False},
        },
    ]
    result = compute_cc_usage_by_category(
        "Fixture A",
        txns,
        ACCOUNT_MAPPINGS,
        {"4110216"},
        CC_PAYMENT_CAT_CC,
        exclude_category_ids={EXCLUDE_CAT_CC},
    )
    assert result == {"Groceries": 800}


def test_compute_cc_usage_by_category_partner_scoped():
    """FxA CC txns must not leak into Fixture B's per-category map (and vice versa)."""
    two_partner_mappings = {
        "accounts": {
            "4110216": {"type": "cc", "excluded": False},  # FxA CC
            "5376195": {"type": "cc", "excluded": False},  # FxB CC
        },
    }
    txns = [
        {
            "amount": -1000,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": GROCERIES_CAT, "title": "Groceries", "is_transfer": False},
        },
        {
            "amount": -500,
            "status": "posted",
            "transaction_account": {"id": 5376195},
            "category": {"id": DINING_CAT, "title": "Dining", "is_transfer": False},
        },
    ]
    partner_a = compute_cc_usage_by_category(
        "Fixture A", txns, two_partner_mappings, {"4110216"}, CC_PAYMENT_CAT_CC
    )
    partner_b = compute_cc_usage_by_category(
        "Fixture B", txns, two_partner_mappings, {"5376195"}, CC_PAYMENT_CAT_CC
    )
    assert partner_a == {"Groceries": 1000}
    assert partner_b == {"Dining": 500}


def test_compute_cc_usage_by_category_title_fallback_to_id():
    """Txn category without title â†’ str(cat_id) key; spend never dropped."""
    txns = [
        {
            "amount": -250,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": GROCERIES_CAT, "is_transfer": False},
        },
    ]
    result = compute_cc_usage_by_category(
        "Fixture A", txns, ACCOUNT_MAPPINGS, {"4110216"}, CC_PAYMENT_CAT_CC
    )
    assert result == {str(GROCERIES_CAT): 250}


# -- compute_budget_usage ----------------------------------------------------


def test_compute_budget_usage_excludes_cc_and_savings():
    txns = [
        {
            "amount": -500,
            "status": "posted",
            "transaction_account": {"id": 4110210},
            "category": {"id": 34025245},
        },
        {
            "amount": -300,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": 34025245},
        },
        {
            "amount": -200,
            "status": "posted",
            "transaction_account": {"id": 4110213},
            "category": {"id": 34025235},
        },
    ]
    result = compute_budget_usage("Fixture A", txns, ACCOUNT_MAPPINGS)
    # Only checking account: 500.
    assert result == 500


def test_compute_budget_usage_handles_null_category():
    """PS can send category=null â€” must not crash with NoneType.get().

    Regression: same root cause as compute_real_cc_bill null-category crash.
    """
    txns = [
        {
            "amount": -500,
            "status": "posted",
            "transaction_account": {"id": 4110210},
            "category": None,  # PS sends explicit null
        },
        {
            "amount": -300,
            "status": "posted",
            "transaction_account": {"id": 4110210},
            "category": {"id": 34025245},
        },
    ]
    # null-category txn: not CC-paydown (no id), not transfer â†’ counted as debit.
    # 500 + 300 = 800.
    result = compute_budget_usage("Fixture A", txns, ACCOUNT_MAPPINGS)
    assert result == 800


# -- per-partner CC bill filter (regression: identical values bug) ---------
#
# Root cause: compute_real_cc_bill / compute_estimated_cc_bill used to
# ignore the `partner` arg and sum BOTH partners' txns, so Fixture A and
# Fixture B got the same number. Fix: pass `partner_account_ids` set; the
# function only sums txns whose transaction_account.id is in the set.


CC_PAYMENT_CAT = 34025345


def test_compute_real_cc_bill_filters_by_partner_account_ids():
    """Fixture A's CC-side txns only â€” Fixture B's CC-side must NOT be included.

    CC-side = positive amounts on this partner's CC account.
    """
    txns = [
        {
            "amount": 1000,
            "status": "posted",
            "transaction_account": {"id": 4110216},  # FxA CC
            "category": {"id": CC_PAYMENT_CAT},
        },
        {
            "amount": 2000,
            "status": "posted",
            "transaction_account": {"id": 5376195},  # FxB CC
            "category": {"id": CC_PAYMENT_CAT},
        },
    ]
    two_partner_mappings = {
        "accounts": {
            "4110216": {"type": "cc", "excluded": False},
            "5376195": {"type": "cc", "excluded": False},
        },
    }
    # Without partner filter: 1000 + 2000 = 3000 (old buggy behavior).
    assert (
        compute_real_cc_bill("Fixture A", txns, two_partner_mappings, CC_PAYMENT_CAT)
        == 3000
    )
    # With Fixture A's account set: 1000 only.
    assert (
        compute_real_cc_bill(
            "Fixture A",
            txns,
            two_partner_mappings,
            CC_PAYMENT_CAT,
            partner_account_ids={"4110216"},
        )
        == 1000
    )
    # With Fixture B's account set: 2000 only.
    assert (
        compute_real_cc_bill(
            "Fixture B",
            txns,
            two_partner_mappings,
            CC_PAYMENT_CAT,
            partner_account_ids={"5376195"},
        )
        == 2000
    )


def test_compute_estimated_cc_bill_filters_by_partner_account_ids():
    """Same fix applies to the estimator â€” txns (both kinds) and the
    current-month envelope events must be filtered by partner."""
    # FxA CC 4110216, FxB CC 5376195, both type=cc.
    two_partner_mappings = {
        "accounts": {
            "4110216": {"type": "cc", "excluded": False},
            "5376195": {"type": "cc", "excluded": False},
        },
    }
    prior_txns = [
        {"amount": -800, "status": "posted", "transaction_account": {"id": 4110216}},
        {"amount": -500, "status": "posted", "transaction_account": {"id": 5376195}},
    ]
    prior_events = [
        {"amount": -200, "transaction_account": {"id": 4110216}},
        {"amount": -100, "transaction_account": {"id": 5376195}},
    ]
    # Future kind: events ignored entirely. Without filter: 800+500 = 1300
    # (old buggy behavior).
    assert (
        compute_estimated_cc_bill(
            "Fixture A",
            prior_txns,
            prior_events,
            two_partner_mappings,
            month_kind="future",
            today=date(2026, 9, 1),
        )
        == 1300
    )
    # Fixture A: 800 only.
    assert (
        compute_estimated_cc_bill(
            "Fixture A",
            prior_txns,
            prior_events,
            two_partner_mappings,
            None,
            {"4110216"},
            month_kind="future",
            today=date(2026, 9, 1),
        )
        == 800
    )
    # Fixture B: 500 only.
    assert (
        compute_estimated_cc_bill(
            "Fixture B",
            prior_txns,
            prior_events,
            two_partner_mappings,
            None,
            {"5376195"},
            month_kind="future",
            today=date(2026, 9, 1),
        )
        == 500
    )
    # Current kind: envelope events also filtered by partner.
    # Fixture A: 800 spend + 200 own envelope = 1000 (Fixture B's 100 excluded).
    assert (
        compute_estimated_cc_bill(
            "Fixture A",
            prior_txns,
            [
                {"amount": -200, "date": "2026-08-20", "transaction_account": {"id": 4110216}},
                {"amount": -100, "date": "2026-08-20", "transaction_account": {"id": 5376195}},
            ],
            two_partner_mappings,
            None,
            {"4110216"},
            month_kind="current",
            today=date(2026, 8, 15),
        )
        == 1000
    )


def test_compute_estimated_cc_bill_excludes_cc_payment_category():
    """CC-paydown txns (category "CC Payment (paired)") are cash moving
    from checking to card â€” not card spend. Excluding them keeps
    cc_spend = actual card purchases only."""
    # FxA CC 4110216, only one CC. Mapping keys it as cc.
    mappings = {"accounts": {"4110216": {"type": "cc", "excluded": False}}}
    # Card purchase: category=Spend, abs=1000.
    # CC-paydown: category=CC Payment (paired), abs=5000.
    # Without exclusion: 1000 + 5000 = 6000.
    # With exclusion: 1000 only.
    prior_txns = [
        {
            "amount": -1000,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": 99, "title": "Spend"},
        },
        {
            "amount": -5000,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": CC_PAYMENT_CAT, "title": "CC Payment (paired)"},
        },
    ]
    # Envelope event on the CC account, future-dated (for current-kind leg).
    prior_events = [
        {"amount": -200, "date": "2026-08-20", "transaction_account": {"id": 4110216}},
    ]
    # Without exclusion filter â€” old behavior (or category not yet known).
    assert (
        compute_estimated_cc_bill(
            "Fixture A",
            prior_txns,
            prior_events,
            mappings,
            None,
            {"4110216"},
            month_kind="future",
            today=date(2026, 9, 1),
        )
        == 1000 + 5000  # 6000
    )
    # With cc_payment_category_id â€” paydown excluded. Future kind: events
    # ignored â†’ spend only (1000).
    assert (
        compute_estimated_cc_bill(
            "Fixture A",
            prior_txns,
            prior_events,
            mappings,
            None,
            {"4110216"},
            CC_PAYMENT_CAT,
            month_kind="future",
            today=date(2026, 9, 1),
        )
        == 1000
    )
    # Current kind with exclusion: spend 1000 + envelope 200 = 1200.
    assert (
        compute_estimated_cc_bill(
            "Fixture A",
            prior_txns,
            prior_events,
            mappings,
            None,
            {"4110216"},
            CC_PAYMENT_CAT,
            month_kind="current",
            today=date(2026, 8, 15),
        )
        == 1000 + 200  # 1200
    )
    # No cc_payment_category_id passed â†’ keep all (caller chose to skip).
    assert (
        compute_estimated_cc_bill(
            "Fixture A",
            prior_txns,
            prior_events,
            mappings,
            None,
            None,
            month_kind="future",
            today=date(2026, 9, 1),
        )
        == 1000 + 5000
    )


def test_compute_estimated_cc_bill_future_ignores_matched_and_unmatched_buys():
    """Future month: estimate = prior posted spend, regardless of whether
    events match posted txns or not (the old bug shape: matched AND
    unmatched events both inflated the estimate).

    Posted 30,000 + event 5,000 (same date+amount as a posted txn) +
    event 2,000 (no posted txn) â†’ 30,000.
    """
    mappings = {"accounts": {"4110216": {"type": "cc", "excluded": False}}}
    prior_txns = [
        {
            "amount": -25000,
            "date": "2026-08-05",
            "status": "posted",
            "transaction_account": {"id": 4110216, "type": "credits"},
        },
        {
            "amount": -5000,
            "date": "2026-08-12",
            "status": "posted",
            "transaction_account": {"id": 4110216, "type": "credits"},
        },
    ]
    prior_events = [
        {
            "amount": -5000,
            "date": "2026-08-12",
            "transaction_account": {"id": 4110216, "type": "credits"},
        },
        {
            "amount": -2000,
            "date": "2026-08-20",
            "transaction_account": {"id": 4110216, "type": "credits"},
        },
    ]
    result = compute_estimated_cc_bill(
        "Fixture A",
        prior_txns,
        prior_events,
        mappings,
        None,
        {"4110216"},
        month_kind="future",
        today=date(2026, 9, 1),
    )
    # Posted spend only: 30,000. Events leg gone (not 32,000, not 37,000).
    assert result == 30000


def test_compute_estimated_cc_bill_hello_fresh_weekly_posts_all_ignored():
    """Realistic fixture: Hello Fresh scheduled 4x1,300 with 4 posted 1,300
    CC charges on the same dates â†’ future estimate = posted spend only."""
    mappings = {"accounts": {"4110216": {"type": "cc", "excluded": False}}}
    dates = ["2026-08-03", "2026-08-10", "2026-08-17", "2026-08-24"]
    prior_txns = [
        {
            "amount": -1300,
            "date": d,
            "status": "posted",
            "transaction_account": {"id": 4110216, "type": "credits"},
        }
        for d in dates
    ]
    prior_events = [
        {
            "amount": -1300,
            "date": d,
            "transaction_account": {"id": 4110216, "type": "credits"},
        }
        for d in dates
    ]
    result = compute_estimated_cc_bill(
        "Fixture A",
        prior_txns,
        prior_events,
        mappings,
        None,
        {"4110216"},
        month_kind="future",
        today=date(2026, 9, 1),
    )
    # Posted spend only: 4 * 1300 = 5200. Events ignored.
    assert result == 5200


# -- compute_future_estimated_cc_baseline (all-mâˆ’1, per-category max) --------


def _future_est_txns():
    return [
        # Groceries â€” free spend (no envelope in mâˆ’1) â†’ counts.
        {
            "amount": -3000,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": GROCERIES_CAT, "title": "Groceries", "is_transfer": False},
        },
        # Hello Fresh real spend 9,000 beats its 5,200 envelope (max wins).
        {
            "amount": -9000,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": 34025280, "title": "Hello Fresh", "is_transfer": False},
        },
        # CC paydown â†’ excluded.
        {
            "amount": -20000,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {
                "id": CC_PAYMENT_CAT_CC,
                "title": "CC Payment (paired)",
                "is_transfer": True,
            },
        },
        # Refund â†’ not spend (PR65 review).
        {
            "amount": 2500,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": {"id": GROCERIES_CAT, "title": "Groceries", "is_transfer": False},
        },
        # Uncategorized â†’ counts under the "Uncategorized" title.
        {
            "amount": -1200,
            "status": "posted",
            "transaction_account": {"id": 4110216},
            "category": None,
        },
    ]


def _future_est_events():
    return [
        # mâˆ’1 envelope: Hello Fresh 5,200.
        {
            "type": "buy",
            "amount": -5200,
            "category": {"id": 34025280, "title": "Hello Fresh", "is_transfer": False},
        },
    ]


def test_future_estimated_cc_bill_per_category_max_plus_free():
    result = compute_future_estimated_cc_bill(
        "Fixture A",
        _future_est_events(),
        _future_est_txns(),
        ACCOUNT_MAPPINGS,
        partner_account_ids={"4110216"},
        cc_payment_category_id=CC_PAYMENT_CAT_CC,
    )
    # max(5,200 envelope, 9,000 real) + 3,000 Groceries + 1,200 Uncategorized
    assert result == 13200


def test_future_estimated_cc_bill_no_txns_envelopes_only():
    result = compute_future_estimated_cc_bill(
        "Fixture A",
        _future_est_events(),
        [],
        ACCOUNT_MAPPINGS,
        partner_account_ids={"4110216"},
        cc_payment_category_id=CC_PAYMENT_CAT_CC,
    )
    # mâˆ’1 has no posted txns â†’ real terms 0, envelopes carry the estimate.
    assert result == 5200


def test_future_estimated_cc_bill_no_events_real_spend_only():
    result = compute_future_estimated_cc_bill(
        "Fixture A",
        [],
        _future_est_txns(),
        ACCOUNT_MAPPINGS,
        partner_account_ids={"4110216"},
        cc_payment_category_id=CC_PAYMENT_CAT_CC,
    )
    # 3,000 + 9,000 + 1,200 (refund + paydown excluded).
    assert result == 13200


# -- compute_scheduled_cc_bill (m+2 and beyond) ------------------------------


def test_scheduled_cc_bill_abs_sums_month_own_envelopes():
    """m+2+ estimate: plain abs-sum of the month's own buy envelopes."""
    buys = [
        {"amount": -1200, "type": "buy"},
        {"amount": -300, "type": "buy"},
        {"amount": 50, "type": "buy"},  # signed noise flattens to abs
    ]
    assert compute_scheduled_cc_bill("Fixture A", buys) == 1550


def test_scheduled_cc_bill_empty_is_zero():
    assert compute_scheduled_cc_bill("Fixture A", []) == 0.0


# -- compute_current_cc_bill_posted (current-month paydown truth) ------------


def _paydown_txns_paired():
    """Both PS legs of one paired CC payment sharing the paydown category."""
    return [
        # checking leg â€” the real paydown (counts)
        {
            "status": "posted",
            "amount": -5000,
            "transaction_account": {"id": 4110210},
            "category": {"id": CC_PAYMENT_CAT_CC},
        },
        # card leg of the same pair (must NOT double-count)
        {
            "status": "posted",
            "amount": 5000,
            "transaction_account": {"id": 4110216},
            "category": {"id": CC_PAYMENT_CAT_CC},
        },
    ]


def test_current_cc_bill_posted_counts_paired_payment_once():
    result = compute_current_cc_bill_posted(
        "Fixture A",
        _paydown_txns_paired(),
        ACCOUNT_MAPPINGS,
        CC_PAYMENT_CAT_CC,
        partner_account_ids={"4110210", "4110216"},
    )
    assert result == 5000


def test_current_cc_bill_posted_skips_positive_reversal_on_checking():
    txns = _paydown_txns_paired() + [
        # paydown refund on checking â€” positive, not a payment
        {
            "status": "posted",
            "amount": 700,
            "transaction_account": {"id": 4110210},
            "category": {"id": CC_PAYMENT_CAT_CC},
        },
    ]
    result = compute_current_cc_bill_posted(
        "Fixture A",
        txns,
        ACCOUNT_MAPPINGS,
        CC_PAYMENT_CAT_CC,
        partner_account_ids={"4110210"},
    )
    assert result == 5000


def test_current_cc_bill_posted_skips_pending_wrong_cat_excluded_account():
    mappings = {
        "accounts": {
            **ACCOUNT_MAPPINGS["accounts"],
            "9999999": {"type": "checking", "excluded": True},
        }
    }
    txns = [
        {
            "status": "pending",
            "amount": -900,
            "transaction_account": {"id": 4110210},
            "category": {"id": CC_PAYMENT_CAT_CC},
        },
        {
            "status": "posted",
            "amount": -900,
            "transaction_account": {"id": 4110210},
            "category": {"id": GROCERIES_CAT},
        },
        {
            "status": "posted",
            "amount": -900,
            "transaction_account": {"id": 9999999},
            "category": {"id": CC_PAYMENT_CAT_CC},
        },
    ]
    result = compute_current_cc_bill_posted(
        "Fixture A",
        txns,
        mappings,
        CC_PAYMENT_CAT_CC,
    )
    assert result == 0.0


# -- compute_net -------------------------------------------------------------


def test_compute_net_current_month():
    result = compute_net(
        salary=42000, bills=18000, estimated_cc_bill=9000, real_cc_bill=None
    )
    assert result == 42000 - 18000 - 9000


def test_compute_net_past_month_uses_real_cc_bill():
    result = compute_net(
        salary=42000, bills=18000, estimated_cc_bill=None, real_cc_bill=8500
    )
    assert result == 42000 - 18000 - 8500


# -- compute_status ----------------------------------------------------------


def test_compute_status_covered():
    assert (
        compute_status(
            salary=42000,
            bills=18000,
            estimated_cc_bill=9000,
            real_cc_bill=None,
            savings_balance=32000,
        )
        == "covered"
    )


def test_compute_status_partial():
    assert (
        compute_status(
            salary=25000,
            bills=18000,
            estimated_cc_bill=9000,
            real_cc_bill=None,
            savings_balance=5000,
        )
        == "partial"
    )


def test_compute_status_shortfall():
    assert (
        compute_status(
            salary=25000,
            bills=18000,
            estimated_cc_bill=9000,
            real_cc_bill=None,
            savings_balance=1000,
        )
        == "shortfall"
    )


# -- compute_real_bills -----------------------------------------------------
#
# Real bills = sum of posted checking-account debits, excluding:
# - CC-paydown transfers (category == cc_payment_category_id)
# - exclude-role categories (KPI role "exclude")
# - transfer categories (is_transfer=True)
# Restricted to partner_account_ids when provided.

CC_PAYMENT_CAT = 34025345
EXCLUDE_CAT = 34028575  # Personal Transfer (Fixture A)


def test_compute_real_bills_sums_posted_checking_debits():
    """Two posted checking debits â†’ sum of abs(amounts)."""
    txns = [
        {
            "amount": -500,
            "status": "posted",
            "transaction_account": {"id": 4110210},
            "category": {"id": 34025245, "is_transfer": False},
        },
        {
            "amount": -1200,
            "status": "posted",
            "transaction_account": {"id": 4110210},
            "category": {"id": 34025245, "is_transfer": False},
        },
    ]
    result = compute_real_bills(
        "Fixture A", txns, ACCOUNT_MAPPINGS, cc_payment_category_id=CC_PAYMENT_CAT
    )
    assert result == 1700


def test_compute_real_bills_drops_credits_and_excluded_accounts():
    """Positive amounts (credits) and excluded accounts must NOT count."""
    txns = [
        # Credit on checking â€” not a bill.
        {
            "amount": 1000,
            "status": "posted",
            "transaction_account": {"id": 4110210},
            "category": {"id": 34025485, "is_transfer": False},
        },
        # Debit on excluded account.
        {
            "amount": -500,
            "status": "posted",
            "transaction_account": {"id": 4110210},
            "category": {"id": 34025245, "is_transfer": False},
        },
    ]
    mappings = {
        "accounts": {
            "4110210": {"type": "checking", "excluded": True},  # excluded
        },
    }
    result = compute_real_bills(
        "Fixture A", txns, mappings, cc_payment_category_id=CC_PAYMENT_CAT
    )
    # Both dropped: excluded account, and credit on (excluded) account.
    assert result == 0


def test_compute_real_bills_excludes_cc_payment_category():
    """Bills-side CC paydown (cat 34025345) is a transfer to card, not a bill."""
    txns = [
        {
            "amount": -5000,
            "status": "posted",
            "transaction_account": {"id": 4110210},
            "category": {"id": CC_PAYMENT_CAT, "is_transfer": False},
        },
        {
            "amount": -800,
            "status": "posted",
            "transaction_account": {"id": 4110210},
            "category": {"id": 34025245, "is_transfer": False},
        },
    ]
    result = compute_real_bills(
        "Fixture A", txns, ACCOUNT_MAPPINGS, cc_payment_category_id=CC_PAYMENT_CAT
    )
    # Only the second txn counts: 800.
    assert result == 800
    # Without exclusion: 5800 (old buggy behavior).
    assert (
        compute_real_bills(
            "Fixture A",
            txns,
            ACCOUNT_MAPPINGS,
            cc_payment_category_id=None,
        )
        == 5800
    )


def test_compute_real_bills_excludes_exclude_role_categories():
    """KPI role 'exclude' categories (e.g. personal transfers) are noise, not bills."""
    txns = [
        {
            "amount": -700,
            "status": "posted",
            "transaction_account": {"id": 4110210},
            "category": {"id": EXCLUDE_CAT, "is_transfer": False},
        },
        {
            "amount": -300,
            "status": "posted",
            "transaction_account": {"id": 4110210},
            "category": {"id": 34025245, "is_transfer": False},
        },
    ]
    result = compute_real_bills(
        "Fixture A",
        txns,
        ACCOUNT_MAPPINGS,
        cc_payment_category_id=CC_PAYMENT_CAT,
        exclude_category_ids={EXCLUDE_CAT},
    )
    # 700 excluded, 300 kept.
    assert result == 300


def test_compute_real_bills_excludes_transfers():
    """is_transfer=True categories (e.g. savings/own-account) drop out."""
    txns = [
        {
            "amount": -2000,
            "status": "posted",
            "transaction_account": {"id": 4110210},
            "category": {"id": 34025235, "is_transfer": True},  # Savings
        },
        {
            "amount": -150,
            "status": "posted",
            "transaction_account": {"id": 4110210},
            "category": {"id": 34025245, "is_transfer": False},
        },
    ]
    result = compute_real_bills(
        "Fixture A", txns, ACCOUNT_MAPPINGS, cc_payment_category_id=CC_PAYMENT_CAT
    )
    # Savings transfer dropped, real bill kept.
    assert result == 150


def test_compute_real_bills_filters_by_partner():
    """partner_account_ids restricts to one partner's accounts only."""
    txns = [
        # FxA Checking debit.
        {
            "amount": -1000,
            "status": "posted",
            "transaction_account": {"id": 4110210},
            "category": {"id": 34025245, "is_transfer": False},
        },
        # FxB Checking debit.
        {
            "amount": -2500,
            "status": "posted",
            "transaction_account": {"id": 5376190},
            "category": {"id": 34025245, "is_transfer": False},
        },
    ]
    # Fixture A: 1000 only.
    assert (
        compute_real_bills(
            "Fixture A",
            txns,
            ACCOUNT_MAPPINGS,
            cc_payment_category_id=CC_PAYMENT_CAT,
            partner_account_ids={"4110210"},
        )
        == 1000
    )
    # Fixture B: 2500 only.
    assert (
        compute_real_bills(
            "Fixture B",
            txns,
            ACCOUNT_MAPPINGS,
            cc_payment_category_id=CC_PAYMENT_CAT,
            partner_account_ids={"5376190"},
        )
        == 2500
    )


# -- budget_usage: per-partner isolation (partner leak fix) --------------------


def test_compute_budget_usage_partner_isolation():
    """Fixture A and Fixture B must get DIFFERENT budget_usage -- not household sum.

    Bug (2026-08): compute_budget_usage filtered to checking accounts but
    not to the partner's accounts -> both partners got the household total
    (56695.71 in Aug production). partner_account_ids scopes the sum.
    """
    txns = [
        {
            "amount": -1000,
            "status": "posted",
            "transaction_account": {"id": 4110210},  # FxA Check
            "category": {"id": 34025245, "is_transfer": False},
        },
        {
            "amount": -250,
            "status": "posted",
            "transaction_account": {"id": 4110210},  # FxA Check
            "category": {"id": 34025245, "is_transfer": False},
        },
        {
            "amount": -7000,
            "status": "posted",
            "transaction_account": {"id": 5376190},  # FxB Check
            "category": {"id": 34025245, "is_transfer": False},
        },
    ]
    fxa_ids = {"4110210", "4110213", "4110216"}
    fxb_ids = {"5376190"}
    fxa_result = compute_budget_usage(
        "Fixture A", txns, ACCOUNT_MAPPINGS, None, fxa_ids
    )
    fxb_result = compute_budget_usage("Fixture B", txns, ACCOUNT_MAPPINGS, None, fxb_ids)
    assert fxa_result == 1250
    assert fxb_result == 7000
    # The leak: both used to equal the household sum (8250).
    assert fxa_result != fxb_result


def test_compute_budget_usage_no_partner_scope_is_household():
    """Without partner_account_ids, household sum (documented caller mistake)."""
    txns = [
        {
            "amount": -1000,
            "status": "posted",
            "transaction_account": {"id": 4110210},  # FxA Check
            "category": {"id": 34025245, "is_transfer": False},
        },
        {
            "amount": -7000,
            "status": "posted",
            "transaction_account": {"id": 5376190},  # FxB Check
            "category": {"id": 34025245, "is_transfer": False},
        },
    ]
    result = compute_budget_usage("Fixture A", txns, ACCOUNT_MAPPINGS)
    assert result == 8000
