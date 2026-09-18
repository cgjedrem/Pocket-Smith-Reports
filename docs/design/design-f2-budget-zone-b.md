# F2 — Budget Zone Redesign (Step B)

Status: APPROVED (design-first L1-L2 complete, ready for implementation)
Date: 2026-07-31
Repo: Pocket-Smith-Reports
Parent: `design-f2-bills.md`
Sub-area: `EconomyBar.tsx` → Budget zone (right half of capsule)
Predecessor: `design-f2-bills-zone-a.md` (Step A — bills zone, shipped)
Sibling (not in this doc): C. Savings box widening

## Summary

Replace the budget zone's nested dashed `ccUsage` meter with a **vertical
fill bar that grows bottom-to-top** behind the zone content. The fill is
`ccUsage / budget` and uses a **green → yellow → orange gradient** that
darkens as the budget is consumed. When `ccUsage > budget` the fill
caps at 100% and the **whole zone tints red** as the overspend signal.

Two values stay in the zone: `Budget + CC buys` (envelope) and
`ccUsage` (fill driver). No small uppercase labels — just the two values.

## Decisions (from grill-me, 2026-07-31)

- **Fill math:** `ccUsage / budget`, clamped `[0, 100]`. Zero denominator →
  no fill.
- **Fill direction:** **bottom → top.** Fills like a stock chart from
  baseline upward.
- **Fill color:** **gradient green → amber**, driven by the fill percentage.
  The existing palette uses `--income` (green) at the low end and
  `--savings` (amber, hue `33 90% 50%`) at the high end. We treat
  `bg-savings` as the "warning" tone for this gradient — no new token
  needed. Cut point: 0% green, 50% blend, 100% amber.
- **Overspend behavior:** cap fill at 100%, **the entire zone gets a red
  tint** (`bg-shortfall/15` or similar) signaling "over budget."
- **Labels kept:** two values, no small uppercase labels.
  - **Budget + CC buys** `{budgetLabel}` — the envelope amount
  - **CC usage** `{ccUsageLabel}` — the value driving the fill
  - `estimatedCcBill` and its dashed meter are **removed from the
    budget zone** (it already lives in the bills zone after Step A).
- **Value position:** both values at **top-right** of the zone (Budget
  primary, CC usage secondary below it).

## L1 — Requirements

| # | Requirement |
|---|---|
| R1 | Budget zone shows a vertical fill bar behind the content, growing bottom-to-top. |
| R2 | Fill width spans the full zone. Fill height = `ccUsage / budget`, clamped `[0, 100]`. |
| R3 | Fill color is a green → yellow → orange gradient driven by fill %. |
| R4 | When `ccUsage > budget` the fill caps at 100% and the entire zone background tints red. |
| R5 | The two values rendered are `Budget + CC buys` (envelope) and `CC usage` (fill driver). |
| R6 | The nested `Est. CC bill` dashed meter is **removed** from the budget zone. |
| R7 | The `estimatedCcBill` value still flows into the bills zone (Step A) and the Total pill. |
| R8 | The CreditCard icon, accent rail, and `pl-4 pr-3` padding stay. |
| R9 | Bills zone, savings box, salary, status badge, outer frame: untouched. |

## L2 — Design

### Data

`PartnerEconomy` already exposes:
- `budget: number` — envelope = `everydayBudget + ccBuys`
- `ccUsage: number` — amount charged so far
- `ccUsageLabel: string` — formatted

We need a **new derived value** for the fill height:

```ts
// In finance-data.ts buildMonth()
const budgetUsagePct = pctWidth(ccUsage, budget, 0); // 0% min, clamped 100%
const budgetOverspent = ccUsage > budget;
```

Add both to `EconomyBarView` so the component can use them:
```ts
interface EconomyBarView {
  // ... existing fields
  budgetUsageWidth: string;   // CSS width string, vertical via height in component
  budgetOverspent: boolean;
}
```

### Layout (Budget zone, current → new)

**Current:**
```
┌──────────────────────────────────────────────┐
│ ▌ 💳 Budget + CC buys       17 250 kr        │  ← top label
│ ▌                                            │
│ ▌  Est. CC bill             14 000 kr        │  ← sub-header
│ ▌  ┌─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┐  │  ← dashed bar
│ ▌  │ ▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │  │  ← ccUsage fill
│ ▌  └─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┘  │
└──────────────────────────────────────────────┘
```

**New:**
```
┌──────────────────────────────────────────────┐
│ ▌ 💳 Budget + CC buys       17 250 kr        │  ← value 1 (top-right)
│ ▌    CC usage                7 000 kr        │  ← value 2 (below)
│ ▌                                            │
│ ▌                  ░░░░░░░░░░░░░░░░░░░░░░░░ │  ← empty
│ ▌                  ░░░░░░░░░░░░░░░░░░░░░░░░ │
│ ▌                  ░░░░░░░░░░░░░░░░░░░░░░░░ │
│ ▌  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░ │  ← fill 40% (green→yellow)
│ ▌  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░ │  ← (bottom-anchored)
└──────────────────────────────────────────────┘
   ccUsage / budget = 7000 / 17250 = 40.6%
```

