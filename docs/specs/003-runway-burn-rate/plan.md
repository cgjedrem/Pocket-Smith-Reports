# Implementation Plan: Runway & Burn Rate

**Branch**: Existing app-managed worktree branch; unchanged.
**Date**: 2026-10-31 | **Spec**: [spec.md](spec.md)
**Input**: `docs/specs/003-runway-burn-rate/spec.md`
**Status**: Backend and frontend implemented and locally validated under direct user continuation.
Merged-plan gate checked and **NOT passed** (coordinator-reported check);
constitution dependency discrepancy remains recorded, not a passed gate.

## Local implementation authorization — 2026-10-31

The coordinator checked the mandatory merged-plan gate and reported it did not
pass. The latest direct user instruction explicitly requested continuing local
implementation rather than stopping at that planning gate. This is not a claim
that `--skip-review` was supplied, that review passed, or that artifacts were
published. Gate configuration stays unchanged. No branch changes, commits, push,
PR, or publication to force the gate. Historical planning-only statements below
describe the earlier pass, not the current execution authorization.

The backend pass generated `tasks.md` and implemented/validated the backend.
The subsequent direct frontend instruction authorized completing runway frontend
and documentation autonomously in this same worktree, without subagents or
publication. Frontend implementation, mocked tests/build, and synthetic Chromium
checks are now complete. QA approval, human comprehension, and integrated
backend/browser performance remain handoff work. Optional commit, context-update,
and bugfix hooks are skipped. No gate configuration changed.

### Constitution scope disposition

The pre-existing dependency declarations differ from constitution 1.0.2.
Runway introduces no dependencies and requires no pin change. Incidental package
downgrades or constitutional amendments would be unrelated repairs; leave both
unchanged and report the discrepancy rather than claim full constitution
compliance. This bounded implementation does not waive the merge/review gate.

## Summary

Add a small Runway & Burn Rate panel and explicit liquid-account settings to
Bills. Calculate selected **current recorded signed balances / average monthly
recorded spending (gross burn)** per stable account owner and once for the
household. Use the previous three completed server-local months, at least two
usable observations, and one common month set. No income/refund netting, future
income, forecasts, historical runway, fair-share allocation, or financial advice.

Use three new local-only endpoints and a separate `runway_config.json`. Derive
spending from validated raw transactions, never from legacy Bills fallback zeros,
projected savings, or frontend mock stores. Return explicit availability,
exclusions, coverage, currency, and freshness evidence. A snapshot-independent
client panel remains usable even when the current Bills snapshot is missing.

Research decisions are in [research.md](research.md); exact entities and invariants
in [data-model.md](data-model.md); wire contract in
[contracts/runway-api.md](contracts/runway-api.md). Backend implementation is
complete locally, as is frontend implementation; QA remains in [tasks.md](tasks.md).

## Technical Context

**Language/Version**: Python >=3.13; TypeScript 5, React 19.

**Primary Dependencies**: Existing FastAPI/Pydantic, React/Vite 6, Tailwind 4,
Radix primitives. Current `pyproject.toml` declares FastAPI `>=0.140,<0.142`,
uvicorn `>=0.51,<0.54`, Pydantic `>=2`, httpx, WeasyPrint `>=70,<71`,
pypdf `>=6.16.1,<6.19`. These are declaration facts, not verification of the
installed environment or approval of constitution drift. No dependency changes.

**Storage**: Existing atomic JSON file storage; one new settings file resolved
from `storage.PRIVATE_DATA_DIR` at runtime. No database, migrations, materialized
runway result, scheduler, source rewrites, or sync modification.

**Testing**: pytest with new colocated, isolated runway unit/API tests;
Vitest/Testing Library for hook, panel, settings, privacy, and Bills integration.
Synthetic browser acceptance remains separate from automated tests.

**Target Platform**: Existing local-first FastAPI service and Vite browser SPA;
Windows PowerShell development; Windows/Ubuntu Python 3.13 verification.

**Project Type**: Existing Python API + React web application; preserve layers.

**Performance Goals**: SC-005: visible result or explicit unavailable state within
two seconds for 10,000 transactions across three months and 20 mapped accounts,
under a recorded local synthetic acceptance environment. Linear transaction
passes plus bounded source re-read; no network calls or persistent cache.

