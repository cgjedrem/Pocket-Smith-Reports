# Quickstart: Synthetic Validation of Lifestyle Creep

**Current status (2026-11-02)**: The shared Home + Common and two personal report-group amendment is complete: **60/60 tasks checked; zero pending**. T059 supplied independent review **PASS, no significant issues**; T060 rebuilt/deployed both images and passed **68/68 browser assertions** (57 synthetic, 11 unmocked structural/metadata-only), the identical-category-ID component regression and nine containment tests. Both services remain healthy with the same named private volume. Live legacy history correctly needs explicit user-run schema-7 resync, not an automatic migration or a fake-ready result. Exact commands, evidence and final manifest are in section 21.

**Historical visibility checkpoint (2026-11-02)**: The corrected one-target/reference-period contract and visit-local category visibility were complete: **56/56 tasks checked; zero pending** at that boundary. T055 independent code-review **PASS** was supplied in the final-verification handoff; T056 frontend-only container deployment and **67/67 browser assertions** passed (58 synthetic, 9 unmocked structural-only); see section 20. Section 19 preserves the earlier corrected API/client/T052 review/T053 runtime evidence. The 48/48 count and 164-assertion smoke for the superseded multi-month interpretation remain historical only. The failed merged-plan gate remains failed; no commit or remote publication is claimed.

