# Contracts: Hide Amounts Toggle

**Feature**: `002-hide-amounts-toggle` | **Date**: 2026-10-02

No HTTP/API contracts change — this is a pure client feature. The contracts
below are the module API and the UI behavior contract that tests assert.

## 1. Module contract — `client/src/lib/privacy-store.ts`

```ts
export const AMOUNT_MASK: "****";

// Store shape (useSyncExternalStore-compatible, same pattern as
// client/src/lib/bills-source.ts)
export function subscribe(listener: () => void): () => void;
export function isAmountsHidden(): boolean;            // stable snapshot getter
export function useAmountsHidden(): boolean;           // React hook wrapper

// Mutations — every mutation notifies all subscribers exactly once
export function toggleAmountsHidden(): void;
export function setAmountsHidden(hidden: boolean): void;

// Last-mile masking for format functions
export function maskAmount(formatted: string): string;
```

### `maskAmount` rules

| Input state | `hidden=false` | `hidden=true` |
|---|---|---|
| `"12,340 kr"` | unchanged | `"****"` |
| `"+2,000 kr"` / `"-1,500 kr"` | unchanged | `"****"` (sign never leaks) |
| `"0 kr"` | unchanged | `"****"` (zero is masked) |
| `""` (absent value) | `""` | `""` (absence must not become a mask) |
| `"65%"` / `"2026-04"` | unchanged | unchanged (callers never pass these) |

### Store invariants

- I-1: `isAmountsHidden()` returns the same value across calls until a
  mutation (referential stability for `useSyncExternalStore`).
- I-2: Store init reads `localStorage["psr:hide-amounts"]`; `"1"` ⇒ hidden,
  anything else/unavailable ⇒ visible. Reading never throws (jsdom, SSR,
  disabled storage).
- I-3: Every mutation writes localStorage before notifying subscribers.
- I-4: No network or financial-data interaction — the store touches only
  localStorage.

## 2. UI contract — header toggle (AppLayout)

| Property | Contract |
|---|---|
| Placement | Right end of the global header nav, visible on every route |
| Icon | `Eye` when visible-state, `EyeOff` when hidden-state (lucide-react) |
| `aria-label` | `"Hide amounts"` when visible, `"Show amounts"` when hidden |
| `aria-pressed` | `true` iff amounts are hidden |
| Keyboard | Focusable, activates on Enter/Space (native `<button>`) |
| Effect | Subscribed page roots re-render **in place** (no remount, no refetch, selection state preserved); the bills hook re-maps cached raw snapshots through the pure mappers and re-hydrates `bills-source` (no network) — see research.md Decisions 3/3b |

## 3. Coverage contract — surfaces that MUST mask

Tests + quickstart verify each of these renders `****` when hidden:

| Surface | Format site (existing) |
|---|---|
| Bills dashboard labels (salary, bills, budget, CC usage/bill, savings, net, remaining) | `formatKr`, `formatSignedKr` (`components/bills/finance-data.ts`) — covers mock AND live paths via `lib/bills-mapper.ts` |
| Bills graph axis ticks | local `Intl.NumberFormat` formatter (`components/bills/GraphView.tsx`) |
| Monthly report KPIs, reconciliation, drilldowns | local helpers (`KpiRoleSummary.tsx`, `ReconciliationSection.tsx`, `SectionDrilldowns.tsx`) |
| Report charts (donut center, bar values, partner KPI matrix) | `charts/DonutChart.tsx`, `charts/HorizontalBarChart.tsx`, `charts/PartnerKpiMatrix.tsx` |
| Mega-report sections (all tables) | `formatNOK` (`mega-reports/sections/helpers.ts`), local helpers in `InvestmentTable.tsx`, `PartnerSplitTable.tsx`, `PersonalTable.tsx` |
| Mega-report chart axes | `compactNOK` (`helpers.ts`) |
| All recharts tooltips | shared `ui/chart.tsx` tooltip value |

## 4. Non-goals (explicitly out of contract)

- Percentages, transaction counts, dates, month labels, category/partner
  labels: never masked.
- Chart geometry (bar widths, line shapes): unchanged.
- PDF/HTML export artifacts: unchanged.
- API payloads: unchanged (presentation-layer only).
