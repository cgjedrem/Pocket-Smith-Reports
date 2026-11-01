# Tasks: Runway & Burn Rate

**Input**: `docs/specs/003-runway-burn-rate/{spec,plan,research,data-model,quickstart}.md`
and `contracts/runway-api.md`; requirements checklist reviewed, 16/16 checked.
**Scope of execution**: backend/frontend implementation, technical runtime
acceptance and independent local QA complete. **34/34 original tasks checked**,
plus post-review real-data fix T035 (RD-001), which is outside review3.
**Review loop**: Final bounded independent review3 **PASS WITH CAVEATS**:
no remaining in-scope defect. Reviews 1 and 2 found issues that were fixed and
regression-tested before review3 closed the residual QA-001 collision.
Real HTTP acceptance and Linux native tests pass. Canonical Linux retains the
verified baseline lock readiness failure (RT-002), reproduced on unchanged HEAD
without runway or its isolation helper. Manual and remote checks below remain
explicitly unverified, not local implementation gates.
See [review-report.md](review-report.md).
**Tests**: mandatory; write and run failing tests before their implementation.
**Format**: `[ID] [P?] [USn?] owner: action with exact paths`. `[P]` means independent
files after stated prerequisites, not permission for concurrent edits to one service.

## Authorization and gate record

- Merged-plan gate checked by coordinator and **NOT passed**. Latest direct user
  continuation requested local implementation nonetheless. No `--skip-review`
  supplied or claimed; no gate configuration changes or publication to force it.
- Stay on the current app-managed branch; no branch mutation/commit/push/PR.
- Pre-existing dependency-pin/constitution discrepancy stays documented in
  `plan.md`; no new dependencies or unrelated pin changes.
- Setup-tasks executed with `SPECIFY_FEATURE_DIRECTORY=docs\specs\003-runway-burn-rate`;
  resolved `.specify/templates/tasks-template.md`. No optional commit/context
  update/bugfix hooks. No skills or subagents reinvoked.
- Checked task means completed work, not downstream review or user acceptance.

## Phase 1 — Setup

- [x] T001 BE: Read artifacts, checklist, constitution, source/storage/test conventions; record actual gate disposition in `docs/specs/003-runway-burn-rate/plan.md`.
- [x] T002 BE: Resolve setup-tasks template and create this dependency-ordered `docs/specs/003-runway-burn-rate/tasks.md`.
- [x] T003 BE: Run explicit-feature implementation prerequisites; record execution evidence in `docs/specs/003-runway-burn-rate/quickstart.md`.

## Phase 2 — Foundation (blocks backend stories)

- [x] T004 BE: Add temp storage/env and fail-closed filesystem/network guards before app import in `src/budget_api/tests/runway/conftest.py`; prove guards in `src/budget_api/tests/runway/test_isolation.py`.
- [x] T005 BE: Write initial failing calculation/API tests in `src/budget_api/tests/runway/{test_calculation,test_api}.py`.
- [x] T006 BE: Define strict request/persisted settings, structured issues, observations, owners and response DTOs in `src/budget_api/models/runway.py` matching `contracts/runway-api.md`.

## Phase 3 — US1: Recorded spending comparison (P1)

Independent test: October synthetic A/B/household example, 3.0/0.5/1.3 ratios;
checking/card gross purchases, no refund netting, all exclusions, dedupe, stable IDs.

- [x] T007 [US1] BE tests first: arithmetic, exclusions/descendants, stable identity and invalid duplicate/date/amount/posting cases in `src/budget_api/tests/runway/test_calculation.py`.
- [x] T008 [US1] BE: Implement exact completed-month window, strict source parsing, gross classification, stable-ID dedupe and Decimal owner/household math in `src/budget_api/services/runway.py`.
- [x] T009 [US1] BE: Expose independent result via `src/budget_api/routers/runway.py`; register in `src/budget_api/main.py` without Bills snapshot/schema changes.
- [x] T010 [P] [US1] FE tests first: panel arithmetic/context and unavailable states in `client/src/components/bills/__tests__/runway.test.tsx`.
- [x] T011 [US1] FE: Add `client/src/types/runway.ts`, `client/src/api/runway.ts`, `client/src/lib/runway.ts`, and `client/src/components/bills/RunwayPanel.tsx`; static gross-burn/account-owner/not-forecast copy, selected scope, observations and backend half-up/tiny display. Depends T010, T009.

