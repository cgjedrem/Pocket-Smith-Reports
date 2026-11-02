# Implementation Plan: Lifestyle creep detector

**Branch**: existing app-managed worktree branch | **Date**: 2026-10-31 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `docs/specs/005-lifestyle-creep/spec.md`.

**Feature identifier**: `005-lifestyle-creep`, independent of the app-managed branch.

**Original delivery boundary**: Phase 0 research and Phase 1 design only.

**Current usage-graph checkpoint (2026-11-02)**: T061 adds a client-only, lazily mounted per-category usage graph with a descriptive trailing average (up to three prior consecutive months, minimum two) and strict above-average markers. **63/63 checked; zero pending**. T062 independent review **PASS, no significant issues** was supplied in the final-verification assignment. T063 rebuilt/deployed only the owned frontend and passed **339 Chromium assertions** (333 synthetic, 6 separate unmocked metadata/structural-only), nine containment tests and `git diff --check`. Both services remain healthy; API container/image and named private volume are unchanged. The live report GET now returns `ready`, `grouping=report`, three groups; no live category graph was opened, no live amounts/identities captured and no sync performed. Earlier insufficient-history evidence remains historical. API, calculation and verdict contracts are unchanged; see quickstart section 22.

**Historical report-group checkpoint (2026-11-02)**: T057–T060 complete, **60/60 checked; zero pending**. T059 independent review **PASS, no significant issues** was supplied in the verification handoff. Both actual Compose images were rebuilt and deployed; T060 passed **68 Chromium assertions** (57 synthetic, 11 unmocked metadata/structure-only), plus the identical-category-ID component regression and nine containment tests. Both services remain healthy at `127.0.0.1:8080`, with the existing named private volume unchanged. The live report endpoint honestly returns `insufficient_history` with four `legacy_history` issues and all three group headings: schema-7 evidence requires an explicit user-run resync, which verification did not perform. Exact commands, sanitized evidence, baseline tests and the final slice manifest are in quickstart section 21.

**Historical visibility boundary (2026-11-02)**: Corrected-contract and visit-local category-visibility tasks T049–T056 were complete, **56/56 checked; zero pending** at that checkpoint. T055 independent code-review **PASS** was supplied in the final-verification handoff. T056 rebuilt/updated only the frontend and passed **67 Chromium assertions** (58 synthetic, 9 unmocked structural-only); both Compose services remained healthy and the API's existing named volume was unchanged. The T054 client baseline was **50 files / 558 tests**, with a passing production build; the final frontend image build also passed. Exact amendment commands, sanitization boundaries and containment results are in quickstart section 20. Prior corrected-contract evidence (283 backend tests, 552 client tests, T052 review and T053 smoke) remains in section 19. Earlier multi-month results are historical, not corrected-contract acceptance.

**Latest semantic correction**: The user's explicit clarification replaces the 2026-11-02 multi-month evaluation interpretation below. The earlier completed counts remain historical evidence only; they do not verify the one-target/reference-period implementation.

