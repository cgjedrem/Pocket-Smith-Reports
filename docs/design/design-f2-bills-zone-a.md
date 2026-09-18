# F2 — Bills Zone Redesign (Step A)

Status: APPROVED (design-first L1-L2 complete, ready for implementation)
Date: 2026-07-31
Repo: Pocket-Smith-Reports
Parent: `design-f2-bills.md`
Sub-area: `EconomyBar.tsx` → Bills zone (left half of capsule)
Sibling (not in this doc): B. Budget zone vertical fill, C. Savings box
Sibling (not in this doc): outer frame, salary, total pill (NO change this step)

## Sibling docs

- Step B (budget zone, approved): `design-f2-budget-zone-b.md`
- Step C (savings box, not started): `design-f2-savings-box-c.md`

## Summary

Restructure the **bills zone** of `EconomyBar.tsx` so it:
1. Shows two stacked labels: `Bills {X}` (top) + `Estimated cc bill {Y}` (bottom, red).
2. Treats `estimatedCcBill` as **the total bills amount** (the conceptual sum of all
   outflows, cc-included) — `Bills` becomes a scheduled sub-breakdown.
3. Fills the zone **red, left-to-right**, scaled by `bills / (bills + estimatedCcBill)`.
4. Keeps the red accent rail + receipt icon + capsule border. Total pill in capsule
   top-left is **kept** (no change).

## Decisions (from grill-me)

- **Scope = bills zone only.** Budget zone, savings box, outer frame, salary row
  are all out of scope for this step. They ship in B and C.
- **Estimated cc bill = total bills amount.** Semantically the cc statement
  represents the running total of committed spend this cycle. `Bills` is a
  scheduled-only sub-breakdown of that total.
- **Fill math:** `fillPct = bills / (bills + estimatedCcBill)`, clamped `[0, 100]`.
  When `bills + estimatedCcBill === 0`, fallback to `0%` (no fill).
- **Fill direction:** left → right.
- **Fill color:** `bg-shortfall` (existing token), opacity `/40` for soft fill on
  the muted zone background.
- **Label order:** `Bills` on top, `Estimated cc bill` below. The est. cc bill
  text uses `text-shortfall` for the value (red), `Bills` keeps neutral foreground.
- **Total pill (capsule top-left):** kept as-is. The labels inside the bills
  zone are a sub-breakdown; the Total pill remains the at-a-glance number.

## L1 — Requirements

| # | Requirement |
|---|---|
| R1 | Bills zone shows `Bills {X}` label (top) and `Estimated cc bill {Y}` label (bottom). |
| R2 | `Estimated cc bill` value text is red (`text-shortfall`). |
| R3 | Bills zone background has a left-to-right red fill proportional to `bills / (bills + estimatedCcBill)`. |
| R4 | Fill is clamped to `[0, 100]`. Zero denominators render empty fill. |
| R5 | Bills zone keeps red accent rail + Receipt icon + capsule border. |
| R6 | Capsule top-left `Total {X}` pill is preserved. |
| R7 | Budget zone, savings box, outer frame, salary row, status badge, and est. cc bill nested meter (in budget zone) are **untouched** by this PR. |

## L2 — Design

### Data

`PartnerEconomy` already exposes:
- `bills: number` — scheduled bills total
- `estimatedCcBill: number` — projected cc statement (the "total bills amount")

We need a **new derived value** for the fill width:

```ts
// In finance-data.ts (or computed in EconomyBar)
// pctWidth helper exists already (clamps [min, 100])
const billsFillWidth = pctWidth(
  economy.bills,
  economy.bills + economy.estimatedCcBill,
  0, // no minimum — empty when no bills
);
```

Add `billsFillWidth: string` to the `EconomyBarView` type so the value is
pre-computed in `buildMonth()` and shipped with the other width strings.

### Layout (Bills zone only, current → new)

**Current (`EconomyBar.tsx` lines ~96-108):**
```
┌────────────────────────────────────────────┐
│ ▌📄  Bills                       31 500 kr │  ← single label, red zone
└────────────────────────────────────────────┘
```

**New:**
```
┌────────────────────────────────────────────┐
│ ▌📄  Bills                       31 500 kr │  ← top label (neutral)
│ ▌    Estimated cc bill          14 000 kr │  ← bottom label (red value)
│ ▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │  ← left-to-right red fill
└────────────────────────────────────────────┘
   bills/(bills+estCcBill) = 31500/45500 = 69%
```

