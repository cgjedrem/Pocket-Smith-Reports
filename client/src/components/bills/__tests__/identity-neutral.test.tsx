// US2 / T049 — schema-4 rows (partner_id "") render identity-neutral:
// partner filter hidden, re-sync hint, neutral dots, no inferred grouping.
// Identity-mode rows get the slot-ordered filter back.

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { FinanceEvent } from "@/types/api";

import { IDENTITY_NEUTRAL_HINT } from "../finance-data";
import { TableView } from "../TableView";

vi.mock("@/hooks/useBillsSourceSubscription", () => ({
  useBillsSourceSubscription: () => 0,
}));

type Row = FinanceEvent & { monthLabel: string };

function mkRow(over: Partial<Row> & { title: string }): Row {
  return {
    id: over.title,
    date: "2026-07-03",
    day: 3,
    type: "bill",
    account: "Example Joint",
    partner: { partner_id: "", partner_slot: "", label: "Fixture A" },
    amount: -100,
    monthLabel: "July 2026",
    ...over,
  };
}

// Legacy schema-4 rows — no semantic ids, labels kept for display.
const LEGACY_ROWS: Row[] = [
  mkRow({
    title: "Rent",
    partner: { partner_id: "", partner_slot: "", label: "Fixture A" },
  }),
  mkRow({
    title: "Salary",
    type: "salary",
    amount: 42_000,
    partner: { partner_id: "", partner_slot: "", label: "Fixture B" },
  }),
];

const IDENTITY_ROWS: Row[] = [
  mkRow({
    title: "Rent",
    partner: { partner_id: "partner_a", partner_slot: "a", label: "Fixture A" },
  }),
  mkRow({
    title: "Salary",
    type: "salary",
    amount: 42_000,
    partner: { partner_id: "partner_b", partner_slot: "b", label: "Fixture B" },
  }),
];

let rows: Row[] = LEGACY_ROWS;
vi.mock("@/lib/bills-source", () => ({
  getAllEvents: () => rows,
  getMonths: () => [],
}));

describe("TableView — identity-neutral mode (schema-4 rows)", () => {
  it("hides the partner filter and shows the re-sync hint", () => {
    rows = LEGACY_ROWS;
    render(<TableView />);

    // No partner select — no positional inference from legacy payloads.
    expect(screen.queryByRole("combobox", { name: "Partner" })).toBeNull();
    // Other filters stay.
    expect(screen.getByRole("combobox", { name: "Type" })).toBeInTheDocument();
    // Hint tells the user how to restore the identity view.
    expect(screen.getByRole("note")).toHaveTextContent(IDENTITY_NEUTRAL_HINT);
  });

  it("renders rows with neutral dots and display labels — no partner accents", () => {
    rows = LEGACY_ROWS;
    const { container } = render(<TableView />);

    expect(screen.getByText("Rent")).toBeInTheDocument();
    expect(screen.getByText("Salary")).toBeInTheDocument();
    // Labels still display (they are attached to their own rows).
    expect(screen.getByText("Fixture A")).toBeInTheDocument();
    expect(screen.getByText("Fixture B")).toBeInTheDocument();
    // No partner accent classes anywhere; dots are the neutral tone.
    expect(container.querySelectorAll('[class*="bg-partner-"]').length).toBe(0);
    expect(
      container.querySelectorAll(".bg-muted-foreground").length,
    ).toBeGreaterThanOrEqual(2);
  });
});

describe("TableView — identity mode (schema-5 rows)", () => {
  it("shows the partner filter keyed by partner_id in slot order", () => {
    rows = IDENTITY_ROWS;
    render(<TableView />);

    expect(screen.queryByRole("note")).toBeNull();
    const select = screen.getByRole("combobox", { name: "Partner" });
    const options = Array.from(select.querySelectorAll("option")).map((o) => ({
      value: o.value,
      label: o.textContent,
    }));
    expect(options).toEqual([
      { value: "all", label: "All partners" },
      // Slot order a → b; filter values are ids, labels are display text.
      { value: "partner_a", label: "Fixture A" },
      { value: "partner_b", label: "Fixture B" },
    ]);
  });
});
