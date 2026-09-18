// TS types — mirror backend Pydantic models exactly.
// Source: src/budget_api/models/bills.py + design doc L4.

export type BillsEventType = "bill" | "buy" | "savings" | "salary";
export type BillsPartnerStatus = "covered" | "partial" | "shortfall";

export interface BillsEvent {
  id: string;
  date: string; // YYYY-MM-DD
  day: number; // 1-31
  title: string; // category name (e.g. "Mortgage", "Salary (Partner B)")
  type: BillsEventType;
  account: string; // bank account name (e.g. "FxA Check Handelsbanken")
  partner: string;
  amount: number;
  is_cc_payment: boolean;
  is_matched: boolean | null;
  /** US4 (schema 5+, pydantic defaults "" pre-schema-5): stable semantic
   * identity — account_mappings partner key. */
  partner_id: string;
  /** US4: BE-assigned display slot, deterministic sorted partner_id order. */
  partner_slot: "a" | "b" | "";
}

export interface BillsSourceCounts {
  ps_events_fetched: number;
  ps_transactions_fetched: number;
  events_kept_after_filter: number;
}

export interface PartnerBills {
  partner: string;
  /** US4 (schema 5+, pydantic defaults "" pre-schema-5): stable semantic
   * identity — account_mappings partner key. */
  partner_id: string;
  /** US4: BE-assigned display slot, deterministic sorted partner_id order. */
  partner_slot: "a" | "b" | "";
  salary: number;
  bills: number;
  /** Sum of type="buy" events per partner (planned CC purchases).
   * Distinct from real_cc_bill / estimated_cc_bill (realized card spend).
   * BE-side input to everyday_budget (F2 §8). */
  planned_cc_buys: number;
  /** F2 §8 locked: salary(m+1) − bills(m+1) − scheduledCcBuys(m+1),
   * computed BE-side. Null when m+1 data missing (last sync-window
   * month) → FE hides the budget zone. Negative stays negative. */
  everyday_budget: number | null;
  savings_transfer: number;
  /** F2 §13 revised (2026-08-28): planned savings envelope =
   * salary − bills − cc_bill. Static, event-derived. BE defaults 0.0
   * on pre-field snapshots → 0 means 'no plan known' (empty envelope). */
  savings_planned: number;
  /** F2 §13 revised: actual savings so far. Past = real cash flow,
   * current = growth since the 1st, future / missing live anchor = null
   * (fill hidden, envelope still shown). */
  savings_delta: number | null;
  savings_balance: number;
  estimated_cc_bill: number | null;
  real_cc_bill: number | null;
  // F2-UI (L2 amendment 2026-08-03): past-month actual bills sum
  // (posted checking-account debits, excluding cc_payment + exclude-role
  // categories + transfers). Null for current/future months — UI gates
  // the planned-vs-actual row on this field.
  real_bills: number | null;
  cc_usage: number;
  /** Real posted CC spend keyed by category title — same filters/gate as
   * cc_usage (values sum to it). Past + current months; null when no real
   * CC activity or on snapshots written before the field existed. */
  cc_usage_by_category?: Record<string, number> | null;
  budget_usage: number;
  net: number;
  status: BillsPartnerStatus;
  events: BillsEvent[];
}

export interface BillsSnapshot {
  schema_version: number;
  month: string; // YYYY-MM
  month_label: string;
  is_past: boolean;
  is_current: boolean;
  is_future: boolean;
  synced_at: string; // ISO 8601
  bills_count: number;
  buys_count: number;
  warnings: string[];
  partners: PartnerBills[];
  source_counts: BillsSourceCounts;
}

export interface BillsEventList {
  events: BillsEvent[];
  total: number;
}

export interface BillsEventsFilters {
  // Semantic identity key (US4, schema 5+). Supersedes the legacy label
  // param server-side.
  partner_id?: string;
  type?: BillsEventType;
  category?: string;
  from?: string; // YYYY-MM-DD
  to?: string; // YYYY-MM-DD
  order?: "asc" | "desc";
  limit?: number;
}
