// F2-A — bills zone UI tests.
// Pin the F2-A design rules:
//   - Bills zone shows a single horizontal row: small "Bills" label +
//     value (left, on the red), small "Estimated cc bill" label + value
//     (right, in the muted remainder).
//   - Red fill width = bills / totalBills, left to right.
//   - Capsule top-left "Total bills" pill still renders.
// Labels in this row are 9-10px uppercase; the value sits inline with
// its label. This test pins both the labels AND the value positions.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { PartnerEconomy } from "@/types/api";

import { EconomyBar } from "../EconomyBar";
import { formatKr } from "../finance-data";

function makeEconomy(overrides: Partial<PartnerEconomy>): PartnerEconomy {
  const bills = 31_500;
  const estimatedCcBill = 14_000;
  const budget = 17_250;
  const ccUsage = 7_000;
  const estimatedSalary = 44_000;
  const savingsBalance = 20_000;
  const savingsContribution = 3_000;
  const savingsPlanned = 3_000;
  const net = estimatedSalary - bills - estimatedCcBill; // -1,500

  // Pre-compute widths that mirror finance-data.ts so the fixture
  // matches what the production buildMonth() would emit.
  const totalBills = bills + estimatedCcBill;
  const outflows = totalBills;
  // Bills zone width = outer − budget (budget is constant 11.862%).
  const SALARY_ZONE_FRACTION = 0.659;
  const BUDGET_ZONE_RATIO = 0.18;
  const outerRatio = Math.min(totalBills / estimatedSalary, 1) * SALARY_ZONE_FRACTION;
  const budgetRatio = SALARY_ZONE_FRACTION * BUDGET_ZONE_RATIO;
  const billsZoneW = Math.min(
    100,
    Math.max(0, (outerRatio - budgetRatio) * 100),
  );
  const fillBills = Math.min(
    100,
    Math.max(0, (bills / Math.max(totalBills, 1)) * 100),
  );
  const totalBillsRatio = totalBills / estimatedSalary;
  const billsFillSmall = totalBillsRatio < 0.5;
  // F2-B: vertical fill in budget zone = ccUsage / budget.
  const budgetUsageShare = Math.min(
    100,
    Math.max(0, (ccUsage / Math.max(budget, 1)) * 100),
  );
  const budgetFillTone: "income" | "warning" | "shortfall" =
    ccUsage > budget
      ? "shortfall"
      : budgetUsageShare > 80
        ? "shortfall"
        : budgetUsageShare > 50
          ? "warning"
          : "income";
  // F2-C: random mock delta in [-1.5×contribution, +1.5×contribution].
  const savingsDelta = Math.round(savingsContribution * 0.3);
  const savingsDeltaTone: "income" | "shortfall" | "neutral" =
    savingsDelta > 0 ? "income" : savingsDelta < 0 ? "shortfall" : "neutral";
  const estCcShare = Math.min(
    100,
    Math.max(0, (estimatedCcBill / Math.max(budget, 1)) * 100),
  );
  const ccUsageShare = Math.min(
    100,
    Math.max(0, (ccUsage / Math.max(estimatedCcBill, 1)) * 100),
  );
  const salaryShare = Math.min(
    100,
    Math.max(6, (estimatedSalary / Math.max(outflows, 1)) * 100),
  );
  const remaining = estimatedSalary - outflows; // -1,500

  return {
    partner: { partner_id: "partner_a", partner_slot: "a", label: "Fixture A" },
    estimatedSalary,
    bills,
    budget,
    ccUsage,
    estimatedCcBill,
    savingsBalance,
    savingsContribution,
    savingsPlanned,
    savingsDelta,
    net,
    status: "covered",
    // All labels come from formatKr() so they match what the component
    // actually renders in production (en-US locale → comma separator).
    estimatedSalaryLabel: formatKr(estimatedSalary),
    billsLabel: formatKr(bills),
    budgetLabel: formatKr(budget),
    ccUsageLabel: formatKr(ccUsage),
    estimatedCcBillLabel: formatKr(estimatedCcBill),
    savingsBalanceLabel: formatKr(savingsBalance),
    savingsContributionLabel: formatKr(savingsContribution),
    savingsPlannedLabel: formatKr(savingsPlanned),
    savingsDeltaLabel: formatKr(savingsDelta),
    // F2-UI L2 amendment 2026-08-03: past-only posted-txn bills sum.
    // Default null → row hidden (current/future month).
    realBills: null,
    realBillsLabel: "",
    // F2-UI L2 amendment 2026-08-03: past-only real CC bill.
    // Default null → Real cc bill pair hidden (current/future month).
    realCcBill: null,
    realCcBillLabel: "",
    bar: {
      billsWidth: `${billsZoneW}%`,
      budgetWidth: `${budgetRatio * 100}%`,
      billsFillWidth: `${fillBills}%`,
      billsFillSmall,
      estCcBillWidth: `${estCcShare}%`,
      ccUsageWidth: `${ccUsageShare}%`,
      budgetUsageWidth: `${budgetUsageShare}%`,
      budgetOverspent: ccUsage > budget,
      budgetFillTone,
      savingsPlannedWidth: `${savingsPlanned / Math.max(savingsBalance, 1) * 100}%`,
      savingsDeltaWidth: `${Math.abs(savingsDelta) / Math.max(savingsBalance, 1) * 100}%`,
      savingsDeltaTone,
      salaryWidth: `${salaryShare}%`,
      upperBarWidth: `${outerRatio * 100}%`,
      remainingLabel:
        remaining >= 0
          ? `${formatKr(remaining)} left`
          : `${formatKr(Math.abs(remaining))} short`,
      remainingTone: remaining >= 0 ? "income" : "shortfall",
      netLabel: formatKr(net),
    },
    ...overrides,
  };
}

