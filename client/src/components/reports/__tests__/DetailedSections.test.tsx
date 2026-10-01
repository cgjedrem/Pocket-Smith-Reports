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
  SplitSection as SplitSectionDto,
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

// 10. Common-economy split (calculation_version 9, additive). split is
// optional/nullable — feature off, no config, or a stored v7/v8 payload
// that predates the field entirely (test that as `undefined`, not just
// `null`, since older reports literally lack the key).
describe("CommonEconomySplitSection", () => {
  // a-side only — b-side fields omitted (undefined), simulating a stale
  // stored v9 row persisted before the b-side columns existed.
  function splitRow(
    category_id: string,
    label: string,
    section: string,
    actual: number,
    fair: number,
  ): SplitSectionDto["rows"][number] {
    return { category_id, label, section, actual, fair, delta: actual - fair };
  }

  // Full 7-field row — both a-side and b-side (b-side is the exact
  // complement per compute_split()'s docstring: actual_b = total - actual).
  function splitRowFull(
    category_id: string,
    label: string,
    section: string,
    actual: number,
    fair: number,
    actual_b: number,
    fair_b: number,
  ): SplitSectionDto["rows"][number] {
    return {
      category_id,
      label,
      section,
      actual,
      fair,
      delta: actual - fair,
      actual_b,
      fair_b,
      delta_b: actual_b - fair_b,
    };
  }

  it("renders no block at all when split is null", () => {
    render(<DetailedSections report={mkReport({ split: null })} />);
    expect(screen.queryByRole("heading", { name: /Common Economy Split/i })).not.toBeInTheDocument();
    expect(screen.queryByText("—")).not.toBeInTheDocument();
  });

  it("renders no block at all when split is undefined (pre-field stored report)", () => {
    // mkReport spreads `...partial` over a base with no `split` key —
    // omitting it entirely from `partial` reproduces a v7/v8 payload.
    render(<DetailedSections report={mkReport({})} />);
    expect(screen.queryByRole("heading", { name: /Common Economy Split/i })).not.toBeInTheDocument();
  });

  it("renders the per-category actual/fair/delta table (7 columns, both partners), grouped under a per-section subheading", () => {
    const split: SplitSectionDto = {
      shares: { partner_a: 60, partner_b: 40 },
      sections: ["home", "common", "trips"],
      rows: [
        splitRowFull("cat-1", "Groceries", "common", 600, 500, 150, 100),
        splitRowFull("cat-2", "Rent", "home", 1000, 900, 300, 250),
      ],
      settlement: null,
    };
    render(<DetailedSections report={mkReport({ split })} />);

    const section = sectionOf("10. Common Economy Split");
    // Column headers carry BOTH partners' real display labels (Alex/Sam
    // here), not generic "Actual"/"Fair share"/"Delta" — parity with the
    // HTML/PDF twin (accounting_html.py::_legacy_split_section uses
    // partner_labels["partner_a"] / partner_labels["partner_b"]).
    const headers = Array.from(section.querySelectorAll("thead th")).map((th) => th.textContent);
    expect(headers).toEqual([
      "Category",
      "Alex actual",
      "Alex fair share",
      "Alex delta",
      "Sam actual",
      "Sam fair share",
      "Sam delta",
    ]);

    // Group order follows section.sections ("home" before "common") even
    // though the row for "home" (Rent) comes second in `rows` — subheadings
    // use the same raw section-key label the category-mapping editor's
    // detailedSectionLabel() falls back to for non-personal sections.
    const headings = Array.from(section.querySelectorAll("tr.split-section-heading")).map(
      (tr) => tr.textContent,
    );
    expect(headings).toEqual(["home", "common"]);

    // Rent (home) row cells — a-side actual=1000.00/fair=900.00/delta=+100.00,
    // b-side (Sam) actual=300.00/fair=250.00/delta=+50.00.
    const rentRow = within(section).getByText("Rent").closest("tr")!;
    expect(Array.from(rentRow.querySelectorAll("td")).map((td) => td.textContent)).toEqual([
      "Rent",
      "1,000.00",
      "900.00",
      "+100.00",
      "300.00",
      "250.00",
      "+50.00",
    ]);
    // Groceries (common) row cells — a-side actual=600.00/fair=500.00/delta=+100.00,
    // b-side (Sam) actual=150.00/fair=100.00/delta=+50.00.
    const groceriesRow = within(section).getByText("Groceries").closest("tr")!;
    expect(Array.from(groceriesRow.querySelectorAll("td")).map((td) => td.textContent)).toEqual([
      "Groceries",
      "600.00",
      "500.00",
      "+100.00",
      "150.00",
      "100.00",
      "+50.00",
    ]);

    // Grand-totals row — LAST tbody row, ONE row across both section
    // groups (not per group). Hand-computed column sums:
    //   actual   600 + 1000 = 1,600.00
    //   fair     500 +  900 = 1,400.00
    //   delta    100 +  100 = +200.00
    //   actual_b 150 +  300 =   450.00
    //   fair_b   100 +  250 =   350.00
    //   delta_b   50 +   50 = +100.00
    const bodyRows = Array.from(section.querySelectorAll("tbody tr"));
    const totalsRow = bodyRows[bodyRows.length - 1];
    expect(totalsRow.className).toBe("legacy-total");
    expect(Array.from(totalsRow.querySelectorAll("td")).map((td) => td.textContent)).toEqual([
      "Total",
      "1,600.00",
      "1,400.00",
      "+200.00",
      "450.00",
      "350.00",
      "+100.00",
    ]);
  });

  it("renders em-dash for b-side cells when actual_b/fair_b/delta_b are null (stale stored CALCULATION_VERSION=9 row, predates b-side columns)", () => {
    const split: SplitSectionDto = {
      shares: { partner_a: 60, partner_b: 40 },
      sections: ["home"],
      rows: [
        {
          category_id: "cat-1",
          label: "Rent",
          section: "home",
          actual: 1000,
          fair: 900,
          delta: 100,
          actual_b: null,
          fair_b: null,
          delta_b: null,
        },
      ],
      settlement: null,
    };
    render(<DetailedSections report={mkReport({ split })} />);

    const section = sectionOf("10. Common Economy Split");
    const rentRow = within(section).getByText("Rent").closest("tr")!;
    expect(Array.from(rentRow.querySelectorAll("td")).map((td) => td.textContent)).toEqual([
      "Rent",
      "1,000.00",
      "900.00",
      "+100.00",
      "—",
      "—",
      "—",
    ]);

    // Totals row: a-side sums render normally; EVERY b-side totals cell is
    // an em-dash (one null contributor poisons the column sum — never a
    // fabricated 0, mirroring the backend "never fabricate" convention).
    const bodyRows = Array.from(section.querySelectorAll("tbody tr"));
    const totalsRow = bodyRows[bodyRows.length - 1];
    expect(totalsRow.className).toBe("legacy-total");
    expect(Array.from(totalsRow.querySelectorAll("td")).map((td) => td.textContent)).toEqual([
      "Total",
      "1,000.00",
      "900.00",
      "+100.00",
      "—",
      "—",
      "—",
    ]);
  });

  it("groups a row with section: null under the fallback 'unknown' heading without crashing (stale CALCULATION_VERSION=9 stored row, predates the derived section key)", () => {
    const split: SplitSectionDto = {
      shares: { partner_a: 60, partner_b: 40 },
      sections: ["home"],
      rows: [
        splitRowFull("cat-1", "Rent", "home", 1000, 900, 300, 250),
        {
          category_id: "cat-2",
          label: "Old Category",
          section: null,
          actual: 50,
          fair: 40,
          delta: 10,
        },
      ],
      settlement: null,
    };
    render(<DetailedSections report={mkReport({ split })} />);

    const section = sectionOf("10. Common Economy Split");
    // Canonical "home" first; stray "unknown" appended after in first-seen
    // order. detailedSectionLabel returns the raw key verbatim for
    // non-personal sections, so the fallback heading renders literally
    // "unknown" (ugly but acceptable — v9 stored reports are regenerable).
    const headings = Array.from(section.querySelectorAll("tr.split-section-heading")).map(
      (tr) => tr.textContent,
    );
    expect(headings).toEqual(["home", "unknown"]);

    // Null-section row sits directly under the "unknown" heading, and its
    // omitted b-side fields (v9 rows carry none) render as em-dashes.
    const unknownHeading = within(section).getByText("unknown").closest("tr")!;
    const staleRow = unknownHeading.nextElementSibling as HTMLTableRowElement;
    expect(Array.from(staleRow.querySelectorAll("td")).map((td) => td.textContent)).toEqual([
      "Old Category",
      "50.00",
      "40.00",
      "+10.00",
      "—",
      "—",
      "—",
    ]);
  });

  it("labels a personal_partner_a/b group 'Personal — {label}', mirroring detailedSectionLabel", () => {
    const split: SplitSectionDto = {
      shares: { partner_a: 50, partner_b: 50 },
      sections: ["personal_partner_a", "personal_partner_b"],
      rows: [
        splitRow("cat-1", "Hobby", "personal_partner_a", 200, 200),
        splitRow("cat-2", "Gym", "personal_partner_b", 100, 100),
      ],
      settlement: null,
    };
    render(<DetailedSections report={mkReport({ split })} />);
    const section = sectionOf("10. Common Economy Split");
    const headings = Array.from(section.querySelectorAll("tr.split-section-heading")).map(
      (tr) => tr.textContent,
    );
    expect(headings).toEqual(["Personal — Alex", "Personal — Sam"]);
  });

  it("renders no transfer text when balanced (settlement null); delta totals snap to 0.00", () => {
    const split: SplitSectionDto = {
      shares: { partner_a: 50, partner_b: 50 },
      sections: ["home"],
      rows: [splitRowFull("cat-1", "Home", "home", 500, 500, 500, 500)],
      settlement: null,
    };
    render(<DetailedSections report={mkReport({ split })} />);
    const section = sectionOf("10. Common Economy Split");
    // No fabricated transfer — balanced (settlement null with real rows)
    // renders the ORIGINAL balanced wording: a bare em-dash sentence below
    // the totals row, never a 0.00 "pays" text.
    expect(within(section).queryByText(/pays/)).not.toBeInTheDocument();
    const bodyRows = Array.from(section.querySelectorAll("tbody tr"));
    const totalsRow = bodyRows[bodyRows.length - 1];
    expect(totalsRow.className).toBe("legacy-total");
    const settlementP = section.querySelector("p.note.split-settlement");
    expect(settlementP).not.toBeNull();
    expect(settlementP!.textContent).toBe("—");
    // ORDER — sentence sits after the totals row in DOM order.
    expect(
      totalsRow.compareDocumentPosition(settlementP!) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    // Single row Home 500/500 (b-side 500/500) — sums are the row values.
    expect(Array.from(totalsRow.querySelectorAll("td")).map((td) => td.textContent)).toEqual([
      "Total",
      "500.00",
      "500.00",
      "0.00", // float dust snapped; no "-0.00", no spurious "+"
      "500.00",
      "500.00",
      "0.00",
    ]);
  });

  it("totals row sums raw floats then formats once — NOT sum of rounded rows", () => {
    // Twin of backend test_totals_row_sums_raw_then_formats_once
    // (test_split_html.py). Two categories each A-paid 0.008 at 50/50:
    // each row's fair (0.004) and delta (0.004) format 0.00, but the raw
    // totals (0.008) format 0.01 — a round-then-sum implementation would
    // print 0.00. 0.008 > 0.005 so the totals snapDust never engages here.
    const split: SplitSectionDto = {
      shares: { partner_a: 50, partner_b: 50 },
      sections: ["home", "common"],
      rows: [
        splitRowFull("cat-1", "Home thing", "home", 0.008, 0.004, 0.0, 0.004),
        splitRowFull("cat-2", "Common thing", "common", 0.008, 0.004, 0.0, 0.004),
      ],
      settlement: null,
    };
    render(<DetailedSections report={mkReport({ split })} />);

    const section = sectionOf("10. Common Economy Split");
    // Per-row cells round individually: fair 0.00, delta +0.00.
    const homeRow = within(section).getByText("Home thing").closest("tr")!;
    expect(Array.from(homeRow.querySelectorAll("td")).map((td) => td.textContent)).toEqual([
      "Home thing",
      "0.01",
      "0.00",
      "+0.00",
      "0.00",
      "0.00",
      "-0.00",
    ]);

    // Totals row — hand-computed raw sums, formatted once:
    //   actual   0.008 + 0.008 = 0.016 → 0.02
    //   fair     0.004 + 0.004 = 0.008 → 0.01   (round-then-sum → 0.00)
    //   delta    0.004 + 0.004 = 0.008 → +0.01  (round-then-sum → +0.00)
    //   actual_b 0.000 + 0.000 = 0.000 → 0.00
    //   fair_b   0.004 + 0.004 = 0.008 → 0.01
    //   delta_b -0.004 - 0.004 = -0.008 → -0.01 (round-then-sum → -0.00)
    const bodyRows = Array.from(section.querySelectorAll("tbody tr"));
    const totalsRow = bodyRows[bodyRows.length - 1];
    expect(totalsRow.className).toBe("legacy-total");
    expect(Array.from(totalsRow.querySelectorAll("td")).map((td) => td.textContent)).toEqual([
      "Total",
      "0.02",
      "0.01",
      "+0.01",
      "0.00",
      "0.01",
      "-0.01",
    ]);
  });

  it("renders the settlement sentence BELOW the totals row when settlement is present (original 'pays' wording)", () => {
    // Restored 2026-10-01 (user request): settlement sentence re-added
    // after the table — totals row kept AND the plain-language summary.
    const split: SplitSectionDto = {
      shares: { partner_a: 60, partner_b: 40 },
      sections: ["home", "common", "trips"],
      rows: [splitRow("cat-1", "Groceries", "common", 1234, 0)],
      settlement: { from_partner: "Sam", to_partner: "Alex", amount: 1234 },
    };
    render(<DetailedSections report={mkReport({ split })} />);
    const section = sectionOf("10. Common Economy Split");
    // Original React wording — "{from} pays {to} {fmt(amount)}" — NOT the
    // backend twin's "Settlement: X owes Y N." phrasing.
    const settlementP = section.querySelector("p.note.split-settlement");
    expect(settlementP).not.toBeNull();
    expect(settlementP!.textContent).toBe("Sam pays Alex 1,234.00");

    // ORDER: the sentence comes AFTER the totals row in DOM order
    // (totals row is the last tbody row; the <p> follows </table>).
    const bodyRows = Array.from(section.querySelectorAll("tbody tr"));
    const totalsRow = bodyRows[bodyRows.length - 1];
    expect(totalsRow.className).toBe("legacy-total");
    expect(
      totalsRow.compareDocumentPosition(settlementP!) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("renders NO settlement sentence when there is nothing to settle (zero rows, settlement null)", () => {
    // Enabled config with zero categories selected is an allowed state —
    // the empty-state row renders, but no "—" settlement sentence and no
    // fabricated 0.00 transfer (mirrors the backend twin's empty-rows
    // early return: empty/null → nothing).
    const split: SplitSectionDto = {
      shares: { partner_a: 50, partner_b: 50 },
      sections: [],
      rows: [],
      settlement: null,
    };
    render(<DetailedSections report={mkReport({ split })} />);
    const section = sectionOf("10. Common Economy Split");
    expect(
      within(section).getByText("No categories in the selected split sections this month."),
    ).toBeInTheDocument();
    expect(section.querySelector("p.split-settlement")).toBeNull();
    expect(within(section).queryByText(/pays/)).not.toBeInTheDocument();
  });
});
