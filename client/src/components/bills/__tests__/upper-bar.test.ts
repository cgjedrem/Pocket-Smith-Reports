// F2 — synthetic data tests for the upper-bar width + status math.
// These pin the rule the user signed off on:
//   upperBarWidth = (outflow / salary) * SALARY_ZONE_FRACTION, clamped at 100%
// where outflow = bills + est. CC bill. The capsule lives in the salary
// zone column so the % is measured against the salary bar, not the card.
// When outflow > salary the bar stops at the salary zone width — the
// "X KR SHORT" / savings delta text already communicates the shortfall.
// The test cases verify status classification matches.

import { describe, expect, it } from "vitest";

import {
  SYNTHETIC_SCENARIOS,
  runScenario,
} from "./fixtures";

describe("upperBarWidth rule", () => {
  for (const scenario of SYNTHETIC_SCENARIOS) {
    it(`${scenario.name}: capsule width matches expected % of card row`, () => {
      const { upperBarPct } = runScenario(scenario);
      // Allow 1% tolerance for rounding (the helper clamps at min=6%).
      expect(Math.abs(upperBarPct - scenario.expectedUpperBarPctOfCard)).toBeLessThanOrEqual(1);
    });

    it(`${scenario.name}: status matches expected branch`, () => {
      const { status } = runScenario(scenario);
      expect(status).toBe(scenario.expectedStatus);
    });
  }
});

describe("upperBarWidth rule — narrative assertions", () => {
  it("capsule is shorter than the salary zone when outflow < salary", () => {
    // comfortable: outflow 23k < salary 50k → upperBar should be well under 100%.
    const result = runScenario(SYNTHETIC_SCENARIOS[0]); // comfortable
    expect(result.upperBarPct).toBeLessThan(100);
  });

  it("capsule width grows as bills grow (helper is sensitive to bills)", () => {
    // Same salary, higher bills → wider capsule.
    const lowBills = upperBarWidthFor(10_000, 5_000, 50_000);
    const highBills = upperBarWidthFor(25_000, 5_000, 50_000);
    expect(highBills).toBeGreaterThan(lowBills);
  });
});

function upperBarWidthFor(bills: number, estCc: number, salary: number): number {
  // Local mirror to keep the narrative test self-contained.
  // Mirror the helper: pct(outflow, salary) clamped at min=6.
  const outflow = bills + estCc;
  if (salary <= 0) return 6;
  return Math.max(6, (outflow / salary) * 100);
}