// F2 — Bills dashboard mock data. Ported from v0 design (f2-import/lib/finance-data.ts).
// REPLACE WITH REAL API: this is in-browser mock only. When F2-BE lands, swap
// `getMonths()` + `getAllEvents()` for `client/src/api/events.ts` calls.
//
// Deterministic PRNG → stable data across renders. No backend calls.

import type {
  EconomyBarView,
  F2PartnerIdentity,
  FinanceEvent,
  MonthData,
  PartnerEconomy,
  PartnerSlot,
} from "@/types/api";

export const PARTNERS: F2PartnerIdentity[] = [
  { partner_id: "partner_a", partner_slot: "a", label: "Fixture A" },
  { partner_id: "partner_b", partner_slot: "b", label: "Fixture B" },
];

// Partner accent by BE-assigned slot: "a" → teal, "b" → violet, missing
// (legacy payload) → neutral gray. Never label text, never payload position.
export function partnerDotClass(slot: PartnerSlot | undefined): string {
  if (slot === "a") return "bg-partner-a";
  if (slot === "b") return "bg-partner-b";
  return "bg-muted-foreground";
}

// Identity-neutral = at least one row AND all rows are legacy/no semantic partner ids.
// Empty list is not neutral (no data → no hint). Neutral surfaces: no partner colors,
// no partner filter, no per-partner breakdowns — never positional inference.
export function isIdentityNeutral<T extends { partner: { partner_id: string } }>(
  items: T[],
): boolean {
  return items.length > 0 && items.every((p) => p.partner.partner_id === "");
}

// Hint copy shown wherever identity features are suppressed by neutral mode.
export const IDENTITY_NEUTRAL_HINT =
  "Re-sync to restore the per-partner view.";

// Event↔economy partner match: semantic key when both sides carry one,
// else label within this snapshot (legacy mode — labels stay attached to
// their own block's events, so in-snapshot label match is safe).
export function samePartnerIdentity(
  a: F2PartnerIdentity,
  b: F2PartnerIdentity,
): boolean {
  if (a.partner_id !== "" && b.partner_id !== "") {
    return a.partner_id === b.partner_id;
  }
  return a.label === b.label;
}

const SLOT_ORDER: Record<PartnerSlot, number> = { a: 0, b: 1, "": 2 };

// Display order by BE-assigned slot; legacy payloads (slot "") fall back
// to label for deterministic rendering. Never payload position.
export function byDisplayOrder<T extends { partner: F2PartnerIdentity }>(
  items: T[],
): T[] {
  return [...items].sort(
    (a, b) =>
      SLOT_ORDER[a.partner.partner_slot] - SLOT_ORDER[b.partner.partner_slot] ||
      a.partner.label.localeCompare(b.partner.label),
  );
}

const BILL_CATEGORIES: Record<string, string[]> = {
  Housing: ["Rent", "Home insurance", "Property tax"],
  Utilities: ["Electricity", "Water", "Heating", "Internet", "Mobile plan"],
  Living: ["Groceries", "Daycare", "Gym membership", "Public transport"],
  Subscriptions: ["Streaming bundle", "Cloud storage", "News subscription"],
  Debt: ["Car loan", "Student loan", "Credit card"],
};

const BUY_ITEMS = [
  ["Electronics", "New laptop"],
  ["Electronics", "Wireless headphones"],
  ["Furniture", "Standing desk"],
  ["Furniture", "Living room chair"],
  ["Travel", "Weekend trip"],
  ["Travel", "Summer flights"],
  ["Home", "Kitchen appliance"],
  ["Gifts", "Birthday gift"],
  ["Clothing", "Winter jacket"],
  ["Hobby", "Camera lens"],
];

// Deterministic PRNG — same seed → same numbers across renders.
function mulberry32(seed: number) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

function pick<T>(rand: () => number, arr: T[]): T {
  return arr[Math.floor(rand() * arr.length)];
}

function round(n: number, step = 10) {
  return Math.round(n / step) * step;
}

// CSS width string for a part of a whole, clamped to [min, 100].
// Whole <= 0 returns `min` (avoids divide-by-zero; zero denominator
// renders as 0% by convention). Part > whole clamps to 100% by
// design — callers that care about over-100% should validate first.
function pctWidth(part: number, whole: number, min = 0): string {
  const raw = (part / Math.max(whole, 1)) * 100;
  return `${Math.max(min, Math.min(100, raw))}%`;
}

// Numeric percent in [min, 100] — same clamp semantics as pctWidth but
// returns a number for comparisons (e.g. "is this bar small?").
function pctNum(part: number, whole: number, min = 0): number {
  const raw = (part / Math.max(whole, 1)) * 100;
  return Math.max(min, Math.min(100, raw));
}

