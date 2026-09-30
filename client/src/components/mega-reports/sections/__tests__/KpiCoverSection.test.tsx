// KpiCoverSection — mega report KPI grid + charts + mega SplitSummaryCard.
// Covers the mega SplitSummaryCard coverage gap (none existed before this
// file): split_summary present -> headline settlement text with real
// partner labels; split_summary null/absent -> card omitted entirely (never
// a fabricated empty card); balanced (settlement null) -> em-dash, no
// fabricated zero-amount transfer. Neutral fixture ids (LG-002): alex/sam,
// labels Alex/Sam.
//
// Uses fireEvent-style RTL (no @testing-library/user-event dependency in
// this repo — see MonthPicker.test.tsx / DetailedSections.test.tsx for the
// established pattern). No new deps: renders the real TrendBarLineChart /
// TrendLineChart (recharts) as-is.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { MegaReportResponse, SplitSection } from "@/types/mega_report";

import { KpiCoverSection } from "../KpiCoverSection";

const PARTNER_LABELS = { partner_a: "Alex", partner_b: "Sam" };

function mkReport(overrides: Partial<MegaReportResponse> = {}): MegaReportResponse {
  const months = ["2026-01", "2026-02"];
  return {
    start: "2026-01",
    end: "2026-02",
    stale: false,
    calculation_version: 2,
    txn_counts: {},
    months,
    partner_labels: PARTNER_LABELS,
    detail_agg: {
      months,
      cats: {},
      cc_paydowns: {},
      excluded_transactions: {},
      trips: [],
      series: {
        income: { partner_a: [1000, 1200], partner_b: [800, 900], total: [1800, 2100] },
        savings: {
          net_partner_a: [0, 0],
          net_partner_b: [0, 0],
          total: [0, 0],
          investment_net_partner_a: [0, 0],
          investment_net_partner_b: [0, 0],
          investment_net_total: [0, 0],
        },
        real_spend: { partner_a: [500, 600], partner_b: [400, 450], total: [900, 1050] },
        net_cash: { partner_a: [500, 600], partner_b: [400, 450], total: [900, 1050] },
      },
      cumulative: {
        income: { partner_a: 2200, partner_b: 1700, total: 3900 },
        savings: {
          net_partner_a: 0,
          net_partner_b: 0,
          total: 0,
          investment_net_partner_a: 0,
          investment_net_partner_b: 0,
          investment_net_total: 0,
        },
        real_spend: { partner_a: 1100, partner_b: 850, total: 1950 },
        net_cash: { partner_a: 1100, partner_b: 850, total: 1950 },
      },
    },
    // unavailable_reason set -> the salary-allocation table (with its own
    // "—" em-dash cells) never renders, so em-dash assertions below are
    // unambiguous (only the split card can produce one).
    salary_allocation: { income: 0, entries: [], unavailable_reason: "No salary data available" },
    recommendations: null,
    monthly_kpi_pages: [],
    split_summary: null,
    ...overrides,
  };
}

function splitRow(
  category_id: string,
  label: string,
  actual: number,
  fair: number,
): SplitSection["rows"][number] {
  return { category_id, label, actual, fair, delta: actual - fair };
}

describe("KpiCoverSection — mega SplitSummaryCard", () => {
  it("renders the headline settlement text with real partner labels when split_summary is present", () => {
    const split_summary: SplitSection = {
      shares: { partner_a: 70, partner_b: 30 },
      sections: ["home"],
      rows: [splitRow("cat-1", "Groceries", 500, 400)],
      settlement: { from_partner: "Sam", to_partner: "Alex", amount: 500 },
    };
    render(<KpiCoverSection report={mkReport({ split_summary })} />);

    expect(screen.getByText("Common economy split")).toBeInTheDocument();
    // amount < 1000 avoids nb-NO's non-breaking-space thousands separator.
    expect(screen.getByText("Sam pays Alex 500,00")).toBeInTheDocument();
    expect(screen.getByText("Groceries")).toBeInTheDocument();
    // Rows are partner_a's (Alex's) perspective — real label, not "Actual".
    expect(screen.getByText("Alex actual")).toBeInTheDocument();
    expect(screen.getByText("Alex fair")).toBeInTheDocument();
  });

  it("omits the card entirely when split_summary is null", () => {
    render(<KpiCoverSection report={mkReport({ split_summary: null })} />);
    expect(screen.queryByText("Common economy split")).not.toBeInTheDocument();
  });

  it("omits the card entirely when split_summary is absent (pre-field stored report)", () => {
    const report = mkReport();
    delete (report as Partial<MegaReportResponse>).split_summary;
    render(<KpiCoverSection report={report} />);
    expect(screen.queryByText("Common economy split")).not.toBeInTheDocument();
  });

  it("renders em-dash, never a fabricated transfer, when already balanced (settlement null)", () => {
    const split_summary: SplitSection = {
      shares: { partner_a: 50, partner_b: 50 },
      sections: ["home"],
      rows: [splitRow("cat-1", "Home", 500, 500)],
      settlement: null,
    };
    render(<KpiCoverSection report={mkReport({ split_summary })} />);

    expect(screen.getByText("Common economy split")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.queryByText(/pays/)).not.toBeInTheDocument();
  });
});
