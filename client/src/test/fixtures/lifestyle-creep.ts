import type { LifestyleCreepResponse, ReportLifestyleCreepResponse, ReportLifestyleGroup } from "@/types/lifestyle-creep";
import { lifestyleEvidenceMonths, shiftLifestyleMonth } from "@/lib/lifestyle-creep";

// Synthetic contract example — no dashboard fallback.
export function lifestyleFixture(): LifestyleCreepResponse {
  return lifestylePeriodFixture("2026-07", "2026-09", "20", "2026-10");
}

export function economyFixture(): ReportLifestyleCreepResponse {
  return economyPeriodFixture("2026-07", "2026-09", "20", "2026-10");
}

export function economyPeriodFixture(
  referenceStart: string, referenceEnd: string, threshold = "20", target = shiftLifestyleMonth(referenceEnd, 1),
): ReportLifestyleCreepResponse {
  const { partners, ...selection } = lifestylePeriodFixture(referenceStart, referenceEnd, threshold, target);
  const personal = partners[0];
  const group = (
    group_id: ReportLifestyleGroup["group_id"], label: string,
    partner_id: string | null, partner_slot: ReportLifestyleGroup["partner_slot"],
  ): ReportLifestyleGroup => ({
    group_id, label, partner_id, partner_slot, status: "ready",
    categories: [], uncategorized_samples: structuredClone(personal.uncategorized_samples),
  });
  const shared = group("shared", "Shared economy", null, "");
  const a = group("personal_partner_a", "Partner A", "partner_a", "a");
  const b = group("personal_partner_b", "Partner B", "partner_b", "b");
  a.categories = structuredClone(personal.categories);
  for (const [destination, id, title] of [
    [shared, "920001", "Home category"],
    [shared, "920002", "Common category"],
    [b, "930001", "Category B"],
  ] as const) {
    destination.categories.push({
      ...structuredClone(personal.categories[0]),
      category_id: id, category_title: title,
      samples: selection.window_months.map((month) => ({ month, amount: "20" })),
      comparison: {
        month: target, baseline_months: selection.window_months.slice(0, -1),
        baseline_amount: "20", spending_amount: "20", change_amount: "0", growth_percent: "0",
      },
      latest_month_over_month_percent: target === shiftLifestyleMonth(referenceEnd, 1) ? "0" : null,
      is_above_threshold: false,
    });
  }
  return { ...selection, status: "ready", grouping: "report", history_guidance: null, issues: [], groups: [shared, a, b] };
}

export function insufficientEconomyFixture(): ReportLifestyleCreepResponse {
  const data = economyFixture();
  data.status = "insufficient_history";
  data.history_guidance = "Check report mappings, then explicitly re-sync every selected month with one consistent configuration. Reading or retrying never creates report-economy history.";
  data.issues = [{ month: data.month, group_id: null, partner_id: null, code: "legacy_history", reason: null }];
  for (const group of data.groups) {
    group.status = "insufficient_history";
    group.partner_id = null;
    group.categories = [];
    group.uncategorized_samples = [];
  }
  return data;
}

export function lifestylePeriodFixture(
  referenceStart: string, referenceEnd: string, threshold = "20", target = shiftLifestyleMonth(referenceEnd, 1),
): LifestyleCreepResponse {
  const months = lifestyleEvidenceMonths(referenceStart, referenceEnd, target);
  const referenceMonths = months.slice(0, -1);
  const referenceAmounts = referenceMonths.map((_, index) => index === referenceMonths.length - 1 ? 130 : 100);
  const baseline = referenceAmounts.reduce((sum, amount) => sum + amount, 0) / referenceAmounts.length;
  const spending = 140;
  const growth = (spending / baseline - 1) * 100;
  const adjacent = target === shiftLifestyleMonth(referenceEnd, 1)
    ? String((spending / referenceAmounts.at(-1)! - 1) * 100)
    : null;
  return {
    month: target,
    reference_start: referenceStart,
    reference_end: referenceEnd,
    window_months: months,
    evaluation_months: [target],
    baseline_months: referenceMonths.length,
    threshold_percent: threshold,
    status: "ready",
    issues: [],
    partners: [{
      partner_id: "partner_a",
      partner_slot: "a",
      partner: "Partner A",
      status: "ready",
      categories: [{
        category_id: "910001",
        category_title: "Category A",
        samples: months.map((month, index) => ({
          month,
          amount: index === referenceAmounts.length ? String(spending) : String(referenceAmounts[index]),
        })),
        comparison: {
          month: target,
          baseline_months: referenceMonths,
          baseline_amount: String(baseline),
          spending_amount: String(spending),
          change_amount: String(spending - baseline),
          growth_percent: String(growth),
        },
        latest_month_over_month_percent: adjacent,
        is_above_threshold: growth > Number(threshold),
        suppression_reason: null,
      }],
      uncategorized_samples: months.map((month) => ({ month, amount: "0" })),
    }],
  };
}