// F2: bills bar is "small" when totalBills / salary < this threshold.
// Drives whether the EconomyBar shows inline labels (big bar) or
// moves them to an external labels list (small bar). At 0.7 the
// capsule stays wide enough for the inline labels to fit cleanly
// without wrapping in most partner-card layouts.
export const BAR_SMALL_THRESHOLD = 0.7;

// Upper bar = the capsule row showing Bills + est. CC bill combined.
// The capsule lives in the partner card row, but we want its width to be
// comparable to the salary zone (which sits beside the savings box, ~65.9% of
// the partner card row).
//   upperBarWidth% = (outflow / salary) * salaryZoneFraction
// so when outflow < salary the bar is contained in the salary zone and when
// outflow > salary the bar overflows past it visually.
export const SALARY_ZONE_FRACTION = 0.659;

// Budget zone is a constant 18% slice of the salary zone.
// Width = 18% × 65.9% = 11.862% of the partner card row. Wide
// enough to host the icon + "Budget" label + value + vertical fill
// + "CC usage" label + value without clipping.
export const BUDGET_ZONE_RATIO = 0.18;
export const BUDGET_ZONE_WIDTH = `${SALARY_ZONE_FRACTION * BUDGET_ZONE_RATIO * 100}%`;

// Bills zone width = full capsule width (bills is the only zone now —
// the budget bar lives outside the capsule as its own column). Scales
// with totalBills/salary. Clamped to 0% so tiny salaries can't produce
// a negative width. The BUDGET_ZONE_RATIO constant is preserved for
// any future re-integration but no longer subtracted here.
export function billsZoneWidth(
  bills: number,
  estimatedCcBill: number,
  salary: number,
): string {
  if (salary <= 0) return "0%";
  const total = bills + estimatedCcBill;
  const outerRatio = Math.min(total / salary, 1) * SALARY_ZONE_FRACTION;
  return `${outerRatio * 100}%`;
}

export function upperBarWidth(
  bills: number,
  estimatedCcBill: number,
  salary: number,
  min = 6,
): string {
  if (salary <= 0) return `${min}%`;
  const totalBills = bills + estimatedCcBill;
  // F2 contract: capsule width = (outflow / salary) × SALARY_ZONE_FRACTION,
  // clamped to [min, SALARY_ZONE_FRACTION × 100]. When outflow > salary
  // the bar stops at the salary zone width — the "X KR SHORT" / savings
  // delta text already communicates the shortfall. No overflow.
  const ratio = Math.max(
    min,
    Math.min(totalBills / salary, 1) * SALARY_ZONE_FRACTION * 100,
  );
  return `${ratio}%`;
}

function daysInMonth(year: number, monthIndex: number) {
  return new Date(year, monthIndex + 1, 0).getDate();
}

export function formatKr(n: number): string {
  const sign = n < 0 ? "-" : "";
  const abs = Math.abs(Math.round(n));
  return `${sign}${abs.toLocaleString("en-US")} kr`;
}

// F2-C: format with explicit + or − sign. Used for the savings delta value
// so positive deltas show a leading "+" matching how contributions used to.
// Zero returns "0 kr" without a sign — neutral tone, intentionally unsigned.
export function formatSignedKr(n: number): string {
  if (n === 0) return formatKr(0);
  return n > 0 ? `+${formatKr(n)}` : formatKr(n);
}

export function formatDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  return date.toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
}

export function getEconomyStatus(
  estimatedSalary: number,
  bills: number,
  estimatedCcBill: number,
  savingsBalance: number,
): PartnerEconomy["status"] {
  const salaryAfterBills = estimatedSalary - bills;
  if (salaryAfterBills >= estimatedCcBill) return "covered";
  if (salaryAfterBills + savingsBalance >= estimatedCcBill) return "partial";
  return "shortfall";
}

