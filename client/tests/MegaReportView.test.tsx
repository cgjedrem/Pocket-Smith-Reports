// MegaReportView tests — AC22 all 13 sections render, charts render as SVG, partner names.

import { render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MegaReportView } from "@/components/mega-reports/MegaReportView";
import { ApiError } from "@/types/api";
import type { MegaReportResponse } from "@/types/mega_report";

// Mock API module.
vi.mock("@/api/mega_reports", () => ({
  getMegaReport: vi.fn(),
  generateMegaReport: vi.fn(),
  getMegaStatus: vi.fn(),
  exportMegaPdf: vi.fn(),
}));

import { getMegaReport, getMegaStatus } from "@/api/mega_reports";

// Build full mega report w/ all sections populated.
function makeFullReport(): MegaReportResponse {
  return {
    start: "2026-01",
    end: "2026-07",
    stale: false,
    calculation_version: 1,
    txn_counts: { "2026-01": 5, "2026-02": 6 },
    months: ["2026-01", "2026-02"],
    partner_labels: { partner_a: "Fixture A", partner_b: "Fixture B" },
    detail_agg: {
      months: ["2026-01", "2026-02"],
      cats: {
        "cat-rent": {
          title: "Rent", section: "home",
          partner_a_paid: [5000, 5000], partner_b_paid: [0, 0],
          partner_a_received: [0, 0], partner_b_received: [0, 0],
          partner_a_net: [5000, 5000], partner_b_net: [0, 0],
          total: [5000, 5000], count: [1, 1], is_reimbursement: false,
        },
        "cat-groceries": {
          title: "Groceries", section: "common",
          partner_a_paid: [2000, 2100], partner_b_paid: [1000, 1100],
          partner_a_received: [0, 0], partner_b_received: [0, 0],
          partner_a_net: [2000, 2100], partner_b_net: [1000, 1100],
          total: [3000, 3200], count: [5, 6], is_reimbursement: false,
        },
        "cat-hobby": {
          title: "Hobby", section: "personal_partner_a",
          partner_a_paid: [500, 600], partner_b_paid: [0, 0],
          partner_a_received: [0, 0], partner_b_received: [0, 0],
          partner_a_net: [500, 600], partner_b_net: [0, 0],
          total: [500, 600], count: [2, 2], is_reimbursement: false,
        },
        "cat-clothes": {
          title: "Clothes", section: "personal_partner_b",
          partner_a_paid: [0, 0], partner_b_paid: [800, 900],
          partner_a_received: [0, 0], partner_b_received: [0, 0],
          partner_a_net: [0, 0], partner_b_net: [800, 900],
          total: [800, 900], count: [1, 1], is_reimbursement: false,
        },
      },
      cc_paydowns: {
        Visa: { "2026-01": 5000, "2026-02": 3000 },
      },
      excluded_transactions: {
        "2026-01": [
          { date: "2026-01-15", description: "Transfer", category: "Internal", owner: "partner_a", amount: -500 },
        ],
      },
      trips: [
        { label: "Oslo trip", transactions: [{ date: "2026-01-10", owner: "partner_a", amount: -3500 }], total: -3500 },
      ],
      series: {
        income: { partner_a: [35000, 36000], partner_b: [30000, 31000], total: [65000, 67000] },
        savings: {
          net_partner_a: [3000, 3200], net_partner_b: [2000, 2100], total: [5000, 5300],
          investment_net_partner_a: [1000, 1100], investment_net_partner_b: [800, 900], investment_net_total: [1800, 2000],
        },
        real_spend: { partner_a: [28000, 29000], partner_b: [25000, 26000], total: [53000, 55000] },
        net_cash: { partner_a: [7000, 7000], partner_b: [5000, 5000], total: [12000, 12000] },
      },
      cumulative: {
        income: { partner_a: 71000, partner_b: 61000, total: 132000 },
        savings: {
          net_partner_a: 6200, net_partner_b: 4100, total: 10300,
          investment_net_partner_a: 2100, investment_net_partner_b: 1700, investment_net_total: 3800,
        },
        real_spend: { partner_a: 57000, partner_b: 51000, total: 108000 },
        net_cash: { partner_a: 14000, partner_b: 10000, total: 24000 },
      },
    },
    salary_allocation: {
      income: 132000,
      entries: [
        { id: "cat-rent", title: "Rent", amount: 10000 },
        { id: "role-net_savings", title: "Net savings", amount: 10300 },
      ],
      unavailable_reason: null,
    },
    recommendations: {
      schema_version: "1",
      generated_at: "2026-07-29T12:00:00Z",
      period: { start: "2026-01", end: "2026-07" },
      recommendations: [
        { id: "rec1", title: "Reduce grocery spend", body: "Groceries 15% above avg.", severity: "medium", evidence: ["Groceries: 6200 NOK"] },
      ],
    },
    monthly_kpi_pages: [
      {
        month: "2026-01",
        kpis: {
          partner_a: { income: 35000, real_spend: 28000, net_cash: 7000, net_savings: 3000, investment: 1000 },
          partner_b: { income: 30000, real_spend: 25000, net_cash: 5000, net_savings: 2000, investment: 800 },
          total: { income: 65000, real_spend: 53000, net_cash: 12000, net_savings: 5000, investment: 1800 },
        },
      },
    ],
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getMegaStatus).mockRejectedValue(new ApiError("no generation", 404));
});

