// Pure mappers — translate BE BillsSnapshot shape → existing component shapes.
// No side effects, no React, no API calls. Unit-testable.

import {
  BAR_SMALL_THRESHOLD,
  BUDGET_ZONE_WIDTH,
  SALARY_ZONE_FRACTION,
  formatKr,
  formatSignedKr,
} from "@/components/bills/finance-data";
import type {
  EconomyBarView,
  F2EconomyStatus,
  FinanceEvent,
  MonthData,
  PartnerEconomy,
} from "@/types/api";
import type {
  BillsEvent,
  BillsSnapshot,
  PartnerBills,
} from "@/types/bills";

// CSS width string for a part of a whole, clamped to [min, 100].
function pctWidth(part: number, whole: number, min = 0): string {
  if (whole <= 0) return `${min}%`;
  const raw = (part / whole) * 100;
  return `${Math.max(min, Math.min(100, raw))}%`;
}

function pctNum(part: number, whole: number, min = 0): number {
  if (whole <= 0) return min;
  const raw = (part / whole) * 100;
  return Math.max(min, Math.min(100, raw));
}

// Build EconomyBarView from raw PartnerBills numeric fields.
// Mirrors formulas from finance-data.ts so the existing EconomyBar renders correctly.
// Round-4.9: ccUsageOverride swaps the budget capsule / fill / overspent math
// from total card spend to FREE usage (spend outside planned CC buys). Callers
// that don't compute the split (tests, stale snapshots) omit it → total spend.
function buildBarView(partner: PartnerBills, ccUsageOverride?: number): EconomyBarView {
  const {
    salary,
    bills,
    savings_balance,
    savings_delta,
  } = partner;
  const cc_usage = ccUsageOverride ?? partner.cc_usage;
  // Pre-field snapshots lack savings_planned (raw JSON, no Pydantic
  // default) — normalize before any width/formatKr math (NaN guard).
  const savings_planned = partner.savings_planned ?? 0;
  const estimatedCcBill = partner.estimated_cc_bill ?? 0;
  // Use the populated one for display. Past → real, future → estimated.
  // PR65 review: null-aware — real 0.0 is a valid "card paid in full"
  // bill and must NOT fall through to the estimate (`||` would eat it).
  const displayCcBill = partner.real_cc_bill ?? estimatedCcBill;
  // Budget = BE everyday_budget verbatim (F2 §8). BE formula already nets
  // next month's salary, bills, and scheduled CC buys — NO FE arithmetic,
  // no add-back. Null (last sync-window month) → 0 placeholder here;
  // EconomyBar hides the whole zone on PartnerEconomy.budget == null.
  const budget = partner.everyday_budget ?? 0;

  const outflows = bills + displayCcBill;
  const remaining = salary - outflows;
  const totalBills = bills + displayCcBill;
  const fillRatio = pctNum(totalBills, salary, 0) / 100;

  return {
    billsWidth:
      salary <= 0
        ? "0%"
        : `${Math.min(totalBills / salary, 1) * SALARY_ZONE_FRACTION * 100}%`,
    budgetWidth: BUDGET_ZONE_WIDTH,
    billsFillWidth: pctWidth(bills, totalBills, 0),
    billsFillSmall: fillRatio < BAR_SMALL_THRESHOLD,
    estCcBillWidth: pctWidth(displayCcBill, Math.max(bills + displayCcBill, 1)),
    ccUsageWidth: pctWidth(cc_usage, Math.max(displayCcBill, 1)),
    // Budget zone = ccUsage vs budget (NOT salary — that mis-renders).
    budgetUsageWidth: pctWidth(cc_usage, Math.max(budget, 1), 0),
    // Overspent: ccUsage (realized card spend) > budget (planned envelope).
    // For past months this is exactly what user wants to compare.
    budgetOverspent: cc_usage > budget,
    budgetFillTone: (() => {
      // Negative or zero budget → can't compute ratio; force shortfall
      // tone (the bg tint already shows the problem visually).
      if (budget <= 0) return "shortfall" as const;
      const ratio = cc_usage / budget;
      return ratio >= 0.8
        ? ("shortfall" as const)
        : ratio >= 0.5
          ? ("warning" as const)
          : ("income" as const);
    })(),
    // F2 §13 revised: savings box = envelope (planned) + fill (actual).
    // Envelope track = savings_balance (box's existing scale) —
    // planned and |delta| both clamp against it. Null delta (future /
    // no live anchor) → width 0 + neutral tone → EconomyBar hides fill.
    savingsPlannedWidth: pctWidth(savings_planned, savings_balance, 0),
    savingsDeltaWidth:
      savings_delta == null
        ? "0%"
        : pctWidth(Math.abs(savings_delta), savings_balance, 0),
    savingsDeltaTone:
      savings_delta == null
        ? ("neutral" as const)
        : savings_delta > 0
          ? ("income" as const)
          : savings_delta < 0
            ? ("shortfall" as const)
            : ("neutral" as const),
    salaryWidth: pctWidth(salary, Math.max(outflows, 1), 6),
    upperBarWidth:
      salary <= 0
        ? "6%"
        : `${Math.max(6, Math.min(totalBills / salary, 1) * SALARY_ZONE_FRACTION * 100)}%`,
    remainingLabel:
      remaining >= 0
        ? `${formatKr(remaining)} left`
        : `${formatKr(Math.abs(remaining))} short`,
    remainingTone: remaining >= 0 ? "income" : "shortfall",
    netLabel: formatKr(partner.net),
  };
}