describe("EconomyBar — bills zone (F2-A)", () => {
  it("renders the small uppercase 'Bills' label", () => {
    render(<EconomyBar economy={makeEconomy({})} />);
    // The label is uppercase via CSS (tracking-wide uppercase), not via
    // text content. Match case-insensitive on the visible text.
    expect(screen.getByText(/^bills$/i)).toBeInTheDocument();
  });

  it("renders the small uppercase 'Estimated cc bill' label", () => {
    render(<EconomyBar economy={makeEconomy({})} />);
    expect(screen.getByText(/estimated cc bill/i)).toBeInTheDocument();
  });

  it("renders the bills value formatted with formatKr (comma separator)", () => {
    render(<EconomyBar economy={makeEconomy({})} />);
    // formatKr(31_500) → "31,500 kr" (en-US locale). The value now
    // appears in two places: the upper-row "Bills" label AND the new
    // "Estimated total bills" badge row. Assert at least one match.
    expect(screen.getAllByText("31,500 kr").length).toBeGreaterThanOrEqual(1);
  });

  it("renders the est. cc bill value formatted with formatKr (comma separator)", () => {
    render(<EconomyBar economy={makeEconomy({})} />);
    // formatKr(14_000) → "14,000 kr". The same number also appears in
    // the budget zone's existing nested meter (out of scope for F2-A),
    // so we assert at least one match exists.
    expect(screen.getAllByText("14,000 kr").length).toBeGreaterThanOrEqual(1);
  });

  it("bills value sits on the red fill (text-shortfall-foreground color)", () => {
    const { container } = render(
      <EconomyBar economy={makeEconomy({})} />,
    );
    // The bills value span has class `text-shortfall-foreground` (no
    // opacity modifier). The small label uses `/80` — filter to exact
    // class match so the modifier suffix doesn't match.
    const billsSpan = Array.from(
      container.querySelectorAll("span"),
    ).find(
      (el) =>
        el.textContent === "31,500 kr" &&
        el.className.split(/\s+/).includes("text-shortfall-foreground"),
    );
    expect(billsSpan).toBeDefined();
  });

  it("est. cc bill value sits in the muted remainder (text-foreground/70 color)", () => {
    const { container } = render(
      <EconomyBar economy={makeEconomy({})} />,
    );
    // The est. cc bill value span uses `text-foreground/70` — the muted
    // token for the right side of the bills zone row.
    const estCcSpan = Array.from(
      container.querySelectorAll("span"),
    ).find(
      (el) =>
        el.textContent === "14,000 kr" &&
        el.className.split(/\s+/).includes("text-foreground/70"),
    );
    expect(estCcSpan).toBeDefined();
  });

  it("renders the capsule top-left Total bills pill", () => {
    render(<EconomyBar economy={makeEconomy({})} />);
    expect(screen.getByText(/^total bills$/i)).toBeInTheDocument();
    // Total bills = bills + estCcBill = 31,500 + 14,000 = 45,500 kr.
    expect(screen.getByText("45,500 kr")).toBeInTheDocument();
  });

  it("applies the bills fill width to the left-to-right red bar", () => {
    const { container } = render(
      <EconomyBar economy={makeEconomy({})} />,
    );
    // The fill bar is the absolute-positioned div with the red shortfall
    // tint and inline width.
    const fill = container.querySelector(
      'div[aria-hidden="true"].bg-shortfall\\/40',
    ) as HTMLElement | null;
    expect(fill).not.toBeNull();
    // Bills fill = bills / totalBills = 31,500 / 45,500 ≈ 69.23%.
    expect(fill?.style.width).toBe("69.23076923076923%");
  });

  it("renders a zero-width fill when bills are zero (no division by zero)", () => {
    const zero = makeEconomy({
      bills: 0,
      billsLabel: formatKr(0),
      bar: {
        billsWidth: "0%",
        budgetWidth: "11.862%",
        billsFillWidth: "0%",
        billsFillSmall: false,
        estCcBillWidth: "70%",
        ccUsageWidth: "0%",
        budgetUsageWidth: "0%",
        budgetOverspent: false,
        budgetFillTone: "income",
        savingsPlannedWidth: "0%",
        savingsDeltaWidth: "0%",
        savingsDeltaTone: "neutral",
        salaryWidth: "100%",
        upperBarWidth: "30%",
        remainingLabel: "44,000 kr left",
        remainingTone: "income",
        netLabel: "44,000 kr",
      },
    });
    const { container } = render(<EconomyBar economy={zero} />);
    const fill = container.querySelector(
      'div[aria-hidden="true"].bg-shortfall\\/40',
    ) as HTMLElement | null;
    expect(fill).not.toBeNull();
    expect(fill?.style.width).toBe("0%");
  });

  it("renders the Real bills + Real cc bill rows only on past months (labels-list branch)", () => {
    // Labels-list branch (billsFillSmall=true) is where past-only
    // actuals live. Build fixture via makeEconomy (which builds the
    // bar from local vars), then override billsFillSmall + add the
    // past-only actuals.
    const base = makeEconomy({
      realBills: 6_500,
      realBillsLabel: formatKr(6_500),
      realCcBill: 7_500,
      realCcBillLabel: formatKr(7_500),
    });
    const past: PartnerEconomy = {
      ...base,
      bar: { ...base.bar, billsFillSmall: true },
    };
    const { rerender } = render(<EconomyBar economy={past} />);
    expect(screen.getByText(/^real bills$/i)).toBeInTheDocument();
    expect(screen.getByText(/^real cc bill$/i)).toBeInTheDocument();
    expect(screen.getByText(/estimated total bills/i)).toBeInTheDocument();

    // Current/future month: both real_* null → both rows hidden.
    const future: PartnerEconomy = {
      ...base,
      realBills: null,
      realBillsLabel: "",
      realCcBill: null,
      realCcBillLabel: "",
      bar: { ...base.bar, billsFillSmall: true },
    };
    rerender(<EconomyBar economy={future} />);
    expect(screen.queryByText(/^real bills$/i)).toBeNull();
    expect(screen.queryByText(/^real cc bill$/i)).toBeNull();
    // Estimated total bills still renders on current/future (always).
    expect(screen.getByText(/estimated total bills/i)).toBeInTheDocument();
  });

  it("clamps fill to 100% when bills exceed estCcBill", () => {
    const overshoot = makeEconomy({
      bills: 50_000,
      billsLabel: formatKr(50_000),
      bar: {
        billsWidth: "90%",
        budgetWidth: "11.862%",
        billsFillWidth: "100%",
        billsFillSmall: false,
        estCcBillWidth: "70%",
        ccUsageWidth: "50%",
        budgetUsageWidth: "50%",
        budgetOverspent: false,
        budgetFillTone: "income",
        savingsPlannedWidth: "0%",
        savingsDeltaWidth: "0%",
        savingsDeltaTone: "neutral",
        salaryWidth: "100%",
        upperBarWidth: "120%",
        remainingLabel: "20,000 kr short",
        remainingTone: "shortfall",
        netLabel: "-20,000 kr",
      },
    });
    const { container } = render(<EconomyBar economy={overshoot} />);
    const fill = container.querySelector(
      'div[aria-hidden="true"].bg-shortfall\\/40',
    ) as HTMLElement | null;
    expect(fill).not.toBeNull();
    expect(fill?.style.width).toBe("100%");
  });
});
