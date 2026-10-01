// Category tree multi-select — nested checkboxes with parent/descendant
// cascade semantics, for the common-economy split category picker
// (SplitConfigSection). Fetches GET /api/categories (flat list, existing
// api/categories.ts helper) and builds the parent/child tree client-side —
// same tree-build approach as CategoryTree.tsx.
//
// Selection semantics (controlled — parent owns `selected`):
// - Checking a node adds it AND every descendant id to the selected list.
// - Unchecking a node removes it AND every descendant id.
// - A parent renders indeterminate when some but not all of
//   {self + descendants} are selected.
// `selected` is the full flat id list (parents + leaves alike) — matches
// the backend contract (categories: string[], any tree level, source of
// truth; server expands a selected parent to its descendant closure again
// at report-build time — redundant overlap here is harmless, backend
// dedupes on PUT).

import { useEffect, useMemo, useState } from "react";

import { listCategories } from "@/api/categories";
import { EmptyState } from "@/components/EmptyState";
import { ErrorAlert } from "@/components/ErrorAlert";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import type { Category } from "@/types/api";

// Exported for CategoryTreeSelect.test.tsx's cyclic-data defense-in-depth
// test — buildTree can't produce a reachable cycle (see MAX_CLOSURE_DEPTH
// comment), so the test constructs a malformed TreeNode graph directly.
export interface TreeNode {
  cat: Category;
  children: TreeNode[];
}

function buildTree(cats: Category[]): TreeNode[] {
  const byId = new Map<string, TreeNode>();
  cats.forEach((c) => byId.set(c.id, { cat: c, children: [] }));
  const roots: TreeNode[] = [];
  byId.forEach((node) => {
    if (node.cat.parent_id && byId.has(node.cat.parent_id)) {
      byId.get(node.cat.parent_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  });
  return roots;
}

// Max closure-walk depth — mirrors the render-path MAX_DEPTH guard below.
// A well-formed tree (buildTree's byId map, single parent_id per node)
// can't actually loop back into a real root's descendants (see
// CategoryTreeSelect.test.tsx cyclic-data test comment for the proof), so
// this never fires on real data. Defense-in-depth only: malformed/hand-
// built TreeNode graphs (e.g. a manually stitched fixture, or a future
// caller that skips buildTree) could still self-reference and stack-
// overflow without a stop condition.
const MAX_CLOSURE_DEPTH = 20;

// Self + every descendant id, recursive. depth-guarded — cyclic children
// (self-ref or a loop) stop instead of recursing forever.
export function closureIds(node: TreeNode, depth = 0): string[] {
  if (depth >= MAX_CLOSURE_DEPTH) return [node.cat.id];
  return [node.cat.id, ...node.children.flatMap((c) => closureIds(c, depth + 1))];
}

type NodeCheckState = "checked" | "unchecked" | "indeterminate";

function nodeState(node: TreeNode, selected: ReadonlySet<string>): NodeCheckState {
  const ids = closureIds(node);
  const selectedCount = ids.filter((id) => selected.has(id)).length;
  if (selectedCount === 0) return "unchecked";
  if (selectedCount === ids.length) return "checked";
  return "indeterminate";
}

// Max render depth — cycle guard (mirrors CategoryTree.tsx).
const MAX_DEPTH = 20;

interface CategoryTreeSelectProps {
  selected: string[];
  onChange: (ids: string[]) => void;
}

export function CategoryTreeSelect({ selected, onChange }: CategoryTreeSelectProps) {
  const [cats, setCats] = useState<Category[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await listCategories();
        if (!cancelled) setCats(list.categories);
      } catch (err) {
        if (!cancelled) {
          setError((err as { detail?: string })?.detail ?? "Cannot reach server");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const tree = useMemo(() => buildTree(cats ?? []), [cats]);
  const selectedSet = useMemo(() => new Set(selected), [selected]);

  const handleToggle = (node: TreeNode, checked: boolean) => {
    const ids = closureIds(node);
    const next = new Set(selectedSet);
    if (checked) {
      ids.forEach((id) => next.add(id));
    } else {
      ids.forEach((id) => next.delete(id));
    }
    onChange(Array.from(next));
  };

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading categories...</p>;
  }

  if (error) return <ErrorAlert message={error} />;

  if (!cats || cats.length === 0) {
    return <EmptyState message="No categories — run sync first." />;
  }

  return (
    <TreeView nodes={tree} selected={selectedSet} onToggle={handleToggle} />
  );
}

function TreeView({
  nodes,
  selected,
  onToggle,
  depth = 0,
}: {
  nodes: TreeNode[];
  selected: ReadonlySet<string>;
  onToggle: (node: TreeNode, checked: boolean) => void;
  depth?: number;
}) {
  if (depth >= MAX_DEPTH) return null;
  return (
    <ul className="m-0 list-none space-y-1 p-0" style={{ paddingLeft: depth ? "1.25rem" : 0 }}>
      {nodes.map((node) => {
        const state = nodeState(node, selected);
        const inputId = `category-tree-${node.cat.id}`;
        return (
          <li key={node.cat.id}>
            <div className="flex items-center gap-2">
              <Checkbox
                id={inputId}
                checked={state === "indeterminate" ? "indeterminate" : state === "checked"}
                onCheckedChange={(v) => onToggle(node, Boolean(v))}
              />
              <Label htmlFor={inputId} className={cn("font-normal", depth === 0 && "font-medium")}>
                {node.cat.title}
              </Label>
            </div>
            {node.children.length > 0 && (
              <TreeView
                nodes={node.children}
                selected={selected}
                onToggle={onToggle}
                depth={depth + 1}
              />
            )}
          </li>
        );
      })}
    </ul>
  );
}
