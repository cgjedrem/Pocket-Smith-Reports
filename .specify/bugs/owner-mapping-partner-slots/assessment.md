# Bug Assessment: Report generation fails with custom partner IDs

- **Slug**: owner-mapping-partner-slots
- **Created**: 2026-09-29T20:25:00+02:00
- **Source**: pasted text (live repro in dev UI during session)
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

Observed in dev: generating the monthly report for 2026-09 via the UI fails with
`transactions[0] has no account-ID owner mapping`, persisted in
`data/private/2026-09_monthly_report_status.json` (`status: failed`). Other
months (e.g. 2027-09) succeed.

## Symptom

Monthly/mega report generation aborts immediately when transaction[0] belongs
to an account whose `partner_id` in `account_mappings.json` is a custom slug
(e.g. `christian`, `rasma`) instead of the legacy placeholders `partner_a` /
`partner_b`. Expected: any configured partner_id maps deterministically to a
depersonalized owner slot.

## Reproduction

1. Set up `data/private/account_mappings.json` with custom partners
   (`partners.christian`, `partners.rasma`) and accounts referencing
   `partner_id: "christian"` / `"rasma"` (created via POST /api/partners).
2. Sync transactions (e.g. month 2026-09).
3. POST /api/reports/monthly/2026-09/generate from the client.
4. Status goes `failed` with `transactions[0] has no account-ID owner mapping`.

## Suspected Code Paths

- `src/budget_api/services/report_builder.py:110 _load_account_owners()` — the bridge that converts budget_api `partner_id` schema → v4_pipeline owner schema; only copies `partner_id` values equal to the literal strings `"partner_a"`/`"partner_b"`, silently dropping every custom partner. **Root cause.**
- `src/v4_pipeline/accounting.py:normalize_transactions()` — raises `AccountingValidationError("transactions[{index}] has no account-ID owner mapping")` when `owners.get(account_id)` is None and the record isn't a synthetic fixture. The validator is behaving correctly; it's fed an empty owner map.
- `src/budget_api/services/bills_builder.py:_partner_slot_map()` — existing precedent: deterministic sorted-partner_id → slot `a`/`b` mapping used by the bills feature.
- `src/budget_api/services/report_pdf.py` and `services/mega_builder.py` — both consume `_load_account_owners()` and are affected the same way.

## Root Cause Hypothesis

Confidence: **high**.

The depersonalization work (001-depersonalize-identifiers) replaced fixed
`partner_a`/`partner_b` identities with user-defined partner IDs plus labels.
The bills feature was updated to handle this (`_partner_slot_map` derives
display slots a/b from sorted partner IDs), but `_load_account_owners()` in
`report_builder.py` was left filtering on the legacy literal strings. With a
mapping file using custom IDs, the bridge returns `{}`, so the first
non-synthetic transaction fails validation. Months whose transaction[0]
happened to be excluded/transfer-free could appear to work if every raw event
lands on the empty-or-miss path differently; in practice any month fails as
soon as a real transaction is normalized with an empty owner map.

## Proposed Remediation

**Preferred**: Reuse the canonical slot derivation in `_load_account_owners()`:
collect partner IDs from `account_mappings.json` (`partners` block, falling
back to account `partner_id` values), sort them for deterministic order, map
first → `partner_a`, second → `partner_b` (extra partners after the cap are
left unmapped, consistent with the bills slot-`""` degradation: transactions
on such accounts will fail loudly rather than be silently misassigned — the
two-owner pipeline can't represent them anyway). This mirrors
`_partner_slot_map`'s ordering semantics ("identity-neutral ordering key").

Keep the explicit legacy behavior: an account whose `partner_id` is already
`partner_a`/`partner_b` continues to work — with exactly two partners
(`partner_a`, `partner_b`) the sorted mapping is identical, so legacy files
are unchanged.

**Alternatives**:
- Accept `account_owners` translation inside v4_pipeline instead — wider blast
  radius; rejected (pipeline should stay slot-native).
- Keep literal-only filter and force users to rename partner IDs — breaks the
  depersonalized-labels feature the repo just shipped; rejected.

**Files likely to change**:
- `src/budget_api/services/report_builder.py` (`_load_account_owners`)
- `src/budget_api/tests/reports/` (new/updated tests, e.g. `test_report_builder.py` / acceptance)

**Tests to add or update**:
- Custom partner IDs (`alice`/`bob`) → owners map contains their accounts as
  partner_a (sorted-first) / partner_b (sorted-second); report generation for
  a fixture month succeeds.
- Legacy `partner_a`/`partner_b` partner IDs → unchanged output (regression).
- Missing mapping file / malformed file → still `{}` (existing degenerate
  behavior preserved).
- Determinism: same input → same slot assignment regardless of JSON key order.

## Risks & Considerations

- Slot assignment is by sorted partner ID; if existing stored monthly reports
  were generated with legacy `partner_a`/`partner_b` files, regenerating them
  under a custom-ID mapping could swap which partner renders as "A" vs "B" if
  the custom IDs sort differently. Acceptable: regeneration is explicit and
  labels follow the pipeline slots, so display stays consistent within any
  single mapping.
- `report_pdf.py` and `mega_builder.py` share `_load_account_owners()` — one
  change fixes all three consumers (PDF export, mega reports).
- No API contract changes; error path stays loud and specific.

## Open Questions

- None — reproduction confirmed live in session (2026-09 status file shows the
  exact error; mapping file uses `christian`/`rasma`).
