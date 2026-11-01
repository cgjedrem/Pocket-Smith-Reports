import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/lifestyle-creep", () => ({ getEconomyLifestyleCreep: vi.fn() }));

import { getEconomyLifestyleCreep } from "@/api/lifestyle-creep";
import { useLifestyleCreep } from "../useLifestyleCreep";
import {
  economyFixture as lifestyleFixture, economyPeriodFixture as lifestylePeriodFixture, insufficientEconomyFixture,
} from "@/test/fixtures/lifestyle-creep";
import { ApiError } from "@/types/api";
import type { ReportLifestyleCreepResponse as LifestyleCreepResponse } from "@/types/lifestyle-creep";

const get = vi.mocked(getEconomyLifestyleCreep);
const originalSelection = { month: "2026-10", threshold: "20", start: "2026-07", end: "2026-09" };

function deferred() {
  let resolve!: (data: LifestyleCreepResponse) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<LifestyleCreepResponse>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 10, 2, 12));
});
afterEach(() => vi.useRealTimers());

describe("useLifestyleCreep", () => {
  it("requests explicit target/reference identity and retries the same read-only selection", async () => {
    const pending = deferred();
    get.mockReturnValueOnce(pending.promise).mockResolvedValue(lifestyleFixture());
    const { result } = renderHook(() => useLifestyleCreep(
      originalSelection.month, originalSelection.threshold, originalSelection.start, originalSelection.end,
    ));
    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBeNull();
    await act(async () => pending.resolve(lifestyleFixture()));
    expect(result.current.data?.status).toBe("ready");
    act(() => result.current.retry());
    expect(result.current.data).toBeNull();
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(get.mock.calls).toEqual([
      ["2026-10", "20", "2026-07", "2026-09"],
      ["2026-10", "20", "2026-07", "2026-09"],
    ]);
  });

  it.each([new ApiError("Synthetic failure", 500), new Error("Synthetic network error")])("normalizes errors and recovers on Retry", async (error) => {
    get.mockRejectedValueOnce(error).mockResolvedValue(lifestyleFixture());
    const { result } = renderHook(() => useLifestyleCreep(
      originalSelection.month, "20", originalSelection.start, originalSelection.end,
    ));
    await waitFor(() => expect(result.current.error).toBeInstanceOf(ApiError));
    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(false);
    act(() => result.current.retry());
    await waitFor(() => expect(result.current.data?.status).toBe("ready"));
    expect(result.current.error).toBeNull();
  });

  it.each(["success", "failure"] as const)("ignores stale %s after a new target/reference selection succeeds", async (outcome) => {
    const old = deferred();
    const latest = lifestylePeriodFixture("2026-06", "2026-08", "30", "2026-10");
    get.mockReturnValueOnce(old.promise).mockResolvedValueOnce(latest);
    const { result, rerender } = renderHook(
      ({ start }) => useLifestyleCreep("2026-10", "30", start, "2026-08"),
      { initialProps: { start: "2026-07" } },
    );
    rerender({ start: "2026-06" });
    await waitFor(() => expect(result.current.data).toBe(latest));
    await act(async () => outcome === "success" ? old.resolve(lifestyleFixture()) : old.reject(new Error("Stale failure")));
    expect(result.current.data).toBe(latest);
    expect(result.current.error).toBeNull();
  });

  it("clears the old result immediately when the target changes", async () => {
    const pending = deferred();
    get.mockResolvedValueOnce(lifestyleFixture()).mockReturnValueOnce(pending.promise);
    const { result, rerender } = renderHook(
      ({ month, start, end }) => useLifestyleCreep(month, "20", start, end),
      { initialProps: { month: "2026-10", start: "2026-07", end: "2026-09" } },
    );
    await waitFor(() => expect(result.current.data).not.toBeNull());
    rerender({ month: "2026-09", start: "2026-06", end: "2026-08" });
    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(true);
    await act(async () => pending.resolve(lifestylePeriodFixture("2026-06", "2026-08", "20", "2026-09")));
    expect(result.current.data?.month).toBe("2026-09");
  });

  it.each([
    { month: "2026-09" }, { threshold_percent: "21" },
    { reference_start: "2026-06" }, { reference_end: "2026-08" },
  ])("rejects response identity mismatch %j", async (mismatch) => {
    get.mockResolvedValue({ ...lifestyleFixture(), ...mismatch });
    const { result } = renderHook(() => useLifestyleCreep("2026-10", "20", "2026-07", "2026-09"));
    await waitFor(() => expect(result.current.error).toBeInstanceOf(ApiError));
    expect(result.current.data).toBeNull();
  });

  it("rejects malformed evidence coverage even when selection echoes match", async () => {
    const malformed = { ...lifestyleFixture(), window_months: null } as unknown as LifestyleCreepResponse;
    get.mockResolvedValue(malformed);
    const { result } = renderHook(() => useLifestyleCreep("2026-10", "20", "2026-07", "2026-09"));
    await waitFor(() => expect(result.current.error).toBeInstanceOf(ApiError));
    expect(result.current.data).toBeNull();
  });

  it.each([
    "mode", "missing", "order", "duplicate", "slot", "shared-person", "same-person", "missing-person",
    "mixed-coverage", "money-in-incomplete", "sample-window", "cross-group-category",
  ])("rejects malformed report group identity or coverage: %s", async (failure) => {
    const data = lifestyleFixture();
    if (failure === "mode") Object.assign(data, { grouping: "card" });
    if (failure === "missing") data.groups.pop();
    if (failure === "order") data.groups.reverse();
    if (failure === "duplicate") data.groups[2] = structuredClone(data.groups[1]);
    if (failure === "slot") data.groups[0].partner_slot = "a";
    if (failure === "shared-person") data.groups[0].partner_id = "partner_a";
    if (failure === "same-person") data.groups[2].partner_id = data.groups[1].partner_id;
    if (failure === "missing-person") data.groups[1].partner_id = null;
    if (failure === "mixed-coverage") data.groups[0].status = "insufficient_history";
    if (failure === "money-in-incomplete") data.status = "insufficient_history";
    if (failure === "sample-window") data.groups[0].categories[0].samples[0].month = "2026-01";
    if (failure === "cross-group-category") data.groups[0].categories[0].category_id = data.groups[1].categories[0].category_id;
    get.mockResolvedValue(data);
    const { result } = renderHook(() => useLifestyleCreep("2026-10", "20", "2026-07", "2026-09"));
    await waitFor(() => expect(result.current.error).toBeInstanceOf(ApiError));
    expect(result.current.data).toBeNull();
  });

  it("accepts signed report amounts and preserves authoritative suppression and verdicts", async () => {
    const data = lifestyleFixture();
    const category = data.groups[1].categories[0];
    category.samples.forEach((sample) => { sample.amount = "-10"; });
    category.comparison.baseline_amount = "-10";
    category.comparison.spending_amount = "-10";
    category.comparison.change_amount = "0";
    category.comparison.growth_percent = null;
    category.latest_month_over_month_percent = null;
    category.suppression_reason = "negative_baseline";
    category.is_above_threshold = false;
    data.groups[0].categories[0].comparison.growth_percent = "20";
    data.groups[0].categories[0].is_above_threshold = true;
    get.mockResolvedValue(data);
    const { result } = renderHook(() => useLifestyleCreep("2026-10", "20", "2026-07", "2026-09"));
    await waitFor(() => expect(result.current.data).toBe(data));
    expect(result.current.error).toBeNull();
    expect(result.current.data?.groups[0].categories[0].is_above_threshold).toBe(true);
  });

  it("accepts three legacy insufficient groups without identities or monetary samples", async () => {
    const data = insufficientEconomyFixture();
    get.mockResolvedValue(data);
    const { result } = renderHook(() => useLifestyleCreep("2026-10", "20", "2026-07", "2026-09"));
    await waitFor(() => expect(result.current.data).toBe(data));
    expect(result.current.error).toBeNull();
    expect(result.current.data?.groups).toHaveLength(3);
  });

  it.each(["success", "failure"] as const)("ignores an older %s after Retry of the same selection", async (outcome) => {
    const old = deferred();
    const repaired = lifestyleFixture();
    get.mockReturnValueOnce(old.promise).mockResolvedValueOnce(repaired);
    const { result } = renderHook(() => useLifestyleCreep("2026-10", "20", "2026-07", "2026-09"));
    act(() => result.current.retry());
    await waitFor(() => expect(result.current.data).toBe(repaired));
    await act(async () => outcome === "success" ? old.resolve(lifestyleFixture()) : old.reject(new Error("Old read failed")));
    expect(result.current.data).toBe(repaired);
    expect(result.current.error).toBeNull();
  });

  it.each([
    ["2026-10", "", "2026-09"],
    ["2026-10", "2026-08", "2026-08"], ["2026-10", "2026-09", "2026-08"],
    ["2026-10", "2024-08", "2026-09"], ["2026-10", "2026-07", "2026-10"],
    ["2026-11", "2026-07", "2026-09"], ["2026-12", "2026-07", "2026-09"], ["", "2026-07", "2026-09"],
  ])("rejects invalid selection %s / %s / %s without a request", async (month, start, end) => {
    const { result } = renderHook(() => useLifestyleCreep(month!, "20", start!, end!));
    await waitFor(() => expect(result.current.error?.status).toBe(400));
    expect(get).not.toHaveBeenCalled();
  });

  it("canonicalizes equivalent thresholds and retries exact target/range identity", async () => {
    get.mockResolvedValue(lifestyleFixture());
    const { result, rerender } = renderHook(
      ({ threshold }) => useLifestyleCreep("2026-10", threshold, "2026-07", "2026-09"),
      { initialProps: { threshold: "20" } },
    );
    await waitFor(() => expect(result.current.data).not.toBeNull());
    rerender({ threshold: "+020.00" });
    expect(get).toHaveBeenCalledTimes(1);
    act(() => result.current.retry());
    await waitFor(() => expect(result.current.data).not.toBeNull());
    expect(get.mock.calls).toEqual([
      ["2026-10", "20", "2026-07", "2026-09"],
      ["2026-10", "20", "2026-07", "2026-09"],
    ]);
  });

  it("ignores success and failure after unmount", async () => {
    const pending = deferred();
    get.mockReturnValue(pending.promise);
    const rendered = vi.fn();
    const { unmount } = renderHook(() => {
      rendered();
      return useLifestyleCreep("2026-10", "20", "2026-07", "2026-09");
    });
    unmount();
    const count = rendered.mock.calls.length;
    await act(async () => pending.resolve(lifestyleFixture()));
    expect(rendered).toHaveBeenCalledTimes(count);
  });
});