**Constraints**: No real financial data, `.env`, main checkout, Docker, live API
or existing stack contact/start, commits, push, PR, or branch changes. A temporary
static synthetic preview on loopback 5203 was explicitly authorized for frontend
verification and stopped afterward; no backend server was started. Client package manager
is exactly `pnpm@10.30.3`; no new dependencies. Both new paths join no-store.
The opt-in isolated test runner blocks private fallback/network before collection
and imports, including guarded subprocesses; see quickstart for proof.

**Scale/Scope**: One local household's configured owners; up to ten eligible
reserve accounts in selection usability exercise. Feature 003 only. Debt/assets,
lifestyle creep, exports, old Bills math, and unrelated settings stay untouched.

## Constitution Check — historical planning assessment

*Required pre-research assessment and post-design re-check; constitution 1.0.2.*

**Overall: ERROR / BLOCKED, not waived.** The baseline dependency discrepancy
below prevents claiming a passed gate. Per this planning-only request, these
documents record a bounded proposed design and the blocker; they are not a
successful gate transition. No downstream execution is authorized by this plan.

| Gate | Pre-research assessment | Post-design assessment |
|---|---|---|
| I — Synthetic-only/private data | Pass for this pass: memory, report, and source text only; protected data never opened. | Design conforms: deterministic fixtures, neutral labels, no financial payload logging; test isolation required before execution. |
| II — Fail closed | Report/sync builders stay unchanged. Spec explicitly permits qualified positive recorded history, not partial report publication. | Design conforms: invalid/known partial months excluded globally; unproven zeros rejected; no fallback records or invented balances; all limitations exposed. This does not relax pipeline rules. |
| III — Atomic/staged publication | No HTML/PDF publication proposed. | N/A to report publication; selection uses existing atomic replace, no paired artifacts. |
| IV / Technical Constraints — Python and dependency pins | **ERROR:** constitution requires FastAPI 0.140.x, uvicorn `<0.52`, WeasyPrint `==69.0`, pypdf `==6.14.2`; current declarations differ (above). | **ERROR unchanged:** no dependency edits or silent constitutional amendment. Coordinator must reconcile via the governed process before claiming this gate passes. Installed pins were not inspected. |
| V — Hardened PocketSmith client | No new integration or credential access. | Design conforms: no PocketSmith, sync, permissions, or network in any runway route. |
| VI — Layers/local-first | Existing Python router/service/model structure retained. | Design conforms; one router delegates validation/calculation to service/models. 400 `{detail}` remains standard. No CORS expansion or production exposure. |
| VII — React/pnpm | `client/package.json` verifies React/Vite, pnpm 10.30.3 pin; the constitution's missing-pin note is stale. No lint script exists. | Design conforms to Vite exception expressly stated in Principle VII. Build/test planned. Lint remains the documented baseline pending gate, not a newly invented command. |
| VIII — Colocated tests/merge gates | Tests required for implementation, but user forbids writing/running them in this pass. | Verification designed, **not run**. Full regression blocked until global temp isolation is verified. Dual-OS and renderer split remain required. |
| IX — PowerShell | Commands use feature override in each process; no branch mutation. | Pass for planning commands; future commands in quickstart use PowerShell-safe syntax. |
| Workflow/review | Actual skill and central hooks inspected. No mandatory central before-plan hook. | **Pending:** mandatory `before_tasks` plan-review gate. No publication, waiver, tasks, or implementation. |

The constitution's old CORS-port list also omits the explicit 5200/5201 origins
now in `main.py`; the local-only principle still holds. Do not expand it for this
feature. Browser evidence can use intercepted same-origin requests without a
production CORS edit.

### Historical planning hook and setup record

- Ran required `.specify/scripts/powershell/setup-plan.ps1 -Json` from this root
  with `SPECIFY_FEATURE_DIRECTORY=docs\specs\003-runway-burn-rate`.
- Parsed `FEATURE_SPEC`, `IMPL_PLAN`, and `SPECS_DIR` into this feature directory.
  Script JSON reported `BRANCH=003-runway-burn-rate`; direct Git status verified
  the actual app-managed branch remained unchanged. The feature-context identifier
  is not permission to create/switch/rename a branch.
- Loaded the copied/resolved plan template. Used `docs/specs/`, not its example
  root `specs/`. Restored setup's path-format rewrite of `.specify/feature.json`
  to the original feature-003 content; no unrelated context update.
- Optional before/after plan Git commit hooks: skipped, publication out of scope.
  Optional after-plan agent-context update: skipped, preserve unrelated context.
- No mandatory `hooks.before_plan` entry is registered centrally. The installed
  red-team extension declaration is not proof of an executed spec review.
  No red-team gate/review is claimed passed or waived.
