import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { HorizontalBarChart } from "@/components/reports/charts/HorizontalBarChart";

describe("HorizontalBarChart", () => {
  it("reserves space for long labels and uses readable bar dimensions", () => {
    const fullLabel = "Student Loan (Fixture A)";
    const { container } = render(
      <HorizontalBarChart
        data={[{ label: fullLabel, value: 1200 }]}
      />
    );

    const chart = container.querySelector("svg");
    const label = container.querySelector('g > text[text-anchor="end"]');
    const track = container.querySelector("rect");

    expect(chart).toHaveAttribute("viewBox", "0 0 680 48");
    expect(chart).toHaveAttribute("preserveAspectRatio", "xMidYMid meet");
    expect(label).not.toBeNull();
    expect(label).toHaveAttribute("x", "214");
    expect(label).toHaveTextContent(fullLabel);
    expect(label).not.toHaveAttribute("textLength");
    expect(label).toHaveAttribute("font-size", "12");
    expect(track).toHaveAttribute("x", "220");
    expect(track).toHaveAttribute("width", "328");
    expect(track).toHaveAttribute("height", "22");
  });

  it("renders the full label without truncation when overlong", () => {
    const fullLabel = "Long category label that cannot fit in the chart reserve";
    const { container } = render(
      <HorizontalBarChart data={[{ label: fullLabel, value: 1200 }]} />
    );

    const label = container.querySelector('g > text[text-anchor="end"]');
    expect(label).not.toBeNull();
    expect(label).toHaveAttribute("x", "214");
    expect(label).toHaveTextContent(fullLabel);
    expect(label).not.toHaveAttribute("textLength");
    expect(label).not.toHaveAttribute("lengthAdjust");
    const group = label.closest("g");
    expect(group).toHaveAttribute("aria-label", fullLabel);
    expect(group?.querySelector("title")).toHaveTextContent(fullLabel);
  });

  it("shrinks the label font when the longest label exceeds the reserve", () => {
    const longLabel = "Transportation and Utilities (Personal, Fixture A, Fixture B)";
    const data = [
      { label: longLabel, value: 500 },
      { label: "Hello Fresh", value: 1159 },
    ];
    const { container } = render(<HorizontalBarChart data={data} />);

    const labels = Array.from(
      container.querySelectorAll('g > text[text-anchor="end"]')
    );
    expect(labels.length).toBe(2);
    for (const label of labels) {
      expect(label).toHaveAttribute("font-size", "10");
    }
  });

  it("centers the zero-total SVG with the populated chart responsive layout", () => {
    const { container } = render(
      <HorizontalBarChart data={[{ label: "Empty category", value: 0 }]} />
    );

    const chart = container.querySelector("svg");

    expect(chart).toHaveAttribute("viewBox", "0 0 680 90");
    expect(chart).toHaveAttribute("height", "90");
    expect(chart).toHaveAttribute("preserveAspectRatio", "xMidYMid meet");
    expect(chart).toHaveStyle({ display: "block", margin: "0 auto" });
  });
});