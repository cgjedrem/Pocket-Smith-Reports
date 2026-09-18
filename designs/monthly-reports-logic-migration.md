# Monthly Reports — Business Logic Migration to Backend (APPROVED L1–L5)

## What this sub-feature is

Move ALL monthly-report business logic from the frontend
(`client/src/components/reports/*`) to the backend (`src/v4_pipeline/accounting.py`
+ `src/budget_api/services/report_builder.py`), under a strict split: backend
owns all domain math, derived booleans, sign enums, and section routing;
frontend keeps only `toLocaleString` formatting, chart geometry, and Tailwind
classes keyed off server-provided enums.

Today `DetailedSections.tsx` (~900 lines) re-derives grouping, category
aggregation (`legacyCategoryGroups` duplicates `accounting.py:_aggregate`),
paired-reimbursement matching, percentage math, and section routing in TS.
This is the divergence risk the migration eliminates.

## Related docs

- `designs/f2-bills-ui.md` (L1–L3 precedent), `designs/f2-bills-dashboard.md` (L4–L5 precedent)
- Explorer map: `DetailedSections.tsx`, `KpiRoleSummary.tsx`, `client/src/types/report.ts`,
  `client/src/api/reports.ts`, `routers/reports.py`, `services/report_builder.py`,
  `v4_pipeline/accounting.py`, `budget_api/models/reports.py`

# L1 — Capabilities (APPROVED)

## In-scope

- Strict split (Q1): every domain derivation moves server-side — section
  grouping/routing, category aggregation, paired reimbursements, all
  percentages (row/household/savings-rate/personal-share), `balanced` flag,
  sign enums (`pos`/`neg`/`zero`) for all money fields.
- Monthly reports only (Q2): Mega and Bills keep their own pipelines; this
  validates the fat-DTO pattern before any deliberate replication.
- Dead-code removal (Q3): delete never-imported frontend components
  `CategoryHighlights.tsx`, `SubcategoryOverviews.tsx`,
  `TransactionDrilldowns.tsx` AND their backend ports
  (`_category_highlights`, `_subcategory_overviews`, `_transaction_drilldowns`
  in `report_builder.py`) plus the DTO fields they feed.
- Contract bump (Q4): `CALCULATION_VERSION` 4→5. Stored reports go stale
  lazily (existing staleness gate at `report_builder.py:380`); user
  regenerates per month. No bulk migration, no auto-fetch.

## Out-of-scope

- Mega reports, Bills dashboard, MoM pipeline, sync stages.
- PDF rendering path changes (consumes same contract; must keep working).
- Sign-convention cleanup (paid-negative stays — see L4 Q3).
- `fmt()` duplication consolidation beyond what section rewrites touch.

## Success criteria

- Zero financial math / grouping / routing / sign-derivation in
  `client/src/components/reports/*`.
- Every displayed number arrives pre-computed in the `detailed` DTO.
- Golden-fixture parity: new builders produce the same numbers the old
  frontend math produced for `data/sample_apr_2026.json`.
- CI green on synthetic fixture; one live month manually parity-checked
  pre-merge (DATA_POLICY forbids live data in CI).

## Risks

- Paired-reimbursement divergence (tie-break sort semantics) — mitigated:
  reuse CLI `_paired_reimbursements` (`accounting_html.py:633`), which the
  frontend code is a faithful port of (verified same sort key `(date, id)`,
  same greedy first-match, same owner/opposite/non-zero predicate).
- Two category taxonomies (roles vs sections) stay split — not unified here;
  documented risk only.
- Silent drift if old and new paths coexist too long — mitigated by
  additive-then-swap with deletion PR in the same stack.

# L2 — Components (APPROVED)

## Backend (new)

