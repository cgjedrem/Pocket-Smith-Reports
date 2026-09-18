// ReportView tests — F16 / AC24. All 8 sections render, charts render.
// PR3 (monthly-reports-logic-migration): fixture now supplies report.detailed
// (server-computed DTO) directly — components no longer derive section
// content from normalized_transactions/savings_summary/detailed_section_mapping
// category routing, so tests assert against the detailed fixture, not
// recomputed transaction math.

import { render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ReportView } from "@/components/reports/ReportView";
import { ApiError } from "@/types/api";
import type { DetailedSections, ReportResponse } from "@/types/report";

// Mock reports API.
vi.mock("@/api/reports", () => ({
  getReport: vi.fn(),
  generateReport: vi.fn(),
  getStatus: vi.fn(),
  exportPdf: vi.fn(),
}));

// Mock shared SCSS import — no-op.
vi.mock("@/styles/report-shared.scss", () => ({}));

import { getReport, getStatus } from "@/api/reports";

// Full detailed DTO — every section populated so all headings/tables render.
// Values are internally consistent with kpis/personal_share below but the
// frontend never recomputes them; they arrive pre-computed from the server.
// Sign convention mirrors the real builders + golden fixture: expense/net
// sections carry positive magnitudes with *_class "pos" (spending is not
// negated in detailed DTOs); only paired-reimbursement legs are signed by
// direction and net-zero rows read "zero". Keeping this fixture
// golden-convention-shaped is what lets the chart paths (r.total > 0)
// actually execute in tests.
function makeDetailed(): DetailedSections {
  return {
    income: {
      salary: {
        partner_a: 500,
        partner_a_class: "pos",
        partner_b: 500,
        partner_b_class: "pos",
        total: 1000,
        total_class: "pos",
        row_pct_partner_a: 50.0,
        row_pct_partner_b: 50.0,
        household_pct: 100.0,
      },
      third_party: {
        partner_a: 0,
        partner_a_class: "zero",
        partner_b: 0,
        partner_b_class: "zero",
        total: 0,
        total_class: "zero",
        row_pct_partner_a: null,
        row_pct_partner_b: null,
        household_pct: null,
      },
      total_partner_a: 500,
      total_partner_a_class: "pos",
      total_partner_b: 500,
      total_partner_b_class: "pos",
      total_income: 1000,
      total_income_class: "pos",
    },
    savings: {
      partner_a: {
        to_savings: 50,
        to_savings_class: "pos",
        from_savings: 0,
        from_savings_class: "zero",
        net_saved: 50,
        net_saved_class: "pos",
        income: 500,
        income_class: "pos",
        rate: 10.0,
      },
      partner_b: {
        to_savings: 50,
        to_savings_class: "pos",
        from_savings: 0,
        from_savings_class: "zero",
        net_saved: 50,
        net_saved_class: "pos",
        income: 500,
        income_class: "pos",
        rate: 10.0,
      },
      household: {
        to_savings: 100,
        to_savings_class: "pos",
        from_savings: 0,
        from_savings_class: "zero",
        net_saved: 100,
        net_saved_class: "pos",
        income: 1000,
        income_class: "pos",
        rate: 10.0,
      },
    },
    home: {
      rows: [
        {
          category_title: "Rent",
          partner_a_net: 160,
          partner_a_net_class: "pos",
          partner_b_net: 160,
          partner_b_net_class: "pos",
          total: 320,
          total_class: "pos",
          g_share_partner_a: 50.0,
          g_share_partner_b: 50.0,
        },
      ],
      paired_reimbursements: [],
      total_partner_a: 160,
      total_partner_a_class: "pos",
      total_partner_b: 160,
      total_partner_b_class: "pos",
      total: 320,
      total_class: "pos",
      share_partner_a: 50.0,
      share_partner_b: 50.0,
    },
    common: {
      rows: [
        {
          category_title: "Groceries",
          partner_a_net: 100,
          partner_a_net_class: "pos",
          partner_b_net: 80,
          partner_b_net_class: "pos",
          total: 180,
          total_class: "pos",
          g_share_partner_a: 55.6,
          g_share_partner_b: 44.4,
        },
      ],
      paired_reimbursements: [
        {
          category_title: "Utilities",
          partner_a: 50,
          partner_a_class: "pos",
          partner_b: -50,
          partner_b_class: "neg",
          total: 0,
          total_class: "zero",
        },
      ],
      total_partner_a: 100,
      total_partner_a_class: "pos",
      total_partner_b: 80,
      total_partner_b_class: "pos",
      total: 180,
      total_class: "pos",
      share_partner_a: 55.6,
      share_partner_b: 44.4,
    },
    personal_partner_a: {
      rows: [
        {
          category_title: "Hobby",
          paid_partner_a: 100,
          paid_partner_a_class: "pos",
          paid_partner_b: 0,
          paid_partner_b_class: "zero",
          total: 100,
          total_class: "pos",
          // Row % is against the COMBINED personal_total (shared across both
          // personal sections) — mirrors detailed_personal_sections.
          pct_personal: 66.7,
          pct_household: 66.7,
        },
      ],
      personal_total: 150,
      personal_total_class: "pos",
      household_total: 150,
      household_total_class: "pos",
      pct_personal: 100.0,
      pct_household: 66.7,
    },
    personal_partner_b: {
      rows: [
        {
          category_title: "Clothes",
          paid_partner_a: 0,
          paid_partner_a_class: "zero",
          paid_partner_b: 50,
          paid_partner_b_class: "pos",
          total: 50,
          total_class: "pos",
          pct_personal: 33.3,
          pct_household: 33.3,
        },
      ],
      personal_total: 150,
      personal_total_class: "pos",
      household_total: 150,
      household_total_class: "pos",
      pct_personal: 100.0,
      pct_household: 33.3,
    },
    trips: {
      rows: [],
      paired_reimbursements: [],
      total_partner_a: 0,
      total_partner_a_class: "zero",
      total_partner_b: 0,
      total_partner_b_class: "zero",
      total: 0,
      total_class: "zero",
      share_partner_a: null,
      share_partner_b: null,
    },
    cc_payments: {
      partner_a_paid: 30,
      partner_a_paid_class: "pos",
      partner_b_paid: 20,
      partner_b_paid_class: "pos",
      household_paid: 50,
      household_paid_class: "pos",
    },
    excluded: {
      rows: [
        {
          category_title: "Gifts",
          paid_partner_a: 20,
          paid_partner_a_class: "pos",
          paid_partner_b: 10,
          paid_partner_b_class: "pos",
          total: 30,
          total_class: "pos",
        },
      ],
      total: 30,
      total_class: "pos",
    },
    household_totals: null,
  };
}