- `before_tasks` **plan-review-gate** is mandatory and still pending for the
  coordinator. Its merged/locally-clean artifact checks were not executed.
  New uncommitted planning artifacts are not satisfaction of that gate.
- No `tasks.md`, acceptance-to-task mapping, or implementation sign-off created.
  No delegation. Ordinary decisions below are resolved, not questions to the user.

## Project Structure

### Documentation (this feature)

```text
docs/specs/003-runway-burn-rate/
├── spec.md                    existing; unchanged
├── checklists/                existing; unchanged
├── plan.md                    this planning record
├── research.md                decisions, evidence, alternatives
├── data-model.md              source/entity and calculation contracts
├── contracts/
│   └── runway-api.md          normative HTTP/JSON contract
└── quickstart.md              safe future validation guide
```

`tasks.md` was absent in the planning pass. It now tracks completed backend and
frontend work with explicit remaining QA handoff.

### Source Code (repository root)

Backend and client manifests below are implemented:

```text
src/budget_api/
├── main.py                               modify: register router + 2 no-store paths
├── models/runway.py                      new: request/response/evidence models
├── routers/runway.py                     new: all 3 thin runway routes
├── services/runway.py                    new: settings, local adapter, pure math
├── tests/isolated_run.py                  new: opt-in parent/child temp guards
└── tests/runway/
    ├── conftest.py                       new: temp/env/network/fallback guards
    ├── test_isolation.py                 new: guard proofs
    ├── test_calculation.py               new: source, arithmetic, evidence cases
    └── test_api.py                       new: endpoints, atomicity, compatibility
client/src/
├── types/runway.ts                       new: wire DTOs
├── api/runway.ts                         new: typed API calls
├── api/client.ts                         modify: optional no-store request policy
├── hooks/useRunway.ts                    new: request/settings/save lifecycle
├── hooks/__tests__/useRunway.test.tsx      new: races/failure/retry
├── lib/runway.ts                         new: money/reason presentation helpers
├── components/bills/RunwayPanel.tsx       new: independent summary/history/states
├── components/bills/RunwaySettings.tsx    new: explicit account selection
├── components/bills/__tests__/runway.test.tsx
│                                        new: settings/panel/privacy
├── components/bills/__tests__/runway-fixtures.ts
│                                        new: neutral typed contract fixtures
├── components/bills/__tests__/BillsDashboard.test.tsx
│                                        modify: alias route's runway mocks
├── pages/BillsPage.tsx                   modify: stable independent panel mount
└── tests/BillsPage.test.tsx              modify: snapshot/window/branch independence
client/tests/SettingsPage.test.tsx        modify: missing categories/split mocks
```

**Structure Decision**: Reuse current API/client directories. A single service
module is sufficient; no repository abstraction, generic evidence engine,
controller layer, generated client, store framework, or new test dependency.
The service computes `PRIVATE_DATA_DIR / "runway_config.json"` dynamically; no
new static storage constant or storage-fixture patch list entry is necessary.
Broader safety-harness edits, if later needed for full regression, require a
separate verified file manifest; they are not hidden in this estimate.

## Architecture and boundaries

### Backend flow

1. Thin routes validate request shape and reject unsupported inputs. Settings GET
   returns saved IDs plus eligible/current-invalid picker metadata; no balances
   are persisted in config. Nonempty PUT validates every selected account,
   performs a stable-source check, then atomically replaces only runway settings.
2. Result GET derives server-local calendar window without a month query. Load
   exact local sources into memory; detect running sync or changing source bytes.
   No imports/calls into Bills builder, sync, report builder, PS client, or env reader
   from the runway service.
3. Validate transaction provenance and relevant fields. Apply complete exclusions
   and stable-ID deduplication. Never drop a bad transaction to rescue a month.
   Determine the common usable month set before all averages.
4. Resolve current selected balances and currency evidence, retaining invalid
   selections. Aggregate signed reserves and gross spending per owner, then
   household once. Compute ratio only with sufficient valid positive denominator
   and positive valid reserves; expose valid observations even when ratio is null.
5. Return nullable measures, all reasons, monthly observations, distinct source
   dates, and current calculation time. No saved result, implicit GET writes,
   fallback snapshot, historical reserves, or currency conversion.

Runway-local conventions are deliberate: strict source validation with optional
read-only provenance, bounded double-reading, and static privacy-safe 400 text
rather than echoed validation locations. JSON duplicate object keys fail. Sync
route functions run file work in FastAPI's worker pool, not the async event loop.
No legacy source reader/writer changes. Tests add an opt-in global isolation
runner rather than making shared fixtures autouse for normal runs.