// Map one partner block → existing PartnerEconomy shape.
// Budget = BE `everyday_budget` verbatim (F2 §8 locked formula computed
// server-side). Null → budget zone hidden (same null-gate pattern as
// realBills/savingsDelta).
export function mapPartnerToEconomy(
  partner: PartnerBills,
  freeCcUsage: number | null = null,
): PartnerEconomy {
  const estimatedCcBill = partner.estimated_cc_bill ?? 0;
  // PR65 review: null-aware — real 0.0 (card paid in full) must not fall
  // through to the estimate.
  const displayCcBill = partner.real_cc_bill ?? estimatedCcBill;
  // Budget = BE everyday_budget passthrough. Negative stays negative.
  const budget = partner.everyday_budget;
  // Round-4.9: budget capsule shows FREE usage (outside planned buys) when
  // the caller passed the split; otherwise total real card spend.
  const ccUsage = freeCcUsage ?? partner.cc_usage;

  return {
    // US4 identity triple — id/slot "" on legacy files → neutral mode.
    partner: {
      partner_id: partner.partner_id ?? "",
      partner_slot: partner.partner_slot ?? "",
      label: partner.partner,
    },
    estimatedSalary: partner.salary,
    bills: partner.bills,
    budget,
    ccUsage,
    estimatedCcBill: displayCcBill,
    realCcBill: partner.real_cc_bill,
    realCcBillLabel:
      partner.real_cc_bill != null ? formatKr(partner.real_cc_bill) : "",
    savingsBalance: partner.savings_balance,
    savingsContribution: partner.savings_transfer,
    savingsPlanned: partner.savings_planned ?? 0,
    savingsDelta: partner.savings_delta,
    net: partner.net,
    status: partner.status as F2EconomyStatus,
    estimatedSalaryLabel: formatKr(partner.salary),
    billsLabel: formatKr(partner.bills),
    // Null budget → empty label. EconomyBar hides the whole zone on
    // budget == null, same gate pattern as realBillsLabel.
    budgetLabel: budget != null ? formatKr(budget) : "",
    ccUsageLabel: formatKr(ccUsage),
    ccUsageIsFree: freeCcUsage != null,
    estimatedCcBillLabel: formatKr(displayCcBill),
    // F2-UI L2 amendment 2026-08-03: past-only posted-txn sum.
    // Null for current/future — UI uses that as the past-month gate.
    realBills: partner.real_bills,
    realBillsLabel:
      partner.real_bills != null ? formatKr(partner.real_bills) : "",
    // F2 grid R2: scheduled CC buys sum. BE always sends it; stale
    // snapshots lacking the field map to null (line hidden).
    plannedCcBuys: partner.planned_cc_buys ?? null,
    plannedCcBuysLabel:
      partner.planned_cc_buys != null ? formatKr(partner.planned_cc_buys) : "",
    // F2 grid R3: real CC spend per category title (free-budget tab).
    // Stale snapshots → undefined → null (section hidden).
    ccUsageByCategory: partner.cc_usage_by_category ?? null,
    savingsBalanceLabel: formatKr(partner.savings_balance),
    savingsContributionLabel: formatKr(partner.savings_transfer),
    savingsPlannedLabel: formatKr(partner.savings_planned ?? 0),
    // Null delta → empty label. EconomyBar hides fill + value on null,
    // same gate pattern as realBillsLabel ("" when null).
    savingsDeltaLabel:
      partner.savings_delta != null ? formatSignedKr(partner.savings_delta) : "",
    bar: buildBarView(partner, freeCcUsage ?? undefined),
  };
}

