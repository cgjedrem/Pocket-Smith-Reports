// TS types — match backend Pydantic models exactly.
// Source: src/budget_api/models/*.py + design doc L4.

export interface RowCounts {
  transactions: number;
  events: number;
  budget: number;
  categories: number;
  accounts: number;
}

export interface SyncResult {
  timestamp: string;
  start_month: string;
  end_month: string;
  months_synced: number;
  row_counts: RowCounts;
  errors: string[];
  duration_ms: number;
}

export interface SyncStatus {
  status: "running" | "success" | "failed";
  last_sync: string;
  start_month: string;
  end_month: string;
  months_synced: number;
  row_counts: RowCounts;
  errors: string[];
  duration_ms: number;
}

export interface Partner {
  id: string;
  label: string;
}

export interface PartnerCreate {
  label: string;
}

export interface PartnerUpdate {
  label: string;
}

export interface PartnerList {
  partners: Partner[];
}

export type AccountType = "checking" | "cc" | "savings" | null;

export interface Account {
  id: string;
  name: string;
  partner_id: string | null;
  type: AccountType;
  excluded: boolean;
}

export interface AccountBindingUpdate {
  partner_id: string | null;
  type: AccountType;
  excluded: boolean;
}

export interface AccountList {
  accounts: Account[];
}

export interface ApiKeyStatus {
  configured: boolean;
}

export interface ApiKeyUpdate {
  api_key: string;
}

export interface Category {
  id: string;
  title: string;
  parent_id: string | null;
}

export interface CategoryDetail {
  id: string;
  title: string;
  parent_id: string | null;
  children: Category[];
  parent_path: Category[];
}

export interface CategoryList {
  categories: Category[];
}

// ApiError — thrown by client.ts, consumers read .detail for message.
export class ApiError extends Error {
  detail: string;
  status?: number;
  constructor(detail: string, status?: number) {
    super(detail);
    this.name = "ApiError";
    this.detail = detail;
    this.status = status;
  }
}

// Sync status union — shared by StatusBadge + SyncPage.
export type SyncStatusType = SyncStatus["status"];

// F2 — Bills dashboard types. Ported from v0 design (mock data — no BE yet).

// US4: partner identity triple (BE contracts/partner-identity). `partner_id`
// = stable semantic key resolved BE-side from account config; `partner_slot`
// = BE-assigned display slot, deterministic sorted partner_id order;
// `label` = config-derived display label (payload-driven, never hardcoded).
// Legacy payloads may carry id/slot "" → FE renders identity-neutral.
export type PartnerSlot = "a" | "b" | "";

export interface F2PartnerIdentity {
  partner_id: string;
  partner_slot: PartnerSlot;
  label: string;
}
// F2 grid R4: "salary"/"savings" pass through from BE unchanged (round-4
// mapper fix — previously coerced to "bill", which leaked salary/savings
// events into BudgetTab's Bills-budget totals).
export type F2EventType = "bill" | "buy" | "salary" | "savings";
export type F2EconomyStatus = "covered" | "partial" | "shortfall";

export interface FinanceEvent {
  id: string;
  date: string; // ISO yyyy-mm-dd
  day: number;
  title: string; // category name (e.g. "Mortgage", "Salary (Partner B)")
  type: F2EventType;
  account: string; // bank account name (e.g. "FxA Check Handelsbanken")
  partner: F2PartnerIdentity;
  amount: number; // positive = income, negative = expense
  /** Mock-data only: original category label (e.g. "Income", "Savings").
   * Not present on BE-sourced events. Used by finance-data.ts filters. */
  category?: string;
  /** BE-only (BillsEvent.is_matched): true when a scheduled buy was found
   * among posted CC transactions (date+amount match). Null for non-buy
   * events and on current/future months → nothing rendered. */
  isMatched?: boolean | null;
  /** BE-only (BillsEvent.is_cc_payment): true when the event is a credit
   * card paydown. Passed through for chip/label logic. */
  isCcPayment?: boolean;
}

export interface FinanceEventList {
  events: FinanceEvent[];
}

