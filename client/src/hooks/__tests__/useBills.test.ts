// Hook tests — mock api/bills + lib/bills-source.

import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/bills", () => ({
  getSnapshot: vi.fn(),
  getEvents: vi.fn(),
  getEvent: vi.fn(),
}));

vi.mock("@/lib/bills-source", () => ({
  hydrate: vi.fn(),
  reset: vi.fn(),
}));

import { getEvent, getEvents, getSnapshot } from "@/api/bills";
import { useBillsEvent, useBillsEvents, useBillsSnapshot } from "@/hooks/useBills";
import { ApiError } from "@/types/api";
import { hydrate } from "@/lib/bills-source";

const mockedGetSnapshot = vi.mocked(getSnapshot);
const mockedGetEvents = vi.mocked(getEvents);
const mockedGetEvent = vi.mocked(getEvent);
const mockedHydrate = vi.mocked(hydrate);

function snapResponse() {
  return {
    schema_version: 1,
    month: "2026-07",
    month_label: "July 2026",
    is_past: true,
    is_current: false,
    is_future: false,
    synced_at: "2026-08-02T14:01:08Z",
    bills_count: 0,
    buys_count: 0,
    warnings: [],
    partners: [],
    source_counts: {
      ps_events_fetched: 0,
      ps_transactions_fetched: 0,
      events_kept_after_filter: 0,
    },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useBillsSnapshot", () => {
  it("fetches snapshot range and hydrates source on 200", async () => {
    mockedGetSnapshot.mockResolvedValue(snapResponse() as never);
    const { result } = renderHook(() => useBillsSnapshot("2026-07"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.snapshots.length).toBeGreaterThan(0);
    expect(result.current.snapshots[0].month).toBe("2026-07");
    expect(result.current.error).toBeNull();
    expect(result.current.notFound).toBe(false);
    expect(mockedHydrate).toHaveBeenCalledOnce();
  });

  it("marks notFound on 404 of primary month", async () => {
    mockedGetSnapshot.mockImplementation(async (m: string) => {
      if (m === "2026-03") throw new ApiError("missing", 404);
      return snapResponse() as never;
    });
    const { result } = renderHook(() => useBillsSnapshot("2026-03"));
    await waitFor(() => expect(result.current.notFound).toBe(true));
    expect(result.current.error).toBeNull();
  });

  it("sets error on 500 of primary month", async () => {
    mockedGetSnapshot.mockImplementation(async (m: string) => {
      if (m === "2026-07") throw new ApiError("oops", 500);
      return snapResponse() as never;
    });
    const { result } = renderHook(() => useBillsSnapshot("2026-07"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error?.detail).toBe("oops");
    expect(result.current.notFound).toBe(false);
  });

  it("refetch re-runs the query", async () => {
    mockedGetSnapshot.mockResolvedValue(snapResponse() as never);
    const { result } = renderHook(() => useBillsSnapshot("2026-07"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    const firstCalls = mockedGetSnapshot.mock.calls.length;
    expect(firstCalls).toBeGreaterThan(0);
    act(() => result.current.refetch());
    await waitFor(() =>
      expect(mockedGetSnapshot.mock.calls.length).toBeGreaterThan(firstCalls),
    );
  });
});

describe("useBillsEvents", () => {
  it("fetches events list on 200", async () => {
    mockedGetEvents.mockResolvedValueOnce({
      events: [],
      total: 0,
    } as never);
    const { result } = renderHook(() => useBillsEvents("2026-07"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.events).toEqual([]);
    expect(result.current.total).toBe(0);
  });

  it("sets error on 400 and clears list", async () => {
    mockedGetEvents.mockRejectedValueOnce(new ApiError("bad", 400));
    const { result } = renderHook(() => useBillsEvents("2026-07"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error?.detail).toBe("bad");
    expect(result.current.events).toEqual([]);
  });
});

describe("useBillsEvent", () => {
  it("does not fetch when open=false", async () => {
    const { result } = renderHook(() =>
      useBillsEvent("evt-1", "2026-07", false),
    );
    expect(mockedGetEvent).not.toHaveBeenCalled();
    expect(result.current.event).toBeNull();
  });

  it("fetches event on open=true", async () => {
    mockedGetEvent.mockResolvedValueOnce({
      id: "evt-1",
      date: "2026-07-01",
      day: 1,
      title: "x",
      type: "bill",
      account: "c",
      partner: { partner_id: "partner_a", partner_slot: "a", label: "Fixture A" },
      amount: -10,
      is_cc_payment: false,
      is_matched: null,
    } as never);
    const { result } = renderHook(() =>
      useBillsEvent("evt-1", "2026-07", true),
    );
    await waitFor(() => expect(result.current.event?.id).toBe("evt-1"));
  });

  it("marks notFound on 404", async () => {
    mockedGetEvent.mockRejectedValueOnce(new ApiError("Event evt-1 not found in 2026-07", 404));
    const { result } = renderHook(() =>
      useBillsEvent("evt-1", "2026-07", true),
    );
    await waitFor(() => expect(result.current.notFound).toBe(true));
    expect(result.current.error).toBeNull();
  });
});
