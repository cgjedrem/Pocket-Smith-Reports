import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("production same-origin API routing", () => {
  it("routes JSON and PDF requests through the frontend origin", async () => {
    vi.stubEnv("VITE_API_URL", "");
    vi.resetModules();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response('{"configured":false}', {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }))
      .mockResolvedValueOnce(new Response("%PDF-1.7", {
        status: 200,
        headers: { "Content-Type": "application/pdf" },
      }));
    vi.stubGlobal("fetch", fetchMock);

    const { apiGet } = await import("../src/api/client");
    const { exportPdf } = await import("../src/api/reports");
    await expect(apiGet("/api/settings/api-key")).resolves.toEqual({
      configured: false,
    });
    await exportPdf("2026-04");

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/settings/api-key",
      "/api/reports/monthly/2026-04/pdf",
    ]);
  });
});
