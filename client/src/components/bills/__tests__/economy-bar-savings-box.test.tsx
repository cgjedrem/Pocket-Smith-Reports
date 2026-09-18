// F2-C — savings box UI tests.
// Pin the F2-C design rules:
//   - Box is flex-1 (~20% of the row), min-w-[10rem]. Full row height
//     via items-stretch on the parent row.
//   - Shows "Savings" label + "Total savings {balance}" value.
//   - Shows a new "Δ savings" label + signed delta value (can be negative).
//   - Delta tone: green when +, red when −, neutral when 0.
//   - Vertical status bar on the left edge of the bottom row,
//     fill = |delta| / balance. Bottom-anchored, fills bottom→top.
//   - Status bar tone matches the delta sign.
//   - The old "+{contribution}" chip is removed.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { PartnerEconomy } from "@/types/api";

import { EconomyBar } from "../EconomyBar";
import { formatKr, formatSignedKr } from "../finance-data";

function makeEconomy(overrides: Partial<PartnerEconomy> = {}): PartnerEconomy {
  // F2-C-aware fixture. We compute everything from the final `savingsDelta`
  // value (post-override) so tests that override the delta see a consistent
  // label + bar state.
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
  const fillBills = (bills / Math.max(totalBills, 1)) * 100;
  const billsFillSmall = totalBills / estimatedSalary < 0.5;
  const estCcShare = (estimatedCcBill / Math.max(budget, 1)) * 100;
  const ccUsageShare = (ccUsage / Math.max(estimatedCcBill, 1)) * 100;
  const budgetUsageShare = (ccUsage / Math.max(budget, 1)) * 100;
  const budgetFillTone: "income" | "warning" | "shortfall" =
    ccUsage > budget
      ? "shortfall"
      : budgetUsageShare > 80
        ? "shortfall"
        : budgetUsageShare > 50
          ? "warning"
          : "income";
  const salaryShare = Math.max(6, (estimatedSalary / Math.max(outflows, 1)) * 100);
  const remaining = estimatedSalary - outflows;

  // Base object.
  const base: PartnerEconomy = {
    partner: { partner_id: "partner_a", partner_slot: "a", label: "Fixture A" },
    estimatedSalary,
    bills,
    budget,
    ccUsage,
    estimatedCcBill,
    realCcBill: null,
    realCcBillLabel: "",
    realBills: null,
    realBillsLabel: "",
    savingsBalance,
    savingsContribution,
    savingsPlanned,
    savingsDelta: 2_000, // default positive mock
    net,
    status: "covered",
    estimatedSalaryLabel: formatKr(estimatedSalary),
    billsLabel: formatKr(bills),
    budgetLabel: formatKr(budget),
    ccUsageLabel: formatKr(ccUsage),
    estimatedCcBillLabel: formatKr(estimatedCcBill),
    savingsBalanceLabel: formatKr(savingsBalance),
    savingsContributionLabel: formatKr(savingsContribution),
    savingsPlannedLabel: "", // computed below
    savingsDeltaLabel: "", // computed below
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
      savingsPlannedWidth: "", // computed below
      savingsDeltaWidth: "",
      savingsDeltaTone: "neutral",
      salaryWidth: `${salaryShare}%`,
      upperBarWidth: `${outerRatio * 100}%`,
      remainingLabel:
        remaining >= 0
          ? `${formatKr(remaining)} left`
          : `${formatKr(Math.abs(remaining))} short`,
      remainingTone: remaining >= 0 ? "income" : "shortfall",
      netLabel: formatKr(net),
    },
  };

  // Apply overrides.
  const final: PartnerEconomy = { ...base, ...overrides };

  // Recompute F2-C derived fields from the final savingsDelta.
  // F2 §13 revised: delta is null on future months → empty label,
  // 0% width, neutral tone. Envelope = planned / balance (both clamp).
  final.savingsDeltaLabel =
    final.savingsDelta != null ? formatSignedKr(final.savingsDelta) : "";
  final.savingsPlannedLabel = formatKr(final.savingsPlanned);
  const fillPct =
    final.savingsDelta == null
      ? 0
      : Math.min(
          100,
          Math.max(0, (Math.abs(final.savingsDelta) / Math.max(final.savingsBalance, 1)) * 100),
        );
  const envelopePct = Math.min(
    100,
    Math.max(0, (final.savingsPlanned / Math.max(final.savingsBalance, 1)) * 100),
  );
  final.bar = {
    ...final.bar,
    savingsPlannedWidth: `${envelopePct}%`,
    savingsDeltaWidth: `${fillPct}%`,
    savingsDeltaTone:
      final.savingsDelta == null
        ? "neutral"
        : final.savingsDelta > 0
          ? "income"
          : final.savingsDelta < 0
            ? "shortfall"
            : "neutral",
  };

  return final;
}

