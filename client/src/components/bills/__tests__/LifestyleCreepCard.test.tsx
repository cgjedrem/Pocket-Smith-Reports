import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { LifestyleCreepCard, type LifestyleCreepCardProps } from "../LifestyleCreepCard";
import {
  economyFixture as lifestyleFixture, economyPeriodFixture as lifestylePeriodFixture,
  insufficientEconomyFixture,
} from "@/test/fixtures/lifestyle-creep";
import { setAmountsHidden } from "@/lib/privacy-store";
import type { ReportLifestyleCreepResponse as LifestyleCreepResponse } from "@/types/lifestyle-creep";
import { ApiError } from "@/types/api";

function show(data: LifestyleCreepResponse | null = lifestyleFixture(), props: Partial<LifestyleCreepCardProps> = {}) {
  const selected = data ?? lifestyleFixture();
  return render(
    <MemoryRouter>
      <LifestyleCreepCard
        targetMonth={selected.month}
        referenceStart={selected.reference_start}
        referenceEnd={selected.reference_end}
        targetDraft={selected.month}
        referenceStartDraft={selected.reference_start}
        referenceEndDraft={selected.reference_end}
        currentMonth="2026-11"
        onTargetDraftChange={vi.fn()}
        onReferenceStartDraftChange={vi.fn()}
        onReferenceEndDraftChange={vi.fn()}
        onComparisonApply={vi.fn()}
        thresholdDraft="20"
        appliedThreshold="20"
        onThresholdDraftChange={vi.fn()}
        onThresholdApply={vi.fn()}
        data={data}
        loading={false}
        error={null}
        onRetry={vi.fn()}
        {...props}
      />
    </MemoryRouter>,
  );
}

beforeEach(() => setAmountsHidden(false));

