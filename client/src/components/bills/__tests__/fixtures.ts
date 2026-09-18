// F2 — synthetic PartnerEconomy fixtures for unit tests.
// Each scenario covers one branch of the upper-bar / status math so the
// rules can be asserted without depending on the random mock data.

import type { PartnerEconomy } from "@/types/api";

import { getEconomyStatus, upperBarWidth } from "../finance-data";

export interface SyntheticScenario {
  name: string;
  bills: number;
  estimatedCcBill: number;
  salary: number;
  savings: number;
  // Expected status + upper-bar width % of the partner-card row.
  expectedStatus: PartnerEconomy["status"];
  /**
   * upperBarWidth returns the % of the partner-card row the capsule should
   * occupy. The capsule is sized against the salary zone (~65.9% of card
   * row). Capsule is clamped at the salary zone width when outflow > salary
   * — the "X KR SHORT" / savings delta text communicates the shortfall,
   * not the bar width.
   */
  expectedUpperBarPctOfCard: number;
}

export const SYNTHETIC_SCENARIOS: SyntheticScenario[] = [
  {
    // Salary easily absorbs bills + est CC. Savings untouched.
    name: "comfortable",
    bills: 15_000,
    estimatedCcBill: 8_000,
    salary: 50_000,
    savings: 30_000,
    expectedStatus: "covered",
    // outflow 23k vs salary 50k = 46% × 0.659 = 30% of partner card row
    expectedUpperBarPctOfCard: 30,
  },
  {
    // Bills + est CC exactly equal to salary. Tight but covered.
    name: "exact",
    bills: 22_000,
    estimatedCcBill: 13_000,
    salary: 35_000,
    savings: 8_000,
    expectedStatus: "covered",
    // outflow 35k vs salary 35k = 100% × 0.659 = 66% (capsule at salary zone)
    expectedUpperBarPctOfCard: 66,
  },
  {
    // Salary alone can't cover; savings covers the rest. Partial.
    name: "partial",
    bills: 18_000,
    estimatedCcBill: 14_000,
    salary: 25_000,
    savings: 12_000,
    expectedStatus: "partial",
    // outflow 32k vs salary 25k = 128% → clamped at 100% × 0.659 = 66%
    expectedUpperBarPctOfCard: 66,
  },
  {
    // Salary + savings both fall short. Upper bar clamped at salary zone.
    name: "shortfall",
    bills: 22_000,
    estimatedCcBill: 14_000,
    salary: 25_000,
    savings: 4_000,
    expectedStatus: "shortfall",
    // outflow 36k vs salary 25k = 144% → clamped at 100% × 0.659 = 66%
    expectedUpperBarPctOfCard: 66,
  },
  {
    // No savings at all. Pure salary-vs-outflow test.
    name: "zero_savings",
    bills: 12_000,
    estimatedCcBill: 6_000,
    salary: 40_000,
    savings: 0,
    expectedStatus: "covered",
    // outflow 18k vs salary 40k = 45% × 0.659 = 30% (well inside salary zone)
    expectedUpperBarPctOfCard: 30,
  },
  {
    // Salary really small, bills huge. Savings carry the difference. Partial.
    name: "extreme_shortfall",
    bills: 28_000,
    estimatedCcBill: 5_000,
    salary: 20_000,
    savings: 50_000,
    expectedStatus: "partial",
    // outflow 33k vs salary 20k = 165% → clamped at 100% × 0.659 = 66%
    expectedUpperBarPctOfCard: 66,
  },
];

/** Run a scenario through the same helpers the component uses. */
export function runScenario(s: SyntheticScenario) {
  const status = getEconomyStatus(
    s.salary,
    s.bills,
    s.estimatedCcBill,
    s.savings,
  );
  const upperBar = upperBarWidth(s.bills, s.estimatedCcBill, s.salary);
  const upperBarPct = Number(upperBar.replace("%", ""));
  return { status, upperBar, upperBarPct };
}