- `accounting.py` (domain math, per Q1 split-by-kind):
  - `_paired_reimbursements` — moved/promoted from `accounting_html.py` so the
    JSON contract and HTML render the same concept from one implementation.
  - Section-group builders for the 9 sections: income (salary vs third-party
    split + row/household pct), savings (adds `rate = net_saved/income*100`),
    home/common/trips (per-category paid/received/net per partner + paired
    rows + gShare), personal×2, cc_payments, excluded (paid-only sums).
  - `household` scope totals: composition rule
    `[home, common, personal_partner_a, personal_partner_b, trips]` — currently a
    hardcoded frontend array (`DetailedSections.tsx:592-619`).
  - `personal_share = personal_spend / total_real_spend * 100`;
    `balanced = reconciliation.difference === 0`; sign enums for all money
    fields (precedent: `partner_panels.net_class`).
- `report_builder.py` (DTO shaping): new `_detailed()` view port composing
  the above into the contract; delete the three dead ports.

## DTO shape (Q2)

Single `detailed` object on `ReportResponse`:
`report.detailed.{income, savings, home, common, personal_partner_a,
personal_partner_b, trips, cc_payments, excluded}` — each fully pre-computed
(rows, totals, percentages, sign enums). Also `detailed.household_totals`.

## Raw field removal (Q3)

`normalized_transactions` dropped from `ReportResponse` in the final PR once
no frontend consumer remains.

## Frontend (updated, presentation-only)

- `DetailedSections.tsx` — shrinks to: read `detailed.*`, format via `fmt()`,
  render. All internal derivation functions deleted.
- `KpiRoleSummary.tsx` — consumes `personal_share` + server sign enums.
- `ReconciliationSection.tsx` — consumes `balanced`.
- Deleted: `CategoryHighlights.tsx`, `SubcategoryOverviews.tsx`,
  `TransactionDrilldowns.tsx`.
- `client/src/types/report.ts` — new `DetailedSection` types; drop dead DTO
  fields and `normalized_transactions`.

## New tests

- pytest: per-section golden tests on synthetic fixture; pairing edge cases
  (tie-break date/id sort, zero amounts, same-owner same-amount NOT paired);
  pct div-by-zero guards (income=0); sign enum boundaries (±0.0 → "zero").
- vitest: render-only tests — components render from a fixed `detailed`
  payload with no computation mocks.

# L3 — Interactions (APPROVED)

## Transition (Q1: additive-then-swap)

1. PR-A: backend ships `detailed` additively; frontend unchanged (still
   self-computes). Green and independently reviewable.
2. PR-B: frontend sections swap to `detailed` consumers.
3. PR-C: delete old frontend derivation code, dead components/ports,
   `normalized_transactions`, bump docs.

Mount/generate/poll/stale flows unchanged. Staleness: `calculation_version`
mismatch marks report stale via existing gate; user regenerates lazily (Q4).

## Parity proof (Q2: golden fixture)

Run old pipeline math vs new builders on `data/sample_apr_2026.json`
(+ one live month, manual pre-merge). Snapshot every `detailed` field.
CI gates on synthetic only (DATA_POLICY).

## Failure modes

- income = 0 → percentage fields are `null` (not 0, not crash); frontend
  renders em-dash (existing convention for unavailable metrics).
- `savings_summary = null` → `detailed.savings` null → existing
  "Savings summary unavailable" fallback preserved.

## Concurrency / Security

Unchanged: single-process uvicorn + `threading.Lock` generate guard;
127.0.0.1 bind; no new endpoints (contract change only on existing 5).

# L4 — Contracts (APPROVED)

- Percentages (Q1): 0–100 floats, matching current frontend output. No
  conversion at the swap seam.
- Sign enums (Q2): server emits `"pos" | "neg" | "zero"` per money field as
  `<field>_class`; frontend maps enum→Tailwind class in one lookup table.
- Amount signs (Q3): paid-negative convention verbatim from `_aggregate`
  (`paid` sums negatives, `received` sums positives, `net = paid - received`).
  No semantic drift during parity phase.
- Nullable semantics: missing underlying section data → section key is `null`,
  never fabricated zeros (existing stored-report rule).

# L5 — Implementation Plan (APPROVED)

