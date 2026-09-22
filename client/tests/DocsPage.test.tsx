// DocsPage tests — static usage guide: sections render, TOC anchors resolve.
// No API calls (page is static).

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DocsPage } from "@/pages/DocsPage";

const TOC_LABELS = [
  "Overview",
  "Connect & sync",
  "Set up accounts & labels",
  "Monthly reports",
  "Mega reports (12 months)",
  "Bills dashboard",
  "Settings",
  "Command line",
  "Troubleshooting",
];

describe("DocsPage", () => {
  it("renders title and intro", () => {
    render(<DocsPage />);
    expect(screen.getByRole("heading", { name: "Docs" })).toBeInTheDocument();
    expect(
      screen.getByText(/how to use pocket-smith reports/i),
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

  it("points each app page to its main job", () => {
    render(<DocsPage />);
    expect(screen.getByText(/choose a start and end month/i)).toBeInTheDocument();
    expect(screen.getAllByText(/partner labels/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/single-month report/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/12-month range/i)).toBeInTheDocument();
  });
});