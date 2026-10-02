// Common-economy split settings — SplitConfigSection.
// Covers: initial fetch populates fields, client-side sum-validation error
// path (never PUTs when shares don't sum to 100), successful save round-
// trip (PUT payload carries `categories`, not `sections` — category-level
// split selection Gate 2: `sections` is server-derived/read-only, never
// sent back), 422/400 server error surfaced verbatim, partner label
// resolution via the GET response's `labels` field (real names — not
// listPartners() id-mapped, since backend partner ids are the real ids,
// e.g. "alex", never literally "partner_a"/"partner_b"), and a legacy-
// shaped GET response (empty `categories`, non-empty `sections`) doesn't
// crash the client.
//
// CategoryTreeSelect (the category picker) is mocked here — it has its own
// dedicated test file (CategoryTreeSelect.test.tsx) covering fetch/tree/
// cascade-select behavior; this file only checks SplitConfigSection wires
// `categories` through to it and round-trips the PUT payload correctly.
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

// Stub CategoryTreeSelect — renders `selected` ids as plain checkboxes
// keyed by id so tests can toggle them without a real /api/categories
// fetch.
vi.mock("@/components/settings/CategoryTreeSelect", () => ({
  CategoryTreeSelect: ({
    selected,
    onChange,
  }: {
    selected: string[];
    onChange: (ids: string[]) => void;
  }) => (
    <div>
      {["home-cat", "common-cat", "trips-cat"].map((id) => (
        <label key={id}>
          <input
            type="checkbox"
            aria-label={id}
            checked={selected.includes(id)}
            onChange={(e) => {
              if (e.target.checked) {
                onChange([...selected, id]);
              } else {
                onChange(selected.filter((s) => s !== id));
              }
            }}
          />
          {id}
        </label>
      ))}
    </div>
  ),
}));

import { getSplitConfig, updateSplitConfig } from "@/api/settings";
import { SplitConfigSection } from "../SplitConfigSection";

const mockedGet = vi.mocked(getSplitConfig);
const mockedUpdate = vi.mocked(updateSplitConfig);

