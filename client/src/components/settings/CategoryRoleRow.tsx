// Category role row — per-category KPI role + detailed section dropdowns + save.
// Null values default to "exclude"/"excluded" — no "(none)" option.

import { useEffect, useState } from "react";

import { updateCategoryMapping } from "@/api/category_mappings";
import { ErrorAlert } from "@/components/ErrorAlert";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DETAILED_SECTION_OPTIONS,
  detailedSectionLabel,
  KPI_ROLE_OPTIONS,
  type CategoryMapping,
  type DetailedSection,
  type KpiRole,
} from "@/types/category_mappings";

// Defaults — null → explicit exclude/excluded.
const DEFAULT_KPI_ROLE: KpiRole = "exclude";
const DEFAULT_SECTION: DetailedSection = "excluded";

interface CategoryRoleRowProps {
  mapping: CategoryMapping;
  onSaved: () => void;
  // Display-label resolver for section options — editor supplies one wired
  // to config partner labels. Defaults to neutral fallbacks.
  partnerLabels?: Record<string, string>;
}

export function CategoryRoleRow({ mapping, onSaved, partnerLabels }: CategoryRoleRowProps) {
  const [kpiRole, setKpiRole] = useState<KpiRole>(
    mapping.kpi_role ?? DEFAULT_KPI_ROLE
  );
  const [detailedSection, setDetailedSection] = useState<DetailedSection>(
    mapping.detailed_section ?? DEFAULT_SECTION
  );
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Resync when server values change.
  useEffect(() => {
    setKpiRole(mapping.kpi_role ?? DEFAULT_KPI_ROLE);
    setDetailedSection(mapping.detailed_section ?? DEFAULT_SECTION);
  }, [mapping.kpi_role, mapping.detailed_section]);

  const dirty =
    kpiRole !== (mapping.kpi_role ?? DEFAULT_KPI_ROLE) ||
    detailedSection !== (mapping.detailed_section ?? DEFAULT_SECTION);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await updateCategoryMapping(mapping.category_id, {
        kpi_role: kpiRole,
        detailed_section: detailedSection,
      });
      setSaved(true);
      onSaved();
    } catch (err) {
      setError((err as { detail?: string })?.detail ?? "Cannot reach server");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex items-center gap-2 py-1">
      <span className="flex-1 truncate text-sm" title={mapping.category_title}>
        {mapping.category_title}
      </span>
      <Select
        value={kpiRole}
        onValueChange={(v) => setKpiRole(v as KpiRole)}
      >
        <SelectTrigger size="sm" className="w-[9rem]">
          <SelectValue placeholder="exclude" />
        </SelectTrigger>
        <SelectContent>
          {KPI_ROLE_OPTIONS.map((r) => (
            <SelectItem key={r} value={r}>
              {r}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select
        value={detailedSection}
        onValueChange={(v) => setDetailedSection(v as DetailedSection)}
      >
        <SelectTrigger size="sm" className="w-[10rem]">
          <SelectValue placeholder="excluded" />
        </SelectTrigger>
        <SelectContent>
          {DETAILED_SECTION_OPTIONS.map((s) => (
            <SelectItem key={s} value={s}>
              {detailedSectionLabel(s, partnerLabels ?? {})}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Button
        type="button"
        size="sm"
        variant="outline"
        onClick={handleSave}
        disabled={saving || !dirty}
      >
        {saving ? "Saving..." : "Save"}
      </Button>
      {saved && !dirty && (
        <span className="text-xs text-primary">Saved</span>
      )}
      {error && <ErrorAlert message={error} />}
    </div>
  );
}