## Phase 4 — US2: Explicit liquid selection (P1)

Independent test: absent GET writes nothing; valid Save/reload; invalid whole
selection preserves bytes; signed balance sum and owner with no selection.

- [x] T012 [US2] BE tests first: strict body, uniqueness, eligibility, drift, missing/zero/negative balances, empty reset and atomic failures in `src/budget_api/tests/runway/test_api.py`.
- [x] T013 [US2] BE: Implement dynamic `runway_config.json`, picker/read-time eligibility and atomic Save in `src/budget_api/services/runway.py`; GET/PUT settings in `src/budget_api/routers/runway.py`.
- [x] T014 [US2] FE tests first: explicit selection, missing saved option, settings-load/save failures and retained drafts in `client/src/components/bills/__tests__/runway.test.tsx`.
- [x] T015 [US2] FE: Add `client/src/components/bills/RunwaySettings.tsx`, labelled eligible/ineligible choices, explicit Save/reset and saved/draft separation. Depends T011, T014.

## Phase 5 — US3: Evidence and availability (P1)

Independent test: common 3/2/1/0 window, no older backfill, partial/unverified/
complete-zero, stale/unknown dates, currency conflict, numeric limits and retry.

- [x] T016 [US3] BE tests first: coverage, source corruption, currency, changing bytes/sync, precision/calendar/rounding and all null reasons in `src/budget_api/tests/runway/{test_calculation,test_api}.py`.
- [x] T017 [US3] BE: Implement provenance, freshness, scoped currencies, common included/excluded months, explicit null reasons and bounded stable-read checks in `src/budget_api/services/runway.py`.
- [x] T018 [US3] FE tests first: qualifiers, every excluded month/reason/date, missing versus observed zero in `client/src/components/bills/__tests__/runway.test.tsx`.
- [x] T019 [US3] FE: Render full safe reason mapping, source/balance dates, exact common window and qualifications in `client/src/lib/runway.ts` and `client/src/components/bills/RunwayPanel.tsx`. Depends T018, T017.

## Phase 6 — US4: Independent resilient Bills integration (P2)

Independent test: no current snapshot still yields runway; failure stays local;
failed settings load disables Save; stale response never replaces newer result.

- [x] T020 [US4] BE tests first: legacy/missing snapshots, GET no writes/no network, 200/400/409/500 no-store, query rejection and safe errors in `src/budget_api/tests/runway/test_api.py`.
- [x] T021 [US4] BE: Finish thin error translation, request rejection, both exact no-store paths in `src/budget_api/{routers/runway,main}.py`.
- [x] T022 [P] [US4] FE tests first: request generations, load/save failure, retry/draft preservation in `client/src/hooks/__tests__/useRunway.test.tsx`; fail closed on every unexpected fetch.
- [x] T023 [US4] FE: Implement independent lifecycle in `client/src/hooks/useRunway.ts`. Depends T022, T011.
- [x] T024 [US4] FE tests first: missing/legacy Bills and independent runway failure in `client/src/tests/BillsPage.test.tsx`; labelled controls in component tests and actual keyboard activation in synthetic Chromium (B7 in quickstart).
- [x] T025 [US4] FE: Mount independent panel outside Bills loading/error branches in `client/src/pages/BillsPage.tsx`; no display-month dependence. Depends T015, T019, T023, T024.

## Phase 7 — US5: Hide money, retain comparison (P2)

Independent test: zero/negative/positive money hidden in text/title/ARIA/tooltips;
ratio/context remains readable; toggle changes neither fetches nor selection.

- [x] T026 [US5] BE: Verify API issues/errors have no raw money/payees and picker has no balances in `src/budget_api/tests/runway/test_api.py`.
- [x] T027 [US5] FE tests first: mask every money surface and preserve saved/draft state in `client/src/components/bills/__tests__/runway.test.tsx`.
- [x] T028 [US5] FE: Connect existing privacy state through `client/src/lib/runway.ts` and the panel; settings have no monetary fields and retain drafts during parent privacy rerenders. No raw amount attributes or money in warning copy. Depends T027, T025.

## Phase 8 — Regression, review, handoff

