import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RunwayPanel } from "@/components/bills/RunwayPanel";
import { issue, jsonResponse, runwayFixture, settingsFixture, deferred } from "./runway-fixtures";
import { setAmountsHidden } from "@/lib/privacy-store";
import { runwayIssueText, runwayMoney } from "@/lib/runway";

let payload: ReturnType<typeof runwayFixture>;
let config: ReturnType<typeof settingsFixture>;
let fetchMock: ReturnType<typeof vi.fn>;
let putStatus: number;
let getSettingsStatus: number;

beforeEach(() => {
  setAmountsHidden(false);
  payload = runwayFixture();
  config = settingsFixture();
  putStatus = 200;
  getSettingsStatus = 200;
  fetchMock = vi.fn(async (url: string, init: RequestInit) => {
    const path = new URL(url, "http://fixture.test").pathname;
    if (path === "/api/bills/runway" && init.method === "GET") return jsonResponse(payload);
    if (path === "/api/settings/runway" && init.method === "GET") return jsonResponse(config, getSettingsStatus);
    if (path === "/api/settings/runway" && init.method === "PUT") {
      if (putStatus !== 200) return jsonResponse({ detail: "raw money -987654" }, putStatus);
      config = { ...config, ...JSON.parse(init.body as string) };
      return jsonResponse(config);
    }
    throw new Error("Unexpected API route");
  });
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => { act(() => setAmountsHidden(false)); vi.unstubAllGlobals(); });

async function openSettings() {
  fireEvent.click(screen.getByText("Liquid account settings"));
  await screen.findByRole("checkbox", { name: /Reserve A/ });
}

describe("RunwayPanel", () => {
  it("renders owner/household figures and descriptive common-month context", async () => {
    render(<RunwayPanel />);
    expect(screen.getByText("Loading runway…")).toBeVisible();
    await screen.findByText("1.3 months");
    const household = screen.getByRole("region", { name: "Household runway" });
    expect(household).toHaveTextContent("120,000 kr");
    expect(household).toHaveTextContent("90,000 kr");
    expect(screen.getByRole("region", { name: "Partner A runway" })).toHaveTextContent("3.0 months");
    expect(screen.getByRole("region", { name: "Partner B runway" })).toHaveTextContent("0.5 months");
    expect(screen.getByText(/Average monthly spending \(net, as in Reports\)/)).toBeVisible();
    expect(screen.getByText(/refunds and reimbursements reduce spending/i)).toBeVisible();
    expect(household).toHaveTextContent("Average monthly spending (net)");
    expect(screen.queryByText(/gross burn|recorded spending/i)).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Monthly net spending" })).toBeVisible();
    expect(screen.getByText(/not a forecast, financial advice, or a recommendation/i)).toBeVisible();
    expect(screen.getByText(/excluded from net spending as in Reports/i)).toBeVisible();
    expect(screen.getByText(/3 of 3 completed months/)).toBeVisible();
    expect(screen.getByRole("heading", { name: "July 2026" })).toBeVisible();
    expect(screen.getByText(/Catalog collected: Unknown/)).toBeVisible();
    expect(screen.getAllByText(/Balance date: 2026-10-30 \(date only\)/)).toHaveLength(2);
  });

  it("explains common economy split attribution with owner labels and shares", async () => {
    payload.split_shares = { partner_a: 60, partner_b: 40 };
    payload.owners[0].owner.label = "Alex";
    payload.owners[1].owner.label = "Sam";
    render(<RunwayPanel />);
    await screen.findByText("1.3 months");
    expect(screen.getByText(/^Owner spending:/)).toHaveTextContent(
      "Owner spending: shared categories split 60 / 40 (Alex / Sam, common economy split); other spending by who paid. Owners sum to the household.",
    );
    expect(screen.getByRole("region", { name: "Alex runway" })).toHaveTextContent("Attribution: 60% of shared categories + own other spending");
    expect(screen.getByRole("region", { name: "Sam runway" })).toHaveTextContent("Attribution: 40% of shared categories + own other spending");
    expect(screen.getByRole("region", { name: "Household runway" })).not.toHaveTextContent("Attribution:");
  });

  it("maps split shares by owner slot, not response order", async () => {
    payload.split_shares = { partner_a: 55.5, partner_b: 44.5 };
    payload.owners.reverse();
    render(<RunwayPanel />);
    await screen.findByText("1.3 months");
    expect(screen.getByText(/^Owner spending:/)).toHaveTextContent("split 55.5 / 44.5 (Partner A / Partner B");
    expect(screen.getByRole("region", { name: "Partner B runway" })).toHaveTextContent("44.5% of shared categories");
  });

  it("explains payer attribution without split shares", async () => {
    payload.owner_attribution = "payer";
    payload.split_shares = null;
    render(<RunwayPanel />);
    await screen.findByText("1.3 months");
    expect(screen.getByText(/^Owner spending:/)).toHaveTextContent("Owner spending: attributed to the partner whose account paid (net).");
    expect(screen.getByRole("region", { name: "Partner A runway" })).toHaveTextContent("Attribution: paid from own accounts (net)");
    expect(screen.queryByText(/common economy split/)).not.toBeInTheDocument();
  });

  it("formats negative net monthly spending with a minus sign", async () => {
    payload.observations[0].owners[1].spending = -1500;
    payload.observations[0].household_spending = -250;
    render(<RunwayPanel />);
    const july = await screen.findByRole("region", { name: "July 2026 observation" });
    const negative = within(july).getByText("-1,500 kr");
    expect(negative).toHaveClass("tabular-nums");
    expect(within(july).getByText("-250 kr")).toHaveClass("tabular-nums");
    expect(runwayMoney(-1500, "USD")).toBe("-1,500 USD");
  });

  it.each([0, -400])("keeps runway unavailable for nonpositive net average %s", async (average) => {
    payload.household = { ...payload.household, average_monthly_spending: average, runway_months: null, runway_display: null, status: "unavailable", issues: [issue("nonpositive_burn")] };
    render(<RunwayPanel />);
    await screen.findByText(/Net spending is zero or negative/);
    const household = screen.getByRole("region", { name: "Household runway" });
    expect(household).toHaveTextContent("Unavailable");
    expect(household).toHaveTextContent(runwayMoney(average, "NOK"));
    expect(screen.queryByText("1.3 months")).not.toBeInTheDocument();
  });

  it("identifies every missing/partial month without older backfill", async () => {
    payload.included_months = ["2026-09"];
    payload.included_month_count = 1;
    payload.observations.slice(0, 2).forEach((row, i) => {
      row.status = "excluded";
      row.coverage = i ? "partial" : "missing";
      row.household_spending = null;
      row.owners.forEach((owner) => { owner.spending = null; });
      row.issues = [issue(i ? "partial_source" : "missing_source", { month: row.month, severity: "blocking" })];
    });
    payload.household = { ...payload.household, average_monthly_spending: null, runway_months: null, runway_display: null, status: "unavailable", issues: [issue("insufficient_history")] };
    render(<RunwayPanel />);
    await screen.findByText(/1 of 3 completed months/);
    expect(screen.getByRole("region", { name: "Household runway" })).toHaveTextContent("Unavailable");
    expect(screen.getByText(/Fewer than two usable completed months/)).toBeVisible();
    expect(screen.getByText(/Monthly source missing/)).toBeVisible();
    expect(screen.getByText(/Month only partially covered/)).toBeVisible();
    expect(screen.queryByText("June 2026")).not.toBeInTheDocument();
  });

  it("renders qualified coverage/currency and tiny server-rounded ratios", async () => {
    payload.household.runway_display = "<0.1";
    payload.household.runway_months = 0.001;
    payload.household.currency_status = "unverified";
    payload.household.issues = [issue("coverage_unverified", { month: "2026-07" }), issue("currency_unverified"), issue("source_times_differ")];
    render(<RunwayPanel />);
    await screen.findByText("<0.1 months");
    expect(screen.getByText(/Month coverage unverified — recorded transactions only/)).toHaveTextContent("July 2026");
    expect(screen.getByText(/Single-currency assumption; currency unverified/)).toBeVisible();
    expect(screen.getByText(/Sources collected at different times/)).toBeVisible();
  });

  it.each([0, -2000])("preserves observed reserves %s without fabricating zero months", async (reserves) => {
    payload.household = { ...payload.household, reserves, runway_months: null, runway_display: null, status: "unavailable", issues: [issue("nonpositive_reserves")] };
    render(<RunwayPanel />);
    await screen.findByText(/Selected reserves are zero or negative/);
    expect(screen.getByRole("region", { name: "Household runway" })).toHaveTextContent(runwayMoney(reserves, "NOK"));
    expect(screen.queryByText("0.0 months")).not.toBeInTheDocument();
  });

  it("shows no selection and empty owners without inventing accounts", async () => {
    payload.selected_account_ids = [];
    payload.selected_accounts = [];
    payload.owners = [];
    payload.selection_status = "unconfigured";
    payload.household = { ...payload.household, selected_account_ids: [], reserves: null, runway_months: null, runway_display: null, status: "unavailable", issues: [issue("no_selection")] };
    config.accounts = [];
    config.liquid_account_ids = [];
    render(<RunwayPanel />);
    await screen.findByText("Select liquid accounts");
    expect(screen.getByText("No selected reserve accounts.")).toBeVisible();
    expect(screen.getByText(/No configured account owners available/)).toBeVisible();
    fireEvent.click(screen.getByText("Liquid account settings"));
    expect(await screen.findByText(/No account choices available/)).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("saves explicitly, resets drafts, and preserves draft across collapse and masking without refetch", async () => {
    const { container } = render(<RunwayPanel />);
    await screen.findByText("1.3 months");
    await openSettings();
    fireEvent.click(screen.getByRole("checkbox", { name: /Extra reserve/ }));
    expect(screen.getByText(/Unsaved changes/)).toBeVisible();
    const calls = fetchMock.mock.calls.length;
    act(() => setAmountsHidden(true));
    expect(screen.getByRole("checkbox", { name: /Extra reserve/ })).toBeChecked();
    expect(container.innerHTML).not.toMatch(/120,000|90,000|70,000|30,000/);
    expect(screen.getByText("1.3 months")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(calls);
    fireEvent.click(screen.getByText("Liquid account settings"));
    fireEvent.click(screen.getByText("Liquid account settings"));
    expect(screen.getByRole("checkbox", { name: /Extra reserve/ })).toBeChecked();
    act(() => setAmountsHidden(false));
    expect(screen.getByRole("region", { name: "Household runway" })).toHaveTextContent("120,000 kr");
    fireEvent.click(screen.getByRole("button", { name: "Reset changes" }));
    expect(screen.getByRole("checkbox", { name: /Extra reserve/ })).not.toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "Clear selection" }));
    expect(fetchMock).toHaveBeenCalledTimes(calls);
    fireEvent.click(screen.getByRole("button", { name: "Save selection" }));
    await screen.findByText(/Selection saved locally/);
    expect(config.liquid_account_ids).toEqual([]);
    expect(fetchMock.mock.calls.filter(([, init]) => init.method === "PUT")).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledTimes(calls + 2);
  });

  it("disables Save after settings load error and recovers through retry", async () => {
    getSettingsStatus = 500;
    render(<RunwayPanel />);
    await screen.findByText("1.3 months");
    fireEvent.click(screen.getByText("Liquid account settings"));
    expect(await screen.findByRole("button", { name: "Save selection" })).toBeDisabled();
    expect(screen.getByText(/Could not load runway settings/)).toBeVisible();
    expect(screen.queryByText("0 accounts in saved selection.")).not.toBeInTheDocument();
    getSettingsStatus = 200;
    fireEvent.click(screen.getByRole("button", { name: "Retry settings" }));
    await screen.findByRole("checkbox", { name: /Reserve A/ });
    fireEvent.click(screen.getByRole("checkbox", { name: /Extra reserve/ }));
    expect(screen.getByRole("button", { name: "Save selection" })).toBeEnabled();
  });

  it("retains invalid selected options for removal, never silently drops them", async () => {
    config.accounts[0].eligible = false;
    config.accounts[0].issues = [issue("account_missing")];
    config.selection_status = "invalid";
    render(<RunwayPanel />);
    await openSettings();
    const option = screen.getByRole("checkbox", { name: /Reserve A/ });
    expect(option).toBeChecked();
    expect(option).toBeEnabled();
    expect(screen.getByRole("checkbox", { name: /Card A/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Save selection" })).toBeDisabled();
    fireEvent.click(option);
    expect(option).toBeDisabled();
    expect(screen.getByRole("button", { name: "Save selection" })).toBeEnabled();
  });

  it("retains draft on save failure and never echoes raw financial errors", async () => {
    putStatus = 400;
    render(<RunwayPanel />);
    await openSettings();
    fireEvent.click(screen.getByRole("checkbox", { name: /Extra reserve/ }));
    fireEvent.click(screen.getByRole("button", { name: "Save selection" }));
    await screen.findByRole("alert");
    expect(screen.getByRole("alert")).not.toHaveTextContent("987654");
    expect(screen.getByRole("checkbox", { name: /Extra reserve/ })).toBeChecked();
    expect(screen.getByText(/Results use the last loaded saved selection/)).toBeVisible();
    putStatus = 200;
    fireEvent.click(screen.getByRole("button", { name: "Save selection" }));
    await screen.findByText(/Selection saved locally/);
  });

  it("shows saving and local result error/retry states", async () => {
    const pending = deferred<Response>();
    render(<RunwayPanel />);
    await openSettings();
    fireEvent.click(screen.getByRole("checkbox", { name: /Extra reserve/ }));
    fetchMock.mockReturnValueOnce(pending.promise);
    fireEvent.click(screen.getByRole("button", { name: "Save selection" }));
    expect(screen.getByRole("button", { name: "Saving…" })).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: /Extra reserve/ })).toBeDisabled();
    fetchMock.mockResolvedValueOnce(jsonResponse({}, 500));
    await act(() => pending.resolve(jsonResponse(config)));
    await screen.findByText(/Could not load runway/);
    expect(screen.getByText(/Selection saved locally; result refresh failed/)).toBeVisible();
    expect(screen.queryByText("1.3 months")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry runway" }));
    await screen.findByText("1.3 months");
  });

  it("masks zero, signed balances and observations on all text/attribute surfaces", async () => {
    payload.selected_accounts[0].balance = -2345;
    payload.selected_accounts[1].balance = 0;
    payload.observations[0].owners[0].spending = 0;
    render(<RunwayPanel />);
    await screen.findByText("-2,345 kr");
    act(() => setAmountsHidden(true));
    const panel = screen.getByRole("region", { name: "Runway & Burn Rate" });
    expect(panel.innerHTML).not.toMatch(/2,345|0 kr|120,000|90,000|70,000/);
    expect(within(panel).getAllByText("****").length).toBeGreaterThan(15);
    expect(within(panel).getByText("1.3 months")).toBeVisible();
  });

  it("shows two common months, all coverage reasons, and independently unavailable owner reserves", async () => {
    payload.included_months = ["2026-07", "2026-09"];
    payload.included_month_count = 2;
    const missing = payload.observations[1];
    missing.status = "excluded";
    missing.coverage = "missing";
    missing.household_spending = null;
    missing.owners.forEach((owner) => { owner.spending = null; });
    missing.issues = [issue("missing_source", { month: missing.month, severity: "blocking" })];
    payload.owners[1] = { ...payload.owners[1], reserves: null, selected_account_ids: [], runway_months: null, runway_display: null, status: "unavailable", issues: [issue("no_selection")] };
    payload.household.issues = [issue("excluded_months")];
    render(<RunwayPanel />);
    await screen.findByText(/2 of 3 completed months/);
    expect(screen.getByText(/^Included months:/)).toHaveTextContent("July 2026, September 2026");
    expect(screen.getByRole("region", { name: "Partner B runway" })).toHaveTextContent("No selected reserve accounts");
    expect(screen.getByRole("region", { name: "Household runway" })).toHaveTextContent("1.3 months");
  });

  it("keeps currency-conflicting observations separate and labels every blocking issue", async () => {
    payload.household = {
      ...payload.household, reserves_currency_code: "USD", spending_currency_code: "NOK",
      currency_code: null, currency_status: "conflict", status: "unavailable",
      runway_months: null, runway_display: null,
      issues: [issue("currency_conflict", { severity: "blocking" }), issue("balance_date_unknown"), issue("coverage_unverified", { month: "2026-08" })],
    };
    render(<RunwayPanel />);
    await screen.findByText("120,000 USD");
    const household = screen.getByRole("region", { name: "Household runway" });
    expect(household).toHaveTextContent("90,000 kr");
    expect(household).toHaveTextContent("Incompatible currencies");
    expect(household).toHaveTextContent("Balance date unknown");
    expect(household).toHaveTextContent("August 2026");
    expect(screen.queryByText("1.3 months")).not.toBeInTheDocument();
  });

  it("retains and labels previous saved figures after a manual refresh fails", async () => {
    render(<RunwayPanel />);
    await screen.findByText("1.3 months");
    fetchMock.mockResolvedValueOnce(jsonResponse({}, 500));
    fireEvent.click(screen.getByRole("button", { name: "Refresh runway" }));
    await screen.findByRole("button", { name: "Retry runway" });
    expect(screen.getByText("1.3 months")).toBeVisible();
    expect(screen.getByText(/Refresh failed; previous result retained/)).toBeVisible();
  });

  it("uses stable identity for reordered owners and leaves rounded ratios to the backend", async () => {
    payload.owners.reverse();
    payload.owners[0].owner.label = "Partner B renamed";
    payload.household.runway_display = "1.3";
    payload.household.runway_months = 1.25;
    render(<RunwayPanel />);
    await screen.findByText("1.3 months");
    expect(screen.getByRole("region", { name: "Partner B renamed runway" })).toHaveTextContent("0.5 months");
    expect(screen.getByRole("region", { name: "July 2026 observation" })).toHaveTextContent("Partner B renamed");
    expect(screen.getByText("Reserve B · Partner B renamed")).toBeVisible();
  });
});

describe("runway presentation", () => {
  it("uses separate verified currencies without conversion, with privacy masking", () => {
    expect(runwayMoney(1234, "NOK")).toBe("1,234 kr");
    expect(runwayMoney(1234, "USD")).toBe("1,234 USD");
    expect(runwayMoney(null, null)).toBe("Unavailable");
    setAmountsHidden(true);
    expect(runwayMoney(-1234, "USD")).toBe("****");
    expect(runwayMoney(0, null)).toBe("****");
  });
  it("uses a static fallback for unknown issue codes", () => {
    expect(runwayIssueText(issue("raw 987654"))).not.toContain("987654");
    expect(runwayIssueText(issue("__proto__"))).toMatch(/Additional source limitation/);
  });
  it.each([
    "no_selection", "invalid_settings", "invalid_selection", "account_missing",
    "account_unowned", "account_excluded", "account_type_ineligible", "missing_balance",
    "invalid_balance", "insufficient_history", "missing_source", "invalid_source",
    "partial_source", "unproven_zero", "ownership_incomplete", "sources_changing",
    "currency_conflict", "nonpositive_reserves", "nonpositive_burn", "coverage_unverified",
    "currency_unverified", "source_stale", "source_date_unknown", "balance_stale",
    "balance_date_unknown", "balance_date_unverified", "classification_unverified",
    "excluded_months", "source_times_differ",
  ])("maps contract issue %s to static scoped copy", (code) => {
    const text = runwayIssueText(issue(code, { month: "2026-07", account_id: "1100001", partner_id: "owner_a" }), config.owners, config.accounts);
    expect(text).toContain("July 2026 · Partner A · Reserve A:");
    expect(text).not.toContain("Additional source limitation");
    expect(text).not.toContain(code);
  });
});
