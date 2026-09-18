// Tests for report warnings display (US4 additive).
// Warnings should render as a banner when present, and be absent when empty or undefined.

import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock reports API *before* imports
vi.mock("@/api/reports", () => ({
  getReport: vi.fn(),
  generateReport: vi.fn(),
  getStatus: vi.fn(),
  exportPdf: vi.fn(),
}));

// Mock shared SCSS import
vi.mock("@/styles/report-shared.scss", () => ({}));

import { render, screen, waitFor } from "@testing-library/react";
import { ReportView } from "@/components/reports/ReportView";
import { ApiError } from "@/types/api";
import type { DetailedSections, ReportResponse } from "@/types/report";
import { getReport, getStatus } from "@/api/reports";

function makeDetailed(): DetailedSections {
  return {
    income: null,
    savings: null,
    home: null,
    common: null,
    personal_partner_a: null,
    personal_partner_b: null,
    trips: null,
    cc_payments: null,
    excluded: null,
    household_totals: null,
  };
}

function makeReportWithWarnings(warnings?: string[]): ReportResponse {
  return {
    month: "2026-07",
    stale: false,
    txn_count: 0,
    normalized_transactions: [],
    categories: [],
    reconciliation: { source: 0, report: 0, difference: 0 },
    detailed_section_mapping: null,
    kpis: null,
    root_totals: { paid: 0, received: 0, net: 0, count: 0 },
    owner_totals: {
      partner_a: { paid: 0, received: 0, net: 0 },
      partner_b: { paid: 0, received: 0, net: 0 },
    },
    partner_panels: {
      partner_a: { label: "Fixture A", paid: 0, received: 0, net: 0, net_class: "zero" },
      partner_b: { label: "Fixture B", paid: 0, received: 0, net: 0, net_class: "zero" },
    },
    partner_labels: { partner_a: "Fixture A", partner_b: "Fixture B" },
    detailed: makeDetailed(),
    balanced: true,
    ...(warnings !== undefined && { warnings }),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getStatus).mockRejectedValue(new ApiError("no generation", 404));
});

describe("ReportView — warnings banner (US4)", () => {
  it("renders warning banner when report has warnings", async () => {
    const report = makeReportWithWarnings([
      "Partner label mismatch detected",
      "Duplicate account mapping",
    ]);
    vi.mocked(getReport).mockResolvedValue(report);

    render(<ReportView month="2026-07" />);

    await waitFor(() => {
      expect(screen.getByText("Fidelity warnings")).toBeInTheDocument();
    });

    expect(screen.getByText("Partner label mismatch detected")).toBeInTheDocument();
    expect(screen.getByText("Duplicate account mapping")).toBeInTheDocument();
  });

  it("does not render banner when warnings array is empty", async () => {
    const report = makeReportWithWarnings([]);
    vi.mocked(getReport).mockResolvedValue(report);

    render(<ReportView month="2026-07" />);

    await waitFor(() => {
      expect(screen.getByText("Report — 2026-07")).toBeInTheDocument();
    });

    expect(screen.queryByText("Fidelity warnings")).not.toBeInTheDocument();
  });

  it("does not render banner when warnings field is absent (legacy report)", async () => {
    const report = makeReportWithWarnings();
    // Explicitly remove warnings to simulate legacy report
    delete report.warnings;
    vi.mocked(getReport).mockResolvedValue(report);

    render(<ReportView month="2026-07" />);

    await waitFor(() => {
      expect(screen.getByText("Report — 2026-07")).toBeInTheDocument();
    });

    expect(screen.queryByText("Fidelity warnings")).not.toBeInTheDocument();
  });

  it("renders single warning correctly", async () => {
    const report = makeReportWithWarnings(["Single warning message"]);
    vi.mocked(getReport).mockResolvedValue(report);

    render(<ReportView month="2026-07" />);

    await waitFor(() => {
      expect(screen.getByText("Single warning message")).toBeInTheDocument();
    });
  });

  it("renders multiple warnings as a list", async () => {
    const warnings = [
      "First warning",
      "Second warning",
      "Third warning",
    ];
    const report = makeReportWithWarnings(warnings);
    vi.mocked(getReport).mockResolvedValue(report);

    render(<ReportView month="2026-07" />);

    await waitFor(() => {
      for (const warning of warnings) {
        expect(screen.getByText(warning)).toBeInTheDocument();
      }
    });

    // Should have "Fidelity warnings" heading
    expect(screen.getByText("Fidelity warnings")).toBeInTheDocument();
  });
});
