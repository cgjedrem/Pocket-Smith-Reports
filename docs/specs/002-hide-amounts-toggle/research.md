# Phase 0 Research: Hide Amounts Toggle

**Date**: 2026-10-02 | **Feature**: `002-hide-amounts-toggle`

All Technical Context fields were resolvable from repo evidence; no NEEDS
CLARIFICATION items remained. This file records the design decisions.

## Decision 1: Module-level privacy store with `useSyncExternalStore`

- **Decision**: A new `client/src/lib/privacy-store.ts` holds the `hidden`
  boolean, exposes `subscribe` / `isAmountsHidden` / `toggleAmountsHidden` /
  `setAmountsHidden` / `useAmountsHidden()`, plus `maskAmount(formatted)` and
  `AMOUNT_MASK = "****"`.
- **Rationale**: `client/src/lib/bills-source.ts` already uses exactly this
  pattern (module store + subscribe + snapshot). Format functions are plain
  module-level functions called during render — they can read the store
  directly without prop drilling or context threading through ~12 files.
  Satisfies the react-client charter rule "state/business rules live outside
  components: src/lib/ for logic".
- **Alternatives considered**:
  - *React Context + prop threading*: rejected — every format helper is a
    plain function, not a component; threading context into them would touch
    far more code and invite missed call sites.
  - *CSS-only hiding (blur/invisibility class on a wrapper)*: rejected — the
    real figures remain in the DOM (devtools, copy-paste, accessibility tree)
    and bar/axis text would blur inconsistently.

## Decision 2: Mask at the last mile, inside existing format functions

- **Decision**: Each existing currency-format helper calls
  `maskAmount(...)` on its fully formatted result. No parallel masked
  variants, no changes to data mapping (`bills-mapper.ts` needs zero edits —
  it already routes every label through `formatKr`/`formatSignedKr`).
- **Rationale**: The audit found ~10 format sites covering every amount
  surface (KPI cards, tables, donut centers, bar values, chart tooltips via
  shared `ui/chart.tsx`, mega-report sections via `formatNOK`/`compactNOK`,
  bills dashboard via `formatKr`). Masking inside them makes "missed a spot"
  structurally unlikely and keeps components untouched (thin-components
  charter rule).
- **Alternatives considered**:
  - *`<Amount>` wrapper component at every render site*: rejected — ~50+
    JSX call sites, high miss risk, violates thin-components minimalism.
  - *Masking in `bills-mapper.ts` / API layer*: rejected — mapper labels are
    computed at hydration, not render; masking there would bake the mask
    into stored strings. (Hydration-time computation is handled by
    re-deriving from cached raw snapshots on toggle — see Decision 3b.)

## Decision 3: Reactive in-place re-render — NO remount (revised after review)

- **Decision**: Each page root that can render amounts
  (`MonthlyReportsPage`, `MegaReportsPage`, `BillsPage`, `BillsPreviewPage`)
  calls `useAmountsHidden()`. When the flag flips, React re-renders the page
  subtree **in place** — format functions re-run during render, while
  component state (selected month, filters), mounted fetch effects, and the
  DOM subtree are all preserved. `AppLayout` only hosts the toggle button;
  it does NOT wrap the outlet in a remount key.
- **Rationale**: The original remount-on-toggle design contradicted FR-008:
  pages fetch on mount (`MonthlyReportsPage` `useEffect`→`refresh`,
  `useBills.ts` `useBillsSnapshot` `useEffect`→`/api/bills/dashboard`) and
  hold selections in component state, so a remount would issue backend
  requests and reset user selections. In-place re-render re-invokes render-
  time formatters with zero network activity and zero state loss, satisfying
  FR-008 and FR-009 exactly.
- **Alternatives considered**:
  - *Remount via `key` on the outlet*: REJECTED (initial design) — triggers
    mount effects → refetch + state reset (FR-008 violation).
  - *Subscribe in every leaf component*: rejected — dozens of edits; a page-
    root subscription re-renders the whole (unmemoized) subtree for free.

## Decision 3b: Bills labels re-derive from cached raw snapshots on toggle

- **Decision**: The bills live path precomputes display labels at hydration
  time (`useBillsSnapshot` → `mapSnapshotToMonthData`/`mapSnapshotToEvents`
  → `hydrate()` into the `bills-source` module store), so a re-render alone
  cannot re-mask them. `useBillsSnapshot` therefore subscribes to
  `useAmountsHidden()` and, on change, re-runs the pure mappers over its
  **already-cached raw `snapshots` state** and calls `hydrate()` again —
  a pure in-memory recompute with no network request. The mock path
  (`BillsPreviewPage` / `bills-source` seeding) re-derives the same way.
  Existing `useBillsSourceSubscription` consumers re-render from the store
  notification as they already do.
- **Rationale**: Keeps formatting last-mile (mappers stay the single label
  producer) while making the precomputed-label path reactive without a
  refetch. Raw snapshots are already held in hook state, so no new caching
  layer is introduced.
- **Alternatives considered**:
  - *Store raw numbers in bills-source and format at render*: rejected —
    large refactor of the MonthData/FinanceEvent contracts and every bills
    component; re-mapping cached snapshots achieves the same invalidation
    with a two-line hook change.
  - *Refetch on toggle*: rejected — violates FR-008.

## Decision 4: Toggle in the global header

- **Decision**: Eye/EyeOff icon button (lucide-react, already a dependency)
  right-aligned in the existing `AppLayout` nav, with `aria-label`
  ("Hide amounts"/"Show amounts") and `aria-pressed`, ghost styling matching
  the existing nav (`text-muted-foreground hover:text-foreground`).
- **Rationale**: FR-001 (always accessible from every page) — the header is
  the only element present on all routes. Charter a11y gate requires
  labelled, keyboard-operable controls.
- **Alternatives considered**: per-page toggles (violates FR-003 spirit),
  settings-only toggle (not reachable mid-screenshot).

## Decision 5: Persistence in `localStorage`

- **Decision**: Key `psr:hide-amounts`, values `"1"`/`"0"`, read lazily at
  store init with a non-browser/`JSON`-safe guard so vitest/jsdom never
  crashes; default visible (FR-007).
- **Rationale**: Spec assumption — client-side persistence suffices; no
  account concept exists.
- **Alternatives considered**: sessionStorage (loses state across tabs —
  worse for the screenshot use case), server-side preference (out of scope,
  no backend changes wanted).

## Decision 6: Charts keep geometry, mask only rendered numerics

- **Decision**: Recharts axis tick formatters and tooltip value formatters
  route through the mask; bar/line geometry is untouched (spec FR-006).
- **Rationale**: Matches "keep the percentage" — proportions stay useful in
  screenshots while no absolute figure leaks.
