// SyncPage tests — F10 / AC33-AC34.
// Mock all API calls — no real network.

import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SyncPage } from "@/pages/SyncPage";
import { ApiError } from "@/types/api";
import type { SyncStatus } from "@/types/api";

// Mock sync API module.
vi.mock("@/api/sync", () => ({
  getSyncStatus: vi.fn(),
  triggerSync: vi.fn(),
}));

import { getSyncStatus, triggerSync } from "@/api/sync";

// Helpers — build status objects.
function makeStatus(over: Partial<SyncStatus> = {}): SyncStatus {
  return {
    status: "success",
    last_sync: "2026-07-27T12:00:00Z",
    start_month: "2026-04",
    end_month: "2026-07",
    months_synced: 4,
    row_counts: {
      transactions: 100,
      events: 5,
      budget: 12,
      categories: 40,
      accounts: 3,
    },
    errors: [],
    duration_ms: 1500,
    ...over,
  };
}

// 404-shaped error — SyncPage treats detail w/ "no sync" as empty state.
function noSyncError(): ApiError {
  return new ApiError("no sync has been run yet", 404);
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("SyncPage — AC33 render", () => {
  it("renders title + month pickers + sync button", async () => {
    vi.mocked(getSyncStatus).mockResolvedValue(makeStatus());
    render(<SyncPage />);
    expect(screen.getByRole("heading", { name: "Sync" })).toBeInTheDocument();
    // MonthPicker uses <span> label, not <label>.
    expect(screen.getByText("Start month")).toBeInTheDocument();
    expect(screen.getByText("End month")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sync" })).toBeInTheDocument();
    await waitFor(() => expect(getSyncStatus).toHaveBeenCalled());
  });

  it("404 → empty state 'No sync yet'", async () => {
    vi.mocked(getSyncStatus).mockRejectedValue(noSyncError());
    render(<SyncPage />);
    await waitFor(() =>
      expect(screen.getByText(/No sync yet/i)).toBeInTheDocument()
    );
  });

  it("network error → shows error alert", async () => {
    vi.mocked(getSyncStatus).mockRejectedValue(new ApiError("Cannot reach server", 500));
    render(<SyncPage />);
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Cannot reach server")
    );
  });
});

describe("SyncPage — AC34 polling", () => {
  it("running status → starts polling, stops on success", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    // First call: running. Subsequent: success.
    vi.mocked(getSyncStatus)
      .mockResolvedValueOnce(makeStatus({ status: "running" }))
      .mockResolvedValueOnce(makeStatus({ status: "success" }));

    render(<SyncPage />);
    // Mount fetch — running.
    await waitFor(() => expect(getSyncStatus).toHaveBeenCalledTimes(1));
    expect(screen.getByText("Running")).toBeInTheDocument();

    // Advance past 2s poll interval.
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });
    await waitFor(() => expect(getSyncStatus).toHaveBeenCalledTimes(2));
    expect(screen.getByText("Success")).toBeInTheDocument();
    // No further polls after terminal state.
    const callsAfterStop = getSyncStatus.mock.calls.length;
    await act(async () => {
      vi.advanceTimersByTime(4000);
    });
    expect(getSyncStatus.mock.calls.length).toBe(callsAfterStop);
  });

  it("running → stops on failed, shows errors", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(getSyncStatus)
      .mockResolvedValueOnce(makeStatus({ status: "running" }))
      .mockResolvedValueOnce(
        makeStatus({ status: "failed", errors: ["boom", "kaboom"] })
      );

    render(<SyncPage />);
    await waitFor(() => expect(getSyncStatus).toHaveBeenCalledTimes(1));
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });
    await waitFor(() => expect(screen.getByText("Failed")).toBeInTheDocument());
    expect(screen.getByText("boom")).toBeInTheDocument();
    expect(screen.getByText("kaboom")).toBeInTheDocument();
  });
});

describe("SyncPage — success status", () => {
  it("shows row counts table", async () => {
    vi.mocked(getSyncStatus).mockResolvedValue(makeStatus());
    render(<SyncPage />);
    await waitFor(() => expect(screen.getByText("Success")).toBeInTheDocument());
    expect(screen.getByText("Transactions")).toBeInTheDocument();
    expect(screen.getByText("100")).toBeInTheDocument();
    expect(screen.getByText("Accounts")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });
});

describe("SyncPage — sync button", () => {
  it("triggers triggerSync then polls", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    // Mount: empty (no sync). After trigger: running → success.
    vi.mocked(getSyncStatus)
      .mockRejectedValueOnce(noSyncError()) // mount → throws → empty
      .mockResolvedValueOnce(makeStatus({ status: "running" }))
      .mockResolvedValueOnce(makeStatus({ status: "success" }));
    vi.mocked(triggerSync).mockResolvedValue(makeStatus({ status: "running" }));

    render(<SyncPage />);
    await waitFor(() => expect(screen.getByText(/No sync yet/i)).toBeInTheDocument());

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Sync" }));
    });
    await waitFor(() => expect(triggerSync).toHaveBeenCalled());
    // Polling starts — first poll returns running.
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });
    await waitFor(() => expect(screen.getByText("Running")).toBeInTheDocument());
    // Next poll → success.
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });
    await waitFor(() => expect(screen.getByText("Success")).toBeInTheDocument());
  });

  it("start > end → client-side error, no API call", async () => {
    vi.mocked(getSyncStatus).mockRejectedValue(noSyncError());
    render(<SyncPage />);
    await waitFor(() => expect(screen.getByText(/No sync yet/i)).toBeInTheDocument());

    // MonthPicker: Popover + two Selects (month + year).
    // Open end month picker, change month to March → end < start → error.
    const endTrigger = screen.getByText("2026-07").closest("button")!;
    await act(async () => {
      fireEvent.click(endTrigger);
    });
    // Wait for popover content, then open month select.
    await waitFor(() => {
      expect(screen.getAllByRole("combobox").length).toBeGreaterThan(0);
    });
    await act(async () => {
      fireEvent.click(screen.getAllByRole("combobox")[0]);
    });
    // Wait for option listbox, select "March".
    await waitFor(() => {
      expect(screen.getByRole("option", { name: "March" })).toBeInTheDocument();
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("option", { name: "March" }));
    });
    // start "2026-04" > end "2026-03" → validation error.
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Sync" }));
    });
    expect(triggerSync).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(/before or equal/i);
  });
});