Frontend follows existing hooks, typed API wrappers, Tailwind/Radix controls and
render-time privacy formatters. `lib/runway.ts` is justified by shared static issue
copy and currency-aware money presentation; it performs no financial calculation.
`runway_display` is rendered verbatim, preserving backend half-up/tiny rounding.
The small `apiGet`/`apiPut` cache option is an additive existing-helper extension;
other callers keep their prior behavior. Native `<details>` is the local
expandable-settings choice, noted for team review rather than a new UI framework.
The picker has no money fields, so it needs no second privacy subscription.

### Client flow

- Keep the panel mounted outside legacy Bills loading/error/not-found branches,
  adjacent to the household area on success. No dependency on `snapshots[0]`,
  mock hydration, selected Bills display months, or a current snapshot.
- Load result and settings independently. Keep server-confirmed IDs, editable
  draft, save state, and result state separate. Request generations suppress
  late responses; saving invalidates any older result request. On success refresh
  runway only. On failure preserve the draft and label retained result as using
  the saved selection. Never enable Save after a failed settings read.
- Show loading, error/retry, unavailable, qualified, and available distinctly.
  Use an expandable settings section, labelled checkboxes, explicit Save,
  status/live-region text, and keyboard-operable controls.
- Show selected accounts/owners, all three candidate months and exclusion reasons,
  gross-spending observations, calculation/source/balance dates, warnings, and
  descriptive-not-predictive copy. No chart or historical runway is needed.
- Subscribe to global privacy; mask every money surface with `****` including
  attributes, tooltips, signs, zero, and accessible text. Do not embed amounts in
  reason/error strings. Ratios, labels, dates, and counts remain visible.

## Validation design and handoff

| Requirements | Future verification evidence |
|---|---|
| FR-002–008, 013–019, 026 | Pure synthetic calculations: spec arithmetic; 3/2/1/0 months; calendar edges; complete/unknown/partial history; refunds/exclusions; duplicates; ownership; signed reserves; currency; all reasons; half-up and tiny ratios. |
| FR-009–012, 015, 020–021, 025 | Isolated API tests: missing GET does not write; empty Save; strict invalid PUT preserves bytes; catalog drift; no source changes/network; legacy Bills unchanged; no-store on successes and errors. |
| FR-001, 022–023 | Hook/panel/page tests: independent missing-current-snapshot result, initial loading, settings-load/save failure, retained draft/saved-result distinction, retries and late response suppression. |
| FR-024–025 | Global privacy test: visible text, titles/tooltips/ARIA, zero and negatives, unchanged ratio/context, no refetch or selection reset. |
| SC-004–008, FR-027 | Separate synthetic browser usability/privacy evidence and recorded 10,000-transaction timing; comprehension exercise, not automated-test substitution. |

Commands and safety prerequisites are in [quickstart.md](quickstart.md).
No tests ran during the earlier planning pass. Current backend evidence is in
quickstart: 124 focused backend passes, 1116 canonical Windows passes, two renderer
tests deselected, 0.241s synthetic backend timing (prior backend pass, not rerun).
Frontend: 62 focused and 414 full-suite passes, strict TypeScript/production build,
seven synthetic Chromium scenarios with screenshots. Browser API responses were
intercepted; this is not real backend/browser performance or human acceptance.
Ubuntu/native-renderer checks, independent QA and full-product sign-off remain open.

### Migration summary

No database migration. First explicit successful Save creates the additive
version-1 settings file; GET absence has defined behavior. Unknown future settings
versions fail explicitly. No account-binding fields, BillsSnapshot schema 5,
report contract/calculation versions, existing stored snapshots, or source
financial records are migrated.

## Complexity Tracking

| Violation / issue | Why needed | Simpler alternative rejected because |
|---|---|---|
| Baseline dependency declarations contradict constitution IV/Technical Constraints | Not needed by runway; not introduced or justified by this design. | Neither silently downgrading packages nor declaring stale constitution text nonbinding is authorized. Reconcile through governance; gate remains ERROR. |

No additional architectural violation is requested. Backend implementation and
local validation, including frontend, are complete under the direct continuation;
no migration or repository dependency changes. The next work is unchecked QA.
The merged-plan gate remains NOT passed; resolve it through an authorized process
before merge, not by publishing to force this local execution through a gate.
