import { Badge } from "@/components/ui/badge";
import type { CategoryDetail } from "@/types/api";

// Category detail — read-only.

interface CategoryDetailProps {
  category: CategoryDetail;
}

export function CategoryDetail({ category }: CategoryDetailProps) {
  return (
    <div className="mt-2 rounded-md border border-border bg-muted/30 p-3">
      <div className="text-sm text-muted-foreground">
        ID: <span className="font-mono">{category.id}</span>
      </div>
      <h4 className="my-1">{category.title}</h4>

      {category.parent_path.length > 0 && (
        <div className="mb-2 flex flex-wrap items-center gap-1 text-sm text-muted-foreground">
          <span>Path:</span>
          {category.parent_path.map((p, i) => (
            <span key={p.id} className="flex items-center gap-1">
              {i > 0 && <span>›</span>}
              <Badge variant="outline">{p.title}</Badge>
            </span>
          ))}
        </div>
      )}

      {category.children.length > 0 && (
        <div>
          <div className="mb-1 text-sm font-semibold">Children:</div>
          <ul className="m-0 list-disc pl-5 text-sm">
            {category.children.map((c) => (
              <li key={c.id}>{c.title}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}