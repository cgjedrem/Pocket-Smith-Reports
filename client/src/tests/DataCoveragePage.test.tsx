import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DataCoveragePage } from "@/pages/DataCoveragePage";
import { issue, jsonResponse, runwayFixture, settingsFixture, deferred } from "@/components/bills/__tests__/runway-fixtures";

let payload: ReturnType<typeof runwayFixture>;
let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  payload = runwayFixture();
  fetchMock = vi.fn(async (url: string, init: RequestInit) => {
    const path = new URL(url, "http://fixture.test").pathname;
    if (path === "/api/bills/runway" && init.method === "GET") return jsonResponse(payload);
    if (path === "/api/settings/runway" && init.method === "GET") return jsonResponse(settingsFixture());
    throw new Error("Unexpected API route");
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/data-coverage"]}>
      <Routes>
        <Route path="/data-coverage" element={<DataCoveragePage />} />
        <Route path="/bills" element={<Link to="/data-coverage">Open Data coverage</Link>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("DataCoveragePage", () => {
  it("shows loading state before source diagnostics arrive", async () => {
    const pending = deferred<Response>();
    fetchMock.mockImplementation(async (url: string, init: RequestInit) => {
      const path = new URL(url, "http://fixture.test").pathname;
      if (path === "/api/bills/runway" && init.method === "GET") return pending.promise;
      if (path === "/api/settings/runway" && init.method === "GET") return jsonResponse(settingsFixture());
      throw new Error("Unexpected API route");
    });

    renderPage();
    expect(screen.getByRole("status")).toHaveTextContent("Loading data coverage");
    await act(() => pending.resolve(jsonResponse(payload)));
    expect(await screen.findByRole("region", { name: "July 2026 coverage" })).toBeVisible();
  });

  it("renders coverage, provenance dates, and safely formatted issues without amounts", async () => {
    payload.observations[0].coverage = "unverified";
    payload.observations[0].issues = [
      issue("coverage_unverified", { month: "2026-07" }),
      issue("source_date_unknown", { month: "2026-07" }),
      issue("source_times_differ", { month: "2026-07" }),
    ];
    payload.issues = [issue("source_date_unknown")];
    renderPage();

    const july = await screen.findByRole("region", { name: "July 2026 coverage" });
    expect(within(july).getByText(/Coverage: unverified/)).toBeVisible();
    expect(within(july).getByText(/Month coverage unverified — recorded transactions only/)).toBeVisible();
    expect(within(july).getByText(/Source collection date unknown/)).toBeVisible();
    expect(within(july).getByText(/Sources collected at different times/)).toBeVisible();
    expect(screen.getByText(/Runway calculated: 2026-10-31/)).toBeVisible();
    expect(screen.getByText(/Catalog collected: Unknown · unknown/)).toBeVisible();
    expect(screen.getByText(/Coverage dates: 2026-07-01 – 2026-07-31/)).toBeVisible();
    expect(screen.queryByText(/70,000|90,000|120,000/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Monthly net spending/)).not.toBeInTheDocument();
  });

  it("shows an explicit empty state when no monthly observations are returned", async () => {
    payload.observations = [];
    payload.included_months = [];
    payload.included_month_count = 0;
    renderPage();
    expect(await screen.findByText("No monthly coverage observations available.")).toBeVisible();
  });

  it("opens the routed page from a link", async () => {
    render(
      <MemoryRouter initialEntries={["/bills"]}>
        <Routes>
          <Route path="/data-coverage" element={<DataCoveragePage />} />
          <Route path="/bills" element={<Link to="/data-coverage">Data coverage</Link>} />
        </Routes>
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("link", { name: "Data coverage" }));
    expect(await screen.findByRole("heading", { name: "Data coverage" })).toBeVisible();
  });

  it("shows error and retries the runway source request", async () => {
    let failed = true;
    fetchMock.mockImplementation(async (url: string, init: RequestInit) => {
      const path = new URL(url, "http://fixture.test").pathname;
      if (path === "/api/bills/runway" && init.method === "GET") return failed ? jsonResponse({}, 500) : jsonResponse(payload);
      if (path === "/api/settings/runway" && init.method === "GET") return jsonResponse(settingsFixture());
      throw new Error("Unexpected API route");
    });

    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load runway");
    failed = false;
    fireEvent.click(screen.getByRole("button", { name: "Retry data coverage" }));
    expect(await screen.findByRole("region", { name: "July 2026 coverage" })).toBeVisible();
    expect(fetchMock.mock.calls.filter(([, init]) => init.method === "GET")).toHaveLength(3);
  });
});
