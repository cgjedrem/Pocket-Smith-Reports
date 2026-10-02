# Implementation Plan: Hide Amounts Toggle

**Branch**: `002-hide-amounts-toggle` | **Date**: 2026-10-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/docs/specs/002-hide-amounts-toggle/spec.md`

## Summary

Add a global, persistent "hide amounts" privacy toggle to the React client so
the maintainer can screenshot any page (reports, mega reports, bills) with
real data loaded and share it publicly. A module-level privacy store
(`client/src/lib/privacy-store.ts`, same pattern as `bills-source.ts`) holds
one boolean; every existing currency-format helper routes its result through
`maskAmount()` (`"****"`). Page roots subscribe via `useAmountsHidden()` and
re-render **in place** (no remount, no refetch — FR-008); the bills hook
re-maps its cached raw snapshots through the pure mappers and re-hydrates
`bills-source` on toggle (pure recompute, no network). No backend, API, or
data changes.

## Technical Context

**Language/Version**: TypeScript 5 (strict), React 19
**Primary Dependencies**: Vite 6, Tailwind CSS v4, Radix/shadcn primitives, recharts 3.8, lucide-react 1.27 (all already in `client/package.json` — no new dependencies)
**Storage**: `localStorage["psr:hide-amounts"]` (client-only; no server storage)
**Testing**: vitest 3 + Testing Library, colocated `client/src/**/__tests__`
**Target Platform**: Vite SPA in browser (Windows dev, PowerShell)
**Project Type**: Web application (frontend-only slice; backend untouched)
**Performance Goals**: Toggle re-render < 1s (SC-002); masking adds O(1) work per format call
**Constraints**: No data refetch on toggle (FR-008); pnpm only, single lockfile (pnpm-strict fragment); UTF-8 no BOM; PowerShell-compatible commands
**Scale/Scope**: ~12 existing files touched (format helpers + AppLayout), 1 new module, 1 new test file

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Evidence |
|---|---|---|
| I. Real data never in VCS | PASS | Feature touches no data files; it exists to *protect* real data in screenshots |
| II. Pipelines fail closed | N/A | No pipeline/sync changes |
| III. Atomic publishing | N/A | No report artifact changes |
| IV. Python backend pins | N/A | Backend untouched |
| V. PocketSmith client hardened | N/A | No API client changes |
| VI. Backend layers separated | N/A | Backend untouched |
| VII. React 19 + Vite + TS, pnpm only | PASS | Client-only change; no new deps; `pnpm test`/`pnpm build` are the gates |
| VIII. Tests colocated, gate merges | PASS | New tests in `client/src/lib/__tests__/` next to the store |
| IX. Windows PowerShell platform | PASS | All commands PowerShell-safe |
| Charter: react-client (logic in `lib/`, thin components, a11y gate) | PASS | Store lives in `src/lib/`; components get a one-line mask call or none; toggle has `aria-label` + `aria-pressed` + native button keyboard support |
| Quality & Workflow: artifacts under `docs/specs/` | PASS | Feature directory lives at `docs/specs/002-hide-amounts-toggle/` per the PR #27 consolidation (moved here after review feedback; the initial `specs/` placement predated this repo's layout rule) |

Post-Phase-1 re-check: design artifacts introduce no new principle friction
(store-in-lib, no refetch, no new deps). **No violations — Complexity
Tracking empty.**

## Project Structure

### Documentation (this feature)

```text
docs/specs/002-hide-amounts-toggle/
├── plan.md              # This file
├── research.md          # Phase 0 output — decisions, incl. post-review reactive redesign
├── data-model.md        # Phase 1 output — single MaskPreference boolean
├── quickstart.md        # Phase 1 output — 4 validation scenarios
├── contracts/
│   └── privacy-store.md # Phase 1 output — module API, UI contract, coverage matrix
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by this command)
```

### Source Code (repository root)

```text
client/src/
├── lib/
│   ├── privacy-store.ts              # NEW — store + maskAmount + useAmountsHidden
│   ├── bills-source.ts               # (pattern reference, unchanged)
│   └── __tests__/
│       └── privacy-store.test.ts     # NEW — store, mask, formatter, persistence tests
├── layouts/
│   └── AppLayout.tsx                 # MOD — eye toggle button in header (no remount)
├── hooks/
│   └── useBills.ts                   # MOD — useBillsSnapshot re-maps cached raw
│                                     #     snapshots + re-hydrates bills-source on toggle
├── pages/
│   ├── MonthlyReportsPage.tsx        # MOD — useAmountsHidden() subscription (re-render in place)
│   ├── MegaReportsPage.tsx           # MOD — useAmountsHidden() subscription
│   ├── BillsPage.tsx                 # MOD — useAmountsHidden() subscription
│   └── BillsPreviewPage.tsx          # MOD — useAmountsHidden() subscription + mock re-derive
├── components/
│   ├── bills/
│   │   ├── finance-data.ts           # MOD — formatKr, formatSignedKr mask
│   │   └── GraphView.tsx             # MOD — axis tick formatter masks
│   ├── reports/
│   │   ├── KpiRoleSummary.tsx        # MOD — format helper masks
│   │   ├── ReconciliationSection.tsx # MOD — format helper masks
│   │   ├── SectionDrilldowns.tsx     # MOD — format helper masks
│   │   └── charts/
│   │       ├── DonutChart.tsx        # MOD — center/total value masks
│   │       ├── HorizontalBarChart.tsx# MOD — bar value masks
│   │       └── PartnerKpiMatrix.tsx  # MOD — cell value masks
│   ├── mega-reports/sections/
│   │   ├── helpers.ts                # MOD — formatNOK, compactNOK mask
│   │   ├── InvestmentTable.tsx       # MOD — format helper masks
│   │   ├── PartnerSplitTable.tsx     # MOD — format helper masks
│   │   └── PersonalTable.tsx         # MOD — format helper masks
│   └── ui/
│       └── chart.tsx                 # MOD — shared recharts tooltip value masks
└── lib/bills-mapper.ts               # UNCHANGED — already routes all labels via formatKr
```

**Structure Decision**: Existing Vite SPA layout; the only new module lands in
`client/src/lib/` per the react-client charter fragment ("state/business rules
live outside components: src/lib/ for logic"). No new directories beyond the
colocated test file.

## Complexity Tracking

No constitution violations — table intentionally empty.
