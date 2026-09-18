import { apiGet } from "./client";
import type { SyncResult, SyncStatus } from "@/types/api";

// Trigger sync — GET /api/sync (async, returns 202 + SyncStatus).
// startMonth/endMonth: "YYYY-MM" format (e.g. "2026-07"). Must be start ≤ end.
export function triggerSync(
  startMonth: string, // YYYY-MM
  endMonth: string    // YYYY-MM
): Promise<SyncResult | SyncStatus> {
  const params = new URLSearchParams({
    start_month: startMonth,
    end_month: endMonth,
  });
  return apiGet<SyncResult | SyncStatus>(`/api/sync?${params.toString()}`);
}

// Poll sync status — GET /api/sync/status.
export function getSyncStatus(): Promise<SyncStatus> {
  return apiGet<SyncStatus>("/api/sync/status");
}