// Route + nav tests for the Lifestyle Creep tab — real router config.

import { render, screen, waitFor, within } from "@testing-library/react";
import { RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/lifestyle-creep", () => ({ getEconomyLifestyleCreep: vi.fn() }));

import { getEconomyLifestyleCreep } from "@/api/lifestyle-creep";
import { setAmountsHidden } from "@/lib/privacy-store";
import { router } from "@/router";
import { economyPeriodFixture as lifestylePeriodFixture } from "@/test/fixtures/lifestyle-creep";
import { currentLifestyleMonth, defaultLifestyleSelection } from "@/lib/lifestyle-creep";

const get = vi.mocked(getEconomyLifestyleCreep);
let otherFetch: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.resetAllMocks();
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 10, 2, 12));
  setAmountsHidden(false);
  // Tripwire — no real network from any route.
  otherFetch = vi.fn(async () => { throw new Error("Unexpected API route"); });
  vi.stubGlobal("fetch", otherFetch);
  get.mockImplementation(async (month, threshold, start, end) =>
    lifestylePeriodFixture(start, end, threshold, month));
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("Lifestyle Creep route", () => {
  it("deep link renders the page inside the app shell with an active nav tab after Bills", async () => {
    await router.navigate("/lifestyle-creep");
    render(<RouterProvider router={router} />);

    const nav = screen.getByRole("navigation");
    const tab = within(nav).getByRole("link", { name: "Lifestyle Creep" });
    expect(tab).toHaveAttribute("href", "/lifestyle-creep");
    expect(tab).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "Bills" })).not.toHaveAttribute("aria-current");

    // Tab order — directly after Bills.
    const names = within(nav).getAllByRole("link").map((link) => link.textContent);
    expect(names.indexOf("Lifestyle Creep")).toBe(names.indexOf("Bills") + 1);

    expect(screen.getByRole("heading", { level: 1, name: "Lifestyle Creep" })).toBeInTheDocument();
    expect(await screen.findByRole("region", { name: "Lifestyle creep detector" })).toBeInTheDocument();
    await waitFor(() => expect(get).toHaveBeenCalledTimes(1));
    const selection = defaultLifestyleSelection();
    expect(get).toHaveBeenCalledWith(selection.target, "20", selection.referenceStart, selection.referenceEnd);
    expect(currentLifestyleMonth()).toBe("2026-11");
    expect(screen.getByLabelText("Target month")).toHaveValue(selection.target);
    expect(screen.getByLabelText("Reference start")).toHaveValue(selection.referenceStart);
    expect(screen.getByLabelText("Reference end")).toHaveValue(selection.referenceEnd);
    expect(otherFetch).not.toHaveBeenCalled();
  });
});
