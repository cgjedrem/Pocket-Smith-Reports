import { useCallback, useEffect, useMemo, useState } from "react";

import { getCategoryDetail, listCategories } from "@/api/categories";
import { CategoryDetail } from "@/components/CategoryDetail";
import { EmptyState } from "@/components/EmptyState";
import { ErrorAlert } from "@/components/ErrorAlert";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Category, CategoryDetail as CategoryDetailT } from "@/types/api";

// Category tree — flat list → tree, click → detail.

interface TreeNode {
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

// Max render depth — cycle guard.
const MAX_DEPTH = 20;

function TreeView({
  nodes,
  onSelect,
  selectedId,
  depth = 0,
}: {
  nodes: TreeNode[];
  onSelect: (id: string) => void;
  selectedId: string | null;
  depth?: number;
}) {
  if (depth >= MAX_DEPTH) return null;
  return (
    <ul
      className="m-0 list-none p-0"
      style={{ paddingLeft: `${depth}rem` }}
    >
      {nodes.map((n) => (
        <li key={n.cat.id}>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onSelect(n.cat.id)}
            className={cn(
              "justify-start px-2 py-0.5 text-sm font-normal",
              n.cat.id === selectedId && "font-semibold text-primary",
            )}
          >
            {"›".repeat(depth)} {n.cat.title}
          </Button>
          {n.children.length > 0 && (
            <TreeView
              nodes={n.children}
              onSelect={onSelect}
              selectedId={selectedId}
              depth={depth + 1}
            />
          )}
        </li>
      ))}
    </ul>
  );
}

export function CategoryTree() {
  const [cats, setCats] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CategoryDetailT | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const list = await listCategories();
        setCats(list.categories);
      } catch (err) {
        const detail = (err as { detail?: string })?.detail;
        if (detail && detail.includes("no categories")) {
          setCats([]);
        } else {
          setError(detail ?? "Cannot reach server");
        }
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleSelect = useCallback(async (id: string) => {
    setSelectedId(id);
    setDetail(null);
    setDetailError(null);
    try {
      const d = await getCategoryDetail(id);
      setDetail(d);
    } catch (err) {
      setDetailError((err as { detail?: string })?.detail ?? "Cannot reach server");
    }
  }, []);

  // Memoize tree before early returns — hooks must run unconditionally.
  const tree = useMemo(() => buildTree(cats), [cats]);

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading...</p>;
  }

  if (error) return <ErrorAlert message={error} />;

  if (cats.length === 0) {
    return <EmptyState message="No categories — run sync first." />;
  }

  return (
    <div>
      <TreeView nodes={tree} onSelect={handleSelect} selectedId={selectedId} />
      {detailError && <ErrorAlert message={detailError} />}
      {detail && <CategoryDetail category={detail} />}
    </div>
  );
}