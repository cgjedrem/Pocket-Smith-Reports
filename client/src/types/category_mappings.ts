// TS types — match backend Pydantic models (src/budget_api/models/category_mappings.py).

export type KpiRole =
  | "income"
  | "savings"
  | "spend"
  | "personal_spend"
  | "investment"
  | "exclude";

export type DetailedSection =
  | "income_salary"
  | "income_third_party"
  | "savings"
  | "home"
  | "common"
  | "personal_partner_a"
  | "personal_partner_b"
  | "trips"
  | "cc_payments"
  | "excluded";

export interface CategoryMapping {
  category_id: string;
  category_title: string;
  kpi_role: KpiRole | null;
  detailed_section: DetailedSection | null;
}

export interface CategoryMappingList {
  categories: CategoryMapping[];
}

export interface CategoryMappingUpdate {
  kpi_role: KpiRole;
  detailed_section: DetailedSection;
}

// Option lists for dropdowns — order matches design doc.
export const KPI_ROLE_OPTIONS: KpiRole[] = [
  "income",
  "savings",
  "spend",
  "personal_spend",
  "investment",
  "exclude",
];

export const DETAILED_SECTION_OPTIONS: DetailedSection[] = [
  "income_salary",
  "income_third_party",
  "savings",
  "home",
  "common",
  "personal_partner_a",
  "personal_partner_b",
  "trips",
  "cc_payments",
  "excluded",
];

// Display label for a detailed-section option. Personal sections resolve
// from config-driven partner labels (payload) — missing labels fall back
// to neutral "Partner A/B". Other sections keep their raw contract value.
export function detailedSectionLabel(
  section: DetailedSection,
  partnerLabels: Record<string, string>,
): string {
  if (section === "personal_partner_a") {
    return `Personal — ${partnerLabels["partner_a"] ?? "Partner A"}`;
  }
  if (section === "personal_partner_b") {
    return `Personal — ${partnerLabels["partner_b"] ?? "Partner B"}`;
  }
  return section;
}