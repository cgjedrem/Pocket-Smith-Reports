// MonthlyReportsPage tests — F15 / AC23-AC28.
// Mock reports API. Test month list, select, 404, generate flow, stale.

import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MonthlyReportsPage } from "@/pages/MonthlyReportsPage";
import { ApiError } from "@/types/api";
import type { GenerateStatus, MonthList, ReportResponse } from "@/types/report";

// Mock reports API.
vi.mock("@/api/reports", () => ({
  getMonths: vi.fn(),
  getReport: vi.fn(),
  generateReport: vi.fn(),
  getStatus: vi.fn(),
  exportPdf: vi.fn(),
}));

import {
  getMonths,
  getReport,
  generateReport,
  getStatus,
} from "@/api/reports";

// Helpers — build report objects.
function makeMonths(months: string[] = ["2026-07", "2026-06"]): MonthList {
  return { months };
}

function makeReport(over: Partial<ReportResponse> = {}): ReportResponse {
  return {
    month: "2026-07",
    stale: false,
    txn_count: 10,
    normalized_transactions: [],
    categories: [],
    reconciliation: { source: 1000, report: 1000, difference: 0 },
    detailed_section_mapping: null,
    kpis: {
      total: { income: 500, real_spend: 300, net_cash: 200, net_savings: 100 },
      partner_a: { income: 300, real_spend: 150, personal_spend: 50, net_cash: 150, net_savings: 50 },
      partner_b: { income: 200, real_spend: 150, personal_spend: 50, net_cash: 50, net_savings: 50 },
    },
    root_totals: { paid: 500, received: 500, net: 0, count: 10 },
    owner_totals: {
      partner_a: { paid: 250, received: 250, net: 0 },
      partner_b: { paid: 250, received: 250, net: 0 },
    },
    partner_panels: {
      partner_a: {
        label: "Fixture A",
        paid: 250,
        received: 250,
        net: 0,
        net_class: "pos" as const,
      },
      partner_b: {
        label: "Fixture B",
        paid: 250,
        received: 250,
        net: 0,
        net_class: "pos" as const,
      },
    },
    category_highlights: [],
    subcategory_overviews: [],
    transaction_drilldowns: [],
    partner_labels: { partner_a: "Fixture A", partner_b: "Fixture B" },
    ...over,
  };
}

function makeStatus(over: Partial<GenerateStatus> = {}): GenerateStatus {
  return {
    status: "success",
    errors: [],
    started_at: "2026-07-28T12:00:00Z",
    completed_at: "2026-07-28T12:00:01Z",
    ...over,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  // Default: status 404 (never generated), report 404.
  vi.mocked(getStatus).mockRejectedValue(new ApiError("no generation", 404));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("MonthlyReportsPage — AC23 month list", () => {
  it("renders title + month selector with selected month", async () => {
    vi.mocked(getMonths).mockResolvedValue(makeMonths());
    vi.mocked(getReport).mockResolvedValue(makeReport());

    render(<MonthlyReportsPage />);
    expect(screen.getByRole("heading", { name: "Monthly Reports" })).toBeInTheDocument();
    const toolbar = await screen.findByRole("toolbar", { name: "Report controls" });
    expect(toolbar).toHaveTextContent("2026-07");
    expect(toolbar).toHaveTextContent("Report — 2026-07");
    expect(toolbar).toHaveTextContent("Export PDF");
    expect(toolbar).toHaveTextContent("Regenerate");
  });

  it("empty months → empty state 'Run sync first'", async () => {
    vi.mocked(getMonths).mockResolvedValue({ months: [] });
    render(<MonthlyReportsPage />);
    await waitFor(() =>
      expect(screen.getByText(/Run sync first/i)).toBeInTheDocument()
    );
  });

  it("network error → error alert", async () => {
    vi.mocked(getMonths).mockRejectedValue(new ApiError("Cannot reach server", 500));
    render(<MonthlyReportsPage />);
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Cannot reach server")
    );
  });
});

describe("MonthlyReportsPage — AC24 select + render", () => {
  it("auto-selects newest month → fetches report", async () => {
    vi.mocked(getMonths).mockResolvedValue(makeMonths());
    vi.mocked(getReport).mockResolvedValue(makeReport());

    render(<MonthlyReportsPage />);
    await waitFor(() => expect(getReport).toHaveBeenCalledWith("2026-07"));
    // Overview header renders.
    await waitFor(() =>
      expect(screen.getByText("Monthly Report")).toBeInTheDocument()
    );
  });

  it("partner labels shown — Fixture A/Fixture B", async () => {
    vi.mocked(getMonths).mockResolvedValue(makeMonths());
    vi.mocked(getReport).mockResolvedValue(makeReport());

    render(<MonthlyReportsPage />);
    await waitFor(() => expect(screen.getAllByText("Fixture A").length).toBeGreaterThan(0));
    expect(screen.getAllByText("Fixture B").length).toBeGreaterThan(0);
  });
});

describe("MonthlyReportsPage — AC25 404 → GenerateButton", () => {
  it("404 report → shows Generate button", async () => {
    vi.mocked(getMonths).mockResolvedValue(makeMonths());
    vi.mocked(getReport).mockRejectedValue(new ApiError("no report generated yet", 404));

    render(<MonthlyReportsPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Generate report/i })).toBeInTheDocument()
    );
  });
});

describe("MonthlyReportsPage — AC26 generate flow", () => {
  it("click Generate → 202 → poll → success → report renders", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(getMonths).mockResolvedValue(makeMonths());
    // First getReport (mount) → 404. Subsequent → success.
    vi.mocked(getReport)
      .mockRejectedValueOnce(new ApiError("no report", 404))
      .mockResolvedValue(makeReport());
    vi.mocked(generateReport).mockResolvedValue(makeStatus({ status: "generating" }));
    // Mount getStatus → 404 (never generated). Poll: generating then success.
    vi.mocked(getStatus)
      .mockRejectedValueOnce(new ApiError("no generation", 404))
      .mockResolvedValueOnce(makeStatus({ status: "generating" }))
      .mockResolvedValueOnce(makeStatus({ status: "success" }));

    render(<MonthlyReportsPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Generate report/i })).toBeInTheDocument()
    );

    // Click generate.
    await act(async () => {
      screen.getByRole("button", { name: /Generate report/i }).click();
    });
    await waitFor(() => expect(generateReport).toHaveBeenCalledWith("2026-07"));

    // Advance past 2s poll — first poll returns generating.
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });
    // Second poll — success → fetch report.
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });
    await waitFor(() =>
      expect(screen.getByText("Monthly Report")).toBeInTheDocument()
    );
  });
});

describe("MonthlyReportsPage — AC27 stale badge", () => {
  it("stale=true → StaleBadge visible", async () => {
    vi.mocked(getMonths).mockResolvedValue(makeMonths());
    vi.mocked(getReport).mockResolvedValue(makeReport({ stale: true }));

    render(<MonthlyReportsPage />);
    await waitFor(() => expect(screen.getByText("Stale")).toBeInTheDocument());
  });
});