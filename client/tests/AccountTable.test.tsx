// AccountTable tests — F12 / AC37-AC38.
// Render, excluded greyed, pagination, per-row save.

import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AccountTable } from "@/components/AccountTable";
import { ApiError } from "@/types/api";
import type { Account, AccountList, Partner, PartnerList as PartnerListT } from "@/types/api";

// Mock accounts + partners API.
vi.mock("@/api/accounts", () => ({
  listAccounts: vi.fn(),
  updateBinding: vi.fn(),
}));

vi.mock("@/api/partners", () => ({
  listPartners: vi.fn(),
}));

import { listAccounts, updateBinding } from "@/api/accounts";
import { listPartners } from "@/api/partners";

function makeAccount(over: Partial<Account> = {}): Account {
  return {
    id: "acc-1",
    name: "Checking",
    partner_id: null,
    type: null,
    excluded: false,
    ...over,
  };
}

const PARTNERS: Partner[] = [
  { id: "alice", label: "Alice" },
  { id: "bob", label: "Bob" },
];

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listPartners).mockResolvedValue({ partners: PARTNERS } as PartnerListT);
});

describe("AccountTable — AC37 render", () => {
  it("renders accounts + headers", async () => {
    vi.mocked(listAccounts).mockResolvedValue({
      accounts: [
        makeAccount({ id: "a1", name: "Checking" }),
        makeAccount({ id: "a2", name: "Savings" }),
      ],
    });
    render(<AccountTable />);
    await waitFor(() => expect(screen.getByText("Checking")).toBeInTheDocument());
    expect(screen.getByText("Savings")).toBeInTheDocument();
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Partner")).toBeInTheDocument();
    expect(screen.getByText("Type")).toBeInTheDocument();
    expect(screen.getByText("Excluded")).toBeInTheDocument();
  });

  it("empty → empty state", async () => {
    vi.mocked(listAccounts).mockResolvedValue({ accounts: [] });
    render(<AccountTable />);
    await waitFor(() =>
      expect(screen.getByText(/No accounts/i)).toBeInTheDocument()
    );
  });
});

describe("AccountTable — AC38 excluded greyed", () => {
  it("excluded row → opacity 0.5", async () => {
    vi.mocked(listAccounts).mockResolvedValue({
      accounts: [makeAccount({ id: "a1", name: "Old", excluded: true })],
    });
    render(<AccountTable />);
    await waitFor(() => expect(screen.getByText("Old")).toBeInTheDocument());
    const row = screen.getByText("Old").closest("tr");
    expect(row).not.toBeNull();
    // shadcn uses Tailwind opacity-50 class, not inline style.
    expect(row?.className).toContain("opacity-50");
  });

  it("included row → opacity 1", async () => {
    vi.mocked(listAccounts).mockResolvedValue({
      accounts: [makeAccount({ id: "a1", name: "Active", excluded: false })],
    });
    render(<AccountTable />);
    await waitFor(() => expect(screen.getByText("Active")).toBeInTheDocument());
    const row = screen.getByText("Active").closest("tr");
    // No opacity class when not excluded.
    expect(row?.className).not.toContain("opacity-50");
  });
});

describe("AccountTable — pagination", () => {
  // 12 accounts → 2 pages (10 + 2).
  function makeMany(n: number): Account[] {
    return Array.from({ length: n }, (_, i) =>
      makeAccount({ id: `a${i}`, name: `Acc${i}` })
    );
  }

  it("prev disabled on page 1, next advances", async () => {
    vi.mocked(listAccounts).mockResolvedValue({ accounts: makeMany(12) });
    render(<AccountTable />);
    await waitFor(() => expect(screen.getByText("Acc0")).toBeInTheDocument());
    const prev = screen.getByRole("button", { name: "Prev" });
    const next = screen.getByRole("button", { name: "Next" });
    expect(prev).toBeDisabled();
    expect(next).not.toBeDisabled();

    await act(async () => {
      fireEvent.click(next);
    });
    await waitFor(() => expect(screen.getByText("Acc10")).toBeInTheDocument());
    expect(screen.queryByText("Acc0")).not.toBeInTheDocument();
  });

  it("next disabled on last page", async () => {
    vi.mocked(listAccounts).mockResolvedValue({ accounts: makeMany(12) });
    render(<AccountTable />);
    await waitFor(() => expect(screen.getByText("Acc0")).toBeInTheDocument());
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Next" }));
    });
    await waitFor(() => expect(screen.getByText("Acc10")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Prev" })).not.toBeDisabled();
  });

  it("≤10 accounts → no pagination controls", async () => {
    vi.mocked(listAccounts).mockResolvedValue({ accounts: makeMany(5) });
    render(<AccountTable />);
    await waitFor(() => expect(screen.getByText("Acc0")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Prev" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Next" })).not.toBeInTheDocument();
  });
});

describe("AccountTable — per-row save", () => {
  it("change partner + save → updateBinding + refresh", async () => {
    vi.mocked(listAccounts)
      .mockResolvedValueOnce({
        accounts: [makeAccount({ id: "a1", name: "Checking", partner_id: null })],
      })
      .mockResolvedValueOnce({
        accounts: [makeAccount({ id: "a1", name: "Checking", partner_id: "alice" })],
      });
    vi.mocked(updateBinding).mockResolvedValue(
      makeAccount({ id: "a1", name: "Checking", partner_id: "alice" })
    );

    render(<AccountTable />);
    await waitFor(() => expect(screen.getByText("Checking")).toBeInTheDocument());

    // Radix Select — keyboard open (ArrowDown), then click option.
    const triggers = screen.getAllByRole("combobox");
    await act(async () => {
      fireEvent.keyDown(triggers[0], { key: "ArrowDown" });
      fireEvent.keyUp(triggers[0], { key: "ArrowDown" });
    });
    await waitFor(() => expect(screen.getByText("Alice")).toBeInTheDocument());
    await act(async () => {
      fireEvent.click(screen.getByText("Alice"));
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Save" }));
    });

    await waitFor(() => expect(updateBinding).toHaveBeenCalled());
    expect(updateBinding).toHaveBeenCalledWith("a1", {
      partner_id: "alice",
      type: null,
      excluded: false,
    });
    // Refresh called — listAccounts called twice.
    expect(listAccounts).toHaveBeenCalledTimes(2);
  });

  it("save error → error alert shown", async () => {
    vi.mocked(listAccounts).mockResolvedValue({
      accounts: [makeAccount({ id: "a1", name: "Checking" })],
    });
    vi.mocked(updateBinding).mockRejectedValue(
      new ApiError("invalid partner", 400)
    );

    render(<AccountTable />);
    await waitFor(() => expect(screen.getByText("Checking")).toBeInTheDocument());

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Save" }));
    });
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("invalid partner")
    );
  });
});