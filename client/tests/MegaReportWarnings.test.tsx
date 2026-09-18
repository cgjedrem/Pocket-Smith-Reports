// Tests for mega report warnings display (US4 additive).
// Warnings should render as a banner when present, and be absent when empty or undefined.

import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock mega reports API *before* imports
vi.mock("@/api/mega_reports", () => ({
  getMegaReport: vi.fn(),
  generateMegaReport: vi.fn(),
  getMegaStatus: vi.fn(),
  exportMegaPdf: vi.fn(),
}));

import { render, screen, waitFor } from "@testing-library/react";
import { MegaReportView } from "@/components/mega-reports/MegaReportView";
import { ApiError } from "@/types/api";
import type { MegaReportResponse } from "@/types/mega_report";
import { getMegaReport, getMegaStatus } from "@/api/mega_reports";

function makeMegaReportWithWarnings(warnings?: string[]): MegaReportResponse {
  return {
    start: "2026-01",
    end: "2026-07",
    stale: false,
    calculation_version: 1,
    txn_counts: {},
    months: [],
    partner_labels: { partner_a: "Fixture A", partner_b: "Fixture B" },
    detail_agg: {
      months: [],
      cats: {},
      cc_paydowns: {},
      excluded_transactions: {},
      trips: [],
      series: {
        income: { partner_a: [], partner_b: [], total: [] },
        savings: {
          net_partner_a: [],
          net_partner_b: [],
          total: [],
          investment_net_partner_a: [],
          investment_net_partner_b: [],
          investment_net_total: [],
        },
        real_spend: { partner_a: [], partner_b: [], total: [] },
        net_cash: { partner_a: [], partner_b: [], total: [] },
      },
      cumulative: {
        income: { partner_a: 0, partner_b: 0, total: 0 },
        savings: {
          net_partner_a: 0,
          net_partner_b: 0,
          total: 0,
          investment_net_partner_a: 0,
          investment_net_partner_b: 0,
          investment_net_total: 0,
        },
        real_spend: { partner_a: 0, partner_b: 0, total: 0 },
        net_cash: { partner_a: 0, partner_b: 0, total: 0 },
      },
    },
    salary_allocation: {
      income: 0,
      entries: [],
      unavailable_reason: null,
    },
    recommendations: null,
    monthly_kpi_pages: [],
    ...(warnings !== undefined && { warnings }),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getMegaStatus).mockRejectedValue(new ApiError("no generation", 404));
});

describe("MegaReportView — warnings banner (US4)", () => {
  it("renders warning banner when mega report has warnings", async () => {
    const report = makeMegaReportWithWarnings([
      "Multiple partners detected",
      "Label consistency check failed",
    ]);
    vi.mocked(getMegaReport).mockResolvedValue(report);

    render(<MegaReportView start="2026-01" end="2026-07" />);

    await waitFor(() => {
      expect(screen.getByText("Fidelity warnings")).toBeInTheDocument();
    });

    expect(screen.getByText("Multiple partners detected")).toBeInTheDocument();
    expect(screen.getByText("Label consistency check failed")).toBeInTheDocument();
  });

  it("does not render banner when warnings array is empty", async () => {
    const report = makeMegaReportWithWarnings([]);
    vi.mocked(getMegaReport).mockResolvedValue(report);

    render(<MegaReportView start="2026-01" end="2026-07" />);

    await waitFor(() => {
      expect(screen.getByText(/Mega Report/i)).toBeInTheDocument();
    });

    expect(screen.queryByText("Fidelity warnings")).not.toBeInTheDocument();
  });

  it("does not render banner when warnings field is absent (legacy mega report)", async () => {
    const report = makeMegaReportWithWarnings();
    // Explicitly remove warnings to simulate legacy report
    delete report.warnings;
    vi.mocked(getMegaReport).mockResolvedValue(report);

    render(<MegaReportView start="2026-01" end="2026-07" />);

    await waitFor(() => {
      expect(screen.getByText(/Mega Report/i)).toBeInTheDocument();
    });

    expect(screen.queryByText("Fidelity warnings")).not.toBeInTheDocument();
  });

  it("renders multiple warnings as a list", async () => {
    const warnings = [
      "First warning message",
      "Second warning message",
      "Third warning message",
    ];
    const report = makeMegaReportWithWarnings(warnings);
    vi.mocked(getMegaReport).mockResolvedValue(report);

    render(<MegaReportView start="2026-01" end="2026-07" />);

    await waitFor(() => {
      for (const warning of warnings) {
        expect(screen.getByText(warning)).toBeInTheDocument();
      }
    });
  });
});
