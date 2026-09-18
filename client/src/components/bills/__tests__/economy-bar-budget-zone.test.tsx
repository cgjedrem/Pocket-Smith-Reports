// F2-B — budget zone UI tests.
// Pin the F2-B design rules:
//   - Budget zone shows a vertical fill bar growing bottom→top.
//   - Fill width = ccUsage / budget, clamped [0, 100].
//   - Fill uses linear-gradient(to top, var(--income), var(--savings)).
//   - When ccUsage > budget the fill is solid var(--shortfall) and
//     the whole zone background is bg-shortfall/15.
//   - Two values rendered: "Budget" (envelope) and "CC usage" (fill
//     driver). The "Budget + CC buys" full label was dropped because
//     the zone is now 18% wide (11.862% of row) and can't fit the text.

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
  const net = estimatedSalary - bills - estimatedCcBill;

  const totalBills = bills + estimatedCcBill;
  const outflows = totalBills;
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
  const billsFillSmall = totalBills / estimatedSalary < 0.5;
  const estCcShare = Math.min(
    100,
    Math.max(0, (estimatedCcBill / Math.max(budget, 1)) * 100),
  );
  const ccUsageShare = Math.min(
    100,
    Math.max(0, (ccUsage / Math.max(estimatedCcBill, 1)) * 100),
  );
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
  // F2-C: random mock delta — deterministic +2,000 for stable tests.
  const savingsDelta = 2_000;
  const savingsDeltaTone: "income" | "shortfall" | "neutral" =
    savingsDelta > 0 ? "income" : "shortfall";
  const savingsDeltaWidth = `${(Math.abs(savingsDelta) / Math.max(savingsBalance, 1)) * 100}%`;
  const savingsPlannedWidth = `${(savingsPlanned / Math.max(savingsBalance, 1)) * 100}%`;
  const salaryShare = Math.min(
    100,
    Math.max(6, (estimatedSalary / Math.max(outflows, 1)) * 100),
  );
  const remaining = estimatedSalary - outflows;

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
    estimatedSalaryLabel: formatKr(estimatedSalary),
    billsLabel: formatKr(bills),
    budgetLabel: formatKr(budget),
    ccUsageLabel: formatKr(ccUsage),
    estimatedCcBillLabel: formatKr(estimatedCcBill),
    savingsBalanceLabel: formatKr(savingsBalance),
    savingsContributionLabel: formatKr(savingsContribution),
    savingsPlannedLabel: formatKr(savingsPlanned),
    savingsDeltaLabel: formatKr(savingsDelta),
    // F2-UI L2 amendment 2026-08-03: past-only planned-vs-actual gate.
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
      savingsPlannedWidth,
      savingsDeltaWidth,
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

