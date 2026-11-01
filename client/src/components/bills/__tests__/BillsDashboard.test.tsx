// F2 — smoke test. Page renders without errors. F2-FE: now aliases BillsPage → wraps in Router.

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { runwayFixture, settingsFixture } from "./runway-fixtures";

vi.mock("@/api/runway", () => ({
  getRunway: vi.fn(async () => runwayFixture()),
  getRunwaySettings: vi.fn(async () => settingsFixture()),
  updateRunwaySettings: vi.fn(),
}));

vi.mock("@/hooks/useBills", () => ({
  useBillsSnapshot: vi.fn(() => ({
    snapshots: [],
    months: [],
    loading: false,
    error: null,
    notFound: true,
    refetch: vi.fn(),
  })),
  useBillsEvents: vi.fn(() => ({
    events: [],
    total: 0,
    loading: false,
    error: null,
    refetch: vi.fn(),
  })),
}));

import { BillsPreviewPage } from "@/pages/BillsPreviewPage";

describe("BillsPreviewPage", () => {
  it("renders the 404 takeover (snapshot missing)", async () => {
    render(
      <MemoryRouter initialEntries={["/bills-preview"]}>
        <BillsPreviewPage />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: /bills/i })).toBeInTheDocument();
    expect(screen.getByText(/no snapshot for/i)).toBeInTheDocument();
    await screen.findByText("1.3 months");
  });

  it("renders the Run sync button", async () => {
    render(
      <MemoryRouter initialEntries={["/bills-preview"]}>
        <BillsPreviewPage />
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("button", { name: /run sync/i }),
    ).toBeInTheDocument();
    await screen.findByText("1.3 months");
  });
});