describe("EconomyBar — savings box (F2-C)", () => {
  it("renders the small uppercase 'Savings' label", () => {
    render(<EconomyBar economy={makeEconomy()} />);
    expect(screen.getByText(/^savings$/i)).toBeInTheDocument();
  });

  it("renders the total savings balance value", () => {
    render(<EconomyBar economy={makeEconomy()} />);
    expect(screen.getByText("20,000 kr")).toBeInTheDocument();
  });

  it("renders the 'Δ savings' sub-label", () => {
    render(<EconomyBar economy={makeEconomy()} />);
    expect(screen.getByText(/δ savings|delta savings|Δ savings/i)).toBeInTheDocument();
  });

  it("renders a positive delta with a leading '+' sign", () => {
    render(<EconomyBar economy={makeEconomy({ savingsDelta: 2_000 })} />);
    expect(screen.getByText("+2,000 kr")).toBeInTheDocument();
  });

  it("renders a negative delta without a '+' (formatKr prepends '-')", () => {
    // Use a value that doesn't collide with bar.netLabel (-1,500 default).
    render(<EconomyBar economy={makeEconomy({ savingsDelta: -2_500 })} />);
    expect(screen.getByText("-2,500 kr")).toBeInTheDocument();
  });

  it("tones the positive delta value with text-income", () => {
    const { container } = render(
      <EconomyBar economy={makeEconomy({ savingsDelta: 2_000 })} />,
    );
    const span = Array.from(container.querySelectorAll("span")).find(
      (el) => el.textContent === "+2,000 kr",
    );
    expect(span?.className).toContain("text-income");
  });

  it("tones the negative delta value with text-shortfall", () => {
    const { container } = render(
      <EconomyBar economy={makeEconomy({ savingsDelta: -2_500 })} />,
    );
    const span = Array.from(container.querySelectorAll("span")).find(
      (el) => el.textContent === "-2,500 kr",
    );
    expect(span?.className).toContain("text-shortfall");
  });

  it("renders a neutral tone when delta is 0", () => {
    const { container } = render(
      <EconomyBar economy={makeEconomy({ savingsDelta: 0 })} />,
    );
    const spans = Array.from(container.querySelectorAll("span")).filter(
      (el) => el.textContent === "0 kr",
    );
    const neutral = spans.find((s) =>
      s.className.includes("text-foreground/60"),
    );
    expect(neutral).toBeDefined();
  });

  it("applies the savings delta width to the vertical fill bar", () => {
    const { container } = render(
      <EconomyBar economy={makeEconomy({ savingsDelta: 4_000 })} />,
    );
    // 4000 / 20000 = 20% → pctWidth emits raw float.
    // Fill = the bg-income div inside the savings track (aria-hidden).
    const track = container.querySelector(
      "div[aria-hidden='true'].bg-foreground\\/10",
    );
    const fill = track?.querySelector(
      "div.bg-income",
    ) as HTMLElement | null | undefined;
    expect(fill).not.toBeNull();
    expect(fill?.style.height).toBe("20%");
  });

  it("uses bg-shortfall for the fill bar when delta is negative", () => {
    const { container } = render(
      <EconomyBar economy={makeEconomy({ savingsDelta: -3_500 })} />,
    );
    const track = container.querySelector(
      "div[aria-hidden='true'].bg-foreground\\/10",
    );
    const fill = track?.querySelector("div.bg-shortfall");
    expect(fill).not.toBeNull();
  });

  it("renders transparent fill when delta is 0", () => {
    const { container } = render(
      <EconomyBar economy={makeEconomy({ savingsDelta: 0 })} />,
    );
    const track = container.querySelector(
      "div[aria-hidden='true'].bg-foreground\\/10",
    );
    const fill = track?.querySelector("div.bg-transparent");
    expect(fill).not.toBeNull();
  });

  it("does NOT render the old '+{contribution}' chip", () => {
    // The old chip was "+3,000 kr" (savingsContributionLabel = 3,000).
    // The new default delta is +2,000 kr so we should NOT see +3,000 kr.
    const { container } = render(<EconomyBar economy={makeEconomy()} />);
    const span = Array.from(container.querySelectorAll("span")).find(
      (el) => el.textContent === "+3,000 kr",
    );
    expect(span).toBeUndefined();
  });

  // F2 §13 revised (2026-08-28): savings box = planned envelope +
  // actual fill. Null delta → fill + value hidden, envelope still shown.
  it("renders the planned envelope marker at planned/balance height", () => {
    const { container } = render(
      <EconomyBar economy={makeEconomy()} />,
    );
    // planned 3,000 / balance 20,000 = 15%.
    const envelope = container.querySelector(
      "[data-testid='savings-envelope']",
    ) as HTMLElement | null;
    expect(envelope).not.toBeNull();
    expect(envelope?.style.height).toBe("15%");
  });

  it("renders envelope at 0% when planned is 0 ('no plan known')", () => {
    const { container } = render(
      <EconomyBar economy={makeEconomy({ savingsPlanned: 0 })} />,
    );
    const envelope = container.querySelector(
      "[data-testid='savings-envelope']",
    ) as HTMLElement | null;
    expect(envelope?.style.height).toBe("0%");
  });

  it("hides the fill + Δ value on null delta, keeps envelope + planned label", () => {
    const { container } = render(
      <EconomyBar economy={makeEconomy({ savingsDelta: null })} />,
    );
    const track = container.querySelector(
      "div[aria-hidden='true'].bg-foreground\\/10",
    );
    // Envelope marker still rendered at planned/balance height.
    const envelope = track?.querySelector(
      "[data-testid='savings-envelope']",
    ) as HTMLElement | null | undefined;
    expect(envelope).not.toBeNull();
    expect(envelope?.style.height).toBe("15%");
    // Fill not rendered (only the envelope marker inside the track).
    expect(
      track?.querySelector("div.bg-income, div.bg-shortfall, div.bg-transparent"),
    ).toBeNull();
    // Δ value hidden; planned label shown instead.
    expect(screen.queryByText("+2,000 kr")).toBeNull();
    expect(screen.getByText(/planned 3,000 kr/i)).toBeInTheDocument();
  });
});
