"""F2-BE bills event classifier — bucketing + CC-payment + buy matching.

Pure functions. No I/O. Tested in isolation.
"""

from __future__ import annotations

from typing import Any, Literal

Bucket = Literal["bill", "buy", "savings", "salary", "excluded"]


def resolve_event_account_id(
    event: dict[str, Any],
    account_catalog: list[dict[str, Any]] | None = None,
) -> str:
    """Return the transaction_account.id for an event.

    PS `/users/{id}/events` returns `scenario.account_id` (bank account id).
    account_mappings + downstream code use transaction_account.id.
    Walk catalog to translate bank_id → transaction_account.id.

    Falls back to `event.transaction_account.id` for tests / fixtures that
    already use the right shape. Returns "" if neither resolves.
    """
    scenario = event.get("scenario") or {}
    bank_id = scenario.get("account_id")
    if bank_id is not None and account_catalog:
        for acct in account_catalog:
            if acct.get("account_id") == bank_id:
                return str(acct.get("id", ""))
    txn_acct = event.get("transaction_account") or {}
    if txn_acct.get("id") is not None:
        return str(txn_acct["id"])
    return ""


def classify_event(
    event: dict[str, Any],
    account_mappings: dict[str, Any],
    category_roles: dict[str, Any],
    account_catalog: list[dict[str, Any]] | None = None,
    savings_category_id: int | None = None,
) -> Bucket:
    """Bucket a PS event by transaction account type + local mapping override.

    Rules (per f2-bills-sync.md L1 capability #6):
    - excluded=true account → "excluded"
    - no local type override → "excluded"
    - is_transfer=true category → "excluded"
    - (checking, spend) → "bill"
    - (cc, spend) → "buy"
    - (savings, savings) → "savings"
    - (checking, income) → "salary"
    - anything else → "excluded"

    `account_catalog` is used to translate real PS event shape
    (scenario.account_id) into the transaction_account.id the mappings use.
    """
    accounts = account_mappings.get("accounts", {})
    account_id = resolve_event_account_id(event, account_catalog)
    mapping = accounts.get(account_id, {})

    # Excluded account → invisible.
    if mapping.get("excluded", True):
        return "excluded"

    local_type = mapping.get("type")
    if local_type is None:
        return "excluded"

    # Category role lookup.
    category_id = event.get("category", {}).get("id")
    if category_id is None:
        return "excluded"

    # Savings category for this partner → bucket as "savings" regardless
    # of is_transfer on the parent category (PS marks the parent "Savings"
    # as is_transfer=true, but the per-partner child like "Sparekonto
    # (Fixture A)" has is_transfer=false and IS the savings event).
    if savings_category_id is not None and int(category_id) == int(savings_category_id):
        return "savings"

    category_id_str = str(category_id)
    role = category_roles.get(category_id_str, "spend")

    # Transfer categories → excluded (only non-savings transfers).
    category = event.get("category", {})
    if category.get("is_transfer", False):
        return "excluded"

    # Bucket by (local_type, role).
    if local_type == "checking" and role == "spend":
        return "bill"
    # CC account: any non-transfer, non-savings role is a scheduled CC buy
    # (user 2026-08-30: "include ALL scheduled cc buys" — personal_spend
    # categories like Charity/Memberships (Personal) on the card are still
    # card spend paid by next month's salary).
    if local_type == "cc" and role in ("spend", "personal_spend"):
        return "buy"
    if local_type == "savings" and role == "savings":
        return "savings"
    if local_type == "checking" and role == "income":
        return "salary"
    return "excluded"


def is_cc_payment(
    event: dict[str, Any],
    cc_payment_category_id: int,
) -> bool:
    """True if this event is a bills-side CC-paydown transaction.

    Checks: category id matches the per-partner CC payments category.
    The caller resolves cc_payment_category_id per partner.
    """
    category = event.get("category", {})
    return category.get("id") == cc_payment_category_id


def match_scheduled_buys(
    events: list[dict[str, Any]],
    transactions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Match scheduled CC buys against real CC transactions by (date, amount).

    Returns a NEW list of events with is_matched populated.
    Pure function — does not mutate the input.

    Only type=buy events get is_matched. Other events get is_matched=None.
    """
    # Build a set of (date, abs_amount) from posted CC transactions.
    cc_txns: set[tuple[str, float]] = set()
    for txn in transactions:
        txn_account = txn.get("transaction_account", {})
        if txn_account.get("type") == "credits":
            date = txn.get("date", "")
            amount = abs(txn.get("amount", 0))
            cc_txns.add((date, amount))

    result: list[dict[str, Any]] = []
    for event in events:
        new_event = dict(event)
        # is_matched only meaningful on buy events.
        # The caller sets type on the event before calling this.
        if new_event.get("type") == "buy":
            date = new_event.get("date", "")
            amount = abs(new_event.get("amount", 0))
            new_event["is_matched"] = (date, amount) in cc_txns
        else:
            new_event["is_matched"] = None
        result.append(new_event)

    return result
