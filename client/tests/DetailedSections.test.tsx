// DetailedSections tests — PR5 smoke-fix regression coverage.
// FIX 1: personal Subtotal renders the section's own subtotal (fallback
// personal_total + signOf for pre-PR5 stored reports).
// FIX 2: per-category drill-downs restored under every section, reading
// report.normalized_transactions routed by detailed_section_mapping.

import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DetailedSections } from "@/components/reports/DetailedSections";
import type { DetailedSections as DetailedSectionsDto, ReportResponse } from "@/types/report";

// One fixture txn per detailed section (+ one unmapped leaf for the "common"
// fallback). Leaf ids match detailed_section_mapping.category_sections keys.
function makeTxns(): Record<string, unknown>[] {
  const t = (
    id: number,
    leafId: string,
    leafTitle: string,
    amount: number,
    payee: string,
    owner: string,
    date: string,
    root?: { id: string; title: string }
  ): Record<string, unknown> => ({
    id,
    date,
    amount,
    payee,
    note: "",
    account_id: "acc1",
    account_name: "Checking",
    owner,
    category_path: root
      ? [root, { id: leafId, title: leafTitle }]
      : [{ id: leafId, title: leafTitle }],
    is_transfer: false,
  });
  return [
    t(1, "sal1", "Salary", 55000, "Employer AS", "partner_a", "2026-08-01"),
    t(2, "sal2", "Refund", 1200, "Refund Central", "partner_b", "2026-08-05"),
    t(3, "home1", "Rent", -16000, "Landlord", "partner_a", "2026-08-01"),
    t(4, "com1", "Supermarket", -450.5, "Rema 1000", "partner_b", "2026-08-03", {
      id: "rootG",
      title: "Groceries",
    }),
    // Unmapped leaf -> groups under "common" (old fallback, verbatim).
    t(5, "unm1", "Kiosk", -120, "Kiosk 7", "partner_a", "2026-08-04"),
    t(6, "pc1", "Games", -700, "Steam games", "partner_a", "2026-08-11"),
    t(7, "pc1", "Games", -350, "Board Game Store", "partner_a", "2026-08-02"),
    t(8, "pr1", "Clothes", -900, "H&M", "partner_b", "2026-08-07"),
    t(9, "trip1", "Flights", -3200, "SAS Airlines", "partner_a", "2026-08-15"),
    t(10, "cc1", "CC Payment", -1500, "DNB Mastercard", "partner_b", "2026-08-20"),
    t(11, "exc1", "Gifts", -300, "Gift Shop", "partner_a", "2026-08-12"),
    t(12, "sav1", "Fond", -2000, "Kron Fond", "partner_b", "2026-08-10"),
  ];
}

const MAPPING = {
  category_sections: {
    sal1: "income_salary",
    sal2: "income_third_party",
    home1: "home",
    com1: "common",
    // unm1 intentionally unmapped — falls back to "common".
    pc1: "personal_partner_a",
    pr1: "personal_partner_b",
    trip1: "trips",
    cc1: "cc_payments",
    exc1: "excluded",
    sav1: "savings",
  },
  account_roles: {},
};

