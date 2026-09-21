// DocsPage tests — static docs page: sections render, TOC anchors resolve,
// key install commands present. No API calls (page is static).

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DocsPage } from "@/pages/DocsPage";

const TOC_LABELS = [
  "Overview",
  "Getting started",
  "Install & run",
  "First run",
  "Using the app",
  "Staged live sync",
  "Report CLI",
  "Synthetic fixture contract",
  "Release notes",
  "Testing & QA",
  "Data & privacy",
];

describe("DocsPage", () => {
  it("renders title and intro", () => {
    render(<DocsPage />);
    expect(screen.getByRole("heading", { name: "Docs" })).toBeInTheDocument();
    expect(
      screen.getByText(/install, run, and use pocket-smith reports/i),
    ).toBeInTheDocument();
  });

  it("renders the TOC in order", () => {
    render(<DocsPage />);
    const nav = screen.getByRole("navigation", { name: "On this page" });
    const links = within(nav).getAllByRole("link");
    expect(links.map((l) => l.textContent)).toEqual(TOC_LABELS);
  });

  it("every TOC anchor resolves to a rendered section heading", () => {
    render(<DocsPage />);
    const nav = screen.getByRole("navigation", { name: "On this page" });
    for (const link of within(nav).getAllByRole("link")) {
      const href = link.getAttribute("href")!;
      expect(href).toMatch(/^#/);
      const section = document.getElementById(href.slice(1));
      expect(section, `missing section ${href}`).not.toBeNull();
      expect(
        section!.querySelector("h2"),
        `section ${href} has no heading`,
      ).not.toBeNull();
    }
  });

  it("documents the core install and run commands", () => {
    render(<DocsPage />);
    // Backend + frontend commands from the quick start.
    expect(screen.getByText(/run_api\.ps1 -Port 8001/)).toBeInTheDocument();
    expect(screen.getByText(/pnpm dev/)).toBeInTheDocument();
    expect(screen.getByText(/uv sync/)).toBeInTheDocument();
  });

  it("references the data policy and hardening docs by path", () => {
    render(<DocsPage />);
    // LG-002 forbids personal identifiers in tracked files, so repo links use
    // plain file paths rather than absolute GitHub URLs.
    expect(screen.getAllByText("docs/DATA_POLICY.md").length).toBeGreaterThan(0);
    expect(
      screen.getByText("docs/production-hardening-loops.md"),
    ).toBeInTheDocument();
  });
});