- [x] T029 BE: Run focused runway suite plus largest safely isolated relevant/canonical Windows backend suite. Add opt-in collection-time harness only if needed in `src/budget_api/tests/isolated_run.py`; document exact results and pre-existing failures in `docs/specs/003-runway-burn-rate/quickstart.md`. No protected data or live network.
- [x] T030 BE: Exercise 10,000 synthetic transactions / 20 accounts and record backend-only timing in `src/budget_api/tests/runway/test_calculation.py` and `docs/specs/003-runway-burn-rate/quickstart.md`; not browser timing acceptance.
- [x] T031 BE: Caveman self-review; align `docs/specs/003-runway-burn-rate/{plan,data-model,quickstart}.md`, `contracts/runway-api.md`, directly related `README.md`, and durable `memory.md`; provide file/API handoff and no-migration summary.
- [x] T032 FE: Run focused hook/component/page suites, full safely mocked client tests and `pnpm build`; self-review and align README/feature docs/memory. Evidence and file manifest in `docs/specs/003-runway-burn-rate/quickstart.md`.
- [x] T033 runtime executor: Complete technical SC-004–008 browser checks with synthetic fixtures: keyboard/configuration, **real HTTP** backend-to-built-browser SC-005 at 10,000 transactions/20 mappings, masking, failure/race behavior, and five-fact source-copy visibility. HTTP H1–H7 pass, 13 API responses/four screenshots; IPC evidence remains separately labeled, not HTTP E2E. Environment/raw timings/screenshots in `docs/specs/003-runway-burn-rate/quickstart.md`. Human comprehension/ease-of-use observation explicitly deferred, not claimed passed.
- [x] T034 QA/coordinator: Final bounded independent review3 approved the typed fingerprint fix, its 36 regressions and evidence consistency with no remaining in-scope defect (99% confidence for QA-001 closure). Retain accepted QA-002/003/RT-001, HTTP acceptance/cleanup and verified RT-002 baseline attribution. Latest local Windows 215 focused / 869 API / 1207 canonical passes, 2 existing renderer exclusions. Historical Linux 1172 passed/1 baseline readiness failure remains non-green. Human/screen-reader/Ubuntu/remote checks unverified/nonblocking for local handoff. Coordinator verified fresh Git inventory, whitespace and unchanged branch; no publication approval.
- [x] T035 BE: Real-data null `is_transfer` fix (RD-001). Real PocketSmith transactions carry `"is_transfer": null`; strict `_flag` excluded all three real candidate months with `invalid_source`. Failing tests first in `src/budget_api/tests/runway/{synthetic,test_calculation,test_api}.py` (9 failed/40 passed before; 49 passed after), then add `_transfer_flag` in `src/budget_api/services/runway.py` at the four PocketSmith-sourced `is_transfer` read sites: null/absent is not a transfer, a non-null value must be a literal boolean, binding `excluded` stays strict (matches `v4_pipeline/accounting.py`). Align `docs/specs/003-runway-burn-rate/{spec,data-model,research,review-report}.md`. Latest local Windows 264 runway / 918 API / 1256 canonical passes, 2 existing renderer exclusions. Outside review3: bounded independent review done (pass-with-caveats); see the RD-001 section of `review-report.md` for the evidence ledger.

## Dependencies and execution strategy

T001–T003 → T004–T005 → T006 → backend tests then implementation in story order
(T007–T009 → T012–T013 → T016–T017 → T020–T021 → T026 → T029–T031).
All backend tests may be authored in the initial red phase. Backend service/model
edits remain sequential. P1 MVP requires US1+US2+US3, not just arithmetic.

FE can author isolated mocks/tests after the contract is fixed; integration awaits
backend. `[P]` tasks T010/T022 can run separately from BE implementation once their
contract prerequisite holds. No parallel edits to shared frontend files.
T032 follows T028; T033–T034 require both backend and frontend validation.
Unchecked QA tasks are not part of implementation completion and must not be
reported as passed. No publication or commits at intermediate checkpoints.

## Historical backend handoff — 2026-10-31

Backend scope complete: **19/34 tasks checked; 15 frontend/QA tasks remain**.
Final tests: **124 focused passes**, **1116 canonical Windows passes**, two
renderer tests deselected, one existing TestClient dependency warning. Final
synthetic service timing: **0.241s**. Exact commands and review in quickstart.