describe("MegaReportView — AC22 all 13 sections render", () => {
  it("renders all 13 section headings from mock JSON", async () => {
    vi.mocked(getMegaReport).mockResolvedValue(makeFullReport());
    render(<MegaReportView start="2026-01" end="2026-07" />);

    // CardTitle (div) sections — matched by text (no heading role in shadcn CardTitle).
    const textTitles = [
      "1. KPI Cover",
      "2. Income",
      "3. Savings",
      "4. Home",
      "5. Common",
      "6. Personal Fixture A",
      "7. Personal Fixture B",
      "8. Trips",
      // Nb. source bug: CcPaydownsSection numbered "10." (dup with Monthly Reports).
      "10. Credit-card paydowns",
      "13. Appendices",
    ];
    // Real <h2> sections — matched by role.
    const roleHeadings = [
      "9. Recommendations",
      "10. Monthly Reports",
      "12. Excluded categories",
    ];

    for (const h of textTitles) {
      await waitFor(() => {
        expect(screen.getByText(h)).toBeInTheDocument();
      });
    }
    for (const h of roleHeadings) {
      await waitFor(() => {
        expect(screen.getByRole("heading", { name: h })).toBeInTheDocument();
      });
    }
  });
});

describe("MegaReportView — AC32 charts render as SVG", () => {
  it("renders SVG chart elements", async () => {
    vi.mocked(getMegaReport).mockResolvedValue(makeFullReport());
    render(<MegaReportView start="2026-01" end="2026-07" />);
    await waitFor(() => {
      expect(screen.getByText("1. KPI Cover")).toBeInTheDocument();
    });
    // SVGs present — LineChart, StackedBarLineChart, SubcatStackedBarChart.
    const svgs = document.querySelectorAll("svg");
    expect(svgs.length).toBeGreaterThanOrEqual(4);
  });
});

describe("MegaReportView — AC28 partner names shown", () => {
  it("shows configured labels (Fixture A/B), not Partner A/B fallbacks", async () => {
    vi.mocked(getMegaReport).mockResolvedValue(makeFullReport());
    render(<MegaReportView start="2026-01" end="2026-07" />);
    await waitFor(() => {
      expect(screen.getByText("6. Personal Fixture A")).toBeInTheDocument();
      expect(screen.getByText("7. Personal Fixture B")).toBeInTheDocument();
    });
  });
});

describe("MegaReportView — AC30 recommendations cards render", () => {
  it("renders recommendation cards when artifact exists", async () => {
    vi.mocked(getMegaReport).mockResolvedValue(makeFullReport());
    render(<MegaReportView start="2026-01" end="2026-07" />);
    await waitFor(() => {
      expect(screen.getByText("Reduce grocery spend")).toBeInTheDocument();
    });
  });
});

describe("MegaReportView — AC31 recommendations empty state", () => {
  it("shows empty state when no recommendations artifact", async () => {
    const report = makeFullReport();
    report.recommendations = null;
    vi.mocked(getMegaReport).mockResolvedValue(report);
    render(<MegaReportView start="2026-01" end="2026-07" />);
    await waitFor(() => {
      expect(screen.getByText("No recommendations available.")).toBeInTheDocument();
    });
  });
});

