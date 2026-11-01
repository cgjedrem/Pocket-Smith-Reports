import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { useRunway } from "@/hooks/useRunway";
import { deferred, jsonResponse, runwayFixture, settingsFixture } from "@/components/bills/__tests__/runway-fixtures";
import { setAmountsHidden } from "@/lib/privacy-store";

let resultGet: Mock<() => Promise<Response>>;
let settingsGet: Mock<() => Promise<Response>>;
let settingsPut: Mock<(init: RequestInit) => Promise<Response>>;
let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  resultGet = vi.fn(async () => jsonResponse(runwayFixture()));
  settingsGet = vi.fn(async () => jsonResponse(settingsFixture()));
  settingsPut = vi.fn(async () => jsonResponse(settingsFixture()));
  fetchMock = vi.fn((url: string, init: RequestInit) => {
    const path = new URL(url, "http://fixture.test").pathname;
    if (path === "/api/bills/runway" && init.method === "GET") return resultGet();
    if (path === "/api/settings/runway" && init.method === "GET") return settingsGet();
    if (path === "/api/settings/runway" && init.method === "PUT") return settingsPut(init);
    throw new Error("Unexpected API route");
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => { act(() => setAmountsHidden(false)); vi.unstubAllGlobals(); });

describe("useRunway", () => {
  it("loads independent no-store endpoints without display-window parameters", async () => {
    const { result } = renderHook(useRunway);
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.settingsLoading).toBe(false));
    expect(result.current.data?.household.runway_display).toBe("1.3");
    expect(result.current.draftIds).toEqual(["1100001", "1100006"]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    for (const [url, init] of fetchMock.mock.calls) {
      expect(url).not.toContain("?");
      expect(init.cache).toBe("no-store");
    }
  });

  it("keeps result failure local and retries with static safe error text", async () => {
    resultGet.mockResolvedValueOnce(jsonResponse({ detail: "raw money 123456" }, 500));
    const { result } = renderHook(useRunway);
    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.error).not.toContain("123456");
    expect(result.current.settings).not.toBeNull();
    await act(() => result.current.refresh());
    expect(result.current.data?.household.runway_display).toBe("1.3");
    expect(result.current.error).toBeNull();
  });

  it("blocks save after settings-load failure until retry succeeds", async () => {
    settingsGet.mockResolvedValueOnce(jsonResponse({ detail: "unreadable" }, 500));
    const { result } = renderHook(useRunway);
    await waitFor(() => expect(result.current.settingsError).not.toBeNull());
    await act(() => result.current.save());
    expect(settingsPut).not.toHaveBeenCalled();
    expect(result.current.data).not.toBeNull();
    await act(() => result.current.retrySettings());
    expect(result.current.settingsError).toBeNull();
    expect(result.current.draftIds).toEqual(["1100001", "1100006"]);
  });

  it("preserves draft and saved result after failed save, then refreshes only result on success", async () => {
    settingsPut.mockResolvedValueOnce(jsonResponse({ detail: "raw -123456" }, 400));
    const { result } = renderHook(useRunway);
    await waitFor(() => expect(result.current.settingsLoading).toBe(false));
    act(() => result.current.setDraftIds(["1100007"]));
    await act(() => result.current.save());
    expect(result.current.saveError).not.toContain("123456");
    expect(result.current.draftIds).toEqual(["1100007"]);
    expect(result.current.settings?.liquid_account_ids).toEqual(["1100001", "1100006"]);
    expect(result.current.data?.selected_account_ids).toEqual(["1100001", "1100006"]);
    settingsPut.mockResolvedValueOnce(jsonResponse({ ...settingsFixture(), liquid_account_ids: ["1100007"] }));
    await act(() => result.current.save());
    expect(result.current.settings?.liquid_account_ids).toEqual(["1100007"]);
    expect(JSON.parse(settingsPut.mock.calls[0][0].body as string)).toEqual({ liquid_account_ids: ["1100007"] });
    expect(settingsPut.mock.calls[0][0].cache).toBe("no-store");
    expect(resultGet).toHaveBeenCalledTimes(2);
    expect(settingsGet).toHaveBeenCalledOnce();
  });

  it("rejects late pre-save results and clears retained figures after successful save", async () => {
    const old = deferred<Response>();
    const fresh = deferred<Response>();
    resultGet.mockReturnValueOnce(old.promise).mockReturnValueOnce(fresh.promise);
    const { result } = renderHook(useRunway);
    await waitFor(() => expect(result.current.settingsLoading).toBe(false));
    act(() => result.current.setDraftIds([]));
    settingsPut.mockResolvedValueOnce(jsonResponse({ ...settingsFixture(), liquid_account_ids: [], selection_status: "empty" }));
    await act(() => result.current.save());
    await act(() => old.resolve(jsonResponse(runwayFixture())));
    expect(result.current.data).toBeNull();
    const latest = runwayFixture();
    latest.selected_account_ids = [];
    latest.selection_status = "empty";
    await act(() => fresh.resolve(jsonResponse(latest)));
    expect(result.current.data?.selection_status).toBe("empty");
  });

  it("ignores overlapping result failures and late settings reads", async () => {
    const old = deferred<Response>();
    settingsGet.mockReturnValueOnce(old.promise);
    const { result } = renderHook(useRunway);
    await act(() => result.current.retrySettings());
    act(() => result.current.setDraftIds(["1100007"]));
    await act(() => old.resolve(jsonResponse(settingsFixture())));
    expect(result.current.draftIds).toEqual(["1100007"]);
    const staleResult = deferred<Response>();
    resultGet.mockReturnValueOnce(staleResult.promise);
    act(() => { void result.current.refresh(); });
    await act(() => result.current.refresh());
    await act(() => staleResult.reject(new Error("late failure")));
    expect(result.current.error).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it("does not refetch or change drafts on privacy toggles", async () => {
    const { result, rerender } = renderHook(useRunway);
    await waitFor(() => expect(result.current.settingsLoading).toBe(false));
    act(() => result.current.setDraftIds(["1100007"]));
    act(() => setAmountsHidden(true));
    rerender();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(result.current.draftIds).toEqual(["1100007"]);
  });

  it("blocks duplicate saves and ignores results after unmount", async () => {
    const pending = deferred<Response>();
    settingsPut.mockReturnValue(pending.promise);
    const { result, unmount } = renderHook(useRunway);
    await waitFor(() => expect(result.current.settingsLoading).toBe(false));
    act(() => result.current.setDraftIds([]));
    act(() => { void result.current.save(); void result.current.save(); });
    expect(settingsPut).toHaveBeenCalledOnce();
    unmount();
    await act(() => pending.resolve(jsonResponse(settingsFixture())));
    expect(resultGet).toHaveBeenCalledOnce();
  });
});
