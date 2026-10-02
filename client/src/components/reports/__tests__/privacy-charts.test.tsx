// Chart value privacy masking — SC-001 for report charts.
// DonutChart center total + HorizontalBarChart bar values mask when hidden;
// on-chart percentages stay (FR-005), geometry untouched.

import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { setAmountsHidden } from "@/lib/privacy-store";

import { DonutChart } from "../charts/DonutChart";
import { HorizontalBarChart } from "../charts/HorizontalBarChart";

afterEach(() => {
  setAmountsHidden(false);
});

describe("DonutChart privacy masking", () => {
  const data = [
    { label: "Food", value: 750, color: "#1f77b4" },
    { label: "Rent", value: 250, color: "#ff7f0e" },
  ];

  it("shows the computed total when visible", () => {
    render(<DonutChart data={data} />);
    expect(screen.getByText("1,000")).toBeInTheDocument();
  });

  it('masks the center total when hidden; % slice labels stay', () => {
    const { rerender } = render(<DonutChart data={data} />);
    setAmountsHidden(true);
    rerender(<DonutChart data={data} />);
    expect(screen.getAllByText("****").length).toBeGreaterThan(0);
    expect(screen.queryByText("1,000")).toBeNull();
    // FR-005 — proportions remain useful.
    expect(screen.getAllByText("75%").length).toBe(1);
  });
});

describe("HorizontalBarChart privacy masking", () => {
  const data = [
    { label: "Food", value: 750 },
    { label: "Rent", value: 250 },
  ];

  it("shows bar values when visible", () => {
    render(<HorizontalBarChart data={data} />);
    expect(screen.getByText(/750/)).toBeInTheDocument();
  });

  it("masks bar values when hidden; % stays", () => {
    const { rerender } = render(<HorizontalBarChart data={data} />);
    setAmountsHidden(true);
    rerender(<HorizontalBarChart data={data} />);
    expect(screen.queryByText(/750/)).toBeNull();
    const masked = screen.getAllByText(/^\*\*\*\*/);
    expect(masked.length).toBeGreaterThan(0);
    // FR-005 — the share stays readable.
    expect(screen.getAllByText(/\(75\.0%\)/).length).toBe(1);
  });
});
