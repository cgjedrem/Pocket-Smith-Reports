// CategoryMappingsEditor tests — F17 / AC31-AC33.
// List, dropdowns, save. Partner labels must come from config (US2/T046).

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CategoryMappingsEditor } from "@/components/settings/CategoryMappingsEditor";
import { ApiError } from "@/types/api";
import type { CategoryMappingList } from "@/types/category_mappings";

// Mock category_mappings API.
vi.mock("@/api/category_mappings", () => ({
  getCategoryMappings: vi.fn(),
  updateCategoryMapping: vi.fn(),
}));

// Mock partners API — editor resolves personal-section labels from config.
vi.mock("@/api/partners", () => ({
  listPartners: vi.fn(),
}));

import { getCategoryMappings } from "@/api/category_mappings";
import { listPartners } from "@/api/partners";

function makeMappings(): CategoryMappingList {
  return {
    categories: [
      {
        category_id: "cat1",
        category_title: "Groceries",
        kpi_role: "spend",
        detailed_section: "common",
      },
      {
        category_id: "cat2",
        category_title: "Salary",
        kpi_role: "income",
        detailed_section: "income_salary",
      },
      {
        category_id: "cat3",
        category_title: "Z Unmapped",
        kpi_role: null,
        detailed_section: null,
      },
    ],
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  // Default: partners fetch fails silently — neutral fallbacks, never blocks.
  vi.mocked(listPartners).mockRejectedValue(new Error("unavailable"));
});

describe("CategoryMappingsEditor — AC31 render", () => {
  it("renders category list with titles", async () => {
    vi.mocked(getCategoryMappings).mockResolvedValue(makeMappings());

    render(<CategoryMappingsEditor />);
    await waitFor(() => expect(screen.getByText("Groceries")).toBeInTheDocument());
    expect(screen.getByText("Salary")).toBeInTheDocument();
  });

  it("renders column headers", async () => {
    vi.mocked(getCategoryMappings).mockResolvedValue(makeMappings());

    render(<CategoryMappingsEditor />);
    await waitFor(() => expect(screen.getByText("Category")).toBeInTheDocument());
    expect(screen.getByText("KPI role")).toBeInTheDocument();
    expect(screen.getByText("Detailed section")).toBeInTheDocument();
  });

  it("empty → empty state 'No categories'", async () => {
    vi.mocked(getCategoryMappings).mockResolvedValue({ categories: [] });

    render(<CategoryMappingsEditor />);
    await waitFor(() =>
      expect(screen.getByText(/No categories/i)).toBeInTheDocument()
    );
  });

  it("404 'no categories' → empty state", async () => {
    vi.mocked(getCategoryMappings).mockRejectedValue(
      new ApiError("no categories — run sync first", 404)
    );

    render(<CategoryMappingsEditor />);
    await waitFor(() =>
      expect(screen.getByText(/No categories/i)).toBeInTheDocument()
    );
  });

  it("network error → error alert", async () => {
    vi.mocked(getCategoryMappings).mockRejectedValue(
      new ApiError("Cannot reach server", 500)
    );

    render(<CategoryMappingsEditor />);
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Cannot reach server")
    );
  });

  it("renders group headers in report order", async () => {
    vi.mocked(getCategoryMappings).mockResolvedValue(makeMappings());

    render(<CategoryMappingsEditor />);
    await waitFor(() => expect(screen.getByText("Income — Salary")).toBeInTheDocument());
    expect(screen.getByText("Common")).toBeInTheDocument();
    expect(screen.getByText("Unmapped")).toBeInTheDocument();
  });
});

describe("CategoryMappingsEditor — US2/T046 config-driven partner labels", () => {
  const personalMappings = (): CategoryMappingList => ({
    categories: [
      {
        category_id: "catP1",
        category_title: "Hobby A",
        kpi_role: "spend",
        detailed_section: "personal_partner_a",
      },
      {
        category_id: "catP2",
        category_title: "Hobby B",
        kpi_role: "spend",
        detailed_section: "personal_partner_b",
      },
    ],
  });

  const configPartners = () =>
    vi.mocked(listPartners).mockResolvedValue({
      partners: [
        { id: "partner_a", label: "Fixture A" },
        { id: "partner_b", label: "Fixture B" },
      ],
    });

  it("personal group headers resolve from payload partner labels", async () => {
    vi.mocked(getCategoryMappings).mockResolvedValue(personalMappings());
    configPartners();

    render(<CategoryMappingsEditor />);
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Personal — Fixture A" })
      ).toBeInTheDocument()
    );
    expect(
      screen.getByRole("heading", { name: "Personal — Fixture B" })
    ).toBeInTheDocument();
    // No neutral placeholder remains once config labels arrive.
    expect(screen.queryByText("Personal — Partner A")).toBeNull();
    expect(screen.queryByText("Personal — Partner B")).toBeNull();
  });

  it("detailed-section dropdown options use config labels", async () => {
    vi.mocked(getCategoryMappings).mockResolvedValue(personalMappings());
    configPartners();

    render(<CategoryMappingsEditor />);
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Personal — Fixture A" })
      ).toBeInTheDocument()
    );

    // Open the detailed-section dropdown of the first row.
    const row = screen.getByText("Hobby A").closest("div")!;
    // First trigger is KPI role; second is detailed section.
    const triggers = row.querySelectorAll('[data-slot="select-trigger"]');
    expect(triggers.length).toBe(2);
    fireEvent.click(triggers[1]);

    const listbox = document.querySelector('[role="listbox"]');
    expect(listbox).not.toBeNull();
    const opts = Array.from(
      (listbox as HTMLElement).querySelectorAll('[role="option"]'),
    ).map((o) => o.textContent);
    expect(opts).toContain("Personal — Fixture A");
    expect(opts).toContain("Personal — Fixture B");
    expect(opts).not.toContain("Personal — Partner A");
  });

  it("partners fetch failure falls back to neutral Partner A/B labels", async () => {
    vi.mocked(getCategoryMappings).mockResolvedValue(personalMappings());
    // beforeEach default: listPartners rejects.

    render(<CategoryMappingsEditor />);
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Personal — Partner A" })
      ).toBeInTheDocument()
    );
    expect(
      screen.getByRole("heading", { name: "Personal — Partner B" })
    ).toBeInTheDocument();
  });
});

describe("CategoryMappingsEditor — AC32-AC33 save buttons", () => {
  it("renders Save button per row", async () => {
    vi.mocked(getCategoryMappings).mockResolvedValue(makeMappings());

    render(<CategoryMappingsEditor />);
    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: "Save" }).length).toBe(3)
    );
  });

  it("Save disabled when not dirty", async () => {
    vi.mocked(getCategoryMappings).mockResolvedValue(makeMappings());

    render(<CategoryMappingsEditor />);
    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: "Save" }).length).toBe(3)
    );
    // Save buttons disabled — no changes yet.
    const saveButtons = screen.getAllByRole("button", { name: "Save" });
    saveButtons.forEach((btn) => expect(btn).toBeDisabled());
  });
});