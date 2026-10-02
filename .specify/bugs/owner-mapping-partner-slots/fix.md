# Bug Fix: Report generation fails with custom partner IDs

- **Slug**: owner-mapping-partner-slots
- **Fixed**: 2026-09-29T20:26:00+02:00
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

`_load_account_owners()` now derives v4_pipeline owner slots (`partner_a` /
`partner_b`) deterministically from sorted custom partner IDs instead of only
recognizing the literal legacy strings, so report generation works with
depersonalized `account_mappings.json` files.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `src/budget_api/services/report_builder.py` | modified | `_load_account_owners()`: collect partner IDs from the `partners` block plus account `partner_id` values, sort, map first two to `partner_a`/`partner_b` (mirrors `bills_builder._partner_slot_map` ordering semantics) |
| `src/budget_api/tests/test_report_builder.py` | added tests | New `TestLoadAccountOwners` class, 8 tests |

## Diff Highlights

```python
# before
if partner_id in ("partner_a", "partner_b"):
    owners[acc_id] = partner_id

# after
slots = {
    pid: f"partner_{chr(ord('a') + i)}"
    for i, pid in enumerate(sorted(partner_ids))
    if i < 2
}
if partner_id in slots:
    owners[acc_id] = slots[partner_id]
```

## Tests Added or Updated

- `test_custom_partner_ids_map_to_sorted_slots` — christian/rasma regression for the reported error
- `test_custom_ids_without_partners_block` — slot derivation from account `partner_id` values alone
- `test_legacy_partner_ids_unchanged` — legacy `partner_a`/`partner_b` files map identically
- `test_deterministic_regardless_of_key_order` — JSON key order independence
- `test_third_partner_excluded` — two-owner cap degrades loudly, not silently
- `test_missing_file_returns_empty` / `test_malformed_file_returns_empty` — degenerate behavior preserved
- `test_build_report_with_custom_partner_ids` — end-to-end generation succeeds with custom IDs

## Local Verification

- `uv run pytest src/budget_api/tests/test_report_builder.py -q` → 32 passed
- `uv run pytest src/budget_api/tests -q` → 575 passed (full backend suite, covers PDF/mega consumers)
- Live manual check: POST /api/reports/monthly/2026-09/generate against real
  data (`partners: christian/rasma`) → status `success`, previously `failed`
  with `transactions[0] has no account-ID owner mapping`.

## Deviations from Assessment

None.

## Follow-ups

- Consider extracting the sorted-partner-ID → slot derivation into a shared
  helper (currently duplicated logic between `bills_builder._partner_slot_map`
  and `_load_account_owners`) — left out of this fix per minimal-change scope.
- `GET /api/sync/status` and `/api/category-mappings` 404s seen in dev logs
  are unrelated (not-yet-synced state), not part of this bug.
