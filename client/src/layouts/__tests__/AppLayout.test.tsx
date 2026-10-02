// AppLayout header toggle tests — contracts/privacy-store.md §2.
// Eye toggle: aria-label, aria-pressed, click + keyboard activation.

import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { AppLayout } from "@/layouts/AppLayout";
import { setAmountsHidden } from "@/lib/privacy-store";

function renderLayout() {
  return render(
    <MemoryRouter>
      <AppLayout />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  localStorage.clear();
  setAmountsHidden(false);
});

describe("AppLayout hide-amounts toggle", () => {
  it('renders an eye toggle with aria-label "Hide amounts" and aria-pressed=false by default', () => {
    renderLayout();
    const toggle = screen.getByRole("button", { name: "Hide amounts" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
  });

  it('clicking flips aria-pressed and swaps the label to "Show amounts"', () => {
    renderLayout();
    const toggle = screen.getByRole("button", { name: "Hide amounts" });
    fireEvent.click(toggle);
    const flipped = screen.getByRole("button", { name: "Show amounts" });
    expect(flipped).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(flipped);
    expect(
      screen.getByRole("button", { name: "Hide amounts" }),
    ).toHaveAttribute("aria-pressed", "false");
  });

  it("is a native button — keyboard Enter/Space activates it", () => {
    renderLayout();
    const toggle = screen.getByRole("button", { name: "Hide amounts" });
    // Native <button> gives Enter/Space activation for free in browsers;
    // pin the tag so the element can't regress to a div.
    expect(toggle.tagName).toBe("BUTTON");
    expect(toggle).toHaveAttribute("type", "button");
  });
});
