# Bug Isolation

## Affected Component
Backend (Python) — F2-BE bills snapshot builder + event classifier.

## Affected Files
- `src/budget_api/services/bills_builder.py` — orchestrates classification +
  derivation. Two sites: line 257 (per-partner account filter) and
  line 245 (partner_account_ids set).
- `src/budget_api/services/bills_classifier.py` — pure bucketing fn, line 47
  reads wrong key.
- `src/budget_api/services/bills_derivations.py` — uses
  `event.get("transaction_account", {}).get("id", "")` for prior-events CC bill
  computation. Affected for prior months too.

## Root Cause Location
- File: `src/budget_api/services/bills_builder.py`
- Line: 257
- Function: `build_bills_snapshot`
- Explanation: `event_acct_id` is `""` because real events have
  `scenario.account_id` (underlying bank), not `transaction_account.id`
  (transaction_account). The empty string is not in any partner's
  `partner_account_ids` set, so every event is dropped before classification.

Secondary root cause:
- File: `src/budget_api/services/bills_classifier.py`
- Line: 47
- Function: `classify_event`
- Explanation: same wrong key. Even if a buggy caller passed an event through,
  the classifier would still produce bucket=`"excluded"`.

## Diagnosis
- Bug type: Integration mismatch (PS API contract vs fabricated test fixtures)
- Root cause: PS `/users/{id}/events` returns `scenario.account_id` (bank
  account id). Code + tests assume `transaction_account.id` (transaction_account
  id, used as mapping key). Identity gap: same number space? No — different
  number systems. Mapping needs catalog lookup.
- Similar patterns: `bills_derivations.py` `compute_estimated_cc_bill` reads
  same key. Will also mis-compute prior CC bills. **Out of scope for THIS bug**
  (prior months are past → use real_cc_bill, not estimated). But a shared fix
  is cleaner.
- Cascading effects:
  - bills_count / buys_count always 0 in current month.
  - mapSnapshotToEvents in client returns empty → BillsPage shows no events.
  - `is_matched` and `is_cc_payment` always false.

## Proposed Fix (design — not yet implemented)

Add a single helper in bills_classifier.py:

```python
def resolve_event_account_id(
    event: dict, account_catalog: list[dict]
) -> str:
    """Return the transaction_account.id for an event.

    PS events have scenario.account_id (bank account). The mapping
    + classifier need transaction_account.id. Walk the catalog to translate.
    Falls back to event.transaction_account.id for tests/fixtures that
    already use the right shape.
    """
    scenario = event.get("scenario") or {}
    bank_id = scenario.get("account_id")
    if bank_id is not None:
        for acct in account_catalog:
            if acct.get("account_id") == bank_id:
                return str(acct["id"])
    txn_acct = event.get("transaction_account") or {}
    if txn_acct.get("id") is not None:
        return str(txn_acct["id"])
    return ""
```

Then wire it into:
- `bills_builder.build_bills_snapshot` — pass account_catalog into the
  per-partner loop, use `resolve_event_account_id` instead of raw
  `event.transaction_account.id` access.
- `bills_classifier.classify_event` — same swap. Needs account_catalog
  parameter. Existing test fixtures pass `transaction_account.id` directly,
  so the fallback path keeps them green.
- `bills_derivations.compute_estimated_cc_bill` — same swap (only matters
  for future months; future is out of scope but fix is one-line).

Test additions:
- `test_builder.py::test_real_ps_event_shape_uses_catalog_lookup` — pass
  a real-shaped event with `scenario.account_id` + matching catalog entry,
  assert it lands in the right partner.
- `test_classifier.py::test_classify_event_with_scenario_account_id` —
  same.

## Verification Plan
1. Re-run repro script. Assert `events_kept_after_filter == 5`.
2. Assert Fixture A partner has 3 events (1 salary + 2 mortgage).
3. Assert Fixture B partner has 2 events (1 salary + 1 mortgage).
4. Assert `bills_count: 3`, `buys_count: 0`, salary derivations non-zero.
5. Existing tests stay green (fallback path covers fabricated `transaction_account`).