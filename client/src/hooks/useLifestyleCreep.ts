import { useCallback, useEffect, useState } from "react";
import { getEconomyLifestyleCreep } from "@/api/lifestyle-creep";
import {
  canonicalThreshold, currentLifestyleMonth, lifestyleEvidenceMonths, lifestyleSelectionError,
} from "@/lib/lifestyle-creep";
import { ApiError } from "@/types/api";
import type { MonthlyAmount, ReportLifestyleCreepResponse } from "@/types/lifestyle-creep";

export interface LifestyleCreepState {
  data: ReportLifestyleCreepResponse | null;
  loading: boolean;
  error: ApiError | null;
  retry: () => void;
}

interface RequestState extends Omit<LifestyleCreepState, "retry"> {
  key: string;
}

function responseMatchesSelection(
  data: ReportLifestyleCreepResponse,
  month: string,
  threshold: string,
  referenceStart: string,
  referenceEnd: string,
): boolean {
  const expectedEvidence = lifestyleEvidenceMonths(referenceStart, referenceEnd, month);
  const signedDecimal = /^(?:0|-?(?:[1-9]\d*(?:\.\d*[1-9])?|0\.\d*[1-9]))$/;
  const samplesMatch = (samples: MonthlyAmount[]) => Array.isArray(samples)
    && samples.length === expectedEvidence.length
    && samples.every((sample, index) => sample?.month === expectedEvidence[index]
      && typeof sample.amount === "string" && signedDecimal.test(sample.amount));
  const groupIds = ["shared", "personal_partner_a", "personal_partner_b"];
  const slots = ["", "a", "b"];
  return !!data
    && data.grouping === "report"
    && data.month === month
    && data.threshold_percent === threshold
    && data.reference_start === referenceStart
    && data.reference_end === referenceEnd
    && Array.isArray(data.window_months)
    && data.window_months.length === expectedEvidence.length
    && data.window_months.every((value, index) => value === expectedEvidence[index])
    && Array.isArray(data.evaluation_months)
    && data.evaluation_months.length === 1
    && data.evaluation_months[0] === month
    && data.baseline_months === expectedEvidence.length - 1
    && Array.isArray(data.issues)
    && Array.isArray(data.groups)
    && data.groups.length === 3
    && (data.status === "ready" || data.status === "insufficient_history")
    && (data.history_guidance === null || typeof data.history_guidance === "string")
    && data.groups.every((group, index) => group
      && group.group_id === groupIds[index]
      && group.partner_slot === slots[index]
      && typeof group.label === "string"
      && (index === 0 ? group.partner_id === null
        : group.partner_id === null || (typeof group.partner_id === "string" && !!group.partner_id.trim()))
      && Array.isArray(group.categories)
      && Array.isArray(group.uncategorized_samples)
      && (data.status === "ready"
        ? group.status === "ready" && (index === 0 || !!group.partner_id)
          && samplesMatch(group.uncategorized_samples)
          && new Set(group.categories.map((category) => category.category_id)).size === group.categories.length
          && group.categories.every((category) => category
            && /^[1-9]\d*$/.test(category.category_id)
            && typeof category.category_title === "string"
            && samplesMatch(category.samples)
            && category.comparison?.month === month
            && Array.isArray(category.comparison.baseline_months)
            && category.comparison.baseline_months.length === expectedEvidence.length - 1
            && category.comparison.baseline_months.every((value, i) => value === expectedEvidence[i])
            && [category.comparison.baseline_amount, category.comparison.spending_amount,
              category.comparison.change_amount].every((value) => typeof value === "string" && signedDecimal.test(value))
            && [category.comparison.growth_percent, category.latest_month_over_month_percent]
              .every((value) => value === null || (typeof value === "string" && signedDecimal.test(value)))
            && typeof category.is_above_threshold === "boolean"
            && [null, "zero_baseline", "negative_baseline", "low_frequency"].includes(category.suppression_reason)
            && !(category.is_above_threshold && category.suppression_reason !== null))
        : group.status === "insufficient_history" && group.categories.length === 0
          && group.uncategorized_samples.length === 0))
    && (data.status !== "ready" || (data.issues.length === 0
      && data.groups[1].partner_id !== data.groups[2].partner_id
      && new Set(data.groups.flatMap((group) => group.categories.map((category) => category.category_id))).size
        === data.groups.reduce((count, group) => count + group.categories.length, 0)));
}

export function useLifestyleCreep(
  month: string, rawThreshold: string, referenceStart: string, referenceEnd: string,
): LifestyleCreepState {
  const threshold = canonicalThreshold(rawThreshold);
  const [attempt, setAttempt] = useState(0);
  const key = `report:${month}:${referenceStart}:${referenceEnd}:${threshold}:${attempt}`;
  const [state, setState] = useState<RequestState>({
    key: "", data: null, loading: true, error: null,
  });
  const retry = useCallback(() => setAttempt((value) => value + 1), []);

  useEffect(() => {
    let cancelled = false;
    const current = currentLifestyleMonth();
    if (threshold === null || lifestyleSelectionError(month, referenceStart, referenceEnd, current)) {
      setState({ key, data: null, loading: false, error: new ApiError("Invalid detector selection", 400) });
      return;
    }

    setState({ key, data: null, loading: true, error: null });
    getEconomyLifestyleCreep(month, threshold, referenceStart, referenceEnd)
      .then((data) => {
        if (cancelled) return;
        if (!responseMatchesSelection(data, month, threshold, referenceStart, referenceEnd)) {
          throw new ApiError("History response did not match the selected target, reference period, and threshold", 0);
        }
        setState({ key, data, loading: false, error: null });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setState({
          key, data: null, loading: false,
          error: error instanceof ApiError ? error : new ApiError("Could not load lifestyle history", 0),
        });
      });
    // Existing apiGet has no signal option — cleanup guards both completions.
    return () => { cancelled = true; };
  }, [month, threshold, referenceStart, referenceEnd, attempt, key]);

  // Hide old selection before effects run, including explicit Retry.
  return state.key === key
    ? { data: state.data, loading: state.loading, error: state.error, retry }
    : { data: null, loading: true, error: null, retry };
}
