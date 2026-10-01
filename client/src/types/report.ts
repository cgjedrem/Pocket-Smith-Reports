// TS types — match backend Pydantic models (src/budget_api/models/reports.py).
// Source: design doc L4 + backend models.

export interface MonthList {
  months: string[];
}

export type GenerateStatusType = "generating" | "success" | "failed";

export interface GenerateStatus {
  status: GenerateStatusType;
  errors: string[];
  started_at: string | null;
  completed_at: string | null;
}

export interface RootTotals {
  paid: number;
  received: number;
  net: number;
  count: number;
}

export interface OwnerTotals {
  partner_a: { paid: number; received: number; net: number };
  partner_b: { paid: number; received: number; net: number };
}

export interface PartnerPanel {
  label: string;
  paid: number;
  received: number;
  net: number;
  net_class: "pos" | "neg";
}

// KPI role totals — per partner + total. Matches _role_kpis() shape.
export interface KpiRoleTotals {
  income: number;
  real_spend: number;
  personal_spend: number;
  net_cash: number;
  // Optional: absent on reports generated before this field existed
  // (CALCULATION_VERSION not bumped for this addition — same nullable-
  // fallback convention as net_saved_class).
  net_cash_class?: SignClass;
  net_savings: number;
  investment: number;
}

export interface Kpis {
  partner_a: KpiRoleTotals;
  partner_b: KpiRoleTotals;
  total: KpiRoleTotals;
}

export interface SavingsSummaryTotals {
  to_savings: number;
  from_savings: number;
  net_saved: number;
}

export interface SavingsSummary {
  partner_a: SavingsSummaryTotals;
  partner_b: SavingsSummaryTotals;
  total: SavingsSummaryTotals;
}

export interface Reconciliation {
  source: number;
  report: number;
  difference: number;
}

// --------------------------------------------------------------------------- //
// Detailed section DTOs (PR1 contracts, PR2 populates via report_builder).
// Sign-class enum mirrors backend SignClass — paid-negative convention verbatim
// (paid sums negatives, received sums positives, net = paid - received).
// Percentages are 0-100 or null (null when the denominator was 0 — never a
// fabricated 0%).
// --------------------------------------------------------------------------- //

export type SignClass = "pos" | "neg" | "zero";

export interface IncomeRow {
  partner_a: number;
  partner_a_class: SignClass;
  partner_b: number;
  partner_b_class: SignClass;
  total: number;
  total_class: SignClass;
  row_pct_partner_a: number | null;
  row_pct_partner_b: number | null;
  household_pct: number | null;
}

export interface IncomeSection {
  salary: IncomeRow;
  third_party: IncomeRow;
  total_partner_a: number;
  total_partner_a_class: SignClass;
  total_partner_b: number;
  total_partner_b_class: SignClass;
  total_income: number;
  total_income_class: SignClass;
}

export interface SavingsPartnerRow {
  to_savings: number;
  to_savings_class: SignClass;
  from_savings: number;
  from_savings_class: SignClass;
  net_saved: number;
  net_saved_class: SignClass;
  income: number;
  income_class: SignClass;
  rate: number | null; // net_saved / income * 100; null when income === 0
}

export interface DetailedSavingsSection {
  partner_a: SavingsPartnerRow;
  partner_b: SavingsPartnerRow;
  household: SavingsPartnerRow;
}

export interface PairedReimbursementRow {
  category_title: string;
  partner_a: number; // signed: positive when partner_a received
  partner_a_class: SignClass;
  partner_b: number; // signed: positive when partner_b received
  partner_b_class: SignClass;
  total: number; // always 0
  total_class: SignClass; // always "zero"
}

export interface NetCategoryRow {
  category_title: string;
  partner_a_net: number;
  partner_a_net_class: SignClass;
  partner_b_net: number;
  partner_b_net_class: SignClass;
  total: number;
  total_class: SignClass;
  g_share_partner_a: number | null;
  g_share_partner_b: number | null;
  // Nested transparency rows rendered directly under this category row
  // (CALCULATION_VERSION 8+). Optional/undefined on stored v7 reports —
  // renderers fall back to the section-level paired_reimbursements list.
  paired_reimbursements?: PairedReimbursementRow[];
}

export interface NetSection {
  rows: NetCategoryRow[];
  paired_reimbursements: PairedReimbursementRow[];
  total_partner_a: number;
  total_partner_a_class: SignClass;
  total_partner_b: number;
  total_partner_b_class: SignClass;
  total: number;
  total_class: SignClass;
  share_partner_a: number | null;
  share_partner_b: number | null;
}

export interface PersonalCategoryRow {
  category_title: string;
  paid_partner_a: number;
  paid_partner_a_class: SignClass;
  paid_partner_b: number;
  paid_partner_b_class: SignClass;
  total: number;
  total_class: SignClass;
  pct_personal: number | null;
  pct_household: number | null;
}

export interface PersonalSection {
  rows: PersonalCategoryRow[];
  // PR5 additive — per-section subtotal (sum of this section's own row
  // totals; the section's "Subtotal" row in the old UI). null on stored
  // reports written before PR5 — fall back to personal_total there.
  subtotal: number | null;
  subtotal_class: SignClass | null;
  personal_total: number;
  personal_total_class: SignClass;
  household_total: number;
  household_total_class: SignClass;
  pct_personal: number | null;
  pct_household: number | null;
}

