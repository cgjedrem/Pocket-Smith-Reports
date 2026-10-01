// Common-economy split settings — GET/PUT /api/settings/split.
// Enable toggle + partner_a/partner_b % shares (must sum to 100, checked
// client-side before PUT — server re-validates: 422 sum!=100, 400 shape/
// category errors) + category-level picker (CategoryTreeSelect, category-
// level split selection Gate 2 — `categories` is the write contract;
// `sections` is server-derived/read-only display, never sent on PUT).
//
// Partner slot labels (partner_a/partner_b -> display name) come straight
// off the GET response's `labels` field (SplitConfigResponse — real names
// resolved server-side via the same slot-map path report_builder uses).
// NOT listPartners() id-mapped: backend partner ids are the real ids (e.g.
// "alex"), never literally "partner_a"/"partner_b", so mapping listPartners()
// by id silently fell through to the neutral fallback for every custom-ID
// household. Neutral "Partner A"/"Partner B" fallback only if `labels` is
// missing/empty (e.g. load error before the fetch resolves).

import { useCallback, useEffect, useMemo, useState } from "react";

import { getSplitConfig, updateSplitConfig } from "@/api/settings";
import { BillsWarningBanner } from "@/components/bills/BillsWarningBanner";
import { ErrorAlert } from "@/components/ErrorAlert";
import { CategoryTreeSelect } from "@/components/settings/CategoryTreeSelect";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import type { SplitConfig } from "@/types/api";

function sumsTo100(a: number, b: number): boolean {
  return Math.abs(a + b - 100) <= 1e-6;
}

export function SplitConfigSection() {
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [enabled, setEnabled] = useState(false);
  // Kept as strings while editing — numeric inputs, parsed on save/validate.
  const [shareA, setShareA] = useState("50");
  const [shareB, setShareB] = useState("50");
  const [categories, setCategories] = useState<string[]>([]);
  // Server-derived, read-only display only — never sent back on PUT.
  const [sections, setSections] = useState<string[]>([]);

  const [partnerLabels, setPartnerLabels] = useState<Record<string, string>>({});
  // Additive, GET-response-only (SplitConfigResponse.warning) — legacy
  // sections-only config that couldn't translate to categories because
  // detailed_section_mapping.json is missing. Cleared on a successful save
  // (PUT always writes the categories shape, so the condition can't
  // immediately recur).
  const [warning, setWarning] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const config = await getSplitConfig();
      applyConfig(config);
      // Display-only, GET-response-only field — never touched by the PUT
      // round-trip in handleSave (server's PUT response is plain
      // SplitConfig, no `labels`), so labels persist across saves.
      setPartnerLabels(config.labels ?? {});
      setWarning(config.warning ?? null);
    } catch (err) {
      setLoadError((err as { detail?: string })?.detail ?? "Cannot reach server");
    } finally {
      setLoading(false);
    }
  }, []);

  function applyConfig(config: SplitConfig) {
    setEnabled(config.enabled);
    setShareA(String(config.shares.partner_a));
    setShareB(String(config.shares.partner_b));
    setCategories(config.categories);
    setSections(config.sections);
  }

  useEffect(() => {
    refresh();
  }, [refresh]);

  const labelA = partnerLabels["partner_a"] ?? "Partner A";
  const labelB = partnerLabels["partner_b"] ?? "Partner B";

  const parsedA = Number(shareA);
  const parsedB = Number(shareB);
  const sharesAreNumeric = shareA.trim() !== "" && shareB.trim() !== "" && !Number.isNaN(parsedA) && !Number.isNaN(parsedB);
  const sumError = useMemo(() => {
    if (!sharesAreNumeric) return "Shares must be numbers.";
    if (!sumsTo100(parsedA, parsedB)) {
      return `Shares must sum to exactly 100 (currently ${(parsedA + parsedB).toFixed(2)}).`;
    }
    return null;
  }, [sharesAreNumeric, parsedA, parsedB]);

  const handleSave = useCallback(async () => {
    setSaveError(null);
    setSaved(false);
    // Client-side pre-validation — inline error, no PUT round-trip.
    if (sumError) {
      setSaveError(sumError);
      return;
    }
    setSaving(true);
    try {
      const updated = await updateSplitConfig({
        enabled,
        shares: { partner_a: parsedA, partner_b: parsedB },
        categories,
      });
      applyConfig(updated);
      setWarning(null);
      setSaved(true);
    } catch (err) {
      setSaveError((err as { detail?: string })?.detail ?? "Cannot reach server");
    } finally {
      setSaving(false);
    }
  }, [sumError, enabled, parsedA, parsedB, categories]);

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading...</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      {loadError && <ErrorAlert message={loadError} />}
      {warning && <BillsWarningBanner warnings={[warning]} title="Split configuration warning" />}

      <div className="flex items-center gap-2">
        <Checkbox
          id="split-enabled"
          checked={enabled}
          onCheckedChange={(v) => setEnabled(Boolean(v))}
        />
        <Label htmlFor="split-enabled">Enable common economy split</Label>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Label htmlFor="split-share-a" className="min-w-[6rem]">
            {labelA} %
          </Label>
          <input
            id="split-share-a"
            type="number"
            min={0}
            max={100}
            step="any"
            value={shareA}
            onChange={(e) => setShareA(e.target.value)}
            className="h-9 w-24 rounded-md border border-input bg-transparent px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
          />
        </div>
        <div className="flex items-center gap-2">
          <Label htmlFor="split-share-b" className="min-w-[6rem]">
            {labelB} %
          </Label>
          <input
            id="split-share-b"
            type="number"
            min={0}
            max={100}
            step="any"
            value={shareB}
            onChange={(e) => setShareB(e.target.value)}
            className="h-9 w-24 rounded-md border border-input bg-transparent px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
          />
        </div>
      </div>

      {sumError && (
        <p role="alert" className="text-sm text-destructive">
          {sumError}
        </p>
      )}

      <div className="flex flex-col gap-1">
        <span className="text-sm font-medium">Categories included</span>
        <CategoryTreeSelect selected={categories} onChange={setCategories} />
        {sections.length > 0 && (
          <p className="text-xs text-muted-foreground">
            Included sections: {sections.join(", ")}
          </p>
        )}
      </div>

      <div className="flex items-center gap-2">
        <Button type="button" onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : "Save"}
        </Button>
        {saved && <span className="text-sm text-primary">Saved.</span>}
      </div>

      {saveError && <ErrorAlert message={saveError} />}
    </div>
  );
}