// Build full report with all sections populated.
function makeFullReport(): ReportResponse {
  return {
    month: "2026-07",
    stale: false,
    txn_count: 5,
    normalized_transactions: [
      {
        id: "t1",
        date: "2026-07-03",
        amount: -450.5,
        payee: "Rema 1000",
        note: "Weekly shop",
        account_id: "acc1",
        account_name: "Checking",
        owner: "partner_a",
        category_path: [
          { id: "root1", title: "Groceries" },
          { id: "leaf1", title: "Supermarket" },
        ],
        is_transfer: false,
      },
    ],
    categories: [],
    reconciliation: { source: 1000, report: 1000, difference: 0 },
    detailed_section_mapping: {
      category_sections: { leaf1: "common" },
      account_roles: {},
    },
    kpis: {
      partner_a: {
        income: 500,
        real_spend: 300,
        personal_spend: 100,
        net_cash: 200,
        net_savings: 50,
        investment: 0,
      },
      partner_b: {
        income: 500,
        real_spend: 200,
        personal_spend: 50,
        net_cash: 300,
        net_savings: 50,
        investment: 0,
      },
      total: {
        income: 1000,
        real_spend: 500,
        personal_spend: 150,
        net_cash: 500,
        net_savings: 100,
        investment: 0,
      },
    },
    savings_summary: {
      partner_a: { to_savings: 50, from_savings: 0, net_saved: 50 },
      partner_b: { to_savings: 50, from_savings: 0, net_saved: 50 },
      total: { to_savings: 100, from_savings: 0, net_saved: 100 },
    },
    root_totals: { paid: 500, received: 1000, net: 500, count: 5 },
    owner_totals: {
      partner_a: { paid: 250, received: 500, net: 250 },
      partner_b: { paid: 250, received: 500, net: 250 },
    },
    partner_panels: {
      partner_a: { label: "Fixture A", paid: 250, received: 500, net: 250, net_class: "pos" },
      partner_b: { label: "Fixture B", paid: 250, received: 500, net: 250, net_class: "pos" },
    },
    partner_labels: { partner_a: "Fixture A", partner_b: "Fixture B" },
    detailed: makeDetailed(),
    personal_share: 30.0,
    balanced: true,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getStatus).mockRejectedValue(new ApiError("no generation", 404));
});