The fill is a child `<div>` absolutely positioned at the bottom of the
`Zone` container, full height, `width: billsFillWidth`, `bg-shortfall/40`.

### Component delta

Only the inner content of the existing **Bills `Zone`** instance changes:

```tsx
<Zone
  icon={Receipt}
  title="Bills"
  valueLabel={billsLabel}
  accent="bg-shortfall"
  tint="bg-shortfall/10"
  iconColor="text-shortfall"
  className="shrink-0 pl-5 relative overflow-hidden"
  style={{ width: bar.billsWidth, minWidth: "6rem" }}
>
  {/* NEW: red fill bar (left → right) */}
  <div
    className="pointer-events-none absolute inset-y-0 left-0 bg-shortfall/40"
    style={{ width: bar.billsFillWidth }}
    aria-hidden="true"
  />
  {/* NEW: est. cc bill sub-label, below the main Bills label */}
  <div className="relative z-10 flex min-w-0 flex-1 flex-col gap-1">
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-[10px] font-medium uppercase tracking-wide leading-none text-foreground/60">
        Bills
      </span>
      <span className="text-sm font-semibold tabular-nums text-foreground">
        {billsLabel}
      </span>
    </div>
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-[9px] font-medium uppercase tracking-wide leading-none text-foreground/60">
        Estimated cc bill
      </span>
      <span className="text-[10px] font-semibold tabular-nums text-shortfall">
        {estimatedCcBillLabel}
      </span>
    </div>
  </div>
</Zone>
```

The `Zone` component itself stays as-is. We just:
1. Add `relative overflow-hidden` to its className.
2. Drop the default icon+label content (the `Zone` always renders its own
   label/value) — instead, pass `title=""` and render our own content as
   `children`. **This means `Zone` needs an opt-in `children` prop, or we
   refactor the Bills branch to render its own div from scratch.**

### Two implementation paths

**Path A (minimal Zone change):** add `children?: React.ReactNode` to `Zone`.
When provided, `Zone` skips its default label block and renders the children
inside the tinted container with the accent rail + icon still showing. The
icon is suppressed for the bills branch (Est. cc bill sub-row is the focus).

**Path B (bills-specific div):** don't reuse `Zone` for the new bills branch.
Inline a dedicated `<div>` that mimics the Zone styling. More duplication
but no shared-component API change.

**Recommended: Path A.** One prop addition, no duplication, future zones
benefit.

### Tokens used (existing — no new tokens)

- `bg-shortfall`, `bg-shortfall/40` — fill
- `text-shortfall` — est. cc bill value
- `text-foreground/60` — small uppercase labels
- `text-foreground` — Bills value
- `border-2` (capsule), `border-shortfall` (accent rail) — unchanged

### Out of scope (ship in B and C)

- Budget zone vertical `used` fill bar
- Savings box widening + status bar + difference
- Outer black frame + yellow expenses container
- Salary as full-width bottom bar
- Total pill math change

## Open questions

- None for step A. All decisions captured.

## Correction log

### 2026-07-31 — label layout revised after grill-me

User feedback: "bills number should be inside that red filled area while
estimated cc bill should be outside that area."

- **Fill math: unchanged.** `bills / (bills + estCcBill)` = 69% with sketch
  values.
- **Bills value:** now sits on the red fill (left), `text-shortfall-foreground`.
- **Est. cc bill value:** now sits in the muted remainder (right),
  `text-foreground/70`.
- **Small uppercase labels kept** on both sides, inline with their values.
- Component delta above shows the **first draft** (stacked rows). The
  **shipped** version uses a single horizontal `flex justify-between` row.

## Estimated effort

- `EconomyBar.tsx` — add `children` prop to `Zone` (~5 lines), update bills
  branch markup (~20 lines). ~30 min.
- `finance-data.ts` — add `billsFillWidth` to `EconomyBarView`, compute in
  `buildMonth` (~5 lines). ~10 min.
- Tests — extend `__tests__/EconomyBar.test.tsx` (if exists) or create with
  2-3 cases: zero denom, 50% fill, 100% fill. ~30 min.
- **Total: ~1.5 hours.** No backend changes. No API changes. Mock data only.
