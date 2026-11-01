// BillsPage tests — mock hooks + bills-source.

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/hooks/useBills", () => ({
  useBillsSnapshot: vi.fn(),
  useBillsEvents: vi.fn(),
  useBillsEvent: vi.fn(() => ({
    event: null,
    loading: false,
    error: null,
    notFound: false,
    refetch: vi.fn(),
  })),
}));

vi.mock("@/lib/bills-source", () => ({
  hydrate: vi.fn(),
  reset: vi.fn(),
  subscribe: vi.fn(() => () => {}),
  getMonths: vi.fn(() => []),
  getAllEvents: vi.fn(() => []),
}));

vi.mock("@/hooks/useBillsSourceSubscription", () => ({
  useBillsSourceSubscription: vi.fn(() => 0),
}));

import { useBillsEvents, useBillsSnapshot } from "@/hooks/useBills";
import { BillsPage } from "@/pages/BillsPage";
import { ApiError } from "@/types/api";
import { jsonResponse, runwayFixture, settingsFixture } from "@/components/bills/__tests__/runway-fixtures";

const mockedSnap = vi.mocked(useBillsSnapshot);
const mockedEvents = vi.mocked(useBillsEvents);
let runwayFetch: ReturnType<typeof vi.fn>;

function snapPayload() {
  const now = new Date();
  const month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  return {
    schema_version: 1,
    month,
    month_label: "Current",
    is_past: true,
    is_current: false,
    is_future: false,
    synced_at: new Date().toISOString(),
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

function currentMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

beforeEach(() => {
  vi.clearAllMocks();
  runwayFetch = vi.fn(async (url: string, init: RequestInit) => {
    const path = new URL(url, "http://fixture.test").pathname;
    if (path === "/api/bills/runway" && init.method === "GET") return jsonResponse(runwayFixture());
    if (path === "/api/settings/runway" && init.method === "GET") return jsonResponse(settingsFixture());
    throw new Error("Unexpected API route");
  });
  vi.stubGlobal("fetch", runwayFetch);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function renderPage(initialPath = "/bills") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/bills" element={<BillsPage />} />
        <Route path="/sync" element={<div>Sync page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("BillsPage", () => {
  it("renders title + snapshot data on 200", async () => {
    mockedSnap.mockReturnValue({
      snapshots: [snapPayload() as never],
      months: ["2026-07"],
      loading: false,
      error: null,
      notFound: false,
      refetch: vi.fn(),
    });
    mockedEvents.mockReturnValue({
      events: [],
      total: 0,
      loading: false,
      error: null,
      refetch: vi.fn(),
    });
    renderPage();
    expect(screen.getByRole("heading", { name: /bills/i })).toBeInTheDocument();
    // Mock snapshot has 0 events → BillsDashboard renders its 3-view toggle.
    await waitFor(() =>
      expect(screen.getByText(/^Grid$/)).toBeInTheDocument(),
    );
    await screen.findByText("1.3 months");
  });

  it("renders 404 takeover alert", async () => {
    mockedSnap.mockReturnValue({
      snapshots: [],
      months: [currentMonth()],
      loading: false,
      error: null,
      notFound: true,
      refetch: vi.fn(),
    });
    mockedEvents.mockReturnValue({
      events: [],
      total: 0,
      loading: false,
      error: null,
      refetch: vi.fn(),
    });
    renderPage();
    expect(screen.getByText(new RegExp(`no snapshot for ${currentMonth()}`, "i"))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run sync/i })).toBeInTheDocument();
    await screen.findByText("1.3 months");
  });

  it("renders error + retry on 500", async () => {
    mockedSnap.mockReturnValue({
      snapshots: [],
      months: ["2026-07"],
      loading: false,
      error: new ApiError("Cannot reach server"),
      notFound: false,
      refetch: vi.fn(),
    });
    mockedEvents.mockReturnValue({
      events: [],
      total: 0,
      loading: false,
      error: null,
      refetch: vi.fn(),
    });
    renderPage();
    expect(screen.getByRole("alert")).toHaveTextContent("Cannot reach server");
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    await screen.findByText("1.3 months");
  });

  it("passes currentMonth to useBillsSnapshot", async () => {
    mockedSnap.mockReturnValue({
      snapshots: [snapPayload() as never],
      months: [currentMonth()],
      loading: false,
      error: null,
      notFound: false,
      refetch: vi.fn(),
    });
    mockedEvents.mockReturnValue({
      events: [],
      total: 0,
      loading: false,
      error: null,
      refetch: vi.fn(),
    });
    renderPage();
    expect(mockedSnap).toHaveBeenCalledWith(currentMonth(), 3, 12);
    await screen.findByText("1.3 months");
  });

  it("shows runway despite missing current Bills snapshot", async () => {
    mockedSnap.mockReturnValue({
      snapshots: [], months: [currentMonth()], loading: false,
      error: null, notFound: true, refetch: vi.fn(),
    });
    renderPage();
    await screen.findByText("1.3 months");
    expect(screen.getByRole("button", { name: /run sync/i })).toBeVisible();
    expect(runwayFetch).toHaveBeenCalledTimes(2);
  });

  it("keeps legacy Bills usable during runway-only failure and retry", async () => {
    mockedSnap.mockReturnValue({
      snapshots: [snapPayload() as never], months: [currentMonth()], loading: false,
      error: null, notFound: false, refetch: vi.fn(),
    });
    runwayFetch.mockResolvedValueOnce(jsonResponse({}, 500));
    renderPage();
    await screen.findByRole("button", { name: "Retry runway" });
    expect(screen.getByText(/^Grid$/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Retry runway" }));
    await screen.findByText("1.3 months");
    expect(mockedSnap.mock.results[0].value.refetch).not.toHaveBeenCalled();
  });

  it("retains runway drafts across Bills branches and display-window changes", async () => {
    const state = {
      snapshots: [] as ReturnType<typeof snapPayload>[], months: [currentMonth()], loading: true,
      error: null, notFound: false, refetch: vi.fn(),
    };
    mockedSnap.mockReturnValue(state);
    const view = renderPage();
    await screen.findByText("1.3 months");
    fireEvent.click(screen.getByText("Liquid account settings"));
    fireEvent.click(screen.getByRole("checkbox", { name: /Extra reserve/ }));
    mockedSnap.mockReturnValue({ ...state, loading: false, snapshots: [snapPayload() as never] });
    view.rerender(
      <MemoryRouter initialEntries={["/bills"]}>
        <Routes><Route path="/bills" element={<BillsPage />} /></Routes>
      </MemoryRouter>,
    );
    expect(screen.getByRole("checkbox", { name: /Extra reserve/ })).toBeChecked();
    fireEvent.change(screen.getByLabelText("Past months"), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply window" }));
    expect(mockedSnap).toHaveBeenLastCalledWith(currentMonth(), 1, 12);
    expect(runwayFetch).toHaveBeenCalledTimes(2);
  });
});
