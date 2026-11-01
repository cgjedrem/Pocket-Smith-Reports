import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

vi.mock("@/api/lifestyle-creep", () => ({ getEconomyLifestyleCreep: vi.fn() }));

import { getEconomyLifestyleCreep } from "@/api/lifestyle-creep";
import { LifestyleCreepPage } from "../LifestyleCreepPage";
import { economyPeriodFixture as lifestylePeriodFixture } from "@/test/fixtures/lifestyle-creep";
import { setAmountsHidden } from "@/lib/privacy-store";
import { ApiError } from "@/types/api";
import type { ReportLifestyleCreepResponse as LifestyleCreepResponse } from "@/types/lifestyle-creep";

const get = vi.mocked(getEconomyLifestyleCreep);
let otherFetch: ReturnType<typeof vi.fn>;

function visit() {
  return render(<MemoryRouter initialEntries={["/lifestyle-creep"]}><LifestyleCreepPage /></MemoryRouter>);
}
function draft(target: string, start: string, end: string) {
  fireEvent.change(screen.getByLabelText("Target month"), { target: { value: target } });
  fireEvent.change(screen.getByLabelText("Reference start"), { target: { value: start } });
  fireEvent.change(screen.getByLabelText("Reference end"), { target: { value: end } });
}
function apply() {
  fireEvent.click(screen.getByRole("button", { name: "Apply comparison" }));
}
async function ready() {
  await screen.findByRole("table", { name: /Partner A.*target/i });
}
function categoriesFixture(start: string, end: string, threshold: string, target: string) {
  const data = lifestylePeriodFixture(start, end, threshold, target);
  const first = data.groups[1];
  first.categories.push({ ...structuredClone(first.categories[0]), category_id: "910002" });
  data.groups[2].categories = first.categories.map((category, index) => ({
    ...structuredClone(category), category_id: `93000${index + 1}`,
  }));
  return data;
}
function partnerView(label = "Partner A") {
  return screen.getByRole("region", { name: `${label} category comparisons` });
}
function hideCategory(id = "910001", label = "Partner A") {
  fireEvent.click(within(partnerView(label)).getByRole("button", { name: `Hide Category A (ID ${id})` }));
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 10, 2, 12));
  setAmountsHidden(false);
  otherFetch = vi.fn(async () => { throw new Error("Unexpected API route"); });
  vi.stubGlobal("fetch", otherFetch);
  get.mockImplementation(async (target, threshold, start, end) => lifestylePeriodFixture(start, end, threshold, target));
});
afterEach(() => {
  setAmountsHidden(false);
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("Lifestyle Creep page", () => {
  it("hides only the selected ID's row and disclosure, independently for each partner and duplicate title", async () => {
    get.mockImplementation(async (target, threshold, start, end) => categoriesFixture(start, end, threshold, target));
    visit();
    await ready();
    hideCategory();
    const a = within(partnerView());
    const b = within(partnerView("Partner B"));
    expect(a.queryByRole("rowheader", { name: /910001/ })).not.toBeInTheDocument();
    expect(a.queryByText("Target comparison: Category A (ID 910001)")).not.toBeInTheDocument();
    expect(a.getByRole("rowheader", { name: /910002/ })).toBeInTheDocument();
    expect(a.getByText("Target comparison: Category A (ID 910002)")).toBeInTheDocument();
    expect(b.getByRole("rowheader", { name: /930001/ })).toBeInTheDocument();
    expect(b.getByText("Target comparison: Category A (ID 930001)")).toBeInTheDocument();
    expect(a.getByRole("status")).toHaveTextContent("1 of 2 categories hidden in this view");
    expect(b.getByRole("status")).toHaveTextContent("0 of 2 categories hidden in this view");
    expect(get).toHaveBeenCalledTimes(1);
    expect(otherFetch).not.toHaveBeenCalled();
  });

  it("shows hidden rows marked Hidden, restores individually and restores all only for that partner without requests", async () => {
    get.mockImplementation(async (target, threshold, start, end) => categoriesFixture(start, end, threshold, target));
    visit();
    await ready();
    hideCategory();
    hideCategory("930001", "Partner B");
    const a = within(partnerView());
    const toggle = a.getByRole("button", { name: "Show hidden categories" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    expect(a.getByRole("row", { name: /910001/ })).toHaveTextContent("Hidden");
    expect(a.getByText("Target comparison: Category A (ID 910001)")).toBeInTheDocument();
    expect(a.getByRole("button", { name: "Hide Category A (ID 910002)" })).toBeInTheDocument();
    fireEvent.click(a.getByRole("button", { name: "Restore Category A (ID 910001)" }));
    expect(a.queryByText("Hidden", { exact: true })).not.toBeInTheDocument();
    expect(a.getByRole("button", { name: "Hide Category A (ID 910001)" })).toBeInTheDocument();
    hideCategory();
    hideCategory("910002");
    fireEvent.click(toggle);
    expect(a.queryByRole("table")).not.toBeInTheDocument();
    fireEvent.click(a.getByRole("button", { name: "Restore all" }));
    expect(a.getAllByRole("rowheader")).toHaveLength(2);
    expect(a.queryByRole("button", { name: "Restore all" })).not.toBeInTheDocument();
    expect(within(partnerView("Partner B")).queryByRole("rowheader", { name: /930001/ })).not.toBeInTheDocument();
    expect(get).toHaveBeenCalledTimes(1);
    expect(otherFetch).not.toHaveBeenCalled();
  });

  it("recovers an all-hidden view without claiming that no categories were observed or changing the server assessment", async () => {
    visit();
    await ready();
    hideCategory();
    const a = within(partnerView());
    expect(a.getByText(/All categories are hidden in this view/)).toBeInTheDocument();
    expect(a.queryByText(/No categorized spending observed/)).not.toBeInTheDocument();
    expect(a.queryByRole("table")).not.toBeInTheDocument();
    expect(a.queryByText(/Target comparison:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/No category was flagged/)).not.toBeInTheDocument();
    expect(a.getByText(/not the assessment across all covered categories/)).toBeInTheDocument();
    fireEvent.click(a.getByRole("button", { name: "Show hidden categories" }));
    expect(a.getByRole("table")).toBeInTheDocument();
    fireEvent.click(a.getByRole("button", { name: "Restore all" }));
    expect(a.getByRole("rowheader", { name: /910001/ })).not.toHaveTextContent("Hidden");
  });

  it("retains true no-categories empty state", async () => {
    get.mockImplementation(async (target, threshold, start, end) => {
      const data = lifestylePeriodFixture(start, end, threshold, target);
      data.groups[1].categories = [];
      return data;
    });
    visit();
    expect(await screen.findByText("No categorized spending observed in the required evidence months.")).toBeInTheDocument();
    expect(screen.queryByText(/All categories are hidden/)).not.toBeInTheDocument();
  });

  it("retains ID visibility and show-hidden state through loading refetches, errors and renamed categories; fresh visits reset", async () => {
    const first = visit();
    await ready();
    hideCategory();
    fireEvent.click(within(partnerView()).getByRole("button", { name: "Show hidden categories" }));
    let resolve!: (data: LifestyleCreepResponse) => void;
    get.mockImplementationOnce(() => new Promise((done) => { resolve = done; }));
    fireEvent.change(screen.getByRole("textbox", { name: /Threshold/ }), { target: { value: "30" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply threshold" }));
    expect(screen.getByText(/Loading target/)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    await act(async () => resolve(lifestylePeriodFixture("2026-07", "2026-09", "30", "2026-10")));
    await ready();
    expect(within(partnerView()).getByRole("button", { name: "Show hidden categories" })).toHaveAttribute("aria-pressed", "true");
    expect(within(partnerView()).getByRole("row", { name: /910001/ })).toHaveTextContent("Hidden");
    fireEvent.click(within(partnerView()).getByRole("button", { name: "Show hidden categories" }));
    get.mockRejectedValueOnce(new ApiError("Synthetic failure", 500));
    draft("2026-09", "2026-04", "2026-08");
    apply();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    get.mockImplementationOnce(async (target, threshold, start, end) => {
      const data = lifestylePeriodFixture(start, end, threshold, target);
      data.groups[1].label = "Renamed partner";
      data.groups[1].partner_id = "renamed-stable-person";
      data.groups[1].categories[0].category_title = "Renamed category";
      return data;
    });
    fireEvent.click(screen.getByRole("button", { name: "Retry history" }));
    expect(await screen.findByText(/All categories are hidden/)).toBeInTheDocument();
    expect(within(partnerView("Renamed partner")).getByRole("status")).toHaveTextContent("1 of 1");
    expect(within(partnerView("Renamed partner")).queryByText(/Target comparison:/)).not.toBeInTheDocument();
    expect(get).toHaveBeenCalledTimes(4);
    expect(get).toHaveBeenLastCalledWith("2026-09", "30", "2026-04", "2026-08");
    expect(otherFetch).not.toHaveBeenCalled();
    first.unmount();
    visit();
    await ready();
    expect(within(partnerView()).getByRole("status")).toHaveTextContent("0 of 1");
    expect(within(partnerView()).getByRole("button", { name: "Show hidden categories" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByText("Target comparison: Category A (ID 910001)")).toBeInTheDocument();
  });

  it("keeps shown hidden rows and collapsed details masked, with no visibility or privacy requests", async () => {
    visit();
    await ready();
    hideCategory();
    act(() => setAmountsHidden(true));
    fireEvent.click(within(partnerView()).getByRole("button", { name: "Show hidden categories" }));
    const region = partnerView();
    expect(region.innerHTML).not.toContain(" kr");
    expect(within(region).getByRole("row", { name: /910001/ })).toHaveTextContent("Hidden");
    expect(region.querySelector("details")).not.toHaveAttribute("open");
    for (const details of region.querySelectorAll("details")) expect(details.innerHTML).not.toContain(" kr");
    fireEvent.click(within(region).getByRole("button", { name: "Restore Category A (ID 910001)" }));
    expect(region.innerHTML).not.toContain(" kr");
    act(() => setAmountsHidden(false));
    expect(region.innerHTML).toContain(" kr");
    expect(get).toHaveBeenCalledTimes(1);
    expect(otherFetch).not.toHaveBeenCalled();
  });

  it.each([
    [new Date(2026, 10, 2, 12), "2026-10", "2026-07", "2026-09"],
    [new Date(2027, 1, 1, 0, 1), "2027-01", "2026-10", "2026-12"],
  ])("defaults to latest completed target and preceding three references on %s", async (date, target, start, end) => {
    vi.setSystemTime(date);
    visit();
    await ready();
    expect(get).toHaveBeenCalledExactlyOnceWith(target, "20", start, end);
    expect(screen.getByLabelText("Target month")).toHaveValue(target);
    expect(screen.getByLabelText("Reference start")).toHaveValue(start);
    expect(screen.getByLabelText("Reference end")).toHaveValue(end);
    expect(screen.getByLabelText("Target month")).toHaveAttribute("max", target);
    expect(screen.getByText(/Compares spending in the selected target month with average monthly spending in the selected reference period/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Detector viewing month")).not.toBeInTheDocument();
    expect(otherFetch).not.toHaveBeenCalled();
  });

  it("keeps local drafts unapplied and applies target plus references in one request", async () => {
    visit();
    await ready();
    draft("2026-10", "2026-03", "2026-08");
    expect(get).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Selected target month: 2026-10")).toBeInTheDocument();
    expect(screen.getByText(/Draft not applied/)).toBeInTheDocument();
    apply();
    await ready();
    expect(get).toHaveBeenCalledTimes(2);
    expect(get).toHaveBeenLastCalledWith("2026-10", "20", "2026-03", "2026-08");
    expect(screen.getByText("Selected target month: 2026-10")).toBeInTheDocument();
    expect(screen.getByText(/Required evidence months:/)).toHaveTextContent("2026-03, 2026-04, 2026-05, 2026-06, 2026-07, 2026-08, 2026-10");
    apply();
    expect(get).toHaveBeenCalledTimes(2);
  });

  it.each([
    ["2026-10", "", "2026-09", /Choose a target month and both reference months/],
    ["2026-10", "2026-09", "", /Choose a target month and both reference months/],
    ["2026-10", "2026-08", "2026-07", /on or before/],
    ["2026-10", "2026-08", "2026-08", /at least 2 consecutive/],
    ["2026-10", "2024-08", "2026-08", /at most 24 consecutive/],
    ["2026-10", "2026-07", "2026-10", /earlier than target/],
    ["2026-11", "2026-07", "2026-09", /completed target month before/],
    ["2026-12", "2026-07", "2026-09", /completed target month before/],
    ["0001-02", "0001-01", "0001-01", /0001-03 or later/],
  ])("rejects invalid selection %s / %s / %s without fetching", async (target, start, end, error) => {
    visit();
    await ready();
    draft(target, start, end);
    apply();
    for (const label of ["Target month", "Reference start", "Reference end"]) {
      expect(screen.getByLabelText(label)).toHaveAttribute("aria-invalid", "true");
      expect(screen.getByLabelText(label)).toHaveAccessibleDescription(error);
    }
    expect(get).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Selected target month: 2026-10")).toBeInTheDocument();
    expect(screen.getByText(/Selected reference period: 2026-07 through 2026-09/)).toBeInTheDocument();
  });

  it("applies threshold separately, preserves it on period changes, and resets on fresh visit", async () => {
    const first = visit();
    await ready();
    const threshold = screen.getByRole("textbox", { name: /Threshold/ });
    for (const raw of ["", "Infinity", "100.00000000000000001", "0.99999999999999999"]) {
      fireEvent.change(threshold, { target: { value: raw } });
      fireEvent.click(screen.getByRole("button", { name: "Apply threshold" }));
      expect(get).toHaveBeenCalledTimes(1);
      expect(threshold).toHaveAttribute("aria-invalid", "true");
      expect(screen.getByText("Applied threshold: 20%")).toBeInTheDocument();
    }
    for (const raw of ["30", "20.5", "1", "100"]) {
      fireEvent.change(threshold, { target: { value: raw } });
      fireEvent.submit(threshold.closest("form")!);
      await ready();
      expect(get).toHaveBeenLastCalledWith("2026-10", raw, "2026-07", "2026-09");
    }
    fireEvent.change(threshold, { target: { value: "+0100.0" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply threshold" }));
    expect(get).toHaveBeenCalledTimes(5);
    draft("2026-10", "2026-04", "2026-09");
    apply();
    await ready();
    expect(get).toHaveBeenLastCalledWith("2026-10", "100", "2026-04", "2026-09");
    first.unmount();
    visit();
    await ready();
    expect(get).toHaveBeenLastCalledWith("2026-10", "20", "2026-07", "2026-09");
    expect(screen.getByRole("textbox", { name: /Threshold/ })).toHaveValue("20");
    expect(screen.getByLabelText("Target month")).toHaveValue("2026-10");
    expect(screen.getByLabelText("Reference start")).toHaveValue("2026-07");
    expect(screen.getByLabelText("Reference end")).toHaveValue("2026-09");
  });

  it("retries the exact applied target/reference/threshold despite changed drafts", async () => {
    visit();
    await ready();
    fireEvent.change(screen.getByRole("textbox", { name: /Threshold/ }), { target: { value: "30" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply threshold" }));
    await ready();
    get.mockRejectedValueOnce(new ApiError("Synthetic detector failure", 500));
    draft("2026-10", "2026-01", "2026-06");
    apply();
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load lifestyle history");
    draft("2026-10", "2026-02", "2026-07");
    fireEvent.change(screen.getByRole("textbox", { name: /Threshold/ }), { target: { value: "25" } });
    fireEvent.click(screen.getByRole("button", { name: "Retry history" }));
    await ready();
    expect(get.mock.calls.slice(-2)).toEqual([
      ["2026-10", "30", "2026-01", "2026-06"],
      ["2026-10", "30", "2026-01", "2026-06"],
    ]);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("Applied threshold: 30%")).toBeInTheDocument();
    expect(otherFetch).not.toHaveBeenCalled();
  });

  it("mounts a usage graph only in expanded disclosures for shared and personal groups, masked and hidden locally", async () => {
    visit();
    await ready();
    const card = screen.getByRole("region", { name: "Lifestyle creep detector" });
    expect(card.querySelector("figure")).toBeNull();
    const groups = ["Shared economy", "Partner A", "Partner B"];
    for (const label of groups) {
      fireEvent.click(partnerView(label).querySelector("summary")!);
      expect(await within(partnerView(label)).findByRole("figure", { name: /Monthly usage over the selected evidence period/ }))
        .toHaveAttribute("data-lifestyle-trend", "chart");
    }
    expect(card.querySelectorAll("figure")).toHaveLength(3);
    expect(card.querySelectorAll("details[open]")).toHaveLength(3);
    const personal = within(partnerView()).getByRole("figure");
    expect(personal).toHaveTextContent("2 of 4 months above their trailing average: 2026-09, 2026-10.");
    expect(within(personal).getByRole("list", { name: "Graph legend" })).toHaveTextContent("Trailing average (up to 3 prior months)");
    expect(within(partnerView("Shared economy")).getByRole("figure")).toHaveTextContent("No month is above its trailing average.");

    act(() => setAmountsHidden(true));
    expect(card.innerHTML).not.toContain(" kr");
    expect(card.querySelector("svg.recharts-surface")).toBeNull();
    expect(card.querySelectorAll('figure[data-lifestyle-trend="masked"]')).toHaveLength(3);
    expect(card.querySelectorAll("details[open]")).toHaveLength(3);
    act(() => setAmountsHidden(false));
    expect(card.querySelectorAll("svg.recharts-surface")).toHaveLength(3);
    expect(card.querySelectorAll("details[open]")).toHaveLength(3);

    hideCategory();
    expect(within(partnerView()).queryByRole("figure")).not.toBeInTheDocument();
    fireEvent.click(within(partnerView()).getByRole("button", { name: "Show hidden categories" }));
    expect(within(partnerView()).getByText("Target comparison: Category A (ID 910001)")).toBeInTheDocument();
    expect(within(partnerView()).queryByRole("figure")).not.toBeInTheDocument();
    expect(card.querySelectorAll("figure")).toHaveLength(2);
    expect(get).toHaveBeenCalledTimes(1);
    expect(otherFetch).not.toHaveBeenCalled();
  });

  it("breaks the graph across a target gap without a target trailing average", async () => {
    visit();
    await ready();
    draft("2026-10", "2026-04", "2026-07");
    apply();
    await ready();
    fireEvent.click(partnerView().querySelector("summary")!);
    const chart = await within(partnerView()).findByRole("figure");
    expect(chart).toHaveTextContent(/2 calendar months between 2026-07 and 2026-10 are not in the selected evidence/);
    expect(within(chart).getByRole("row", { name: /2026-10 \(selected target\)/ })).toHaveTextContent("Not shown");
    expect(within(chart).getAllByRole("row")).toHaveLength(6);
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("masks all money including collapsed samples without a detector refetch", async () => {
    visit();
    await ready();
    const card = screen.getByRole("region", { name: "Lifestyle creep detector" });
    expect(card.innerHTML).toContain(" kr");
    act(() => setAmountsHidden(true));
    expect(card.innerHTML).not.toContain(" kr");
    expect(within(card).getAllByText("27.27%").length).toBeGreaterThan(0);
    for (const details of card.querySelectorAll("details")) expect(details.innerHTML).not.toContain(" kr");
    act(() => setAmountsHidden(false));
    expect(card.innerHTML).toContain(" kr");
    expect(get).toHaveBeenCalledTimes(1);
  });
});