Files: `src/budget_api/models/runway.py`, `services/runway.py`,
`routers/runway.py`, `main.py`, `tests/isolated_run.py`, and
`tests/runway/{conftest,test_isolation,test_calculation,test_api}.py`;
`README.md`, `memory.md`, and this feature's plan/research/data-model/contract/
quickstart/tasks artifacts. Existing spec/requirements checklist retained.

Contract: GET `/api/bills/runway`, GET/PUT `/api/settings/runway`; strict unique
ID strings on PUT; no query parameters; 400/409/500 safe `{detail}` errors;
domain-unavailable result is 200 with null measures and structured issues.
Every exact-path response has no-store. GET does not write; explicit PUT writes
only the independent version-1 config. **No database or snapshot migration.**

Frontend must map stable issue codes to safe copy, mask every money field,
preserve draft/saved distinction, reject late request generations, and mount
outside legacy Bills loading/error branches. Retained results must identify the
saved selection. No Bills sync needed after Save. No full-feature or gate
completion claim; no `task_complete` tool is exposed in this backend session.

## Historical frontend handoff — 2026-10-31 (before integrated runtime)

**32/34 tasks checked. All 13 frontend tasks complete; T033–T034 remain open.**
The direct frontend continuation authorized local execution despite the recorded
merged-plan gate failure; that gate is still **NOT passed**, configuration unchanged.
No subagents, branch mutations, commits, push, PR, live API, or backend changes.

Evidence: initial missing-implementation red suites, then three failing Bills
integration tests before mounting the panel. Final focused suite **62 passed**;
full guarded client suite **414 passed across 44 files**; strict TypeScript and
production build passed. Synthetic Chromium **B1–B7 passed**, with eight screenshots,
zero unhandled API routes, zero page errors, zero API requests reaching the helper.
Browser helper stopped. Detailed identities, commands, observations, limitations,
and the 14-file frontend manifest are in [quickstart.md](quickstart.md).

T033 is **partially exercised, not approved**: automated keyboard configuration,
stubbed UI latency, masking, and responsive panel evidence exist; a human
five-fact comprehension exercise and actual backend-to-browser 10,000-transaction
timing do not. T034 still needs independent integrated QA, Ubuntu/native-renderer
checks, and authorized review/merge-gate disposition. The existing global mobile
navigation overflow is recorded, not silently fixed outside runway scope.

## Review 1 backend rework — 2026-10-31

- [x] R1-BE-001: Scan stable transaction identities across candidate sources before
  accepting the common window; invalidate every affected month. Preserve
  identical-copy dedupe and source-order independence. Calculation/API regressions.
- [x] R1-BE-002: Reject malformed embedded category titles before classification;
  preserve valid string repayment evidence. List/object and real-route regressions.
- [x] R1-BE-003: Remove collection-time global guards from feature conftest;
  scope feature guards and provide explicit early pytest-plugin isolation for
  ordinary pytest plus legacy aliases. Prove protected paths/network still fail
  closed. Permit only validated temp-PDF `pdftotext` extraction, with synthetic
  allow/deny/intercepted-launch regressions.
- [x] R1-BE-004: Extract reusable synthetic `World`; verify fresh-process app import
  after storage/ENV_FILE isolation and real routes with 10,000 transactions.
  Record exact frontend-specialist setup recipe in quickstart.
- [x] R1-BE-005: Final ordinary focused **158 passed**; canonical Windows backend
  **1150 passed, 2 renderer deselected**. Persist review 1, remediation, self-review,
  and durable memory. No frontend/dependency changes or publication.
- [x] R1-QA-001: Independent re-review of all three fixes and integrated behavior.
  Review2 accepted QA-002/003 and found residual QA-001; final independent
  review3 closed QA-001 and approved T034 for local handoff.

At that backend rework handoff the original checklist was **32/34**, with T033/T034
pending. Review-loop subitems are not extra completed feature tasks. The subsequent
runtime record below supersedes only the technical acceptance status; no gate
pass or human observation is inferred.

## Historical IPC runtime acceptance handoff — 2026-10-31