// Full detailed DTO — every section populated. Personal sections carry the
// smoke-test values: Fixture A 6,043.97 (7.5%), Fixture B 9,659.78 (12.0%), with
// shared personal_total 15,703.75 that must NOT render as either subtotal.
// Sign convention is paid-negative, so the fixture uses negatives.
function makeDetailed(): DetailedSectionsDto {
  return {
    income: {
      salary: {
        partner_a: 55000,
        partner_a_class: "pos",
        partner_b: 0,
        partner_b_class: "zero",
        total: 55000,
        total_class: "pos",
        row_pct_partner_a: 100.0,
        row_pct_partner_b: 0.0,
        household_pct: 100.0,
      },
      third_party: {
        partner_a: 0,
        partner_a_class: "zero",
        partner_b: 1200,
        partner_b_class: "pos",
        total: 1200,
        total_class: "pos",
        row_pct_partner_a: 0.0,
        row_pct_partner_b: 100.0,
        household_pct: 2.1,
      },
      total_partner_a: 55000,
      total_partner_a_class: "pos",
      total_partner_b: 1200,
      total_partner_b_class: "pos",
      total_income: 56200,
      total_income_class: "pos",
    },
    savings: null,
    home: {
      rows: [
        {
          category_title: "Rent",
          partner_a_net: -16000,
          partner_a_net_class: "neg",
          partner_b_net: 0,
          partner_b_net_class: "zero",
          total: -16000,
          total_class: "neg",
          g_share_partner_a: 100.0,
          g_share_partner_b: 0.0,
        },
      ],
      paired_reimbursements: [],
      total_partner_a: -16000,
      total_partner_a_class: "neg",
      total_partner_b: 0,
      total_partner_b_class: "zero",
      total: -16000,
      total_class: "neg",
      share_partner_a: 100.0,
      share_partner_b: 0.0,
    },
    common: {
      rows: [
        {
          category_title: "Groceries / Supermarket",
          partner_a_net: 0,
          partner_a_net_class: "zero",
          partner_b_net: -450.5,
          partner_b_net_class: "neg",
          total: -450.5,
          total_class: "neg",
          g_share_partner_a: 0.0,
          g_share_partner_b: 100.0,
        },
      ],
      paired_reimbursements: [],
      total_partner_a: 0,
      total_partner_a_class: "zero",
      total_partner_b: -450.5,
      total_partner_b_class: "neg",
      total: -450.5,
      total_class: "neg",
      share_partner_a: 0.0,
      share_partner_b: 100.0,
    },
    personal_partner_a: {
      rows: [
        {
          category_title: "Games",
          paid_partner_a: -6043.97,
          paid_partner_a_class: "neg",
          paid_partner_b: 0,
          paid_partner_b_class: "zero",
          total: -6043.97,
          total_class: "neg",
          pct_personal: 100.0,
          pct_household: 7.5,
        },
      ],
      subtotal: -6043.97,
      subtotal_class: "neg",
      personal_total: -15703.75,
      personal_total_class: "neg",
      household_total: -80400,
      household_total_class: "neg",
      pct_personal: 100.0,
      pct_household: 7.5,
    },
    personal_partner_b: {
      rows: [
        {
          category_title: "Clothes",
          paid_partner_a: 0,
          paid_partner_a_class: "zero",
          paid_partner_b: -9659.78,
          paid_partner_b_class: "neg",
          total: -9659.78,
          total_class: "neg",
          pct_personal: 100.0,
          pct_household: 12.0,
        },
      ],
      subtotal: -9659.78,
      subtotal_class: "neg",
      personal_total: -15703.75,
      personal_total_class: "neg",
      household_total: -80400,
      household_total_class: "neg",
      pct_personal: 100.0,
      pct_household: 12.0,
    },
    trips: {
      rows: [
        {
          category_title: "Flights",
          partner_a_net: -3200,
          partner_a_net_class: "neg",
          partner_b_net: 0,
          partner_b_net_class: "zero",
          total: -3200,
          total_class: "neg",
          g_share_partner_a: 100.0,
          g_share_partner_b: 0.0,
        },
      ],
      paired_reimbursements: [],
      total_partner_a: -3200,
      total_partner_a_class: "neg",
      total_partner_b: 0,
      total_partner_b_class: "zero",
      total: -3200,
      total_class: "neg",
      share_partner_a: 100.0,
      share_partner_b: 0.0,
    },
    cc_payments: {
      partner_a_paid: 0,
      partner_a_paid_class: "zero",
      partner_b_paid: -1500,
      partner_b_paid_class: "neg",
      household_paid: -1500,
      household_paid_class: "neg",
    },
    excluded: {
      rows: [
        {
          category_title: "Gifts",
          paid_partner_a: -300,
          paid_partner_a_class: "neg",
          paid_partner_b: 0,
          paid_partner_b_class: "zero",
          total: -300,
          total_class: "neg",
        },
      ],
      total: -300,
      total_class: "neg",
    },
    household_totals: null,
  };
}

function makeReport(overrides: Partial<ReportResponse> = {}): ReportResponse {
  return {
    month: "2026-08",
    stale: false,
    txn_count: 11,
    normalized_transactions: makeTxns(),
    categories: [],
    reconciliation: { source: 0, report: 0, difference: 0 },
    detailed_section_mapping: MAPPING,
    kpis: null,
    savings_summary: null,
    root_totals: { paid: 27220.25, received: 56200, net: 28979.75, count: 11 },
    owner_totals: {
      partner_a: { paid: 23000, received: 55000, net: 32000 },
      partner_b: { paid: 4220.25, received: 1200, net: -3020.25 },
    },
    partner_panels: {
      partner_a: { label: "Fixture A", paid: 23000, received: 55000, net: 32000, net_class: "pos" },
      partner_b: { label: "Fixture B", paid: 4220.25, received: 1200, net: -3020.25, net_class: "neg" },
    },
    partner_labels: { partner_a: "Fixture A", partner_b: "Fixture B" },
    detailed: makeDetailed(),
    personal_share: null,
    balanced: true,
    ...overrides,
  };
}

