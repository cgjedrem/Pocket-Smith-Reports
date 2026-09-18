// Category mappings editor — Settings section.
// Fetches GET /api/category-mappings. Groups by detailed_section in report order.
// Per-row save → PUT → refresh (row moves to new group).

import { useCallback, useEffect, useMemo, useState } from "react";

import { getCategoryMappings } from "@/api/category_mappings";
import { listPartners } from "@/api/partners";
import { CategoryRoleRow } from "@/components/settings/CategoryRoleRow";
import { EmptyState } from "@/components/EmptyState";
import { ErrorAlert } from "@/components/ErrorAlert";
import {
  detailedSectionLabel,
  type CategoryMapping,
  type DetailedSection,
} from "@/types/category_mappings";

// Group order + headers — matches monthly report (DetailedSections.tsx).
// Personal-group labels resolve from config partner labels at render time.
const SECTION_GROUPS: { key: DetailedSection | null; label: string }[] = [
  { key: "income_salary", label: "Income — Salary" },
  { key: "income_third_party", label: "Income — Third Party" },
  { key: "savings", label: "Savings" },
  { key: "home", label: "Home" },
  { key: "common", label: "Common" },
  { key: "personal_partner_a", label: "Personal — Partner A" },
  { key: "personal_partner_b", label: "Personal — Partner B" },
  { key: "trips", label: "Trips" },
  { key: "cc_payments", label: "CC Payments" },
  { key: "excluded", label: "Excluded" },
  { key: null, label: "Unmapped" },
];

export function CategoryMappingsEditor() {
  const [mappings, setMappings] = useState<CategoryMapping[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Config-driven partner labels (id → label). Partners fetch failure →
  // empty map → neutral fallbacks; never blocks the editor.
  const [partnerLabels, setPartnerLabels] = useState<Record<string, string>>(
    {},
  );

  const refresh = useCallback(async () => {
    try {
      const list = await getCategoryMappings();
      setMappings(list.categories);
    } catch (err) {
      const detail = (err as { detail?: string; status?: number })?.detail;
      // 404 "no categories" → empty state, not error.
      if (detail && detail.includes("no categories")) {
        setMappings([]);
      } else {
        setError(detail ?? "Cannot reach server");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    listPartners()
      .then((list) => {
        const map: Record<string, string> = {};
        for (const p of list.partners) map[p.id] = p.label;
        setPartnerLabels(map);
      })
      .catch(() => {});
  }, []);

  // Group by detailed_section, sort alphabetically within group.
  const grouped = useMemo(() => {
    const buckets = new Map<DetailedSection | null, CategoryMapping[]>();
    for (const m of mappings) {
      const key = m.detailed_section;
      const arr = buckets.get(key) ?? [];
      arr.push(m);
      buckets.set(key, arr);
    }
    for (const arr of buckets.values()) {
      arr.sort((a, b) => a.category_title.localeCompare(b.category_title));
    }
    return buckets;
  }, [mappings]);

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading...</p>;
  }

  return (
    <div>
      {error && <ErrorAlert message={error} />}
      {mappings.length === 0 ? (
        <EmptyState message="No categories — run sync first." />
      ) : (
        <div className="flex flex-col gap-4">
          {/* Column headers — once at top. */}
          <div className="flex items-center gap-2 border-b border-border pb-1 text-xs font-medium text-muted-foreground">
            <span className="flex-1">Category</span>
            <span className="w-[9rem]">KPI role</span>
            <span className="w-[10rem]">Detailed section</span>
            <span className="w-[5rem]" />
          </div>
          {SECTION_GROUPS.map(({ key, label }) => {
            const rows = grouped.get(key) ?? [];
            if (rows.length === 0) return null;
            const heading =
              key === "personal_partner_a" || key === "personal_partner_b"
                ? detailedSectionLabel(key, partnerLabels)
                : label;
            return (
              <div key={key ?? "unmapped"} className="flex flex-col gap-1">
                <h3 className="text-sm font-semibold text-foreground">{heading}</h3>
                {rows.map((m) => (
                  <CategoryRoleRow
                    key={m.category_id}
                    mapping={m}
                    onSaved={refresh}
                    partnerLabels={partnerLabels}
                  />
                ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}