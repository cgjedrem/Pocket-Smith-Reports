import { apiGet, apiPut } from "./client";
import type { RunwayResponse, RunwaySettingsResponse, RunwaySettingsUpdate } from "@/types/runway";

export function getRunway(): Promise<RunwayResponse> {
  return apiGet<RunwayResponse>("/api/bills/runway", { cache: "no-store" });
}

export function getRunwaySettings(): Promise<RunwaySettingsResponse> {
  return apiGet<RunwaySettingsResponse>("/api/settings/runway", { cache: "no-store" });
}

export function updateRunwaySettings(body: RunwaySettingsUpdate): Promise<RunwaySettingsResponse> {
  return apiPut<RunwaySettingsResponse>("/api/settings/runway", body, { cache: "no-store" });
}