function buildMonth(
  base: Date,
  offset: number,
  openingSavings: Record<string, number>,
): MonthData {
  const d = new Date(base.getFullYear(), base.getMonth() + offset, 1);
  const year = d.getFullYear();
  const monthIndex = d.getMonth();
  const key = `${year}-${String(monthIndex + 1).padStart(2, "0")}`;
  const rand = mulberry32(year * 100 + monthIndex);
  const dim = daysInMonth(year, monthIndex);

  const events: FinanceEvent[] = [];
  type Acc = { salary: number; savings: number; bills: number; ccBuys: number };
  // Accumulator keyed by semantic identity — labels stay display-only.
  const perPartner: Record<string, Acc> = {
    partner_a: {
      salary: round(38000 + rand() * 8000, 100),
      savings: 0,
      bills: 0,
      ccBuys: 0,
    },
    partner_b: {
      salary: round(34000 + rand() * 8000, 100),
      savings: 0,
      bills: 0,
      ccBuys: 0,
    },
  };

  // Salary income events (25th) + a monthly savings transfer (26th).
  for (const partner of PARTNERS) {
    events.push({
      id: `${key}-salary-${partner.partner_id}`,
      date: `${key}-25`,
      day: 25,
      title: `Salary — ${partner.label}`,
      type: "bill",
      category: "Income",
      partner,
      amount: perPartner[partner.partner_id].salary,
    });
    const savings = round(3000 + rand() * 6000, 100);
    perPartner[partner.partner_id].savings = savings;
    events.push({
      id: `${key}-savings-${partner.partner_id}`,
      date: `${key}-26`,
      day: 26,
      title: `Savings transfer — ${partner.label}`,
      type: "bill",
      category: "Savings",
      partner,
      amount: -savings,
    });
  }

  // Bills.
  const billCount = 10 + Math.floor(rand() * 5);
  const catKeys = Object.keys(BILL_CATEGORIES);
  for (let i = 0; i < billCount; i++) {
    const cat = pick(rand, catKeys);
    const title = pick(rand, BILL_CATEGORIES[cat]);
    const partner = pick(rand, PARTNERS);
    const amount = round(400 + rand() * 6000, 10);
    const day = 1 + Math.floor(rand() * Math.min(28, dim - 1));
    perPartner[partner.partner_id].bills += amount;
    events.push({
      id: `${key}-bill-${i}`,
      date: `${key}-${String(day).padStart(2, "0")}`,
      day,
      title,
      type: "bill",
      category: cat,
      partner,
      amount: -amount,
    });
  }

  // Scheduled buys.
  const buyCount = 2 + Math.floor(rand() * 3);
  for (let i = 0; i < buyCount; i++) {
    const [cat, title] = pick(rand, BUY_ITEMS);
    const partner = pick(rand, PARTNERS);
    const amount = round(1500 + rand() * 12000, 50);
    const day = 1 + Math.floor(rand() * Math.min(28, dim - 1));
    perPartner[partner.partner_id].ccBuys += amount;
    events.push({
      id: `${key}-buy-${i}`,
      date: `${key}-${String(day).padStart(2, "0")}`,
      day,
      title,
      type: "buy",
      category: cat,
      partner,
      amount: -amount,
    });
  }

  events.sort((a, b) => a.day - b.day);

  const partners: PartnerEconomy[] = PARTNERS.map((partner) => {
    const p = perPartner[partner.partner_id];
    // MOCK-ONLY budget math. Live path = BE everyday_budget passthrough
    // (bills-mapper.ts, F2 §8); this synthetic data is never served by
    // the API so it keeps its own simple envelope formula.
    const budget = p.salary - p.bills - p.ccBuys;
    // The projected statement is the share of the budget that lands on the card.
    const estimatedCcBill = round(budget * (0.45 + rand() * 0.4), 100);
    // How much of that statement has actually been charged so far.
    const ccUsage = round(estimatedCcBill * (0.3 + rand() * 0.55), 100);
    // This month's transfer grows the running savings-account balance.
    const savingsContribution = p.savings;
    // F2-C: this-month net change to savings. Random mock; can be negative.
    // Range: -50% of contribution to +50% of contribution (clamped to ±
    // 1.5× contribution), or 0 for very small contributions.
    let savingsDelta: number;
    if (savingsContribution <= 0) {
      savingsDelta = 0;
    } else {
      const swing = (rand() - 0.5) * savingsContribution * 3; // -1.5× to +1.5×
      savingsDelta = round(swing, 100);
    }
    const savingsBalance = round(
      openingSavings[partner.partner_id] + savingsContribution,
      100,
    );
    openingSavings[partner.partner_id] = savingsBalance;
    const net = p.salary - p.bills - estimatedCcBill;
    const status = getEconomyStatus(
      p.salary,
      p.bills,
      estimatedCcBill,
      savingsBalance,
    );

    // F2 §13 revised: planned savings envelope. Static, event-derived:
    // salary − bills − est CC bill (mock has no real_cc_bill). Can be
    // negative → clamped to 0 (envelope can't be negative visually).
    const savingsPlanned = Math.max(0, p.salary - p.bills - estimatedCcBill);
    // Pre-compute every value the capsule bar needs to render.
    const outflows = p.bills + estimatedCcBill; // what salary must cover
    const remaining = p.salary - outflows;
    const totalBills = p.bills + estimatedCcBill;
    const bar: EconomyBarView = {
      // Bills zone width = capsule outer − budget zone. Scales with
      // totalBills/salary so the capsule visually reflects how much of
      // salary the outflow consumes.
      billsWidth: billsZoneWidth(p.bills, estimatedCcBill, p.salary),
      // Constant budget slice width = 7% of salary zone (4.613% of row).
      // Same value for every month so the capsule's right edge never moves.
      budgetWidth: BUDGET_ZONE_WIDTH,
      // Inner red bar fill = bills share of totalBills. Shows how much
      // of the capsule's outflow is real bills (vs estimated cc bill).
      billsFillWidth: pctWidth(p.bills, totalBills, 0),
      // Cutoff: totalBills/salary < BAR_SMALL_THRESHOLD → "small bar" →
      // render the external labels list instead of inline labels.
      billsFillSmall:
        pctNum(totalBills, p.salary, 0) / 100 < BAR_SMALL_THRESHOLD,
      estCcBillWidth: pctWidth(estimatedCcBill, budget),
      ccUsageWidth: pctWidth(ccUsage, estimatedCcBill),
      // F2-B: vertical fill in the budget zone = ccUsage / budget.
      budgetUsageWidth: pctWidth(ccUsage, budget, 0),
      budgetOverspent: ccUsage > budget,
      // F2-B: discrete fill tone by usage bucket.
      // usageRatio < 0.5 → income (green), 0.5-0.8 → warning (yellow),
      // > 0.8 → shortfall (red). overspent (ratio ≥ 1) also red.
      // Computed once to avoid repeat division + keep boundary
      // semantics explicit: ratio === 1 (at-budget) tints red.
      budgetFillTone: (() => {
        const ratio = ccUsage / Math.max(budget, 1);
        return ratio >= 0.8 ? "shortfall" : ratio >= 0.5 ? "warning" : "income";
      })(),
      // F2 §13 revised: savings envelope (planned) + fill (actual).
      // Mock always has a delta (never null — mock is "current month").
      savingsPlannedWidth: pctWidth(savingsPlanned, savingsBalance, 0),
      savingsDeltaWidth: pctWidth(Math.abs(savingsDelta), savingsBalance, 0),
      savingsDeltaTone:
        savingsDelta > 0
          ? "income"
          : savingsDelta < 0
            ? "shortfall"
            : "neutral",
      salaryWidth: pctWidth(p.salary, outflows, 6),
      upperBarWidth: upperBarWidth(p.bills, estimatedCcBill, p.salary),
      remainingLabel:
        remaining >= 0
          ? `${formatKr(remaining)} left`
          : `${formatKr(Math.abs(remaining))} short`,
      remainingTone: remaining >= 0 ? "income" : "shortfall",
      netLabel: formatKr(net),
    };

    return {
      partner,
      estimatedSalary: p.salary,
      bills: p.bills,
      budget,
      ccUsage,
      estimatedCcBill,
      savingsBalance: savingsBalance,
      savingsContribution: savingsContribution,
      savingsPlanned,
      // F2-C: this-month net change to savings (mock).
      savingsDelta: savingsDelta,
      net: net,
      status,
      estimatedSalaryLabel: formatKr(p.salary),
      billsLabel: formatKr(p.bills),
      budgetLabel: formatKr(budget),
      ccUsageLabel: formatKr(ccUsage),
      estimatedCcBillLabel: formatKr(estimatedCcBill),
      savingsBalanceLabel: formatKr(savingsBalance),
      savingsContributionLabel: formatKr(savingsContribution),
      savingsPlannedLabel: formatKr(savingsPlanned),
      // F2-C: signed delta label (e.g. "+2,000 kr", "-1,500 kr", "0 kr").
      savingsDeltaLabel: formatSignedKr(savingsDelta),
      bar,
    };
  });

  // Count actual bills (exclude Income + Savings transfers).
  const billsCount = events.filter(
    (e) => e.type === "bill" && e.amount < 0 && e.category !== "Savings",
  ).length;
  const buysCount = events.filter((e) => e.type === "buy").length;
  const net = events.reduce((sum, e) => sum + e.amount, 0);

  return {
    key,
    label: `${MONTH_NAMES[monthIndex]} ${year}`,
    year,
    monthIndex,
    events,
    billsCount,
    buysCount,
    net,
    partners,
  };
}

export function getMonths(): MonthData[] {
  const base = new Date(2026, 6, 1); // July 2026 as "current" for the mock.
  // Starting balances already sitting in each savings account — keyed by
  // semantic identity, never by label.
  const openingSavings: Record<string, number> = {
    partner_a: 84000,
    partner_b: 61500,
  };
  return Array.from({ length: 12 }, (_, i) =>
    buildMonth(base, i, openingSavings),
  );
}

export function getAllEvents(): (FinanceEvent & { monthLabel: string })[] {
  return getMonths().flatMap((m) =>
    m.events
      .filter((e) => e.category !== "Income" && e.category !== "Savings")
      .map((e) => ({ ...e, monthLabel: m.label })),
  );
}
