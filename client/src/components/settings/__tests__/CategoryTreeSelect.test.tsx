// CategoryTreeSelect — parent/child category picker with cascade-select
// semantics (category-level split selection Gate 2 — SplitConfigSection's
// category picker). Covers: loading/error/empty states, tree render from
// the flat GET /api/categories list, checking a parent selects every
// descendant, indeterminate rendering when only some descendants are
// selected, and unchecking a parent clears the whole subtree.

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CategoryList } from "@/types/api";

vi.mock("@/api/categories", () => ({
  listCategories: vi.fn(),
}));

import { listCategories } from "@/api/categories";
import { CategoryTreeSelect, closureIds, type TreeNode } from "../CategoryTreeSelect";

const mockedList = vi.mocked(listCategories);

// Two-level tree: Home (parent) -> Rent, Groceries (children); Trips (leaf,
// no children).
const CATEGORIES: CategoryList = {
  categories: [
    { id: "home", title: "Home", parent_id: null },
    { id: "rent", title: "Rent", parent_id: "home" },
    { id: "groceries", title: "Groceries", parent_id: "home" },
    { id: "trips", title: "Trips", parent_id: null },
  ],
};

afterEach(() => {
  vi.clearAllMocks();
});

describe("CategoryTreeSelect", () => {
  it("shows a loading state before the fetch resolves", () => {
    mockedList.mockReturnValue(new Promise(() => {})); // never resolves
    render(<CategoryTreeSelect selected={[]} onChange={vi.fn()} />);
    expect(screen.getByText("Loading categories...")).toBeInTheDocument();
  });

  it("shows an error state when the fetch fails", async () => {
    mockedList.mockRejectedValue({ detail: "Cannot reach server" });
    render(<CategoryTreeSelect selected={[]} onChange={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach server");
  });

  it("shows an empty state when there are no categories", async () => {
    mockedList.mockResolvedValue({ categories: [] });
    render(<CategoryTreeSelect selected={[]} onChange={vi.fn()} />);
    expect(await screen.findByText("No categories — run sync first.")).toBeInTheDocument();
  });

  it("renders the tree from the flat list, nesting children under their parent", async () => {
    mockedList.mockResolvedValue(CATEGORIES);
    render(<CategoryTreeSelect selected={[]} onChange={vi.fn()} />);

    await waitFor(() => expect(screen.getByLabelText("Home")).toBeInTheDocument());
    expect(screen.getByLabelText("Rent")).toBeInTheDocument();
    expect(screen.getByLabelText("Groceries")).toBeInTheDocument();
    expect(screen.getByLabelText("Trips")).toBeInTheDocument();
    // Nothing selected — every checkbox starts unchecked.
    expect(screen.getByLabelText("Home")).not.toBeChecked();
    expect(screen.getByLabelText("Rent")).not.toBeChecked();
  });

  it("checking a parent selects it and every descendant", async () => {
    mockedList.mockResolvedValue(CATEGORIES);
    const onChange = vi.fn();
    render(<CategoryTreeSelect selected={[]} onChange={onChange} />);

    await waitFor(() => expect(screen.getByLabelText("Home")).toBeInTheDocument());
    fireEvent.click(screen.getByLabelText("Home"));

    expect(onChange).toHaveBeenCalledTimes(1);
    const ids = onChange.mock.calls[0][0] as string[];
    expect(new Set(ids)).toEqual(new Set(["home", "rent", "groceries"]));
  });

  it("renders indeterminate on a parent when only some descendants are selected", async () => {
    mockedList.mockResolvedValue(CATEGORIES);
    render(<CategoryTreeSelect selected={["rent"]} onChange={vi.fn()} />);

    await waitFor(() => expect(screen.getByLabelText("Home")).toBeInTheDocument());
    const homeCheckbox = screen.getByLabelText("Home");
    expect(homeCheckbox).toHaveAttribute("data-state", "indeterminate");
    expect(screen.getByLabelText("Rent")).toBeChecked();
    expect(screen.getByLabelText("Groceries")).not.toBeChecked();
  });

  it("shows a parent as fully checked when every descendant is selected", async () => {
    mockedList.mockResolvedValue(CATEGORIES);
    render(<CategoryTreeSelect selected={["home", "rent", "groceries"]} onChange={vi.fn()} />);

    await waitFor(() => expect(screen.getByLabelText("Home")).toBeInTheDocument());
    expect(screen.getByLabelText("Home")).toHaveAttribute("data-state", "checked");
  });

  it("unchecking a parent clears it and every descendant", async () => {
    mockedList.mockResolvedValue(CATEGORIES);
    const onChange = vi.fn();
    render(
      <CategoryTreeSelect selected={["home", "rent", "groceries", "trips"]} onChange={onChange} />,
    );

    await waitFor(() => expect(screen.getByLabelText("Home")).toBeInTheDocument());
    fireEvent.click(screen.getByLabelText("Home"));

    expect(onChange).toHaveBeenCalledTimes(1);
    const ids = onChange.mock.calls[0][0] as string[];
    // "trips" is unrelated — survives the Home subtree's clear.
    expect(new Set(ids)).toEqual(new Set(["trips"]));
  });

  it("a leaf with no children toggles independently of its siblings", async () => {
    mockedList.mockResolvedValue(CATEGORIES);
    const onChange = vi.fn();
    render(<CategoryTreeSelect selected={["home", "rent", "groceries"]} onChange={onChange} />);

    await waitFor(() => expect(screen.getByLabelText("Trips")).toBeInTheDocument());
    fireEvent.click(screen.getByLabelText("Trips"));

    expect(onChange).toHaveBeenCalledTimes(1);
    const ids = onChange.mock.calls[0][0] as string[];
    expect(new Set(ids)).toEqual(new Set(["home", "rent", "groceries", "trips"]));
  });
});

// closureIds — cyclic-data defense-in-depth. buildTree's byId map gives
// every node exactly one parent, so a real cyclic parent_id chain (e.g. a
// data-corruption case) always ends up disconnected from every real root
// (a root has no parent, so it can't be part of a cycle; walking a cycle
// member's parent chain never terminates at a root either) — closureIds
// is never reached with cyclic input from the actual render path. This
// test constructs the malformed graph directly, bypassing buildTree, to
// prove the depth guard stops recursion instead of stack-overflowing —
// hardening for any future caller that builds a TreeNode graph another way.
describe("closureIds — cyclic-data guard", () => {
  it("stops at MAX_CLOSURE_DEPTH on a self-referencing node instead of recursing forever", () => {
    const selfCycle: TreeNode = {
      cat: { id: "loop", title: "Loop", parent_id: null },
      children: [],
    };
    selfCycle.children.push(selfCycle); // node is its own child

    const ids = closureIds(selfCycle);
    expect(ids.length).toBeLessThan(1000); // did not stack-overflow / run away
    expect(ids.every((id) => id === "loop")).toBe(true);
  });

  it("stops at MAX_CLOSURE_DEPTH on a two-node mutual cycle", () => {
    const a: TreeNode = { cat: { id: "a", title: "A", parent_id: null }, children: [] };
    const b: TreeNode = { cat: { id: "b", title: "B", parent_id: null }, children: [] };
    a.children.push(b);
    b.children.push(a); // a -> b -> a -> ...

    const ids = closureIds(a);
    expect(ids.length).toBeLessThan(1000);
    expect(new Set(ids)).toEqual(new Set(["a", "b"]));
  });
});
