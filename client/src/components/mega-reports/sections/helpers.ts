// Shared helpers for mega report sections.

import { maskAmount } from "@/lib/privacy-store";
import type { MegaReportResponse, CategoryAgg } from "@/types/mega_report";

// Format NOK — 2 decimals, thousands separator. Masked last-mile.
export function formatNOK(v: number): string {
  return maskAmount(v.toLocaleString("nb-NO", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
}

// Partner display name from partner_labels.
export function partnerLabel(report: MegaReportResponse, key: "partner_a" | "partner_b"): string {
  return report.partner_labels[key] ?? key;
}

// Filter cats by section.
export function catsBySection(report: MegaReportResponse, section: string): CategoryAgg[] {
  return Object.entries(report.detail_agg.cats)
    .filter(([, c]) => c.section === section)
    .map(([, c]) => c);
}

// Sum a numeric array.
export function sumArr(arr: number[]): number {
  return arr.reduce((a, b) => a + (b || 0), 0);
}

// Compact NOK — M / k / int, for chart axes. Masked last-mile.
export function compactNOK(v: number): string {
  const a = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (a >= 1_000_000)
    return maskAmount(`${sign}${(a / 1_000_000).toFixed(1)}M`);
  if (a >= 1_000) return maskAmount(`${sign}${(a / 1_000).toFixed(0)}k`);
  return maskAmount(`${sign}${a.toFixed(0)}`);
}

// Stable DOM id slug for a sub-category title (used by nav anchors).
// Lowercases, collapses non-alphanumerics to "-", trims leading/trailing "-".
export function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}