**33/34 original tasks checked. T033 technically complete; T034/review2 open.**
Direct user continuation authorized autonomous synthetic-only validation and a
separate bounded code-staged container; merged-plan gate remains **NOT passed**.
No subagents, production/test-code edits, branch mutations, commits, push, PR,
real API or Compose actions.

- Real TestClient responses consumed by actual unchanged production build in
  Chromium: **I1–I7 passed, four new screenshots, 13 real API responses**.
  Prior mock B1–B7/eight screenshots retained separately.
- **SC-005**: initial **507.759 ms**; refreshes **259.173 / 265.826 / 233.771 ms**,
  all within **2000 ms**, with **10,000 transactions / 20 mappings**.
  Actual A-only PUT/recompute **248.577 ms**, empty PUT/unavailable **275.682 ms**.
- **SC-007**: hide/show **68.310 / 55.978 ms**, zero refetches or lost draft,
  money masked including attributes, ratios/context preserved.
- Real selection persistence, no Bills refetch on Save, missing Bills independence,
  explicit unavailable response and source transparency verified. Source hashes
  unchanged; all own helpers stopped and synthetic temp root removed.
- Linux **Debian 12 / Python 3.13.18**, canonical four trees with no exclusions:
  **1147 passed, 5 failed in 91.49s**, one warning. Not a pass.
  Four native failures reproduce a feature guard rejection of `/sbin/ldconfig -p`;
  same four unchanged native tests pass in the synthetic-only container without
  that Python plugin. Fifth lock timeout passes alone; cause unverified.
- Windows guarded native UTF-8/PDF/pdftotext test **1 passed**. Actual Linux
  pdftotext through unchanged temp-file guard also passes on a generated text PDF;
  this does not fix or replace failed WeasyPrint discovery/canonical evidence.
- No repository code changes: prior frontend **414 tests/build** and Windows
  **158 focused / 1150 canonical + 2 deselected / 4 legacy compatibility** remain
  historical required-gate evidence, not rerun totals.

Follow-up records (not additional original task completions):

- **MANUAL-003, deferred/unverified (not a local implementation gate):** Actual human SC-008 five-fact comprehension and SC-004
  observed ease/configuration time. User absent; no participant or answers.
  Automated content/keyboard evidence is not a human study. Does not reopen
  completed T033 technical objectives.
- [x] RT-001, BE/coordinator: Exact trusted Linux `ldconfig -p` policy implemented
  in `src/budget_api/tests/isolated_run.py`; 21 allow/deny regressions added.
  Windows 45 guard/179 focused/1171 canonical pass; Linux target 50 pass including
  all four native tests. Those also pass in canonical; no blanket allowance/skips.
- [x] RT-002, BE: Narrowly diagnose publisher-lock five-second readiness timeout.
  Same staged Linux runtime, baseline `979a01c5daca080cd141bfdb2c82970488998018`
  without runway/helper: canonical prefix **113 passed / 1 failed** at unchanged
  `ready.wait(5)`. Collection-expanded duplicate import paths delay spawn's
  evidence-runner pytest import before readiness; diagnostic deduplication
  passes, and **179 runway tests then lock = 180 passed** without workaround.
  Baseline environment limitation, not feature leakage; no production/test fix
  or green canonical claim. Evidence in quickstart/review-report.
  **T034 independent QA2 remains unchecked.**

