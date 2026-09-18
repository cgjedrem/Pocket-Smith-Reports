// F2 — smoke test. Page renders without errors. F2-FE: now aliases BillsPage → wraps in Router.

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

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
  it("renders the 404 takeover (snapshot missing)", () => {
    render(
      <MemoryRouter initialEntries={["/bills-preview"]}>
        <BillsPreviewPage />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: /bills/i })).toBeInTheDocument();
    expect(screen.getByText(/no snapshot for/i)).toBeInTheDocument();
  });

  it("renders the Run sync button", () => {
    render(
      <MemoryRouter initialEntries={["/bills-preview"]}>
        <BillsPreviewPage />
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("button", { name: /run sync/i }),
    ).toBeInTheDocument();
  });
});
