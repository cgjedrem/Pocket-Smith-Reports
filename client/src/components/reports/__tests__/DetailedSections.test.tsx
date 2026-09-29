// NetSection rendering — parity with accounting_html.py `_legacy_net_section`.
// v8 DTO: paired reimbursements nested per category row (NetCategoryRow.
// paired_reimbursements), fully-paired categories keep a zero-net row, the
// separate captioned "Paired reimbursements" table + Home/Common notes are
// gone. Stored v7 reports only carry the section-level list — fallback
// renders it after the category rows, still inside the main table.

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type {
  DetailedSections as DetailedSectionsDto,
  NetCategoryRow,
  NetSection as NetSectionDto,
  PairedReimbursementRow,
  ReportResponse,
  SignClass,
} from "@/types/report";

import { DetailedSections } from "../DetailedSections";

const PARTNER_LABELS = { partner_a: "Alex", partner_b: "Sam" };

function signOf(v: number): SignClass {
  if (v === 0) return "zero";
  return v > 0 ? "pos" : "neg";
}

// One paired reimbursement: partner_a received `amount`, partner_b sent it.
function pair(category_title: string, amount: number): PairedReimbursementRow {
  return {
    category_title,
    partner_a: amount,
    partner_a_class: signOf(amount),
    partner_b: -amount,
    partner_b_class: signOf(-amount),
    total: 0,
    total_class: "zero",
  };
}

function netRow(
  category_title: string,
  partner_a_net: number,
  partner_b_net: number,
  paired_reimbursements?: PairedReimbursementRow[],
): NetCategoryRow {
  const total = partner_a_net + partner_b_net;
  return {
    category_title,
    partner_a_net,
    partner_a_net_class: signOf(partner_a_net),
    partner_b_net,
    partner_b_net_class: signOf(partner_b_net),
    total,
    total_class: signOf(total),
    g_share_partner_a: total === 0 ? null : (partner_a_net / total) * 100,
    g_share_partner_b: total === 0 ? null : (partner_b_net / total) * 100,
    paired_reimbursements,
  };
}

function netSection(
  rows: NetCategoryRow[],
  paired_reimbursements: PairedReimbursementRow[] = [],
): NetSectionDto {
  const totalA = rows.reduce((s, r) => s + r.partner_a_net, 0);
  const totalB = rows.reduce((s, r) => s + r.partner_b_net, 0);
  const total = totalA + totalB;
  return {
    rows,
    paired_reimbursements,
    total_partner_a: totalA,
    total_partner_a_class: signOf(totalA),
    total_partner_b: totalB,
    total_partner_b_class: signOf(totalB),
    total,
    total_class: signOf(total),
    share_partner_a: total === 0 ? null : (totalA / total) * 100,
    share_partner_b: total === 0 ? null : (totalB / total) * 100,
  };
}

function mkReport(partial: Partial<DetailedSectionsDto>): ReportResponse {
  return {
    month: "2026-04",
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
      partner_a: { label: PARTNER_LABELS.partner_a, paid: 0, received: 0, net: 0, net_class: "pos" },
      partner_b: { label: PARTNER_LABELS.partner_b, paid: 0, received: 0, net: 0, net_class: "pos" },
    },
    partner_labels: PARTNER_LABELS,
    detailed: {
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
      ...partial,
    },
  };
}

// tbody rows of the section's ONE net table: [className, [cell texts]].
function tbodyRows(sectionEl: HTMLElement) {
  const tables = Array.from(sectionEl.querySelectorAll("table"));
  expect(tables).toHaveLength(1); // no separate reimbursements table
  return Array.from(tables[0].querySelectorAll("tbody tr")).map((tr) => [
    tr.className,
    Array.from(tr.querySelectorAll("td")).map((td) => td.textContent ?? ""),
  ]);
}

function sectionOf(headingText: string): HTMLElement {
  const el = screen.getByRole("heading", { name: headingText }).closest("section");
  expect(el).not.toBeNull();
  return el as HTMLElement;
}

