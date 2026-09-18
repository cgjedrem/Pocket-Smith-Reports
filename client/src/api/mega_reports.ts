// Mega report API client — wraps apiGet/apiPost for /api/mega-reports/* endpoints.
// Mirrors api/reports.ts pattern. PDF export uses raw fetch → Blob.

import { apiGet, apiPost, BASE_URL } from "./client";
import { ApiError } from "@/types/api";
import type {
  MegaReportList,
  MegaReportResponse,
} from "@/types/mega_report";
import type { GenerateStatus } from "@/types/report";

// Re-export getMonths for year picker + range validation (F1.2 endpoint).
export { getMonths } from "./reports";

// List generated mega reports — sorted newest first.
export function getMegaReports(): Promise<MegaReportList> {
  return apiGet<MegaReportList>("/api/mega-reports");
}

// Get mega report JSON — 404 if not generated, 400 if invalid/missing months.
export function getMegaReport(start: string, end: string): Promise<MegaReportResponse> {
  return apiGet<MegaReportResponse>(
    `/api/mega-reports/${encodeURIComponent(start)}/${encodeURIComponent(end)}`
  );
}

// Start async generation — 202 + GenerateStatus.
export function generateMegaReport(start: string, end: string): Promise<GenerateStatus> {
  return apiPost<GenerateStatus>(
    `/api/mega-reports/${encodeURIComponent(start)}/${encodeURIComponent(end)}/generate`
  );
}

// Poll generation status — 404 if never run.
export function getMegaStatus(start: string, end: string): Promise<GenerateStatus> {
  return apiGet<GenerateStatus>(
    `/api/mega-reports/${encodeURIComponent(start)}/${encodeURIComponent(end)}/status`
  );
}

// Export PDF — binary stream. Triggers browser download.
// Returns Blob on success. Throws ApiError on non-2xx.
// Caller can pass AbortSignal to cancel an in-flight export (e.g. when
// dialog closes mid-request).
export async function exportMegaPdf(
  start: string,
  end: string,
  signal?: AbortSignal,
): Promise<Blob> {
  const url = `${BASE_URL}/api/mega-reports/${encodeURIComponent(start)}/${encodeURIComponent(end)}/pdf`;
  let res: Response;
  try {
    res = await fetch(url, { method: "POST", headers: {}, signal });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
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
    throw new ApiError(detail, res.status);
  }
  return res.blob();
}