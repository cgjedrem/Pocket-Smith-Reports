// PartnerList tests — F12 / AC36.
// CRUD + delete guards + empty state.

import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PartnerList } from "@/components/PartnerList";
import { ApiError } from "@/types/api";
import type { Partner, PartnerList as PartnerListT } from "@/types/api";

// Mock partners API.
vi.mock("@/api/partners", () => ({
  listPartners: vi.fn(),
  createPartner: vi.fn(),
  updatePartner: vi.fn(),
  deletePartner: vi.fn(),
}));

import {
  createPartner,
  deletePartner,
  listPartners,
  updatePartner,
} from "@/api/partners";

function makeList(partners: Partner[]): PartnerListT {
  return { partners };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

afterEach(() => {
  vi.spyOn(window, "confirm").mockRestore();
});

describe("PartnerList — AC36 render", () => {
  it("renders partners from API", async () => {
    vi.mocked(listPartners).mockResolvedValue(
      makeList([
        { id: "alice", label: "Alice" },
        { id: "bob", label: "Bob" },
      ])
    );
    render(<PartnerList />);
    await waitFor(() => expect(screen.getByText("Alice")).toBeInTheDocument());
    expect(screen.getByText("Bob")).toBeInTheDocument();
  });

  it("empty list → empty state", async () => {
    vi.mocked(listPartners).mockResolvedValue(makeList([]));
    render(<PartnerList />);
    await waitFor(() =>
      expect(screen.getByText(/No partners yet/i)).toBeInTheDocument()
    );
  });
});

describe("PartnerList — add partner", () => {
  it("fill form + submit → createPartner + refresh", async () => {
    // First load: empty. After create: 1 partner.
    vi.mocked(listPartners)
      .mockResolvedValueOnce(makeList([]))
      .mockResolvedValueOnce(makeList([{ id: "carol", label: "Carol" }]));
    vi.mocked(createPartner).mockResolvedValue({ id: "carol", label: "Carol" });

    render(<PartnerList />);
    await waitFor(() => expect(screen.getByText(/No partners yet/i)).toBeInTheDocument());

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Add Partner" }));
    });
    const input = screen.getByPlaceholderText("Partner label");
    await act(async () => {
      fireEvent.change(input, { target: { value: "Carol" } });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Save" }));
    });

    await waitFor(() => expect(createPartner).toHaveBeenCalledWith("Carol"));
    expect(screen.getByText("Carol")).toBeInTheDocument();
  });

  it("empty label submit → form validation error, no API call", async () => {
    vi.mocked(listPartners).mockResolvedValue(makeList([]));
    render(<PartnerList />);
    await waitFor(() => expect(screen.getByText(/No partners yet/i)).toBeInTheDocument());

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Add Partner" }));
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Save" }));
    });
    expect(createPartner).not.toHaveBeenCalled();
    expect(screen.getByText("label is required")).toBeInTheDocument();
  });
});

describe("PartnerList — edit partner", () => {
  it("edit → submit → updatePartner + refresh", async () => {
    vi.mocked(listPartners)
      .mockResolvedValueOnce(makeList([{ id: "alice", label: "Alice" }]))
      .mockResolvedValueOnce(makeList([{ id: "alice", label: "Alice2" }]));
    vi.mocked(updatePartner).mockResolvedValue({ id: "alice", label: "Alice2" });

    render(<PartnerList />);
    await waitFor(() => expect(screen.getByText("Alice")).toBeInTheDocument());

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    });
    const input = screen.getByPlaceholderText("Partner label");
    await act(async () => {
      fireEvent.change(input, { target: { value: "Alice2" } });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Save" }));
    });

    await waitFor(() => expect(updatePartner).toHaveBeenCalledWith("alice", "Alice2"));
    expect(screen.getByText("Alice2")).toBeInTheDocument();
  });
});

describe("PartnerList — delete partner", () => {
  it("confirm → deletePartner + refresh", async () => {
    vi.mocked(listPartners)
      .mockResolvedValueOnce(makeList([{ id: "alice", label: "Alice" }]))
      .mockResolvedValueOnce(makeList([]));
    vi.mocked(deletePartner).mockResolvedValue(undefined);
    window.confirm = vi.fn().mockReturnValue(true);

    render(<PartnerList />);
    await waitFor(() => expect(screen.getByText("Alice")).toBeInTheDocument());

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    });
    await waitFor(() => expect(deletePartner).toHaveBeenCalledWith("alice"));
    await waitFor(() => expect(screen.queryByText("Alice")).not.toBeInTheDocument());
  });

  it("cancel confirm → no delete", async () => {
    vi.mocked(listPartners).mockResolvedValue(makeList([{ id: "alice", label: "Alice" }]));
    vi.spyOn(window, "confirm").mockReturnValueOnce(false);

    render(<PartnerList />);
    await waitFor(() => expect(screen.getByText("Alice")).toBeInTheDocument());

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    });
    expect(deletePartner).not.toHaveBeenCalled();
    expect(screen.getByText("Alice")).toBeInTheDocument();
  });

  it("409 bound accounts → error shown", async () => {
    vi.mocked(listPartners).mockResolvedValue(makeList([{ id: "alice", label: "Alice" }]));
    vi.mocked(deletePartner).mockRejectedValue(
      new ApiError("partner has bound accounts", 409)
    );
    window.confirm = vi.fn().mockReturnValue(true);

    render(<PartnerList />);
    await waitFor(() => expect(screen.getByText("Alice")).toBeInTheDocument());

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    });
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("partner has bound accounts")
    );
  });

  it("409 last partner → error shown", async () => {
    vi.mocked(listPartners).mockResolvedValue(makeList([{ id: "alice", label: "Alice" }]));
    vi.mocked(deletePartner).mockRejectedValue(
      new ApiError("cannot delete last partner", 409)
    );
    window.confirm = vi.fn().mockReturnValue(true);

    render(<PartnerList />);
    await waitFor(() => expect(screen.getByText("Alice")).toBeInTheDocument());

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    });
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("cannot delete last partner")
    );
  });
});