**Overspent variant (ccUsage > budget):**
```
┌══════════════════════════════════════════════┐  ← zone bg = red tint
│ ▌ 💳 Budget + CC buys       17 250 kr        │
│ ▌    CC usage               18 000 kr        │  ← exceeds budget
│ ▌  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │  ← cap at 100% (red)
└══════════════════════════════════════════════┘
```

### Component delta

Replace the entire `<div className="relative flex min-w-0 flex-1 flex-col border-l border-border/60 bg-muted/40 pl-4 pr-3">`
budget zone with:

```tsx
<div
  className={cn(
    "relative flex min-w-0 flex-1 flex-col border-l border-border/60 pl-4 pr-3 overflow-hidden",
    // Overspend signal: red zone background.
    bar.budgetOverspent ? "bg-shortfall/15" : "bg-muted/40",
  )}
>
  {/* Accent rail (unchanged). */}
  <span
    className="absolute inset-y-2 left-0 w-1 rounded-full bg-foreground/30 z-10"
    aria-hidden="true"
  />

  {/* Top row — values only, no uppercase labels. */}
  <div className="relative z-10 flex items-center gap-2 pb-1 pt-3">
    <CreditCard
      className="size-4 shrink-0 text-foreground/70"
      aria-hidden="true"
    />
    <div className="flex min-w-0 flex-1 items-baseline justify-between gap-2">
      <span className="truncate text-[10px] font-medium uppercase tracking-wide leading-none text-foreground/60">
        Budget + CC buys
      </span>
      <span className="shrink-0 text-sm font-semibold leading-none tabular-nums text-foreground">
        {budgetLabel}
      </span>
    </div>
  </div>
  <div className="relative z-10 flex items-baseline justify-end gap-2 pb-2">
    <span className="text-[9px] font-medium uppercase tracking-wide text-foreground/45">
      CC usage
    </span>
    <span className="text-[10px] font-semibold tabular-nums text-foreground/70">
      {ccUsageLabel}
    </span>
  </div>

  {/* F2-B: vertical fill bar, bottom-anchored, gradient by %.
      Wrapper is a flex-1 grow so the fill can size against it. */}
  <div className="relative z-0 mt-auto flex-1 min-h-[2rem]">
    <div
      className={cn(
        "absolute inset-x-0 bottom-0 rounded-t-md transition-[height,background]",
        // Gradient via Tailwind arbitrary values; stops are color tokens.
        bar.budgetUsageWidth === "0%" ? "bg-transparent" : "",
      )}
      style={{
        height: bar.budgetUsageWidth,
        background: bar.budgetOverspent
          ? "var(--shortfall)"
          : `linear-gradient(to top, var(--savings), color-mix(in srgb, var(--savings) 70%, var(--warning) 30%) 50%, var(--warning))`,
      }}
      aria-hidden="true"
    />
  </div>
</div>
```
income)` — green base (low fill)
- `var(--savings)` — amber (high fill, acts as the "warning" tone)
- `var(--shortfall)` — red (overspend + zone tint)
- `bg-muted/40` — base zone background (non-overspent)
- `bg-shortfall/15` — overspent zone background

**Gradient math:** the gradient uses `to top` so the bottom of the bar
is pure income-green and the top fades to savings-amber. No
intermediate yellow stop — the blend is handled by the gradient
interpolation itself. With Tailwind
v4 + `@theme` this reads from CSS variables. The 50% stop is a
mid-blend of savings and warning.

### Tokens used (existing — no new tokens)

- `var(--income)` (gradient base, green)
- `var(--savings)` (gradient top, amber)
- `var(--warning)` (intermediate stop)
- `var(--shortfall)` (overspend color + zone tint)
- `text-foreground`, `text-foreground/60`, `text-foreground/70`, `text-foreground/45` (label/value colors, unchanged)
- `border-border/60` (left border, unchanged)

### Out of scope (ship in C)

- Savings box widening + status bar + difference
- Outer black frame + yellow expenses container
- Salary as full-width bottom bar
- Total pill math change

## Open questions

- None for step B. All decisions captured.

## Estimated effort

- `EconomyBar.tsx` — replace budget zone inner markup (~30 lines delta).
- `finance-data.ts` — add `budgetUsageWidth` + `budgetOverspent` to
  `EconomyBarView`, compute in `buildMonth` (~5 lines).
- `types/api.ts` — add the two new fields to `EconomyBarView` interface.
- Tests — new file `economy-bar-budget-zone.test.tsx`, ~6 cases:
  zero fill, 50% fill, 100% fill, overspent, gradient render,
  no-label-uppercase-tags.
- **Total: ~1.5 hours.** No backend changes. No API changes. Mock data
  only.

## Correction log

### 2026-07-31 — initial design

User feedback (grill-me):
- fill = ccUsage / budget
- bottom → top direction
- gradient green → yellow → orange
- overspend: cap at 100%, zone tints red
- keep both values, no labels
- values stay top-right