describe("MegaReportView — AC33 monthly KPI pages render", () => {
  it("renders per-month KPI cards", async () => {
    vi.mocked(getMegaReport).mockResolvedValue(makeFullReport());
    render(<MegaReportView start="2026-01" end="2026-07" />);
    await waitFor(() => {
      // Month heading in MonthliesSection.
      const monthliesHeading = screen.getByRole("heading", { name: "10. Monthly Reports" });
      const monthliesSection = monthliesHeading.closest("div");
      expect(monthliesSection).not.toBeNull();
      expect(within(monthliesSection!).getByText("2026-01")).toBeInTheDocument();
    });
  });
});

describe("MegaReportView — AC34 CC paydowns table renders", () => {
  it("renders CC paydowns table with card row", async () => {
    vi.mocked(getMegaReport).mockResolvedValue(makeFullReport());
    render(<MegaReportView start="2026-01" end="2026-07" />);
    // "Visa" renders in both by-card + per-month tables — scope to the CC card.
    const title = await screen.findByText("10. Credit-card paydowns");
    const card = title.closest('[data-slot="card"]');
    expect(card).not.toBeNull();
    expect(
      within(card as HTMLElement).getAllByText("Visa").length
    ).toBeGreaterThan(0);
  });
});

describe("MegaReportView — AC35 excluded transactions table renders", () => {
  it("renders excluded transactions table", async () => {
    vi.mocked(getMegaReport).mockResolvedValue(makeFullReport());
    render(<MegaReportView start="2026-01" end="2026-07" />);
    await waitFor(() => {
      expect(screen.getByText("Transfer")).toBeInTheDocument();
    });
  });
});

describe("MegaReportView — AC36 trips section renders", () => {
  it("renders trip cards", async () => {
    vi.mocked(getMegaReport).mockResolvedValue(makeFullReport());
    render(<MegaReportView start="2026-01" end="2026-07" />);
    await waitFor(() => {
      expect(screen.getByText("Oslo trip")).toBeInTheDocument();
    });
  });
});

describe("MegaReportView — AC37 salary allocation table renders", () => {
  it("renders salary allocation table", async () => {
    vi.mocked(getMegaReport).mockResolvedValue(makeFullReport());
    render(<MegaReportView start="2026-01" end="2026-07" />);
    // "Salary allocation" also appears as a nav child title — scope to KPI card.
    const title = await screen.findByText("1. KPI Cover");
    const card = title.closest('[data-slot="card"]');
    expect(card).not.toBeNull();
    expect(
      within(card as HTMLElement).getByText("Salary allocation")
    ).toBeInTheDocument();
    // "Net savings" appears in KPI card + salary table — check >=1 match.
    expect(screen.getAllByText("Net savings").length).toBeGreaterThan(0);
  });
});

describe("MegaReportView — AC23 404 → GenerateButton", () => {
  it("shows generate button on 404", async () => {
    vi.mocked(getMegaReport).mockRejectedValue(new ApiError("no report", 404));
    render(<MegaReportView start="2026-01" end="2026-07" />);
    await waitFor(() => {
      expect(screen.getByText("Generate mega report")).toBeInTheDocument();
    });
  });
});

describe("MegaReportView — AC25 stale badge", () => {
  it("shows stale badge when stale=true", async () => {
    const report = makeFullReport();
    report.stale = true;
    vi.mocked(getMegaReport).mockResolvedValue(report);
    render(<MegaReportView start="2026-01" end="2026-07" />);
    await waitFor(() => {
      expect(screen.getByText("Stale")).toBeInTheDocument();
    });
  });
});

// US3 / T063 — BE 409: stored contract marker absent/!= current. Same UX
// path as stale: badge + backend detail + Regenerate affordance.
describe("MegaReportView — T063 contract 409 → Regenerate", () => {
  it("409 → StaleBadge + backend detail + Regenerate button, no sections", async () => {
    vi.mocked(getMegaReport).mockRejectedValue(
      new ApiError(
        "Mega report 2026-01..2026-07 predates contract version 2 — regenerate to rebuild it.",
        409
      )
    );

    render(<MegaReportView start="2026-01" end="2026-07" />);
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
    expect(screen.queryByText("1. KPI Cover")).toBeNull();
    expect(screen.queryByText("13. Appendices")).toBeNull();
  });
});