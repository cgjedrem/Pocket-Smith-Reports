// Shared tooltip privacy masking — contracts/privacy-store.md §3.
// The default value formatter in ui/chart.tsx covers every recharts
// tooltip app-wide. Percentage entries (unit "%") stay visible (FR-005).

import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ChartContainer, ChartTooltipContent } from "@/components/ui/chart";
import { setAmountsHidden } from "@/lib/privacy-store";

const CONFIG = {
  amount: { label: "Amount", color: "#1f77b4" },
  pct: { label: "Share", color: "#2ca02c" },
};

function tooltipTree() {
  const payload = [
    { dataKey: "amount", name: "amount", value: 1234, payload: {} },
    // Percentage-valued entry — keyed by unit so FR-005 keeps it visible.
    { dataKey: "pct", name: "pct", value: 65.2, unit: "%", payload: {} },
  ];
  return (
    <ChartContainer config={CONFIG}>
      <ChartTooltipContent active payload={payload as never} />
    </ChartContainer>
  );
}

afterEach(() => {
  setAmountsHidden(false);
});

describe("ChartTooltipContent privacy masking", () => {
  it("shows formatted numbers when visible", () => {
    render(tooltipTree());
    expect(screen.getByText("1,234")).toBeInTheDocument();
    expect(screen.getByText("65.2")).toBeInTheDocument();
  });

  it('masks monetary values when hidden; percentage entry stays visible', () => {
    const { rerender } = render(tooltipTree());
    setAmountsHidden(true);
    rerender(tooltipTree());
    expect(screen.getAllByText("****").length).toBeGreaterThan(0);
    expect(screen.queryByText("1,234")).toBeNull();
    // FR-005 — percentage survives.
    expect(screen.getAllByText("65.2").length).toBe(1);
  });
});
