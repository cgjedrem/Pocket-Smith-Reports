// Wire decimals stay strings — server owns all detection decisions.
export type DecimalString = string;
export type Month = string;
export type HistoryReason =
  | "open_month" | "future_month" | "no_cc_accounts"
  | "missing_source_context" | "invalid_source" | null;

export interface HistoryIssue {
  month: Month;
  partner_id: string | null;
  code:
    | "missing_snapshot" | "legacy_history" | "partial_month"
    | "missing_partner_identity" | "missing_partner"
    | "unavailable_history" | "scope_changed" | "no_stable_partners";
  reason: HistoryReason;
}

export interface MonthlyAmount {
  month: Month;
  amount: DecimalString;
}

export interface LifestyleComparison {
  month: Month;
  baseline_months: Month[];
  baseline_amount: DecimalString;
  spending_amount: DecimalString;
  change_amount: DecimalString;
  growth_percent: DecimalString | null;
}

export interface LifestyleCategory {
  category_id: string;
  category_title: string;
  samples: MonthlyAmount[];
  comparison: LifestyleComparison;
  latest_month_over_month_percent: DecimalString | null;
  is_above_threshold: boolean;
  suppression_reason: "zero_baseline" | "low_frequency" | null;
}

export interface LifestylePartner {
  partner_id: string;
  partner_slot: "a" | "b" | "";
  partner: string;
  status: "ready" | "insufficient_history";
  categories: LifestyleCategory[];
  uncategorized_samples: MonthlyAmount[];
}

export interface LifestyleCreepResponse {
  month: Month;
  reference_start: Month;
  reference_end: Month;
  window_months: Month[];
  evaluation_months: [Month];
  baseline_months: number;
  threshold_percent: DecimalString;
  status: "ready" | "partial" | "insufficient_history";
  issues: HistoryIssue[];
  partners: LifestylePartner[];
}

export type EconomyGroupId = "shared" | "personal_partner_a" | "personal_partner_b";

export interface ReportLifestyleCategory extends Omit<LifestyleCategory, "suppression_reason"> {
  suppression_reason: "zero_baseline" | "negative_baseline" | "low_frequency" | null;
}

export interface ReportLifestyleGroup {
  group_id: EconomyGroupId;
  label: string;
  partner_id: string | null;
  partner_slot: "a" | "b" | "";
  status: "ready" | "insufficient_history";
  categories: ReportLifestyleCategory[];
  uncategorized_samples: MonthlyAmount[];
}

export interface ReportHistoryIssue extends HistoryIssue {
  group_id: EconomyGroupId | null;
}

export interface ReportLifestyleCreepResponse extends Omit<LifestyleCreepResponse, "status" | "issues" | "partners"> {
  grouping: "report";
  history_guidance: string | null;
  status: "ready" | "insufficient_history";
  issues: ReportHistoryIssue[];
  groups: ReportLifestyleGroup[];
}
