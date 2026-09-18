// Mega report TS types — match backend models/mega_reports.py + design doc L4.
// GenerateStatus imported from report.ts (F1.2 — no redefinition).

export interface MegaReportRange {
  start: string;
  end: string;
}

export interface MegaReportList {
  reports: MegaReportRange[];
}

// Re-export GenerateStatus for convenience.
export type { GenerateStatus, GenerateStatusType } from "./report";

export interface SalaryAllocationEntry {
  id: string;
  title: string;
  amount: number;
}

export interface SalaryAllocation {
  income: number;
  entries: SalaryAllocationEntry[];
  unavailable_reason: string | null;
}

export type RecommendationSeverity = "high" | "medium" | "low";

export interface Recommendation {
  id: string;
  title: string;
  body: string;
  severity: RecommendationSeverity;
  evidence: string[];
}

export interface RecommendationsArtifact {
  schema_version: string;
  generated_at: string;
  period: { start: string; end: string };
  recommendations: Recommendation[];
}

export interface MonthlyKpiPartner {
  income: number;
  real_spend: number;
  net_cash: number;
  net_savings: number;
  investment?: number;
}

export interface MonthlyKpiPage {
  month: string;
  kpis: {
    partner_a: MonthlyKpiPartner;
    partner_b: MonthlyKpiPartner;
    total: MonthlyKpiPartner;
  };
}

export interface CategoryAgg {
  title: string;
  section: string;
  partner_a_paid: number[];
  partner_b_paid: number[];
  partner_a_received: number[];
  partner_b_received: number[];
  partner_a_net: number[];
  partner_b_net: number[];
  total: number[];
  count: number[];
  is_reimbursement: boolean;
}

export interface ExcludedTransaction {
  id?: number | string;
  date: string;
  description: string;
  category: string;
  owner: string;
  amount: number;
}

export interface Trip {
  label: string;
  date_start: string | null;
  date_end: string | null;
  days: number | null;
  txn_count: number;
  total: number;
  partner_a_paid: number;
  partner_b_paid: number;
  cats: string[];
  cat_breakdown: Record<string, number>;
  txns: Record<string, unknown>[];
}

export interface DetailAgg {
  months: string[];
  cats: Record<string, CategoryAgg>;
  cc_paydowns: Record<string, Record<string, number>>;
  excluded_transactions: Record<string, ExcludedTransaction[]>;
  trips: Trip[];
  series: {
    income: { partner_a: number[]; partner_b: number[]; total: number[] };
    savings: {
      net_partner_a: number[];
      net_partner_b: number[];
      total: number[];
      investment_net_partner_a: number[];
      investment_net_partner_b: number[];
      investment_net_total: number[];
    };
    real_spend: { partner_a: number[]; partner_b: number[]; total: number[] };
    net_cash: { partner_a: number[]; partner_b: number[]; total: number[] };
  };
  cumulative: {
    income: { partner_a: number; partner_b: number; total: number };
    savings: {
      net_partner_a: number;
      net_partner_b: number;
      total: number;
      investment_net_partner_a: number;
      investment_net_partner_b: number;
      investment_net_total: number;
    };
    real_spend: { partner_a: number; partner_b: number; total: number };
    net_cash: { partner_a: number; partner_b: number; total: number };
  };
}

export interface MegaReportResponse {
  start: string;
  end: string;
  stale: boolean;
  calculation_version: number;
  // Breaking-contract identity marker (BE v2+); absent on legacy payloads.
  contract_version?: number;
  txn_counts: Record<string, number>;
  months: string[];
  partner_labels: Record<string, string>;
  detail_agg: DetailAgg;
  salary_allocation: SalaryAllocation;
  recommendations: RecommendationsArtifact | null;
  monthly_kpi_pages: MonthlyKpiPage[];
  // Per-month raw txns routed to detailed sections (Income, Savings, etc.).
  // Mirrors the CLI appendix tables: Date | Payee | Account | Amount per subcat.
  appendix_transactions?: Record<string, AppendixTransaction[]> | null;
  // Server-side partner label resolution warnings (US4 additive).
  warnings?: string[];
}

// Appendix transaction — shape mirrors src/mom/sections/section_appendices.py.
// `_detailed_section`, `_main_category`, `_subcategory` are routing tags from
// mega/build_mega.py::_appendix_transactions.
export interface AppendixTransaction {
  id: number | null;
  date: string;
  amount: number;
  payee: string;
  account: { name: string };
  _detailed_section: string;
  _main_category: { id: string | number; title: string };
  _subcategory: { id: string | number; title: string } | null;
  // PS label[0] — trips cluster txns by this. Only populated for trips.
  _trip_label?: string | null;
}