4 stacked PRs (Q1) off trunk `feature/mr-logic-sceleton`, each PR targeting
the previous branch (house pattern F1.2 #12–16 / F2).

- PR1 — Contracts + golden fixture: `models/reports.py` + `types/report.ts`
  `detailed` types (backend fields defaulted/optional, additive);
  `CALCULATION_VERSION`→5; extend `sample_apr_2026.json`/section mapping so
  all 9 sections are covered; snapshot baseline of current expected values.
- PR2 — Backend logic: move `_paired_reimbursements` into `accounting.py`;
  section builders; household totals; `personal_share`, `balanced`, sign
  enums; `report_builder._detailed()` shaping; delete 3 dead ports; pytest
  golden tests pass.
- PR3 — Frontend swap: all 9 sections + KPI summary + reconciliation consume
  `detailed`; enum→class lookup table; vitest render-only; manual parity
  check vs one live month.
- PR4 — Deletion: dead f.e. components, old derivation code,
  `normalized_transactions` from contract, docs (`README`/memory). **Landed**:
  deleted `CategoryHighlights.tsx`/`SubcategoryOverviews.tsx`/
  `TransactionDrilldowns.tsx` + their orphaned `report.ts` type aliases;
  dropped `normalized_transactions` from `ReportResponse`
  (models/reports.py + report_builder.py output + report.ts) while keeping
  it inside `accounting.py`'s internal contract dict (still consumed by the
  CLI/PDF `accounting_html.py` path and `mega/build_mega.py`) — **reverted in
  PR5** (drill-down UX loss found in smoke testing; see PR5 note); closed the
  net_cash sign-enum gap (`kpis.<partner>.net_cash_class` via
  `accounting._sign_class`, `KpiRoleSummary.tsx` swapped to consume it,
  nullable-fallback kept for reports generated before this field existed —
  same convention as `net_saved_class`, no `CALCULATION_VERSION` bump for
  this addition). `ReconciliationSection`/`KpiRoleSummary` v4-shape
  fallbacks (`balanced ?? …`, `netSavedClass ?? …`) were verified NOT dead:
  `GET /reports/monthly/{month}` serves stale reports as-is (marks
  `stale: true`, does not block/regenerate), and `ReportView.tsx` renders
  them regardless of the stale flag (badge only) — so pre-migration
  stored reports missing these fields are still a reachable render path.
  Fallbacks kept, contrary to the original plan assumption.

### Post-merge smoke-test fixes (PR5)

Both regressions below were found by manual browser smoke-testing of the
live app on the PR4 state (branch `feature/mr-logic-pr5-smoke-fixes`,
stacked on PR4).

- **FIX 1 — personal-section Subtotal parity bug.** The `PersonalSection`
  DTO exposed only the *shared* `personal_total` (both personal sections
  combined), so the migrated frontend rendered that combined number as each
  section's "Subtotal" row, while the old UI accumulated each section's own
  rows (`fmt(subtotal)` in the old `DetailedSections.tsx`; legacy HTML does
  the same in `accounting_html._legacy_personal_sections`; 2026-08 live
  values: Fixture A 6,043.97 / Fixture B 9,659.78 — not 15,703.75 twice). Added
  `subtotal` + `subtotal_class` (sum of the section's own row totals, plus
  the standard `_sign_class` enum) to `detailed_personal_sections()`, the
  `PersonalSection` model, and the `report.ts` mirror; golden snapshot
  regenerated with a sum-of-rows parity test. The fields are additive with
  `None` defaults so stored v5 reports written before PR5 still pass
  `ReportResponse` validation on GET — frontend keeps the old rendering as
  fallback; no `CALCULATION_VERSION` bump (same convention as PR4's
  `net_cash_class`).
