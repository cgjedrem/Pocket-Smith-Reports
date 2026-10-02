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
    computed once at hydration, so toggling would not update them without a
    refetch (violates FR-008).

## Decision 3: Remount-on-toggle for invalidation

- **Decision**: `AppLayout` reads `useAmountsHidden()` and renders
  `<main>` (or `<Outlet/>`) with `key={hidden ? "hidden" : "visible"}` so the
  page subtree remounts and re-derives every label from the store.
- **Rationale**: Labels are plain strings produced during render; a remount
  is the simplest correct invalidation and guarantees FR-009 (immediate,
  exact restore). Module-level data sources (`bills-source.ts`) survive
  remount, and page components hold no fetch-state that a remount would lose
  beyond what they already re-derive — satisfying FR-008 (no refetch of
  financial data; report pages re-read from their existing caches/hooks the
  same way any remount/navigation does).
- **Alternatives considered**:
  - *Make every format function reactive via hook*: impossible — they are
    plain functions called inside render of components that would each need
    the hook; a remount achieves the same with one line.

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
