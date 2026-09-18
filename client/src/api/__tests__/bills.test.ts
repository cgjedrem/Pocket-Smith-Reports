// API client tests — thin wrappers around apiGet. Mock apiGet, assert calls.

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  apiGet: vi.fn(),
}));

import { apiGet } from "@/api/client";
import { getEvent, getEvents, getSnapshot } from "@/api/bills";

const mockedApiGet = vi.mocked(apiGet);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("getSnapshot", () => {
  it("calls /api/bills/dashboard with encoded month", async () => {
    mockedApiGet.mockResolvedValueOnce({} as never);
    await getSnapshot("2026-07");
    expect(mockedApiGet).toHaveBeenCalledWith(
      "/api/bills/dashboard?month=2026-07",
    );
  });

  it("encodes special chars in month", async () => {
    mockedApiGet.mockResolvedValueOnce({} as never);
    await getSnapshot("2026/07");
    expect(mockedApiGet).toHaveBeenCalledWith(
      "/api/bills/dashboard?month=2026%2F07",
    );
  });
});

describe("getEvents", () => {
  it("calls /api/bills/dashboard/events with just month", async () => {
    mockedApiGet.mockResolvedValueOnce({ events: [], total: 0 } as never);
    await getEvents("2026-07");
    expect(mockedApiGet).toHaveBeenCalledWith(
      "/api/bills/dashboard/events?month=2026-07",
    );
  });

  it("appends all filter params when provided", async () => {
    mockedApiGet.mockResolvedValueOnce({ events: [], total: 0 } as never);
    await getEvents("2026-07", {
      partner_id: "partner_a",
      type: "bill",
      category: "Housing",
      from: "2026-07-01",
      to: "2026-07-31",
      order: "desc",
      limit: 100,
    });
    const url = mockedApiGet.mock.calls[0][0];
    expect(url).toContain("month=2026-07");
    // Filter keyed by partner_id — label is display-only.
    expect(url).toContain("partner_id=partner_a");
    expect(url).toContain("type=bill");
    expect(url).toContain("category=Housing");
    expect(url).toContain("from=2026-07-01");
    expect(url).toContain("to=2026-07-31");
    expect(url).toContain("order=desc");
    expect(url).toContain("limit=100");
  });

  it("omits undefined filters", async () => {
    mockedApiGet.mockResolvedValueOnce({ events: [], total: 0 } as never);
    await getEvents("2026-07", { partner_id: "partner_a" });
    const url = mockedApiGet.mock.calls[0][0];
    expect(url).not.toContain("type=");
    expect(url).not.toContain("category=");
    expect(url).not.toContain("from=");
    expect(url).not.toContain("to=");
    expect(url).not.toContain("order=");
    expect(url).not.toContain("limit=");
  });
});

describe("getEvent", () => {
  it("calls /api/bills/dashboard/event with id + month", async () => {
    mockedApiGet.mockResolvedValueOnce({} as never);
    await getEvent("evt-123", "2026-07");
    expect(mockedApiGet).toHaveBeenCalledWith(
      "/api/bills/dashboard/event?id=evt-123&month=2026-07",
    );
  });
});