describe("NetSection — nested paired reimbursements", () => {
  it("renders a fully-paired category row with a reimb-row directly under it", () => {
    const home = netSection([
      netRow("Home", 0, 0, [pair("Home", 100)]),
    ]);
    render(<DetailedSections report={mkReport({ home })} />);

    const homeSection = sectionOf("3. Home");
    // Column headers come from report.partner_labels, not hardcoded names.
    expect(within(homeSection).getByText("Alex net")).toBeInTheDocument();
    expect(within(homeSection).getByText("Sam net")).toBeInTheDocument();

    const rows = tbodyRows(homeSection);
    expect(rows).toHaveLength(3);
    // Fully-paired category keeps its row: 0.00 totals, em-dash shares.
    expect(rows[0][0]).toBe("");
    expect(rows[0][1]).toEqual(["Home", "0.00", "0.00", "0.00", "— / —"]);
    // Reimb-row immediately after its category row, signed +/- amounts.
    expect(rows[1][0]).toBe("reimb-row");
    expect(rows[1][1]).toEqual([
      "Home (paired reimbursement)",
      "+100.00",
      "-100.00",
      "0.00",
      "", // no share cell on transparency rows
    ]);
    expect(rows[2][0]).toBe("legacy-total");
  });

  it("interleaves each Common category with its own reimb-rows", () => {
    const common = netSection([
      netRow("Groceries X", 0, 0, [pair("Groceries X", 600)]),
      netRow("Dining", 0, 0, [pair("Dining", 400)]),
    ]);
    render(<DetailedSections report={mkReport({ common })} />);

    const rows = tbodyRows(sectionOf("4. Common"));
    expect(rows).toHaveLength(5);
    expect(rows.map((r) => (r[1] as string[])[0])).toEqual([
      "Groceries X",
      "Groceries X (paired reimbursement)",
      "Dining",
      "Dining (paired reimbursement)",
      "Total",
    ]);
    expect(rows[1][0]).toBe("reimb-row");
    expect(rows[3][0]).toBe("reimb-row");
  });

  it("renders no captioned reimbursements table and no Common split note", () => {
    const home = netSection([netRow("Home", 0, 0, [pair("Home", 100)])]);
    const common = netSection([netRow("Dining", 0, 0, [pair("Dining", 400)])]);
    render(<DetailedSections report={mkReport({ home, common })} />);

    expect(
      screen.queryByText("Paired reimbursements (net 0, shown for transparency)"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/No 50\/50 split/)).not.toBeInTheDocument();
    expect(screen.queryByText(/reimbursement rows show both cash legs/)).not.toBeInTheDocument();
  });

  it("renders a partner_b-received pair with correct signs and classes", () => {
    // partner_b received 50, partner_a sent it: -50 neg / +50 pos.
    const pairB: PairedReimbursementRow = {
      category_title: "Home",
      partner_a: -50.0,
      partner_a_class: "neg",
      partner_b: 50.0,
      partner_b_class: "pos",
      total: 0,
      total_class: "zero",
    };
    const home = netSection([netRow("Home", 0, 0, [pairB])]);
    render(<DetailedSections report={mkReport({ home })} />);

    const homeSection = sectionOf("3. Home");
    const reimb = homeSection.querySelector("tr.reimb-row");
    expect(reimb).not.toBeNull();
    const cells = Array.from(reimb!.querySelectorAll("td"));
    expect(cells[0].textContent).toBe("Home (paired reimbursement)");
    expect(cells[1].textContent).toBe("-50.00");
    expect(cells[1].className).toContain("neg");
    expect(cells[2].textContent).toBe("+50.00");
    expect(cells[2].className).toContain("pos");
  });

  it("falls back to section-level pairs for v7 reports without nested lists", () => {
    const home = netSection(
      [netRow("Rent", -500, 500), netRow("Utilities", -100, 100)],
      [pair("Rent", 100)], // section-level flattened list, rows lack nested lists
    );
    render(<DetailedSections report={mkReport({ home })} />);

    const rows = tbodyRows(sectionOf("3. Home"));
    // Categories first, then the section-level pair, then the total — all in
    // the single main table (tbodyRows refuses a second table).
    expect(rows.map((r) => (r[1] as string[])[0])).toEqual([
      "Rent",
      "Utilities",
      "Rent (paired reimbursement)",
      "Total",
    ]);
    expect(rows[2][0]).toBe("reimb-row");
    expect(rows[2][1]).toContain("+100.00");
  });
});
