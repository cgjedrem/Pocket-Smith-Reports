import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({ apiGet: vi.fn() }));

import { apiGet } from "@/api/client";
import { getEconomyLifestyleCreep, getLifestyleCreep } from "@/api/lifestyle-creep";
import { jsonResponse } from "@/components/bills/__tests__/runway-fixtures";
import { economyFixture, lifestyleFixture } from "@/test/fixtures/lifestyle-creep";
import { ApiError } from "@/types/api";

const get = vi.mocked(apiGet);
const noStore = { cache: "no-store" };
beforeEach(() => vi.resetAllMocks());
afterEach(() => vi.unstubAllGlobals());

describe("getLifestyleCreep", () => {
  it("encodes target, threshold, and both reference bounds; keeps the uncached contract", async () => {
    get.mockResolvedValue(lifestyleFixture());
    await getLifestyleCreep("2026-11", "+020.50", "2026-05", "2026-10");
    expect(get).toHaveBeenCalledWith(
      "/api/bills/lifestyle-creep?month=2026-11&threshold_percent=%2B020.50&reference_start=2026-05&reference_end=2026-10",
      noStore,
    );
    await getLifestyleCreep("2026-11", "", "", "2026/10");
    expect(get).toHaveBeenLastCalledWith(
      "/api/bills/lifestyle-creep?month=2026-11&threshold_percent=&reference_start=&reference_end=2026%2F10", noStore,
    );
  });

  describe("getEconomyLifestyleCreep", () => {
    it("opts in to report grouping with encoded selection and no-store without changing the CC wrapper", async () => {
      const data = economyFixture();
      get.mockResolvedValue(data);
      expect(await getEconomyLifestyleCreep("2026/10", "+020.5", "2026-07", "2026-09")).toBe(data);
      expect(get).toHaveBeenCalledExactlyOnceWith(
        "/api/bills/lifestyle-creep?month=2026%2F10&threshold_percent=%2B020.5&reference_start=2026-07&reference_end=2026-09&grouping=report",
        noStore,
      );
    });

    it("sends grouping and no-store to fetch on every read including Retry", async () => {
      const client = await vi.importActual<typeof import("@/api/client")>("@/api/client");
      get.mockImplementation(client.apiGet);
      const fetchMock = vi.fn(async (_url: string, _init: RequestInit) => jsonResponse(economyFixture()));
      vi.stubGlobal("fetch", fetchMock);
      for (let attempt = 0; attempt < 2; attempt++) {
        await getEconomyLifestyleCreep("2026-10", "20", "2026-07", "2026-09");
      }
      expect(fetchMock).toHaveBeenCalledTimes(2);
      for (const [url, init] of fetchMock.mock.calls) {
        expect(new URL(url).searchParams.get("grouping")).toBe("report");
        expect(init).toMatchObject({ method: "GET", cache: "no-store" });
      }
    });
  });
  it("encodes month and raw threshold, including leading plus", async () => {
    get.mockResolvedValue(lifestyleFixture());
    await getLifestyleCreep("2026/10", "+020.50", "2026-07", "2026-09");
    expect(get).toHaveBeenCalledWith(
      "/api/bills/lifestyle-creep?month=2026%2F10&threshold_percent=%2B020.50&reference_start=2026-07&reference_end=2026-09",
      noStore,
    );
    await getLifestyleCreep("2026-10", "", "2026-07", "2026-09");
    expect(get).toHaveBeenLastCalledWith(
      "/api/bills/lifestyle-creep?month=2026-10&threshold_percent=&reference_start=2026-07&reference_end=2026-09",
      noStore,
    );
  });

  it("sends an uncached GET to fetch, so Retry and selection changes never reuse a browser cache entry", async () => {
    const client = await vi.importActual<typeof import("@/api/client")>("@/api/client");
    get.mockImplementation(client.apiGet);
    const fetchMock = vi.fn(async (_url: string, _init: RequestInit) => jsonResponse(lifestyleFixture()));
    vi.stubGlobal("fetch", fetchMock);
    await getLifestyleCreep("2026-10", "20", "2026-07", "2026-09");
    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(new URL(url).pathname).toBe("/api/bills/lifestyle-creep");
    expect(new URL(url).searchParams.get("reference_start")).toBe("2026-07");
    expect(new URL(url).searchParams.get("reference_end")).toBe("2026-09");
    expect(init.method).toBe("GET");
    expect(init.cache).toBe("no-store");
  });

  it("preserves decimal strings and the original response", async () => {
    const response = lifestyleFixture();
    get.mockResolvedValue(response);
    expect(await getLifestyleCreep("2026-10", "20", "2026-07", "2026-09")).toBe(response);
  });

  it.each([400, 500])("preserves ApiError for HTTP %s", async (status) => {
    const error = new ApiError("Synthetic failure", status);
    get.mockRejectedValue(error);
    await expect(getLifestyleCreep("2026-10", "20", "2026-07", "2026-09")).rejects.toBe(error);
  });
});
