import { apiGet } from "./client";
import type { LifestyleCreepResponse, ReportLifestyleCreepResponse } from "@/types/lifestyle-creep";

export function getLifestyleCreep(
  month: string,
  threshold: string,
  referenceStart: string,
  referenceEnd: string,
): Promise<LifestyleCreepResponse> {
  const params = new URLSearchParams({
    month,
    threshold_percent: threshold,
    reference_start: referenceStart,
    reference_end: referenceEnd,
  });
  return apiGet<LifestyleCreepResponse>(`/api/bills/lifestyle-creep?${params}`, { cache: "no-store" });
}

export function getEconomyLifestyleCreep(
  month: string,
  threshold: string,
  referenceStart: string,
  referenceEnd: string,
): Promise<ReportLifestyleCreepResponse> {
  const params = new URLSearchParams({
    month,
    threshold_percent: threshold,
    reference_start: referenceStart,
    reference_end: referenceEnd,
    grouping: "report",
  });
  return apiGet<ReportLifestyleCreepResponse>(`/api/bills/lifestyle-creep?${params}`, { cache: "no-store" });
}