- **FIX 2 — `normalized_transactions` restored to the public contract.** The
  PR4 cut also removed the per-category transaction drill-down data from the
  report response; smoke testing showed the drill-down UX loss. Restored to
  `ReportResponse` / `report_builder.build_report()` / `report.ts` exactly as
  pre-PR4 (`normalized_transactions: list[dict]`, required). It never left
  `accounting.py`'s internal contract dict — CLI/PDF and mega consumers were
  untouched. `CALCULATION_VERSION` stays 5: pre-PR1 (v4) stored reports
  already carry the field and keep rendering via the v4 fallbacks retained in
  PR4. Reports generated under PR4 (v5 without the field) must be
  regenerated — they fail response validation. Frontend restores drill-downs
  under **all 9** detailed sections; savings keeps its old-UI shape (open
  `.drilldown-card` per category, grouped by leaf **title**), everything else
  uses the collapsed `<details class="drilldown">` pattern.

## Fixture coverage (Q2)

Synthetic fixture extended to cover all 9 sections, both partners, zero-value
edges; CI gates on synthetic only; one live month diffed manually pre-merge.


## PR#53 Copilot review fixes (applied in-PR)

Copilot's PR#53 review findings triaged and fixed directly on this PR (not a
stacked follow-on) so the diff reviewers see is the final state:

- **C1 (accepted):** the detailed DTO graph was untested with a populated
  payload. Added `test_detailed_dto_contract_populated_roundtrip` —
  fully populated sections with explicit pos/neg/zero sign values and null
  percentages validate and JSON round-trip losslessly.
- **C2 (accepted):** `PairedReimbursementRow` pre-formatted display strings
  violated the presentation boundary (design L4: numeric + SignClass, the
  frontend formats). Replaced with signed numerics + classes; PR2 emits them,
  PR3 formats via `fmtSigned` preserving the old "+123.45" rendering.
- **C3 (accepted):** per-partner personal share had no contract field, so the
  PR3 panel silently dropped the old "(X.X%)" suffix (parity break). Added
  nullable `personal_share_partner_a/b` on ReportResponse (household
  real_spend denominator, matching the old UI); PR2 computes, PR3 renders.
- **C4 (rejected):** per-category paid/received on net rows — the old UI net
  tables display net-only; paid/received were never-rendered intermediates
  and stay recoverable from `normalized_transactions`. Documented, not fixed.


## PR#54 Copilot review fixes (applied in-PR)

- **F1 (accepted):** PR2 removed the `category_highlights` /
  `subcategory_overviews` / `transaction_drilldowns` members from
  `client/src/types/report.ts` while the (already dead, unimported)
  components `CategoryHighlights.tsx` / `SubcategoryOverviews.tsx` /
  `TransactionDrilldowns.tsx` still referenced them — five new TS2339/TS7006
  errors at this layer (tsconfig compiles all of `src`). Deletion of the
  three dead views moved up from PR4 into PR2 so each layer type-checks.
- **F2 (accepted):** `_paired_reimbursements` sorted on `(date, id)` where
  normalized records carry raw upstream ids — numeric when present, `None`
  when missing. Two same-day records mixing both raised `TypeError` in the
  tuple sort, aborting report generation. Tie-breaker normalized to
  `str(id or "")`, mirroring the old frontend comparator
  (`String(id ?? "")`). Regression test added.

## PR#55 Copilot review fixes (applied in-PR)

- **F1 (accepted):** sign classes were unstyled outside `.partner-box` —
  the server `_class` values applied to detailed table cells had no visual
  effect. `.legacy-table`-scoped `.pos` / `.neg` (+ muted `.zero`, which had
  no style anywhere) added to `report-shared.scss`.
- **F2 (accepted):** `_build_detailed` always returned a zero-filled income
  object whenever a section mapping existed, so the frontend's
  "No income this month." empty state was unreachable (zero table with
  meaningless percentage noise on no-income months). New
  `has_income_records()` predicate in `accounting.py`; `_build_detailed`
  emits `income=None` unless income records exist — the DTOs (pydantic + TS
  mirror) already declared `IncomeSection | None`.
