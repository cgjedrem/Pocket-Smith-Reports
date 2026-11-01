import type { RunwayIssue, RunwayMeasures, RunwayResponse, RunwaySettingsResponse } from "@/types/runway";

export function issue(code: string, scope: Partial<RunwayIssue> = {}): RunwayIssue {
  return { code, severity: "qualification", month: null, account_id: null, partner_id: null, ...scope };
}

export function settingsFixture(): RunwaySettingsResponse {
  return {
    schema_version: 1,
    liquid_account_ids: ["1100001", "1100006"],
    selection_status: "valid",
    owners: [
      { partner_id: "owner_a", partner_slot: "a", label: "Partner A" },
      { partner_id: "owner_b", partner_slot: "b", label: "Partner B" },
    ],
    accounts: [
      { id: "1100001", name: "Reserve A", partner_id: "owner_a", type: "checking", excluded: false, selected: true, eligible: true, issues: [] },
      { id: "1100006", name: "Reserve B", partner_id: "owner_b", type: "savings", excluded: false, selected: true, eligible: true, issues: [] },
      { id: "1100007", name: "Extra reserve", partner_id: "owner_a", type: "savings", excluded: false, selected: false, eligible: true, issues: [] },
      { id: "1100008", name: "Card A", partner_id: "owner_a", type: "cc", excluded: false, selected: false, eligible: false, issues: [issue("account_type_ineligible", { severity: "blocking" })] },
    ],
    issues: [],
  };
}

export function measures(reserves = 120000, spending = 90000, display = "1.3"): RunwayMeasures {
  return {
    selected_account_ids: ["1100001", "1100006"],
    reserves,
    average_monthly_spending: spending,
    runway_months: reserves / spending,
    runway_display: display,
    currency_code: "NOK",
    reserves_currency_code: "NOK",
    spending_currency_code: "NOK",
    currency_status: "verified",
    status: "qualified",
    issues: [issue("source_stale")],
  };
}

export function runwayFixture(): RunwayResponse {
  const settings = settingsFixture();
  return {
    schema_version: 1,
    calculation_version: 1,
    calculated_at: "2026-10-31T12:00:00+00:00",
    as_of_month: "2026-10",
    basis: "gross_recorded_spending",
    candidate_months: ["2026-07", "2026-08", "2026-09"],
    included_months: ["2026-07", "2026-08", "2026-09"],
    included_month_count: 3,
    selection_status: "valid",
    selected_account_ids: settings.liquid_account_ids,
    selected_accounts: settings.accounts.slice(0, 2).map((account, i) => ({
      ...account,
      balance: i === 0 ? 90000 : 30000,
      currency_code: "NOK",
      currency_status: "verified",
      balance_date: "2026-10-30",
      balance_date_precision: "date",
      balance_freshness: "stale",
      issues: [issue("balance_stale")],
    })),
    catalog_collected_at: null,
    catalog_freshness: "unknown",
    observations: ["2026-07", "2026-08", "2026-09"].map((month, i) => ({
      month,
      status: "included",
      coverage: "complete",
      collected_at: "2026-10-01T00:15:00+00:00",
      freshness: "stale",
      coverage_start: `${month}-01`,
      coverage_end: `${month}-${i === 2 ? "30" : "31"}`,
      owners: [
        { partner_id: "owner_a", spending: 20000 + i * 10000, currency_code: "NOK", currency_status: "verified" },
        { partner_id: "owner_b", spending: 50000 + i * 10000, currency_code: "NOK", currency_status: "verified" },
      ],
      household_spending: 70000 + i * 20000,
      household_currency_code: "NOK",
      issues: [issue("source_stale", { month })],
    })),
    owners: [
      { ...measures(90000, 30000, "3.0"), selected_account_ids: ["1100001"], owner: settings.owners[0] },
      { ...measures(30000, 60000, "0.5"), selected_account_ids: ["1100006"], owner: settings.owners[1] },
    ],
    household: measures(),
    issues: [issue("source_date_unknown")],
  };
}

export function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}