// Locate a numbered section element by its heading.
function sectionOf(headingName: string): HTMLElement {
  const heading = screen.getByRole("heading", { name: headingName });
  const section = heading.closest("section");
  expect(section).not.toBeNull();
  return section as HTMLElement;
}

// Full textContent of every <details> summary in a section — summaries wrap
// the category title in <b>, so query by textContent, not own-text.
function summaryTexts(section: HTMLElement): string[] {
  return Array.from(section.querySelectorAll("details summary")).map(
    (s) => (s.textContent ?? "").replace(/\s+/g, " ").trim()
  );
}

describe("DetailedSections — FIX 1 personal Subtotal parity", () => {
  it("renders each section's own subtotal, not the shared personal_total", () => {
    render(<DetailedSections report={makeReport()} />);

    const partnerA = sectionOf("5. Fixture A personal spending");
    const subC = within(partnerA).getByText("Subtotal").closest("tr");
    expect(subC).not.toBeNull();
    expect(subC).toHaveTextContent("-6,043.97");
    expect(subC).toHaveTextContent("7.5%");

    const partnerB = sectionOf("6. Fixture B personal spending");
    const subR = within(partnerB).getByText("Subtotal").closest("tr");
    expect(subR).not.toBeNull();
    expect(subR).toHaveTextContent("-9,659.78");
    expect(subR).toHaveTextContent("12.0%");

    // Combined personal_total must not leak into either Subtotal row.
    expect(subC).not.toHaveTextContent("15,703.75");
    expect(subR).not.toHaveTextContent("15,703.75");
  });

  it("styles the subtotal cell via subtotal_class", () => {
    render(<DetailedSections report={makeReport()} />);
    const partnerA = sectionOf("5. Fixture A personal spending");
    const subC = within(partnerA).getByText("Subtotal").closest("tr");
    const cell = within(subC!).getByText("-6,043.97");
    expect(cell).toHaveClass("neg");
  });

  it("falls back to personal_total + signOf for pre-PR5 stored reports", () => {
    const report = makeReport();
    report.detailed!.personal_partner_a!.subtotal = null;
    report.detailed!.personal_partner_a!.subtotal_class = null;
    render(<DetailedSections report={report} />);

    const partnerA = sectionOf("5. Fixture A personal spending");
    const subC = within(partnerA).getByText("Subtotal").closest("tr");
    const cell = within(subC!).getByText("-15,703.75");
    expect(cell).toHaveClass("neg"); // signOf(-15703.75)
  });
});

