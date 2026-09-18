"""F2-BE bills classifier tests — bucketing + CC-payment + buy matching."""

from __future__ import annotations

from budget_api.services.bills_classifier import (
    classify_event,
    is_cc_payment,
    match_scheduled_buys,
)

# -- Test fixtures -----------------------------------------------------------

ACCOUNT_MAPPINGS = {
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
        "4629234": {
            "name": "Pension",
            "partner_id": "partner_a",
            "type": None,
            "excluded": True,
        },
    },
}

CATEGORY_ROLES = {
    "2100013": "income",
    "2100003": "spend",
    "2100001": "savings",
    "2100011": "spend",  # CC Payment (paired)
}

CC_PAYMENT_CATEGORY_ID = 2100011


def _event(
    account_id: int, category_id: int, is_transfer: bool = False, amount: float = -100
) -> dict:
    return {
        "transaction_account": {
            "id": account_id,
            "type": "bank" if account_id != 1100003 else "credits",
        },
        "category": {"id": category_id, "is_transfer": is_transfer},
        "amount": amount,
        "date": "2026-07-15",
    }


# -- classify_event tests ----------------------------------------------------


def test_classify_bill_on_checking_account():
    event = _event(1100001, 2100003)
    assert classify_event(event, ACCOUNT_MAPPINGS, CATEGORY_ROLES) == "bill"


def test_classify_buy_on_credits_account():
    event = _event(1100003, 2100003)
    assert classify_event(event, ACCOUNT_MAPPINGS, CATEGORY_ROLES) == "buy"


def test_classify_personal_spend_on_cc_is_buy():
    """PR65: CC account + personal_spend role (Charity, Memberships
    (Personal)) = scheduled CC buy — the card spend is paid with next
    month's salary like any other buy."""
    roles = {**CATEGORY_ROLES, "2100015": "personal_spend"}
    event = _event(1100003, 2100015)
    assert classify_event(event, ACCOUNT_MAPPINGS, roles) == "buy"


def test_classify_personal_spend_on_checking_stays_excluded():
    """Same personal_spend role on a non-CC account must NOT become a
    bill — behavior unchanged for checking/savings."""
    roles = {**CATEGORY_ROLES, "2100015": "personal_spend"}
    event = _event(1100001, 2100015)
    assert classify_event(event, ACCOUNT_MAPPINGS, roles) == "excluded"


def test_classify_savings_on_savings_account():
    event = _event(1100002, 2100001)
    assert classify_event(event, ACCOUNT_MAPPINGS, CATEGORY_ROLES) == "savings"


def test_classify_partner_savings_category_overrides_is_transfer():
    """Real PS shape: savings transfer txns have is_transfer=False on the
    child category, but the parent "Savings" category has is_transfer=True.
    With per-partner savings_category_id, the event buckets as 'savings'
    even if the parent is_transfer was true."""
    # is_transfer=True (parent), but category id matches partner savings.
    event = _event(1100001, 2100014, is_transfer=True)
    assert (
        classify_event(
            event,
            ACCOUNT_MAPPINGS,
            CATEGORY_ROLES,
            savings_category_id=2100014,
        )
        == "savings"
    )


def test_classify_partner_savings_category_only_for_matching_partner():
    """If event category id matches a DIFFERENT partner's savings category,
    do NOT bucket as savings — fall through to the normal rules.

    CATEGORY_ROLES treats 2100010 as spend → on a checking account it
    buckets as 'bill', not 'savings'. Confirms the per-partner id check
    didn't over-fire.
    """
    # Category 2100010 is Fixture B's savings; event is on Fixture A's account.
    event = _event(1100001, 2100010, is_transfer=False)
    result = classify_event(
        event,
        ACCOUNT_MAPPINGS,
        CATEGORY_ROLES,
        savings_category_id=2100014,  # Fixture A's id (different)
    )
    # Falls through to normal rules: checking + spend → "bill".
    assert result == "bill"


def test_classify_no_savings_category_id_falls_back_to_old_rules():
    """Without savings_category_id param, transfer categories still excluded."""
    event = _event(1100001, 2100001, is_transfer=True)
    assert (
        classify_event(event, ACCOUNT_MAPPINGS, CATEGORY_ROLES) == "excluded"
    )


def test_classify_salary_income_on_checking():
    event = _event(1100001, 2100013, amount=42000)
    assert classify_event(event, ACCOUNT_MAPPINGS, CATEGORY_ROLES) == "salary"


def test_classify_excluded_on_excluded_account():
    event = _event(4629234, 2100003)
    assert classify_event(event, ACCOUNT_MAPPINGS, CATEGORY_ROLES) == "excluded"


def test_classify_excluded_on_transfer_category():
    event = _event(1100001, 2100003, is_transfer=True)
    assert classify_event(event, ACCOUNT_MAPPINGS, CATEGORY_ROLES) == "excluded"


def test_classify_excluded_on_unmapped_bank_account():
    event = _event(9999999, 2100003)
    assert classify_event(event, ACCOUNT_MAPPINGS, CATEGORY_ROLES) == "excluded"


