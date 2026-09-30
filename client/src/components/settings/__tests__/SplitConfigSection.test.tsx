// Common-economy split settings — SplitConfigSection.
// Covers: initial fetch populates fields, client-side sum-validation error
// path (never PUTs when shares don't sum to 100), successful save round-
// trip, 422/400 server error surfaced verbatim, and partner label
// resolution via the GET response's `labels` field (real names — not
// listPartners() id-mapped, since backend partner ids are the real ids,
// e.g. "alex", never literally "partner_a"/"partner_b").
//
// Uses fireEvent (no @testing-library/user-event dependency in this repo —
// see MonthPicker.test.tsx for the established pattern).

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SplitConfigResponse } from "@/types/api";

vi.mock("@/api/settings", () => ({
  getSplitConfig: vi.fn(),
  updateSplitConfig: vi.fn(),
}));

import { getSplitConfig, updateSplitConfig } from "@/api/settings";
import { SplitConfigSection } from "../SplitConfigSection";

const mockedGet = vi.mocked(getSplitConfig);
const mockedUpdate = vi.mocked(updateSplitConfig);

const DEFAULT_CONFIG: SplitConfigResponse = {
  enabled: false,
  shares: { partner_a: 50, partner_b: 50 },
  sections: ["home", "common", "trips"],
  labels: { partner_a: "Alex", partner_b: "Sam" },
};

function setup(config: SplitConfigResponse = DEFAULT_CONFIG) {
  mockedGet.mockResolvedValue(config);
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("SplitConfigSection", () => {
  it("loads and displays the persisted config", async () => {
    setup({
      enabled: true,
      shares: { partner_a: 60, partner_b: 40 },
      sections: ["home", "trips"],
      labels: { partner_a: "Alex", partner_b: "Sam" },
    });
    render(<SplitConfigSection />);

    await waitFor(() => expect(screen.getByLabelText("Alex %")).toHaveValue(60));
    expect(screen.getByLabelText("Sam %")).toHaveValue(40);
    expect(screen.getByLabelText("Enable common economy split")).toBeChecked();
    expect(screen.getByLabelText("Home")).toBeChecked();
    expect(screen.getByLabelText("Trips")).toBeChecked();
    expect(screen.getByLabelText("Common")).not.toBeChecked();
  });

  it("shows an inline sum-validation error and never PUTs when shares don't sum to 100", async () => {
    setup();
    render(<SplitConfigSection />);

    await waitFor(() => expect(screen.getByLabelText("Alex %")).toHaveValue(50));

    fireEvent.change(screen.getByLabelText("Alex %"), { target: { value: "70" } });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Shares must sum to exactly 100 (currently 120.00).",
    );

    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    // Client-side pre-validation blocks the PUT entirely — never round-trips
    // a known-invalid sum to the server.
    expect(mockedUpdate).not.toHaveBeenCalled();
  });

  it("saves successfully when shares sum to 100", async () => {
    // Start with only "home" selected so clicking Common/Trips below adds
    // them (they'd toggle OFF if the fixture started with all 3 checked).
    setup({
      enabled: false,
      shares: { partner_a: 50, partner_b: 50 },
      sections: ["home"],
      labels: { partner_a: "Alex", partner_b: "Sam" },
    });
    mockedUpdate.mockResolvedValue({
      enabled: true,
      shares: { partner_a: 55, partner_b: 45 },
      sections: ["home", "common", "trips"],
    });
    render(<SplitConfigSection />);

    await waitFor(() => expect(screen.getByLabelText("Alex %")).toHaveValue(50));

    fireEvent.click(screen.getByLabelText("Enable common economy split"));
    fireEvent.change(screen.getByLabelText("Alex %"), { target: { value: "55" } });
    fireEvent.change(screen.getByLabelText("Sam %"), { target: { value: "45" } });
    fireEvent.click(screen.getByLabelText("Common"));
    fireEvent.click(screen.getByLabelText("Trips"));

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(mockedUpdate).toHaveBeenCalledWith({
        enabled: true,
        shares: { partner_a: 55, partner_b: 45 },
        sections: ["home", "common", "trips"],
      }),
    );
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
  });

  it("surfaces a 422/400 server validation error verbatim", async () => {
    setup();
    mockedUpdate.mockRejectedValue({ detail: "shares must sum to exactly 100", status: 422 });
    render(<SplitConfigSection />);

    await waitFor(() => expect(screen.getByLabelText("Alex %")).toHaveValue(50));

    // Shares still sum to 100 client-side (defaults) — the PUT goes out and
    // the server rejects it (e.g. a stale/concurrent-edit race); the raw
    // detail string surfaces unchanged.
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "shares must sum to exactly 100",
    );
  });

  it("renders real partner names for a custom-ID household (backend ids are never partner_a/partner_b)", async () => {
    // Regression for the label-lookup bug: backend partner ids are the real
    // ids (e.g. "alex"/"sam"), never literally "partner_a"/"partner_b", so
    // this fixture models a household where those real ids exist — the
    // component must render the `labels` field's names, not fall through to
    // "Partner A"/"Partner B" because no listPartners() entry has id
    // "partner_a".
    setup({
      enabled: true,
      shares: { partner_a: 70, partner_b: 30 },
      sections: ["home", "common", "trips"],
      labels: { partner_a: "Alex", partner_b: "Sam" },
    });
    render(<SplitConfigSection />);

    await waitFor(() => expect(screen.getByLabelText("Alex %")).toHaveValue(70));
    expect(screen.getByLabelText("Sam %")).toHaveValue(30);
    expect(screen.queryByLabelText("Partner A %")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Partner B %")).not.toBeInTheDocument();
  });

  it("falls back to neutral Partner A/Partner B labels when `labels` is missing", async () => {
    setup({
      enabled: false,
      shares: { partner_a: 50, partner_b: 50 },
      sections: ["home", "common", "trips"],
      labels: undefined as unknown as Record<string, string>,
    });
    render(<SplitConfigSection />);

    await waitFor(() => expect(screen.getByLabelText("Partner A %")).toHaveValue(50));
    expect(screen.getByLabelText("Partner B %")).toHaveValue(50);
  });
});
