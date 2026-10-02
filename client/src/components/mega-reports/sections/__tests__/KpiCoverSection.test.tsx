// KpiCoverSection — mega report KPI grid + charts + mega SplitSummaryCard.
// Covers the mega SplitSummaryCard coverage gap (none existed before this
// file): split_summary present -> 7-column table + totals row + the
// settlement sentence restored BELOW the totals row (2026-10-01 user
// request — totals row keeps the numeric who-owes-who signal, the
// sentence spells it out in words); split_summary null/absent -> card
// omitted entirely (never a fabricated empty card); balanced -> delta
// totals "0,00" + em-dash settlement sentence, no fabricated zero-amount
// transfer. Neutral fixture ids (LG-002): alex/sam, labels Alex/Sam.
//
// Uses fireEvent-style RTL (no @testing-library/user-event dependency in
// this repo — see MonthPicker.test.tsx / DetailedSections.test.tsx for the
// established pattern). No new deps: renders the real TrendBarLineChart /
// TrendLineChart (recharts) as-is.

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { MegaReportResponse, SplitSection } from "@/types/mega_report";

import { KpiCoverSection } from "../KpiCoverSection";

const PARTNER_LABELS = { partner_a: "Alex", partner_b: "Sam" };

// nb-NO renders negative numbers with U+2212 (MINUS SIGN), not ASCII "-".
const MINUS = String.fromCharCode(0x2212);

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
  // b-side additive columns — omit to simulate a stale stored v9 row
  // (undefined, same fallback as null per SplitCategoryRow docstring).
  actual_b?: number | null,
  fair_b?: number | null,
): SplitSection["rows"][number] {
  const delta = actual - fair;
  const hasB = actual_b !== undefined && fair_b !== undefined;
  const delta_b = hasB
    ? actual_b === null || fair_b === null
      ? null
      : actual_b - fair_b
    : undefined;
  return { category_id, label, section: "home", actual, fair, delta, actual_b, fair_b, delta_b };
}