describe("DetailedSections — FIX 2 per-category drill-downs", () => {
  it("renders drill-downs grouped by category under each section", () => {
    const { container } = render(<DetailedSections report={makeReport()} />);

    // Per-category <details class="drilldown">: home 1, common 2 (com1 + the
    // unmapped fallback), personal x2, trips 1, excluded 1.
    const drills = container.querySelectorAll("details.drilldown");
    expect(drills.length).toBe(7);

    expect(summaryTexts(sectionOf("3. Home"))).toContain("Rent - 16,000.00 NOK - 1 txns");
    expect(summaryTexts(sectionOf("5. Fixture A personal spending"))).toContain(
      "Games - 1,050.00 NOK - 2 txns"
    );
    expect(summaryTexts(sectionOf("6. Fixture B personal spending"))).toContain(
      "Clothes - 900.00 NOK - 1 txns"
    );
    expect(summaryTexts(sectionOf("7. Trips (Common + Personal)"))).toContain(
      "Flights - 3,200.00 NOK - 1 txns"
    );
    expect(summaryTexts(sectionOf("9. Excluded categories"))).toContain(
      "Gifts - 300.00 NOK - 1 txns"
    );
  });

  it("titles multi-level categories as 'Root / Leaf' like the old UI", () => {
    render(<DetailedSections report={makeReport()} />);
    expect(summaryTexts(sectionOf("4. Common"))).toContain(
      "Groceries / Supermarket - 450.50 NOK - 1 txns"
    );
  });

  it("shows transaction rows (date/payee/amount, as-is signed) inside drilldowns", () => {
    render(<DetailedSections report={makeReport()} />);
    const common = sectionOf("4. Common");
    const row = within(common).getByText("Rema 1000").closest("tr");
    expect(row).not.toBeNull();
    expect(row).toHaveTextContent("2026-08-03");
    expect(row).toHaveTextContent("-450.50");
  });

  it("sorts drilldown rows by date then id", () => {
    render(<DetailedSections report={makeReport()} />);
    const partnerA = sectionOf("5. Fixture A personal spending");
    const details = partnerA.querySelector("details.drilldown");
    expect(details).not.toBeNull();
    const rows = details!.querySelectorAll(".tx-table tbody tr");
    expect(rows.length).toBe(2);
    expect(rows[0]).toHaveTextContent("Board Game Store"); // 2026-08-02
    expect(rows[1]).toHaveTextContent("Steam games"); // 2026-08-11
  });

  it("routes unmapped leaf categories to the Common drilldown", () => {
    render(<DetailedSections report={makeReport()} />);
    const common = sectionOf("4. Common");
    expect(summaryTexts(common)).toContain("Kiosk - 120.00 NOK - 1 txns");
    expect(within(common).getByText("Kiosk 7")).toBeInTheDocument();
  });

  it("routes transfers to Excluded unless mapped home/savings/excluded (DTO parity)", () => {
    // _routed_section parity: a common-mapped transfer shows in the Excluded
    // drilldown (where the DTO's excluded rows count it), not under Common.
    const commonTransfer = {
      id: 98,
      date: "2026-08-09",
      amount: -500,
      payee: "Internal Move",
      note: "",
      account_id: "acc1",
      account_name: "Checking",
      owner: "partner_a",
      category_path: [
        { id: "rootG", title: "Groceries" },
        { id: "com1", title: "Supermarket" },
      ],
      is_transfer: true,
    };
    // Keeps its section: savings-mapped transfer stays under Savings.
    const savingsTransfer = {
      ...commonTransfer,
      id: 99,
      payee: "Savings Move",
      category_path: [{ id: "sav1", title: "Fond" }],
    };
    render(
      <DetailedSections
        report={makeReport({
          normalized_transactions: [...makeTxns(), commonTransfer, savingsTransfer],
        })}
      />
    );

    expect(within(sectionOf("4. Common")).queryByText("Internal Move")).not.toBeInTheDocument();
    expect(
      within(sectionOf("4. Common")).queryByText(
        "Groceries / Supermarket - 950.50 NOK - 2 txns"
      )
    ).not.toBeInTheDocument();
    const excluded = sectionOf("9. Excluded categories");
    expect(within(excluded).getByText("Internal Move")).toBeInTheDocument();
    expect(summaryTexts(excluded)).toContain("Groceries / Supermarket - 500.00 NOK - 1 txns");
    expect(within(excluded).queryByText("Savings Move")).not.toBeInTheDocument();
    expect(within(sectionOf("2. Savings")).getByText("Savings Move")).toBeInTheDocument();
  });

  it("income drilldown expands to list salary + third-party txns", async () => {
    render(<DetailedSections report={makeReport()} />);
    const income = sectionOf("1. Income");
    const summary = within(income).getByText("Transaction details (2)");

    // Collapsed: table only renders when open.
    expect(within(income).queryByText("Employer AS")).not.toBeInTheDocument();

    fireEvent.click(summary);

    expect(await within(income).findByText("Employer AS")).toBeInTheDocument();
    expect(within(income).getByText("Refund Central")).toBeInTheDocument();
    expect(within(income).getByText("+55,000.00")).toBeInTheDocument();
  });

  it("CC payments drilldown lists payments with abs Paid column", () => {
    render(<DetailedSections report={makeReport()} />);
    const cc = sectionOf("8. CC Payments");
    expect(within(cc).getByText("CC payment details")).toBeInTheDocument();
    const row = within(cc).getByText("DNB Mastercard").closest("tr");
    expect(row).not.toBeNull();
    expect(row).toHaveTextContent("2026-08-20");
    expect(row).toHaveTextContent("1,500.00"); // abs, unsigned
  });

  it("savings drilldown shows an open card per category (leaf title grouping)", () => {
    render(<DetailedSections report={makeReport()} />);
    const savings = sectionOf("2. Savings");
    // Leaf-title grouping, always-open card markup (old UI parity — QA I-1).
    const cards = savings.querySelectorAll(".drilldown-card h3");
    const titles = Array.from(cards).map((h) => h.textContent ?? "");
    expect(titles).toContain("Fond - 2,000.00 NOK - 1 txns");
    expect(within(savings).getByText("Kron Fond")).toBeInTheDocument();
  });

  it("renders no drill-downs when normalized_transactions is empty", () => {
    const { container } = render(
      <DetailedSections report={makeReport({ normalized_transactions: [] })} />
    );
    expect(container.querySelectorAll("details.drilldown").length).toBe(0);
    expect(container.querySelectorAll(".drilldown-card").length).toBe(0);
  });
});
