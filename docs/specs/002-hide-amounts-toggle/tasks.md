# Tasks: Hide Amounts Toggle

**Input**: Design documents from `/docs/specs/002-hide-amounts-toggle/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/privacy-store.md, quickstart.md

**Tests**: Included — repo constitution VIII (colocated tests gate merges) and quickstart.md Scenario 1 require them. Tests are written BEFORE the implementation task they cover. Review feedback added per-surface rendering tests (SC-001) so a local formatter regression cannot slip past green shared-helper tests.

**Organization**: Tasks grouped by user story (US1 = mask all amounts P1, US2 = charts/tooltips P2, US3 = persistence P3).

**Post-review design note**: invalidation is REACTIVE, not remount — page roots subscribe via `useAmountsHidden()` and re-render in place (FR-008: no refetch, no state reset); `useBillsSnapshot` re-maps its cached raw snapshots and re-hydrates `bills-source` on toggle (research.md Decisions 3/3b). AppLayout hosts only the toggle button.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1/US2/US3 per spec.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the test baseline so pre-existing failures are never attributed to this feature

- [ ] T001 Record the pre-existing client test/build baseline: run `pnpm test` and `pnpm build` in `client/`, note which failures exist BEFORE any change (memory.md predicts IntersectionObserver stub failures, SyncPage hardcoded 2026-07, and possibly a red vite build); paste the failing test names into the PR description

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The privacy store and toggle mechanism every story depends on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T002 Write failing store tests in `client/src/lib/__tests__/privacy-store.test.ts` per contracts/privacy-store.md §1 invariants I-1/I-2/I-4: `maskAmount` passthrough when visible and `"****"` when hidden; `""` stays `""`; `toggleAmountsHidden` flips and notifies each subscriber exactly once; `isAmountsHidden()` referentially stable between mutations (useSyncExternalStore-safe); init throws nothing when localStorage is unavailable
- [ ] T003 Create `client/src/lib/privacy-store.ts` following the module-store pattern of `client/src/lib/bills-source.ts`: exports `AMOUNT_MASK = "****"`, `subscribe(listener)`, `isAmountsHidden()`, `toggleAmountsHidden()`, `setAmountsHidden(v)`, `useAmountsHidden()` (useSyncExternalStore wrapper), `maskAmount(formatted)`; in-memory state only at this point (persistence is US3); make T002 pass
- [ ] T004 Write failing AppLayout tests (extend or add under `client/src/**/__tests__` near `client/src/layouts/AppLayout.tsx`, follow existing test conventions): header renders an eye toggle button with `aria-label="Hide amounts"` and `aria-pressed=false` by default; clicking it flips `aria-pressed` and swaps the label to `"Show amounts"`; keyboard Space/Enter activates it
- [ ] T005 Modify `client/src/layouts/AppLayout.tsx`: add right-aligned (`ml-auto`) ghost icon button in the existing `<nav>` using lucide-react `Eye`/`EyeOff`, `aria-label` + `aria-pressed` per contracts §2, calling `toggleAmountsHidden()`. NO remount key on the outlet — invalidation is per-page subscription (T030). Make T004 pass
- [ ] T030 Subscribe page roots so toggling re-renders in place: call `useAmountsHidden()` in `client/src/pages/MonthlyReportsPage.tsx`, `MegaReportsPage.tsx`, `BillsPage.tsx`, and `BillsPreviewPage.tsx` (read the value; the subscription is what matters — destructure it even if unused by markup, with a one-line comment: re-render on privacy toggle, no remount). Verify no fetch effect re-fires on toggle (effects' dep arrays unchanged)

**Checkpoint**: Store + toggle exist and are tested; page roots re-render on toggle (no visible effect yet — no formatter masked)

---

## Phase 3: User Story 1 - Mask all monetary amounts on demand (Priority: P1) 🎯 MVP

**Goal**: One header click replaces every monetary amount on monthly reports, mega reports, and the bills dashboard with `****`; percentages, counts, dates, and labels untouched; deactivating restores exact values with no refetch

**Independent Test**: Toggle on → no monetary figure visible on any of the three pages (quickstart.md Scenario 3 steps 1–4); toggle off → original figures restored; Network tab shows zero requests caused by the toggle

### Tests for User Story 1 ⚠️

> Write FIRST, ensure they FAIL before implementation

- [ ] T006 [US1] Add formatter masking tests to `client/src/lib/__tests__/privacy-store.test.ts` (single task — same file, never parallel with itself): `formatKr`/`formatSignedKr` (from `client/src/components/bills/finance-data.ts`) and `formatNOK` (from `client/src/components/mega-reports/sections/helpers.ts`) return `"****"` when hidden — including negative, signed-positive, and zero inputs — and normal output when visible
- [ ] T007 [P] [US1] Add a rendering test for the monthly-report KPI surface (`client/src/components/reports/__tests__/`, extend existing conventions): render `KpiRoleSummary` with fixture data, toggle hidden via `setAmountsHidden(true)`, assert every amount cell reads `****` AND the percentage cell(s) are byte-identical to the visible render (FR-005 guard, SC-001/SC-004)
- [ ] T031 [P] [US1] Add a rendering test for a mega-report table surface (`PartnerSplitTable` with a minimal fixture `MegaReportResponse`): hidden → all currency cells `****`; visible → nb-NO figures; row/category labels unchanged
- [ ] T032 [P] [US1] Add a rendering test for the bills surface: hydrate `bills-source` from a small synthetic `BillsSnapshot` via the same mapper path `useBillsSnapshot` uses, render the partner card/economy bar component, toggle hidden, assert salary/bills/CC/savings labels are `****` while status text and widths (style attributes) are unchanged

### Implementation for User Story 1

- [ ] T008 [P] [US1] Mask `formatKr` and `formatSignedKr` in `client/src/components/bills/finance-data.ts` by routing their return values through `maskAmount()` — covers ALL bills dashboard labels on both mock and live paths (lib/bills-mapper.ts routes through these; do NOT edit bills-mapper.ts); makes T006 pass for those two
- [ ] T009 [P] [US1] Mask `formatNOK` in `client/src/components/mega-reports/sections/helpers.ts` via `maskAmount()`; makes T006 pass for formatNOK
- [ ] T010 [P] [US1] Mask the local `toLocaleString` format helper in `client/src/components/reports/KpiRoleSummary.tsx`; makes T007 pass
- [ ] T011 [P] [US1] Mask the local format helper in `client/src/components/reports/ReconciliationSection.tsx`
- [ ] T012 [P] [US1] Mask the local format helper in `client/src/components/reports/SectionDrilldowns.tsx`
- [ ] T013 [P] [US1] Mask the local format helper in `client/src/components/mega-reports/sections/InvestmentTable.tsx`
- [ ] T014 [P] [US1] Mask the local format helper in `client/src/components/mega-reports/sections/PartnerSplitTable.tsx`; makes T031 pass
- [ ] T015 [P] [US1] Mask the local format helper in `client/src/components/mega-reports/sections/PersonalTable.tsx`
- [ ] T033 [US1] Make the bills live/mock label path reactive: in `client/src/hooks/useBills.ts` (`useBillsSnapshot`), subscribe to `useAmountsHidden()` and re-run `mapSnapshotToMonthData`/`mapSnapshotToEvents` over the cached `snapshots` state + `hydrate()` when the flag flips (pure recompute — add the flag to a `useEffect` that does NOT call the API); apply the same re-derive in the mock seeding path used by `BillsPreviewPage.tsx`; makes T032 pass
- [ ] T016 [US1] Sweep the three pages for any remaining rendered monetary figure not routed through the sites above (grep `client/src/pages` and `client/src/components` for `toLocaleString`/`NumberFormat` outside the modified files; verify `AppendicesSection.tsx` shows only transaction COUNTS, which per contract §4 must NOT be masked); mask any missed monetary site

**Checkpoint**: US1 fully functional — every non-chart amount on all three pages masks/unmasks from the header toggle, in place, with no network activity

---

## Phase 4: User Story 2 - Chart and tooltip figures are masked too (Priority: P2)

**Goal**: No chart axis label, data-point value, or hover tooltip leaks a monetary figure while masked; chart geometry still renders

**Independent Test**: With masking active, hover every chart and inspect every axis on the three pages (quickstart.md Scenario 3 step 4)

### Tests for User Story 2 ⚠️

> Write FIRST, ensure they FAIL before implementation

- [ ] T017 [US2] Extend `client/src/lib/__tests__/privacy-store.test.ts` (sequential after T006 — same file): `compactNOK` returns `"****"` when hidden; `"1.0M"`/`"250k"`-style output when visible
- [ ] T034 [P] [US2] Add a tooltip rendering test: render a recharts chart through the shared `client/src/components/ui/chart.tsx` tooltip with a monetary payload, hidden → tooltip value reads `****`; visible → formatted number; a percentage-valued tooltip entry stays unmasked (FR-005)
- [ ] T035 [P] [US2] Add a chart-value rendering test for `DonutChart` (center/total) and `HorizontalBarChart` (bar values): hidden → `****`; visible → numbers

### Implementation for User Story 2

- [ ] T018 [US2] Mask `compactNOK` in `client/src/components/mega-reports/sections/helpers.ts` via `maskAmount()` (same file as T009 — sequence after it); makes T017 pass
- [ ] T019 [P] [US2] Mask the axis tick formatter (`Intl.NumberFormat("no-NO")` wrapper) in `client/src/components/bills/GraphView.tsx`
- [ ] T020 [P] [US2] Mask the center/total value in `client/src/components/reports/charts/DonutChart.tsx`; makes T035 pass for DonutChart
- [ ] T021 [P] [US2] Mask bar values in `client/src/components/reports/charts/HorizontalBarChart.tsx`; makes T035 pass for HorizontalBarChart
- [ ] T022 [P] [US2] Mask cell values in `client/src/components/reports/charts/PartnerKpiMatrix.tsx`
- [ ] T023 [US2] Mask the tooltip value (`item.value.toLocaleString()`) in the shared `client/src/components/ui/chart.tsx` — this covers ALL recharts tooltips app-wide; if a percentage-only tooltip routes through this formatter, key the mask on the value kind so percentages stay unmasked per FR-005; makes T034 pass

**Checkpoint**: US1 AND US2 both work — full pages including charts are screenshot-safe

---

## Phase 5: User Story 3 - Preference survives a page reload (Priority: P3)

**Goal**: The mask preference persists in the browser across reloads; a fresh browser defaults to visible

**Independent Test**: Toggle on → reload → still masked; toggle off → reload → visible; clear site data → visible (quickstart.md Scenario 3 steps 5–6)

### Tests for User Story 3 ⚠️

> Write FIRST, ensure they FAIL before implementation

- [ ] T024 [US3] Add persistence tests to `client/src/lib/__tests__/privacy-store.test.ts` (sequential — same file): setting hidden writes `localStorage["psr:hide-amounts"]="1"` BEFORE subscribers are notified (invariant I-3); a simulated fresh module init with `"1"` present starts hidden, with `"0"`/absent/garbage starts visible (invariant I-2)

### Implementation for User Story 3

- [ ] T025 [US3] Add lazy localStorage init (key `psr:hide-amounts`, `"1"`=hidden, anything else/unavailable=visible, never throws) and write-before-notify on every mutation in `client/src/lib/privacy-store.ts`; makes T024 pass

**Checkpoint**: All three user stories independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Gates and end-to-end proof

- [ ] T026 Run `pnpm test` in `client/` and confirm zero NEW failures vs. the T001 baseline (all new tests pass)
- [ ] T027 Run `pnpm build` in `client/` (`tsc -b && vite build`) and confirm no NEW failure vs. the T001 baseline
- [ ] T028 Execute quickstart.md Scenario 3 (manual end-to-end with the API + dev server running, including keyboard/Space activation and devtools Network check proving the toggle causes ZERO requests) and Scenario 4 (screenshot spot-check); record results in the PR description
- [ ] T029 [P] Update the speckit agent context files if the optional `/speckit-agent-context-update` hook is requested

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on T001 — BLOCKS all user stories (T030 page subscriptions included here because every story's invalidation depends on them)
- **US1 (Phase 3)**: Depends on Phase 2 — the MVP
- **US2 (Phase 4)**: Depends on Phase 2 (store) and T009→T018 sequencing note; otherwise independent of US1
- **US3 (Phase 5)**: Depends on Phase 2 (store file exists); independent of US1/US2
- **Polish (Phase 6)**: Depends on all stories

### User Story Dependencies

- **US1 (P1)**: After Foundational. No dependency on US2/US3.
- **US2 (P2)**: After Foundational. Shares `helpers.ts` with US1 (T009 → T018 sequential; everything else parallel).
- **US3 (P3)**: After Foundational. Same file as T003 — sequential within the store, no other conflicts.

### Parallel Opportunities

- T007, T031, T032 (US1 rendering tests, different files) in parallel — AFTER T006 lands in the shared store test file
- T008, T010–T015 — all different files — in parallel (7 tasks)
- T034 + T035 in parallel; T019–T022 — all different files — in parallel
- US2 and US3 can proceed in parallel after US1 (single file collisions noted above)

## Parallel Example: User Story 1

```text
# After T008/T009 land, launch together:
Task: "Mask format helper in client/src/components/reports/KpiRoleSummary.tsx"
Task: "Mask format helper in client/src/components/reports/ReconciliationSection.tsx"
Task: "Mask format helper in client/src/components/reports/SectionDrilldowns.tsx"
Task: "Mask format helper in client/src/components/mega-reports/sections/InvestmentTable.tsx"
Task: "Mask format helper in client/src/components/mega-reports/sections/PartnerSplitTable.tsx"
Task: "Mask format helper in client/src/components/mega-reports/sections/PersonalTable.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phases 1–2 (baseline, store, toggle, page subscriptions)
2. Phase 3 (US1) → validate independently → demoable: every text amount masks
3. US2 + US3 complete the screenshot-safety story

### Incremental Delivery

Each phase is a safe commit boundary; store + toggle (Phase 2) merged alone is invisible and harmless.

---

## Notes

- One new module (`client/src/lib/privacy-store.ts`), one new test file; ~14 surgical edits inside EXISTING format functions — no parallel masked variants (research.md Decision 2)
- `client/src/lib/bills-mapper.ts` must NOT be edited — labels re-derive through it when `useBillsSnapshot` re-maps cached snapshots on toggle (research.md Decision 3b)
- No remount keys anywhere: pages keep component state and do not refetch on toggle (FR-008)
- Percentages, counts, dates, partner/category labels are NEVER masked (FR-005); `AppendicesSection.tsx` count stays visible
- Empty labels (`""`) stay empty — never become `"****"` (data-model.md)
- Commit style: Conventional Commits, e.g. `feat(client): ...` (constitution Quality & Workflow)
