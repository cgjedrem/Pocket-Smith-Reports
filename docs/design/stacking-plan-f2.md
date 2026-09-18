# F2 Bills Preview — PR Stacking Plan

Status: ACTIVE (in flight)
Date: 2026-07-30
Trunk: `feature/f2.1-bills-sceleton` (off `main`)

## Stack

```
feature/f2.1-bills-sceleton                    (trunk)
  └─ f2-pr1-foundation                         types, mock, theme, router, layout, v0 cleanup
    └─ f2-pr2-bar-core                         EconomyBar + MonthCard + bar tests
      └─ f2-pr3-event-list                     EventRow + AddEventDialog + shadcn dialog/alert-dialog
        └─ f2-pr4-views                        BillsDashboard + GraphView + TableView + page + toggle-group
          └─ f2-pr5-docs                       this plan
```

5 PRs. Merge order top→down: pr5 → pr4 → pr3 → pr2 → pr1 → trunk.

## Per-PR scope

### PR 1 — Foundation + v0 cleanup
**Base:** `feature/f2.1-bills-sceleton`

**Code (new):**
- `client/src/components/bills/finance-data.ts` — `mulberry32`, `formatKr`, `MONTH_NAMES`, `pctWidth`, `upperBarWidth`, `getEconomyStatus`, `buildMonth`, `getMonths`, `getAllEvents`
- `client/src/components/bills/finance-format.ts` — currency/date helpers

**Code (modified):**
- `client/src/types/api.ts` — F2 types: `F2Partner`, `F2EventType`, `F2EconomyStatus`, `FinanceEvent`, `FinanceEventList`, `PartnerEconomy`, `MonthData`, `MonthList`, `EconomyBarView`
- `client/src/styles/theme.css` — HSL vars: `--income`, `--savings`, `--shortfall`, `--partner-a`, `--partner-b` + foregrounds
- `client/src/router.tsx` — `/bills-preview` route
- `client/src/layouts/AppLayout.tsx` — nav link
- `client/vite.config.js` — likely `assetsInclude` for SVG

**v0 import cleanup (deletes — files were never tracked, so deletion happens out-of-band):**
- `docs/design/f2-import/` (dir)
- `docs/design/f2-import-INDEX.md`
- `docs/design/f2-import-MIGRATION.md`
- `docs/design/f2-import-PLAN.md`
- `docs/design/f2-bills-v0-prompt.md`

**Other:**
- `docs/design/design-f1.3-mega-reports.md` → `docs/design/done/` (move)

**Why bottom:** every other PR imports types from `api.ts` + helpers from `finance-data.ts`. Theme vars are referenced by every component. Router + layout carry the page.

### PR 2 — Bar core
- `client/src/components/bills/EconomyBar.tsx` — capsule bar with status, partner dot, bills + budget zones, salary bar + savings box in shared salary-zone column, total label badge
- `client/src/components/bills/MonthCard.tsx` — month header + partner bars + collapsible event list
- `client/src/components/bills/__tests__/fixtures.ts` — 6 synthetic scenarios
- `client/src/components/bills/__tests__/upper-bar.test.ts` — 14 tests
- `client/src/components/bills/__tests__/BillsDashboard.test.tsx` — smoke test

### PR 3 — Event list
- `client/src/components/bills/EventRow.tsx` — day-by-day event with edit/delete buttons
- `client/src/components/bills/AddEventDialog.tsx` — controlled shadcn dialog with create + edit modes
- `client/src/components/ui/dialog.tsx` — shadcn
- `client/src/components/ui/alert-dialog.tsx` — shadcn

### PR 4 — Views
- `client/src/components/bills/BillsDashboard.tsx` — header, view toggle, dialog state
- `client/src/components/bills/GraphView.tsx` — all months in 2-col grid
- `client/src/components/bills/TableView.tsx` — tabular data
- `client/src/components/ui/toggle-group.tsx` — shadcn
- `client/src/components/ui/toggle.tsx` — shadcn
- `client/src/pages/BillsPreviewPage.tsx` — page entry, mounts Dashboard

### PR 5 — Docs
- This plan

## Out of scope (follow-up PRs)
- Hide "Est. CC bill" sub-block on the current month (uses `isCurrentMonth` flag).
- Replace mock data with real FastAPI `/api/bills/months` endpoint.
- Savings projection / forecasting.
- CC paydown planner.
- App shell with cross-page navigation (F7).