export interface EconomyBarView {
  // F2: bills zone width = outer capsule − budget zone. Scales with
  // totalBills/salary.
  billsWidth: string;
  // Budget zone width = constant 11.862% of the partner card row
// (18% of the salary zone, which is 65.9% of row). Never scales —
// see BUDGET_ZONE_RATIO in finance-data.ts.
  budgetWidth: string;
  billsFillWidth: string;
  // F2: true when totalBills/salary < BAR_SMALL_THRESHOLD (0.5).
  // Drives whether EconomyBar renders the capsule with inline labels
  // or swaps in an external labels list (cleaner at small fills).
  billsFillSmall: boolean;
  estCcBillWidth: string;
  ccUsageWidth: string;
  // F2-B: vertical fill bar in the budget zone.
  // budgetUsageWidth = ccUsage / budget clamped [0, 100].
  // Used as a CSS height on the bottom-anchored fill.
  budgetUsageWidth: string;
  // F2-B: when ccUsage > budget, the whole zone tints red.
  budgetOverspent: boolean;
  // F2-B: discrete fill tone by usage bucket.
  // < 50% → "income" (green), 50-80% → "warning" (yellow), > 80% → "shortfall" (red).
  budgetFillTone: "income" | "warning" | "shortfall";
  // F2 §13 revised: savings box is an envelope+fill pair (same mental
  // model as the budget zone).
  // savingsPlannedWidth = planned envelope = planned / savingsBalance,
  // clamped [0, 100] — the track's upper bound.
  savingsPlannedWidth: string;
  // savingsDeltaWidth = |delta| / savingsBalance clamped [0, 100].
  // Used as a CSS height on the bottom-anchored fill.
  // Null delta (future / no live anchor) → "0%" — fill not rendered.
  savingsDeltaWidth: string;
  // F2-C: tone of the delta value + fill.
  // "income" when delta > 0, "shortfall" when < 0,
  // "neutral" when 0 OR delta is null.
  savingsDeltaTone: "income" | "shortfall" | "neutral";
  salaryWidth: string;
  upperBarWidth: string;
  remainingLabel: string;
  remainingTone: "income" | "shortfall";
  netLabel: string;
}

export interface PartnerEconomy {
  partner: F2PartnerIdentity;
  estimatedSalary: number;
  bills: number;
  // F2 §8: BE everyday_budget passthrough. Null when next-month data
  // missing (last sync-window month) → EconomyBar hides the budget
  // zone, GraphView drops the point. Negative stays negative.
  budget: number | null;
  ccUsage: number;
  estimatedCcBill: number;
  // F2-UI L2 amendment 2026-08-03: past-only actual CC bill
  // (CC-side paydowns posted on partner CC accounts). Null for
  // current/future months. UI gates the planned-vs-actual cc pair
  // on this field being non-null.
  realCcBill: number | null;
  realCcBillLabel: string;
  // F2-UI L2 amendment 2026-08-03: past-only posted-txn bills sum.
  // Null on current/future — UI hides the planned-vs-actual row.
  realBills: number | null;
  realBillsLabel: string;
  savingsBalance: number;
  savingsContribution: number;
  // F2 §13 revised: planned savings envelope (salary − bills − cc_bill).
  // 0 = 'no plan known' (pre-field BE snapshot) → empty envelope.
  savingsPlanned: number;
  // F2 §13 revised: actual savings so far. Past = real cash flow,
  // current = growth since the 1st. Null on future months / missing
  // live anchor → fill hidden, envelope still shown.
  savingsDelta: number | null;
  net: number;
  status: F2EconomyStatus;
  /** BE planned_cc_buys passthrough: sum of this partner's scheduled
   * type="buy" events for the month. Optional — populated by
   * bills-mapper from live snapshots; mock/fixture data omits it. */
  plannedCcBuys?: number | null;
  /** formatKr(plannedCcBuys); "" when unavailable. */
  plannedCcBuysLabel?: string;
  /** BE cc_usage_by_category passthrough: real posted CC spend per
   * category title (same filters as ccUsage). Optional — stale snapshots
   * lack the field; null when no real CC activity. BudgetTab's free
   * budget section hides on null/undefined. */
  ccUsageByCategory?: Record<string, number> | null;
  estimatedSalaryLabel: string;
  billsLabel: string;
  budgetLabel: string;
  ccUsageLabel: string;
  /** PR65 review: true when ccUsage is FREE usage (outside planned buys),
   * not total card spend — EconomyBar relabels the capsule accordingly. */
  ccUsageIsFree?: boolean;
  estimatedCcBillLabel: string;
  savingsBalanceLabel: string;
  savingsContributionLabel: string;
  // F2 §13 revised: planned envelope label (formatKr).
  savingsPlannedLabel: string;
  // F2-C: delta formatted with explicit + or − sign.
  // Empty string when delta is null (fill + value hidden).
  savingsDeltaLabel: string;
  bar: EconomyBarView;
}

export interface MonthData {
  key: string;
  label: string;
  year: number;
  monthIndex: number;
  events: FinanceEvent[];
  billsCount: number;
  buysCount: number;
  net: number;
  partners: PartnerEconomy[];
}

export interface MonthList {
  months: MonthData[];
}