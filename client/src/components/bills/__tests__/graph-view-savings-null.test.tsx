// F2 §13 revised — GraphView null savingsDelta handling.
// Pins the PRODUCTION savingsDeltaFill helper (imported from GraphView)
// plus a recharts harness wired to that same helper, driven by the
// ChartRow shape mapToRow produces. jsdom renders bars instantly with
// isAnimationActive={false} (verified — no rAF needed).

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Bar, Cell, ComposedChart } from "recharts";

import { GraphView, savingsDeltaFill } from "../GraphView";
import { formatKr } from "../finance-data";
import type { MonthData, PartnerEconomy } from "@/types/api";

function SavingsDeltaBars({ rows }: { rows: { label: string; savingsDelta: number | null }[] }) {
  // Same JSX shape as GraphView SavingsChart's delta Bar, using the
  // production fill helper.
  return (
    <ComposedChart width={600} height={300} data={rows}>
      <Bar dataKey="savingsDelta" name="Monthly delta" isAnimationActive={false} radius={[3, 3, 0, 0]}>
        {rows.map((row, i) => (
          <Cell key={i} fill={savingsDeltaFill(row.savingsDelta)} />
        ))}
      </Bar>
    </ComposedChart>
  );
}

describe("GraphView — savings null delta (F2 §13)", () => {
  it("maps null delta → transparent cell, real delta → income cell", () => {
    const { container } = render(
      <SavingsDeltaBars
        rows={[
          { label: "July 2026", savingsDelta: 2_000 },
          { label: "September 2026", savingsDelta: null },
        ]}
      />,
    );
    // Delta bars = rects named "Monthly delta". Null point skipped by
    // recharts → only the real delta bar renders, income green.
    const rects = Array.from(
      container.querySelectorAll("path.recharts-rectangle"),
    );
    const fills = rects.map((r) => r.getAttribute("fill"));
    expect(fills).toContain("hsl(142 52% 36%)");
    // Exactly one delta rect (null month skipped), and no green bar
    // was painted for the null value (old `null >= 0` bug).
    expect(fills.filter((f) => f === "hsl(142 52% 36%)")).toHaveLength(1);
  });

  it("production fill helper: null → transparent, + → income, − → shortfall", () => {
    expect(savingsDeltaFill(null)).toBe("transparent");
    expect(savingsDeltaFill(2_000)).toBe("hsl(142 52% 36%)");
    expect(savingsDeltaFill(-500)).toBe("hsl(0 72% 51%)");
  });

  it("renders the full GraphView with a null-delta month (smoke)", async () => {
    const source = await import("@/lib/bills-source");
    source.hydrate(
      [makeMonth("2026-07", "July 2026", 2_000), makeMonth("2026-09", "September 2026", null)],
      [],
    );
    const { container } = render(<GraphView />);
    const headings = Array.from(container.querySelectorAll("h3")).map((h) => h.textContent);
    expect(headings).toContain("Savings balance");
    source.reset();
  });
});

function makePartner(over: Partial<PartnerEconomy> = {}): PartnerEconomy {
  return {
    partner: { partner_id: "partner_a", partner_slot: "a", label: "Fixture A" },
    estimatedSalary: 44_000,
    bills: 15_500,
    budget: 23_000,
    ccUsage: 12_000,
    estimatedCcBill: 9_800,
    realCcBill: null,
    realCcBillLabel: "",
    realBills: null,
    realBillsLabel: "",
    savingsBalance: 32_000,
    savingsContribution: 5_000,
    savingsPlanned: 3_000,
    savingsDelta: 2_000,
    net: 16_700,
    status: "covered",
    estimatedSalaryLabel: formatKr(44_000),
    billsLabel: formatKr(15_500),
    budgetLabel: formatKr(23_000),
    ccUsageLabel: formatKr(12_000),
    estimatedCcBillLabel: formatKr(9_800),
    savingsBalanceLabel: formatKr(32_000),
    savingsContributionLabel: formatKr(5_000),
    savingsPlannedLabel: formatKr(3_000),
    savingsDeltaLabel: "+2,000 kr",
    bar: {
      billsWidth: "50%",
      budgetWidth: "11.862%",
      billsFillWidth: "60%",
      billsFillSmall: false,
      estCcBillWidth: "40%",
      ccUsageWidth: "40%",
      budgetUsageWidth: "18%",
      budgetOverspent: false,
      budgetFillTone: "income",
      savingsPlannedWidth: "9.375%",
      savingsDeltaWidth: "6.25%",
      savingsDeltaTone: "income",
      salaryWidth: "100%",
      upperBarWidth: "50%",
      remainingLabel: "18,700 kr left",
      remainingTone: "income",
      netLabel: formatKr(16_700),
    },
    ...over,
  };
}

function makeMonth(key: string, label: string, savingsDelta: number | null): MonthData {
  return {
    key,
    label,
    year: 2026,
    monthIndex: 6,
    events: [],
    billsCount: 0,
    buysCount: 0,
    net: 16_700,
    partners: [makePartner({ savingsDelta })],
  };
}


