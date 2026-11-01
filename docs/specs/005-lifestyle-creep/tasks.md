---
description: "Executable local task handoff for the lifestyle-creep detector"
---

# Tasks: Lifestyle creep detector

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [history contract](contracts/bills-history-v6.md), [API contract](contracts/lifestyle-creep-api.md), [card contract](contracts/bills-card.md), [quickstart.md](quickstart.md).

**Setup**: Ran `.specify/scripts/powershell/setup-tasks.ps1 -Json` with explicit `SPECIFY_FEATURE_DIRECTORY='docs/specs/005-lifestyle-creep'`. Used its resolved `.specify/templates/tasks-template.md` content and all available design artifacts.

**Tests**: Required, synthetic-only. Write each behavior's tests first; establish a meaningful failing assertion before implementing it, then rerun to green. Do not mistake an unsafe import or missing dependency for the expected failure. No application imports, runtime tests, servers, or implementation occur during task generation.

**Organization**: Story-owned tasks, explicit dependencies, and sequential backend/frontend execution slices. Checked markers represent completed implementation or executed checks, not an implied planning/merge-review pass.

**Historical 2026-11-02 multi-month amendment**: T001–T048 completed that earlier interpretation, including its recorded reviews and container smoke. User clarification now supersedes that interpretation; those historical test counts do not verify the corrected one-target/reference-period contract. The failed merged-plan gate remains failed; no publication occurred.

**Current checkpoint (2026-11-02)**: T057–T060 complete, **60/60 checked; zero pending**. Supplied T059 independent review **PASS, no significant issues**; T060 rebuilt both images and passed **68 browser assertions** (57 synthetic, 11 unmocked structural/metadata-only). Both services remain healthy with the named private volume retained. Live legacy report history correctly remains insufficient pending explicit user-run resync; no sync occurred. Exact evidence and manifest are in quickstart section 21. Earlier task checkpoints remain historical.

## Local Authorization and Failed Gate

