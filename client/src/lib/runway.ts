import { formatKr } from "@/components/bills/finance-format";
import { maskAmount } from "@/lib/privacy-store";
import type { RunwayIssue, RunwayOwner, RunwayAccountOption } from "@/types/runway";

// No conversion. Known foreign currency must not wear a kr label.
export function runwayMoney(value: number | null, currency: string | null): string {
  if (value === null) return "Unavailable";
  if (!currency || currency === "NOK") return formatKr(value);
  return maskAmount(`${formatKr(value).replace(/ kr$/, "")} ${currency}`);
}

export function runwayMonth(month: string): string {
  const [year, number] = month.split("-").map(Number);
  return new Date(year, number - 1, 1).toLocaleDateString("en-GB", { month: "long", year: "numeric" });
}

export function runwayDate(date: string | null): string {
  return date ? date.replace("T", " ") : "Unknown";
}

const reasons: Record<string, string> = {
  no_selection: "No selected reserve accounts",
  invalid_settings: "Saved runway settings could not be read. Retry settings before saving.",
  invalid_selection: "Saved selection is no longer eligible. Review liquid account settings.",
  account_missing: "Selected account is missing. Remove it from the selection or restore its mapping.",
  account_unowned: "Account has no configured owner.",
  account_excluded: "Account is excluded from reporting.",
  account_type_ineligible: "Only checking and savings accounts can be selected.",
  missing_balance: "Recorded balance missing — not treated as zero.",
  invalid_balance: "Recorded balance invalid — not treated as zero.",
  insufficient_history: "Fewer than two usable completed months. Average and runway unavailable.",
  missing_source: "Monthly source missing.",
  invalid_source: "Local source invalid. Affected observations unavailable.",
  partial_source: "Month only partially covered or collected before month end.",
  unproven_zero: "Zero spending lacks complete-month evidence.",
  ownership_incomplete: "Spending ownership incomplete — no partial household total.",
  sources_changing: "Local sources are changing. Retry runway when stable.",
  currency_conflict: "Incompatible currencies — affected comparison unavailable; no conversion.",
  nonpositive_reserves: "Selected reserves are zero or negative. Runway undefined.",
  nonpositive_burn: "Recorded spending is zero. Runway undefined.",
  coverage_unverified: "Month coverage unverified — recorded transactions only.",
  currency_unverified: "Single-currency assumption; currency unverified.",
  source_stale: "Source older than 24 hours.",
  source_date_unknown: "Source collection date unknown.",
  balance_stale: "Balance older than 24 hours.",
  balance_date_unknown: "Balance date unknown.",
  balance_date_unverified: "Balance date unverified.",
  classification_unverified: "Category classification unverified; exclusions may be incomplete.",
  excluded_months: "Some candidate months excluded. Average uses included months only.",
  source_times_differ: "Sources collected at different times; not one synchronized snapshot.",
};

export function runwayIssueText(
  issue: RunwayIssue,
  owners: RunwayOwner[] = [],
  accounts: Pick<RunwayAccountOption, "id" | "name">[] = [],
): string {
  const scope = [
    issue.month ? runwayMonth(issue.month) : null,
    issue.partner_id ? owners.find((owner) => owner.partner_id === issue.partner_id)?.label ?? issue.partner_id : null,
    issue.account_id ? accounts.find((account) => account.id === issue.account_id)?.name ?? `Account ${issue.account_id}` : null,
  ].filter(Boolean).join(" · ");
  const text = Object.hasOwn(reasons, issue.code)
    ? reasons[issue.code]
    : "Additional source limitation. Refresh local data and retry.";
  return scope ? `${scope}: ${text}` : text;
}