describe("KpiCoverSection — mega SplitSummaryCard", () => {
  it("renders both partners' 7-column actual/fair/delta + totals row + the settlement sentence below it when split_summary is present", () => {
    const split_summary: SplitSection = {
      shares: { partner_a: 70, partner_b: 30 },
      sections: ["home"],
      // Settlement on the DTO — rendered again (restored 2026-10-01).
      settlement: { from_partner: "Sam", to_partner: "Alex", amount: 200 },
      rows: [
        splitRow("cat-1", "Groceries", 500, 400, 100, 200),
        // Second row so the totals are real sums, not a copy of one row.
        // All amounts < 1000 to avoid nb-NO's non-breaking-space
        // thousands separator.
        splitRow("cat-2", "Rent", 300, 200, 150, 100),
      ],
    };
    render(<KpiCoverSection report={mkReport({ split_summary })} />);

    expect(screen.getByText("Common economy split")).toBeInTheDocument();
    // Settlement sentence restored — original React "pays" wording with
    // formatNOK (NOT the backend twin's "owes"/"NOK." phrasing), as a
    // bolded <p> headline.
    const settlementP = screen.getByText("Sam pays Alex 200,00");
    expect(settlementP.tagName).toBe("P");
    expect(settlementP.className).toContain("font-semibold");
    expect(screen.getByText("Groceries")).toBeInTheDocument();
    // Rows are partner_a's (Alex's) perspective — real label, not "Actual".
    // Both partners get all 3 columns — parity with monthly
    // DetailedSections.tsx's 7-column split table.
    expect(screen.getByText("Alex actual")).toBeInTheDocument();
    expect(screen.getByText("Alex fair share")).toBeInTheDocument();
    expect(screen.getByText("Alex delta")).toBeInTheDocument();
    expect(screen.getByText("Sam actual")).toBeInTheDocument();
    expect(screen.getByText("Sam fair share")).toBeInTheDocument();
    expect(screen.getByText("Sam delta")).toBeInTheDocument();

    // Groceries row cells — a-side actual=500,00/fair=400,00/delta=100,00,
    // b-side (Sam) actual=100,00/fair=200,00/delta=-100,00. nb-NO renders
    // the minus sign as U+2212, not a plain hyphen.
    const row = screen.getByText("Groceries").closest("tr")!;
    expect(Array.from(row.querySelectorAll("td")).map((td) => td.textContent)).toEqual([
      "Groceries",
      "500,00",
      "400,00",
      "100,00",
      "100,00",
      "200,00",
      "\u2212100,00",
    ]);

    // Totals row — LAST tbody row, hand-computed column sums over both rows:
    //   actual   500 + 300 =  800,00
    //   fair     400 + 200 =  600,00
    //   delta    100 + 100 =  200,00
    //   actual_b 100 + 150 =  250,00
    //   fair_b   200 + 100 =  300,00
    //   delta_b  -100 + 50 = -50,00  (renders as U+2212 minus sign)
    const table = screen.getByText("Groceries").closest("table")!;
    const bodyRows = Array.from(table.querySelectorAll("tbody tr"));
    const totalsRow = bodyRows[bodyRows.length - 1];
    expect(Array.from(totalsRow.querySelectorAll("td")).map((td) => td.textContent)).toEqual([
      "Total",
      "800,00",
      "600,00",
      "200,00",
      "250,00",
      "300,00",
      MINUS + "50,00",
    ]);

    // ORDER — settlement sentence sits AFTER the totals row in DOM order
    // (totals row is the last tbody row; the <p> follows the table).
    expect(
      totalsRow.compareDocumentPosition(settlementP) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("renders em-dash for b-side cells when actual_b/fair_b/delta_b are null (stale stored CALCULATION_VERSION=9 row, predates b-side columns)", () => {
    const split_summary: SplitSection = {
      shares: { partner_a: 70, partner_b: 30 },
      sections: ["home"],
      rows: [splitRow("cat-1", "Groceries", 500, 400, null, null)],
      settlement: { from_partner: "Sam", to_partner: "Alex", amount: 100 },
    };
    render(<KpiCoverSection report={mkReport({ split_summary })} />);

    const row = screen.getByText("Groceries").closest("tr")!;
    expect(Array.from(row.querySelectorAll("td")).map((td) => td.textContent)).toEqual([
      "Groceries",
      "500,00",
      "400,00",
      "100,00",
      "—",
      "—",
      "—",
    ]);

    // Totals row: a-side sums render normally; EVERY b-side totals cell is
    // an em-dash (one null contributor poisons the column sum — never a
    // fabricated 0, mirroring the backend "never fabricate" convention).
    const table = screen.getByText("Groceries").closest("table")!;
    const bodyRows = Array.from(table.querySelectorAll("tbody tr"));
    const totalsRow = bodyRows[bodyRows.length - 1];
    expect(Array.from(totalsRow.querySelectorAll("td")).map((td) => td.textContent)).toEqual([
      "Total",
      "500,00",
      "400,00",
      "100,00",
      "—",
      "—",
      "—",
    ]);
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

  it("renders no transfer text when balanced (settlement null); delta totals are 0,00", () => {
    const split_summary: SplitSection = {
      shares: { partner_a: 50, partner_b: 50 },
      sections: ["home"],
      rows: [splitRow("cat-1", "Home", 400, 400, 400, 400)],
      settlement: null,
    };
    render(<KpiCoverSection report={mkReport({ split_summary })} />);

    expect(screen.getByText("Common economy split")).toBeInTheDocument();
    // No fabricated transfer — balanced (settlement null with real rows)
    // renders the ORIGINAL balanced wording: a bare em-dash sentence below
    // the totals row, never a 0,00 "pays" text. The numeric who-owes-who
    // signal stays in the delta totals (0,00 here).
    expect(screen.queryByText(/pays/)).not.toBeInTheDocument();
    const table = screen.getByText("Home").closest("table")!;
    const bodyRows = Array.from(table.querySelectorAll("tbody tr"));
    const totalsRow = bodyRows[bodyRows.length - 1];
    const card = screen.getByText("Common economy split").closest("div")!.parentElement!
      .parentElement as HTMLElement;
    const settlementP = within(card).getByText("—");
    expect(settlementP.tagName).toBe("P");
    expect(settlementP.className).toContain("font-semibold");
    // ORDER — sentence sits after the totals row in DOM order.
    expect(
      totalsRow.compareDocumentPosition(settlementP) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    // Single row Home 400/400 (b-side 400/400) — sums are the row values.
    expect(Array.from(totalsRow.querySelectorAll("td")).map((td) => td.textContent)).toEqual([
      "Total",
      "400,00",
      "400,00",
      "0,00", // snapped float dust, never a negative-zero artifact
      "400,00",
      "400,00",
      "0,00",
    ]);
  });

  it("totals row sums raw floats then formats once — NOT sum of rounded rows", () => {
    // Twin of backend test_totals_row_sums_raw_then_formats_once
    // (test_split_html.py). Two categories each A-paid 0.008 at 50/50:
    // each row's fair (0.004) and delta (0.004) format 0,00, but the raw
    // totals (0.008) format 0,01 — a round-then-sum implementation would
    // print 0,00. 0.008 > 0.005 so the totals snapDust never engages here.
    const split_summary: SplitSection = {
      shares: { partner_a: 50, partner_b: 50 },
      sections: ["home"],
      rows: [
        splitRow("cat-1", "Home thing", 0.008, 0.004, 0.0, 0.004),
        splitRow("cat-2", "Common thing", 0.008, 0.004, 0.0, 0.004),
      ],
      settlement: null,
    };
    render(<KpiCoverSection report={mkReport({ split_summary })} />);

    // Per-row cells round individually: fair 0,00, delta 0,00.
    const row = screen.getByText("Home thing").closest("tr")!;
    expect(Array.from(row.querySelectorAll("td")).map((td) => td.textContent)).toEqual([
      "Home thing",
      "0,01",
      "0,00",
      "0,00",
      "0,00",
      "0,00",
      MINUS + "0,00",
    ]);

    // Totals row — hand-computed raw sums, formatted once:
    //   actual   0.008 + 0.008 = 0.016 → 0,02
    //   fair     0.004 + 0.004 = 0.008 → 0,01   (round-then-sum → 0,00)
    //   delta    0.004 + 0.004 = 0.008 → 0,01   (round-then-sum → 0,00)
    //   actual_b 0.000 + 0.000 = 0.000 → 0,00
    //   fair_b   0.004 + 0.004 = 0.008 → 0,01
    //   delta_b -0.004 - 0.004 = -0.008 → U+2212 + 0,01 (round-then-sum → -0,00)
    const table = row.closest("table")!;
    const bodyRows = Array.from(table.querySelectorAll("tbody tr"));
    const totalsRow = bodyRows[bodyRows.length - 1];
    expect(Array.from(totalsRow.querySelectorAll("td")).map((td) => td.textContent)).toEqual([
      "Total",
      "0,02",
      "0,01",
      "0,01",
      "0,00",
      "0,01",
      MINUS + "0,01",
    ]);
  });

  it("renders the canonical empty-state copy (no table, no settlement, no totals) when split_summary has zero rows", () => {
    // Enabled config with zero categories selected is an allowed state —
    // the card shows the same canonical empty-state sentence as the
    // monthly React renderer (DetailedSections.tsx) and both HTML
    // renderers, never a blank card body, never a synthetic totals row
    // and never a "—" settlement sentence (settlement null + nothing to
    // settle; mirrors the backend twin's empty-rows early return).
    const split_summary: SplitSection = {
      shares: { partner_a: 50, partner_b: 50 },
      sections: [],
      rows: [],
      settlement: null,
    };
    render(<KpiCoverSection report={mkReport({ split_summary })} />);

    expect(screen.getByText("Common economy split")).toBeInTheDocument();
    expect(
      screen.getByText("No categories in the selected split sections this month."),
    ).toBeInTheDocument();
    // CardTitle (div) -> CardHeader (div) -> Card (div).
    const card = screen.getByText("Common economy split").closest("div")!.parentElement!
      .parentElement as HTMLElement;
    expect(card.querySelector("table")).toBeNull();
    expect(within(card).queryByText("Total")).not.toBeInTheDocument();
    expect(screen.queryByText(/pays/)).not.toBeInTheDocument();
    // Nothing to settle — settlement sentence is absent entirely
    // (the "—" balanced wording only applies when real rows exist).
    expect(within(card).queryByText("—")).not.toBeInTheDocument();
  });
});