- Per the coordinator handoff, mandatory `before_tasks` merged-plan review was **RUN and FAILED** because `spec.md` and `plan.md` were untracked and absent from `origin/main`. The coordinator stopped and reported it. Local task-generation inspection confirms untracked artifacts; no remote review is certified.
- The latest direct user continuation says, "If you were planning, stop planning and start implementing." Proceeding to tasks and later **local implementation/review** is an explicit local procedural deviation under that continuation, superseding the earlier user-level pause.
- This is **not a passed merged-plan gate**, **not an explicit `--skip-review` flag** (none was supplied), and not a claim that review or merge occurred. The gate remains failed. Do not edit/disable `.specify/extensions.yml`, rerun the gate merely to relabel it, or manufacture review evidence.
- Optional before/after-task commit hooks and later optional publication/commit hooks are skipped. Remain only in the assigned worktree on its existing app-managed branch; no branches, commits, pushes, PRs, merges, or publication.
- This handoff ends ready for implement. Earlier phase-only statements in the input documents describe their original deliveries; [plan.md](plan.md#workflow-and-gate-handoff) and this section record the subsequent continuation.

## Format and Path Conventions

- Checklist format: `- [ ] TNNN [P?] [USn?] Description with exact paths. Depends: TNNN.`
- `[P]` marks independent files after the listed prerequisites; it does not override the required sequential specialist slices. No same-file concurrent edits.
- Paths are relative to this worktree. Backend: `src/budget_api/`; client: `client/src/`; feature documentation: `docs/specs/005-lifestyle-creep/`.
- Reuse Python/FastAPI/Pydantic, React/TypeScript, pytest, and pnpm/Vitest conventions. No dependencies, lockfile changes, infrastructure work, sibling runway/debts work, or global Bills refactors.
- Decimal strings for **new** fields and exact Decimal decisions are the documented feature-local convention. Existing numeric/title totals remain unchanged. Schema 6 is additive; explicit successful re-sync is the only history upgrade, not a SQL migration or eager rewrite.

## Phase 1: Setup (Safe Shared Fixtures)

**Purpose**: Establish safety before any later test collection or application import.

- [x] T001 Close test-isolation gaps in `src/budget_api/tests/conftest.py` and `src/budget_api/tests/bills/conftest.py`: reuse temporary storage/environment fixtures, add scoped autouse coverage for builder fallback, and defer application/lifespan imports until storage is isolated. Preserve the existing frozen Bills clock; feature tests explicitly freeze their own window dates. Set `BILLS_CALC_LOG=0` in every test shell **before collection/import**; fake all source calls and tripwire unintended filesystem/network access. Verify the isolated harness before feature tests. Depends: none.

## Phase 2: Foundational (Blocking Contracts)

**Purpose**: Shared evidence and response types. No story implementation before T001–T003.

- [x] T002 Add model contract tests in `src/budget_api/tests/bills/test_cc_spend_history.py` and `src/budget_api/tests/bills/test_lifestyle_creep.py`: complete/partial/unavailable state invariants, optional legacy history, canonical decimal-string serialization, positive category IDs, valid scope keys, exact array cardinalities, nullable percentages, and rejection of wrong-type/negative/non-finite amounts without coercion. Depends: T001.
- [x] T003 Add history models and optional `PartnerBills.cc_spend_history` in `src/budget_api/models/bills.py`, advance new snapshot schema to 6, and create response models in `src/budget_api/models/lifestyle_creep.py` per both contracts. Preserve legacy defaults, fields, and numeric serialization; do not infer identity/history or convert old money fields. Make T002 pass. Depends: T002.

**Checkpoint**: Typed additive contracts pass isolated tests; no history is upgraded on read.

## Phase 3: User Story 1 — Understand Sustained Category Spending Growth (P1)

**Goal**: Stable-ID evidence, exact explainable calculation, and inspectable ready-state results.

**Independent test**: Synthetic May–September `[100,100,100,130,140]` yields August/September baselines 100/110, changes 30/30, rolling 30%/~27.27%, and separate ordinary ~7.69%. Render the ready card from the same contract fixture. Equal titles remain distinct; renamed IDs remain continuous. No live sync or other Bills mode is needed.

### Tests for User Story 1

- [x] T004 [P] [US1] Extend `src/budget_api/tests/bills/test_cc_spend_history.py` with shared-filter parity, posted outgoing magnitudes, pending/refund/payment/transfer/exclusion rejection, original child category IDs, partner separation, duplicate titles/renames, deterministic labels, uncategorized splitting, exact decimal accumulation, scope hash order/label invariance and effective-filter changes, and unchanged legacy totals/null semantics. Validate malformed source inputs before permissive filtering. Depends: T003.
- [x] T005 [P] [US1] Extend `src/budget_api/tests/bills/test_lifestyle_creep.py` with every calculation row in `spec.md`/`quickstart.md`: both equality boundaries, `132.001`, flat elevated months, isolated spike, decline, sparse/zero precedence, zero prior-month denominator, empty/all-zero/appearing/disappearing categories, partner/category ID ordering and latest nonempty labels. Cover repeating outputs, coefficients beyond default Decimal precision, and string round trips. Depends: T003.
- [x] T006 [US1] Add `client/src/api/__tests__/lifestyle-creep.test.ts` and ready-state cases in `client/src/components/bills/__tests__/LifestyleCreepCard.test.tsx`: encoded query/default behavior, unchanged decimal strings/ApiError, alert/no-alert/suppressed detail, both baseline windows, separate ordinary growth, duplicate-title disambiguation, empty categories and separate uncategorized samples. Use synthetic contract fixtures, not production Bills mock fallback. Depends: T003.

### Implementation for User Story 1

- [x] T007 [US1] Add a strict validated CC-history aggregation entry point in `src/budget_api/services/bills_derivations.py`: validate original collection/date/amount/ID/filter/ownership context before shared filter iteration, require explicit partner account sets, aggregate with `Decimal(str(value))`, split uncategorized without persisting `-1`, and choose deterministic source labels. Compute the canonical `cc-spend-v1` scope fingerprint from the exact data-model inputs, including effective transfer/payment/exclude roles, never labels or monthly category presence. Depends: T004.
- [x] T008 [US1] Enrich `src/budget_api/services/bills_builder.py` with an explicit typed per-month acquisition context passed through chain/single-month builds and schema-6 history for every partner. Apply source-state precedence: absent context → unavailable; invalid source → unavailable only if legacy build is safe, otherwise abort; no CC/future → unavailable; open acquisition → partial; validated closed acquisition → complete. Preserve all legacy outputs and keep new derivation outside exception-to-zero fallbacks. Depends: T007.
- [x] T009 [US1] Create pure evaluation in `src/budget_api/services/lifestyle_creep.py`: five complete comparable inputs, category union with only observed absence zero-filled, newest nonempty labels, lexical stable-ID ordering, own prior-three baselines, two strict cross-product tests `100*(3*S-T) > p*T`, sufficiently sized local Decimal precision, initial two-positive-month screen and zero-baseline precedence. Return every category, both comparisons and uncategorized samples; derive 28-significant-digit half-even explanations only after exact verdicts. No builder import. Depends: T005.
- [x] T010 [US1] Create `client/src/types/lifestyle-creep.ts` and `client/src/api/lifestyle-creep.ts`, and add optional/nullable history types in `client/src/types/bills.ts`. Mirror contracts exactly, preserve new decimals as strings, encode month/raw valid threshold through existing `apiGet`, and retain ApiError behavior. No current catalogs, dashboard-neighbor derivation, or production mock fallback. Pass wrapper tests from T006. Depends: T006.
- [x] T011 [US1] Create thin typed `client/src/components/bills/LifestyleCreepCard.tsx` and `client/src/components/bills/LifestyleCreepDetails.tsx` for ready results. Render all categories/outcomes, five observations, latest fields from comparison two, both full comparisons, reason-aware undefined percentages, and separate five-month uncategorized detail. Explain sparse limitations and strict recorded-spending rule with CC-only, non-advisory copy; never recompute verdicts. Pass ready-state tests from T006; final privacy/state wiring follows in US4 before delivery. Depends: T009, T010.

**Checkpoint**: Producer/evaluator and ready presentation are independently testable with synthetic evidence. This is the core MVP calculation, not yet a complete Bills-page release.

## Phase 4: User Story 2 — Know When History Cannot Support a Conclusion (P1)

**Goal**: Trusted sync provenance, bounded saved-history retrieval, and honest availability/error states.

**Independent test**: Across only five synthetic snapshot files, distinguish complete zero, missing/interior/legacy/partial/scope-changed records, unknown partners and corruption. A ready Partner A remains inspectable under partial Partner B coverage; corruption cancels all verdicts. Repair files and Retry to ready without sync.

### Tests for User Story 2

- [x] T012 [P] [US2] Create `src/budget_api/tests/test_sync_lifestyle_history.py` with fake source client and temporary publication paths: successful full-range closed-month empty input, missing/invalid input, fetch begun before close and built after rollover, missing context, no CC accounts, future input, later closed re-sync, and transaction-fetch failure after an earlier month succeeded. Assert failure publishes **no new Bills snapshots** and prior partial/unavailable files stay unchanged. Depends: T008.
- [x] T013 [P] [US2] Create `src/budget_api/tests/bills/test_lifestyle_creep_api.py` covering the full API/saved-input matrix in `quickstart.md`: five exact reads once each, October/January windows, invalid query → 400/zero reads, every diagnostic and overall status, stable partner union/unassigned identity, scope mismatch on all five months, literal JSON null/duplicate keys/corrupt schema/identity/amount/I/O → generic 500, no successful partial on corruption, no-store on 200/400/500, corrected-file Retry, and legacy dashboard compatibility. Tripwire scans, config/raw reads, client construction, sync and writes. Depends: T003, T009.
- [x] T014 [US2] Extend `client/src/components/bills/__tests__/LifestyleCreepCard.test.tsx` for every issue code/reason, missing whole-month and unassigned legacy rows, insufficient/partial/ready-empty states, preserved ready-partner detail, no incomplete-partner money/verdicts, uncategorized-only coverage, the required re-sync guidance sentence and `/sync` navigation without acquisition. Depends: T011.

### Implementation for User Story 2

- [x] T015 [US2] Carry per-month acquisition-start time, exact requested full-month bounds and successful supplied transaction inputs through `src/budget_api/services/sync_runner.py` into the builder context from T008. Validate before certifying complete; preserve no-publication-on-any-transaction-fetch-failure across the requested attempt and existing atomic writer. Never promote partial data on elapsed time or default missing input to empty. Pass T012 and producer tests. Depends: T008, T012.
- [x] T016 [US2] Add the bounded reader/readiness adapter to `src/budget_api/services/lifestyle_creep.py`, reusing `storage.bills_dashboard_path` from `src/budget_api/services/storage.py` without a broad storage rewrite. Read only five exact paths, distinguish absence from null, reject duplicate keys/invalid encoding/non-finite constants, and strictly validate the minimal envelope/schema/identity/history contract before evaluation. Union stable partners, retain unassigned issues, require all five scopes, sort/deduplicate diagnostics, and enforce corrupt-error precedence over partial readiness. No scans, catalogs, source fallback, writes or cache. Depends: T009, T013, T015.
- [x] T017 [US2] Add thin `GET /api/bills/lifestyle-creep` in `src/budget_api/routers/bills.py`, backed by selection validation in `src/budget_api/services/lifestyle_creep.py`: required real ASCII month, API-process-clock current-month and five-predecessor bounds, omitted-only default threshold, exact decimal grammar and inclusive 1–100 bounds, and duplicate query rejection **before path resolution**. Ignore unrelated query keys per convention. Return contract 200/400/generic-500 shapes; add the route to `src/budget_api/main.py` no-store handling for success and errors. Pass T013 without altering legacy routes. Depends: T016.
- [x] T018 [US2] Add issue/availability rendering in `client/src/components/bills/LifestyleCreepCard.tsx` using T014 fixtures: required window and affected partner/month/reason, prominent partial coverage, ready-partner details, no verdict for unknown evidence, and existing `/sync` link with re-sync guidance (first window month through the usual sync end month, at least the current month) but no invented route parameters or auto-sync. Complete empty evidence remains ready, not missing. Depends: T014.

**Checkpoint**: The endpoint can explain readiness safely; re-sync produces trusted evidence, but GET/Retry never acquires it. Full page-state wiring remains US4.

## Phase 5: User Story 3 — Adjust Detection Sensitivity Without Changing the Rule (P2)

**Goal**: Exact bounded threshold tuning for one visit, without changing history/baselines/sustained count.

**Independent test**: `[100,100,100,130,140]` flags at 20% but not 30%; 1/20.5/100 are accepted. Invalid edits cause no request and cannot relabel old results. Month changes keep the applied value; fresh visit resets to 20.

### Tests for User Story 3

- [x] T019 [US3] Extend `src/budget_api/tests/bills/test_lifestyle_creep.py` and `src/budget_api/tests/bills/test_lifestyle_creep_api.py` with exact threshold integration regressions: 1/20.5/30/100, equivalent exponent/leading-zero forms, URL-encoded plus, very precise in/out-of-range decimals including `100.00000000000000001`, omission versus empty/whitespace/boolean/null/non-finite/underscore/comma inputs and repeated parameters. Assert truthful canonical threshold, fixed five/three/two lengths, strict equality and zero reads for all rejected selections. The server implementation is T009/T017; correct regressions there before handoff. Depends: T017.
- [x] T020 [P] [US3] Create threshold cases in `client/src/lib/__tests__/lifestyle-creep.test.ts` matching T019 grammar/bounds and canonical equivalence without JS float rounding. Verify exact acceptance/rejection, explicit empty handling, and no silent clamp/default. Depends: T010.
- [x] T021 [P] [US3] Extend `client/src/components/bills/__tests__/LifestyleCreepCard.test.tsx` and create `client/src/pages/__tests__/BillsPage.lifestyle-creep.test.tsx` sensitivity cases for invalid draft/no request, truthful earlier applied label, valid Apply, equivalent-value deduplication, applied-threshold persistence across detector months, and fresh-mount reset without persistent storage. Page cases turn green at T029. Depends: T018.

### Implementation for User Story 3

- [x] T022 [US3] Create `client/src/lib/lifestyle-creep.ts` exact decimal-text threshold validation/canonicalization for grammar and 1–100 comparisons; preserve value and reject invalid inputs before Apply. Keep it feature-local and dependency-free, with no financial calculation or persistent state. Pass T020. Depends: T020.
- [x] T023 [US3] Add labelled controlled threshold text input, decimal affordance, Apply, associated inline errors and explicit applied-value/not-applied feedback to `client/src/components/bills/LifestyleCreepCard.tsx`. Define typed draft/applied callbacks for visit-local ownership in `client/src/pages/BillsPage.tsx`; use T022, never native empty-to-zero or float-only bounds. Keep baseline three and sustained two fixed. Page ownership and request lifecycle are completed in T029. Depends: T021, T022.

**Checkpoint**: Server threshold boundaries and controlled sensitivity behavior are covered independently. Do not mark page lifecycle assertions complete before US4 integration.

## Phase 6: User Story 4 — Review Results Safely Within Bills (P2)

**Goal**: An independently fetched, accessible, privacy-masked Bills card in every display state.

**Independent test**: Mock all six loading/error/insufficient/partial/no-alert/alert states. Change detector month/threshold and race responses; only the current selection may display. Toggle hiding, Grid/Graph/Table and display window without detector refetch; all monetary DOM/assistive surfaces remain masked while percentages remain visible.

### Tests for User Story 4

- [x] T024 [P] [US4] Create `client/src/hooks/__tests__/useLifestyleCreep.test.ts` for loading/success/error/read-only Retry, selection-change clearing, stale success/failure rejection, cleanup/unmount, returned month/canonical-threshold mismatch, equivalent threshold deduplication, and only month/applied-threshold/retry request identity. Spy on requests; never use dashboard fallback. Depends: T010, T022.
- [x] T025 [P] [US4] Extend `client/src/pages/__tests__/BillsPage.lifestyle-creep.test.tsx`: current-month default, reachable detector-only historical-month selection and validation, rollover/year boundaries, persistence/reset from T021, card visible despite dashboard loading/error/notFound/empty data, placement outside Grid/Graph/Table/window controls, and no detector refetch on privacy/mode/past/future changes. Mock adjacent Bills/app-shell dependencies without sibling-feature integration. Depends: T021, T023.
- [x] T026 [P] [US4] Extend `client/src/components/bills/__tests__/LifestyleCreepCard.test.tsx` and `client/src/lib/__tests__/lifestyle-creep.test.ts` for every state, zero/signed/uncategorized money, overflow-safe decimal presentation, nullable versus genuine zero percentages, visible percentages with rounded-above-threshold verdicts, and hidden money in visible text/title/tooltips/aria/hidden detail/data attributes. Exercise keyboard Apply/Retry/disclosures/sync link, labelled validation, and busy/error announcements. Depends: T023.

### Implementation for User Story 4

- [x] T027 [US4] Create `client/src/hooks/useLifestyleCreep.ts` with typed loading/data/error/Retry state over T010 API; key only on detector month and canonical applied threshold. Clear previous-selection results, guard request generation/cleanup, reject mismatched response identity, and suppress stale success/error completions. Retry rereads the same selection; no amount/mode/window dependencies, storage, mock fallback or verdict math. Pass T024. Depends: T024.
- [x] T028 [US4] Complete loading/error/Retry and accessibility in `client/src/components/bills/LifestyleCreepCard.tsx` and `client/src/components/bills/LifestyleCreepDetails.tsx`; add presentation helpers in `client/src/lib/lifestyle-creep.ts`. Subscribe to `useAmountsHidden()` and reuse masked money/sign conventions, converting only at formatting boundaries with privacy-aware finite-decimal text fallback on overflow. Mask **all** monetary surfaces, including collapsed detail and zeros, without masking percentages/status/IDs or logging money. Keep both components thin; pass T026. Depends: T018, T023, T026.
- [x] T029 [US4] Wire `client/src/pages/BillsPage.tsx` to the hook/card with visit-local draft/applied threshold and detector-only viewing month defaulting to the current month of the browser's local calendar. Expose a labelled historical-month control; keep existing dashboard month/window semantics unchanged. Mount the card once between `HouseholdSummary` and `BillsDashboard` where available (after the T035 rebase it sits below the Runway panel and above `BillsDashboard`), outside all dashboard early-return branches and visualization controls. Keep it usable on dashboard failures, validate/label the actual selected month, preserve threshold on month change, and reset on fresh visit. Pass all T021/T025 integration assertions. Depends: T025, T027, T028.

**Checkpoint**: All four stories are wired. No feature completion claim until the safe validation/review tasks pass or an unavailable check is explicitly reported pending.

## Phase 7: Polish & Cross-Cutting Validation

**Purpose**: Verify the complete feature locally without private data or publication.

- [x] T030 Run targeted Python tests, then the full Windows non-renderer command in `docs/specs/005-lifestyle-creep/quickstart.md` covering `src/mega/tests`, `src/v4_pipeline/tests`, `src/mom/tests`, and `src/budget_api/tests`. Re-establish `BILLS_CALC_LOG=0` and `PYTHONPATH=src` per shell; verify every exercised import/filesystem/lifespan path is isolated **before** running. Record exact results in quickstart; if isolation cannot be proven, leave the full suite pending rather than access real data. No Ubuntu/renderer pass claim. Depends: T019.
- [x] T031 Run the targeted client tests from `docs/specs/005-lifestyle-creep/quickstart.md`, adding `client/src/lib/__tests__/lifestyle-creep.test.ts` and the new page test; then run full `pnpm test` and `pnpm build` in `client`. Include existing Bills privacy/compatibility coverage. Use pinned tooling; restore locked dependencies only after actual missing-dependency failure, never after assertion failure. No new lint script or lockfile edits. Record exact results in quickstart. Depends: T029, T030.
- [x] T032 Execute all eight synthetic browser-smoke scenarios in `docs/specs/005-lifestyle-creep/quickstart.md` using available interception tooling. If needed use only an attached client helper on 127.0.0.1:5205; install catch-all API mocks/unknown-request and external-origin aborts **before navigation**, so nothing reaches the existing Vite proxy/backend. No API server, live sync, or services 8080/5200/8100. Check accessibility/privacy/request counts and stop the helper. If tooling is absent, explicitly record pending rather than install a browser dependency. Depends: T031.
- [x] T033 Perform local development review and caveman self-review against `docs/specs/005-lifestyle-creep/spec.md`, `plan.md`, and all three contracts; inspect only feature changes in `src/budget_api/` and `client/src/`. Check filter parity/source trust, exact math, corrupt-error precedence, request bounds/races, masking, compatibility and scope exclusions. Return severity/file/line findings to the owning specialist sequentially, fix and rerun affected/full checks, and record unresolved risks in `docs/specs/005-lifestyle-creep/quickstart.md`. This is local review, not merged-plan review. Depends: T030, T031, T032.
- [x] T034 Update `docs/specs/005-lifestyle-creep/tasks.md`, `plan.md`, and `quickstart.md` with actual completion, file manifests, additive schema-6/re-sync upgrade and rollback notes, commands/results and pending checks. Append only verified durable facts to `memory.md`. Recheck branch/worktree scope and absence of sibling/governance/lockfile changes; retain the failed-gate deviation verbatim in substance. No publication/commit hook. Leave any unavailable validation task unchecked; do not claim fully validated completion while it is pending. Depends: T033.

**T033/T034 final status (first implementation round, 2026-10-31)**: Initial integrated review **FAIL** and both Important source-integrity findings are preserved in [review-report.md](review-report.md). Both reproduced before fixes and are remediated with 36 added regressions. Affected tests at that point: **448 passed**; full Windows nonrenderer at that point: **1220 passed, 2 deselected** (superseded by the final counts below). Independent re-review closed both findings and passed the code review; the coordinator resolved its sole caveat by checking the full tracked/untracked Git manifest. **34/34 tasks were complete locally at that point.** [Quickstart section 13](quickstart.md#13-integrated-qa-rework-cycle1--2026-10-31) preserves red/green history, and section 14 records final acceptance. No consumer-contract change required a client rerun after cycle1. A later unmocked browser to real-FastAPI smoke on synthetic temporary storage (isolated ports 5205 and 8105, no response mocks) passed 182/182 assertions with zero failed requests and no repository change; see [quickstart section 15](quickstart.md#15-unmocked-real-api-browser-smoke---2026-10-31). The merged-plan gate remains failed under the recorded continuation; no publication is claimed. Later work (rebase onto main, real-data validation and the independent review round) is tracked in Phase 9 below and in [quickstart section 16](quickstart.md#16-post-rebase-real-data-validation). Final counts after that work: backend non-renderer suite **1580 passed, 2 deselected**; client **49 files, 540 tests passing**; production client build passing.

## Phase 9: Rebase, real-data validation and review round

**Purpose**: Carry the detector onto the main branch that now contains the runway feature, run it on real data through the container stack without recording any private value, and close an independent review. Results are recorded generically in [quickstart section 16](quickstart.md#16-post-rebase-real-data-validation) and in the post-rebase section of [review-report.md](review-report.md).

- [x] T035 Rebase the feature commits onto the updated main branch (a safety ref was created first) and resolve the two real conflicts: the union of the no-store path set and router registrations in `src/budget_api/main.py`, and the runway page taken with the detector mount re-applied in `client/src/pages/BillsPage.tsx`. Add a never-resolving detector API client stub to `client/src/tests/BillsPage.test.tsx` so runway fetch-count assertions stay intact, the 37 merge and routing tests in `src/budget_api/tests/bills/test_lifestyle_creep_runway_merge.py`, and the ordering and independence cases in `client/src/pages/__tests__/BillsPage.lifestyle-creep.test.tsx`. Backend and client suites and the production client build pass on the merged tree. Depends: T034.
- [x] T036 Bring up the container stack with an explicit compose project name after creating a byte-verified copy of the private-data volume and tagging the previous images for rollback. No copy name, timestamp or data value is recorded. Depends: T035.
- [x] T037 Run the first real re-sync, find that every history block reported `invalid_source` because `compute_cc_spend_history` required every `category_roles.json` key to be a canonical category ID while the reports pipeline stores a role for a synthetic non-numeric `uncategorized` key, and fix it in `src/budget_api/services/bills_derivations.py` (only `exclude` keys define the population and scope fingerprint and must be canonical IDs; other non-ID keys are ignored; a non-ID `exclude` key still fails closed). Add 22 synthetic regressions in `src/budget_api/tests/bills/test_cc_spend_history.py` and `src/budget_api/tests/test_sync_lifestyle_history.py`. Depends: T036.
- [x] T038 Run an independent read-only review of the post-rebase delta. Verdict: pass-with-caveats, no critical or high findings. The ten findings and their dispositions are in `docs/specs/005-lifestyle-creep/review-report.md`. Depends: T037.
- [x] T039 Apply the review-driven fixes: re-sync guidance wording in the UI and docs, strict role-key test forms in `src/budget_api/tests/bills/test_cc_spend_history.py`, stale comment refresh in `src/budget_api/main.py` and `src/budget_api/routers/bills.py`, runway header comment restored in the Bills page, no-store fetch option on the detector request, and the known limitations documented in `docs/specs/005-lifestyle-creep/quickstart.md` and `README.md`. Depends: T038.
- [x] T040 Rebuild the container stack from the final tree and repeat the structural verification of the real page. Done by the coordinator on 2026-11-02 after T041, on the working tree (the committed feature work plus the uncommitted tab move and documentation changes; no documentation commit was made): frontend image rebuilt and recreated on the existing data volume, then a headless Chromium check of Bills, the new tab and the deep link on real data, recording structure and status only. Results in [quickstart section 17](quickstart.md#container-rebuild-and-real-page-check-t040---2026-11-02). Depends: T039, T041.
- [x] T041 Move the detector to its own Lifestyle Creep tab/route at the user's request (2026-11-02): new `client/src/pages/LifestyleCreepPage.tsx` owns the visit-local month and threshold state, `client/src/router.tsx` adds the `lifestyle-creep` route, `client/src/layouts/AppLayout.tsx` adds the **Lifestyle Creep** nav tab after **Bills**, and `client/src/pages/BillsPage.tsx` drops all detector wiring. Components stay in `client/src/components/bills/`; the API path is unchanged. `client/src/pages/__tests__/BillsPage.lifestyle-creep.test.tsx` is replaced by `client/src/pages/__tests__/LifestyleCreepPage.test.tsx`, `client/src/tests/BillsPage.test.tsx` asserts Bills neither renders nor fetches the detector, and `client/src/tests/LifestyleCreepRoute.test.tsx` covers the deep link and nav tab. Results in [quickstart section 17](quickstart.md#17-separate-lifestyle-creep-tab---2026-11-02). Depends: T039.

**Checkpoint**: T035 to T041 are complete (41 of 41 tasks). T040 was verified on the working tree, not on a documentation commit. The failed merged-plan gate remains failed and no publication is claimed.

## Dependencies & Execution Order

### Story Dependency Graph

```text
T001 safety → T002–T003 contracts
                  ├─ US1 evidence/calculation + ready UI
                  └─ US2 provenance/readiness → bounded GET
US1 + US2 → US3 sensitivity
US1 + US2 + US3 → US4 hook/privacy/page integration
backend checks → client checks → synthetic browser smoke → local review → handoff
handoff → rebase onto main → real-data validation → independent review → review fixes → final container rebuild
```

The graph is a summary; each task's `Depends` list is authoritative. Numeric IDs follow template/story order, not a requirement to interleave specialists. US2 intentionally depends on US1 evidence; US4 intentionally depends on earlier presentation/contracts. Independent tests use synthetic service inputs or typed component props, not incomplete production fallbacks.

### Sequential Specialist Execution Slices

| Slice | Task order | Boundary / exit evidence |
| --- | --- | --- |
| Backend first | T001–T005 → T007–T009 → T012–T013 → T015–T017 → T019 → T030 | Python contracts, source provenance, additive snapshot production, evaluator and endpoint. Required synthetic/regression tests and safe Windows suite; exact file manifest and results. No client edits. |
| Frontend second | T006 → T010–T011 → T014 → T018 → T020–T023 → T024–T029 → T031 | Typed wrapper, exact input helpers, thin card/details, hook and reachable page integration. Required client tests/build and manifest. No server or sibling edits. |
| Local validation/review | T032 → T033 → T034 | Synthetic browser evidence, local review/fix loop, truthful task/result updates. Backend/frontend corrections remain sequential. No review-gate pass or publication claim. |
| Rebase, real-data validation and review round | T035 → T036 → T037 → T038 → T039 → T040 | Rebase with merge tests, container bring-up with a verified data copy, real re-sync and its defect fix, independent review, review fixes, then the coordinator's final rebuild. Results are generic and sanitized (quickstart section 16). |

T030/T031 each write their own results sequentially; do not edit the shared quickstart concurrently. If a full check is safely unavailable, record the exact limitation and preserve its unchecked state; this is not a pass or authorization to weaken isolation.

### Parallel Examples by Story

These are eligible same-slice examples only, not an instruction to run backend and frontend specialists together:

- **US1**: After T003, T004 producer tests and T005 calculator tests touch separate Python files. Each must finish before its implementation.
- **US2**: After their listed dependencies, T012 sync tests and T013 endpoint/readiness tests touch separate modules with independent temporary fixtures.
- **US3**: In the frontend slice, T020 exact-parser tests and T021 sensitivity presentation/page tests can be authored independently; T022/T023 wait for their respective tests.
- **US4**: After T023 and the other listed dependencies, T024 hook tests, T025 page tests and T026 card/helper privacy tests have disjoint files. T027 and T028 may follow independently once their tests exist; page wiring waits for both.

Never overlap edits to `services/lifestyle_creep.py`, `LifestyleCreepCard.tsx`, shared fixtures, or page tests between stories. Implementation is test-first within each slice.

## Requirement and Contract Coverage

| Coverage | Primary tasks |
| --- | --- |
| FR-001, FR-004–FR-007; stable IDs, CC population, uncategorized, legacy preservation | T002–T004, T006–T008, T010–T011, T013 |
| FR-008–FR-011; completion, no false zeros, scope, partner readiness | T004, T008, T012–T016, T018 |
| FR-012–FR-016; exact math, sparse/zero rules, full explanations | T005, T009, T011, T026, T028 |
| FR-017–FR-018; exact configurable threshold and visit lifecycle | T017, T019–T023, T025, T027, T029 |
| FR-002–FR-003, FR-019–FR-021, FR-024; legacy window, bounded GET, states/errors/Retry | T013, T016–T018, T024–T025, T027–T029 |
| Historical multi-month FR-026–FR-032 interpretation; now superseded | T042–T048 (historical verification only; not evidence for the current contract) |
| Corrected target/reference period, one server comparison, atomic selection, response identity, variable evidence and privacy | T049–T053 |
| FR-022–FR-023, FR-025; privacy, access, independent requests, descriptive scope | T011, T018, T023–T029, T032–T033 |
| Schema-6 contract | T002–T004, T007–T008, T012–T016 |
| API contract | T002–T003, T005, T009–T010, T013, T016–T017, T019, T024, T027 |
| Card contract; SC-001–SC-008 end-to-end verification | T006, T011, T014, T018, T020–T029, T030–T033 |

## Implementation Strategy

1. **Core MVP first**: Build trusted evidence and US1 exact calculation, then US2 fail-closed retrieval. Demonstrate using isolated tests, not real history.
2. **Smallest safe Bills increment**: US1 alone is not a shippable card; US2 diagnostics and US4 privacy/independent wiring are required before any UI delivery. Complete US3 visit-local tuning in the same sequential frontend slice rather than shipping a misleading interim threshold.
3. **Incremental verification**: Run behavior tests after each change; backend validation before frontend handoff, then client checks, synthetic smoke and local review. Fix only feature regressions; report unrelated baseline failures without touching sibling work.
4. **Safe commands**: Follow quickstart exactly. Never read/search/print/write real `data/private/`, credentials/`.env`, actual financial records, or the main checkout. Only isolated synthetic fixture paths are permitted. Dependency restoration is failure-driven and locked.
5. **Historical prior-interpretation completion count**: 41 tasks: setup 1, foundational 2, US1 8, US2 7, US3 5, US4 6, final validation/handoff 5, rebase/real-data validation/review round 7 (including T041, the user-directed move to a separate tab). The historical **41 of 41 complete** statement applied before the corrected target/reference clarification and is not the current task status. T040 (final container rebuild and structural verification) was done by the coordinator on 2026-11-02 against the working tree, with the tab move and documentation changes still uncommitted ([quickstart section 17](quickstart.md#container-rebuild-and-real-page-check-t040---2026-11-02)). The first 34 were complete locally after the first implementation round, including independent re-review and coordinator scope verification. Exact commands, file manifests, synthetic screenshots and the existing app-navigation mobile-overflow limitation are recorded in [quickstart](quickstart.md#11-frontend-execution-evidence--2026-10-31); the unmocked real-API smoke is in [section 15](quickstart.md#15-unmocked-real-api-browser-smoke---2026-10-31); the post-rebase real-data validation and known limitations are in [section 16](quickstart.md#16-post-rebase-real-data-validation). The failed merged-plan gate remains failed; it was not rerun or relabelled. No publication is claimed.

## Historical Phase 10: Selectable Comparison Period — 2026-11-02 (prior interpretation, superseded)

**Historical scope only**: The prior amendment selected inclusive From/To evaluated months, 1–24 completed months, with sustained semantics. It is superseded by Phase 11's one-target/reference-period contract. Counts and results below preserve the earlier record and do not certify current controls. No new feature directory, feature pointer, branch, dependencies, hooks or governance changes. Preserve all existing uncommitted tab-move/doc edits.

- [x] T042 [US5] Amend `docs/specs/005-lifestyle-creep/spec.md`, `plan.md`, `data-model.md`, `contracts/lifestyle-creep-api.md`, `checklists/requirements.md` and `tasks.md` with dated precedence, requirements, assumptions, acceptance, range contract and bounded read policy. Preserve earlier dated evidence and failed-gate honesty. Depends: T041.
- [x] T043 [US5] Add synthetic range tests in `src/budget_api/tests/bills/test_lifestyle_creep.py` and `test_lifestyle_creep_api.py`: 1/2/6/24 months, 25 rejection, earliest/latest/year boundaries, strict equality, any consecutive eligible pair, category sparse/zero gaps, one-month descriptive-only behavior, variable DTO/detail sizes, all-evidence readiness and exact no-side-effect reads. Verify a meaningful failing range case before implementation. Depends: T042.
- [x] T044 [US5] Extend `src/budget_api/services/lifestyle_creep.py`, `models/lifestyle_creep.py` and `routers/bills.py`: optional paired range inputs, full validation before I/O, default compatibility, additive echoed boundaries, 4–27 exact evidence snapshots, variable arrays, exact rolling math and any-consecutive-pair verdict. Preserve Decimal rules, category-summary compatibility, old error messages, no-store and no writes/sync/catalogs. Depends: T043.
- [x] T045 [US5] Run the targeted synthetic lifecycle/model/API/compatibility tests, record commands/counts here and check `git diff --check`. Fixtures must isolate storage before imports and use a worktree-local pytest base directory; no real financial files, `.env`, Docker or neighboring checkout access. Depends: T044.
- [x] T046 [US5] Frontend: update `client/src/types/lifestyle-creep.ts`, `api/lifestyle-creep.ts`, `hooks/useLifestyleCreep.ts`, feature helpers/controls/details and `pages/LifestyleCreepPage.tsx`, with colocated tests and `docs/specs/005-lifestyle-creep/contracts/bills-card.md`. Explicit From/To, derive `month=To+1`, validate whole request/response identity, render every comparison and final selected month, preserve sensitivity/Retry/races/privacy/accessibility, and run targeted/full client tests/build as appropriate. Depends: T045.
- [x] T047 [US5] Independent integrated review and synthetic acceptance of the backend/client amendment, including date bounds, range races, sustained semantics, full evidence coverage, monetary masking and preserved Bills/tab behavior. Coordinator handoff reports independent code-review **PASS, no significant findings**; synthetic acceptance is the recorded T045/T046 tests, not a new verifier test run. See `review-report.md`. Depends: T046.
- [x] T048 [US5] Coordinator-delegated verification specialist rebuilt API/frontend for the user-requested existing Compose stack after client completion/review. Both containers healthy, original named volume retained, and unmocked range-controls/results smoke **164 assertions passed**. Exact commands, six successful detector responses and honest insufficient-history coverage are recorded in `quickstart.md` section 18; prior T040 evidence was not reused as proof. No sync or production-data writes. Depends: T047.

**Backend red evidence**: `PYTHONPATH=src`, `BILLS_CALC_LOG=0`; `uv run --no-sync --locked python -m pytest src\budget_api\tests\bills\test_lifestyle_creep.py src\budget_api\tests\bills\test_lifestyle_creep_api.py -q -x -k 'variable_evaluation_lengths or explicit_range_exact_reads' --basetemp=.pytest_cache\comparison-period-red` failed on the intended four-observation/one-evaluation case because the original service required exactly five observations (1 failed, 199 deselected).

**Backend green evidence (2026-11-02)**:

```powershell
$env:PYTHONPATH = 'src'
$env:BILLS_CALC_LOG = '0'
uv run --no-sync --locked python -m pytest src\budget_api\tests\bills\test_lifestyle_creep.py src\budget_api\tests\bills\test_lifestyle_creep_api.py src\budget_api\tests\bills\test_cc_spend_history.py src\budget_api\tests\bills\test_lifestyle_creep_runway_merge.py src\budget_api\tests\test_sync_lifestyle_history.py -q --basetemp=.pytest_cache\comparison-period-final
git --no-pager diff --check
```

Result: **374 passed** in 8.34 seconds; one existing Starlette TestClient/httpx deprecation warning. No dependency changes. The original default calculation matrix and merge/error-body tests still pass; a new exhaustive 243-series synthetic reference check verifies default verdict and suppression compatibility. Worktree-local synthetic pytest directories were removed after validation. `git diff --check` passed. All six amended documents passed UTF-8/no-BOM, balanced code-fence, local-link and JSON-example checks; T001–T048 appear exactly once.

**Backend/spec manifest**: `src/budget_api/services/lifestyle_creep.py`, `src/budget_api/models/lifestyle_creep.py`, `src/budget_api/routers/bills.py`; tests `src/budget_api/tests/bills/test_lifestyle_creep.py`, `src/budget_api/tests/bills/test_lifestyle_creep_api.py`; existing feature documents `spec.md`, `plan.md`, `data-model.md`, `contracts/lifestyle-creep-api.md`, `checklists/requirements.md`, `tasks.md`. Existing edits to other client/docs files were not owned or replaced by this slice.

**Backend handoff completion (before T046)**: T042–T045 complete; T046–T048 pending at that handoff. No backend blocker found. That slice did not claim new client, browser, independent review, container or end-to-end success. No commit, push, PR, branch change, live sync, private-data read or Docker operation occurred.

**Frontend completion (T046, 2026-11-02; historical checkpoint before T047–T048)**: Atomic From/To controls, range validation (1–24 inclusive completed months), derived API month, four-field response identity, variable evidence/details, single-month warning and preserved exact sensitivity/privacy/Retry are implemented. Targeted client: **7 files, 181 tests passed**; full client: **50 files, 594 tests passed**; `pnpm build` (`tsc -b` and Vite) passed; static documentation/identifier containment: **9 passed**. Commands, red/green evidence, source/test/doc manifest and warnings are in [quickstart section 18](quickstart.md#18-selectable-comparison-period---2026-11-02). Checklist was inspected read-only (34 checked, zero unchecked), not independently approved. Existing tab move/backend edits remain intact. At this checkpoint, T047–T048 review/runtime work had not yet run; completion is recorded in the historical checkpoint below. No live sync, private-data, dependency, commit or branch operation.

**Final checkpoint (T047–T048, 2026-11-02; supersedes the frontend-only pending status above)**: The coordinator supplied independent review PASS with no significant findings. The delegated deployment/browser verification then passed 164 assertions against the actual rebuilt stack, without API mocks. All six detector requests returned 200; 24 API responses were observed, with zero HTTP/page/console/connection errors, external requests, non-GET requests or sync requests. Direct and navigation entry settled at `aria-busy=false`; default two-month and single-month results were ready, while both historical multi-month ranges correctly reported insufficient history rather than stale/default results. Both services remain healthy at `127.0.0.1:8080` and retain `pocket-smith-reports_private-data`. **48/48 tasks complete, zero pending**; the failed merged-plan gate is unchanged. Detailed evidence and this slice's documentation/artifact manifest are in quickstart section 18.

## Phase 11: One Target Month Versus Reference Mean — 2026-11-02

**Corrected scope**: One completed target month, an inclusive 2–24-month contiguous reference period before target, and a separate 1–100% threshold. This replaces multi-month evaluation and sustained-growth semantics. Keep all existing tab-move edits; frontend implementation is T051, followed by review and actual-container smoke.

- [x] T049 Replace backend selection/evaluation/response semantics in `services/lifestyle_creep.py`, `models/lifestyle_creep.py`, and `routers/bills.py`. Require a completed target strictly before current API month; validate paired `reference_start`/`reference_end`, default three prior months, and read reference months plus target only. Compare target to reference mean with exact strict threshold math, two-positive-month frequency suppression, optional adjacent-only MoM, one comparison and no sustained verdict. Depends: T048.
- [x] T050 Replace/add synthetic backend tests and update `spec.md`, `plan.md`, `data-model.md`, `contracts/lifestyle-creep-api.md`, `contracts/bills-card.md`, `checklists/requirements.md`, `research.md`, `quickstart.md`, and `tasks.md` to the corrected API and math. Preserve historical verification as historical, not current-contract evidence. Depends: T049.
- [x] T051 Frontend: replace prior From/To evaluation-period inputs with **Target month**, **Reference start**, and **Reference end** selectors; apply all three atomically, send the explicit target/reference triple, verify response identity, show one target-versus-mean comparison, and remove sustained UI language. Update client fixtures/tests, README, card contract, quickstart and memory. Focused and full client verification, build, containment tests, and diff check are recorded in quickstart section 19. Depends: T050.
- [x] T052 Independent review of the corrected frontend/API contract, selection validation, request races, result wording, privacy masking, and preserved route/Bills behavior. Independent read-only review passed with no significant issues after the API month-boundary fix. Depends: T051.
- [x] T053 Actual container smoke for the corrected target/reference controls and API response. Coordinator rebuilt API/frontend and ran the unmocked same-origin browser verification; services healthy, no real-data writes or sync. Exact evidence is in quickstart section 19. Depends: T052.

**T052 finding remediation (2026-11-02; implementation evidence, before independent sign-off)**:
Current API-month selections now return `insufficient_history` with a
null-partner `partial_month` / `open_month` issue and no partners/money instead
of a boundary-induced 400. All evidence is checked against the API clock
before any storage read, irrespective of saved completion status. Future and
malformed selections remain 400; client current-month exclusions remain
unchanged. Minimal card wording identifies the open month and required
evidence rather than falsely claiming reads. At this implementation-remediation
checkpoint, the final relevant backend run later reached **283 passed** across
five files; the remediation-focused client run reached **8 files, 140 passed**.
These are historical intermediate selections, not the final client counts.
Exact commands and final review/runtime evidence are in quickstart section 19.
This remediation paragraph itself records no Docker or actual-data verification.

**T049–T050 verification (2026-11-02; initial run, superseded by final counts below)**: `BILLS_CALC_LOG=0`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `PYTHONPATH=src`; focused lifestyle tests passed **101 tests**. Expanded regression run using `python -m budget_api.tests.isolated_run` across lifestyle unit/API, CC history, runway merge, and sync history passed **264 tests**, one existing Starlette TestClient/httpx deprecation warning. This is the earlier run before the month-boundary correction.

**T049–T050 manifest**: backend service/model/router, two lifestyle test modules, and the runway merge regression test; `spec.md`, `plan.md`, `data-model.md`, `contracts/lifestyle-creep-api.md`, `contracts/bills-card.md`, `checklists/requirements.md`, `research.md`, `quickstart.md`, `tasks.md`. Existing unrelated client source and tab-move source edits remain untouched.

**Final corrected-contract checkpoint (2026-11-02)**: T049–T053 complete, **53/53 checked; zero pending**. T052 independent review passed with no significant issues. The final backend regression selection passed **283 tests** with one pre-existing Starlette TestClient/httpx deprecation warning; the full client suite passed **50 files / 552 tests** and `pnpm build` passed with existing Vite warnings. T053 container/browser verification passed. Exact final commands and sanitized evidence are recorded in quickstart section 19. Phase 10/T047–T048 checks, review and smoke refer to the superseded multi-month contract; their evidence remains historical.

## Phase 12: Visit-local category visibility — 2026-11-02

- [x] T054 Implement per-partner/category stable-ID Hide, Show hidden categories, Restore and Restore all on the standalone Lifestyle Creep comparison table; filter corresponding disclosures, preserve state across loading/error/selection changes during a visit, reset fresh visits, preserve server assessment and masking, add synthetic regression tests and directly related documentation. Targeted: **7 files / 145 tests**; full client: **50 files / 558 tests**; production build passed. See quickstart section 20 for exact commands.
- [x] T055 Independently review T054 against FR-039–FR-041/SC-012, including identity isolation, all-hidden recovery, privacy, request counts and unchanged Bills behavior. Depends on T054. **PASS**, supplied independent code-review result in the final-verification handoff; no blocking findings reported.
- [x] T056 After T055 passes, rebuild and verify the category-visibility amendment in the container/browser, including keyboard controls, hidden row/disclosure behavior, privacy, selection/refetch retention and fresh-visit reset. Depends on T055. Frontend-only Compose build/update passed; both services healthy, API unchanged and existing named volume retained. Chromium **67/67 assertions passed**: **58 synthetic** and **9 unmocked structural-only**; zero browser errors, failed or unexpected/external requests. See quickstart section 20 for exact evidence and scope. Earlier T053 runtime evidence does not verify this amendment.

**Final visibility checkpoint (2026-11-02)**: **56/56 checked; zero pending**. This verification slice changed only `plan.md`, `tasks.md`, `quickstart.md`, `review-report.md`, and appended a sourced fact to ignored `memory.md`. No implementation defects were found. Existing **50 files / 558 client tests** remain the implementation baseline; no unchanged full suite was rerun. Final containment and whitespace results are recorded in quickstart section 20.

## Phase 13: Shared economy and report grouping

- [x] T057 Implement additive schema-7 report-economy acquisition/history, three fixed report-derived groups, signed decimal comparison semantics, explicit `grouping=report` read-only API, synthetic report/category parity and provenance/scope/API regressions, and related spec/model/API/history documentation. Preserve outgoing-card default behavior and all existing controls/hiding work. Verification and source manifest: quickstart section 21.
- [x] T058 Adopt report grouping in the standalone client: shared Home/Common table plus the two report-personal tables, response identity/validation, generic group/category visibility identity, signed explanation/privacy handling, resync guidance, focused/full client tests and build, and related UI/README documentation. Depends on T057. Commands, counts, source manifest and synthetic fixture selectors are recorded in quickstart section 21.
- [x] T059 Independently review the complete shared-economy amendment, report accounting parity, acquisition/scope fail-closed behavior, API compatibility, and client privacy/controls/hiding semantics. Depends on T057 and T058. **PASS, no significant issues**, supplied read-only independent review in the final-verification handoff; not a new self-review by the verifier.
- [x] T060 After T059 passes, rebuild and verify the actual container/browser UI with three report groups, synthetic refund/personal-owner cases, incomplete legacy/resync behavior, selection/threshold/privacy/hiding retention and unchanged Bills behavior. Depends on T059. Both image builds and dependent Compose update succeeded; **68/68 Chromium assertions**, the identical-ID component regression and **9 containment tests** passed. Both services remain healthy on port 8080 with the original named volume. Live report mode is honestly insufficient with all three headings and explicit resync guidance, not fake ready. See quickstart section 21. Prior two-person CC browser evidence is historical only.

**Historical backend handoff boundary, before T058**: T057 complete; T058–T060 pending. Historical
56/56 statements above do not assert completion of this amendment. No real-data
re-sync, dependency change, container action, commit, branch or PR was performed
by the backend slice.

**Historical frontend handoff boundary (2026-11-02), before T059–T060**: T057–T058 complete, **58/60 checked**.
T059 independent review and T060 container/browser verification were pending then.
The frontend slice used synthetic client tests only; no real-data or sync action,
dependency change, Docker, commit, branch, PR or nested agent was used.

**Final report-group checkpoint (2026-11-02)**: **60/60 checked; zero pending**.
T059 supplied independent review PASS and T060 deployment/browser acceptance are
complete. This verification slice changed only README, feature plan/tasks/
quickstart/review-report, ignored memory and session-only browser artifacts.
No implementation changes, private-data modification, sync, dependencies,
branches, commits, PRs or nested agents. Existing uncommitted changes retained.

## Phase 14: Category usage graph

- [x] T061 Add a lazily mounted per-category usage graph inside each Target comparison disclosure: exact trailing average of up to three immediately preceding consecutive evidence months (minimum two, current month excluded), strict above-average triangles, target outline, gap breaks without averages, visible precision failure, legend/summary/data-table text alternative and masked placeholder under Hide amounts. No API, dependency or persistence change. Synthetic helper/component/page tests, full client suite and build; README, UI contract, spec note and quickstart section 22 updated.
- [x] T062 Independently review T061 for averaging/gap/precision correctness, accessibility and complete amount masking. Depends on T061. Independent review PASS, no significant issues, supplied in the final-verification assignment; not a new review by the deployment verifier.
- [x] T063 After T062 passes, rebuild/deploy the frontend and verify the graph in a real browser with synthetic request mocks (desktop and mobile, tick labels, tooltip, gaps, refunds, masking, hide/restore, no extra requests). Depends on T062. Frontend-only deployment passed; 339 Chromium assertions (333 synthetic, 6 separate unmocked structural-only), nine containment tests and clean diff check. API container/image and named volume retained. See quickstart section 22.

**Historical usage-graph handoff boundary (2026-11-02)**: T061 complete, **61/63 checked**.
T062 review and T063 browser/deployment verification were pending. The slice used
synthetic client tests only; no real data, sync, dependency change, Docker,
commit, branch, PR or nested agent.

**Current usage-graph completion (2026-11-02)**: **63/63 checked; zero pending**.
T062's supplied independent review passed. T063 rebuilt/deployed only the owned
frontend and passed the nine-scenario synthetic browser acceptance, plus a separate
read-only live document/report HTTP 200 check. The live response now reports
`ready`, `grouping=report`, three groups; no live graph was expanded or inspected.
This does not rewrite the earlier insufficient-history observation or claim a
verifier-run resync. Both services remain healthy on `127.0.0.1:8080`; API
identity/image and `pocket-smith-reports_private-data` are unchanged. No application
fix, data write, sync, dependency change, branch, commit, PR or nested agent.
All pre-existing uncommitted changes retained.
