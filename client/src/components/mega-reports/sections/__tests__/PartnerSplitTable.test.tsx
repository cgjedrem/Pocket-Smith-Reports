// PartnerSplitTable privacy masking — SC-001.
// Hidden → all currency cells "****"; month rows, partner labels, and
// share percentages unchanged (FR-005).

import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { setAmountsHidden } from "@/lib/privacy-store";

import { PartnerSplitTable } from "../PartnerSplitTable";
import type { PartnerSplitRow } from "../PartnerSplitTable";

const ROWS: PartnerSplitRow[] = [
  { month: "26/01", partnerA: 1234.5, partnerB: 2000, total: 3234.5 },
  { month: "26/02", partnerA: -500.25, partnerB: 750, total: 249.75 },
];

function renderTable() {
  return render(
    <PartnerSplitTable
      aLabel="Alex"
      bLabel="Sam"
      rows={ROWS}
      showShare="home"
      footerLabel="Cumulative"
    />,
  );
}

afterEach(() => {
  setAmountsHidden(false);
});

describe("PartnerSplitTable privacy masking", () => {
  it("shows nb-NO figures when visible", () => {
    renderTable();
    expect(screen.getByText("1 234,50")).toBeInTheDocument();
    expect(screen.getByText("2 000,00")).toBeInTheDocument();
  });

  it("masks all currency cells when hidden; labels + shares unchanged", () => {
    const { container, rerender } = renderTable();
    // Share percentages visible baseline.
    const pctBefore = screen.getAllByText(/%$/).map((c) => c.textContent);

    setAmountsHidden(true);
    rerender(
      <PartnerSplitTable
        aLabel="Alex"
        bLabel="Sam"
        rows={ROWS}
        showShare="home"
        footerLabel="Cumulative"
      />,
    );

    // No figure survives.
    expect(screen.queryByText("1 234,50")).toBeNull();
    expect(screen.queryByText(/2 000,00/)).toBeNull();

    // Row labels + partner labels unchanged.
    expect(screen.getByText("26/01")).toBeInTheDocument();
    expect(screen.getByText("26/02")).toBeInTheDocument();
    expect(screen.getAllByText("Alex").length).toBeGreaterThan(0);

    // Every numeric body/footer cell is either the mask or a percentage.
    const cells = container.querySelectorAll("td");
    for (const cell of cells) {
      const text = cell.textContent ?? "";
      if (text === "26/01" || text === "26/02") continue; // month label
      if (text === "Cumulative") continue; // footer label
      if (text === "running totals shown above") continue;
      if (text.endsWith("%") || text === "—") continue; // FR-005
      expect(text).toBe("****");
    }

    // Percentages byte-identical.
    const pctAfter = screen.getAllByText(/%$/).map((c) => c.textContent);
    expect(pctAfter).toEqual(pctBefore);
  });
});
