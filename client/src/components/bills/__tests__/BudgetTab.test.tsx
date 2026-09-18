// F2 grid R4.6 — BudgetTab (expanded month card "Budget" tab) tests.
// Round-4 redesign: side-by-side partner columns, always-visible BILLS/
// CC/FREE group headers (muted empty-line fallback instead of hiding),
// a "Planned bills" total row every month, "(over)" indicators, and a
// regression test for the mapper type-leak fix (salary/savings must
// never appear in the bill-category rows or the Planned-bills total).
// Round-4.6 adds a Salary row (plain sum, no matching) and a CC bill
// est-vs-real row to the Bills group.

import { render, screen, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import type { FinanceEvent, MonthData, PartnerEconomy } from "@/types/api";

import type { F2PartnerIdentity } from "@/types/api";

import { BudgetTab } from "../BudgetTab";

// Partner identity triples — id keys attribution, slot keys styling/order.
const PARTNER_A: F2PartnerIdentity = { partner_id: "partner_a", partner_slot: "a", label: "Fixture A" };
const PARTNER_B: F2PartnerIdentity = { partner_id: "partner_b", partner_slot: "b", label: "Fixture B" };

let idSeq = 0;
function ev(over: Partial<FinanceEvent> & { title: string; amount: number }): FinanceEvent {
  return {
    id: `e${idSeq++}`,
    date: "2026-07-15",
    day: 15,
    type: "buy",
    account: "FxA CC",
    partner: PARTNER_A,
    ...over,
  };
}

function makePartner(overrides: Partial<PartnerEconomy> = {}): PartnerEconomy {
  return {
    partner: PARTNER_A,
    estimatedSalary: 44_000,
    bills: 18_500,
    budget: 8_200,
    ccUsage: 4_200,
    estimatedCcBill: 9_800,
    realCcBill: 9_800,
    realCcBillLabel: "9,800 kr",
    realBills: 19_000,
    realBillsLabel: "19,000 kr",
    savingsBalance: 32_000,
    savingsContribution: 5_000,
    savingsPlanned: 3_000,
    savingsDelta: 2_000,
    net: 16_700,
    status: "covered",
    estimatedSalaryLabel: "44,000 kr",
    billsLabel: "18,500 kr",
    budgetLabel: "8,200 kr",
    ccUsageLabel: "4,200 kr",
    estimatedCcBillLabel: "9,800 kr",
    savingsBalanceLabel: "32,000 kr",
    savingsContributionLabel: "5,000 kr",
    savingsPlannedLabel: "3,000 kr",
    savingsDeltaLabel: "+2,000 kr",
    bar: {
      billsWidth: "30%",
      budgetWidth: "12%",
      billsFillWidth: "50%",
      billsFillSmall: false,
      estCcBillWidth: "50%",
      ccUsageWidth: "50%",
      budgetUsageWidth: "50%",
      budgetOverspent: false,
      budgetFillTone: "income",
      savingsPlannedWidth: "9%",
      savingsDeltaWidth: "6%",
      savingsDeltaTone: "income",
      salaryWidth: "100%",
      upperBarWidth: "30%",
      remainingLabel: "25,500 kr left",
      remainingTone: "income",
      netLabel: "16,700 kr",
    },
    ...overrides,
  };
}

function makeMonth(over: Partial<MonthData> = {}): MonthData {
  return {
    key: "2026-07",
    label: "July 2026",
    year: 2026,
    monthIndex: 6,
    events: [],
    billsCount: 0,
    buysCount: 0,
    net: 0,
    partners: [],
    ...over,
  };
}

// Width of the colored fill inside the row carrying `valueText`.
function fillStyleOf(valueText: string): string | null {
  const value = screen.getByText(valueText);
  const row = value.closest("div")?.parentElement;
  return row?.querySelector<HTMLElement>("[style]")?.style.width ?? null;
}

// The rendered column for one partner (dot+name header + its 3 groups).
function columnFor(partnerName: string): HTMLElement {
  const tag = screen.getByText(partnerName);
  // PartnerTag > column wrapper (border/rounded-md container).
  return tag.closest("div")!.parentElement as HTMLElement;
}

describe("BudgetTab layout — side-by-side partner columns", () => {
  it("schema-4 payloads (partner_id \"\") still group by in-snapshot label", () => {
    // Legacy neutral mode: no semantic ids — labels stay attached to their
    // own block, so in-snapshot label match keys the columns.
    const legacyA: F2PartnerIdentity = { partner_id: "", partner_slot: "", label: "Fixture A" };
    const legacyB: F2PartnerIdentity = { partner_id: "", partner_slot: "", label: "Fixture B" };
    const month = makeMonth({
      events: [
        ev({ title: "Rent", type: "bill", amount: -900, partner: legacyA }),
        ev({ title: "Groceries", type: "bill", amount: -500, partner: legacyB }),
      ],
      partners: [
        makePartner({ partner: legacyA }),
        makePartner({ partner: legacyB }),
      ],
    });
    render(<BudgetTab month={month} isPast={false} />);
    const colA = columnFor("Fixture A");
    const colB = columnFor("Fixture B");
    expect(within(colA).getByText("Rent")).toBeInTheDocument();
    expect(within(colA).queryByText("Groceries")).toBeNull();
    expect(within(colB).getByText("Groceries")).toBeInTheDocument();
    expect(within(colB).queryByText("Rent")).toBeNull();
  });

  it("renders one column per partner with Bills/CC/Free group headers always visible", () => {
    const month = makeMonth({
      events: [],
      partners: [
        makePartner(),
        makePartner({
          partner: PARTNER_B,
          realBills: null,
          realBillsLabel: "",
          // Zero out CC bill fields too so the Bills group truly has
          // nothing to show (no salary events either) — proves the
          // "No bill budgets" empty state still fires correctly.
          estimatedCcBill: 0,
          realCcBill: null,
        }),
      ],
    });
    render(<BudgetTab month={month} isPast={false} />);

    expect(screen.getByText("Fixture A")).toBeInTheDocument();
    expect(screen.getByText("Fixture B")).toBeInTheDocument();

    const partnerA = columnFor("Fixture A");
    expect(within(partnerA).getByText("Bills")).toBeInTheDocument();
    expect(within(partnerA).getByText("CC")).toBeInTheDocument();
    expect(within(partnerA).getByText("Free")).toBeInTheDocument();

    const partnerB = columnFor("Fixture B");
    expect(within(partnerB).getByText("No bill budgets")).toBeInTheDocument();
    expect(within(partnerB).getByText("No CC budgets")).toBeInTheDocument();
    expect(within(partnerB).getByText("No free-budget data")).toBeInTheDocument();
  });
});

describe("BudgetTab Bills group", () => {
  it("groups bill events by category with planned sums, sorted smallest → largest, and shows a 'Planned bills' total row", () => {
    const month = makeMonth({
      events: [
        ev({ title: "Groceries", type: "bill", amount: -5_000 }),
        ev({ title: "Groceries", type: "bill", amount: -3_000 }),
        ev({ title: "Rent", type: "bill", amount: -15_500 }),
        // Other partner's bill must not leak into Fixture A's rows.
        ev({ title: "Rent", type: "bill", amount: -900, partner: PARTNER_B }),
        // Buys never count in the bills group.
        ev({ title: "Tech", type: "buy", amount: -1_200 }),
      ],
      // No CC bill / salary noise for this test — isolate category rows.
      partners: [makePartner({ estimatedCcBill: 0, realCcBill: null })],
    });
    render(<BudgetTab month={month} isPast />);

    const partnerA = columnFor("Fixture A");
    expect(within(partnerA).getByText("Planned bills")).toBeInTheDocument();
    expect(within(partnerA).getByText("Rent")).toBeInTheDocument();
    expect(within(partnerA).getByText("15,500 kr")).toBeInTheDocument();
    expect(within(partnerA).getByText("Groceries")).toBeInTheDocument();
    expect(within(partnerA).getByText("8,000 kr")).toBeInTheDocument();
    // Total row = 15,500 + 8,000 = 23,500 (bills only, no buys).
    expect(within(partnerA).getByText("23,500 kr")).toBeInTheDocument();
    // Fill = share of section planned total (23,500 ≈ 65.96%).
    expect(fillStyleOf("15,500 kr")).toMatch(/^65\.95/);
    expect(fillStyleOf("8,000 kr")).toMatch(/^34\.04/);
    // Round-4.9: smallest first — Groceries (8,000) before Rent (15,500).
    const groceries = within(partnerA).getByText("Groceries");
    const rent = within(partnerA).getByText("Rent");
    expect(
      groceries.compareDocumentPosition(rent) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("shows the real-paid header bar only when realBills is set, with over indicator", () => {
    const withReal = makeMonth({
      events: [ev({ title: "Rent", type: "bill", amount: -15_500 })],
      partners: [makePartner()], // realBills 19,000 vs planned 18,500
    });
    const { unmount } = render(<BudgetTab month={withReal} isPast />);
    expect(
      screen.getByText((_, node) => node?.textContent === "19,000 kr of 18,500 kr planned (+500 kr over)"),
    ).toBeInTheDocument();
    unmount();

    const noReal = makeMonth({
      events: [ev({ title: "Rent", type: "bill", amount: -15_500 })],
      partners: [makePartner({ realBills: null, realBillsLabel: "" })],
    });
    render(<BudgetTab month={noReal} isPast={false} />);
    expect(screen.queryByText(/of 18,500 kr planned/)).not.toBeInTheDocument();
  });

  it("regression: salary and savings events never appear in bill category rows or the Planned-bills total", () => {
    const month = makeMonth({
      events: [
        ev({ title: "Rent", type: "bill", amount: -15_500 }),
        ev({ title: "Salary — Fixture A", type: "salary", amount: 44_000 }),
        ev({ title: "Savings transfer — Fixture A", type: "savings", amount: -5_000 }),
      ],
      // No CC bill noise — isolate the salary/savings leak check.
      partners: [
        makePartner({
          realBills: null,
          realBillsLabel: "",
          estimatedCcBill: 0,
          realCcBill: null,
        }),
      ],
    });
    render(<BudgetTab month={month} isPast={false} />);

    const partnerA = columnFor("Fixture A");
    // "Savings transfer" title must never render as a bill-category row.
    expect(within(partnerA).queryByText(/Savings transfer/)).not.toBeInTheDocument();
    // The Salary row itself IS intentional (round-4.6) — its plain sum
    // renders, but must NOT be folded into the Planned-bills total.
    expect(within(partnerA).getByText("Salary")).toBeInTheDocument();
    expect(within(partnerA).getByText("44,000 kr")).toBeInTheDocument();
    // Planned-bills total must equal Rent only (15,500), not
    // 15,500 + salary/savings noise. Both the total row and the Rent
    // row show "15,500 kr" — assert 2 matches, and that 59,500
    // (15,500 + 44,000) never appears.
    expect(within(partnerA).getAllByText("15,500 kr")).toHaveLength(2);
    expect(within(partnerA).queryByText("59,500 kr")).not.toBeInTheDocument();

    // Also assert CC/Free groups don't render salary as a buy.
    expect(within(partnerA).getByText("No CC budgets")).toBeInTheDocument();
  });

  it("omits the Salary row when no salary events exist that month", () => {
    const month = makeMonth({
      events: [ev({ title: "Rent", type: "bill", amount: -15_500 })],
      partners: [makePartner({ estimatedCcBill: 0, realCcBill: null })],
    });
    render(<BudgetTab month={month} isPast={false} />);
    const partnerA = columnFor("Fixture A");
    expect(within(partnerA).queryByText("Salary")).not.toBeInTheDocument();
  });

  it("CC bill row: past month shows real vs estimated with over indicator", () => {
    const month = makeMonth({
      events: [ev({ title: "Rent", type: "bill", amount: -15_500 })],
      partners: [
        makePartner({
          estimatedCcBill: 9_800,
          estimatedCcBillLabel: "9,800 kr",
          realCcBill: 11_300,
          realCcBillLabel: "11,300 kr",
        }),
      ],
    });
    render(<BudgetTab month={month} isPast />);
    const partnerA = columnFor("Fixture A");
    expect(within(partnerA).getByText("CC bill")).toBeInTheDocument();
    expect(
      within(partnerA).getByText(
        (_, node) => node?.textContent === "11,300 kr of 9,800 kr planned (+1,500 kr over)",
      ),
    ).toBeInTheDocument();
  });

  it("CC bill row: current/future month shows estimated-only 'planned' with no over indicator", () => {
    const month = makeMonth({
      events: [ev({ title: "Rent", type: "bill", amount: -15_500 })],
      partners: [
        makePartner({
          // realBills null too — isolates the CC bill row's own over
          // indicator from the unrelated "Real paid" row's over span.
          realBills: null,
          realBillsLabel: "",
          estimatedCcBill: 9_800,
          estimatedCcBillLabel: "9,800 kr",
          realCcBill: null,
          realCcBillLabel: "",
        }),
      ],
    });
    render(<BudgetTab month={month} isPast={false} />);
    const partnerA = columnFor("Fixture A");
    expect(within(partnerA).getByText("CC bill")).toBeInTheDocument();
    expect(within(partnerA).getByText("9,800 kr planned")).toBeInTheDocument();
    expect(within(partnerA).queryByText(/over\)/)).not.toBeInTheDocument();
  });

  it("regression (round-4.9): CC paydown event (isCcPayment) never appears in bill rows or the Planned-bills total — only in the 'CC bill' est-vs-real row", () => {
    const month = makeMonth({
      events: [
        ev({ title: "Rent", type: "bill", amount: -15_500 }),
        ev({
          title: "CC Payment (paired)",
          type: "bill",
          amount: -43_160,
          isCcPayment: true,
        }),
      ],
      partners: [makePartner({ estimatedCcBill: 43_160, realCcBill: 43_160 })],
    });
    render(<BudgetTab month={month} isPast />);
    const partnerA = columnFor("Fixture A");
    // No duplicated category row; total is Rent only.
    expect(within(partnerA).queryByText("CC Payment (paired)")).not.toBeInTheDocument();
    expect(within(partnerA).getAllByText("15,500 kr").length).toBeGreaterThanOrEqual(1);
    expect(within(partnerA).queryByText("58,660 kr")).not.toBeInTheDocument();
    // But the single "CC bill" row still shows the real-vs-planned value.
    expect(
      within(partnerA).getByText(
        (_, node) => node?.textContent === "43,160 kr of 43,160 kr planned",
      ),
    ).toBeInTheDocument();
  });

  it("PR65: current month with realCcBill (override) renders est-only 'planned' row, not past-style real-vs-planned", () => {
    const month = makeMonth({
      events: [ev({ title: "Rent", type: "bill", amount: -15_500 })],
      partners: [makePartner({ estimatedCcBill: 9_800, realCcBill: 12_000 })],
    });
    render(<BudgetTab month={month} isPast={false} />);
    const partnerA = columnFor("Fixture A");
    // Current-style: est-only planned row, no real-vs-planned comparison.
    expect(within(partnerA).getByText("9,800 kr planned")).toBeInTheDocument();
    expect(
      within(partnerA).queryByText(
        (_, node) => node?.textContent === "12,000 kr of 9,800 kr planned",
      ),
    ).not.toBeInTheDocument();
  });

  it("'Planned bills' total excludes Salary and CC bill amounts", () => {
    const month = makeMonth({
      events: [
        ev({ title: "Rent", type: "bill", amount: -15_500 }),
        ev({ title: "Salary — Fixture A", type: "salary", amount: 44_000 }),
      ],
      partners: [
        makePartner({
          estimatedCcBill: 9_800,
          estimatedCcBillLabel: "9,800 kr",
          realCcBill: 11_300,
          realCcBillLabel: "11,300 kr",
        }),
      ],
    });
    render(<BudgetTab month={month} isPast />);
    const partnerA = columnFor("Fixture A");
    // Total row must be exactly Rent (15,500), never inflated by
    // salary (44,000) or the CC bill (9,800/11,300).
    expect(within(partnerA).getAllByText("15,500 kr").length).toBeGreaterThanOrEqual(1);
    expect(within(partnerA).queryByText("55,300 kr")).not.toBeInTheDocument();
    expect(within(partnerA).queryByText("59,500 kr")).not.toBeInTheDocument();
  });
});

describe("BudgetTab CC group", () => {
  it("past/current: value = real usage of planned, fill = usage/planned (Hello Fresh example)", () => {
    const month = makeMonth({
      events: [
        ev({ title: "Hello Fresh", amount: -5_200, type: "buy" }),
        ev({ title: "Memberships", amount: -586, type: "buy" }),
      ],
      partners: [
        makePartner({
          ccUsageByCategory: { "Hello Fresh": 3_622, Memberships: 228 },
        }),
      ],
    });
    render(<BudgetTab month={month} isPast />);
    expect(screen.getByText("3,622 kr of 5,200 kr planned")).toBeInTheDocument();
    expect(screen.getByText("228 kr of 586 kr planned")).toBeInTheDocument();
    // Sorted by planned desc → Hello Fresh row before Memberships row.
    const helloFresh = screen.getByText("3,622 kr of 5,200 kr planned");
    const memberships = screen.getByText("228 kr of 586 kr planned");
    expect(helloFresh.compareDocumentPosition(memberships)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
    expect(fillStyleOf("3,622 kr of 5,200 kr planned")).toMatch(/^69\.65/);
    expect(fillStyleOf("228 kr of 586 kr planned")).toMatch(/^38\.9/);
  });

  it("ccUsageByCategory null (future/stale): estimated-only 'planned' row, fill 0", () => {
    const month = makeMonth({
      events: [ev({ title: "Hello Fresh", amount: -5_200, type: "buy" })],
      partners: [makePartner({ ccUsageByCategory: null })],
    });
    render(<BudgetTab month={month} isPast={false} />);
    // Row + round-4.9 Total row share the same planned-only label.
    const rows = screen.getAllByText("5,200 kr planned");
    expect(rows.length).toBeGreaterThanOrEqual(1);
    for (const r of rows) {
      const rowFill = r.closest("div")?.parentElement?.querySelector<HTMLElement>("[style]");
      expect(rowFill?.style.width).toBe("0%");
    }
  });

  it("usage over planned → shortfall tone + over indicator", () => {
    const month = makeMonth({
      events: [ev({ title: "Hello Fresh", amount: -5_200, type: "buy" })],
      partners: [
        makePartner({ ccUsageByCategory: { "Hello Fresh": 6_000 } }),
      ],
    });
    render(<BudgetTab month={month} isPast />);
    // Row + round-4.9 Total row are identical here (single category).
    expect(
      screen.getAllByText(
        (_, node) => node?.textContent === "6,000 kr of 5,200 kr planned (+800 kr over)",
      ).length,
    ).toBe(2);
  });

  it("Total row = sum usage / sum planned, over indicator when exceeded; planned-only fallback", () => {
    const month = makeMonth({
      events: [
        ev({ title: "Hello Fresh", amount: -5_200, type: "buy" }),
        ev({ title: "Memberships", amount: -586, type: "buy" }),
      ],
      partners: [
        makePartner({
          ccUsageByCategory: { "Hello Fresh": 5_200, Memberships: 800 },
        }),
      ],
    });
    render(<BudgetTab month={month} isPast />);
    // usage 6,000 vs planned 5,786 → 214 over.
    expect(
      screen.getByText(
        (_, node) => node?.textContent === "6,000 kr of 5,786 kr planned (+214 kr over)",
      ),
    ).toBeInTheDocument();
  });

  it("guard: BudgetTab.tsx source never references isMatched", () => {
    // Guard test for the round-4.7 user rule: "do not use matched, but
    // budget based — same category txn go to same category planned".
    // Read the component source and assert the literal field name is
    // gone from Section B/C logic.
    const src = readFileSync("src/components/bills/BudgetTab.tsx", "utf-8");
    expect(src).not.toMatch(/isMatched/);
  });
});

describe("BudgetTab Free group", () => {
  it("renders ccUsageByCategory rows minus planned CC-buy categories, sorted ascending, plain values (no 'budget' string)", () => {
    const month = makeMonth({
      events: [ev({ title: "Hello Fresh", amount: -5_200, type: "buy" })],
      partners: [
        makePartner({
          ccUsageByCategory: { "Hello Fresh": 3_622, Groceries: 4_000, Dining: 2_500 },
        }),
      ],
    });
    render(<BudgetTab month={month} isPast />);

    // "Hello Fresh" has a planned CC buy → excluded from FREE entirely.
    const freeHeader = screen.getByText("Free");
    const freeGroup = freeHeader.parentElement as HTMLElement;
    expect(within(freeGroup).queryByText(/Hello Fresh/)).not.toBeInTheDocument();
    expect(within(freeGroup).queryByText(/3,622/)).not.toBeInTheDocument();

    // Round-4.8: plain values, no "of X budget" denominator on usage rows.
    expect(screen.getByText("4,000 kr")).toBeInTheDocument();
    expect(screen.getByText("2,500 kr")).toBeInTheDocument();
    // Sorted ASCENDING → Dining (2,500) before Groceries (4,000).
    const groceries = screen.getByText("4,000 kr");
    const dining = screen.getByText("2,500 kr");
    expect(dining.compareDocumentPosition(groceries)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
  });

  it("no planned buys → FREE still shows all ccUsageByCategory categories", () => {
    const month = makeMonth({
      events: [],
      partners: [
        makePartner({
          ccUsageByCategory: { Groceries: 4_000, Dining: 2_500, Travel: 1_000 },
        }),
      ],
    });
    render(<BudgetTab month={month} isPast />);

    expect(screen.getByText("4,000 kr")).toBeInTheDocument();
    expect(screen.getByText("2,500 kr")).toBeInTheDocument();
    expect(screen.getByText("1,000 kr")).toBeInTheDocument();
  });

  it("merges categories under 500 kr into one 'Other (n)' row, summed", () => {
    const month = makeMonth({
      events: [],
      partners: [
        makePartner({
          ccUsageByCategory: { Groceries: 4_000, Streaming: 300, Snacks: 400 },
        }),
      ],
    });
    render(<BudgetTab month={month} isPast />);

    // Streaming (300) + Snacks (400) = 700, merged into "Other (2)".
    expect(screen.getByText("Other (2)")).toBeInTheDocument();
    expect(screen.getByText("700 kr")).toBeInTheDocument();
    expect(screen.queryByText("Streaming")).not.toBeInTheDocument();
    expect(screen.queryByText("Snacks")).not.toBeInTheDocument();
  });

  it("a single sub-500 category is NOT merged — stays its own row", () => {
    const month = makeMonth({
      events: [],
      partners: [
        makePartner({
          ccUsageByCategory: { Groceries: 4_000, Streaming: 300 },
        }),
      ],
    });
    render(<BudgetTab month={month} isPast />);

    expect(screen.getByText("Streaming")).toBeInTheDocument();
    expect(screen.getByText("300 kr")).toBeInTheDocument();
    expect(screen.queryByText(/Other/)).not.toBeInTheDocument();
  });

  it("round-4.9: 'CC Payment (paired)' row disappears from FREE when its amount equals realCcBill (shown once as Section-A 'CC bill')", () => {
    const month = makeMonth({
      events: [],
      partners: [
        makePartner({
          realCcBill: 43_160,
          ccUsageByCategory: {
            "CC Payment (paired)": 43_160,
            Groceries: 4_000,
          },
        }),
      ],
    });
    render(<BudgetTab month={month} isPast />);

    // FREE group: no duplicate 43,160 row.
    expect(screen.queryByText("CC Payment (paired)")).not.toBeInTheDocument();
    expect(screen.getByText("4,000 kr")).toBeInTheDocument();

    // Same value stays as Section A "CC bill" row exactly once.
    const ccBillRows = screen.getAllByText("CC bill");
    expect(ccBillRows).toHaveLength(1);
  });

  it("round-4.9: a 'CC Payment (paired)' amount that does NOT match realCcBill stays in FREE", () => {
    const month = makeMonth({
      events: [],
      partners: [
        makePartner({
          realCcBill: 43_160,
          ccUsageByCategory: {
            "CC Payment (paired)": 1_500,
            Groceries: 4_000,
          },
        }),
      ],
    });
    render(<BudgetTab month={month} isPast />);
    expect(screen.getByText("CC Payment (paired)")).toBeInTheDocument();
    expect(screen.getByText("1,500 kr")).toBeInTheDocument();
  });

  it("drops only ~0 rows (rounding guard), keeps all other raw values", () => {
    const month = makeMonth({
      events: [],
      partners: [
        makePartner({
          ccUsageByCategory: { Groceries: 4_000, Zeroed: 0.001, Travel: 1_000 },
        }),
      ],
    });
    render(<BudgetTab month={month} isPast />);

    expect(screen.getByText("4,000 kr")).toBeInTheDocument();
    expect(screen.getByText("1,000 kr")).toBeInTheDocument();
    expect(screen.queryByText("Zeroed")).not.toBeInTheDocument();
  });

  it("shows the muted fallback line when ccUsageByCategory is null or absent", () => {
    const nullCat = makeMonth({
      partners: [makePartner({ ccUsageByCategory: null })],
      events: [],
    });
    const { unmount } = render(<BudgetTab month={nullCat} isPast />);
    expect(screen.getByText("No free-budget data")).toBeInTheDocument();
    unmount();

    const absent = makeMonth({ partners: [makePartner()], events: [] });
    render(<BudgetTab month={absent} isPast />);
    expect(screen.getByText("No free-budget data")).toBeInTheDocument();
  });

  it("Total row: value/tone/over — under budget income, over budget shortfall + over indicator", () => {
    const month = makeMonth({
      partners: [
        makePartner({
          ccUsageByCategory: { Groceries: 4_000, Gadgets: 9_000 },
        }),
      ],
    });
    render(<BudgetTab month={month} isPast />);
    // Total = 4,000 + 9,000 = 13,000, budget default 8,200 → over.
    expect(
      screen.getByText(
        (_, node) => node?.textContent === "13,000 kr of 8,200 kr budget (+4,800 kr over)",
      ),
    ).toBeInTheDocument();
    const totalRow = screen.getByText("Total").closest("div")!.parentElement!.querySelector("[style]")!;
    expect(totalRow.className).toContain("bg-shortfall");
  });

  it("Total row: budget null → bare 'X kr' value, neutral tone, fill 0", () => {
    const month = makeMonth({
      partners: [
        makePartner({
          budget: null,
          budgetLabel: "",
          ccUsageByCategory: { Streaming: 300, Hobbies: 600 },
        }),
      ],
    });
    render(<BudgetTab month={month} isPast />);
    expect(screen.getByText("300 kr")).toBeInTheDocument();
    expect(screen.getByText("600 kr")).toBeInTheDocument();
    expect(screen.getByText("Total")).toBeInTheDocument();
    // Total = 300 + 600 = 900, plain, no budget denominator.
    const totalValue = screen.getByText(
      (_, node) => node?.textContent === "900 kr",
    );
    expect(totalValue).toBeInTheDocument();
    const totalRow = screen.getByText("Total").closest("div")!.parentElement!.querySelector("[style]")!;
    expect(totalRow.className).toContain("bg-foreground/30");
  });
});
