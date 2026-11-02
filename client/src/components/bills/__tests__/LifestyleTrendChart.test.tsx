import { act, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { LifestyleTrendChart, trendMonthTick } from "../LifestyleTrendChart";
import { setAmountsHidden } from "@/lib/privacy-store";

function show(entries: Array<[string, string]>, target = entries.at(-1)![0]) {
  return render(
    <LifestyleTrendChart
      samples={entries.map(([month, amount]) => ({ month, amount }))}
      comparison={{ month: target }}
      categoryLabel="Category A (ID 910001)"
    />,
  );
}
function figure() {
  return screen.getByRole("figure", { name: /Monthly usage over the selected evidence period/ });
}
function markers(container: HTMLElement, kind: string) {
  return Array.from(container.querySelectorAll(`[data-trend-marker="${kind}"]`));
}

beforeEach(() => setAmountsHidden(false));
afterEach(() => setAmountsHidden(false));

describe("LifestyleTrendChart", () => {
  it("draws usage and a distinct trailing average with non-color above/target markers and a text alternative", () => {
    const { container } = show([["2026-07", "100"], ["2026-08", "100"], ["2026-09", "130"], ["2026-10", "140"]]);
    const chart = figure();
    expect(chart).toHaveAttribute("data-lifestyle-trend", "chart");
    expect(container.querySelector("svg.recharts-surface")).not.toBeNull();
    expect(container.querySelectorAll(".recharts-line")).toHaveLength(2);
    expect(container.querySelector('.recharts-line-curve[stroke-dasharray="6 4"]')).not.toBeNull();
    expect(markers(container, "above").map((node) => node.closest("[data-trend-month]")!.getAttribute("data-trend-month")))
      .toEqual(["2026-09", "2026-10"]);
    expect(markers(container, "usage")).toHaveLength(2);
    expect(markers(container, "average")).toHaveLength(2);
    expect(markers(container, "target")).toHaveLength(1);
    expect(markers(container, "target")[0].closest("[data-trend-month]")).toHaveAttribute("data-trend-month", "2026-10");
    // jsdom does not lay out tick text; ticks are verified in the synthetic browser check.
    expect(container.querySelectorAll(".recharts-xAxis .recharts-cartesian-axis-tick")).toHaveLength(4);
    expect(trendMonthTick("2026-10")).toBe("2026-10");
    expect(chart).toHaveTextContent("2 of 4 months above their trailing average: 2026-09, 2026-10.");
    const legend = within(chart).getByRole("list", { name: "Graph legend" });
    expect(within(legend).getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      "Solid line with dots: monthly net usage",
      "Dashed line with bars: Trailing average (up to 3 prior months)",
      "Triangle: month above its trailing average",
      "Square outline: selected target month",
    ]);
    expect(chart).toHaveTextContent(/not the applied threshold or the reference-period verdict/);
    expect(chart).toHaveTextContent(/starts once 2 prior months exist \(first: 2026-09\)/);
    const table = within(chart).getByRole("table", { name: "Category A (ID 910001) graph data" });
    const rows = within(table).getAllByRole("row").slice(1).map((row) => row.textContent);
    expect(rows).toEqual([
      "2026-07100 krNot shownNo trailing average — fewer than 2 consecutive prior months in this evidence",
      "2026-08100 krNot shownNo trailing average — fewer than 2 consecutive prior months in this evidence",
      "2026-09130 kr100 kr (2026-07, 2026-08)Above trailing average (▲)",
      "2026-10 (selected target)140 kr110 kr (2026-07, 2026-08, 2026-09)Above trailing average (▲)",
    ]);
  });

  it("explains a target gap, breaks the lines and shows no misleading target average", () => {
    const { container } = show([["2026-01", "10"], ["2026-02", "10"], ["2026-03", "10"], ["2026-06", "500"]]);
    const chart = figure();
    expect(chart).toHaveTextContent(/2 calendar months between 2026-03 and 2026-06 are not in the selected evidence: the lines break there \(not zero\)/);
    expect(chart).toHaveTextContent("No month is above its trailing average.");
    expect(markers(container, "above")).toHaveLength(0);
    expect(markers(container, "average")).toHaveLength(1);
    expect(container.querySelectorAll(".recharts-xAxis .recharts-cartesian-axis-tick")).toHaveLength(5);
    expect(trendMonthTick("gap:2026-03:2026-06")).toBe("…");
    const usagePath = container.querySelectorAll(".recharts-line-curve")[0].getAttribute("d")!;
    expect(usagePath.match(/M/g)).toHaveLength(2);
    expect(within(chart).getByRole("row", { name: /2026-06 \(selected target\)/ })).toHaveTextContent("Not shown");
  });

  it("plots negative and zero net usage with a zero reference line", () => {
    const { container } = show([["2026-07", "-50"], ["2026-08", "0"], ["2026-09", "-10"]]);
    expect(figure()).toHaveTextContent("Values below zero are net refunds; they are plotted as-is.");
    expect(container.querySelector(".recharts-reference-line")).not.toBeNull();
    expect(markers(container, "above")).toHaveLength(1);
    expect(within(figure()).getByRole("row", { name: /2026-09/ })).toHaveTextContent("-25 kr");
  });

  it("fails visibly for unplottable or invalid amounts instead of drawing zero or Infinity", () => {
    const { container, unmount } = show([["2026-07", "90071992547409920"], ["2026-08", "90071992547409920"], ["2026-09", "90071992547409921"]]);
    expect(figure()).toHaveAttribute("data-lifestyle-trend", "unplottable");
    expect(screen.getByRole("status")).toHaveTextContent(/too large or too precise to plot/);
    expect(container.querySelector("svg.recharts-surface")).toBeNull();
    expect(within(figure()).getByRole("row", { name: /2026-09/ })).toHaveTextContent("Above trailing average");
    unmount();
    show([["2026-07", "Infinity"]]);
    expect(figure()).toHaveAttribute("data-lifestyle-trend", "invalid");
    expect(screen.getByRole("status")).toHaveTextContent("Graph unavailable: The 2026-07 amount is not an exact decimal.");
  });

  it("replaces the chart with a masked placeholder while amounts are hidden and restores it", () => {
    const { container } = show([["2026-07", "100"], ["2026-08", "100"], ["2026-09", "130"], ["2026-10", "140"]]);
    act(() => setAmountsHidden(true));
    const chart = figure();
    expect(chart).toHaveAttribute("data-lifestyle-trend", "masked");
    expect(container.querySelector("svg.recharts-surface")).toBeNull();
    expect(container.querySelector("[data-trend-marker]")).toBeNull();
    expect(screen.getByRole("img", { name: "Category A (ID 910001) monthly usage graph hidden while amounts are hidden" })).toBeInTheDocument();
    expect(container.innerHTML).not.toMatch(/ kr|\b1[034]0\b|110/);
    expect(chart).toHaveTextContent("2 of 4 months above their trailing average: 2026-09, 2026-10.");
    expect(chart.textContent!.match(/\*\*\*\*/g)).toHaveLength(6);
    act(() => setAmountsHidden(false));
    expect(container.querySelector("svg.recharts-surface")).not.toBeNull();
    expect(container.innerHTML).toContain("140 kr");
  });
});
