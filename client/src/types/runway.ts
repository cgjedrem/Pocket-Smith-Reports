export type RunwayFreshness = "fresh" | "stale" | "unknown";
export type RunwayCurrencyStatus = "verified" | "unverified" | "conflict";
export type RunwaySelectionStatus = "unconfigured" | "empty" | "valid" | "invalid";

export interface RunwayIssue {
  code: string;
  severity: "blocking" | "qualification";
  month: string | null;
  account_id: string | null;
  partner_id: string | null;
}

export interface RunwayOwner {
  partner_id: string;
  partner_slot: "a" | "b" | "";
  label: string;
}

export interface RunwayAccountOption {
  id: string;
  name: string;
  partner_id: string | null;
  type: "checking" | "savings" | "cc" | "investment" | null;
  excluded: boolean;
  selected: boolean;
  eligible: boolean;
  issues: RunwayIssue[];
}

export interface RunwaySettingsUpdate {
  liquid_account_ids: string[];
}

export interface RunwaySettingsResponse extends RunwaySettingsUpdate {
  schema_version: 1;
  selection_status: RunwaySelectionStatus;
  owners: RunwayOwner[];
  accounts: RunwayAccountOption[];
  issues: RunwayIssue[];
}

export interface RunwaySelectedAccount extends RunwayAccountOption {
  balance: number | null;
  currency_code: string | null;
  currency_status: RunwayCurrencyStatus;
  balance_date: string | null;
  balance_date_precision: "date" | "datetime" | "unknown";
  balance_freshness: RunwayFreshness;
}

export interface RunwayMeasures {
  selected_account_ids: string[];
  reserves: number | null;
  average_monthly_spending: number | null;
  runway_months: number | null;
  runway_display: string | null;
  currency_code: string | null;
  reserves_currency_code: string | null;
  spending_currency_code: string | null;
  currency_status: RunwayCurrencyStatus;
  status: "available" | "qualified" | "unavailable";
  issues: RunwayIssue[];
}

export interface RunwayOwnerResult extends RunwayMeasures {
  owner: RunwayOwner;
}

export interface RunwayOwnerObservation {
  partner_id: string;
  spending: number | null;
  currency_code: string | null;
  currency_status: RunwayCurrencyStatus;
}

export interface RunwayObservation {
  month: string;
  status: "included" | "excluded";
  coverage: "complete" | "unverified" | "partial" | "invalid" | "missing";
  collected_at: string | null;
  freshness: RunwayFreshness;
  coverage_start: string | null;
  coverage_end: string | null;
  owners: RunwayOwnerObservation[];
  household_spending: number | null;
  household_currency_code: string | null;
  issues: RunwayIssue[];
}

export interface RunwayResponse {
  schema_version: 1;
  calculation_version: 1;
  calculated_at: string;
  as_of_month: string;
  basis: "gross_recorded_spending";
  candidate_months: [string, string, string];
  included_months: string[];
  included_month_count: number;
  selection_status: RunwaySelectionStatus | "invalid_settings";
  selected_account_ids: string[] | null;
  selected_accounts: RunwaySelectedAccount[];
  catalog_collected_at: string | null;
  catalog_freshness: RunwayFreshness;
  observations: RunwayObservation[];
  owners: RunwayOwnerResult[];
  household: RunwayMeasures;
  issues: RunwayIssue[];
}
