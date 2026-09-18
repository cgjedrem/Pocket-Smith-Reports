// MegaReportsPage tests — AC19-AC29. Year picker, range picker, generated list, 404, generate flow, stale.

import { render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GeneratedReportsList } from "@/components/mega-reports/GeneratedReportsList";
import { MegaReportsPage } from "@/pages/MegaReportsPage";
import { ApiError } from "@/types/api";
import type { MegaReportList, MegaReportResponse } from "@/types/mega_report";
import type { MonthList } from "@/types/report";

// Mock API modules.
vi.mock("@/api/mega_reports", () => ({
  getMegaReports: vi.fn(),
  generateMegaReport: vi.fn(),
  getMegaReport: vi.fn(),
  getMegaStatus: vi.fn(),
  exportMegaPdf: vi.fn(),
}));

vi.mock("@/api/reports", () => ({
  getMonths: vi.fn(),
}));

import { getMegaReport, getMegaReports, getMegaStatus, generateMegaReport } from "@/api/mega_reports";
import { getMonths } from "@/api/reports";

// Build minimal mega report for stale + ready tests.
function makeReport(over: Partial<MegaReportResponse> = {}): MegaReportResponse {
  return {
    start: "2026-01",
    end: "2026-07",
    stale: false,
    calculation_version: 1,
    txn_counts: {},
    months: ["2026-01", "2026-02"],
    partner_labels: { partner_a: "Fixture A", partner_b: "Fixture B" },
    detail_agg: {
      months: ["2026-01", "2026-02"],
      cats: {},
      cc_paydowns: {},
      excluded_transactions: {},
      trips: [],
      series: {
        income: { partner_a: [1000, 2000], partner_b: [500, 600], total: [1500, 2600] },
        savings: {
          net_partner_a: [100, 200], net_partner_b: [50, 60], total: [150, 260],
          investment_net_partner_a: [0, 0], investment_net_partner_b: [0, 0], investment_net_total: [0, 0],
        },
        real_spend: { partner_a: [800, 900], partner_b: [400, 500], total: [1200, 1400] },
        net_cash: { partner_a: [200, 1100], partner_b: [100, 100], total: [300, 1200] },
      },
      cumulative: {
        income: { partner_a: 3000, partner_b: 1100, total: 4100 },
        savings: {
          net_partner_a: 300, net_partner_b: 110, total: 410,
          investment_net_partner_a: 0, investment_net_partner_b: 0, investment_net_total: 0,
        },
        real_spend: { partner_a: 1700, partner_b: 900, total: 2600 },
        net_cash: { partner_a: 1300, partner_b: 200, total: 1500 },
      },
    },
    salary_allocation: { income: 4100, entries: [], unavailable_reason: null },
    recommendations: null,
    monthly_kpi_pages: [],
    ...over,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getMegaReports).mockResolvedValue({ reports: [] } as MegaReportList);
  vi.mocked(getMonths).mockResolvedValue({ months: ["2026-07", "2026-06", "2026-01"] } as MonthList);
  vi.mocked(getMegaStatus).mockRejectedValue(new ApiError("no generation", 404));
  vi.mocked(getMegaReport).mockRejectedValue(new ApiError("no report", 404));
  vi.mocked(generateMegaReport).mockResolvedValue({ status: "generating", errors: [], started_at: null, completed_at: null });
});

describe("MegaReportsPage — AC19 page renders", () => {
  it("renders range picker + page chrome", async () => {
    render(<MegaReportsPage />);
    await waitFor(() => {
      expect(screen.getByText("Mega Reports")).toBeInTheDocument();
    });
    // Range picker labels (no standalone year picker — month pickers cover it).
    expect(screen.getByText("Start month")).toBeInTheDocument();
    expect(screen.getByText("End month")).toBeInTheDocument();
    // Generated list section only renders when reports exist (US3 AC21).
    expect(screen.queryByText("Generated reports")).not.toBeInTheDocument();
  });

  it("shows empty generated list when no reports", async () => {
    render(<GeneratedReportsList reports={[]} value={null} onChange={() => {}} />);
    expect(screen.getByText("No reports generated yet.")).toBeInTheDocument();
  });

  it("renders generated reports list when reports exist", async () => {
    vi.mocked(getMegaReports).mockResolvedValue({
      reports: [{ start: "2026-01", end: "2026-03" }],
    });
    render(<MegaReportsPage />);
    await waitFor(() => {
      expect(screen.getByText("Generated reports")).toBeInTheDocument();
    });
    expect(screen.getByText("1 generated")).toBeInTheDocument();
    expect(screen.getByText("2026-01 → 2026-03")).toBeInTheDocument();
  });
});

describe("MegaReportsPage — AC20 year picker fills range", () => {
  it("auto-selects newest year Jan–Dec when no reports", async () => {
    render(<MegaReportsPage />);
    await waitFor(() => {
      expect(getMegaReport).toHaveBeenCalledWith("2026-01", "2026-12");
    });
  });
});

describe("MegaReportsPage — AC22 click generated report fetches", () => {
  it("auto-selects newest generated report on mount", async () => {
    vi.mocked(getMegaReports).mockResolvedValue({
      reports: [{ start: "2026-01", end: "2026-07" }],
    });
    render(<MegaReportsPage />);
    await waitFor(() => {
      expect(getMegaReport).toHaveBeenCalledWith("2026-01", "2026-07");
    });
  });
});

describe("MegaReportsPage — AC23 404 → GenerateButton shows", () => {
  it("shows generate button when report 404", async () => {
    render(<MegaReportsPage />);
    await waitFor(() => {
      expect(screen.getByText("Generate mega report")).toBeInTheDocument();
    });
  });
});

describe("MegaReportsPage — AC24 generate flow", () => {
  it("clicks generate → calls generateMegaReport", async () => {
    render(<MegaReportsPage />);
    const btn = await screen.findByText("Generate mega report");
    btn.click();
    await waitFor(() => {
      expect(generateMegaReport).toHaveBeenCalled();
    });
  });
});

describe("MegaReportsPage — AC25 stale badge shows", () => {
  it("renders stale badge when report.stale=true", async () => {
    vi.mocked(getMegaReport).mockResolvedValue(makeReport({ stale: true }));
    render(<MegaReportsPage />);
    await waitFor(() => {
      expect(screen.getByText("Stale")).toBeInTheDocument();
    });
  });
});

describe("MegaReportsPage — AC28 partner names shown", () => {
  it("shows configured labels (Fixture A/B), not Partner A/B fallbacks", async () => {
    vi.mocked(getMegaReport).mockResolvedValue(makeReport());
    render(<MegaReportsPage />);
    await waitFor(() => {
      expect(screen.getAllByText(/Fixture A/).length).toBeGreaterThan(0);
    });
  });
});

describe("MegaReportsPage — AC29 missing months warning", () => {
  it("shows missing months warning when range has gaps", async () => {
    // Default range 2026-01 → 2026-12, months only has 2026-01, 2026-06, 2026-07.
    render(<MegaReportsPage />);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/Missing:/);
    });
  });
});