describe("LifestyleCreepCard target/reference comparison", () => {
  it("renders server report groups in order with Home/Common together and configured personal labels", () => {
    const data = lifestyleFixture();
    data.groups[1].label = "Configured A";
    data.groups[2].label = "Configured B";
    show(data);
    expect(screen.getAllByRole("table").map((table) => table.getAttribute("aria-label"))).toEqual([
      "Shared economy target category comparisons", "Configured A target category comparisons",
      "Configured B target category comparisons",
    ]);
    const shared = screen.getByRole("table", { name: /Shared economy/ });
    expect(within(shared).getByRole("rowheader", { name: /Home category.*920001/ })).toBeInTheDocument();
    expect(within(shared).getByRole("rowheader", { name: /Common category.*920002/ })).toBeInTheDocument();
    expect(within(shared).queryByText("Category A")).not.toBeInTheDocument();
    expect(screen.getByText(/Shared economy includes Home \+ Common only/)).toHaveTextContent(
      "Trips, savings, income, excluded and credit-card payment sections are omitted",
    );
    expect(screen.queryByText(/Recorded credit-card spending only/)).not.toBeInTheDocument();
  });

  it("keeps report-assigned categories in their group regardless of labels or paying-person identity", () => {
    const data = lifestyleFixture();
    data.groups[1].partner_id = "payer_b";
    data.groups[1].categories[0].category_title = "Paid by other person";
    data.groups[2].partner_id = "payer_a";
    data.groups[2].categories[0].category_title = "Paid by other person";
    show(data);
    const a = within(screen.getByRole("table", { name: /Partner A.*target/i }));
    const b = within(screen.getByRole("table", { name: /Partner B.*target/i }));
    expect(a.getByRole("rowheader", { name: /Paid by other person.*910001/ })).toBeInTheDocument();
    expect(b.getByRole("rowheader", { name: /Paid by other person.*930001/ })).toBeInTheDocument();
    expect(a.queryByRole("rowheader", { name: /930001/ })).not.toBeInTheDocument();
    expect(b.queryByRole("rowheader", { name: /910001/ })).not.toBeInTheDocument();
  });

  it("isolates visibility by stable group ID even for identical category IDs, titles and labels", () => {
    const data = lifestyleFixture();
    for (const group of data.groups) {
      group.label = "Same label";
      group.categories = [structuredClone(data.groups[1].categories[0])];
    }
    const { container } = show(data);
    const regions = ["shared", "personal_partner_a", "personal_partner_b"].map((id) =>
      within(container.querySelector<HTMLElement>(`[data-group-id="${id}"]`)!));
    fireEvent.click(regions[0].getByRole("button", { name: "Hide Category A (ID 910001)" }));
    fireEvent.click(regions[1].getByRole("button", { name: "Hide Category A (ID 910001)" }));
    expect(regions[0].queryByRole("table")).not.toBeInTheDocument();
    expect(regions[1].queryByRole("table")).not.toBeInTheDocument();
    expect(regions[2].getByRole("table")).toBeInTheDocument();
    fireEvent.click(regions[0].getByRole("button", { name: "Show hidden categories" }));
    expect(regions[0].getByRole("rowheader")).toHaveTextContent("Hidden");
    expect(regions[1].queryByRole("table")).not.toBeInTheDocument();
    fireEvent.click(regions[0].getByRole("button", { name: "Restore all" }));
    expect(regions[0].getByRole("rowheader")).not.toHaveTextContent("Hidden");
    expect(regions[1].queryByRole("table")).not.toBeInTheDocument();
    expect(regions[2].getByRole("status")).toHaveTextContent("0 of 1");
    expect(data.groups.every((group) => group.categories.length === 1)).toBe(true);
  });

  it("displays signed refunds and the server verdict without clamping net amounts or recalculating", () => {
    const data = lifestyleFixture();
    const category = data.groups[1].categories[0];
    category.samples[0].amount = "-65";
    category.comparison.spending_amount = "-43";
    category.comparison.change_amount = "-153";
    category.comparison.growth_percent = "-139.090909";
    category.is_above_threshold = false;
    show(data);
    const region = screen.getByRole("region", { name: "Partner A category comparisons" });
    expect(within(region).getAllByText("-43 kr")).toHaveLength(2);
    expect(within(region).getByText("-65 kr")).toBeInTheDocument();
    expect(within(region).getAllByText("-153 kr")).toHaveLength(2);
    expect(within(region).getAllByText("Below threshold")).toHaveLength(2);
    fireEvent.click(within(region).getByRole("button", { name: /Hide Category A/ }));
    act(() => setAmountsHidden(true));
    fireEvent.click(within(region).getByRole("button", { name: "Show hidden categories" }));
    for (const details of region.querySelectorAll("details")) details.open = true;
    expect(region.innerHTML).not.toContain(" kr");
    expect(region.innerHTML).not.toMatch(/-43|-65|-153/);
    expect(within(region).getAllByText("-139.09%")).toHaveLength(2);
    act(() => setAmountsHidden(false));
    expect(within(region).getAllByText("-43 kr")).toHaveLength(2);
  });

  it("shows one target versus the selected reference average and only required evidence months", () => {
    const data = lifestylePeriodFixture("2026-07", "2026-09", "20", "2026-12");
    show(data);
    expect(screen.getByText("Selected target month: 2026-12")).toBeInTheDocument();
    expect(screen.getByText("Selected reference period: 2026-07 through 2026-09 (inclusive).")).toBeInTheDocument();
    expect(screen.getByText(/Required evidence:/)).toHaveTextContent(
      "reference months 2026-07 through 2026-09, plus target 2026-12",
    );
    expect(screen.getByText(/Months between the reference period and target are not required/)).toBeInTheDocument();
    expect(screen.getByText(/Required evidence months:/)).toHaveTextContent("2026-07, 2026-08, 2026-09, 2026-12");
    expect(screen.getByText(/Required evidence months:/)).not.toHaveTextContent("2026-10");
    const table = screen.getByRole("table", { name: /Partner A.*target/i });
    expect(within(table).getByText("140 kr")).toBeInTheDocument();
    expect(within(table).getByText("110 kr")).toBeInTheDocument();
    expect(within(table).getByText("+30 kr")).toBeInTheDocument();
    expect(within(table).getByText("27.27%")).toBeInTheDocument();
    expect(within(table).getByText("Above threshold")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: "2026-12 target versus reference-period average" })).toHaveLength(4);
    expect(screen.getAllByText("2026-07, 2026-08, 2026-09")).toHaveLength(4);
    expect(screen.queryByText(/sustained|rolling comparison|last two/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Actual month-over-month/)).not.toBeInTheDocument();
  });

  it("uses the server threshold flag rather than displayed growth to badge the result", () => {
    const data = lifestyleFixture();
    const category = data.groups[1].categories[0];
    category.comparison.growth_percent = "99";
    category.is_above_threshold = false;
    show(data);
    const table = screen.getByRole("table", { name: /Partner A.*target/i });
    expect(within(table).getByText("99%")).toBeInTheDocument();
    expect(within(table).getByText("Below threshold")).toBeInTheDocument();
    expect(screen.getByText("No category was flagged above threshold in the covered report-grouped spending.")).toBeInTheDocument();
  });

  it("labels adjacent-month growth only when the server provides it", () => {
    const data = lifestyleFixture();
    data.groups[1].categories[0].latest_month_over_month_percent = "7.692307692";
    show(data);
    const a = within(screen.getByRole("region", { name: "Partner A category comparisons" }));
    expect(a.getByText(/Actual month-over-month \(2026-10 vs 2026-09\)/)).toHaveTextContent("7.69%");
    expect(a.getByText(/not the reference-period average/)).toBeInTheDocument();
  });

  it.each([
    ["zero_baseline", "Suppressed — zero reference baseline"],
    ["negative_baseline", "Suppressed — negative reference baseline"],
    ["low_frequency", "Suppressed — positive spending in fewer than two reference months"],
  ] as const)("explains %s suppression without inventing an outcome", (reason, wording) => {
    const data = lifestyleFixture();
    const category = data.groups[1].categories[0];
    category.is_above_threshold = false;
    category.suppression_reason = reason;
    if (reason !== "low_frequency") {
      category.samples.slice(0, -1).forEach((sample) => { sample.amount = reason === "zero_baseline" ? "0" : "-10"; });
      category.comparison.baseline_amount = reason === "zero_baseline" ? "0" : "-10";
      category.comparison.change_amount = "140";
      category.comparison.growth_percent = null;
      category.latest_month_over_month_percent = null;
    } else {
      category.samples[0].amount = "0";
      category.samples[1].amount = "0";
      category.comparison.baseline_amount = "43.33333333333333333333333333";
      category.comparison.change_amount = "96.66666666666666666666666667";
      category.comparison.growth_percent = "223.0769230769230769230769231";
    }
    show(data);
    expect(screen.getAllByText(wording).length).toBeGreaterThan(0);
    const a = within(screen.getByRole("region", { name: "Partner A category comparisons" }));
    if (reason !== "low_frequency") {
      expect(a.getAllByText(/Not calculable — nonpositive reference baseline/).length).toBeGreaterThan(0);
    } else {
      expect(screen.getAllByText("223.08%").length).toBeGreaterThan(0);
    }
    if (reason !== "low_frequency") {
      expect(a.queryByText(/Actual month-over-month/)).not.toBeInTheDocument();
    } else {
      expect(a.getByText(/Actual month-over-month \(2026-10 vs 2026-09\)/)).toBeInTheDocument();
    }
  });

  it("shows incomplete issue months and retry guidance without requiring the months between bounds", () => {
    const data = lifestylePeriodFixture("2026-07", "2026-09", "20", "2026-12");
    data.status = "insufficient_history";
    data.groups.forEach((group) => {
      group.status = "insufficient_history"; group.categories = []; group.uncategorized_samples = [];
    });
    data.issues = [{ month: "2026-12", group_id: null, partner_id: null, code: "missing_snapshot", reason: null }];
    data.window_months = ["2026-07", "2026-08", "2026-09", "2026-12"];
    show(data);
    expect(screen.getByRole("status")).toHaveTextContent("Insufficient history");
    expect(screen.getByText(/2026-12 · All report groups: Saved month is missing/)).toBeInTheDocument();
    expect(screen.getByText(/^Check report mappings/)).toHaveTextContent("explicitly re-sync every selected completed reference and target month");
    expect(screen.getByRole("link", { name: /Open sync/ })).toHaveAttribute("href", "/sync");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("keeps all three headings with explicit resync guidance for legacy snapshots, never zero-filled tables", () => {
    const data = insufficientEconomyFixture();
    show(data);
    for (const label of ["Shared economy", "Partner A", "Partner B"]) {
      const region = screen.getByRole("region", { name: `${label} category comparisons` });
      expect(within(region).getByRole("heading", { level: 3 })).toHaveTextContent(label);
      expect(within(region).getByText(/missing evidence is not zero spending/)).toBeInTheDocument();
      expect(within(region).queryByRole("table")).not.toBeInTheDocument();
      expect(region.innerHTML).not.toContain(" kr");
    }
    expect(screen.getByText(data.history_guidance!)).toBeInTheDocument();
    expect(screen.queryByText(/No categorized spending observed|No category was flagged/)).not.toBeInTheDocument();
  });

  it("shows the API open-month response without money, a conclusion, or a claim that history was read", () => {
    const data = insufficientEconomyFixture();
    data.issues = [{ month: data.month, group_id: null, partner_id: null, code: "partial_month", reason: "open_month" }];
    show(data);
    expect(screen.getByRole("status")).toHaveTextContent("Insufficient history — no reliable conclusion.");
    expect(screen.getByText(/Month is still open or history was acquired while open/)).toHaveTextContent(
      "wait until it closes, then re-sync if needed",
    );
    expect(screen.getByText(/Required evidence months:/)).toBeInTheDocument();
    expect(screen.queryByText(/Evidence months read|Selection was rejected|No category was flagged/)).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByText(/kr/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry history" })).toBeInTheDocument();
  });

  it("keeps uncategorized amounts separate and reports complete empty categories", () => {
    const data = lifestyleFixture();
    data.groups.forEach((group) => { group.categories = []; });
    data.groups[0].uncategorized_samples[0].amount = "17";
    show(data);
    expect(screen.getAllByText(/No categorized spending observed in the required evidence months/)).toHaveLength(3);
    expect(screen.getByText(/excluded from category-threshold outcomes/)).toBeInTheDocument();
    expect(screen.getByText("17 kr")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("keeps threshold controls atomic and rejects invalid period drafts", () => {
    const apply = vi.fn();
    const thresholdApply = vi.fn();
    show(lifestyleFixture(), {
      targetDraft: "2026-10",
      referenceStartDraft: "2026-06",
      referenceEndDraft: "2026-08",
      thresholdDraft: "100.00000000000000001",
      onComparisonApply: apply,
      onThresholdApply: thresholdApply,
    });
    const target = screen.getByLabelText("Target month");
    const referenceStart = screen.getByLabelText("Reference start");
    const referenceEnd = screen.getByLabelText("Reference end");
    fireEvent.submit(target.closest("form")!);
    expect(apply).toHaveBeenCalledWith("2026-10", "2026-06", "2026-08");
    fireEvent.click(screen.getByRole("button", { name: "Apply threshold" }));
    expect(thresholdApply).not.toHaveBeenCalled();
    expect(screen.getByText("Applied threshold: 20%")).toBeInTheDocument();
    expect(referenceStart).toHaveAccessibleDescription(/Draft not applied/);
    expect(referenceEnd).toHaveAttribute("type", "month");
  });

  it("announces loading/error safely and retry remains keyboard-operable", () => {
    const retry = vi.fn();
    show(lifestyleFixture(), { loading: true });
    expect(screen.getByRole("status")).toHaveTextContent("Loading target 2026-10 against reference months 2026-07 through 2026-09 at 20%");
    expect(screen.getByRole("region", { name: "Lifestyle creep detector" })).toHaveAttribute("aria-busy", "true");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    cleanup();
    show(lifestyleFixture(), { error: new ApiError("Synthetic secret 123 kr", 500), onRetry: retry });
    expect(screen.getByRole("alert")).toHaveTextContent("Could not load lifestyle history");
    expect(screen.queryByText(/123/)).not.toBeInTheDocument();
    const button = screen.getByRole("button", { name: "Retry history" });
    button.focus();
    fireEvent.click(button);
    expect(retry).toHaveBeenCalledOnce();
  });

  it("masks visible and collapsed money while keeping percentages visible", () => {
    const data = lifestyleFixture();
    data.groups[1].categories[0].comparison.change_amount = "-43";
    data.groups[1].uncategorized_samples[0].amount = "-876543";
    const { container } = show(data);
    expect(container.textContent).toContain("-43 kr");
    act(() => setAmountsHidden(true));
    expect(container.innerHTML).not.toMatch(/(?:140|110|100|130|-43|876543) kr/);
    expect(container.innerHTML).not.toContain(" kr");
    expect(container.textContent).toContain("****");
    expect(container.textContent).toContain("27.27%");
    for (const node of container.querySelectorAll("*")) {
      for (const attribute of node.attributes) {
        expect(attribute.value).not.toMatch(/876543|140 kr|110 kr|-43 kr/);
      }
    }
    for (const details of container.querySelectorAll("details")) expect(details.innerHTML).not.toContain(" kr");
    act(() => setAmountsHidden(false));
    expect(container.textContent).toContain("-43 kr");
  });
});
