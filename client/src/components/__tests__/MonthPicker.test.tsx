// MonthPicker tests — year range past + future.
//
// Verifies the `futureYears` prop extends the year dropdown past the
// current year (root cause: MonthPicker hardcoded 2020 → current year,
// so SyncPage end-month picker could not target future years).

import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MonthPicker } from "@/components/MonthPicker";

beforeEach(() => {
  // Anchor "today" so the year-range assertions are deterministic.
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-08-03T12:00:00Z"));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("MonthPicker", () => {
  it("renders the current value as the trigger label", () => {
    render(
      <MonthPicker
        label="Start month"
        value="2026-08"
        onChange={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: "2026-08" })).toBeInTheDocument();
  });

  it("year dropdown includes currentYear + futureYears by default (10)", () => {
    // Render with no value so the Year/Month SelectValue placeholders are
    // visible — gives the SelectTriggers a stable accessible name.
    const { container } = render(
      <MonthPicker
        label="End month"
        value=""
        onChange={() => {}}
      />,
    );
    // Open the popover.
    fireEvent.click(screen.getByRole("button", { name: "Pick month" }));

    // The two SelectTriggers are in the portal — query the full document.
    const triggers = container.ownerDocument.querySelectorAll(
      '[data-slot="select-trigger"]',
    );
    expect(triggers.length).toBe(2);

    // Identify the year trigger by its SelectValue text content
    // (Radix renders "Year" / "Month" inside data-slot=select-value).
    const yearTrigger = Array.from(triggers).find(
      (t) =>
        t.querySelector('[data-slot="select-value"]')?.textContent === "Year",
    );
    expect(yearTrigger).toBeDefined();
    fireEvent.click(yearTrigger!);

    // Now the listbox of years is rendered. Default futureYears=10 →
    // 2026 + 10 = up to 2036.
    const listbox = container.ownerDocument.querySelector('[role="listbox"]');
    expect(listbox).not.toBeNull();
    const opts = within(listbox as HTMLElement)
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(opts).toContain("2036");
    expect(opts).toContain("2026");
    expect(opts).toContain("2020");
  });

  it("caps at current year when futureYears=0", () => {
    const { container } = render(
      <MonthPicker
        label="End month"
        value=""
        onChange={() => {}}
        futureYears={0}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Pick month" }));
    const triggers = container.ownerDocument.querySelectorAll(
      '[data-slot="select-trigger"]',
    );
    const yearTrigger = Array.from(triggers).find(
      (t) =>
        t.querySelector('[data-slot="select-value"]')?.textContent === "Year",
    );
    fireEvent.click(yearTrigger!);

    const listbox = container.ownerDocument.querySelector('[role="listbox"]');
    const opts = within(listbox as HTMLElement)
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(opts).not.toContain("2027");
    expect(opts).toContain("2026");
  });

  it("extends past 10 years when futureYears=20", () => {
    const { container } = render(
      <MonthPicker
        label="End month"
        value=""
        onChange={() => {}}
        futureYears={20}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Pick month" }));
    const triggers = container.ownerDocument.querySelectorAll(
      '[data-slot="select-trigger"]',
    );
    const yearTrigger = Array.from(triggers).find(
      (t) =>
        t.querySelector('[data-slot="select-value"]')?.textContent === "Year",
    );
    fireEvent.click(yearTrigger!);

    const listbox = container.ownerDocument.querySelector('[role="listbox"]');
    const opts = within(listbox as HTMLElement)
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(opts).toContain("2046"); // 2026 + 20
    expect(opts).toContain("2036");
  });
});
