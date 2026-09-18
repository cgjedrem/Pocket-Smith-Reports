// Report API client — wraps apiGet/apiPost for /api/reports/* endpoints.

import { apiGet, apiPost } from "./client";
import type { GenerateStatus, MonthList, ReportResponse } from "@/types/report";

// List months with synced data — sorted descending.
export function getMonths(): Promise<MonthList> {
  return apiGet<MonthList>("/api/reports/months");
}

// Get monthly report JSON — 404 if not generated.
export function getReport(month: string): Promise<ReportResponse> {
  return apiGet<ReportResponse>(
    `/api/reports/monthly/${encodeURIComponent(month)}`
  );
}

// Start async generation — 202 + GenerateStatus.
export function generateReport(month: string): Promise<GenerateStatus> {
  return apiPost<GenerateStatus>(
    `/api/reports/monthly/${encodeURIComponent(month)}/generate`
  );
}

// Poll generation status — 404 if never run.
export function getStatus(month: string): Promise<GenerateStatus> {
  return apiGet<GenerateStatus>(
    `/api/reports/monthly/${encodeURIComponent(month)}/status`
  );
}

// Export PDF — binary stream. Triggers browser download.
// Returns Blob on success. Throws ApiError on non-2xx.
export async function exportPdf(month: string): Promise<Blob> {
  const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8001";
  const url = `${BASE_URL}/api/reports/monthly/${encodeURIComponent(month)}/pdf`;
  let res: Response;
  try {
    res = await fetch(url, { method: "POST", headers: {} });
  } catch {
    throw new Error("Cannot reach server");
  }
  if (!res.ok) {
    // Parse error detail — match api client pattern.
    const text = await res.text();
    let detail = "PDF export failed";
    if (text) {
      try {
        const parsed = JSON.parse(text);
        if (parsed && typeof parsed === "object" && "detail" in parsed) {
          detail = String((parsed as { detail: unknown }).detail);
        }
      } catch {
        detail = res.statusText || "PDF export failed";
      }
    }
    // Use ApiError shape — import lazily to avoid cycle.
    const { ApiError } = await import("@/types/api");
    throw new ApiError(detail, res.status);
  }
  return res.blob();
}