// Map one BE event → existing FinanceEvent shape.
// BillsEvent.amount sign convention: positive = income, negative = expense (matches FinanceEvent).
// Contract: BE title=category, BE account=bank name → FE same semantics.
// Round-4 fix: pass through type unchanged (bill/buy/salary/savings) —
// only an unrecognized future BE type value defensively maps to "bill".
// Previously all non-"buy" types coerced to "bill", which leaked salary
// and savings events into BudgetTab's Bills-budget group/total.
export function mapEvent(event: BillsEvent): FinanceEvent {
  const KNOWN_TYPES = ["bill", "buy", "salary", "savings"] as const;
  const type = (KNOWN_TYPES as readonly string[]).includes(event.type)
    ? (event.type as FinanceEvent["type"])
    : "bill";
  return {
    id: event.id,
    date: event.date,
    day: event.day,
    title: event.title,
    type,
    account: event.account,
    // US4 identity triple — id/slot "" on legacy files → neutral mode.
    partner: {
      partner_id: event.partner_id ?? "",
      partner_slot: event.partner_slot ?? "",
      label: event.partner,
    },
    amount: event.amount,
    // Match flags passthrough (buy-row ✓/✗ chips). Undefined on stale
    // fixtures → treated as "unknown" by the null gate downstream.
    isMatched: event.is_matched ?? null,
    isCcPayment: event.is_cc_payment ?? false,
  };
}

// Map BE snapshot → single MonthData entry (current month).
// Budget zone needs no cross-month lookup — everyday_budget comes
// pre-computed per partner from the BE.
// Net = sum of partner nets (or 0 if no partners).
export function mapSnapshotToMonthData(snapshot: BillsSnapshot): MonthData {
  const [yearStr, monthStr] = snapshot.month.split("-");
  const year = Number(yearStr);
  const monthIndex = Number(monthStr) - 1;
  const events = snapshot.partners
    .flatMap((p) => p.events)
    .map(mapEvent)
    .sort((a, b) => a.day - b.day);
  const net = snapshot.partners.reduce((sum, p) => sum + p.net, 0);
  return {
    key: snapshot.month,
    label: snapshot.month_label,
    year,
    monthIndex,
    events,
    billsCount: snapshot.bills_count,
    buysCount: snapshot.buys_count,
    net,
    partners: snapshot.partners.map((p) =>
      mapPartnerToEconomy(p, computeFreeCcUsage(p)),
    ),
  };
}

// Round-4.9: free usage = real CC spend NOT covered by a planned CC buy
// envelope (same carve-out BudgetTab's FREE group applies, same category
// keys). Null when BE sent no per-category split (stale snapshot) — caller
// falls back to total spend.
function computeFreeCcUsage(partner: PartnerBills): number | null {
  const byCategory = partner.cc_usage_by_category;
  if (byCategory == null) return null;
  const plannedTitles = new Set(
    partner.events
      .filter((e) => e.type === "buy")
      .map((e) => e.title || "Uncategorized"),
  );
  return Object.entries(byCategory).reduce(
    (sum, [category, value]) =>
      plannedTitles.has(category) ? sum : sum + value,
    0,
  );
}

// Flatten all events from snapshot (excludes Income/Savings transfers like mock).
// Stamps each event with its month label so the existing TableView
// month filter / grouping keeps working.
export function mapSnapshotToEvents(
  snapshot: BillsSnapshot,
): (FinanceEvent & { monthLabel: string })[] {
  return snapshot.partners
    .flatMap((p) => p.events)
    .filter((e) => e.title !== "Income" && e.title !== "Savings")
    .map((e) => ({ ...mapEvent(e), monthLabel: snapshot.month_label }));
}
