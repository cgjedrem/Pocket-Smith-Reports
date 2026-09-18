# F2 — Savings Box Redesign (Step C)

Status: APPROVED (design-first L1-L2 complete, ready for implementation)
Date: 2026-07-31
Repo: Pocket-Smith-Reports
Parent: `design-f2-bills.md`
Sub-area: `EconomyBar.tsx` → Savings box (right side of resources row)
Predecessor: `design-f2-bills-zone-a.md` (Step A — bills zone, shipped)
Predecessor: `design-f2-budget-zone-b.md` (Step B — budget zone, shipped)

## Summary

Replace the thin savings pill (`w-44 sm:w-52`, 36px tall) with a **taller
savings box** that grows vertically to roughly the height of the capsule
above it (~h-28 / 112px). The box contains:
- A `SAVINGS` label + `Total savings {balance}` value
- A **new `savingsDelta` value** (can be negative) with sign-aware tone
  (green when +, red when −)
- A **vertical status bar** anchored to the right edge, growing
  bottom→top, fill = `|savingsDelta| / savingsBalance` clamped `[0, 100]`
- The existing `+{savingsContributionLabel}` indicator is **removed** and
  replaced by the new `savingsDelta` value

Salary bar stays as-is on the left side of the resources row (h-9 / 36px).
The savings box's extra height makes it visually distinct without
restructuring the whole layout.

## Decisions (from grill-me, 2026-07-31)

- **New field:** `savingsDelta: number` on `PartnerEconomy`. Random in mock
  data, can be negative. Separate from `net` (salary − bills − estCcBill)
  which is a different concept.
- **Box dimensions:** w-72 (288px) wide, **h-36 (144px) tall** = salary
  pill height (h-9, 36px) + capsule height (h-28, 112px) − padding. Salary
  pill keeps its h-9 (36px) on the left, no longer stretches.
  Resources row uses `items-end` so the salary pill **bottom-aligns**
  with the savings box's bottom edge (both end at the same y).
- **Status bar:** vertical, anchored to the **right edge** of the box,
  growing **bottom→top**. Fill = `|savingsDelta| / savingsBalance` clamped
  `[0, 100]`. Zero denominator = 0% fill.
- **Status bar color:** matches the difference sign.
  - `savingsDelta > 0` → `bg-income` (green)
  - `savingsDelta < 0` → `bg-shortfall` (red)
  - `savingsDelta === 0` → no fill (empty bar)
- **Difference value tone:** same tokens. Green when +, red when −,
  prefixed with `+` or `−` sign explicitly.
- **Existing indicator:** the `+{savingsContributionLabel}` chip is
  **removed**. Replaced by the new `savingsDelta` value.
- **Salary bar:** unchanged. Stays at h-9 (36px) on the left of the row.
  Items-stretch on the row makes the savings box take the extra vertical
  space without the salary bar growing.

## L1 — Requirements

| # | Requirement |
|---|---|
| R1 | Savings box is w-72 (288px) wide, h-36 (144px) tall. |
| R2 | Box shows `SAVINGS` label + `Total savings {balance}` value. |
| R3 | Box shows a new `savingsDelta` value with explicit `+` or `−` sign. |
| R4 | Tone of `savingsDelta` value: green when +, red when −. |
| R5 | Vertical status bar on the right edge of the box, fill = `|savingsDelta| / savingsBalance` clamped `[0, 100]`. |
| R6 | Status bar color: green when delta > 0, red when delta < 0, no fill when delta === 0. |
| R7 | Existing `+{savingsContributionLabel}` indicator is removed. |
| R8 | Salary bar, status badge, capsule, bills zone, budget zone: untouched. |

## L2 — Design

### Data

`PartnerEconomy` already exposes:
- `savingsBalance: number` — running savings account balance
- `savingsContribution: number` — this-month transfer into savings
- `savingsBalanceLabel: string` — formatted balance
- `savingsContributionLabel: string` — formatted contribution

We need **two new fields**:
- `savingsDelta: number` — this-month net change to savings (random mock, can be negative)
- `savingsDeltaLabel: string` — formatted with `+` or `−` sign

`bar.savingsDeltaTone: "income" | "shortfall" | "neutral"` — for the value tone.
Neutral when `savingsDelta === 0`.

Add to `PartnerEconomy`:
```ts
savingsDelta: number;
savingsDeltaLabel: string;
```

Add to `EconomyBarView`:
```ts
savingsDeltaWidth: string;  // CSS height string for the vertical bar
savingsDeltaTone: "income" | "shortfall" | "neutral";
```

### Layout (current → new)

**Current:**
```
┌──────────────────────────────────────────────────────┐
│ ▌ 💳 Budget + CC buys      17 250 kr                 │
│ ▌          CC usage        4 600 kr                  │  (fill bar inside)
└──────────────────────────────────────────────────────┘
┌─────────────────────────────────┐ ┌──────────────────┐
│ 💰 Estimated salary 44 000 kr   │ │ 🐷 SAVINGS 20k   │  ← thin pill
│         1 500 kr short           │ │       +3 000 kr  │     (h-9)
└─────────────────────────────────┘ └──────────────────┘
   flex-1, h-9                       w-44 sm:w-52
```

**New:**
```
┌──────────────────────────────────────────────────────┐
│ ▌ 💳 Budget + CC buys      17 250 kr                 │  (capsule, h-28)
│ ▌          CC usage        4 600 kr                  │
└──────────────────────────────────────────────────────┘
┌───────────────────────┐ ┌───────────────────────────┐
│ 💰 Estimated salary...│ │ 🐷 SAVINGS                │  (resources row, h-28
│                       │ │   Total savings  20 000  │   via items-stretch)
│                       │ │   Δ savings     -2 000   │ ← red value
│                       │ │              ▓▓▓░░░░░    │ ← vertical bar (right)
└───────────────────────┘ └───────────────────────────┘
   flex-1, h-9                w-72, h-28 (fills row)
```