describe("ReportView — AC24 all 8 sections render", () => {
  it("renders savings section from report.detailed.savings", async () => {
    const report = makeFullReport();
    report.month = "2026-08";
    // Server-computed savings section — household/partner_a values differ
    // from the base fixture's kpis on purpose, to prove the section reads
    // detailed.savings directly rather than recomputing anything.
    report.detailed!.savings = {
      partner_a: {
        to_savings: 2500,
        to_savings_class: "pos",
        from_savings: 400,
        from_savings_class: "pos",
        net_saved: 2100,
        net_saved_class: "pos",
        income: 5000,
        income_class: "pos",
        rate: 42.0,
      },
      partner_b: {
        to_savings: 300,
        to_savings_class: "pos",
        from_savings: 50,
        from_savings_class: "pos",
        net_saved: 250,
        net_saved_class: "pos",
        income: 1000,
        income_class: "pos",
        rate: 25.0,
      },
      household: {
        to_savings: 2800,
        to_savings_class: "pos",
        from_savings: 450,
        from_savings_class: "pos",
        net_saved: 2350,
        net_saved_class: "pos",
        income: 6000,
        income_class: "pos",
        rate: 39.2,
      },
    };
    report.kpis!.partner_a.net_savings = 700;
    report.kpis!.partner_b.net_savings = 77;
    report.kpis!.total.net_savings = 777;
    vi.mocked(getReport).mockResolvedValue(report);

    render(<ReportView month="2026-07" />);

    const savingsHeading = await screen.findByRole("heading", { name: "2. Savings" });
    const savingsSection = savingsHeading.closest("section");
    expect(savingsSection).not.toBeNull();
    expect(within(savingsSection!).getByText("Household").closest("tr")).toHaveTextContent(
      /Household\s*2,800\.00\s*450\.00\s*2,350\.00/
    );
    expect(within(savingsSection!).getByText("Fixture A").closest("tr")).toHaveTextContent(
      /Fixture A\s*2,500\.00\s*400\.00\s*2,100\.00/
    );
    const kpiSummary = screen.getByRole("heading", { name: "KPI Role Summary" }).closest("section");
    expect(kpiSummary).not.toBeNull();
    expect(within(kpiSummary!).getByText("777.00")).toBeInTheDocument();
    const netSavingsChart = within(kpiSummary!).getByText("3. Net savings").closest("svg");
    expect(netSavingsChart).not.toBeNull();
    expect(netSavingsChart).toHaveTextContent(/3\. Net savings.*700.*77/);
  });

  it("shows unavailable savings state when report.detailed.savings is null", async () => {
    const report = makeFullReport();
    report.detailed!.savings = null;
    vi.mocked(getReport).mockResolvedValue(report);

    render(<ReportView month="2026-07" />);

    const savingsHeading = await screen.findByRole("heading", { name: "2. Savings" });
    const savingsSection = savingsHeading.closest("section");
    expect(savingsSection).not.toBeNull();
    expect(within(savingsSection!).getByRole("status")).toHaveTextContent(
      "Savings summary unavailable. Regenerate this report to view savings values."
    );
    expect(within(savingsSection!).queryByText("Household")).not.toBeInTheDocument();
    expect(within(savingsSection!).queryByText("0.00")).not.toBeInTheDocument();
  });

  it("keeps ready actions in the report toolbar at matching default button size", async () => {
    vi.mocked(getReport).mockResolvedValue(makeFullReport());

    render(<ReportView month="2026-07" toolbarStart={<button>2026-07</button>} />);

    const toolbar = await screen.findByRole("toolbar", { name: "Report controls" });
    expect(toolbar).toHaveTextContent("2026-07");
    expect(toolbar).toHaveTextContent("Report — 2026-07");
    expect(toolbar).toHaveTextContent("Export PDF");
    expect(toolbar).toHaveTextContent("Regenerate");
    expect(screen.getByRole("button", { name: "Export PDF" })).toHaveAttribute("data-size", "default");
    expect(screen.getByRole("button", { name: "Regenerate" })).toHaveAttribute("data-size", "default");
  });

  it("renders overview + all section headings", async () => {
    vi.mocked(getReport).mockResolvedValue(makeFullReport());

    render(<ReportView month="2026-07" />);
    // Overview.
    await waitFor(() =>
      expect(screen.getByText("Monthly Report")).toBeInTheDocument()
    );
    // KPI role summary.
    expect(screen.getByText("KPI Role Summary")).toBeInTheDocument();
    // Detailed sections.
    expect(screen.getByText("Detailed Sections")).toBeInTheDocument();
    // Reconciliation.
    expect(screen.getByText("Reconciliation")).toBeInTheDocument();
  });

  it("renders configured partner labels — Fixture A/Fixture B", async () => {
    vi.mocked(getReport).mockResolvedValue(makeFullReport());

    render(<ReportView month="2026-07" />);
    await waitFor(() => expect(screen.getAllByText("Fixture A").length).toBeGreaterThan(0));
    expect(screen.getAllByText("Fixture B").length).toBeGreaterThan(0);
  });

  it("renders reconciliation balanced indicator from report.balanced", async () => {
    vi.mocked(getReport).mockResolvedValue(makeFullReport());

    render(<ReportView month="2026-07" />);
    await waitFor(() => expect(screen.getByText("Balanced")).toBeInTheDocument());
  });

  it("renders reconciliation review-needed indicator when report.balanced is false", async () => {
    const report = makeFullReport();
    report.balanced = false;
    vi.mocked(getReport).mockResolvedValue(report);

    render(<ReportView month="2026-07" />);
    await waitFor(() => expect(screen.getByText("Review needed")).toBeInTheDocument());
    expect(screen.queryByText("Balanced")).not.toBeInTheDocument();
  });

  it("renders SVG charts — KPI matrix", async () => {
    vi.mocked(getReport).mockResolvedValue(makeFullReport());

    const { container } = render(<ReportView month="2026-07" />);
    await waitFor(() =>
      expect(container.querySelector("svg")).not.toBeNull()
    );
  });

  it("renders null percentages as an em-dash instead of a fabricated 0%", async () => {
    vi.mocked(getReport).mockResolvedValue(makeFullReport());

    render(<ReportView month="2026-07" />);
    const incomeHeading = await screen.findByRole("heading", { name: "1. Income" });
    const incomeSection = incomeHeading.closest("section");
    expect(incomeSection).not.toBeNull();
    // Third Party Income row has null row_pct_partner_a/b + household_pct.
    const thirdPartyRow = within(incomeSection!).getByText("Third Party Income").closest("tr");
    expect(thirdPartyRow).not.toBeNull();
    expect(within(thirdPartyRow!).getAllByText("—").length).toBe(3);
  });

  it("shows the no-income empty state when report.detailed.income is null", async () => {
    const report = makeFullReport();
    report.detailed!.income = null;
    vi.mocked(getReport).mockResolvedValue(report);

    render(<ReportView month="2026-07" />);

    const incomeHeading = await screen.findByRole("heading", { name: "1. Income" });
    const incomeSection = incomeHeading.closest("section");
    expect(incomeSection).not.toBeNull();
    expect(within(incomeSection!).getByRole("status")).toHaveTextContent(
      "No income this month."
    );
    expect(within(incomeSection!).queryByText("Total Income")).not.toBeInTheDocument();
  });

  it("renders bar-chart entries for positive-total categories (golden sign convention)", async () => {
    vi.mocked(getReport).mockResolvedValue(makeFullReport());

    render(<ReportView month="2026-07" />);

    // Chart paths filter `r.total > 0` — a real server DTO (positive
    // expense magnitudes) puts category labels inside the chart SVG; the
    // old negative-magnitude fixture made this filter drop every row, so
    // the charts below never rendered in tests.
    const commonHeading = await screen.findByRole("heading", { name: "4. Common" });
    const commonSection = commonHeading.closest("section");
    const commonChart = commonSection!.querySelector("svg");
    expect(commonChart).not.toBeNull();
    expect(commonChart).toHaveTextContent("Groceries");

    const personalHeading = screen.getByRole("heading", {
      name: "5. Fixture A personal spending",
    });
    const personalSection = personalHeading.closest("section");
    const personalChart = personalSection!.querySelector("svg");
    expect(personalChart).not.toBeNull();
    expect(personalChart).toHaveTextContent("Hobby");
  });

  it("shows detailed sections unavailable state when report.detailed is null", async () => {
    const report = makeFullReport();
    report.detailed = null;
    vi.mocked(getReport).mockResolvedValue(report);

    render(<ReportView month="2026-07" />);
    await waitFor(() =>
      expect(
        screen.getByText(
          "Detailed sections unavailable. Regenerate this report to view section detail."
        )
      ).toBeInTheDocument()
    );
  });
});