- **F3 (accepted):** the `ReportView` fixture negated expense magnitudes,
  diverging from the real builders (positive magnitudes + `_sign_class
  "pos"`, confirmed against the golden fixture) — the `r.total > 0` chart
  paths never executed in tests and the shared `personal_total` semantics
  were masked. Fixture flipped to golden conventions and a chart-render
  assertion added; a no-income empty-state test covers F2's render path.
- **F4 (rejected — already fixed downstream):** `personal_total` rendered
  as each personal section's Subtotal while it is the combined total of
  both sections. Real defect, but already fixed in PR5 (`subtotal` /
  `subtotal_class` per-section fields + render) — the smoke-fix layer was
  created for exactly this class of bug; duplicating the fix at PR3 and
  re-dropping it in PR5 adds churn without net change to the merged stack.
## PR#56 Copilot review fixes

Three inline findings, dispositions:

- **F1 (accepted, doc):** `signClasses.ts` fallback comment pointed at
  `report_builder.py`'s `_role_kpis`; the function lives in
  `src/v4_pipeline/accounting.py`. Reference corrected so contract tracing
  resolves.
- **F2 (rejected — superseded by PR57):** test fixtures still carried
  `normalized_transactions` after PR4 removed it from the client
  `ReportResponse` type (tsconfig excludes tests, so vitest never
  complained). Valid against PR56 in isolation, but the stack is the merge
  unit: PR57 restores `normalized_transactions` to the type for drilldowns,
  so removing the fixture fields at PR4 and re-adding them at PR5 is churn
  with zero net change. Type and fixtures agree again at the stack tip.
- **F3 (accepted, doc):** `build_report()` docstring still promised the
  "full contract" after PR4 stopped returning `normalized_transactions`.
  Reworded to describe the public report DTO (contract fields + views),
  pointing at `ReportResponse`/`DetailedSections` as the authoritative
  surface — wording stays accurate whether or not the DTO exposes
  transactions.

## PR#57 Copilot review fixes

Two inline findings, both accepted:

- **F1 (model compat):** `ReportResponse.normalized_transactions` became
  required again when PR5 restored drilldowns, but reports stored under the
  PR4 backend lack the field — strict validation 500ed the GET before the
  Regenerate button could render. Field now defaults to `[]` so those
  reports load and can be regenerated once. Regression test in
  `test_reports.py::TestReportResponseCompat`.
- **F2 (drilldown/DTO parity):** `SectionDrilldowns.groupTxnsBySection`
  dropped the transfer re-route from `_routed_section` — transfers mapped
  to income/common/personal/trips/CC belong in `excluded` (only
  home/savings/excluded keep their section). Without it, drilldowns
  disagreed with the section tables. Rule ported 1:1; regression test in
  `DetailedSections.test.tsx` covers both the re-route and the keep-list.

## Post-review compat fix (stored-report 500, found by live smoke test)

`GET /api/reports/monthly/2026-08` 500'd on a stored PR2-era report:
pydantic `ValidationError` ×12 (`detailed.{home,common,trips}.paired_reimbursements[i]`
missing `partner_a`/`partner_a_class`/`partner_b`/`partner_b_class`) → FE
showed "cannot reach server".

Root cause: `PairedReimbursementRow` partner fields are required, but old
stored rows use the pre-rename shape (`partner_a_display`/`partner_b_display`
strings). `calculation_version` stayed 5 across the stack (per PR53 review),
so those reports weren't flagged stale.

Fix (same pattern as PR57 F1 — validate with defaults, then regenerate-once):
- `models/reports.py` — the four partner fields default to `0.0`/`"zero"` +
  compat comment; old display-string keys dropped as extra fields.
- `report_builder.CALCULATION_VERSION` 5 → 6 (paired-row + transactions-shape
  change) → old reports now `stale=True` and the FE stale banner offers
  Regenerate; golden fixture version updated.
- Tests: paired-row defaults case in `TestReportResponseCompat`,
  `calculation_version=5` added to the stale parametrize.