const DEFAULT_CONFIG: SplitConfigResponse = {
  enabled: false,
  shares: { partner_a: 50, partner_b: 50 },
  categories: ["home-cat", "common-cat", "trips-cat"],
  sections: ["home", "common", "trips"],
  labels: { partner_a: "Alex", partner_b: "Sam" },
  warning: null,
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
      categories: ["home-cat", "trips-cat"],
      sections: ["home", "trips"],
      labels: { partner_a: "Alex", partner_b: "Sam" },
      warning: null,
    });
    render(<SplitConfigSection />);

    await waitFor(() => expect(screen.getByLabelText("Alex %")).toHaveValue(60));
    expect(screen.getByLabelText("Sam %")).toHaveValue(40);
    expect(screen.getByLabelText("Enable common economy split")).toBeChecked();
    expect(screen.getByLabelText("home-cat")).toBeChecked();
    expect(screen.getByLabelText("trips-cat")).toBeChecked();
    expect(screen.getByLabelText("common-cat")).not.toBeChecked();
    // Read-only derived-sections caption — never an editable control.
    expect(screen.getByText("Included sections: home, trips")).toBeInTheDocument();
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

  it("saves successfully when shares sum to 100 — PUT payload carries categories, not sections", async () => {
    // Start with only "home-cat" selected so clicking common/trips below
    // adds them (they'd toggle OFF if the fixture started with all 3
    // checked).
    setup({
      enabled: false,
      shares: { partner_a: 50, partner_b: 50 },
      categories: ["home-cat"],
      sections: ["home"],
      labels: { partner_a: "Alex", partner_b: "Sam" },
      warning: null,
    });
    mockedUpdate.mockResolvedValue({
      enabled: true,
      shares: { partner_a: 55, partner_b: 45 },
      categories: ["home-cat", "common-cat", "trips-cat"],
      sections: ["home", "common", "trips"],
    });
    render(<SplitConfigSection />);

    await waitFor(() => expect(screen.getByLabelText("Alex %")).toHaveValue(50));

    fireEvent.click(screen.getByLabelText("Enable common economy split"));
    fireEvent.change(screen.getByLabelText("Alex %"), { target: { value: "55" } });
    fireEvent.change(screen.getByLabelText("Sam %"), { target: { value: "45" } });
    fireEvent.click(screen.getByLabelText("common-cat"));
    fireEvent.click(screen.getByLabelText("trips-cat"));

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(mockedUpdate).toHaveBeenCalledWith({
        enabled: true,
        shares: { partner_a: 55, partner_b: 45 },
        categories: ["home-cat", "common-cat", "trips-cat"],
      }),
    );
    // `sections` never present in the PUT body — server-derived, read-only.
    expect(mockedUpdate.mock.calls[0][0]).not.toHaveProperty("sections");
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
      categories: ["home-cat", "common-cat", "trips-cat"],
      sections: ["home", "common", "trips"],
      labels: { partner_a: "Alex", partner_b: "Sam" },
      warning: null,
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
      categories: ["home-cat", "common-cat", "trips-cat"],
      sections: ["home", "common", "trips"],
      labels: undefined as unknown as Record<string, string>,
      warning: null,
    });
    render(<SplitConfigSection />);

    await waitFor(() => expect(screen.getByLabelText("Partner A %")).toHaveValue(50));
    expect(screen.getByLabelText("Partner B %")).toHaveValue(50);
  });

  it("handles a legacy-shaped GET response (empty categories, non-empty sections) without crashing", async () => {
    // Router-side guarantee: GET always returns both fields in the new
    // shape (sections server-derived from categories), but this guards the
    // client doesn't assume categories.length > 0 just because sections is
    // non-empty.
    setup({
      enabled: true,
      shares: { partner_a: 50, partner_b: 50 },
      categories: [],
      sections: ["home", "common"],
      labels: { partner_a: "Alex", partner_b: "Sam" },
      warning: null,
    });
    render(<SplitConfigSection />);

    await waitFor(() => expect(screen.getByLabelText("Alex %")).toHaveValue(50));
    expect(screen.getByLabelText("home-cat")).not.toBeChecked();
    expect(screen.getByText("Included sections: home, common")).toBeInTheDocument();
  });

  it("shows a warning banner when the GET response carries `warning`", async () => {
    // iteration-4 finding: legacy sections-only config, mapping sidecar
    // missing — GET can't translate to categories, returns the saved
    // sections as-is + this warning instead of silently emptying the
    // pick-list (src/budget_api/routers/settings.py get_split_config).
    setup({
      enabled: true,
      shares: { partner_a: 50, partner_b: 50 },
      categories: [],
      sections: ["home", "common"],
      labels: { partner_a: "Alex", partner_b: "Sam" },
      warning:
        "detailed_section_mapping.json is missing — this legacy sections-only split config could not be translated to categories; showing the saved sections as-is. Report builds using this config will fail until the mapping file is restored.",
    });
    render(<SplitConfigSection />);

    expect(
      await screen.findByText(/detailed_section_mapping\.json is missing/),
    ).toBeInTheDocument();
  });

  it("renders no warning banner when `warning` is null", async () => {
    setup(); // DEFAULT_CONFIG — warning: null
    render(<SplitConfigSection />);

    await waitFor(() => expect(screen.getByLabelText("Alex %")).toHaveValue(50));
    expect(screen.queryByText("Split configuration warning")).not.toBeInTheDocument();
  });

  it("disables Save and never PUTs when the initial GET fails (defaults would overwrite the real config)", async () => {
    // Regression: on GET failure the form keeps its defaults (50/50, no
    // categories) — an enabled Save would PUT that over the server's real
    // config. Save must be disabled and the handler guarded.
    mockedGet.mockRejectedValue({ detail: "Cannot reach server" });
    render(<SplitConfigSection />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach server");
    const save = screen.getByRole("button", { name: "Save" });
    expect(save).toBeDisabled();
    fireEvent.click(save);
    expect(mockedUpdate).not.toHaveBeenCalled();
  });

  it("disables Save while the legacy-untranslated warning is active (PUT would erase the preserved legacy sections)", async () => {
    // Regression: the legacy sections-only path returns categories=[] +
    // warning — a Save would write categories:[] over the preserved
    // legacy sections. Banner stays, Save is disabled, handler guarded.
    setup({
      enabled: true,
      shares: { partner_a: 50, partner_b: 50 },
      categories: [],
      sections: ["home", "common"],
      labels: { partner_a: "Alex", partner_b: "Sam" },
      warning:
        "detailed_section_mapping.json is missing — this legacy sections-only split config could not be translated to categories; showing the saved sections as-is. Report builds using this config will fail until the mapping file is restored.",
    });
    render(<SplitConfigSection />);

    expect(
      await screen.findByText(/detailed_section_mapping\.json is missing/),
    ).toBeInTheDocument();
    const save = screen.getByRole("button", { name: "Save" });
    expect(save).toBeDisabled();
    fireEvent.click(save);
    expect(mockedUpdate).not.toHaveBeenCalled();
  });

});
