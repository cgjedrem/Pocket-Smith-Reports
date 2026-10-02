// KpiRoleSummary privacy masking — SC-001/SC-004.
// Hidden → every amount cell reads "****"; percentage cells byte-identical
// (FR-005). Component formats at render — toggle + rerender re-runs fmt.

import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { setAmountsHidden } from "@/lib/privacy-store";
import type { KpiRoleTotals, ReportResponse } from "@/types/report";

import { KpiRoleSummary } from "../KpiRoleSummary";

function roleTotals(over: Partial<KpiRoleTotals> = {}): KpiRoleTotals {
  return {
    income: 50000,
    real_spend: 30000,
    personal_spend: 6000,
    net_cash: 20000,
    net_savings: 14000,
    investment: 0,
    ...over,
  };
}

function makeReport(): ReportResponse {
  return {
    month: "2026-04",
    stale: false,
    txn_count: 0,
    normalized_transactions: [],
    categories: [],
    reconciliation: { source: 0, report: 0, difference: 0 },
    detailed_section_mapping: null,
    kpis: {
      partner_a: roleTotals(),
      partner_b: roleTotals({ income: 40000 }),
      total: roleTotals({ income: 90000 }),
    },
    root_totals: { paid: -30000, received: 50000, net: 20000, count: 0 },
    owner_totals: {
      partner_a: { paid: 0, received: 0, net: 0 },
      partner_b: { paid: 0, received: 0, net: 0 },
    },
    partner_panels: {
      partner_a: { label: "Alex", paid: 0, received: 0, net: 0, net_class: "pos" },
      partner_b: { label: "Sam", paid: 0, received: 0, net: 0, net_class: "pos" },
    },
    partner_labels: { partner_a: "Alex", partner_b: "Sam" },
    personal_share: 20.0,
    personal_share_partner_a: 12.5,
    personal_share_partner_b: 7.5,
  };
}

afterEach(() => {
  setAmountsHidden(false);
});

describe("KpiRoleSummary privacy masking", () => {
  it("masks every amount cell when hidden; percentages byte-identical", () => {
    const report = makeReport();
    const { container, rerender } = render(<KpiRoleSummary report={report} />);

    // Visible baseline — real figures present.
    expect(screen.getByText("50,000.00")).toBeInTheDocument();
    const pctBefore = screen.getByText("20.0%").textContent;

    setAmountsHidden(true);
    rerender(<KpiRoleSummary report={report} />);

    // No figure survives.
    expect(screen.queryByText("50,000.00")).toBeNull();
    expect(screen.queryByText(/40,000\.00/)).toBeNull();

    // Every amount cell (.metric-value cards except the % card, .val rows)
    // is exactly "****" or "**** (X.X%)" for the personal-spend row.
    const cells = [
      ...container.querySelectorAll(".metric-value"),
      ...container.querySelectorAll(".partner-box .val"),
    ];
    expect(cells.length).toBeGreaterThan(0);
    for (const cell of cells) {
      const text = cell.textContent ?? "";
      if (text.endsWith("%")) continue; // pure percentage card — FR-005
      expect(text).toMatch(/^\*\*\*\*( \([\d.]+%\))?$/);
    }

    // Percentage cell byte-identical to the visible render (FR-005).
    expect(screen.getByText("20.0%").textContent).toBe(pctBefore);
    // Partner labels untouched (panel heading + chart row label).
    expect(screen.getAllByText("Alex").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Sam").length).toBeGreaterThan(0);
  });

  it("restores exact values when toggled back", () => {
    const report = makeReport();
    const { rerender } = render(<KpiRoleSummary report={report} />);
    setAmountsHidden(true);
    rerender(<KpiRoleSummary report={report} />);
    setAmountsHidden(false);
    rerender(<KpiRoleSummary report={report} />);
    expect(screen.getByText("50,000.00")).toBeInTheDocument();
  });
});