Exact commands, raw timing data, image/input boundaries, artifacts, cleanup and
self-review: [quickstart.md](quickstart.md#integrated-runtime-acceptance-and-cross-platform-attempt--2026-10-31).
This is implementation/runtime evidence, **not independent review2 approval**.

## Bounded backend and real HTTP handoff — 2026-10-31

**33/34 original tasks checked. Local implementation/verification complete;
T034 remains unchecked for independent reviewer.**

- RT-001 remediated and actual Linux native rendering/extraction verified under
  the guard. RT-002 was unresolved at this runtime handoff; subsequent bounded
  diagnosis above verifies baseline attribution. No unrelated production edit.
- Actual uvicorn/FastAPI **8103**, fixed HTTP proxy + unchanged built frontend
  **5203**, synthetic storage + fake env before app import, no credentials/sync.
  **7 Chromium scenarios / 13 browser API responses / 4 screenshots pass**.
  Not Playwright API fulfillment or a TestClient bridge.
- SC-005 **1047.450ms initial**, **305.396/267.264/298.670ms refresh** under 2000ms;
  save/recompute **934.002ms**, empty/unavailable **919.004ms**; privacy
  **59.382/49.141ms**, zero requests, draft retained.
- Both owned HTTP helpers exited 0, PIDs absent, temp root deleted,
  **5203/8103 closed**. Own Linux containers/image cleaned. User Docker/Compose
  and existing ports untouched. No agents/branch changes/commits/push/PR.
- Human usability/comprehension, screen reader, Ubuntu-specific execution and
  remote plan/review remain **unverified**, nonblocking for local handoff per user.
  No new sign-off gate; native Debian rendering is verified.
- Latest commands/results/artifact manifest:
  [quickstart.md](quickstart.md#bounded-backend-rework-and-real-http-acceptance--2026-10-31).
  Prior IPC evidence is historical and does **not** count as real HTTP E2E.

## Review2 residual QA-001 handoff — 2026-10-31

**33/34 original tasks checked. Local fix complete; T034/review3 unchecked.**
One supplied **98%-confidence** residual: Decimal amounts fingerprinted as
ordinary arrays, letting crafted duplicate records bypass conflict detection.

- [x] R2-BE-001: Replace only `_fingerprint` with typed recursive tuples, preserving
  sorted object keys, array order, decoded numeric scale/sign and genuine copies.
  No parser/validation/category/pre-scan/harness/frontend/dependency edits.
- [x] R2-BE-002: Add **36 tests** (32 calculator/identity, 4 API). Before fix,
  **19 failed / 17 passed**: numeric-first accepted July versus array-first
  rejection; cross-month crafted array retaining July date left July accepted.
  Both record placements/source scan orders now invalidate affected months.
  Nested metadata/type/sentinel lookalikes, true duplicates, decoded equivalence
  and invalid nonfinite amounts covered. Same new tests now **36 passed**.
- [x] R2-BE-003: Safe Windows **215 runway / 869 full API / 1207 canonical passed**;
  same **2 renderer exclusions**, existing TestClient warning only. Pre/post
  10,000-transaction/20-mapping medians **133.034→154.280ms integer** and
  **142.855→161.236ms decimal**; post-fix max **295.820ms**, response hashes equal.
- [x] R2-BE-004: Persist supplied review2 residual, exact red/green commands,
  regression inventory, raw timings, narrow self-review and durable memory.
  No migrations, agents/nesting, commits/push/PR, private/env/main-checkout access,
  live user services, Docker/browser startup or unrelated baseline repair.
- [x] R2-QA-001: Final independent review3 passed the residual fix/evidence with
  no targeted defect and approved T034 closure. Retain accepted QA-002/003/RT-001,
  HTTP seven-scenario evidence/5203+8103 cleanup and RT-002 verified baseline
  attribution. This is independent review, not implementer self-approval.

Prior **179 focused / 1171 canonical** are historical, superseded locally by
**215 / 1207**, exactly 36 additional cases. Do not update the historical Linux
**1172 passed / 1 failed** without rerunning; no broad Linux rerun requested.
Prior browser **1047.450ms initial / 267.264–305.396ms refresh / 934.002ms save**
remains historical accepted HTTP evidence, not retested for this internal fix.
Human/screen-reader/Ubuntu-specific/remote observation remains
**unverified/nonblocking** for local handoff. Publication gate remains NOT passed.
See [quickstart.md](quickstart.md#review2-residual-qa-001--2026-10-31) and
[review-report.md](review-report.md#review2-residual-qa-001--local-remediation-review3-pending).

## Final local handoff — 2026-10-31

Final independent review3 is **PASS WITH CAVEATS**, with no remaining in-scope
finding; **34/34 original tasks complete**. Earlier handoff counts and pending
statements above describe their historical stages, not current status.
At the time of this handoff, source changes, all feature tests and documentation
were uncommitted on the local feature branch. The coordinator's fresh Git
inventory matched the backend/frontend/specification manifests; `git diff --check`
passed.

The latest fingerprint fix has full Windows regression and service-performance
evidence. Accepted frontend/build/real-HTTP and Linux evidence was not rerun
after that internal-only fix. The Linux baseline failure, deferred manual
checks and unpassed remote merged-plan gate are retained honestly. No
publication, user acceptance, or entirely green Linux run is claimed.