export interface CcPaymentsSection {
  partner_a_paid: number;
  partner_a_paid_class: SignClass;
  partner_b_paid: number;
  partner_b_paid_class: SignClass;
  household_paid: number;
  household_paid_class: SignClass;
}

export interface ExcludedCategoryRow {
  category_title: string;
  paid_partner_a: number;
  paid_partner_a_class: SignClass;
  paid_partner_b: number;
  paid_partner_b_class: SignClass;
  total: number;
  total_class: SignClass;
}

export interface ExcludedSection {
  rows: ExcludedCategoryRow[];
  total: number;
  total_class: SignClass;
}

export interface HouseholdTotals {
  partner_a: number;
  partner_a_class: SignClass;
  partner_b: number;
  partner_b_class: SignClass;
  total: number;
  total_class: SignClass;
}

// Common-economy split (calculation_version 9, additive). One category row
// within detailed.split — actual/fair/delta are partner_a's perspective
// (two-partner system, shares sum to 100%, so partner_b's numbers are the
// exact complement: actual_b = total - actual, etc.). Matches backend
// src/budget_api/models/reports.py::SplitCategoryRow.
// section: derived display grouping (home/common/trips/personal_partner_a/
// personal_partner_b/...) — category-level selection is the source of
// truth, section is NOT an eligibility filter anymore.
export interface SplitCategoryRow {
  category_id: string;
  label: string;
  // Nullable for the same stored-v9 compat reason as the b-side fields
  // below: v9 stored rows carry only 5 keys (no section, no b-side).
  section: string | null;
  actual: number;
  fair: number;
  delta: number;
  // partner_b's perspective (additive on top of the a-side fields above —
  // exact complement: actual_b = total - actual, fair_b = total - fair,
  // delta_b = -delta). Optional + nullable: compute_split() always
  // populates these for freshly-built reports, but stored
  // CALCULATION_VERSION=9 reports persisted before this change only carry
  // the 5 original keys — render em-dash for those, never fabricate 0.
  actual_b?: number | null;
  fair_b?: number | null;
  delta_b?: number | null;
}

// Single netted transfer for the whole split. from_partner/to_partner are
// REAL display labels (already resolved server-side in report_builder.py —
// never render these as "partner_a"/"partner_b" slot keys).
// Rendered again (restored 2026-10-01, user request): both frontend
// surfaces draw a settlement sentence below the split tables' totals
// rows (DetailedSections.tsx CommonEconomySplitSection, KpiCoverSection.tsx
// SplitSummaryCard) — "X pays Y …" wording; balanced (null) renders the
// original em-dash wording, zero-rows renders nothing. Mirrors the backend
// twin restoration in accounting_html.py / build_mega.py (which use
// "Settlement: X owes Y N." phrasing — NOT mirrored on React).
export interface SplitSettlement {
  from_partner: string;
  to_partner: string;
  amount: number;
}

// detailed.split — global %, per-category rows across every enabled
// section, one netted settlement. Null on the parent DetailedSections when
// no split config exists or the feature is disabled (never fabricate).
// `shares` stays slot-keyed (partner_a/partner_b), unlike settlement.
export interface SplitSection {
  shares: { partner_a: number; partner_b: number };
  sections: string[];
  rows: SplitCategoryRow[];
  settlement: SplitSettlement | null;
}

// report.detailed — one fully pre-computed object per section. Each section
// is null when its underlying data is unavailable (never a fabricated
// zero). Not populated until PR2; PR1 only adds the contract.
export interface DetailedSections {
  income: IncomeSection | null;
  savings: DetailedSavingsSection | null;
  home: NetSection | null;
  common: NetSection | null;
  personal_partner_a: PersonalSection | null;
  personal_partner_b: PersonalSection | null;
  trips: NetSection | null;
  cc_payments: CcPaymentsSection | null;
  excluded: ExcludedSection | null;
  household_totals: HouseholdTotals | null;
  // Additive (calculation_version 9) — common-economy split. Optional:
  // stored v7/v8 reports predate this field entirely (not just null) —
  // consumers must handle `undefined` the same as `null`.
  split?: SplitSection | null;
}

export interface ReportResponse {
  month: string;
  stale: boolean;
  // Breaking-contract identity marker (BE v2+); absent on legacy payloads.
  contract_version?: number;
  txn_count: number;
  // Raw contract
  normalized_transactions: Record<string, unknown>[];
  categories: Record<string, unknown>[];
  reconciliation: Reconciliation;
  detailed_section_mapping: Record<string, unknown> | null;
  kpis: Kpis | null;
  savings_summary?: SavingsSummary | null;
  // Pre-computed presentation views
  root_totals: RootTotals;
  owner_totals: OwnerTotals;
  partner_panels: { partner_a: PartnerPanel; partner_b: PartnerPanel };
  partner_labels: Record<string, string>;
  // PR1 additive contract — populated starting PR2.
  detailed?: DetailedSections | null;
  personal_share?: number | null; // personal_spend / total_real_spend * 100
  // Per-partner personal-spend share vs household real_spend (old
  // KpiPartnerPanel "(X.X%)" parity). null when kpis absent / denominator 0.
  personal_share_partner_a?: number | null;
  personal_share_partner_b?: number | null;
  balanced?: boolean | null; // reconciliation.difference === 0
  // Server-side partner label resolution warnings (US4 additive).
  warnings?: string[];
}