**Overspent/empty state:**
```
┌───────────────────────┐ ┌───────────────────────────┐
│ 💰 Estimated salary...│ │ 🐷 SAVINGS                │
│                       │ │   Total savings  20 000  │
│                       │ │   Δ savings       0 kr   │ ← neutral
│                       │ │              ░░░░░░░░    │ ← no fill (delta = 0)
└───────────────────────┘ └───────────────────────────┘
```

### Component delta

Replace the existing savings pill with:

```tsx
{/* F2-C: savings box — taller (h-28), wider (w-72), with status bar. */}
<div
  className={cn(
    "relative flex w-72 shrink-0 flex-col items-stretch justify-between overflow-hidden rounded-2xl border bg-income/10 pl-4 pr-3 py-2",
  )}
>
  {/* Accent rail on the left edge. */}
  <span
    className="pointer-events-none absolute inset-y-2 left-0 w-1 rounded-full bg-income"
    aria-hidden="true"
  />
  <PiggyBank
    className="pointer-events-none absolute right-3 top-2 size-4 shrink-0 text-income"
    aria-hidden="true"
  />

  {/* Top: label + balance. */}
  <div className="flex flex-col gap-0.5">
    <span className="text-[9px] font-medium uppercase tracking-wide leading-none text-foreground/60">
      Savings
    </span>
    <span className="text-base font-semibold leading-tight tabular-nums text-foreground">
      {savingsBalanceLabel}
    </span>
  </div>

  {/* Bottom: delta value + vertical status bar. */}
  <div className="flex items-end justify-between gap-2">
    <div className="flex flex-col gap-0.5">
      <span className="text-[9px] font-medium uppercase tracking-wide leading-none text-foreground/45">
        Δ savings
      </span>
      <span
        className={cn(
          "text-sm font-semibold leading-none tabular-nums",
          bar.savingsDeltaTone === "income" && "text-income",
          bar.savingsDeltaTone === "shortfall" && "text-shortfall",
          bar.savingsDeltaTone === "neutral" && "text-foreground/60",
        )}
      >
        {savingsDeltaLabel}
      </span>
    </div>
    {/* F2-C: vertical status bar. */}
    <div
      className="relative w-1.5 self-stretch overflow-hidden rounded-full bg-foreground/10"
      aria-hidden="true"
    >
      <div
        className={cn(
          "absolute inset-x-0 bottom-0 rounded-full",
          bar.savingsDeltaTone === "income" && "bg-income",
          bar.savingsDeltaTone === "shortfall" && "bg-shortfall",
          bar.savingsDeltaTone === "neutral" && "bg-transparent",
        )}
        style={{ height: bar.savingsDeltaWidth }}
      />
    </div>
  </div>
</div>
```

The resources row parent changes from `items-stretch` (already there) but
the salary bar gets `self-stretch` so it centers vertically in the now-tall
row.

### Tokens used (existing — no new tokens)

- `bg-income` (delta positive, status bar positive, accent rail)
- `bg-shortfall` (delta negative, status bar negative)
- `bg-income/10` (savings box background tint, current)
- `text-income`, `text-shortfall`, `text-foreground/60` (text colors)
- `text-foreground/45`, `text-foreground/60` (label colors)
- `border` (box border)

### Out of scope (no further steps)

- Outer black frame + yellow expenses container
- Salary as full-width bottom bar
- Total pill math change
- New sub-design docs after C

## Open questions

- None for step C. All decisions captured.

## Estimated effort

- `EconomyBar.tsx` — replace savings pill markup (~40 lines delta).
- `finance-data.ts` — add `savingsDelta` (random mock) +
  `savingsDeltaLabel` to `PartnerEconomy`. Add `savingsDeltaWidth` +
  `savingsDeltaTone` to `EconomyBarView`, compute in `buildMonth` (~10 lines).
- `types/api.ts` — add 4 new fields to the two interfaces.
- Tests — new file `economy-bar-savings-box.test.tsx`, ~6 cases:
  label + value present, delta sign tone, status bar fill width,
  zero delta = no fill, negative delta = red, positive delta = green.
- **Total: ~1.5 hours.** No backend changes. No API changes. Mock data only.

## Correction log

### 2026-07-31 — initial design

User feedback (grill-me):
- "just grow the savings capsule vertically" — savings box becomes taller
  than salary pill, items-stretch on the row does the work.
- Status bar: vertical, bottom→top, fill = |contribution - ccUsage| / balance.
- Difference value: new `savingsDelta` field, random in mock.
- Tone: match existing income/shortfall tokens.
- `+{contribution}` indicator removed.

### 2026-07-31 — height correction after grill-me

User feedback: "only grow the savings bar so that it is equal height to
salary bar plus bills bar". Translated: savings box height = salary pill
(h-9, 36px) + capsule (h-28, 112px) = 148px → use `h-36` (144px, the
nearest tailwind step). Salary pill no longer stretches (was h-9
but rows-stretched it to match the row); kept at h-9 explicitly.

### 2026-07-31 — placement correction after grill-me

User feedback: "heights are correct but placements are wrong".
Changed resources row from `items-center` to `items-end` so the salary
pill bottom-aligns with the savings box's bottom edge. Previously the
salary pill was centered in the 144px row, leaving a 54px gap below it
(salary bottom 568, savings bottom 622). Now both elements end at the
same y (~622).