**Current handoff boundary (after the real-data round)**: 41 of 41 tasks are complete. T001 to T034 were completed in the first implementation round: independent re-review closed both source-integrity findings, and the coordinator verified the complete Git manifest, resolving the reviewer's metadata caveat. Phase 9 (T035 to T039) then covered the rebase onto main, the real-data validation and the independent post-rebase review (pass-with-caveats, no critical or high findings). T041 (2026-11-02, user-directed) moved the card from the Bills page to its own **Lifestyle Creep** tab. T040, the final container rebuild and structural verification, was done by the coordinator on 2026-11-02 against the working tree after T041 ([quickstart section 17](quickstart.md#17-separate-lifestyle-creep-tab---2026-11-02)). The initial integrated QA FAIL, the final acceptance and the post-rebase review are preserved in [review-report.md](review-report.md); the real-data validation and the known limitations are in [quickstart section 16](quickstart.md#16-post-rebase-real-data-validation). Verification before the tab move: backend non-renderer suite 1580 passed (2 native-renderer exclusions), client 49 files and 540 tests passed, production client build passed. Current client result after the tab move and the review follow-up: 50 files and 539 tests passed, `tsc --noEmit` passed. The only non-test source change after the last local `pnpm build` (T041) is the month help text; the coordinator's frontend image rebuild, whose `client/Dockerfile` runs `pnpm build`, succeeded with it (quickstart section 17). Earlier dated records stay in the quickstart: the first-round counts (1220 backend and 468 frontend tests), eight synthetic Chromium scenarios, and an unmocked browser to real-FastAPI smoke on synthetic temporary storage that passed 182/182 assertions ([quickstart section 15](quickstart.md#15-unmocked-real-api-browser-smoke---2026-10-31)). The user continuation authorizes local implementation/review despite the failed merged-plan gate, as recorded below; it does not authorize publication. Original planning/task-generation boundaries below are historical, not current implementation status.

## Summary

**Report-group backend amendment**: T057 adds explicit `grouping=report` on the
existing read-only endpoint and additive snapshot schema 7; default CC consumers
remain unchanged. The sync producer reuses report input loading, contract
normalization, resolved section routing and category grouping. No second category
classifier, current-config GET fallback or report-file GET was introduced.
Shared is exactly Home + Common; personal sections follow category assignment,
including refunds across both payers. Signed observations use the same exact
comparison evaluator with explicit negative-baseline suppression. Existing
schema-6 CC evidence cannot reconstruct this broader population and is never
upgraded by a read. Schema/resync details are in
`contracts/bills-history-v7.md`; API/client interfaces and verification are in
quickstart section 21. T058 adopts report mode on the standalone page with a
separate typed API wrapper, fixed ordered group validation, group/category
visibility namespaces, signed explanations and mapping/resync guidance.
T057–T060 are complete, including supplied independent review PASS and the
successful two-image deployment/browser verification. Current task completion is
**63/63** after the T061 usage graph, supplied T062 review PASS and completed
T063 frontend-only deployment/browser verification; earlier completion statements
describe their historical boundaries only.

The separate Lifestyle Creep tab now compares one completed target month in three
report groups (Shared Home + Common, personal A, personal B) against the mean over
a selected contiguous 2–24-month reference period. Included checking and card
spending uses paid minus received, classified by the report category section,
not the payer. The default reference is the three months immediately before
target. A separate exact threshold (default 20%, finite decimals 1–100%) controls
whether target growth is above threshold. At least two reference months must
have positive spending; zero/negative means suppress the outcome. Missing report
evidence blocks all three groups. T058 preserves the original CC API wrapper but
the page requests only report mode and does not add a toggle or frontend totals.

The original CC implementation had three boundaries (historical; report-mode
changes above and quickstart section 21 supersede the population/presentation):

1. **Trusted monthly evidence at sync**: Add optional `PartnerBills.cc_spend_history` and advance newly built Bills snapshots from schema 5 to 6. Store original category IDs, separate uncategorized amounts, explicit complete/partial/unavailable coverage, and a label-independent scope fingerprint. Only a successful, validated full-month fetch begun after month close can produce complete evidence. Preserve `cc_usage_by_category`, `cc_usage`, and all existing Bills consumers.
2. **Pure evaluation behind a thin GET**: `GET /api/bills/lifestyle-creep` accepts target `month`, threshold and paired `reference_start`/`reference_end`, validates inputs before storage access and reads exactly the selected reference snapshots plus target (3–25 files), once per path. Omitting both reference bounds selects the three months before target. No current catalogs, transaction fallback, PocketSmith calls, writes, or result cache. Expected gaps return diagnostics; malformed records return a generic error, never a successful partial result.
3. **Independent presentation**: A typed API wrapper, feature hook and thin card live on `LifestyleCreepPage`, not Bills. Target month and reference-bound drafts apply atomically; each request supplies all three months. Fetch and response identity include target, both references and canonical threshold; Retry repeats the applied selection. Global privacy masks all money, including collapsed and assistive text, without fetching; percentages remain visible. Ready partners stay inspectable under prominent partial coverage.

**Explicit feature-local numeric convention**: Use `Decimal` for aggregation and decisions, and canonical decimal strings for new persisted and response decimal fields. This is an additive convention, not a conversion of legacy Bills numbers. It avoids binary-float and JSON round-trip threshold errors without new dependencies. The client converts only at the existing presentation formatter boundary and never recomputes verdicts. See [research.md](research.md#r4--exact-decimal-math-and-serialization).

## Technical Context

**Language/Version**: Python >=3.13; React 19, TypeScript 5, Vite 6. Existing runtime and lockfiles remain unchanged.

**Primary Dependencies**: Existing FastAPI/Pydantic, pytest/pytest-asyncio; React Router, Tailwind v4/Radix, Vitest/Testing Library. Standard-library `decimal`, `hashlib`, `json`, and calendar/date handling only for new server logic. No new dependencies.

**Storage**: Existing atomic JSON snapshots resolved through `storage.bills_dashboard_path(month)`. Additive schema 6 evidence within each partner, not a new database, history store, index, or settings file. Legacy snapshots are neither rewritten nor title-migrated on reads.

**Testing**: Pure synthetic calculation tests, isolated builder/sync and FastAPI integration tests, client wrapper/hook/component/page tests, client build, and a request-mocked browser smoke. Targeted tests precede the full Windows Python non-renderer suite. No tests or application imports are needed for this planning phase.

**Target Platform**: Local-first Python API and Vite browser client; Windows PowerShell development, existing Ubuntu/Windows CI requirements. No service contact during planning. If later browser verification needs a server, use an isolated client on 5205 with all API requests mocked; 8105 is the only permitted dedicated API port if separately necessary. Never use the user's Docker stack or services on 8080/5200/8100.

**Project Type**: Existing Python report/API repository plus React SPA; no additional project or service.

**Performance Goals**: Zero storage reads for invalid selections; 4–27 exact snapshot read attempts for valid explicit periods, at most once per path, with an early stop permitted on a fatal read/parse error. No directory scans. Calculation is linear in the loaded partner/category evidence; no invented latency SLA.

**Constraints**: Synthetic-only verification; no access to private records, credentials, or the main checkout. Set `BILLS_CALC_LOG=0` before application imports and isolate storage before builder fallback or app lifespan execution. Preserve legacy routes and totals. No forecasts, runway/debt integration, recurrence inference, persistent sensitivity settings, or unrelated refactors.

**Scale/Scope**: 4–27 monthly snapshots per explicit request; existing stable partner population, all source category IDs observed in that window; one GET and one independently fetched card on its own tab.

## Constitution Check

*Design gate evaluated before Phase 0 and re-evaluated after Phase 1 against constitution v1.0.2. These are design checks, not runtime or before-tasks gate results.*

| Principle | Pre-research | Post-design evidence |
| --- | --- | --- |
| I. Financial privacy | PASS | Only synthetic examples; no private reads; last-mile masking covers all monetary text and attributes. |
| II. Fail closed | PASS | Explicit source provenance; no fetch-failure publication, unknown zero-fill, fallback scan, corrupt-success response, or partial baseline. |
| III. Atomic/staged publishing | PASS | Retain existing atomic snapshot writer; report HTML/PDF publication is untouched. All requested transaction inputs must finish successfully before Bills publication begins. |
| IV. Python and pinned dependencies | PASS for feature delta | Python >=3.13, no new or changed dependencies. Existing manifest/constitution version drift is recorded below, not silently fixed. |
| V. Hardened PocketSmith access | PASS | Detector never constructs a client. Explicit sync remains the only source acquisition path; URL/redirect/loop safeguards remain intact. Cycle1 adds strict sync pagination-cap failure while retaining legacy default truncation. |
| VI. Layer separation | PASS | Models validate contracts; services validate saved evidence and compute; router maps input/domain errors to existing `{detail: string}` responses. |
| VII. React/Vite/TypeScript/pnpm | PASS | Thin component, separate API/hook, existing privacy formatters; no frontend framework or package-manager changes. |
| VIII. Colocated tests | PASS as design obligation | Matrix and safe commands in quickstart cover math, persistence, routes, compatibility, UI, and privacy; execution was pending at design time and its results are recorded in the quickstart. |
| IX. PowerShell/UTF-8 | PASS | PowerShell commands, explicit environment per process, UTF-8 without BOM. No infrastructure changes. |

**Existing governance drift, not introduced here**: Constitution text cites narrower FastAPI/uvicorn and older renderer/PDF versions than current `pyproject.toml`; it also describes a missing pnpm pin, while `client/package.json` now pins `pnpm@10.30.3`. Preserve current manifests and locks rather than upgrading/downgrading as feature work. Constitution reconciliation belongs to its separate amendment workflow. No `pnpm lint` script exists; test/build remain the applicable client checks.

**Post-design result**: No feature-introduced constitution violation or unresolved design question. The additive decimal-string fields are explicitly documented; old fields stay unchanged. Runtime correctness and merge gates are not certified by this check.

## Project Structure

### Documentation (this feature)

```text
docs/specs/005-lifestyle-creep/
├── spec.md
├── checklists/requirements.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── tasks.md
└── contracts/
    ├── lifestyle-creep-api.md
    ├── bills-history-v6.md
    └── bills-card.md
```

`spec.md` and its reviewer-owned checklist remain unchanged inputs. `tasks.md` is the task-generation handoff, not evidence of implementation.

### Source Code (repository root)

The following is the implementation handoff, not a record of source changes:

```text
src/budget_api/
├── models/
│   ├── bills.py
│   └── lifestyle_creep.py                 (new)
├── services/
│   ├── bills_derivations.py
│   ├── bills_builder.py
│   ├── ps_client.py                      (strict sync pagination opt-in)
│   ├── sync_runner.py
│   ├── storage.py                        (reuse path/writer; no broad refactor)
│   └── lifestyle_creep.py                 (new)
├── routers/bills.py
├── main.py                               (no-store allow-list)
└── tests/
    ├── conftest.py                        (reuse temporary storage fixtures)
    ├── bills/conftest.py                  (close builder isolation gaps)
    ├── bills/test_lifestyle_creep.py       (new)
    ├── bills/test_cc_spend_history.py      (new)
    ├── bills/test_lifestyle_creep_api.py   (new)
    └── test_sync_lifestyle_history.py      (new)

client/src/
├── types/
│   ├── bills.ts                          (optional additive history)
│   └── lifestyle-creep.ts                 (new)
├── api/
│   ├── lifestyle-creep.ts                 (new)
│   └── __tests__/lifestyle-creep.test.ts   (new)
├── hooks/
│   ├── useLifestyleCreep.ts               (new)
│   └── __tests__/useLifestyleCreep.test.ts (new)
├── lib/
│   ├── lifestyle-creep.ts                 (new; feature-local input/presentation helpers)
│   └── __tests__/lifestyle-creep.test.ts   (new)
├── components/bills/
│   ├── LifestyleCreepCard.tsx             (new)
│   ├── LifestyleCreepDetails.tsx          (new; thin category/uncategorized detail)
│   └── __tests__/LifestyleCreepCard.test.tsx (new)
├── pages/BillsPage.tsx                    (detector wiring removed 2026-11-02)
├── pages/LifestyleCreepPage.tsx           (new 2026-11-02; own tab, owns detector state)
├── pages/__tests__/LifestyleCreepPage.test.tsx (new 2026-11-02; replaces BillsPage.lifestyle-creep.test.tsx)
├── router.tsx                             (route `lifestyle-creep`)
├── layouts/AppLayout.tsx                  (nav tab "Lifestyle Creep" after Bills)
└── tests/
    ├── BillsPage.test.tsx                 (Bills renders and fetches no detector)
    └── LifestyleCreepRoute.test.tsx       (new 2026-11-02; deep link + nav tab)
```

**Placement amendment (2026-11-02, user-directed)**: The user asked for the detector in its own tab instead of the Bills page. `LifestyleCreepPage` now owns the visit-local month and threshold state that `BillsPage` held, and the card is reached from the **Lifestyle Creep** nav tab at `/lifestyle-creep`. The components stay in `components/bills/`, and the API path `GET /api/bills/lifestyle-creep` is unchanged. Tracked as T041.

**Structure Decision**: Keep the existing API models/services/routers layering. In `services/lifestyle_creep.py`, separate pure readiness/evaluation functions from the bounded storage adapter. Reuse the canonical CC filter iterator through a strict validated aggregation entry point, not the float totals or broad exception fallback. Do not make the detector service depend on `bills_builder` (import-time logging). Client business decisions remain server-owned; the client manages request and presentation state only.

## Complexity Tracking

No feature-introduced violations requiring an exception. No new dependencies, persistence subsystem, account-history reconciliation framework, generic repository layer, or recurrence engine.

## Phase 0: Research Resolution

[research.md](research.md) records decisions, evidence, rationale, and rejected alternatives. The supplied full discovery report was read; only bounded clarification of sync publication, filter precision, identity, storage parsing, error middleware, client tooling, and calendar behavior was needed. No repeated broad discovery or external research was performed.

All ordinary design details are resolved under the user's unattended authorization. In particular: source-trust provenance, precision-safe decimal fields, deterministic ID ordering/labels, scope-change diagnostics, corrupt-versus-missing behavior, and threshold state are specified.

## Phase 1: Design and Integration Boundaries

### Trusted producer and compatibility

Sync records successful full-range transaction acquisition per month before invoking the Bills chain. Carry an explicit in-memory source-coverage context into builder calls; default absence means unavailable, never complete. A fetch started during the source month remains partial even if building finishes after midnight. A transaction-fetch exception prevents new Bills snapshot publication for that sync attempt.

**Cycle1 policy correction (2026-10-31)**: A returned list alone does not establish complete acquisition: legacy `PSClient` returns accumulated rows when its page cap is reached. Sync now constructs `PSClient(..., require_complete_pagination=True)` so a remaining next link at the cap fails all paginated acquisition paths (monthly transactions/events and prior-month fallback) before Bills publication. Default callers retain legacy truncation, and a final page exactly at the cap succeeds. No new result envelope, schema, retry loop, pagination rewrite or multi-file transaction is introduced. Prior catalog/raw/status writes retain their existing behavior; the no-publication guarantee concerns Bills snapshots.

Validate original transaction collections before the permissive legacy filters can drop malformed entries. Validate IDs, dates, finite numeric amounts, account ownership/mappings, role inputs, and transfer flags needed for coverage. Invalid source may produce a well-formed `unavailable/invalid_source` evidence block if the legacy build can still succeed; it must never be transformed into empty complete history. If it prevents a safe build, retain existing failure behavior instead of publishing.

**Cycle1 mapping correction**: Explicitly excluded accounts may have null owner/type, matching the accounts API, including retained mappings absent from the fresh catalog. Included ownership/type must remain resolved. Validate non-null values without inventing bindings; keep known owned CC exclusions in the existing scope fingerprint.

New fields and their migration-by-re-sync rules are normative in [bills-history-v6.md](contracts/bills-history-v6.md). No SQL migration applies; no migration script can safely infer category identity from old titles. A later explicit successful re-sync is the data upgrade, using existing atomic publication. It runs from the first window month through the usual sync end month (at least the current month), in one run under a consistent account/category configuration. The legacy dashboard still reads old snapshots.

### Reader and pure calculation

Validate month and threshold completely before deriving paths. Read each exact monthly file directly, distinguishing missing files from literal JSON `null`, detecting duplicate object keys and malformed evidence. Validate the detector's minimal envelope, not all unrelated legacy Bills fields. Do not call the dashboard route or rely on its recalculated `is_past`.

Read the union of stable partner IDs across the entire required evidence window. An identity-less legacy row remains an explicit unassigned diagnostic, never a manufactured partner. Whole missing months affect all known partners. Compare scopes only after structural validation. All corrupt-record errors take precedence over availability and cancel the whole response; otherwise ready partners can coexist with incomplete partners.

For each ready partner, return every required observation per category in the union of IDs. Only category absence from a complete aggregate means zero, never a missing snapshot. Compute with `Decimal`, using exact cross-products for threshold tests rather than rounded averages or float percentages. The [data model](data-model.md), including its dated variable-period amendment, specifies precision, suppression, deterministic labels and invariants.

### API and UI handoff

[lifestyle-creep-api.md](contracts/lifestyle-creep-api.md) specifies query grammar, 200/400/500 responses, precise field types, availability diagnostics, and no-store behavior. Expected history gaps are 200, not 404. Error bodies remain `{ "detail": "..." }`; no stack trace, raw financial payload, or storage path leaves the route.

[bills-card.md](contracts/bills-card.md) specifies page placement, separate request ownership, draft/applied threshold behavior, all states, `/sync` navigation without triggering sync, all-category inspection, uncategorized coverage, stale-response protection, keyboard access, and privacy.

**Original task-stage integration clarification (superseded by T041/T046)**: The detector originally mounted independently of Bills dashboard early returns with a viewing-month control. It now has its own route; From/To controls and derived API month replace that interaction. Bills dashboard/window semantics remain unchanged. API month validation still uses the server clock, while defaults use the browser clock; see the documented boundary-time limitation.

**Task-level decomposition**: Feature-local `client/src/lib/lifestyle-creep.ts` holds exact threshold validation/canonicalization and privacy-aware decimal presentation helpers; `LifestyleCreepDetails.tsx` keeps the card's category/uncategorized markup thin. These follow the existing lib/hook/component layering, add no dependency or new shared framework, and do not change the wire contracts.

### Verification strategy and requirement coverage

| Coverage | Required verification |
| --- | --- |
| FR-001–FR-010 | Filter parity; stable IDs and rename/duplicate-title cases; separate uncategorized totals; source validation; empty complete versus unknown; failed fetch/no publish; rollover; scope fingerprints; schema-5 compatibility. |
| FR-011–FR-016, FR-028–FR-030 | Exact required window; missing/legacy/partial partners; rolling math, eligible consecutive pairs and strict boundaries; sparse/zero suppression compatibility; all category details. |
| FR-017–FR-018 | Omitted/default and finite decimal 1–100 thresholds; invalid/empty/boolean/non-finite values; equality; no persistent preference; true effective-threshold labelling. |
| FR-019–FR-021 | Loading/error/Retry/insufficient/partial/ready/no-alert/alert; corrupt evidence cancels successful partial data; Retry sees corrected files. |
| FR-022–FR-023 | Mask every money surface including aria/tooltips/hidden text; percentages visible; keyboard/live states; request-race protection; no refetch on privacy/mode/window changes. |
| FR-024–FR-025, FR-026–FR-032 | Bounded 4–27 path attempts and legacy five-path regression; period bounds, atomic drafts, echoed identity, races/Retry, one-month warning; zero reads on invalid queries, no external client/raw fallback/catalog reads/writes. |

See [quickstart.md](quickstart.md) for targeted then full-suite commands and the synthetic browser smoke. Tests, application imports, live sync, dependency restoration, and server startup were deferred at planning time; their results are recorded in the quickstart.

## Workflow and Gate Handoff

- Loaded `.github/skills/speckit-plan/SKILL.md`; ran `setup-plan.ps1 -Json` with `SPECIFY_FEATURE_DIRECTORY=docs/specs/005-lifestyle-creep` and used the resolved plan template.
- Setup returned the intended absolute spec/plan/directory paths. Its `BRANCH` value was `005-lifestyle-creep`: `common.ps1` uses the directory basename as workflow identity when explicit directory resolution omits branch context. This is not a branch switch; Git independently reported the existing app-managed branch.
- Setup may refresh ignored `.specify/feature.json`; it is machine-local, not a shareable feature artifact.
- Optional before-plan commit and after-plan commit/context hooks are skipped by explicit user coordination. No context rewrite or commit occurred.
- At the original planning handoff, the mandatory `before_tasks` plan-review gate had not been reached. **Subsequent coordinator handoff reports that it was RUN and FAILED**: `spec.md` and `plan.md` were untracked and absent from `origin/main`. The coordinator stopped and reported that failure. Task-generation inspection independently confirms the local artifacts are untracked; it does not certify remote review.
- **Explicit local procedural deviation, 2026-10-31**: The latest direct user continuation says, "If you were planning, stop planning and start implementing." The coordinator proceeds with tasks, then local implementation and development/review, under that new instruction rather than the earlier user-level pause. This proceeds despite a failed mandatory merged-plan gate; it is **not a passed merged-plan gate**, **not an explicit `--skip-review` flag** (none was supplied), and not evidence that review or merge happened.
- This task-generation step does not rerun or alter the gate. `.specify/extensions.yml` stays enabled and unchanged. Optional commit/publication hooks are skipped. No branch creation/switch, commit, push, PR, merge, or remote operation may be used to satisfy the failed gate.
- `setup-tasks.ps1 -Json` ran with explicit `SPECIFY_FEATURE_DIRECTORY=docs/specs/005-lifestyle-creep`, resolving this feature and `.specify/templates/tasks-template.md` with template content. `tasks.md` records the deviation and the sequential backend → frontend → local validation/review slices.
- Task generation stops ready for implementation. All implementation tasks remain unchecked. The failed gate remains failed; any future publication requires its separate governance process, not this local continuation.

### Original Planning Validation

- Validated all nine feature documents (including the unchanged spec/checklist) for UTF-8 without BOM, balanced code fences, resolved internal links/anchor, and absence of unresolved template markers.
- Parsed all JSON contract examples; checked required plan headings, seven generated artifact paths, no `tasks.md`, and unchanged Git branch.
- Pure standard-library checks passed for 13 synthetic calculation cases, strict 30% retuning, the response's decimal percentage examples, and October/January five-month windows. These validate document arithmetic, not application code.
- Self-review: no unresolved design contradiction; preserved finite decimal evidence during presentation overflow handling and clarified empty-label fallback before final handoff. Remaining risks are legacy-source availability, the existing title-sensitive payment resolver, and future test-isolation discipline, all documented with handling.
- No source tests, application imports, dependency restores, service contact, or workflow gate execution occurred. No runtime pass is claimed.

The preceding validation bullets describe the original planning phase only. The later failed gate and task-generation handoff are recorded above; they do not retroactively change those planning results.

### Task-Generation Validation

- Standard-library-only static checks passed for UTF-8 without BOM, balanced fences, resolved internal links/anchors, and no unresolved template placeholders in plan/tasks.
- Validated 34 unique sequential unchecked IDs, seven phases, required story labels/file paths, complete acyclic dependencies, and a topologically valid backend → frontend → local review handoff covering every task.
- Story counts: US1 8, US2 7, US3 5, US4 6; setup/foundation/final tasks 8. Nine tasks identify eligible same-slice parallel work, not concurrent backend/frontend execution.
- Self-review retained the no-implementation boundary, mandatory synthetic tests, pre-import isolation, feature-only scope, and accurate failed-gate attribution. Runtime tests, builds, browser smoke and development review remain unchecked implementation obligations.
- Git still reported the existing app-managed branch; no application source or extension configuration changes were made during task generation. Optional task commit hooks were skipped.

The task-generation checks above describe the 34-task, seven-phase list as it was at that time. Phase 9 (T035 to T040) was appended later; see [tasks.md](tasks.md).

## Selectable comparison-period amendment — 2026-11-02

This section supersedes the fixed five-snapshot/two-evaluation limits and viewing-month-only request identity in the original plan. It implements spec FR-026–FR-032 without changing snapshot schema 6, source acquisition, history derivations, existing tab placement or governance.

### Backend slice

1. Extend `validate_selection(month, threshold_percent=None, comparison_start=None, comparison_end=None)` in `services/lifestyle_creep.py`; both optional boundaries are required together. Validate ASCII calendar months, ordering, three available baseline predecessors, 1–24 inclusive evaluated months, `comparison_end < month`, and `month <= date.today()`'s calendar month before deriving paths. The no-range path retains its original five-predecessor minimum/defaults. Explicit one-month `0001-04` can use viewing month `0001-05`.
2. Retain `Selection(month, window_months, threshold)` and add boundary properties derived from the validated evidence. Read exactly `start-3..end` (4–27 paths) through the current reader, once each; use the full evidence count for readiness. Do not scan/read catalogs, repair history or initiate sync.
3. Generalize the pure `evaluate_partner` over 4–27 complete, comparable observations. Each evaluation uses its prior three values. Exact cross-products decide threshold exceedance before 28-significant-digit explanation rounding. A sustained result is any consecutive pair of eligible exceedances, not an all-month conjunction. Preserve original two-month suppression summaries and numerical output.
4. Add required response boundaries and bounded variable arrays to `models/lifestyle_creep.py`. Enforce agreement between boundaries, chronology, observations and comparisons; disallow a one-comparison sustained result. Keep three-element baseline arrays and constants `baseline_months=3`, `sustained_months=2`.
5. Extend the thin Bills route with the optional query pair, reject repeated recognized parameters, preserve old validation-message compatibility, error flattening and no-store behavior.

### Frontend completion (T046, 2026-11-02)

`LifestyleCreepPage` now uses From/To drafts and one Apply period, deriving `month=To+1`. Defaults are the previous two completed months; threshold remains visit-local and canonically deduplicated. The hook keys and guards both boundaries, month and threshold. Wire types allow variable arrays; details map every comparison and take the last for latest values. One-month MoM uses the prior sample, not a nonexistent second comparison. Selected period/evidence labels remain visible across states. Client tests cover bounds, atomic requests, stale results/errors, exact sensitivity, full masking and Bills isolation. The [card contract](contracts/bills-card.md) describes current behavior. Independent review and real-container browser acceptance subsequently completed T047–T048; their separate provenance and runtime coverage are recorded in quickstart section 18.

### Verification and limits

Targeted synthetic tests cover default regression, 1/2/6/24-month selections, 25-month rejection, earliest/latest representable dates and year boundaries, strict equality, any consecutive pair versus separated peaks, sparse/zero gaps, all array lengths, full-window readiness/scope failures, exact bounded reads and validation-before-I/O. Fixture storage is isolated before app imports; worktree-local pytest base directories keep test artifacts out of system temporary directories. No dependencies, real financial data, Docker, source acquisition or publication are part of this backend slice. See T042–T048 for honest completion markers and final test counts.

## Corrected one-target/reference-period implementation — 2026-11-02

The request is no longer an evaluation period. `month` is one completed target. `reference_start` and `reference_end` select 2–24 inclusive contiguous months before target; when absent, the reference is target−3 through target−1. `threshold_percent` remains an independent 1–100 sensitivity value.

Backend contract:

1. Validate ASCII target month no later than the API current month; validate the optional boundary pair, 2–24 range, end-before-target and threshold before storage access. Recheck every evidence month against the API clock before reads. Current-month selections return insufficient history with an open-month issue, no partners/money and zero reads; future selections remain invalid. Saved completion cannot override the clock.
2. Read exactly `reference_start..reference_end` and target, oldest first; a gap between reference end and target does not trigger intermediate reads.
3. Compare target spend with reference arithmetic mean using exact Decimal math. `is_above_threshold` uses `100*(r*S-T) > p*T`, requires positive `T` and at least two distinct positive reference months. Suppress zero baseline before low frequency. Keep samples when suppressed.
4. Return `reference_start`, `reference_end`, exact evidence `window_months`, compatibility `evaluation_months=[month]`, dynamic `baseline_months`, and one `comparison` per category. `latest_month_over_month_percent` is available only when reference end directly precedes target.
5. Missing, partial, legacy, unavailable or changed-scope history anywhere in the reference or target blocks the partner. No implicit shifting, zero-filling, extra target-neighbor read, sync, writes or catalogs.

The client provides target plus reference controls and is verified separately under T051. Historical selectable-period verification above is not a test result for this corrected contract.

**Corrected-contract completion (2026-11-02)**: T052's independent read-only review passed with no significant issues after the API current-month behavior was fixed fail-closed. A current target returns 200 `insufficient_history` without partner money and before path resolution or reads; future and malformed requests remain 400. T053's rebuilt API/frontend container smoke and unmocked same-origin Chromium check passed. Exact commands and sanitized observations are in [quickstart section 19](quickstart.md#19-corrected-target-month-and-reference-period---2026-11-02). Earlier T047/T048 review and container evidence applied to the superseded multi-month interpretation.

## Visit-local category visibility completion — 2026-11-02

T054–T056 are complete. The UI-only amendment uses stable partner/category IDs for Hide, Show hidden categories, Restore and partner-local Restore all; corresponding disclosures follow row visibility. Choices survive fetch/loading/error/Retry during a visit and reset on route re-entry. Server assessments and global monetary masking are unchanged. Independent code-review passed; frontend-only container deployment and synthetic plus structural-only live browser acceptance passed. See [quickstart section 20](quickstart.md#20-visit-local-category-visibility--2026-11-02). No API rebuild, sync, private-volume mutation, dependencies, commits or remote publication occurred in this final verification.
