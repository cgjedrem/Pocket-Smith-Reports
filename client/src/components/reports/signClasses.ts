// Sign-class enum -> Tailwind/CSS class lookup. Server sends "pos"/"neg"/"zero"
// per money field as `<field>_class` (src/budget_api/models/reports.py
// SignClass). One lookup, reused by every report component that color-codes
// a value by sign — no component re-derives pos/neg/zero from a raw number.

import type { SignClass } from "@/types/report";

export const SIGN_CLASS: Record<SignClass, string> = {
  pos: "pos",
  neg: "neg",
  zero: "zero",
};

// Fallback only for values the `detailed` DTO does not (yet) annotate with a
// server-side `_class` sibling — e.g. KPI role totals (`kpis.*.net_cash`),
// which v4_pipeline accounting.py's `_role_kpis` does not enrich with sign
// classes.
// Mirrors accounting.py `_sign_class` exactly (-0 counts as zero) so the
// classification itself never drifts from the backend's definition.
export function signOf(value: number): SignClass {
  if (value === 0) return "zero";
  return value > 0 ? "pos" : "neg";
}
