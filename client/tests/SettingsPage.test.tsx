// SettingsPage tests — F11 / AC33, AC35-AC37, AC43.
// Mock all API modules — no real network.

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SettingsPage } from "@/pages/SettingsPage";

// Mock all 4 section API modules.
vi.mock("@/api/settings", () => ({
  getApiKeyStatus: vi.fn().mockResolvedValue({ configured: true }),
  updateApiKey: vi.fn().mockResolvedValue({ configured: true }),
}));

vi.mock("@/api/partners", () => ({
  listPartners: vi.fn().mockResolvedValue({ partners: [] }),
  createPartner: vi.fn(),
  updatePartner: vi.fn(),
  deletePartner: vi.fn(),
}));

vi.mock("@/api/accounts", () => ({
  listAccounts: vi.fn().mockResolvedValue({ accounts: [] }),
  updateBinding: vi.fn(),
}));

vi.mock("@/api/category_mappings", () => ({
  getCategoryMappings: vi.fn().mockResolvedValue({ categories: [] }),
  updateCategoryMapping: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("SettingsPage — AC33 render", () => {
  it("renders 4 section headings", async () => {
    render(<SettingsPage />);
    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "PocketSmith API Key" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Partners" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Accounts" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Category Mappings" })).toBeInTheDocument();
  });
});

describe("SettingsPage — AC35 ApiKeySection", () => {
  it("configured=true → shows Configured badge + Change button", async () => {
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByText(/Configured/i)).toBeInTheDocument()
    );
    expect(screen.getByRole("button", { name: "Change" })).toBeInTheDocument();
  });
});

describe("SettingsPage — AC36 PartnerList", () => {
  it("renders Add Partner button (empty list)", async () => {
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Add Partner" })).toBeInTheDocument()
    );
  });
});

describe("SettingsPage — AC37 AccountTable", () => {
  it("renders empty state when no accounts", async () => {
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByText(/No accounts/i)).toBeInTheDocument()
    );
  });
});

describe("SettingsPage — AC43 CategoryMappingsEditor", () => {
  it("renders empty state when no categories", async () => {
    render(<SettingsPage />);
    await waitFor(() =>
      expect(screen.getByText(/No categories/i)).toBeInTheDocument()
    );
  });
});