describe("ReportView — AC25 404 → GenerateButton", () => {
  it("404 → shows Generate button + not generated message", async () => {
    vi.mocked(getReport).mockRejectedValue(new ApiError("no report generated yet", 404));

    render(<ReportView month="2026-07" />);
    await waitFor(() =>
      expect(screen.getByText(/No report generated yet/i)).toBeInTheDocument()
    );
    expect(screen.getByRole("button", { name: /Generate report/i })).toBeInTheDocument();
  });
});

describe("ReportView — AC27 stale badge", () => {
  it("stale=true → StaleBadge shows", async () => {
    const report = makeFullReport();
    report.stale = true;
    vi.mocked(getReport).mockResolvedValue(report);

    render(<ReportView month="2026-07" />);
    await waitFor(() => expect(screen.getByText("Stale")).toBeInTheDocument());
  });
});

// US3 / T063 — BE 409: stored contract marker absent/!= current. Same UX
// path as stale: badge + backend detail + Regenerate affordance.
describe("ReportView — T063 contract 409 → Regenerate", () => {
  it("409 → StaleBadge + backend detail + Regenerate button, no sections", async () => {
    vi.mocked(getReport).mockRejectedValue(
      new ApiError(
        "Report for 2026-07 predates contract version 2 — regenerate to rebuild it.",
        409
      )
    );

    render(<ReportView month="2026-07" />);
    await waitFor(() =>
      expect(
        screen.getByText(/predates contract version 2/)
      ).toBeInTheDocument()
    );
    expect(screen.getByText("Stale")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Regenerate/i })
    ).toBeInTheDocument();
    // Sections must NOT render from a mismatched payload.
    expect(screen.queryByText("Detailed Sections")).toBeNull();
    expect(screen.queryByText("Monthly Report")).toBeNull();
  });
});