**Prior delivery status**: Backend and frontend implemented on 2026-10-31, then rebased onto main (which now contains the runway feature) and validated on real data. Sections 8–10 preserve backend execution/handoff; sections 11–12 record passing client tests/build and synthetic browser evidence. Initial integrated QA was **FAIL** with two Important source-integrity findings; [Cycle1 rework](#13-integrated-qa-rework-cycle1--2026-10-31) reproduced and fixed both, and an independent re-review closed them. [Section 16](#16-post-rebase-real-data-validation) records post-rebase validation and known limitations. T001 to T041 were completed before the range amendment: T041 moved the detector to its own tab and T040 verified the prior container, both recorded in [section 17](#17-separate-lifestyle-creep-tab---2026-11-02). Those runtime checks do not certify the new controls.

**Reading note**: Sections 8–18 preserve dated historical execution records and counts. Fixed-five/two-comparison, viewing-month-control, and selectable multi-month examples are prior interpretations, superseded by section 19. Their tests, browser assertions, and task counts do not certify the current contract.

**Contracts**: [API](contracts/lifestyle-creep-api.md), [history v6](contracts/bills-history-v6.md), [Bills card](contracts/bills-card.md), [data model](data-model.md).

## 1. Preconditions and Isolation

Stay in the assigned worktree on its existing app-managed branch. Feature identity is not a reason to create/switch branches. The previously failed before-tasks merged-plan gate remains failed. Local continuation is recorded in plan/tasks; these runtime checks neither rerun nor pass that gate.

For later implementation verification:

- Use synthetic `Partner A`/`Partner B`, synthetic source IDs, and deterministic amounts. No reads, searches, prints, or writes of real financial records or credentials. Do not use the main checkout.
- Set `BILLS_CALC_LOG=0` **before pytest collection or any app/builder import**. Builder logging happens before fixtures; setting it inside a test is too late.
- Use `tmp_private_dir`, synthetic mappings/catalogs and source lists, and temporary environment-path fixtures. Apply storage isolation before builder fallback, sync execution, or FastAPI lifespan. No real credentials are required; source calls are fakes.
- API-suite storage/environment isolation is now autouse, including legacy builder fallback and lifespan. The environment-file override is cleared before each test; named temporary fixtures remain available. The Bills clock fixture imports the builder only after isolation. CLI suites use explicit public synthetic fixtures or temporary roots.
- API tests must tripwire external client construction, config/raw-file reads, globbing, and writes; only the exact required synthetic snapshot paths are allowed (4–27 for explicit ranges, five for legacy/default). Sync tests are separate and use a fake source client and temporary publication targets.
- Do not run the full command until all exercised filesystem/import/lifespan paths are isolated. If this cannot be established, report that suite pending rather than relaxing the private-data boundary.
- Never contact Docker or services 8080/5200/8100. No live sync. API behavior is tested in-process.

## 2. Dependency Policy

Attempt the documented test/build command first with installed tools. Do not inspect private configuration to bootstrap it. Do not restore dependencies speculatively.

Use `uv run --no-sync --locked` below to avoid an implicit dependency restoration during the first test attempt. If it actually fails because Python dependencies are missing, restore the existing lock with `uv sync --locked`, then retry the same command. Do not edit `pyproject.toml` or `uv.lock`.

If a client command actually fails for missing dependencies, run `pnpm install --frozen-lockfile` in `client`, then retry it. Use the existing pinned pnpm 10.30.3 through Corepack (`corepack enable` only if activation is needed), not npm/yarn or a new browser dependency. No lockfile regeneration. A test assertion failure is not a reason to reinstall.

## 3. Targeted Python Tests First

Run from the worktree root, after the planned files and isolation fixtures exist:

```powershell
$env:BILLS_CALC_LOG = '0'
$env:PYTHONPATH = 'src'
uv run --no-sync --locked python -m pytest src/budget_api/tests/bills/test_lifestyle_creep.py src/budget_api/tests/bills/test_cc_spend_history.py src/budget_api/tests/bills/test_lifestyle_creep_api.py src/budget_api/tests/test_sync_lifestyle_history.py -q
```

Each new shell/tool invocation needs those environment assignments again. No shell state is assumed to persist.

### Pure calculation cases

| Synthetic category series | Expected result at 20% |
| --- | --- |
| `[100,100,100,130,140]` | Sustained; baselines 100 and 110; rolling 30% and about 27.27%; ordinary latest about 7.69%. |
| `[100,100,100,130,131]` | No alert; second baseline includes 130. |
| `[100,100,100,120,150]` | No alert; first equality is not strictly greater. |
| `[100,100,100,130,132]` | No alert; second equality is not strictly greater. |
| `[100,100,100,130,132.001]` | Sustained; display rounding must not change result. |
| `[100,100,100,150,150]` | Sustained despite 0% ordinary latest growth. |
| `[100,100,100,160,100]` | Isolated spike; no alert. |
| `[100,100,100,90,80]` | Negative changes preserved; no alert. |
| `[0,100,100,130,150]` | Two initial positive observations; eligible and sustained. |
| `[0,0,100,200,300]` | Low-frequency suppression. |
| `[0,0,0,100,200]` | Zero-baseline suppression wins; no infinite percentage. |
| `[100,100,100,0,150]` | No alert; ordinary latest percentage null. |
| Five complete empty category maps | Ready; empty category results, not insufficient; uncategorized samples remain present. |

Also cover decimal accumulation (`0.1`/`0.2` style inputs), non-terminating averages, coefficients beyond default Decimal context precision, exact thresholds 1/20.5/30/100, and string serialization round trips. Use exact cross-product assertions, not float approximations of verdicts.

### Producer and compatibility cases

- Shared-filter parity: posted outgoing on eligible owned CC accounts only; pending/refunds/credits/transfers/payments/exclusions omitted.
- Stable category/partner IDs; duplicate titles remain separate; renamed labels remain the same series and scope when effective filters are unchanged.
- Split uncategorized qualifying amounts from category IDs; no returned/persisted sentinel.
- Full successful closed-month empty fetch is complete zero; absent source input, invalid types/IDs/amounts/dates/mappings, unknown ownership, and missing context are not.
- A successful source-month fetch begun before close remains partial after rollover; explicit closed-month re-sync changes it to complete.
- Transaction fetch failure prevents all new Bills snapshot publication for that attempt, including months fetched earlier. Previous partial/unavailable history remains unchanged.
- Mapping insertion order and display labels do not change fingerprints; account ownership/inclusion/exclusions and relevant category filters do.
- Old title totals and existing Bills fields retain values/null semantics after enrichment. Legacy schema-5 dashboard retrieval still works; it does not become detector-ready.

### Route / saved-input cases

- Five exact synthetic snapshot read attempts once each, no unrelated reads/writes; valid defaults and historical/year-boundary windows. For January 2027 freeze the API process clock (`date.today()` in the service) to January 2027 or later.
- Invalid/missing/impossible/future/underflow month, duplicate parameters, empty/Boolean/nonnumeric/non-finite/out-of-range thresholds yield 400 and zero reads.
- Missing whole month, interior gap, only four months, absent legacy history, missing partner, identity-less row, partial month, no eligible CC accounts and scope change yield correct diagnostics.
- Partner A ready and Partner B incomplete yields partial; all complete yields ready; none ready/no stable identity yields insufficient.
- Missing file differs from literal JSON `null`. Bad encoding/JSON, duplicate object/partner/category identity, mismatched month, invalid block state, negative/non-finite/wrong-type amount, unknown schema, or I/O failure returns generic 500, not partial success.
- All 200/400/500 responses have `Cache-Control: no-store`; errors have one safe `detail` string.
- Replacing synthetic snapshots in the fixture then retrying changes the result without cache or sync. Unchanged inputs yield identical order and values.

## 4. Full Windows Python Non-Renderer Suite

Only after targeted tests pass and full-path isolation is established:

```powershell
$env:BILLS_CALC_LOG = '0'
$env:PYTHONPATH = 'src'
uv run --no-sync --locked python -m pytest src/mega/tests src/v4_pipeline/tests src/mom/tests src/budget_api/tests -q -m "not pdf_renderer"
```

This follows the canonical four-suite coverage with the Windows renderer exclusion. Do not install native renderers for this feature or claim Ubuntu/renderer results from this Windows run. Existing dual-OS CI obligations still apply before any later merge.

## 5. Client Tests and Build

From the worktree root, first target the feature tests, the Lifestyle Creep page and route, the Bills page (no detector) and Bills privacy:

```powershell
Push-Location client
try {
    pnpm test src/api/__tests__/lifestyle-creep.test.ts src/hooks/__tests__/useLifestyleCreep.test.ts src/components/bills/__tests__/LifestyleCreepCard.test.tsx src/pages/__tests__/LifestyleCreepPage.test.tsx src/tests/BillsPage.test.tsx src/tests/LifestyleCreepRoute.test.tsx src/components/bills/__tests__/privacy-masking.test.tsx
    if ($LASTEXITCODE -ne 0) { throw 'Targeted client tests failed' }
} finally {
    Pop-Location
}
```

Then run the full client suite and build:

```powershell
Push-Location client
try {
    pnpm test
    if ($LASTEXITCODE -ne 0) { throw 'Client tests failed' }
    pnpm build
    if ($LASTEXITCODE -ne 0) { throw 'Client build failed' }
} finally {
    Pop-Location
}
```

Required observations: all loading/retry/availability/outcome states; exact API types including decimal strings; invalid draft versus applied threshold; month-change persistence/fresh-visit reset; request race protection; category/uncategorized details; complete empty evidence; accessible controls; no detector refetch on unrelated controls; every money surface masked with percentages visible; Bills renders no detector and never calls the detector API; the `/lifestyle-creep` deep link and nav tab work. No `pnpm lint` is specified because the current package has no lint script.

## 6. Browser Smoke — Synthetic Request Mocks Only

Use already available browser automation or a test harness with request interception. Do not install a new browser dependency for this feature. If none is available, record browser smoke pending.

If a frontend server is needed after implementation, run only this worktree on the dedicated port:

```powershell
Push-Location client
try {
    pnpm exec vite --host 127.0.0.1 --port 5205 --strictPort
} finally {
    Pop-Location
}
```

This bounded verification helper must be stopped after the smoke. Do not leave it running for this docs phase. Do not start an API; reserve 8105 for a separately necessary isolated API session, never use existing services.

**Critical proxy safeguard**: Current Vite `/api` proxy targets 8100. Changing Vite's port does not change the proxy. Before any browser navigation to `http://127.0.0.1:5205/lifestyle-creep`, install a catch-all API interception handler that fulfills known `/api/**` requests from deterministic synthetic fixtures and aborts every unknown API request. Abort any external/other-origin network traffic. Do not navigate until interception is active. A request falling through to Vite's proxy is a failed safety check, not a permissible smoke.

Mock all app-shell requests, not just lifestyle creep, plus the Bills and Runway requests that step 7 needs. No real backend URL is needed. Use delayed/failed synthetic responses to exercise:

1. Loading then alert for the API contract's positive example; inspect both baseline windows and ordinary month-over-month distinction.
2. Ready/no-alert, zero/sparse suppression, complete empty categories, and uncategorized-only coverage.
3. Insufficient then partial history; ready partner stays inspectable, affected months and `/sync` link are visible. Verify link destination without triggering a sync request.
4. Synthetic 500 then Retry to synthetic success for the same five-month selection.
5. Apply 30%, then 20.5%, then invalid input; effective threshold is truthful. Delay an older request until after a new selection to prove stale-response rejection.
6. Toggle global amount visibility; check visible money, tooltips, aria attributes and hidden text contain only masked money while percentages remain visible. Request count must not increase.
7. Open Bills (`/bills`): it shows no detector and makes no lifestyle request.
8. Keyboard operation of threshold, Apply, Retry, detail disclosure and sync link; inspect announced busy/error/coverage states.

The smoke is scoped to the Lifestyle Creep tab plus the Bills check in step 7. The Bills and Runway fixtures exist only so Bills can render in step 7; do not integrate the detector with Runway or debts.

## 7. Record Results Without Overclaiming

Report exact commands, passes/failures, isolated fixture coverage, request counts, browser evidence, and any pending checks. No implementation or runtime test pass is implied by the design's synthetic examples.

The original planning delivery executed no application tests. The following backend evidence supersedes that runtime status only; frontend/publication/gate status remains separate.

## 8. Backend Execution Evidence — 2026-10-31

All commands ran in this worktree on Windows with Python 3.13.7. `BILLS_CALC_LOG=0`
was set before application imports, and all financial inputs were synthetic.
API fixtures isolate storage and environment paths, reject real private-path opens
and socket connections, and preserve the existing frozen Bills clock. Endpoint
tests additionally reject scans, config/raw reads, writes, sync and source-client
construction; the successful bounded-read test asserts the five exact paths once
each. No real data, credentials, other checkout, running service, Docker, or
frontend server was accessed.

### Exact final commands and results

```powershell
$env:BILLS_CALC_LOG = '0'
$env:PYTHONPATH = 'src'
uv run --no-sync --locked python -m pytest src/budget_api/tests/bills/test_lifestyle_creep.py src/budget_api/tests/bills/test_cc_spend_history.py src/budget_api/tests/bills/test_lifestyle_creep_api.py src/budget_api/tests/test_sync_lifestyle_history.py -q
if ($LASTEXITCODE -eq 0) {
    uv run --no-sync --locked python -m pytest src/mega/tests src/v4_pipeline/tests src/mom/tests src/budget_api/tests -q -m "not pdf_renderer"
}
```

| Check | Observed result |
| --- | --- |
| Targeted four feature files | **192 passed**, 1 warning, 2.82 seconds |
| Full four-suite Windows non-renderer run | **1184 passed**, **2 deselected**, 1 warning, 21.76 seconds |
| Requirements checklist, read-only | 27 checked, 0 unchecked; markers untouched |
| Dependency changes | None to manifests/locks; existing lock restored after actual missing-module failure |

After README/handoff edits, ran `git --no-pager diff --check` successfully and,
with the same two environment assignments, ran:

```powershell
uv run --no-sync --locked python -m pytest src/mom/tests/test_current_tree_containment.py src/mom/tests/test_lg002_identifier_containment.py -q
```

Result: **9 passed** in 0.73 seconds. Confirmed the original branch, 15 completed
backend task markers, no client changes, and ignored `memory.md`.

Both runs emitted the existing Starlette `httpx` TestClient deprecation warning.
No native renderer or Ubuntu result is claimed. Frontend checks and browser smoke
were not run. Tracked-tree containment tests inspect tracked files; these runs do
not certify a future staged/published tree containing the currently untracked
specification artifacts.

### Failure and correction record

- Initial `uv run --no-sync pytest ...` reached expected missing-feature assertions.
  The documented `uv run --no-sync --locked python -m pytest ...` then failed with
  `No module named pytest` in the new local environment. Only then ran
  `uv sync --locked`, preserving `pyproject.toml` and `uv.lock`.
- Tests established red assertions before model, aggregation, detector, sync and
  route implementation. They were rerun after each slice.
- Source-trust review added an unmapped-catalog-account regression; the producer
  now rejects that ambiguity rather than certifying an empty observation.
- Initial full run: 1174 passed, 2 failed, 2 deselected. Both failures asserted
  new builds still emitted schema 5. Updated those two coupled tests to assert
  schema 6 and explicit unavailable history without acquisition context.
- Review added a failing prior-month fallback-acquisition test. A failed fallback
  fetch now blocks all new Bills publication instead of being swallowed as a
  warning. Existing cached data, title totals and successful fallback behavior
  remain unchanged.
- Review added response-window/outcome consistency tests and JSON numeric-overflow
  corruption (`1e9999`) coverage. Invalid windows/suppressed alerts are rejected;
  numeric overflow now produces the same generic 500 as other corrupt input.
- One exploratory command interleaved `bills/*.py`, the root sync test, then
  `bills/test_builder.py` and the reports test. It produced four clock-dependent
  failures. `--setup-show` proved the Bills autouse clock was absent for the later
  explicit Bills path; a standalone run applied it and passed. Use the grouped
  commands above (both final runs passed), not interleaved directory selections.

### Local caveman self-review

- 🔴 Fixed: unknown catalog ownership could certify empty history. Reject before filters.
- 🔴 Fixed: prior acquisition failure could publish Bills. Fail before publication.
- 🔴 Fixed: JSON numeric overflow could hide in ignored fields. Reject nonfinite parsed numbers.
- 🟡 Constraint: schema-5/partial history requires explicit closed-month re-sync; GET never upgrades it.
- 🟡 Validation limits: native renderer, Ubuntu, frontend and staged-tree checks pending.
- ❓ No unresolved backend implementation questions or failing tests in the final commands.

This is local backend self-review, not T033's later integrated frontend/backend
review and not a passed merged-plan gate. Optional pre/post commit and optional
bugfix hooks were skipped. No branches, commits, pushes, PRs, merges, publication,
or extension-config changes occurred.

## 9. Frontend Integration Handoff

Use `GET /api/bills/lifestyle-creep?month=2026-10&threshold_percent=20`.
The [API contract](contracts/lifestyle-creep-api.md#response-types) contains the
complete wire shape and [complete synthetic success example](contracts/lifestyle-creep-api.md#synthetic-success-example).
Python response models are in `src/budget_api/models/lifestyle_creep.py`.

- Keep **all new money, percentage and threshold fields as strings** through
  transport/state. `null` percentages mean an undefined denominator, not 0%.
  Counts remain integers. Never recompute `is_sustained` from rounded displays.
- Omitted threshold defaults to `"20"`; explicit empty/invalid input is 400.
  Encode a leading `+`. Equivalent exponent/leading-zero forms return canonical
  values. Month must be real ASCII `YYYY-MM`, no later than the current month on the API process clock,
  with five representable predecessors.
- Root status is `ready`, `partial`, or `insufficient_history`. Under partial
  coverage retain each ready partner's details. Incomplete partners have empty
  category/uncategorized arrays; root `issues` carries affected month/identity/reason.
- Each ready category has exactly five `samples` and two `comparisons`, each with
  three baseline months. Latest headline amounts come from `comparisons[1]`;
  ordinary latest growth is `latest_month_over_month_percent`. Every observed ID,
  including suppressed/no-alert categories, is returned. Uncategorized has five
  separate samples and no verdict.
- Stable partner/category IDs are join keys. Labels and display slots are not.
  Results are lexically ID-ordered; use labels only for presentation.
- Expected missing/old/partial history is HTTP 200 with diagnostics. Validation is
  400 `{ "detail": "..." }`; corrupt/read/evaluation errors are 500
  `{ "detail": "internal error reading lifestyle creep history" }`.
  All three carry `Cache-Control: no-store`.
- Retry repeats only this GET, reopening the same five paths without a result
  cache. A user-triggered explicit sync is the only upgrade path; no auto-sync or
  title-to-ID recovery. For October 2026 the guidance names May 2026 as the first window month and asks for one sync run from there through the usual sync end month (at least the current month), under a consistent account/category configuration.
- Follow the existing card contract: detector-only visit-local historical month,
  applied-threshold state, stale-response guard, global money masking and labelled
  controls. Mount outside dashboard early returns. Do not couple requests to
  Grid/Graph/Table, display-window or privacy controls.

At the backend-only handoff, completed tasks were **T001–T005, T007–T009,
T012–T013, T015–T017, T019, T030**, and no client files had changed.
Subsequent frontend completion is recorded below; **T033–T034** were the last two tasks of that round and were completed afterwards (sections 13 to 16).

### Migration

Additive JSON schema 6, not SQL. `PartnerBills.cc_spend_history` defaults to null
for legacy model callers. Successful explicit sync writes history blocks with
stable IDs and completion provenance. No migration script, eager rewrite, title
recovery or historical re-sync was run at this handoff (a later real-data validation is recorded in section 16). The existing atomic JSON writer is reused.

## 10. Backend File Manifest

Paths below are relative to the worktree; documentation inputs were already present.

| Action | Files |
| --- | --- |
| Created models/service | `src/budget_api/models/lifestyle_creep.py`; `src/budget_api/services/lifestyle_creep.py` |
| Modified production code | `src/budget_api/models/bills.py`; `src/budget_api/services/bills_derivations.py`; `src/budget_api/services/bills_builder.py`; `src/budget_api/services/sync_runner.py`; `src/budget_api/routers/bills.py`; `src/budget_api/main.py` |
| Created synthetic tests | `src/budget_api/tests/bills/test_cc_spend_history.py`; `src/budget_api/tests/bills/test_lifestyle_creep.py`; `src/budget_api/tests/bills/test_lifestyle_creep_api.py`; `src/budget_api/tests/test_sync_lifestyle_history.py` |
| Modified isolation/regression tests | `src/budget_api/tests/conftest.py`; `src/budget_api/tests/bills/conftest.py`; `src/budget_api/tests/bills/test_builder.py`; `src/budget_api/tests/reports/test_regen_smoke.py` |
| Modified user/handoff docs | `README.md`; this `quickstart.md`; `tasks.md`; `data-model.md`; `contracts/bills-history-v6.md`; `contracts/lifestyle-creep-api.md` |
| Updated local memory | `memory.md` (gitignored; durable facts only) |

## 11. Frontend Execution Evidence — 2026-10-31

Implemented T006, T010–T011, T014, T018, T020–T029 and verified T031.
No backend source files were edited during this slice. No backend imports,
live sync, private financial inputs, other checkout, user service or Docker
operations were used. Existing backend changes were retained.

### Behavior and conventions

- `BillsPage` owns detector-only month and draft/applied threshold state. The
  single card mounts outside dashboard loading/error/not-found/empty branches,
  between summary and visualization when those are available (after the later rebase the Runway panel also sits above it; see section 16). Dashboard current
  month, query-backed display window and visualization behavior stay unchanged.
- New wire quantities remain strings. Feature-local threshold validation uses
  decimal digit position and an integer exponent, not floating-point bounds.
  Equivalent values deduplicate; invalid drafts never fetch, clamp or default.
  Historical changes retain the applied threshold; a fresh page mount resets 20%.
- The hook depends only on detector month, canonical applied threshold and
  explicit retry generation. Selection-tagged state hides previous data before
  effects run; cleanup rejects late success/failure and response identity
  mismatches. Existing `apiGet` has no AbortSignal option, so this uses its
  established cleanup-guard pattern rather than modifying the shared client.
- All server category outcomes remain inspectable, with five observations,
  two rolling comparisons, separate ordinary month-over-month growth, stable
  category IDs and separate uncategorized observations. Incomplete partners
  have no money or category verdicts; ready partners remain visible under partial
  coverage. Every issue code and source reason has local explanatory copy.
- The approved feature-local numeric convention is explicit: exact decimal-text
  input validation plus presentation-only conversion to existing masked
  `formatKr`/`formatSignedKr`. Overflow uses masked grouped decimal text, never
  infinity or invented zero. All collapsed and assistive monetary surfaces mask;
  percentages remain visible. No new app dependency or shared numeric framework.
- `LifestyleCreepControls.tsx` is an additional thin extraction from the planned
  card, using existing button/input styles and native labelled forms. It is
  covered through card/page tests; native disclosure keyboard behavior is also
  checked in Chromium. No novel shared UI pattern or global styling change.

### Exact final client commands and results

From this worktree:

```powershell
Set-Location client
pnpm test src/api/__tests__/lifestyle-creep.test.ts src/lib/__tests__/lifestyle-creep.test.ts src/hooks/__tests__/useLifestyleCreep.test.ts src/components/bills/__tests__/LifestyleCreepCard.test.tsx src/pages/__tests__/BillsPage.lifestyle-creep.test.tsx src/components/bills/__tests__/privacy-masking.test.tsx
if ($LASTEXITCODE -eq 0) {
    pnpm test
    if ($LASTEXITCODE -eq 0) { pnpm build }
}
```

Note (2026-11-02): `BillsPage.lifestyle-creep.test.tsx` was later deleted and replaced in [section 17](#17-separate-lifestyle-creep-tab---2026-11-02); the command above is kept as it was run.

| Check | Final observed result |
| --- | --- |
| Targeted feature + existing Bills privacy | **6 files, 113 passed**, 6.21 seconds |
| Full `pnpm test` | **47 files, 468 passed**, 25.38 seconds |
| `pnpm build` | **Passed**, TypeScript + Vite; 2604 modules, 12.41-second Vite build |
| Dependencies/manifests/lockfiles | No edits or additions |
| Branch | Existing app-managed branch, unchanged |
| `git --no-pager diff --check` | Passed after source and documentation edits |

Coverage includes URL encoding/default/ApiError preservation; exact threshold
bounds/exponents; calendar underflow/year rollover; loading/error/Retry; stale
selection and same-selection retry completions; unmount cleanup; response
identity; all availability/reason/outcome states; duplicate category titles;
empty/uncategorized evidence; zero/signed/overflow money; full DOM/attribute
privacy; no refetch on privacy, all three visualizations or either display-window
control; and card visibility despite missing/failed dashboard data.

### Failure/correction record

- The first targeted `pnpm test` failed because Vitest/node_modules were missing.
  Only then ran `pnpm install --frozen-lockfile` with pinned pnpm 10.30.3; all
  320 packages were reused from cache. No lock regeneration, unrelated dependency,
  npm install, or build-script approval was added.
- Meaningful red tests preceded wrapper/ready rendering, availability diagnostics,
  exact input handling, lifecycle and page wiring. They were rerun to green.
- Integration tests initially queried Bills' existing Radix view choices as
  buttons. Actual semantics are radio controls; corrected the tests, not the UI.
  The synthetic display-source mock also needed `getAllEvents()` for Table mode.
- Self-review added same-selection Retry race coverage and wrap-safe long decimal
  text. The latter is presentation-only; all modified components have behavior
  tests. Final tests/build above include these changes.
- Build succeeds with two warnings: the existing shared `types/api.ts`
  static/dynamic import mix and a main JS chunk exceeding 500 kB (about 1.10 MB,
  gzip 321 kB). No code-splitting/configuration work was introduced.

### Frontend caveman self-review

- 🔴 No unresolved frontend correctness defects found in this local self-review.
- 🟡 `client/src/layouts/AppLayout.tsx:16`: existing nonwrapping navigation overflows
  390px viewport. Detector removal leaves document width 562px; nav removal returns
  390px. Separate app-shell follow-up; no global layout edit in this slice.
- 🟡 `client/src/hooks/useLifestyleCreep.ts:51`: cancelled reads can finish in
  transport; cleanup prevents adoption. Shared API has no signal option.
- 🟡 Validation scope: Chromium synthetic browser only; no live personal history,
  manual assistive-technology audit, Ubuntu or native renderer result claimed.
- ❓ No unresolved frontend/backend contract questions. T033 integrated QA and
  T034 final coordinator summary were still required at that point, not satisfied by this review (both were completed in later rounds; see sections 13 to 16).

## 12. Synthetic Browser Evidence and Frontend Manifest

T032 executed all eight scenarios from section 6 against the final production
build. No browser dependency was added:

1. `pnpm exec playwright --version` failed: no project CLI.
2. Located an existing cached Playwright installation under
   `%LOCALAPPDATA%/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright`.
3. Default launch expected absent `chromium_headless_shell-1243`. Used the already
   installed `chromium_headless_shell-1248` executable explicitly, without download.
   Observed browser version: **Chromium 156.0.8078.4**.

Executed:

```powershell
node '<session-files>\lifestyle-creep-smoke.cjs'
```

The bounded script serves only this worktree's `client/dist` with Node's built-in
HTTP server on **127.0.0.1:5205**. This replaces the optional Vite helper for the
smoke, so no Vite proxy runs. Before navigation, a catch-all Playwright handler
fulfills only the two known Bills GETs with synthetic data, aborts all unknown
APIs and other-origin traffic, and blocks service workers. Static-server `/api`
requests are an additional failure tripwire. Existing client API URLs never
reached their destinations. No API server or actual sync ran.

| Scenario | Observed result |
| --- | --- |
| 1. Loading → sustained | Held first response; busy state, both baseline windows, latest amounts and ordinary 7.69% inspected |
| 2. No-alert/suppressed/empty | 30% no-alert, zero/low-frequency suppression, complete empty and uncategorized-only states passed |
| 3. Insufficient/partial | Missing exact month, repair guidance (wording revised later, see section 16), ready Partner A retained under incomplete Partner B; `/sync` href/focus verified without navigation |
| 4. Error/Retry | Synthetic 500 hides verdicts; keyboard Retry restores selected history |
| 5. Sensitivity/race | 30%, 20.5%, 20%; precise out-of-range rejection, equivalent-value deduplication and delayed old-response rejection passed |
| 6. Privacy | Hide/show money in full DOM, including collapsed content, with percentages visible; detector requests **5 → 5** |
| 7. Independent controls | Grid/Graph/Table and past/future-window apply; detector requests **5 → 5** |
| 8. Keyboard/mobile | Enter/Space for Apply, Retry, disclosures, view/privacy controls; focusable sync link; 342px card fits 390px viewport, table scrolls within 292px container |

Final run: **12 detector GETs, 32 total mocked GETs, zero unknown/external requests,
zero API escapes, zero page errors**. Script closes its browser/context and
static server in `finally`; process exited successfully. A port-specific listener
check afterward found **0 listeners on 5205**. No user processes were stopped.

Mobile limitation is confined to the existing global nav (section 11), not hidden
by a full-site responsive pass claim. Screenshots were taken from the unmodified
page at scroll origin to avoid the existing sticky summary occluding the crop.

### Session artifacts

All artifacts are outside the repository, under:

```text
<session-files> (the agent session files folder, outside the repository)
```

- `lifestyle-creep-smoke.cjs` — reproducible isolated browser harness.
- `lifestyle-browser-evidence.json` — results, browser version, request ledger and layout measurements.
- `lifestyle-desktop-ready.png` — both rolling comparisons expanded.
- `lifestyle-desktop-hidden.png` — masked money, percentages retained.
- `lifestyle-mobile-ready.png` — 390px viewport, card-local table scrolling.
- `lifestyle-mobile-hidden-details.png` — mobile expanded detail with hidden money.
- `lifestyle-insufficient.png` — exact missing month and repair guidance.
- `lifestyle-error.png` — generic error and Retry.

### Frontend file manifest

Paths are relative to the worktree. No deletions, backend edits, package changes,
lockfile changes or global style changes in this frontend slice.

| Action | Files |
| --- | --- |
| Created transport/types | `client/src/types/lifestyle-creep.ts`; `client/src/api/lifestyle-creep.ts` |
| Created hook/helpers | `client/src/hooks/useLifestyleCreep.ts`; `client/src/lib/lifestyle-creep.ts` |
| Created UI | `client/src/components/bills/LifestyleCreepCard.tsx`; `client/src/components/bills/LifestyleCreepControls.tsx`; `client/src/components/bills/LifestyleCreepDetails.tsx` |
| Modified UI/type mirror | `client/src/pages/BillsPage.tsx`; `client/src/types/bills.ts` |
| Created synthetic fixture | `client/src/test/fixtures/lifestyle-creep.ts` |
| Created tests | `client/src/api/__tests__/lifestyle-creep.test.ts`; `client/src/hooks/__tests__/useLifestyleCreep.test.ts`; `client/src/lib/__tests__/lifestyle-creep.test.ts`; `client/src/components/bills/__tests__/LifestyleCreepCard.test.tsx`; `client/src/pages/__tests__/BillsPage.lifestyle-creep.test.tsx` |
| Updated docs | `README.md`; `docs/specs/005-lifestyle-creep/tasks.md`; this `quickstart.md` |
| Updated local memory | `memory.md` (gitignored; verified durable patterns) |

Schema-6/re-sync upgrade and rollback remain as documented in sections 9–10 and
the history contract; this slice adds no migration or read-time history repair.
Disabling the independent card/hook leaves legacy Bills totals and views intact.

**Handoff (first implementation round)**: 32 of 34 task markers were complete. **Only T033 integrated QA and
T034 final coordinator summary remained.** Requirements checklist untouched.
The failed merged-plan gate was not rerun, changed or relabelled. No branch
creation/rename, commits, pushes, PRs, merges, publication hooks or extension
configuration edits occurred.

## 13. Integrated QA Rework Cycle1 — 2026-10-31

The [review report](review-report.md) preserves the supplied initial **FAIL**,
its two Important static findings, reviewed scope and security checklist.
Neither finding had been runtime-reproduced at that review. This backend-only
rework reproduced both before changing production code. Both are now remediated
with passing regressions. They were **pending independent re-review** at that point (it later closed both; see section 14). This cycle was not a final QA pass.

### Reproduction, diagnosis and minimal fixes

1. **Capped acquisition accepted as complete.** With the real `PSClient`
   pagination loop, cap lowered to one, valid synthetic rows/full-month bounds,
   and an August 1 acquisition clock, a remaining next link still returned rows.
   Four failing integration cases covered July transactions/events and April
   prior-month transactions/events during a May–July sync. All four incorrectly
   published a new May Bills snapshot and changed the seeded June partial / July
   unavailable snapshots. Complete one- and two-page controls passed.
   - Added keyword-only `PSClient(..., require_complete_pagination=False)`.
     `sync_all` opts in once for its entire client, including `ensure_prior_month`.
     A next page remaining at the cap raises `PSClientError` before any Bills
     publication. All currently paginated sync inputs are covered, not only
     transactions; single-GET catalogs are unchanged.
   - Default/legacy client callers still warn and return truncated rows at the
     cap. The existing legacy truncation test is unchanged and passing. URL,
     redirect, repeated-link, timeout and error protections are unchanged.
     A last page exactly at the cap still succeeds.
   - This is a Bills-publication guarantee, not a new all-files transaction:
     existing catalog/raw/status writes can precede failure. Prior Bills
     snapshots remain byte-for-byte unchanged, and no new Bills file appears.
2. **Excluded null bindings rejected as invalid source.** A valid CC scope plus
   an excluded mapping with null owner/type raised `unresolved source ownership`
   in the producer and yielded unavailable sync history, both when the account
   was in the catalog and when only its retained mapping remained.
   - Null owner/type is accepted only with explicit Boolean `excluded=true`.
     Known values are still validated; included null/missing ownership/type
     remains fail-closed. No ownership/type is invented or written back.
   - Known owned CC exclusions still enter the fingerprint, including retained
     records absent from the catalog. Excluded unassigned accounts do not change
     the effective CC scope. Producer/build and repeated-sync tests cover both
     catalog states, excluded transactions, exact amounts and stable history.

No API response/model/schema, frontend, dependency, infrastructure or extension
changes were needed. No migration script ran. A later real-data validation is recorded in section 16. Additive schema 6
and explicit successful closed-month re-sync remain the upgrade/repair path;
GET cannot repair previously persisted evidence. Rollback leaves legacy Bills
totals usable but must not restore capped-history certification as trusted data.

### Isolation and exact final commands

All tests used synthetic inputs and temporary storage. `BILLS_CALC_LOG=0` was
set before collection. The bootstrap imports only the inert storage/path
definitions, redirects all private storage constants and the environment-file
path, clears the secret-file override, then imports pytest/application tests.
Per-test autouse temporary fixtures and filesystem/network tripwires remain
enabled. No actual private data, credentials, other checkout, existing service,
Docker, frontend server or live PocketSmith request was accessed.

Run each command from this worktree, repeating the bootstrap assignments in a
new shell. No launcher file, dependency restoration or config edit is needed:

```powershell
$env:BILLS_CALC_LOG = '0'
$env:PYTHONPATH = 'src'
$bootstrap = @'
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from budget_api.services import storage, env_writer

with TemporaryDirectory(prefix='feature005-qa-') as root:
    original = storage.PRIVATE_DATA_DIR
    isolated = Path(root) / 'private'
    isolated.mkdir()
    for name, value in list(vars(storage).items()):
        if isinstance(value, Path) and value.is_relative_to(original):
            setattr(storage, name, isolated / value.relative_to(original))
    env_writer.ENV_PATH = Path(root) / '.env'
    os.environ.pop(env_writer.API_KEY_FILE_ENV, None)
    import pytest
    raise SystemExit(pytest.main(sys.argv[1:]))
'@
```

Targeted affected source/history/endpoint/sync/client/account checks:

```powershell
uv run --no-sync --locked python -c $bootstrap src/budget_api/tests/bills/test_cc_spend_history.py src/budget_api/tests/bills/test_lifestyle_creep.py src/budget_api/tests/bills/test_lifestyle_creep_api.py src/budget_api/tests/bills/test_derivations.py src/budget_api/tests/bills/test_builder.py src/budget_api/tests/bills/test_sync_extension.py src/budget_api/tests/test_sync_lifestyle_history.py src/budget_api/tests/test_ps_client.py src/budget_api/tests/test_accounts.py src/budget_api/tests/test_sync.py -q --tb=short --show-capture=no
```

Reproduction selection, rerun green:

```powershell
uv run --no-sync --locked python -c $bootstrap src/budget_api/tests/bills/test_cc_spend_history.py src/budget_api/tests/test_sync_lifestyle_history.py -q --tb=short -k 'excluded_optional_binding or excluded_unassigned_mapping or capped_acquisition or complete_real_pagination' --show-capture=no
```

Full Windows nonrenderer:

```powershell
uv run --no-sync --locked python -c $bootstrap src/mega/tests src/v4_pipeline/tests src/mom/tests src/budget_api/tests -q -m 'not pdf_renderer'
```

| Check | Actual result |
| --- | --- |
| Before fix: defect selection above, bootstrap on stdin (`python -`), without `--show-capture=no` | **12 failed, 4 passed, 75 deselected**, 1 warning, 1.34 s |
| Before fix: `src/budget_api/tests/test_ps_client.py -q --tb=short -k strict_ --show-capture=no`, same stdin bootstrap | **9 failed, 40 deselected**, 1 warning, 0.76 s; proposed keyword absent, separate from the actual defect reproductions |
| First green targeted run, stdin bootstrap | **448 passed**, 1 warning, 7.90 s |
| First full run, stdin bootstrap | **1219 passed, 1 failed, 2 deselected**, 1 warning, 26.70 s; launcher-only Windows spawn failure below |
| Final full run, `python -c` command above | **1220 passed, 2 deselected**, 1 warning, 20.21 s |
| Final targeted run, `python -c` command above | **448 passed**, 1 warning, 6.04 s |
| Final defect selection, `python -c` command above | **16 passed, 75 deselected**, 1 warning, 1.14 s |

The full count is the previous **1184 + 36 new regressions = 1220**; no baseline
tests were removed or deselected beyond the same two renderer exclusions.
All commands emitted only the existing Starlette/httpx TestClient deprecation
warning. No renderer/Ubuntu result is claimed.

**Launcher correction, not an application fix:** the initial full run piped the
bootstrap to `python -`. Windows multiprocessing tried to reload `<stdin>` in
`test_publisher_lock_times_out_during_cross_process_contention`, so its child
never signalled readiness. Switching only the invocation to `python -c $bootstrap`
fixed it; the complete suite then passed without changing that test or production
publisher code. Use `-c`, not stdin, for this full-suite bootstrap.

Frontend was not rerun: no consumer contract or client code changed. Prior
**468 tests / build / eight browser scenarios** remain historical evidence from
sections 11–12, not new cycle1 executions.

### Cycle1 file manifest and self-review

| Action | Files touched in this rework only |
| --- | --- |
| Modified production | `src/budget_api/services/ps_client.py`; `src/budget_api/services/sync_runner.py`; `src/budget_api/services/bills_derivations.py` |
| Added regressions / adapted fake constructor | `src/budget_api/tests/test_ps_client.py`; `src/budget_api/tests/test_sync_lifestyle_history.py`; `src/budget_api/tests/bills/test_cc_spend_history.py` |
| Created review history | `docs/specs/005-lifestyle-creep/review-report.md` |
| Updated policy / handoff | This `quickstart.md`; `plan.md`; `research.md`; `contracts/bills-history-v6.md`; `tasks.md` |
| Appended durable corrections | `memory.md` (gitignored) |

- 🔴 Fixed: `services/ps_client.py:141` + `sync_runner.py:192`: cap could publish partial acquisition. Strict sync client now raises before Bills writes.
- 🔴 Fixed: `services/bills_derivations.py:114–130`: legal excluded null bindings poisoned every partner. Allow null only outside scope; retain known CC exclusions.
- 🟡 Constraint: previously persisted evidence needs explicit successful re-sync; no read-time rewrite or real-data repair was attempted in this cycle (a later real-data validation is recorded in section 16).
- 🟡 Review status: no unresolved defect found in this focused self-review; independent T033 re-review was still required at that point (it later closed both findings; see section 14). Numeric resource-stress speculation and prior client transport/nav/build observations remain nonblocking, not expanded into fixes.
- ❓ No unresolved implementation decision for these two fixes. T034 final coordinator summary still depended on T033 at that point.

Branch remains the existing app-managed branch; original feature changes are
retained. No new branch/rename, commit, push, PR, merge, extension edit, lockfile
change or publication occurred. The failed merged-plan gate remains failed
under the already-recorded explicit user continuation. **T033/T034 were not yet checked at that point.**

Final hygiene checks passed: `git --no-pager diff --check`; six modified/created
feature documents decoded as UTF-8 without BOM, with balanced fences and
resolving local links/anchors; exactly 34 task IDs, 32 checked, only T033/T034
unchecked at that point; initial FAIL and pending-independent-review wording retained.

## 14. Final local acceptance - 2026-10-31

All **34/34 tasks** were complete at the end of the first implementation round. Independent QA closed both Important
source-integrity findings after cycle1; no implementation blockers remain.
The original FAIL and exact reproduction history remain in
[review-report.md](review-report.md), alongside final acceptance.

| Gate | Final evidence |
| --- | --- |
| Backend | 1220 passed, 2 renderer tests deselected; 448 affected tests passed after fixes |
| Frontend | 468 passed across 47 files; production build passed |
| Browser | Eight synthetic Chromium scenarios passed; no escaped API requests/page errors |
| Review | Both findings independently closed; coordinator resolved Git-metadata caveat |
| Task state | 34 completed, zero pending |
| Publication | None; changes were uncommitted at this boundary |

These numbers are the first-round acceptance counts. The final counts after the rebase and the review round are in [section 16](#16-post-rebase-real-data-validation).

The coordinator inspected the full tracked/untracked Git manifest, not merely
file existence: 18 backend implementation/test files, 15 frontend
implementation/test files, README and 11 feature documents. The index is empty.
`git diff --check` passed, with no dependency, lockfile, workflow-hook or sibling
changes. The isolated browser helper was stopped; port 5205 had no listener.
No source changed after final QA; completion documentation alone was updated.

**Upgrade:** existing title-only or incomplete snapshots cannot supply trusted
history. A later explicit, successful re-sync that covers all five closed months (and runs through the usual sync end month, at least the current month, in one run under a consistent account/category configuration) creates
schema-6 evidence. Until then, the UI reports unavailable history rather than
inventing category IDs or zeroes. A later real-data validation is recorded in section 16.

**Rollback:** the additional history fields are optional and legacy title totals
remain unchanged. Removing the feature UI/endpoint does not require deleting
stored financial history or altering earlier report fields. No database migration
or eager file rewrite was introduced.

The earlier merged-plan gate remains **failed**, with the user's subsequent
local-continuation instruction recorded in the plan; this is not a gate pass or
an explicit `--skip-review`. Optional commit/publication and unrelated bugfix
hooks were skipped. Existing mobile app-navigation overflow and build warnings
remain documented, not newly introduced or silently repaired. No Ubuntu,
native-renderer, live-finance or additional assistive-technology result is claimed.

## 15. Unmocked Real-API Browser Smoke - 2026-10-31

Requested after final acceptance: one bounded check in which the production build
talks to a real FastAPI process over HTTP. Section 12 mocked the API; this section
does not. No repository file, source or dependency changed, and the full suites were
not rerun. Result: **182 of 182 assertions passed**.

### Topology and isolation

Headless Chromium 156 (Playwright 1.63, Node 22.13.1) to a Node server on
127.0.0.1:5205, to uvicorn 0.53 on 127.0.0.1:8105, to synthetic storage in a
temporary directory outside the repository.

- The Node server serves `client/dist` read-only and forwards every `/api/*`
  request unchanged to 127.0.0.1:8105, a hard-coded upstream. It is a pass-through
  proxy, not a mock, and mirrors the Docker layout in the README (static frontend
  plus a same-origin `/api/` proxy). Vite's dev proxy is fixed to port 8100 and was
  not used.
- The API launcher applies the storage, `.env` and API-key patches from
  `src/budget_api/tests/conftest.py` before importing the app and arms a
  `Path.open` tripwire on the real `data/private` and `.env`. Tripwire hits: **0**.
  Its four startup self-probes were blocked before any file access. No API key
  existed and only GET requests were made, so no sync or outbound call was possible.
- Fixtures are synthetic: schema-6 snapshots for five closed months with category
  IDs and a consistent scope fingerprint, two legacy schema-5 snapshots, two months
  with no file, and a dashboard snapshot for every displayed month. Partners are
  labelled "Fixture A" and "Fixture B".
- No `route`, `fulfill` or request-interception call exists in any harness script
  (pattern scan: 0 matches). The browser side only observes request, response,
  failure, console and page-error events.
- Chromium ran with `--host-resolver-rules="MAP * ~NOTFOUND , EXCLUDE 127.0.0.1"`. A
  probe of `localhost:5205` failed to resolve, so nothing could reach 8100 or 8080 by
  name. The user's stack was never contacted.

### Disclosed deviation: base URL swapped in memory

The production bundle bakes in its default API origin
(`VITE_API_URL ?? "http://localhost:8100"`, repeated in `api/reports.ts`). The Node
server removes that string from the served JavaScript in memory (2 occurrences,
42 bytes; disk and served SHA-256 values are in the evidence file), so the page calls
same-origin `/api`. This equals the empty `VITE_API_URL` that the README says the
Docker frontend build uses. The file on disk is untouched and no other byte of any
asset changed. Not exercised by this smoke: CORS between separate origins, the Vite
dev proxy, the Docker image itself, a real re-sync, real data and Ubuntu CI. A later real-data validation through the container stack is recorded in section 16.

### Results

| Scenario | Real request | Observed |
| --- | --- | --- |
| Ready, default 20% | `GET /api/bills/lifestyle-creep?month=2026-10&threshold_percent=20` returned 200 with `Cache-Control: no-store` and `server: uvicorn` | Status ready over 2026-05 to 2026-09, evaluated 2026-08 and 2026-09. Fixture Growth sustained: latest 140 kr against a 110 kr prior average, +30 kr, 27.27%. Fixture Flat (0%) and Fixture Spike (one month only) not sustained. Fixture ZeroBase shown as suppressed with no percentage. A low-frequency category for Fixture B suppressed. UI values equal the response body. |
| Threshold 30% | New request with `threshold_percent=30`, echoed in the response | Fixture Growth no longer sustained (27.27% is below 30%). Restoring 20 flags it again. |
| Stale or legacy history, month 2026-09 | `month=2026-09`, 200 | `insufficient_history` with two `legacy_history` issues (2026-04, both partners). Guidance named 2026-04 through 2026-08 when this smoke ran, with a link to `/sync`; the wording was revised later (see section 16). No category verdicts and no invented zeros. |
| Insufficient history, month 2026-06 | `month=2026-06`, 200 | `insufficient_history` with six issues: 2026-01 and 2026-02 `missing_snapshot`, 2026-03 and 2026-04 `legacy_history` for both partners. Guidance named 2026-01 through 2026-05 when this smoke ran (wording revised later, see section 16). No verdicts. |
| Privacy | No new request | 108 money amounts masked and 24 percentage values still shown. |

Across the run: 25 requests and 25 responses, all 2xx. Twenty-two were `/api` calls
(16 Bills dashboard months and 6 detector reads). There were zero failed requests,
zero page errors, zero console errors or warnings, and every request stayed on
`http://127.0.0.1:5205`. The uvicorn access log lines match the browser-observed API
requests one to one. Applying a month or a threshold produced exactly one new
detector read each time.

### Findings outside the feature, left unfixed

1. `client/src/styles/theme.css:159` sets `--accent: #0f6b78` as a hex value, while
   line 114 maps it through `hsl(var(--accent))`. Hovering a shared outline `Button`,
   including Apply month and Apply threshold, rendered a white label on a transparent
   background (measured contrast 1:1; resting contrast 12.78:1). [Inference] The
   hex-in-HSL mismatch is the likely cause; no patch was tested. The same variant is
   used across the app, and `theme.css` is not in this feature's diff.
2. The existing app navigation overflows at 390px (document width 562px). No
   overflowing element is inside the detector card. This repeats the limitation in
   section 11.

### Run order, cleanup and repository state

Scripts take explicit `--tmp`, `--repo` and `--out` arguments (usage is in each file
header): fixtures, then launcher on 8105, then the browser script, then stop the
started PIDs, finalize in phase `stopped`, delete the temp directory, finalize in
phase `deleted`.

The uvicorn chain (uv 53180, venv launcher 44932, python 51700) was stopped by PID. No
listener remained on 5205 or 8105, and the user's listeners on 8080 and 5173 (PID
39776) were untouched. The temporary storage directory was deleted. Afterwards the
coordinator re-ran the Git checks independently: `git status --porcelain
--untracked-files=all` still lists the same 45 paths before this section was added,
the branch is the existing app-managed branch at `979a01c`, and `git diff --check` is clean.

### Session artifacts

Outside the repository, in the folder named in section 12:

- `lifestyle-real-api-fixtures.py`, `lifestyle-real-api-launcher.py`,
  `lifestyle-real-api-smoke.cjs`, `lifestyle-real-finalize.cjs`: the harness.
- `lifestyle-real-api-evidence.json`: assertions, request ledger, uvicorn access
  lines, tripwire result and cleanup checks. `lifestyle-real-api-smoke-console.txt`
  holds the run output.
- `lifestyle-real-ready.png`, `lifestyle-real-stale.png`,
  `lifestyle-real-insufficient.png`, `lifestyle-real-mobile-ready.png`,
  `lifestyle-real-hover-apply-month.png`, `lifestyle-real-hover-apply-threshold.png`.

## 16. Post-rebase real-data validation

This section records the work after the first implementation round: the rebase onto the main branch that gained the Runway feature, the first run against real data through the container stack, one defect found there and fixed, an independent review of the result, and the review-driven fixes. It is generic on purpose. It records no real counts, names, amounts, volume names or timestamps.

**Provenance**: the rebase, container and real-data results were reported by the coordinator while working against the running stack. They cannot be reproduced from the repository, because real data is never committed; the synthetic tests exercise the same code paths. The code-level statements (role-key rule, clock use, sync-window shape, UI strings) were checked by reading the code. Anything not confirmed from code is labelled `[Unverified]` or `[Inference]`.

### Rebase and conflicts

- The feature commits were rebased onto the updated main branch, which now contains the Runway feature. A safety ref was created before the rebase.
- Only two files had real conflicts. In the app entry module (`src/budget_api/main.py`) the resolution is the union of the no-store path set and the router registrations. In the Bills page component (`client/src/pages/BillsPage.tsx`) the Runway version was taken and the detector mount was re-applied. The README merged cleanly.
- A never-resolving stub of the detector API client was added to the Bills page test (`client/src/tests/BillsPage.test.tsx`), so the Runway fetch-count assertions stay intact.
- The Bills page now renders, top to bottom: summary/header, Runway panel, Lifestyle creep card, Bills dashboard.

### Post-rebase verification

- The backend and client suites and the production client build passed on the merged tree.
- 37 merge and routing tests were added (`src/budget_api/tests/bills/test_lifestyle_creep_runway_merge.py`): routing to the intended endpoint through an ASGI spy, the documented 400 and no-store bodies, Runway behavior unchanged, and schema variants of the stored files.
- Client tests for the order and independence of the Runway panel and the detector card were added (`client/src/pages/__tests__/BillsPage.lifestyle-creep.test.tsx`). They check the order (Runway panel, then the card, then the dashboard) and that each side keeps working when the other one fails.
- Final counts of the review round: backend **1580 passed, 2 renderer tests deselected** (the isolated non-renderer command of section 13); client **49 files and 540 tests passing**; production client build passing.

### Docs containment

A branch-name literal and local absolute paths in documentation tripped the repository containment tests (`src/mom/tests/test_current_tree_containment.py` and `src/mom/tests/test_lg002_identifier_containment.py`) and were neutralized. Run both after every documentation edit. Documentation must not carry local paths, personal identifiers or the app-managed branch name.

### Containers

- Real data lives in the named volume `private-data` declared in `compose.yaml`, which Compose prefixes with the project name. `compose.yaml` sets no project name, so a checkout folder with a different name would get a new, empty volume and would collide with the running stack on the published port (`APP_PORT`, default 8080).
- Start the stack with an explicit project name: `docker compose -p pocket-smith-reports up --build -d`.
- Before the first rebuild: create a byte-verified copy of the private-data volume, and tag the previous images for rollback.
- Rollback: retag the saved images as `latest`, run `docker compose` with `up` and no build, and restore the data from the volume copy.
- Never use `docker compose down -v` or a volume prune. Both remove named volumes and would delete everything the app stores under its private data directory.

### Real-data defect (found and fixed)

- Symptom: the first real re-sync made every history block `invalid_source`.
- Root cause: `compute_cc_spend_history` (`src/budget_api/services/bills_derivations.py`) required every key of `category_roles.json` to be a canonical category ID. The stored file also holds a role under the synthetic, non-numeric `uncategorized` key, which the reports pipeline uses for transactions without a category (`src/v4_pipeline/data_loader.py`). [Unverified] Which writer creates that entry was not traced.
- Fix: every role value is still validated, but only keys whose role is `exclude` define the exclusion population and the scope fingerprint, and only those keys must be canonical IDs. Non-`exclude` keys that are not canonical IDs are ignored. A non-ID `exclude` key still fails closed. The rule is item 2 of the Source-Trust Rules in [contracts/bills-history-v6.md](contracts/bills-history-v6.md#source-trust-rules).
- Tests: 22 synthetic tests were added with the fix. The review round added 12 parametrized cases (six non-canonical key forms, each run against both strictness checks): a leading space, a trailing space, a plus sign, a digit separator (`1_2`), a decimal point and Arabic-Indic digits. All of them fail closed. They never shape the scope without the `exclude` role, and with it they raise `invalid source identity`.

### Real-data outcome

Recorded in generic terms only. No counts, names or amounts.

- Before the re-sync, history stored by schema 5 reported `insufficient_history` with `legacy_history` issues, as designed.
- After one explicit sync, the detector reported `ready` for the evaluated month, with zero issues.
- An independent Decimal recomputation from the spec matched the API at thresholds 20, 1 and 100.
- A headless-browser structural check of the real page found the card in the ready state, the month and threshold controls working, zero console errors, zero failed requests, hide-amounts masking money values, and the expected order of Runway panel, card and Bills dashboard.

### How a user inspects it

1. Open the Bills page of the running app. The "Lifestyle creep detector" card sits below the "Runway & Burn Rate" panel and above the Bills dashboard. (Superseded on 2026-11-02: the card now lives on its own **Lifestyle Creep** tab at `/lifestyle-creep`; see [section 17](#17-separate-lifestyle-creep-tab---2026-11-02).)
2. Controls: "Apply month" (the viewing month, never later than the current month), "Apply threshold" (1 to 100 percent) and "Retry history". Retry reads the saved history again and never starts a sync.
3. Status of the whole card: "Ready" (five complete, comparable months), "Partial coverage" (only the ready partners can be assessed) or "Insufficient history" (a month is missing, legacy or still open). Each partner shows "Ready" or "Insufficient history".
4. When history is incomplete the card lists the issues, gives the re-sync sentence quoted in Known limitations item 2, and links to the Sync page ("Open sync to repair history"). The link only opens the page. It does not start a sync.
5. A failed request shows no status badge. The card shows an alert instead ("Could not load lifestyle history. No conclusion is available. Retry to read the saved history again.", or "Selection was rejected. Check the viewing month and threshold, then retry." for a 400) with "Retry history".
6. For a ready partner the card shows a category table with an outcome per category (sustained growth, no sustained growth, or suppressed for a zero or low-frequency baseline), plus expandable "Comparisons and observations" and uncategorized spending panels. Hide amounts masks money values and keeps percentages visible.

### Known limitations

Items 1 and 3 are documented and deliberately left unchanged (the API contract is not modified). The README carries the same list in short form.

1. **Timezone, first hours of a month — T052 handling supersedes the earlier rejection limitation.** The API uses its process clock (`date.today()` in `services/lifestyle_creep.py`); the current standalone client defaults to the latest completed browser-local month. When that target is still current on the API clock, a fully valid selection now returns 200 with `insufficient_history`, no partners or money, and a null-partner `partial_month` / `open_month` issue. It resolves no snapshot paths and reads no snapshots, even if saved status claims complete. The card shows the open-month reason and no reliable conclusion; its evidence list names required months, not months read. Wait until the API month closes or select an earlier target, then re-sync after closure if saved history is partial. Client-side current-month exclusions remain unchanged. Future API months and malformed selections still return 400. The clocks themselves are not synchronized, and no new container/timezone verification is claimed. Before any financial-history reads, the service checks every selected evidence month against its current clock; builder completion based on acquisition time is not sufficient to bypass this check.
2. **Sync-window shape.** The last month of a sync window has no everyday-budget zone, because next-month events are taken only from months inside the window (`build_bills_chain` in `src/budget_api/services/bills_builder.py`). Past savings balances are derived from the live balance anchor using only the deltas inside the window (`_back_walk_past_balances`), and months outside the window are never recomputed. [Inference] A window that stops before the current month can therefore leave a partial picture on the Bills page. The effect was not reproduced, and the detector evidence itself uses neither input. For that reason the card says: "Re-sync from {first window month} through your usual sync end month (at least the current month) in one run under a consistent account/category configuration, then retry." The earlier wording, which named only the five detector months, is retired.
3. **Hand-edited `exclude` role with a non-ID key.** If `category_roles.json` holds an `exclude` entry whose key is not a canonical category ID, the detector reports `invalid_source` with no detail about the key, because the evidence builder fails closed. [Inference] Only a direct edit of the file can produce this, because the category-mappings route accepts only IDs present in the stored catalog and no other app code writes the file. Deferred.
4. **Re-sync depth.** Viewing month M needs months M-5 to M-1 re-synced with this build. History stored by earlier builds stays `legacy_history` until its month is re-synced, which is the intended result.

### Review round and remaining task

An independent read-only review of the post-rebase delta returned pass-with-caveats, with no critical or high findings. Its ten findings and their dispositions are in [review-report.md](review-report.md#post-rebase-review-real-data-round). The review-driven fixes (re-sync wording in the UI and in these documents, strict key-form tests, refreshed comments, the restored Runway header comment in the Bills page, the no-store fetch option on the detector request, and the limitations above) are T039. T040, the final container rebuild and structural verification, is performed by the coordinator after the documentation commit.

## 17. Separate Lifestyle Creep tab - 2026-11-02

At the user's request the detector moved off the Bills page to its own tab (T041). Client only: no backend, API path or contract field changed. `GET /api/bills/lifestyle-creep` stays where it was.

### What changed

- New page `client/src/pages/LifestyleCreepPage.tsx` with the heading "Lifestyle Creep", a one-line description and the existing card. It holds the detector state that `BillsPage` used to hold, with the same behavior: the viewing month defaults to the browser's local month at mount, the threshold to `20`, both visit-local (reset on a fresh visit, no localStorage or query parameters). It calls `useAmountsHidden()` at the page root like the other pages.
- `client/src/router.tsx`: route `lifestyle-creep`.
- `client/src/layouts/AppLayout.tsx`: nav tab **Lifestyle Creep** directly after **Bills**, same styling as its siblings.
- `client/src/pages/BillsPage.tsx`: detector state, imports and card mount removed. The Runway panel, the dashboard and the window controls are unchanged. The month check of Known limitations item 1 (`currentMonth()`) now lives in `LifestyleCreepPage.tsx`.
- The card components stay in `client/src/components/bills/`.
- `client/src/components/bills/LifestyleCreepControls.tsx` (coordinator change after review): the month help text "Detector only; the Bills display window stays unchanged." became "Uses the five closed months before this month.", because the card no longer sits next to the Bills window controls.
- `client/nginx/default.conf` already falls back to `index.html` (`try_files $uri $uri/ /index.html;`), so a deep link to `/lifestyle-creep` works in the container without a config change.

### Tests

- `client/src/pages/__tests__/BillsPage.lifestyle-creep.test.tsx` was deleted and replaced by `client/src/pages/__tests__/LifestyleCreepPage.test.tsx` (6 tests): defaults to the current month and 20%, no Bills or Runway request; detector failure shows the alert, and **Retry history** requests the same month and threshold again, then clears the alert and shows the partner table (extended after review); threshold retune without coercion, dedupe of equivalent values, persistence across a month change and reset on a fresh visit; future, empty and out-of-range months rejected; hide amounts masks money without a refetch; a fresh January visit uses the new local year. The Bills ordering and dashboard-state cases were dropped because the card is no longer on Bills.
- `client/src/tests/BillsPage.test.tsx`: the never-resolving detector stub became a plain spy, and 4 new cases (dashboard, not found, error, loading) assert that Bills renders no detector region or month control, never calls the detector API, and still makes exactly the two Runway requests.
- New `client/src/tests/LifestyleCreepRoute.test.tsx` (1 test) uses the real router: a deep link to `/lifestyle-creep` renders the app shell with the **Lifestyle Creep** tab active, placed right after **Bills**, `href="/lifestyle-creep"`, plus the page heading and the detector region. The detector API is mocked and global `fetch` is a tripwire.
- Mutation check: with the previous `BillsPage.tsx` (card still mounted) put back temporarily, all 11 cases in `src/tests/BillsPage.test.tsx` failed, the 4 new ones included. The spy returns `undefined`, so a detector mount on Bills fails loudly. The new `BillsPage.tsx` was restored afterwards.

### Commands and results

From `client/`:

```powershell
pnpm exec vitest run src/pages src/tests/BillsPage.test.tsx src/tests/LifestyleCreepRoute.test.tsx src/components/bills/__tests__/LifestyleCreepCard.test.tsx src/hooks/__tests__/useLifestyleCreep.test.ts src/layouts
pnpm exec vitest run
pnpm build
pnpm exec tsc -p tsconfig.json --noEmit
```

- Targeted: 6 files, 70 tests passed.
- Full client suite: 50 files, 539 tests passed. Before the change: 49 files, 540 tests. The difference is the deleted 12-test Bills integration file against 6 + 4 + 1 new tests.
- `pnpm build` (`tsc -b && vite build`) passed, with the known chunk-size and mixed static/dynamic import warnings.
- `tsc --noEmit` passed. The client has no lint script.
- From the repository root, `uv run pytest src/mom/tests/test_current_tree_containment.py src/mom/tests/test_lg002_identifier_containment.py -q`: 9 passed.

### Review follow-up - 2026-11-02

A read-only review returned pass-with-caveats. Follow-up changes: the help text above, current instructions in sections 5 and 6 and in the [card contract](contracts/bills-card.md#required-client-verification), and the Retry test. Mutation check: with `onRetry` replaced by a no-op in `LifestyleCreepPage.tsx`, the extended Retry test failed (1 of 6); the page file was restored byte-identical.

From `client/`:

- Coordinator, after the help text change: `pnpm exec vitest run src/components/bills/__tests__/LifestyleCreepCard.test.tsx src/pages src/tests/BillsPage.test.tsx src/tests/LifestyleCreepRoute.test.tsx`: 4 files, 51 tests passed.
- After the Retry test change, the same four targets: 4 files, 51 tests passed.
- `pnpm exec vitest run`: 50 files, 539 tests passed.
- `pnpm exec tsc -p tsconfig.json --noEmit`: passed.
- No local `pnpm build` after the help text change. The frontend image build below runs `pnpm build` (`client/Dockerfile`) and succeeded.
- Containment tests from the repository root (`$env:PYTHONPATH='src'; uv run --no-sync --locked python -m pytest src/mom/tests/test_current_tree_containment.py src/mom/tests/test_lg002_identifier_containment.py -q`): 9 passed.

### Container rebuild and real-page check (T040) - 2026-11-02

Done by the coordinator on the working tree: the committed feature work plus the uncommitted tab move and documentation changes. No documentation commit was made. Real data was used; only structure and status were recorded, no amounts.

- From the worktree root with `APP_PORT=8080`: `docker compose -p pocket-smith-reports build frontend`, then `docker compose -p pocket-smith-reports up -d frontend`. The frontend container was recreated and is healthy on 127.0.0.1:8080. The api container is healthy and unchanged; its image comes from the earlier rebuild of the same tree. The named volume `pocket-smith-reports_private-data` was preserved.
- Headless Chromium, no mocks, same-origin requests only, DNS blocked except 127.0.0.1:
  - Nav order: Sync, Monthly Reports, Mega Reports, Bills, Lifestyle Creep, Settings, Docs.
  - `/bills` shows the Runway region, no "Lifestyle creep detector" region, and makes no `/api/bills/lifestyle-creep` request.
  - Clicking the tab navigates to `/lifestyle-creep`: h1 "Lifestyle Creep", the link has `aria-current="page"`, and the detector region settles at `aria-busy="false"` with 2 partner tables and 0 alerts. The lifestyle API returned 200 with `status: "ready"`.
  - A deep link to `/lifestyle-creep` returns the document with 200 (nginx SPA fallback) and shows the new help text.
  - 0 console errors, 0 failed requests.

### Known limitation: nav overlap on Mega Reports

Measured by the coordinator in headless Chromium against the container. With the new tab, the right edge of the nav's privacy toggle is at 808px (nav `scrollWidth` 976 at a 1024px viewport, 635 at 390px). The fixed Mega Reports contents toggle (`right: 16px`, 40px wide, `client/src/components/mega-reports/MegaReportNav.module.css`) therefore overlaps the privacy toggle in viewports narrower than about 864px. Before the tab was added that point was about 150px lower. No overlap at 1024px and 1280px. At 390px the nav already overflowed before this change ([section 12](#12-synthetic-browser-evidence-and-frontend-manifest)). Left unchanged; a responsive nav is a separate decision.

## 18. Historical multi-month evaluation period - 2026-11-02

**Superseded**: The user's later clarification confirms one target month versus a separate reference-period mean. This section records the earlier implementation and its verification only; it is not the current contract.

### Current behavior and scope

T046 preserves the earlier uncommitted tab move and integrates the completed backend contract. The frontend slice changes only client feature files, synthetic client tests/fixtures and relevant docs; no backend implementation was changed by this slice.

- **From month** and **To month** select inclusive whole completed months. **Apply period** applies both drafts atomically. Draft edits never fetch or relabel prior results.
- Default is the latest two completed browser-local months: on November 2, September–October; on January 1, November–December of the prior year. There is no viewing-month control.
- Accept 1–24 months, earliest From `0001-04`. Reject empty, malformed, reversed, current/future or oversized selections with associated inline errors and `aria-invalid`, without requests. A single month shows a rolling comparison and an explicit warning that it cannot establish sustained growth.
- Every page request supplies `comparison_start`, `comparison_end`, derived compatibility `month=To+1` and canonical threshold. API wrapper legacy omitted-range arguments remain supported. Requests remain uncached GETs.
- Required evidence is From−3 through To (4–27 snapshots). May–October needs February–October, not just the selected six months. Missing baseline/interior snapshots do not auto-shift, shorten or zero-fill the selection.
- Each evaluated month uses its own prior three-month mean. The server decides sustained growth from any two consecutive eligible strict exceedances; UI outcomes say **within selected period**, not that the latest pair necessarily grew. All comparisons/samples render; latest values use the last comparison. Single-month ordinary MoM uses the preceding baseline sample.
- Selected comparison period and required evidence ranges remain labelled during loading, error, insufficient, partial and ready states. Re-sync guidance begins at From−3 and continues through the usual sync end month, at least current, in one consistent run. Retry never syncs.
- Threshold remains an exact canonical decimal, default 20%, bounds 1–100. Apply threshold remains separate from Apply period; applied sensitivity persists across period changes, equivalent values do not refetch, fresh visits reset. No URL/localStorage persistence.
- Hook identity includes both boundaries, derived month, canonical threshold and Retry attempt. A changed From with the same To is a new selection. Old values disappear immediately; stale successes/failures and mismatched echoed identities cannot overwrite current results. Retry repeats applied boundaries/threshold, ignoring edited drafts.
- Global privacy masks all money, including collapsed long-range details and uncategorized samples, with no requests. Bills still neither renders nor fetches the detector; deep-link/navigation tests preserve the tab placement.

### T046 synthetic verification

All fixtures and network responses were synthetic. No Docker, live sync, server startup, real financial data, credentials, other checkout, dependency change, commit, branch change or PR operation occurred.

From `client`:

```powershell
pnpm test src\api\__tests__\lifestyle-creep.test.ts src\hooks\__tests__\useLifestyleCreep.test.ts src\lib\__tests__\lifestyle-creep.test.ts src\components\bills\__tests__\LifestyleCreepCard.test.tsx src\pages\__tests__\LifestyleCreepPage.test.tsx src\tests\LifestyleCreepRoute.test.tsx src\tests\BillsPage.test.tsx --reporter=dot
pnpm test --reporter=dot
pnpm build
```

| Check | Result |
| --- | --- |
| Initial helper/API red tests | 15 failed, 59 passed: missing period helpers and absent encoded range parameters, before implementation. |
| Targeted client feature/Bills tests | **7 files, 181 tests passed**. |
| Full client suite | **50 files, 594 tests passed** (55 added versus the prior tab-move round). |
| Production build | **Passed**, `tsc -b` plus Vite; 2611 modules transformed. |
| Backend range verification inherited from T045 | **374 targeted tests passed**, recorded by the backend slice in tasks.md; not rerun or claimed as new frontend execution. |
| Documentation containment | **9 passed** in 13.11s; static tracked-text and identifier scans, with no forbidden tracked paths. |

During implementation, two new sample-render assertions needed to select the spend cell because spend and baseline can legitimately display the same amount; production behavior was correct. The first build caught an unused test import, removed before the passing full suite/build. No packages were installed. Non-blocking warnings: React `act(...)` warnings in existing MegaReportsPage/GraphView tests, the existing mixed static/dynamic `types/api.ts` import warning, and the existing large output chunk warning.

From repository root, after verifying the static containment scans exclude prohibited tracked paths:

```powershell
$env:PYTHONPATH = 'src'
$env:BILLS_CALC_LOG = '0'
uv run --no-sync --locked python -m pytest src\mom\tests\test_current_tree_containment.py src\mom\tests\test_lg002_identifier_containment.py -q --basetemp=.pytest_cache\period-client-containment
git --no-pager diff --check
```

`git diff --check` passed. Source and documentation remained in the assigned worktree; no generated test directory remains from this check.

### T046 file manifest

- Source under `client/src`: `api/lifestyle-creep.ts`, `types/lifestyle-creep.ts`, `lib/lifestyle-creep.ts`, `hooks/useLifestyleCreep.ts`, `pages/LifestyleCreepPage.tsx`, `components/bills/LifestyleCreepControls.tsx`, `components/bills/LifestyleCreepCard.tsx`, `components/bills/LifestyleCreepDetails.tsx`.
- Tests/fixtures under `client/src`: `api/__tests__/lifestyle-creep.test.ts`, `lib/__tests__/lifestyle-creep.test.ts`, `hooks/__tests__/useLifestyleCreep.test.ts`, `components/bills/__tests__/LifestyleCreepCard.test.tsx`, `pages/__tests__/LifestyleCreepPage.test.tsx`, `tests/LifestyleCreepRoute.test.tsx`, `test/fixtures/lifestyle-creep.ts`.
- Documentation: `README.md`, feature `contracts/bills-card.md`, `plan.md`, `research.md`, `quickstart.md`, `tasks.md`; sourced durable facts appended to gitignored `memory.md`.
- Preserved without further edits: tab move in `AppLayout.tsx`, router and Bills page/test; deletion of the old Bills detector test; all new backend source/tests and the existing schema/API/spec/checklist/review document edits.

### Remaining gates at the T046 handoff (superseded below)

Only T046 is completed by this frontend slice. T047 independent integrated review and T048 coordinator container/browser acceptance remain unchecked. No new browser or deployment success is claimed. Earlier dated runtime records remain historical. Existing server/browser month-boundary time-zone and responsive-nav limitations remain unchanged.

The requirements checklist was inspected read-only: **34 checked, zero unchecked**, including CHK028–CHK034 for the amendment. These are requirements-quality markers, not independent implementation acceptance. FR-026–FR-032 coverage is mapped in tasks.md. Optional pre/post implementation commit hooks and the optional bugfix verification hook were skipped under the scoped no-commit frontend assignment; no workflow gate was rerun.

### T047 independent review and T048 actual-stack acceptance

**Review provenance**: The coordinator supplied an independent code-review result of **PASS, no significant findings** before deployment. The verification specialist did not act as an independent reviewer or rerun unchanged full suites. T045/T046's synthetic acceptance remains 374 backend tests, 181 targeted client tests and 594 full client tests; these are inherited results, not new runtime measurements.

**Deployment boundary**: Compose ownership labels identified this assigned worktree and its `compose.yaml`. Only API/frontend were rebuilt/recreated; no other project, `.env`, private file or credential was inspected. The API's volume mount stayed `pocket-smith-reports_private-data` at `/app/data/private`; it was not replaced, deleted or pruned. No sync or production-data write was requested. No environment/config interpolation was printed.

From the assigned worktree, in PowerShell:

```powershell
$env:APP_PORT = '8080'
docker compose -p pocket-smith-reports build api frontend
if ($LASTEXITCODE -ne 0) { throw 'Image build failed' }
docker compose -p pocket-smith-reports up -d api frontend
if ($LASTEXITCODE -ne 0) { throw 'Container update failed' }
docker compose -p pocket-smith-reports ps --format json |
    ConvertFrom-Json | Select-Object Service, State, Health
node '<session-files>\lifestyle-period-container-smoke.cjs'
```

Both image builds and container bring-up **passed (exit 0)**. The frontend Docker build runs `VITE_API_URL="" pnpm build`, covering the current TypeScript/Vite production build. API and frontend were **running/healthy** before and after browser verification; the frontend published only `127.0.0.1:8080`, with `/lifestyle-creep` returning HTTP 200. The API runtime and browser month were both `2026-11`.

**Real browser evidence**: Headless Chromium used the actual frontend and backend, no response mocks or bundle changes. DNS resolution was blocked except for `127.0.0.1`. Every detector check waited for its real response and for the named detector region's `aria-busy=false`, not just network idle. No screenshots, traces, raw bodies, financial values or identities were saved or printed. Real bodies were inspected in memory only for dates, statuses, array shapes and counts; details started privacy-hidden.

| Scenario | Inclusive comparison | Derived `month` | Exact evidence window | Evaluations / evidence | HTTP / coverage |
| --- | --- | --- | --- | --- | --- |
| Direct route default | 2026-09 through 2026-10 | 2026-11 | 2026-06 through 2026-10 | 2 / 5 | 200 / ready |
| Change both boundary drafts, then Apply | 2026-05 through 2026-09 | 2026-10 | 2026-02 through 2026-09 | 5 / 8 | 200 / insufficient_history |
| Extend historical end, then Apply | 2026-05 through 2026-10 | 2026-11 | 2026-02 through 2026-10 | 6 / 9 | 200 / insufficient_history |
| Single completed month | 2026-10 through 2026-10 | 2026-11 | 2026-07 through 2026-10 | 1 / 4 | 200 / ready |
| Apply threshold 30 to that single month | 2026-10 through 2026-10 | 2026-11 | 2026-07 through 2026-10 | 1 / 4 | 200 / ready |
| Enter again via the navigation tab | 2026-09 through 2026-10 | 2026-11 | 2026-06 through 2026-10 | 2 / 5 | 200 / ready |

All six queries explicitly included `comparison_start`, `comparison_end`, `month=To+1` and the applied threshold. Echoed identities, every month string, per-category comparison/baseline shapes and displayed evidence labels matched. Historical ranges retained their requested boundaries and displayed insufficient history with no category verdicts; absent coverage was not treated as zero or a failed smoke. **Partial coverage was not observed in this stored dataset**; it remains covered by the inherited synthetic tests.

**164 assertions passed** across **27 requests / 24 API responses / 6 detector responses**. Additional checks:

- From month, To month and Apply period were visible on direct and navigation entry; navigation marked the active page. Default was the prior two completed months.
- Draft edits caused no request; each valid Apply made exactly one detector request. A mutation observer found no stale result table/evidence tree under loading, and settled rows/comparison headings matched only the applied response.
- Reversed, current-month, future-month, 25-month and missing-boundary drafts had `aria-invalid=true` with an associated polite live explanation. Applying each made no request and did not relabel the prior result.
- The one-month response had no sustained verdicts and showed the explanatory warning. Threshold Apply retained that exact range; navigation reset to default range/threshold.
- Show/hide amounts changed the toggle's `aria-pressed` state with **zero extra network requests**. Monetary cells and closed details were masked; no monetary value was captured.
- Bills rendered no detector and made **zero lifestyle API requests**. Returning via its adjacent Lifestyle Creep nav tab loaded the ready default only after the detector settled.
- **Zero page errors, console errors, connection errors, HTTP errors, external requests, non-GET requests and sync requests**. All browser requests were same-origin. Browser/profile helpers were closed and removed; the actual Compose stack remains running healthy.

**Evidence artifacts (session-local, not tracked)**: `<session-files>\lifestyle-period-container-smoke.cjs` and `<session-files>\lifestyle-period-container-evidence.json`. The JSON contains only sanitized controls/check names, query dates/thresholds, coverage statuses, month arrays and counts. There is no synthetic screenshot being presented as real-stack proof.

**T047–T048 manifest**: `README.md`; feature `plan.md`, `tasks.md`, `quickstart.md`, `review-report.md`, `checklists/requirements.md`; appended sourced facts in gitignored `memory.md`; the two session artifacts above. No application source, dependency/lockfile, Compose or Dockerfile changes were required in this verification slice. Existing backend/frontend changes were preserved. No commit, staging, branch, push, PR, hook or governance operation occurred.

**Final checkpoint**: 48/48 tasks complete, zero pending. The earlier pending notices are historical handoff records, superseded by this execution. The failed merged-plan gate and documented timezone/responsive-nav limitations are unchanged.

## 19. Corrected target month and reference period - 2026-11-02

The current contract is one completed target month, compared with the mean over a separate contiguous reference period of 2–24 completed months. The reference defaults to the three calendar months immediately preceding the selected target. `threshold_percent` is a separate sensitivity input (default 20%, inclusive 1–100%).

The API uses `month` for the target and optional paired `reference_start` / `reference_end` for the inclusive reference range. Target selection must be no later than the API process current month; every reference month must precede target. A current-month selection returns insufficient history without reads or money (T052 handling below). Financial evaluation requires all evidence strictly before the current API month and reads exactly references plus target (3–25 snapshots). An older reference end does not cause intervening months or target−1 to be read. The response includes `window_months`, compatibility `evaluation_months=[month]`, dynamic `baseline_months`, one `comparison` per category, `is_above_threshold`, and suppression reason. There is no sustained-month verdict.

For total reference spend `T`, reference count `r`, target spend `S` and threshold `p`, the strict decision is `100*(r*S-T) > p*T`, with `T>0` and at least two distinct positive reference months. The response reports target minus reference mean; exact Decimal arithmetic decides the result before 28-digit explanation rounding. Latest MoM is null unless reference_end directly precedes target.

### Backend verification for corrected contract

From the repository root, with the worktree's existing virtual environment:

```powershell
$env:BILLS_CALC_LOG = '0'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONPATH = 'src'
.\.venv\Scripts\python.exe -m budget_api.tests.isolated_run src\budget_api\tests\bills\test_lifestyle_creep.py src\budget_api\tests\bills\test_lifestyle_creep_api.py
```

Result: **101 passed**, with one existing Starlette TestClient/httpx deprecation warning. A broader regression run covering lifestyle unit/API, CC history, runway merge, and sync history passed **264 tests** with the same warning. The tests use isolated synthetic storage only. No client tests/build, Docker, real financial data, `.env`, or `data/private/` access was performed for this backend correction. The following T051 result records the separate client work; previous section-18 client/runtime counts remain historical.

### T051 frontend implementation and verification

The standalone Lifestyle Creep tab now selects exactly one **Target month** and
an inclusive **Reference start** / **Reference end** range, with **Apply
comparison** applying all three month values atomically. The target defaults to
the latest completed browser-local month; the reference defaults to its prior
three months. The client sends explicit `month`, `reference_start`, and
`reference_end` with the visit-local applied threshold. Invalid drafts do not
fetch. The hook keys target, both references, and canonical threshold, retries
that exact selection, rejects malformed or mismatched response identity, and
ignores stale success/failure completions.

The card labels the target and reference span separately, displays exact
required evidence months (including a possibly separated target), and uses one
server-provided target-versus-reference-average comparison per category. It
shows **Above threshold** / **Below threshold**, suppression explanations, and
adjacent month-over-month only when supplied. No intervening months are implied
or required. Uncategorized samples remain separate. Privacy masks all money
without refetching; Bills remains free of detector UI and requests.

From `client`:

```powershell
pnpm exec vitest run src/api/__tests__/lifestyle-creep.test.ts src/lib/__tests__/lifestyle-creep.test.ts src/hooks/__tests__/useLifestyleCreep.test.ts src/components/bills/__tests__/LifestyleCreepCard.test.tsx src/pages/__tests__/LifestyleCreepPage.test.tsx src/tests/LifestyleCreepRoute.test.tsx src/tests/BillsPage.test.tsx src/components/bills/__tests__/privacy-masking.test.tsx
pnpm exec vitest run
pnpm build
```

From the repository root, after the documentation changes:

```powershell
$env:PYTHONPATH='src'
$env:BILLS_CALC_LOG='0'
uv run --no-sync --locked python -m pytest src/mom/tests/test_current_tree_containment.py src/mom/tests/test_lg002_identifier_containment.py -q
git --no-pager diff --check
```

| Check | Result |
| --- | --- |
| T051 focused feature, route, Bills, and privacy tests | **8 files, 139 passed** |
| T051 full client suite | **50 files, 551 passed** |
| Production build | **Passed**, `tsc -b` and Vite; 2611 modules transformed |
| Tracked-doc/identifier containment | **9 passed** |
| `git diff --check` | **Passed** |

Build emitted the existing mixed static/dynamic import warning for
`types/api.ts` and the existing large-chunk warning. No client dependency,
backend, container, Docker, browser, or real-data changes/checks were made for
T051. No amounts, financial identities, screenshots, or private paths were
recorded. At the T051 checkpoint, independent review T052 and the
coordinator-owned actual-container smoke T053 were still pending; their final
results are recorded below.

**T051 file manifest**: `README.md`; `client/src/api/lifestyle-creep.ts`,
`client/src/types/lifestyle-creep.ts`, `client/src/lib/lifestyle-creep.ts`,
`client/src/hooks/useLifestyleCreep.ts`,
`client/src/pages/LifestyleCreepPage.tsx`,
`client/src/components/bills/LifestyleCreepControls.tsx`,
`client/src/components/bills/LifestyleCreepCard.tsx`,
`client/src/components/bills/LifestyleCreepDetails.tsx`; their focused API,
helper, hook, card, and page tests plus `client/src/test/fixtures/lifestyle-creep.ts`
and `client/src/tests/LifestyleCreepRoute.test.tsx`; feature
`contracts/bills-card.md`, `tasks.md`, and `quickstart.md`; and a dated sourced
entry appended to `memory.md`. The pre-existing standalone tab, router, Bills
exclusion, backend implementation, and unrelated worktree edits were preserved.

### T052 month-boundary finding remediation — 2026-11-02

The reader previously trusted a saved `complete` status without checking the
API calendar. The builder classifies completion against acquisition start time,
not the detector's read-time clock. Simply relaxing target validation would
therefore allow open-month comparisons. The fix accepts current API-month
selection only for a controlled insufficient response, then independently
checks all required evidence before any snapshot access. No arbitrary saved
status can bypass that gate.

Fully validated current-month requests return 200/no-store,
`insufficient_history`, `partners=[]`, and a null-partner `partial_month` /
`open_month` issue. All selected dates/threshold metadata remain unchanged.
Future or malformed selections still return 400. If the API clock moved
backward after validation, open/future evidence blocks all reads and future
evidence carries `unavailable_history` / `future_month`.
After closure, stored partial evidence is still partial until re-synced.

No client selection/default/exclusion, request lifecycle, response shape, or
enum changed. The card's issue wording explains waiting for closure and its
evidence label now says **Required evidence months**, avoiding a false read
claim for this zero-read response.

**Red evidence:** the new browser-ahead regression failed as intended before
the service fix: **1 failed, 84 deselected** (expected 200, received 400).
The first expanded run then identified one stale exact future-month error
assertion (**282 passed, 1 failed**); the first four-file client run identified
one stale evidence-label assertion (**120 passed, 1 failed**). Both assertions
were updated to the corrected documented wording before the final runs.

**Final backend verification**, from repository root:

```powershell
$env:BILLS_CALC_LOG='0'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe -m budget_api.tests.isolated_run src/budget_api/tests/bills/test_lifestyle_creep.py src/budget_api/tests/bills/test_lifestyle_creep_api.py src/budget_api/tests/bills/test_cc_spend_history.py src/budget_api/tests/bills/test_lifestyle_creep_runway_merge.py src/budget_api/tests/test_sync_lifestyle_history.py -q --basetemp=.pytest_cache/t052-boundary-final-check
```

Result: **283 passed**; one existing Starlette TestClient/httpx deprecation
warning. Synthetic temporary storage only; private-file/network tripwires active.
Coverage includes ordinary and year-boundary targets; default and explicit
references; saved complete, partial, unavailable, and missing targets; zero
path resolution/history reads/calculation on open targets; clock recheck over
every evidence month; malformed current/future selection rejection; and retry
after closure without promoting saved partial history.

**Final focused client verification**, from `client`:

```powershell
pnpm exec vitest run src/api/__tests__/lifestyle-creep.test.ts src/lib/__tests__/lifestyle-creep.test.ts src/hooks/__tests__/useLifestyleCreep.test.ts src/components/bills/__tests__/LifestyleCreepCard.test.tsx src/pages/__tests__/LifestyleCreepPage.test.tsx src/tests/LifestyleCreepRoute.test.tsx src/tests/BillsPage.test.tsx src/components/bills/__tests__/privacy-masking.test.tsx
```

Result: **8 files, 140 passed**. Includes the no-money/no-conclusion/open-month
card response and preserved local-current exclusions, hook races, route,
Bills isolation and privacy checks. No full-client/build rerun is claimed.
No database migration, dependencies, Docker, real financial data, commit or
branch operation occurred during this remediation step. This records finding
remediation before independent approval; T052/T053 completion is recorded
below.

### T052/T053 final review and corrected-contract smoke — 2026-11-02

**T052 independent review**: An independent read-only review of the corrected
API/service/model, client controls/hook, tests and documentation passed with no
significant issues. The earlier review finding was that browser-local default
month could be current on the API clock, producing a boundary 400. The fix is
fail-closed: a request targeting the API current month returns 200
`insufficient_history` with no partner money and checks open/current evidence
before resolving any storage paths or reading snapshots. Future and malformed
selections remain 400. Targeted API tests cover current target and prove no
path resolution. The final relevant backend suite below passed 283 tests.

**Final corrected-contract test and build commands**:

From the repository root:

```powershell
$env:PYTHONPATH='src'
$env:BILLS_CALC_LOG='0'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
uv run --no-sync --locked python -m budget_api.tests.isolated_run src/budget_api/tests/bills/test_lifestyle_creep.py src/budget_api/tests/bills/test_lifestyle_creep_api.py src/budget_api/tests/bills/test_cc_spend_history.py src/budget_api/tests/bills/test_lifestyle_creep_runway_merge.py src/budget_api/tests/test_sync_lifestyle_history.py
```

Result: **283 passed**, one pre-existing Starlette TestClient/httpx
deprecation warning. The final focused client run passed **7 files / 139
tests**; the final full `pnpm exec vitest run` passed **50 files / 552 tests**.
`pnpm build` (`tsc -b && vite build`) passed, transforming 2611 modules. The
build retains existing Vite warnings about mixed static/dynamic import of
`types/api.ts` and a chunk over 500kB.

**T053 container commands** (run by the coordinator; not repeated for this
documentation update):

```powershell
$env:APP_PORT='8080'
docker compose -p pocket-smith-reports build api frontend
docker compose -p pocket-smith-reports up -d api frontend
```

Both images were built from this worktree. API and frontend were healthy, with
frontend at `127.0.0.1:8080`; the existing
`pocket-smith-reports_private-data` volume remained mounted. No sync, writes to
real data, shutdown or volume deletion occurred.

**Unmocked Chromium summary**: DNS was blocked except for `127.0.0.1`; browser
traffic was same-origin only. The direct `/lifestyle-creep` link and nav click
worked, with active navigation `aria-current=page`; the Bills card count was
zero. Controls were labeled Target month, Reference start/end and Threshold.
Defaults were target 2026-10, references 2026-07..09, threshold 20. The API
returned ready/200, echoed the selection and reported evidence Jul–Oct,
evaluation_count 1, two partners and 35 categories. A custom target 2026-09
with reference 2026-04..08 returned 200 `insufficient_history`, echoed the
selection and reported evidence Apr–Sep with evaluation_count 1 and no
category data; no stale/default result was shown. A reversed range set
`aria-invalid=true` and caused zero additional API calls. The Bills page made
no detector request. Combined browser errors, failed requests and external
origin requests were all zero. No amounts, partner labels, raw response
bodies or screenshots were captured.

The containment suite passed **9 tests** on the documentation state before
this update; it is rerun after these edits. T052/T053 are complete; the
corrected-contract task checkpoint is **53/53, zero pending**. Earlier
section-18 T047/T048 review and multi-month browser assertions remain
historical, not acceptance evidence for this corrected contract.

## 20. Visit-local category visibility — 2026-11-02

**Scope/status:** T054 implementation, T055 independent code-review **PASS**, and T056 frontend-container/browser acceptance are complete: **56/56 checked; zero pending**. Review provenance is the supplied independent code-review PASS in the final-verification handoff, not a second review performed by the final verifier. Prior section-19 results remain historical evidence for the corrected comparison contract, not browser verification of these new controls.

- Comparison rows now have **Hide** buttons with category title/ID accessible names. Hide removes exactly that stable partner/category pair's row and disclosure. Duplicate titles and the same category ID under another partner are independent.
- Each partner with categories has a view-only hidden count and **Show hidden categories** toggle (`aria-pressed`). Shown hidden rows have a **Hidden** badge and **Restore** action. **Restore all** restores only that partner, including the all-hidden case; true no-category history keeps its original empty message.
- `LifestyleCreepCard` owns an in-memory `Map<partner_id, Set<category_id>>` plus show-hidden partner IDs, outside result branches. Loading/errors, threshold changes, comparison changes and Retry preserve these choices; fresh visits reset them. No API/hook/type/backend, persistence, dependency, Bills, sync or monetary-privacy behavior changes.
- Hidden counts describe only the current view. An explicit note explains that hiding rows/details does not change the assessment across all covered categories. Server no-alert summaries still use the full response, never the filtered rows.
- Existing privacy formatting still masks shown hidden rows and all collapsed detail markup. Synthetic tests inspect that markup and assert no extra API requests for hide/show/restore.

### Local verification

Run from the assigned worktree only, using existing dependencies:

```powershell
Set-Location client
pnpm exec vitest run src\api\__tests__\lifestyle-creep.test.ts src\lib\__tests__\lifestyle-creep.test.ts src\hooks\__tests__\useLifestyleCreep.test.ts src\components\bills\__tests__\LifestyleCreepCard.test.tsx src\pages\__tests__\LifestyleCreepPage.test.tsx src\tests\LifestyleCreepRoute.test.tsx src\tests\BillsPage.test.tsx
pnpm exec vitest run
pnpm build
Set-Location ..
$env:PYTHONPATH = "src"
$env:BILLS_CALC_LOG = "0"
uv run --no-sync --locked python -m pytest src/mom/tests/test_current_tree_containment.py src/mom/tests/test_lg002_identifier_containment.py -q
git diff --check
```

Executed results: targeted **7 files / 145 tests passed**; full client **50 files / 558 tests passed** (six new page tests above the 552 baseline); `pnpm build` passed (2,611 modules transformed), with the existing mixed static/dynamic import and >500 kB chunk warnings. The first targeted run found one existing globally scoped status query ambiguous after adding per-partner hidden-count status; it was scoped to the unchanged partial-coverage message and the final runs above passed.

Post-documentation validation: the exact containment command above passed **9 tests**; `git diff --check` passed. No dependencies were installed or changed.

### T056 executed container/browser verification

Scope controls to `getByRole("region", { name: "<partner label> category comparisons" })`; then use `getByRole("button", { name: "Hide <category title> (ID <category ID>)" })`, **Show hidden categories**, **Restore ...**, and **Restore all**. Inspect the row via `getByRole("rowheader", { name: /<category ID>/ })` and the disclosure summary text `Target comparison: <category title> (ID <category ID>)`.

The implementation slice above did not access Docker/browser/real data. The separate final verification below did deploy the frontend and perform one read-only live structural check. No application changes were needed.

Before deployment, selected Docker metadata confirmed both containers belong to `pocket-smith-reports`, their Compose working-directory label matches the assigned worktree, and both were healthy. The API mounted the existing `pocket-smith-reports_private-data` named volume at `/app/data/private`; frontend had no mounts. No environment/secrets/private-file contents were inspected.

Executed from the assigned worktree:

```powershell
$env:APP_PORT = "8080"
docker compose -p pocket-smith-reports build frontend
if ($LASTEXITCODE -eq 0) { docker compose -p pocket-smith-reports up -d --no-deps frontend }
```

Build passed, including TypeScript/Vite (2,611 modules and the existing mixed-import/large-chunk warnings). Only frontend was recreated. Afterwards frontend and the unchanged API were both **running/healthy**, frontend bound to **127.0.0.1:8080**, and the same API volume remained mounted. API start time remained `2026-11-02T12:04:30.652591049Z`; recreated frontend start time was `2026-11-02T12:24:53.466829591Z`. No `down`, volume operations, API rebuild, sync or data writes were performed.

The final verifier ran existing Playwright/Chromium using session-only `lifestyle-visibility-final.cjs`; sanitized results are in session-only `lifestyle-visibility-final-evidence.json`. Neither file is a repository artifact. **67/67 assertions passed:**

- **58 synthetic assertions** against the deployed frontend at desktop **1440×1000** and mobile **390×844**. Catch-all interception was registered before navigation. Only same-origin static resources and the app document reached the frontend; detector responses were dynamically generated synthetic fixtures echoing the requested target/reference/threshold. The route-reentry check used a synthetic empty monthly-report list. Unexpected APIs/non-GET requests and external origins were blocked; Chromium DNS denied hosts other than `127.0.0.1`.
- Verified keyboard focus and Enter/Space activation; Hide removed both the row and its corresponding disclosure; hidden counts updated; duplicate titles and the same category ID under another partner stayed independent. Show hidden categories set `aria-pressed`, restored the row/disclosure with **Hidden** badge and **Restore** action. Restore and all-hidden **Restore all** recovered rows/disclosures and did not restore another partner's hidden row.
- Each visibility action and the privacy toggle caused **zero additional detector requests**. There were **6 synthetic detector requests total**: initial load, threshold change, changed target/reference selection, intentionally mismatched response, Retry, and route re-entry. The mismatched HTTP-200 synthetic selection exercised the application error branch without introducing a failed network request. Loading/error/Retry and successful selection/threshold fetches retained hidden/show choices; navigating away and back reset both visit-local choices while keeping global privacy active.
- Privacy assertions inspected actual rendered markup, including collapsed details: all **6 monetary table cells** and **18 disclosure monetary values** in the tested hidden-shown partner region were masked. The narrow table overflowed into its working horizontal scroller without that scroller exceeding the viewport.
- **9 unmocked structural-only assertions** on `/lifestyle-creep`: document **HTTP 200**, detector **HTTP 200**, state **ready**, one detector request; target/reference/threshold controls present, privacy enabled before navigation, **2** show-hidden controls, **2** partner regions, **2** tables, **35** rows and **37** disclosures. No live response body, monetary content, partner labels, screenshots or financial text was read/logged for assertions.
- In **both** contexts: **0** runtime/console errors, **0** failed requests, **0** external-origin requests and **0** unexpected routes. Browser contexts and the verifier's Chromium process were closed; actual Compose services were left running.

Harness-only initial attempts corrected the executable path and the accessible button name **Retry history**; these were not application defects or passing evidence. The successful final run above supersedes them. The existing **50 files / 558 frontend tests** were not rerun because implementation was unchanged; Bills no-detector behavior remains covered by the T054 targeted/full-suite results, not a newly claimed Bills browser check.

Final documentation manifest: `plan.md`, `tasks.md`, `quickstart.md`, `review-report.md`; a dated sourced fact was appended to existing ignored `memory.md`. No other source changes, dependencies, commits, branches or remote publication occurred in this verification slice.

Final validation after the status/evidence documentation edits: the exact `PYTHONPATH=src`, `BILLS_CALC_LOG=0`, `uv run --no-sync --locked python -m pytest` containment command above passed **9 tests in 1.12s**; `git diff --check` passed. The task-marker count was independently checked as **56/56**. Subsequent edits only record these results; containment and whitespace checks were repeated before handoff.

## 21. Shared economy: backend and persisted report-group evidence

### Delivered backend boundary

T057 adds opt-in report grouping. At this backend handoff, T058 client adoption,
T059 independent review and T060 container/browser verification were **pending**.
T058 completion is recorded in the frontend subsection below. No UI, dependency,
container, branch, commit or PR action occurred in this backend slice. Existing
uncommitted controls, visit-local visibility and prior documentation remain
preserved. No real financial records, existing generated reports or credentials
were read, and no real re-sync ran.

New builders write **schema 7** with explicit snapshot-level
`economy_spend_history`; the existing schema-6 outgoing CC blocks/fields are
unchanged. Old schemas cannot reconstruct report groups from outgoing card
spending. GET returns all three groups as insufficient with operational resync
guidance until each selected completed month has valid new evidence.
Acquisition remains in the existing explicit sync flow, with no new HTTP calls.

### Client/API handoff

Request the existing endpoint with `grouping=report`:

```text
GET /api/bills/lifestyle-creep?month=2026-10&reference_start=2026-07&reference_end=2026-09&threshold_percent=20&grouping=report
```

The target/reference/threshold request and echoed selection identity are
unchanged. Omission of `grouping` retains the exact outgoing-card `partners[]`
response. Report mode instead returns:

- `grouping: "report"`;
- `groups[]`, exactly ordered `shared`, `personal_partner_a`,
  `personal_partner_b`, including when insufficient;
- each group: `group_id`, `label`, `partner_id: string | null`,
  `partner_slot: "" | "a" | "b"`, `status`, `categories[]`,
  `uncategorized_samples[]`;
- category explanation shape unchanged except signed sample/baseline/spending
  amounts and additive `negative_baseline` suppression;
- file-window-wide `issues[]` with nullable `group_id`/`partner_id`;
- `history_guidance: string | null`, non-null when insufficient.

Use stable `group_id` + `category_id` for hiding/restore identity, not nullable
person ID or labels. Shared has null person ID and empty slot. Incomplete groups
with no valid saved metadata use neutral labels/null person IDs, never current
settings. Preserve target/reference/threshold response identity validation,
masking, loading/error/Retry behavior and request-free visit-local hiding.
All displayed monetary strings can be negative, including the reference mean
and target; baseline <= 0 suppresses the warning explicitly, not the amounts.
There is no sustained-growth/forecast/advice claim.

The authoritative DTOs are `ReportLifestyleCreepResponse`,
`ReportLifestyleGroup`, `ReportLifestyleCategory`, `SignedComparison` and
`SignedMonthlyAmount` in `models/lifestyle_creep.py`; see
`contracts/lifestyle-creep-api.md` for the complete wire contract and
`contracts/bills-history-v7.md` for persisted evidence and rollback.

### Reused accounting and function interfaces

| Interface | Responsibility |
|---|---|
| `prepare_transactions(month, transactions, excluded_account_ids=None) -> list[dict]` | Pure extraction of the existing report loader's month/account/category preparation; the file loader delegates to it unchanged. |
| `detailed_spending_groups(records, resolved_mapping) -> dict[str, list[dict]]` | Actual report section routing/category grouping, retaining category IDs/titles and constituent records. |
| `load_economy_context(month) -> EconomyContext` | Sync-only report input loading; inputs plus frozen excluded IDs. Missing/invalid context becomes unavailable evidence, never zero. |
| `build_economy_history(month, transactions, account_mappings, acquisition, context) -> EconomySpendHistory` | Same trusted full-range acquisition as CC history; signed exact report-population observations and versioned policy fingerprint. No report-file load or additional upstream fetch. |
| `build_bills_snapshot(..., acquisition=None, economy_context=None)` / `build_bills_chain(..., acquisitions=None, economy_context=None)` | Additive optional context; new schema-7 evidence uses the existing snapshot writer. |
| `evaluate_categories(months, histories, threshold, signed=False) -> (categories, uncategorized_samples)` | One generic exact comparison implementation; existing `evaluate_partner` wraps it for default CC responses. |
| `read_report_lifestyle_creep(selection) -> ReportLifestyleCreepResponse` | Read-only complete-window adapter; exactly selected 3–25 snapshot reads, no current config/raw/report/network/write/repair/sync. Open-month API clock guard reads zero files. |

Shared is **Home + Common only**, not the report's larger household composition
or the optional percentage settlement split. Personal grouping follows the
category section, not card owner. Both included checking/card payers contribute
paid minus received: refunds reduce spending and paired reimbursements cancel.
Trips, savings, income, excluded and CC-payment sections do not contribute.
Home transfers remain Home; Common/personal transfers route to excluded.
Savings account roles do not override the detailed category router; an included
Common-category record on a savings-role account is still Common, matching
reports. Parent remaps are resolved by `build_contract`, not a new classifier.

Evidence uses exact decimal sums of normalized source amounts rather than
floating presentation totals. Baseline T > 0 and two positive reference samples
are required before the exact strict inequality `100*(r*S-T) > p*T` can warn.
Zero T yields `zero_baseline`, negative T yields `negative_baseline`, and a
positive low-frequency baseline yields `low_frequency`. Negative target/change
remain valid. Percentages with a nonpositive denominator are null; division
rounding is explanatory only.

### Coverage decisions and limitations

- The scope fingerprints all owner/slot assignments, account inclusion,
  category sections, account roles, optional KPI mappings, category-parent
  relationships and versioned three-group/net policy. Labels/titles do not
  establish identity. All window scopes and saved person identities must match.
- Complete evidence requires a valid full-month acquisition begun after close.
  Valid empty acquisitions are zero only with valid classification inputs.
  Missing/empty mapping/catalog/owner context and invalid inputs fail closed.
- The existing reports do **not** filter pending transactions. To require
  posted evidence without silently changing reports or publishing a different
  population, the producer conservatively marks any acquired pending/unknown
  status unavailable. Fix source/configuration and explicitly re-sync; GET
  cannot resolve it. The original CC filter remains unchanged.
- The shared report context loader also validates optional settlement
  configuration. Invalid settlement configuration can therefore make history
  unavailable even though settlement percentages are not part of this grouping.
- Any incomplete/scope-inconsistent window member blocks **all three** groups.
  Corrupt evidence fails generically with 500, never partial money.
- No migration or real-data validation was performed. A later explicit re-sync
  is needed for report-mode history. An older backend limited to schema 6 may
  reject schema 7; roll back the client opt-in without reverting the updated
  reader if these snapshots already exist.

### Synthetic verification

Environment for all backend commands:

```powershell
$env:PYTHONPATH='src'
$env:BILLS_CALC_LOG='0'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
uv run --no-sync --locked python -m budget_api.tests.isolated_run src\budget_api\tests\bills src\budget_api\tests\test_sync.py src\budget_api\tests\test_sync_lifestyle_history.py src\budget_api\tests\test_sync_economy_history.py src\budget_api\tests\test_report_builder.py src\v4_pipeline\tests\test_accounting.py -q
uv run --no-sync --locked python -m budget_api.tests.isolated_run src\v4_pipeline\tests\test_data_loader.py -q
```

Final targeted result: **766 passed** (16.86s), plus **11 loader tests passed**
(1.35s); one pre-existing Starlette TestClient/httpx deprecation warning in the
expanded selection. No packages installed. Tests use the isolated bootstrap and
synthetic storage only.

Coverage includes actual report-builder totals and source category-ID parity;
Home/Common composition; opposite-payer personal categories; parent remaps;
refunds/net negatives/zero means/reimbursements; excluded accounts and actual
transfer/CC-payment/Trips/savings/income decisions; missing/invalid policy and
closed acquisition provenance; rename-independent scopes and every relevant
policy input; fixed group identities/unique categories; exact signed strict
threshold equality and suppression; old-schema insufficiency; same-scope
identity/category corruption; generic 500/no-store; pre-I/O query validation;
zero-read API clock guard; exactly 3/25 reads without config/scans/writes; and
the original CC/builder/sync suite.

Initial regression attempts found four coupled schema-6 marker assertions;
these now assert the intentional schema-7 producer without changing their
monetary expectations. One test-selector typo was corrected before the final
run. All final selected tests pass.

`python -m py_compile` passed for all ten changed backend source modules;
`git diff --check` passed. Documentation containment is recorded below after
the final amendment edits.

### Slice manifest

| Area | Files |
|---|---|
| Models/API | `src/budget_api/models/bills.py`, `models/lifestyle_creep.py`, `routers/bills.py` |
| History/evaluation/sync | `src/budget_api/services/economy_history.py` (new), `report_lifestyle_creep.py` (new), `lifestyle_creep.py`, `bills_builder.py`, `sync_runner.py` |
| Report reuse | `src/v4_pipeline/accounting.py`, `data_loader.py` |
| New synthetic tests | `src/budget_api/tests/bills/test_economy_history.py`, `test_report_lifestyle_creep.py`, `src/budget_api/tests/test_sync_economy_history.py` |
| Coupled schema assertions | `src/budget_api/tests/bills/test_builder.py`, `test_cc_spend_history.py`, `src/budget_api/tests/test_sync_lifestyle_history.py` |
| Feature documentation | `spec.md`, `plan.md`, `data-model.md`, `tasks.md`, `quickstart.md`, `contracts/lifestyle-creep-api.md`, `contracts/bills-history-v6.md`, `contracts/bills-history-v7.md` (new) |

No client/README edits were made by this slice; T058 owns UI adoption and its
related documentation. Previous source/document changes outside this manifest
were not reverted or represented as new backend work.

Final documentation containment:

```powershell
uv run --no-sync --locked python -m pytest src\mom\tests\test_current_tree_containment.py src\mom\tests\test_lg002_identifier_containment.py -q --basetemp=.pytest_cache\report-economy-containment
git --no-pager diff --check
```

Result: **9 passed** (0.96s); one non-blocking `asyncio_mode` configuration
warning because plugin autoload was disabled for the static-only run.
Whitespace check passed. Backend-handoff task markers were **57 complete / 60 total**,
with T058–T060 explicitly pending. This records backend verification only, not
client, independent-review or runtime acceptance of the new report grouping.

### T058 frontend adoption (2026-11-02)

**Delivered**: `/lifestyle-creep` now requests `grouping=report` on the existing
endpoint. It replaces the former outgoing-CC-owner presentation without a mode
toggle. Tables follow the exact API order: Shared economy (Home + Common only),
then personal A and B using saved configured labels. Included checking and card
spending uses paid minus received across both payers. Personal section placement
is report-classifier output, not payer ownership. Trips, savings, income,
excluded and credit-card payment sections are explicitly omitted. No client
category reclassification, merge, combined total or extra aggregation was added.

**Interface decisions**:

- `getEconomyLifestyleCreep(month, threshold, referenceStart, referenceEnd)`
  returns `ReportLifestyleCreepResponse` with `grouping=report` and
  `cache: "no-store"`. The existing `getLifestyleCreep` wrapper still omits grouping
  and returns the original CC response; existing direct API consumers are not
  reinterpreted. No unsafe response casts are used in production.
- The report DTO mirrors the backend group/category/issue members, signed decimal
  strings, nullable percentages, nullable person IDs and `history_guidance`.
  The hook validates echoed target/references/threshold, required sample window,
  report mode, exactly three ordered IDs and slots, null shared person identity,
  distinct nonempty personal identities when ready, unique category identities,
  and complete/no-money group coverage. Invalid/mixed identities are errors, not
  partial results. The request/stale-response key includes report mode and Retry
  generation. Old successes and errors cannot replace a newer selection.
- Every table and disclosure uses server samples/comparison/suppression/flags;
  formatting never decides a verdict. Signed refunds, negative target/change and
  negative reference means remain representable. Zero and negative means have
  distinct suppression messages; undefined growth says nonpositive reference
  baseline. Low-frequency text explicitly means fewer than two **positive**
  reference months. Uncategorized net samples remain separate inside their
  backend-assigned group, with a coverage note for positive or negative nonzero
  values. No uncategorized alert ID is invented.
- Hidden identity is `group_id` + `category_id`, independent of labels and nullable
  person IDs. Hide filters both rows and disclosures; show/restore and group-only
  Restore all preserve the original visit-local behavior and server assessment.
  Selection/loading/error/Retry and renamed labels/person IDs do not reset it.
  No visibility or privacy action fetches, writes storage, changes settings or
  starts sync. Monetary masking covers signed rows, shown-hidden rows, samples and
  collapsed/open details; percentages remain visible.
- Valid insufficient responses keep all three group headings with empty monetary
  state, not fake zero tables or a no-alert result. The UI shows source issues,
  `history_guidance` (or an explicit mapping/resync fallback), and the existing
  `/sync` link without automatic actions. Schema-6 or missing schema-7 evidence
  requires checking report mappings and explicitly re-syncing every selected
  completed reference/target month with a consistent configuration. GET/Retry
  cannot migrate, repair or infer it; pending/unknown acquired transactions remain
  conservatively unavailable. The API clock-boundary response remains fail-closed.

**Usage**: open the Lifestyle Creep tab; choose Target month, Reference start and
Reference end, then Apply comparison. Threshold applies separately. Inspect the
shared table first and the two personal tables next. Use Hide/Show hidden
categories/Restore/Restore all independently per group; Hide amounts still masks
all money. Retry history repeats the applied comparison rather than drafts.
Bills remains detector-free and sends neither the report nor CC request.

#### Frontend synthetic verification

From `client`:

```powershell
pnpm exec vitest run src\api\__tests__\lifestyle-creep.test.ts src\hooks\__tests__\useLifestyleCreep.test.ts src\components\bills\__tests__\LifestyleCreepCard.test.tsx src\pages\__tests__\LifestyleCreepPage.test.tsx src\lib\__tests__\lifestyle-creep.test.ts src\tests\LifestyleCreepRoute.test.tsx src\tests\BillsPage.test.tsx --reporter=dot
pnpm test --reporter=dot
pnpm build
```

Final focused result: **7 files / 166 tests passed** (8.82s after the final copy check).
Final full result: **50 files / 579 tests passed** (29.25s).
Production **TypeScript + Vite build passed**, **2611 modules** transformed
(11.87s final Vite build). Existing mixed static/dynamic import and >500 kB chunk
warnings remain. Full tests emitted existing `act(...)` warnings in MegaReports
and GraphView tests; there were no failures. An initial build caught the new
fixture inheriting old issue types; it was corrected to emit explicit report
`issues: []` and all final gates passed. No dependencies were installed.

Coverage includes three-table order, configured labels, Home/Common rows in shared
without personal duplicates, server-assigned categories regardless of payer-like
person IDs, signed refunds/negative means and server outcomes, zero/negative/
low-frequency suppression, all three legacy/resync headings without fake money,
independent group hiding, selection/threshold retention, fresh-visit reset,
stale successes/failures and same-selection Retry races, malformed group identity/
coverage rejection, report query serialization/no-store and original CC wrapper
compatibility, signed privacy including shown-hidden/collapsed details, real route
integration, and no detector requests from Bills.

#### Synthetic browser handoff for T060 (not executed by T058)

Tracked fixtures are `client/src/test/fixtures/lifestyle-creep.ts`:

- `economyFixture()` returns report mode for target `2026-10`, references
  `2026-07` through `2026-09`, threshold `"20"`. Shared has category IDs `920001`
  (Home category) and `920002` (Common category), each with reference/target
  samples `"20"` and no warning. Personal A has `910001` (Category A), samples
  `"100", "100", "130", "140"`, mean `"110"` and the server warning. Personal B
  has `930001` (Category B), constant `"20"` samples and no warning. Labels are
  neutral synthetic Partner A/B, not production names.
- `economyPeriodFixture(start, end, threshold, target)` supplies valid arbitrary
  selected periods for mocks. The original `lifestyleFixture()` and
  `lifestylePeriodFixture()` remain CC-compatible fixtures.
- `insufficientEconomyFixture()` returns all three insufficient groups, null
  personal IDs, empty category/uncategorized arrays, a `legacy_history` issue and
  mapping/resync guidance. Do not populate those arrays with zeros.
- The signed card test sets A's first sample to `"-65"`, target to `"-43"`,
  change to `"-153"`, growth to `"-139.090909"` and server flag false. Negative
  baseline cases explicitly use `negative_baseline` with null growth; hook tests
  also accept signed samples and preserve a true server flag beside displayed
  growth equal to the threshold. Copy these synthetic values into a future
  browser mock; do not infer verdicts in the browser.
- Identical IDs/titles/labels across group namespaces are deliberately tested
  directly at the component boundary. The valid API model forbids categories
  spanning report groups and the hook rejects that wire corruption. A browser
  mock must instead use unique valid IDs while checking group-isolated hiding.

Stable selectors: route `/lifestyle-creep`; region **Lifestyle creep detector**,
wait for `aria-busy="false"` after the mocked response; group sections
`[data-group-id="shared"]`, `[data-group-id="personal_partner_a"]`,
`[data-group-id="personal_partner_b"]`; each section's semantic table is named
`{saved label} target category comparisons`. Scope Hide/Restore by group plus
category ID (for example **Hide Category A (ID 910001)**), and scope **Show hidden
categories** / **Restore all** to that group. Controls retain **Target month**,
**Reference start**, **Reference end**, **Apply comparison**, **Apply threshold**
and **Retry history**. Install synthetic mocks for the report request and every
adjacent app-shell route **before navigation**; block unexpected routes rather
than allowing live API passthrough. No browser/container was started by T058.

#### T058 slice manifest and remaining work

| Area | Files updated by this frontend slice |
|---|---|
| Client contract/read/evaluation presentation | `client/src/types/lifestyle-creep.ts`, `api/lifestyle-creep.ts`, `hooks/useLifestyleCreep.ts`, `lib/lifestyle-creep.ts` |
| Three-group UI | `client/src/components/bills/LifestyleCreepCard.tsx`, `LifestyleCreepDetails.tsx` |
| Synthetic evidence | `client/src/test/fixtures/lifestyle-creep.ts`, `api/__tests__/lifestyle-creep.test.ts`, `hooks/__tests__/useLifestyleCreep.test.ts`, `lib/__tests__/lifestyle-creep.test.ts`, `components/bills/__tests__/LifestyleCreepCard.test.tsx`, `pages/__tests__/LifestyleCreepPage.test.tsx`, `tests/LifestyleCreepRoute.test.tsx`, `tests/BillsPage.test.tsx` |
| Documentation | `README.md`, feature `spec.md`, `plan.md`, `tasks.md`, `contracts/bills-card.md`, `quickstart.md`; sourced fact appended to ignored `memory.md` |

Historical T058 handoff task markers: **58 complete / 60 total**. **T059 independent review** and
**T060 owned container/browser deployment verification** were pending then.
Historical sections 19–20 and their review/browser results are preserved, not
relabelled as report-group acceptance. Backend T057's **766 + 11** synthetic tests
were not rerun or changed. No branch/commit/PR, Docker, nested agent, dependency,
real-data/credential access, application storage read/write or sync action occurred.
Existing unrelated uncommitted changes were retained.

Final documentation containment from the repository root:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
uv run --no-sync --locked python -m pytest src\mom\tests\test_current_tree_containment.py src\mom\tests\test_lg002_identifier_containment.py -q --basetemp=.pytest_cache\report-economy-client-containment
git --no-pager diff --check
```

Result: **9 passed**; one non-blocking `asyncio_mode` configuration warning with
plugin autoload disabled. Whitespace check passed. Task-marker check confirmed
**58 checked / 2 pending / 60 total**. The frontend source, tests, production
build and documentation were ready for T059, not a claim at that historical
boundary that review or runtime deployment had already passed.

### T059–T060 final report-group acceptance (2026-11-02)

**Current result: 60/60 tasks checked; zero pending.** T059 independent,
read-only review **PASS, no significant issues** was supplied in the final
verification handoff. The final verifier did not rerun or impersonate that
independent review. The failed merged-plan gate remains unchanged.

#### Actual deployment and preserved storage

Before any operation, targeted `docker inspect --format` fields verified the
two containers belonged to the current worktree/Compose file and project
`pocket-smith-reports`, frontend port `127.0.0.1:8080`, and API volume
`pocket-smith-reports_private-data` mounted at `/app/data/private`.
No container Env, credentials or volume contents were inspected.

```powershell
$env:APP_PORT='8080'
docker compose --env-file NUL -p pocket-smith-reports build api frontend
if ($LASTEXITCODE -eq 0) {
    docker compose --env-file NUL -p pocket-smith-reports up -d api frontend
}
```

Both image builds and the dependent update **passed**. `--env-file NUL` avoids
reading a local environment file. API health was awaited before frontend start.
The image's TypeScript/Vite production build passed with **2611 modules** and
the existing static/dynamic import and chunk-size warnings. Dockerfile dependency
steps were the existing frozen build, not a host dependency or manifest change.
Final targeted service health and HTTP checks passed; the API retains the exact
same named-volume mount and frontend retains no mounts. No down, prune, storage
rewrite, live sync or data repair was performed. Both services remain running.

#### Browser commands and evidence

From the current worktree, using only the already-installed Playwright and
Chromium listed in the verification handoff:

```powershell
$sessionFiles = Join-Path $HOME '.copilot\session-state\49060a89-e541-4878-82f8-220257a08098\files'
node (Join-Path $sessionFiles 'lifestyle-report-final.cjs')
```

All fixtures and stored evidence use neutral synthetic labels only.
Session-only artifacts:

- `files/lifestyle-report-final.cjs` — reproducible verification harness.
- `files/lifestyle-report-final-evidence.json` — sanitized **PASS**, exact named
  assertions and synthetic request parameters; no live bodies or financial data.

**68/68 assertions passed: 57 synthetic + 11 live**, with **14 synthetic detector
requests and one unmocked detector request** in the final run. Each context
installed interception before navigation, blocked service workers, non-GET
requests, unexpected API routes and external origins. Chromium used
`--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1`. Synthetic app-shell,
Bills and runway responses were mocked too; no API passthrough was allowed in
that context. The separate live context supplied **no mock responses**, allowing
only the real detector GET and local document/assets. Every settled result
waited for `aria-busy=false`, not merely network idle.

Synthetic assertions cover:

- Exact shared, `personal_partner_a`, `personal_partner_b` order, three tables,
  configured neutral labels, Home/Common fixture rows only in shared, and
  server-assigned personal categories despite deliberately opposite payer-like
  identities. Fixture responses use the tracked `economyPeriodFixture` through
  an in-memory TypeScript transpiler and echo the requested target, both reference
  bounds and threshold. No new package was needed.
- Signed negative target/reference/change and samples, negative-baseline
  suppression, negative uncategorized samples, and masking of **15 table money
  cells and all monetary detail values**, both open/collapsed and shown-hidden.
  Percentages remain visible.
- Keyboard Hide, removal of matching rows and disclosures, independent group
  counts/show-hidden choices, Restore all without restoring another group,
  zero fetches for visibility/privacy actions, and fresh-visit reset.
- Target/reference drafts apply together; threshold applies separately with one
  fetch. Hidden state survives loading, selection, threshold, malformed evidence,
  Retry and insufficient-history recovery. Delayed stale valid and invalid
  responses cannot replace the newest result or introduce its error.
- Wrong evidence months and duplicate IDs across groups fail closed without a
  CC fallback; every detector request explicitly uses `grouping=report`.
  The wire contract forbids a category ID spanning report groups. Therefore
  identical-ID isolation is tested at the **component boundary**, not by passing
  an invalid browser DTO through the hook.
- Missing schema-7 history shows all three insufficient group headings, explicit
  mapping/resync guidance and no money tables/details or fake-ready conclusion.
  Bills remains detector-free and sends zero report/CC detector requests.
  Mobile tables retain their own horizontally scrollable container.

The existing identical-ID/title/label component-boundary regression was rerun:

```powershell
Set-Location client
pnpm exec vitest run src\components\bills\__tests__\LifestyleCreepCard.test.tsx -t 'isolates visibility by stable group ID' --reporter=dot
```

Result: **1 passed, 16 skipped**, one file. This explicitly verifies the same
category ID across all three component group namespaces, independently hidden,
shown and restored. Earlier full suites were not unnecessarily rerun: the T057
baseline remains **766 backend + 11 loader tests**; T058 remains **166 focused /
579 full client tests**, with a passing production build.

The live browser returned document/API **200**, `grouping=report`,
`status=insufficient_history`, target `2026-10`, reference `2026-07`–`2026-09`,
**four `legacy_history` issues**, exactly three stable group IDs/headings and
**zero monetary tables/details**. Selection/threshold controls and pre-navigation
privacy were present. This is the expected honest outcome for old evidence,
not ready-state acceptance using real financial records. Check report mappings,
then explicitly resync all selected completed months under one consistent
configuration to acquire schema-7 report-group history. Reading/Retry cannot
upgrade schema 6. **No sync was started.**

Both contexts recorded **zero runtime/console errors, failed requests, external
requests, unexpected routes and write requests**. No live screenshots, traces,
HAR, labels, identities, category data or amounts were captured or logged.
Only whitelisted status/group IDs/issue codes/counts/months were retained from
the live response, in memory before sanitized evidence serialization. No direct
`.env`, private-data, main or sibling worktree reads occurred.

One initial harness assertion checked whole-page mobile width and failed on the
already-documented responsive navigation limitation (section 16). It was narrowed
to the relevant table scroll container; no application change or whole-page
responsive fix is claimed. Final runs passed. All owned browser contexts and
Chromium processes were closed; no helper server was started.

#### Final containment, whitespace and slice manifest

```powershell
$env:PYTHONPATH='src'
$env:BILLS_CALC_LOG='0'
uv run --no-sync --locked python -m pytest src\mom\tests\test_current_tree_containment.py src\mom\tests\test_lg002_identifier_containment.py -q
git --no-pager diff --check
```

Containment: **9 passed**. Whitespace: **PASS**. Final marker count:
**60 checked / 0 unchecked / 60 total**.

| Final verification slice | Files/artifacts |
|---|---|
| Current status and durable verification | `README.md`; feature `plan.md`, `tasks.md`, `quickstart.md`, `review-report.md` |
| Local durable memory | Dated, sourced high-confidence fact appended to ignored `memory.md` |
| Session-only browser evidence | `files/lifestyle-report-final.cjs`, `files/lifestyle-report-final-evidence.json` |
| Implementation changes by verifier | None; all existing uncommitted source/test/document changes preserved |

No branch, commit, PR, nested agent, host dependency change or unchanged full-suite
rerun occurred. There is no unresolved implementation task in this amendment.
User-run resync for legacy history and the previously recorded limitations remain
operational constraints, not evidence that current history is ready.

## 22. Category usage graph - 2026-11-02

Scope (T061): each expanded **Target comparison** disclosure in the shared Home+Common and both personal report-grouped tables shows a client-only usage graph for that category's selected evidence (the exact reference months followed by the selected target). The API, request count, the static target-vs-reference-average comparison, the applied threshold and the server verdict are unchanged; the graph is a separate descriptive metric.

Architecture:

- `client/src/lib/lifestyle-trend.ts` - pure exact-decimal helper `lifestyleTrend(samples, { month })` returning `ready` rows/points or `invalid` (bad decimal, duplicate or non-calendar month).
- `client/src/components/bills/LifestyleTrendChart.tsx` - existing Recharts `ComposedChart` inside the shadcn `ChartContainer` (no new dependency): solid usage line, dashed trailing-average line, triangle markers for above-average months, hollow square for the selected target, `y=0` reference line when values are negative, legend outside the colour cue, figcaption summary and a "<category> graph data" table.
- `LifestyleCreepDetails.tsx` - the graph mounts only while its `<details>` is open (`onToggle`), so collapsed categories render no chart; hiding a category unmounts it.

Average rule: label "Trailing average (up to 3 prior months)". For month M it averages up to three immediately preceding consecutive calendar months present in the displayed evidence (month/year rollover handled), excluding M. At least two such months are required; otherwise no average and no marker (so the first two evidence months never have one). A month is marked above only when usage is strictly greater than that average, compared exactly (`amount x n > sum`), including zero and negative values; equality is not above. This is not the applied threshold, not the server verdict and not a forecast.

Gaps: when the target is not adjacent to the last reference month, one gap row (`...` tick) with null values is inserted and both lines use `connectNulls={false}`, so the usage line breaks. Missing months are never zero-filled or interpolated, and a month after a gap has no trailing average. Precision: the table and markers stay exact; if a value cannot be plotted safely (non-finite, beyond `Number.MAX_SAFE_INTEGER`, or underflowing to zero) the chart is replaced by a visible "too large or too precise to plot" status.

Privacy and accessibility: with Hide amounts on, the SVG is replaced by a masked `role="img"` placeholder (no ticks, coordinates or tooltips), table money shows `****` while months and status stay visible, the disclosure stays open and no request is made. The chart SVG is `aria-hidden`; the figcaption summary, explanations, legend and data table are the text alternative, and above-average status is text plus a triangle shape, not colour alone.

Verification (synthetic data only):

- `pnpm exec vitest run` affected: helper 19, chart component 5, page file 23 (+2); affected 9 files / 183 tests passed.
- Full frontend `pnpm exec vitest run`: 52 files / 605 tests passed (previous 50 / 579). `pnpm build`: passed (existing chunk-size warning only).
- Containment (`PYTHONPATH=src BILLS_CALC_LOG=0 uv run --no-sync --locked python -m pytest src/mom/tests/test_current_tree_containment.py src/mom/tests/test_lg002_identifier_containment.py -q`): 9 passed. `git diff --check`: clean. Backend unchanged.

T063 synthetic browser handoff: install synthetic route mocks (modelled on `economyPeriodFixture`, `grouping=report`) plus app-shell requests before navigation. Cases: default references 2026-07..2026-09 with target 2026-10; gap 2026-04..2026-07 to 2026-10; 24 references; refunds/negative values; one huge value. Selectors: region "Lifestyle creep detector", group regions "<label> category comparisons", summary "Target comparison: ...", `figure[data-lifestyle-trend]`, `[data-testid=lifestyle-trend-chart] svg.recharts-surface`, `[data-trend-month] [data-trend-marker=usage|above|average|target]`, `ul[aria-label="Graph legend"]`, table "<category> graph data" rows `[data-trend-row]`. Check real month tick labels (jsdom does not lay them out), tooltip content and masking, ~390px mobile width, and that toggling Hide amounts issues no requests.

Slice manifest: new `client/src/lib/lifestyle-trend.ts`, `client/src/components/bills/LifestyleTrendChart.tsx`, `client/src/lib/__tests__/lifestyle-trend.test.ts`, `client/src/components/bills/__tests__/LifestyleTrendChart.test.tsx`; modified `client/src/components/bills/LifestyleCreepDetails.tsx`, `client/src/pages/__tests__/LifestyleCreepPage.test.tsx`, `README.md`, and this feature's `spec.md`, `plan.md`, `tasks.md`, `contracts/bills-card.md`, `quickstart.md`.

### T062 review and T063 final acceptance

**T062 provenance:** the final-verification assignment supplied independent review
**PASS, no significant issues** for the T061 implementation. The deployment
verifier did not launch another reviewer or present browser checks as independent
code review.

**T063 verdict: PASS; 63/63 tasks checked, zero pending.** Ownership was checked
through selected Compose labels before acting; both services belonged to the
assigned worktree and project `pocket-smith-reports`. With `APP_PORT=8080`, only
the frontend was rebuilt and recreated:

```powershell
$env:APP_PORT = '8080'
docker compose -p pocket-smith-reports build frontend
if ($LASTEXITCODE -eq 0) {
    docker compose -p pocket-smith-reports up -d --no-deps frontend
}
```

The image build ran TypeScript and Vite successfully (2613 modules; existing
mixed-import and >500kB chunk warnings). The API container and image identities
matched before/after; its `pocket-smith-reports_private-data` named volume stayed
mounted at `/app/data/private`. Both services were running/healthy after
verification. No `down`, prune, sync, private-data modification or API recreation
was performed. The actual stack remains running at `127.0.0.1:8080`.

The session-only `files/lifestyle-trend-final.cjs` uses installed Playwright and
TypeScript without installing packages. It transpiles the existing synthetic
fixture helpers in memory. All API routes are intercepted **before** synthetic
navigation; selection/threshold/report grouping are dynamically echoed and
unexpected requests or external origins are blocked. Chromium also blocks DNS
except `127.0.0.1`. Fixed browser time makes default dates deterministic.

**339/339 browser assertions passed: 333 synthetic, 6 separate live structural-only.**
The nine synthetic scenarios cover:

- References `[100,100,100]`, target `150`: two prior-evidence average bars,
  equality unmarked, target triangle plus its separate square, and source-month
  table membership excluding the current target.
- The two-reference minimum; a nonadjacent target with a real two-subpath SVG
  usage line, visible ellipsis tick and no target average; and all 24 references
  plus target, with 23 averages/above markers and the final three-month mean.
- Signed `[-50,0,-10,-20]` with an actual zero reference line, negative mean,
  strict equality and signed tooltip; all-zero usage without above markers.
- Values just above and below the **unrounded** one-third mean, proving exact
  marker decisions despite equal displayed money; and a huge-value guard that
  replaces the plot with an explicit status instead of drawing an inaccurate
  number.
- Keyboard open/collapse with lazy mount/unmount, real SVG month tick labels,
  actual pointer-triggered tooltips with usage/average/status, target distinction,
  accessible caption/legend/table and graphs opening in all three report groups.
- Hide amounts while open: no chart SVG, coordinates, marker nodes or tooltip;
  accessible masked placeholder and `****` table; no raw currency in monetary
  markup/ARIA/title, including collapsed category details. Show restores the plot
  without closing the disclosure or making any API request.
- Category Hide removes its row, disclosure and graph; Show hidden/Restore
  recovers the collapsed category and it can be reopened without requests.
- Desktop and 390px viewport: card/graph stay within the viewport, actual tick
  labels survive resize, table overflow stays local and a pointer tooltip still
  works. Pre-existing outer navigation overflow is outside this amendment.

Table assertions compare the actual source-month values using the application's
existing **rounded whole-kr presentation**. They do not claim that every decimal
digit is printed: exact sum/count comparison is verified by marker status and
the explicit prior-month lists; graph coordinates are only the numeric plotting
layer. No formatter behavior was changed.

Exactly 12 synthetic detector GETs occurred (nine route entries plus three
explicit selection applications); graph/privacy/category actions added none.
Synthetic and live contexts each recorded **zero** console errors, page errors,
failed requests, unexpected routes and external requests; synthetic writes were
also zero.

The separate **unmocked** context enabled privacy before navigation and allowed
only the read-only report GET. Document and API returned HTTP 200; whitelisted
metadata was `status=ready`, `grouping=report`, three groups. Structurally there
were three group regions, 37 disclosures and zero mounted graphs. This is a new
observation, not a rewrite of section 21's earlier insufficient-history result:
the verifier did not sync or repair history and did not open a live graph.
Consequently graph behavior is evidenced by synthetic browser cases, **not**
real-data chart inspection. No live DOM text, monetary values, identities, raw
bodies, screenshots, traces or HAR were persisted.

Harness-only corrections before the final clean run: production Recharts puts
text in `.recharts-xAxis-tick-labels`, separate from axis tick-line groups;
privacy assertions must not treat the legitimate threshold bound `100` as money;
category selectors must exclude the uncategorized disclosure; tooltips need
on-screen SVG coordinates after resize; mocked decimals must follow the API's
canonical fixed-point grammar; request totals must be asserted after all cases.
These failures were not counted as passes. No application change was needed.

After documentation updates, rerun:

```powershell
$env:PYTHONPATH = 'src'
$env:BILLS_CALC_LOG = '0'
uv run --no-sync --locked python -m pytest src\mom\tests\test_current_tree_containment.py src\mom\tests\test_lg002_identifier_containment.py -q
git diff --check
```

Containment passed **9 tests**; `git diff --check` passed. Unchanged application
full suites were not rerun: the T061 baseline above remains 52 files / 605 tests,
with 183 targeted tests. No host dependency, branch, commit, PR or nested agent.

Final verification manifest:

| Surface | Evidence |
|---|---|
| Current tracked status | This section, `plan.md`, `tasks.md`, `review-report.md`, README |
| Session-only harness | `files/lifestyle-trend-final.cjs` |
| Sanitized assertion evidence | `files/lifestyle-trend-final-evidence.json` |
| Synthetic-only screenshots | `files/lifestyle-trend-desktop-synthetic.png`, `files/lifestyle-trend-mobile-synthetic.png` |
| Durable local memory | Dated, sourced fact appended to ignored `memory.md` |
| Application fixes by verifier | None; pre-existing uncommitted changes retained |

The verifier's browser contexts/process were closed. Only the actual Compose
stack remains running.