describe("EconomyBar — budget zone (F2-B)", () => {
  it("renders the 'Budget' label", () => {
    render(<EconomyBar economy={makeEconomy({})} />);
    expect(screen.getByText(/^budget$/i)).toBeInTheDocument();
  });

  it("renders the 'CC usage' label", () => {
    render(<EconomyBar economy={makeEconomy({})} />);
    expect(screen.getByText(/cc usage/i)).toBeInTheDocument();
  });

  it("renders the budget value with formatKr (comma)", () => {
    render(<EconomyBar economy={makeEconomy({})} />);
    expect(screen.getByText("17,250 kr")).toBeInTheDocument();
  });

  it("renders the cc usage value with formatKr (comma)", () => {
    render(<EconomyBar economy={makeEconomy({})} />);
    expect(screen.getByText("7,000 kr")).toBeInTheDocument();
  });

  it("does NOT render the old 'Est. CC bill' sub-label inside the budget zone", () => {
    // The 'Est. CC bill' header was part of the old nested dashed meter
    // and is now removed from the budget zone. The value may still
    // appear in the bills zone (Step A) and the Total pill, so we only
    // assert the LABEL string is gone.
    render(<EconomyBar economy={makeEconomy({})} />);
    expect(screen.queryByText(/^est\.?\s*cc bill$/i)).toBeNull();
  });

  it("applies the budget usage height to the vertical fill bar", () => {
    const { container } = render(<EconomyBar economy={makeEconomy({})} />);
    // The fill bar is the absolute-positioned, bottom-anchored div
    // with a `style.height` matching budgetUsageWidth.
    const fills = container.querySelectorAll("div[style*='height:']");
    // Filter to the one whose parent is the bottom-anchor wrapper (no
    // other inline-height divs exist after F2-B).
    const fill = Array.from(fills).find(
      (el) => (el as HTMLElement).style.height !== "",
    ) as HTMLElement | undefined;
    expect(fill).toBeDefined();
    // 7,000 / 17,250 ≈ 40.58% → pctWidth emits raw float. Floating-point
    // precision varies; the value matches what finance-data.ts emits.
    expect(fill?.style.height).toBe("40.57971014492754%");
  });

  it("uses bg-income class when usage is below 50% (green bucket)", () => {
    const { container } = render(<EconomyBar economy={makeEconomy({})} />);
    // 7000/17250 ≈ 40% → income bucket.
    const fill = container.querySelector(
      "div.absolute.inset-x-0.bottom-0.rounded-t-md.bg-income",
    );
    expect(fill).not.toBeNull();
  });

  it("renders the 'CC usage' label inside the fill wrapper (overlay)", () => {
    // F2-B refinement: the label + value are anchored to the bottom
    // of the fill wrapper, so they always sit at the baseline of the
    // fill region. Verify the label is still findable in the DOM.
    render(<EconomyBar economy={makeEconomy({})} />);
    expect(screen.getByText(/cc usage/i)).toBeInTheDocument();
  });

  it("uses bg-warning class when usage is between 50% and 80% (yellow bucket)", () => {
    const mid = makeEconomy({
      ccUsage: 12_000, // 12k / 17.25k = 69.6% → warning bucket
      ccUsageLabel: formatKr(12_000),
      bar: {
        billsWidth: "60%",
        budgetWidth: "11.862%",
        billsFillWidth: "69%",
        billsFillSmall: false,
        estCcBillWidth: "70%",
        ccUsageWidth: "50%",
        budgetUsageWidth: "70%",
        budgetOverspent: false,
        budgetFillTone: "warning",
        savingsPlannedWidth: "15%",
        savingsDeltaWidth: "10%",
        savingsDeltaTone: "income",
        salaryWidth: "100%",
        upperBarWidth: "60%",
        remainingLabel: "1,500 kr short",
        remainingTone: "shortfall",
        netLabel: "-1,500 kr",
      },
    });
    const { container } = render(<EconomyBar economy={mid} />);
    const fill = container.querySelector(
      "div.absolute.inset-x-0.bottom-0.rounded-t-md.bg-warning",
    );
    expect(fill).not.toBeNull();
  });

  it("uses bg-shortfall class when usage is above 80% (red bucket)", () => {
    const high = makeEconomy({
      ccUsage: 15_000, // 15k / 17.25k = 86.9% → shortfall bucket
      ccUsageLabel: formatKr(15_000),
      bar: {
        billsWidth: "60%",
        budgetWidth: "11.862%",
        billsFillWidth: "69%",
        billsFillSmall: false,
        estCcBillWidth: "70%",
        ccUsageWidth: "50%",
        budgetUsageWidth: "87%",
        budgetOverspent: false,
        budgetFillTone: "shortfall",
        savingsPlannedWidth: "15%",
        savingsDeltaWidth: "10%",
        savingsDeltaTone: "income",
        salaryWidth: "100%",
        upperBarWidth: "60%",
        remainingLabel: "1,500 kr short",
        remainingTone: "shortfall",
        netLabel: "-1,500 kr",
      },
    });
    const { container } = render(<EconomyBar economy={high} />);
    const fill = container.querySelector(
      "div.absolute.inset-x-0.bottom-0.rounded-t-md.bg-shortfall",
    );
    expect(fill).not.toBeNull();
  });

  it("uses bg-shortfall fill + zone tint when overspent", () => {
    const overspent = makeEconomy({
      ccUsage: 25_000, // > budget 17,250
      ccUsageLabel: formatKr(25_000),
      bar: {
        billsWidth: "60%",
        budgetWidth: "11.862%",
        billsFillWidth: "69%",
        billsFillSmall: false,
        estCcBillWidth: "70%",
        ccUsageWidth: "100%",
        budgetUsageWidth: "100%",
        budgetOverspent: true,
        budgetFillTone: "shortfall",
        savingsPlannedWidth: "15%",
        savingsDeltaWidth: "10%",
        savingsDeltaTone: "income",
        salaryWidth: "100%",
        upperBarWidth: "60%",
        remainingLabel: "1,500 kr short",
        remainingTone: "shortfall",
        netLabel: "-1,500 kr",
      },
    });
    const { container } = render(<EconomyBar economy={overspent} />);
    // Zone should have the red overspent tint class.
    const zone = container.querySelector(".bg-shortfall\\/15");
    expect(zone).not.toBeNull();
    // Fill should also be bg-shortfall (red, no warning/income).
    const fill = container.querySelector(
      "div.absolute.inset-x-0.bottom-0.rounded-t-md.bg-shortfall",
    );
    expect(fill).not.toBeNull();
  });

  it("renders a zero-height fill when ccUsage is zero (no division by zero)", () => {
    const zero = makeEconomy({
      ccUsage: 0,
      ccUsageLabel: formatKr(0),
      bar: {
        billsWidth: "60%",
        budgetWidth: "11.862%",
        billsFillWidth: "69%",
        billsFillSmall: false,
        estCcBillWidth: "70%",
        ccUsageWidth: "0%",
        budgetUsageWidth: "0%",
        budgetOverspent: false,
        budgetFillTone: "income",
        savingsPlannedWidth: "15%",
        savingsDeltaWidth: "10%",
        savingsDeltaTone: "income",
        salaryWidth: "100%",
        upperBarWidth: "60%",
        remainingLabel: "1,500 kr short",
        remainingTone: "shortfall",
        netLabel: "-1,500 kr",
      },
    });
    const { container } = render(<EconomyBar economy={zero} />);
    const fills = Array.from(
      container.querySelectorAll("div[style*='height:']"),
    ) as HTMLElement[];
    const fill = fills.find((el) => el.style.height === "0%");
    expect(fill).toBeDefined();
  });

  it("hides the entire budget zone when budget is null (F2 §8 last sync-window month)", () => {
    // BE everyday_budget === null → zone renders nothing. Same
    // null-gate pattern as realBills. Savings box must stay.
    const noBudget = makeEconomy({ budget: null, budgetLabel: "" });
    render(<EconomyBar economy={noBudget} />);
    expect(screen.queryByText(/^budget$/i)).toBeNull();
    // CC usage label lives inside the budget zone → gone with it.
    expect(screen.queryByText(/cc usage/i)).toBeNull();
    // Rest of the card survives (savings box renders its value).
    expect(screen.getByText(formatKr(20_000))).toBeInTheDocument();
  });

  it("hides the Budget row in the labels-list branch when budget is null", () => {
    // billsFillSmall → labels list; null budget → Budget row skipped,
    // CC usage row (a labels-list row, not the zone overlay) stays.
    const smallNoBudget = makeEconomy({ budget: null, budgetLabel: "" });
    smallNoBudget.bar = { ...smallNoBudget.bar, billsFillSmall: true };
    render(<EconomyBar economy={smallNoBudget} />);
    expect(screen.queryByText(/^budget$/i)).toBeNull();
    expect(screen.getByText(/cc usage/i)).toBeInTheDocument();
  });
});