# -- is_cc_payment tests ----------------------------------------------------


def test_is_cc_payment_true_on_matching_category():
    event = _event(1100001, CC_PAYMENT_CATEGORY_ID)
    assert is_cc_payment(event, CC_PAYMENT_CATEGORY_ID) is True


def test_is_cc_payment_false_on_other_category():
    event = _event(1100001, 2100003)
    assert is_cc_payment(event, CC_PAYMENT_CATEGORY_ID) is False


# -- match_scheduled_buys tests ----------------------------------------------


def test_match_scheduled_buys_finds_match_by_date_amount():
    events = [
        {"type": "buy", "date": "2026-07-15", "amount": -500},
        {"type": "bill", "date": "2026-07-20", "amount": -1000},
    ]
    transactions = [
        {
            "date": "2026-07-15",
            "amount": -500,
            "transaction_account": {"type": "credits"},
            "status": "posted",
        },
    ]
    result = match_scheduled_buys(events, transactions)
    assert result[0]["is_matched"] is True
    assert result[1]["is_matched"] is None


def test_match_scheduled_buys_no_match_returns_false():
    events = [
        {"type": "buy", "date": "2026-07-15", "amount": -500},
    ]
    transactions = [
        {
            "date": "2026-07-16",
            "amount": -500,
            "transaction_account": {"type": "credits"},
            "status": "posted",
        },
    ]
    result = match_scheduled_buys(events, transactions)
    assert result[0]["is_matched"] is False


def test_match_scheduled_buys_does_not_mutate_input():
    events = [
        {"type": "buy", "date": "2026-07-15", "amount": -500},
    ]
    transactions: list[dict] = []
    original = [dict(e) for e in events]
    match_scheduled_buys(events, transactions)
    assert events == original  # input not mutated


# -- resolve_event_account_id + real PS event shape -------------------------
#
# Real PS `/users/{id}/events` returns `scenario.account_id` (bank account id),
# not `transaction_account.id` (the transaction_account id mappings use).
# These tests pin the catalog-lookup behavior so the bug can't regress.

from budget_api.services.bills_classifier import resolve_event_account_id

ACCOUNT_CATALOG = [
    {"id": 1100001, "account_id": 4004538, "type": "bank"},
    {"id": 1100003, "account_id": 4004544, "type": "credits"},
    {"id": 1100002, "account_id": 4004541, "type": "bank"},
]


def _real_ps_event(
    bank_account_id: int, category_id: int, amount: float = -100
) -> dict:
    """Mimic real PS /users/{id}/events shape: scenario.account_id only."""
    return {
        "id": "series-123",
        "date": "2026-08-15",
        "amount": amount,
        "scenario": {
            "id": 4137024,
            "account_id": bank_account_id,
            "title": "Some scenario",
        },
        "category": {
            "id": category_id,
            "title": "x",
            "is_transfer": False,
        },
    }


def test_resolve_event_account_id_translates_scenario_via_catalog():
    """scenario.account_id=4004538 (bank) → 1100001 (transaction_account)."""
    event = _real_ps_event(4004538, 2100003)
    assert resolve_event_account_id(event, ACCOUNT_CATALOG) == "1100001"


def test_resolve_event_account_id_falls_back_to_transaction_account():
    """Test/fabricated shape (transaction_account.id) still resolves."""
    event = {
        "transaction_account": {"id": 1100001, "type": "bank"},
        "category": {"id": 2100003},
    }
    assert resolve_event_account_id(event, ACCOUNT_CATALOG) == "1100001"


def test_resolve_event_account_id_falls_back_when_no_catalog():
    """If catalog not provided and event has transaction_account, still works."""
    event = {
        "transaction_account": {"id": 1100001, "type": "bank"},
        "category": {"id": 2100003},
    }
    assert resolve_event_account_id(event) == "1100001"


def test_resolve_event_account_id_empty_when_unresolvable():
    """No scenario, no transaction_account → empty string."""
    event = {"id": "x", "amount": -100}
    assert resolve_event_account_id(event, ACCOUNT_CATALOG) == ""


def test_classify_real_ps_event_uses_catalog_lookup():
    """Regression: real PS event shape (scenario.account_id) must bucket
    into 'bill' for a checking account, not be silently dropped as 'excluded'."""
    event = _real_ps_event(4004538, 2100003, amount=-15000)  # Mortgage spend
    bucket = classify_event(event, ACCOUNT_MAPPINGS, CATEGORY_ROLES, ACCOUNT_CATALOG)
    assert bucket == "bill"


def test_classify_real_ps_salary_event_uses_catalog_lookup():
    """Salary event on Fixture A's checking account → 'salary' bucket."""
    event = _real_ps_event(4004538, 2100013, amount=48111)  # Salary income
    bucket = classify_event(event, ACCOUNT_MAPPINGS, CATEGORY_ROLES, ACCOUNT_CATALOG)
    assert bucket == "salary"
