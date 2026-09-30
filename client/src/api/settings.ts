import { apiGet, apiPut } from "./client";
import type {
  ApiKeyStatus,
  ApiKeyUpdate,
  SplitConfig,
  SplitConfigResponse,
  SplitConfigUpdate,
} from "@/types/api";

// API key configured status — never returns raw key.
export function getApiKeyStatus(): Promise<ApiKeyStatus> {
  return apiGet<ApiKeyStatus>("/api/settings/api-key");
}

// Save API key — writes .env, validates via PS /me.
export function updateApiKey(key: string): Promise<ApiKeyStatus> {
  const body: ApiKeyUpdate = { api_key: key };
  return apiPut<ApiKeyStatus>("/api/settings/api-key", body);
}

// Common-economy split config — GET returns a synthesized default
// (enabled=false, sections=["home","common","trips"]) when no
// split_config.json exists yet (never written to disk just by reading).
// Additive `labels` — real partner_a/partner_b display names resolved
// server-side (never persisted, GET-only — see SplitConfigResponse).
export function getSplitConfig(): Promise<SplitConfigResponse> {
  return apiGet<SplitConfigResponse>("/api/settings/split");
}

// Save split config — 422 shares-sum-!=100, 400 shape/section errors
// (caller pre-validates sum==100 client-side too; server is the source of
// truth).
export function updateSplitConfig(config: SplitConfigUpdate): Promise<SplitConfig> {
  return apiPut<SplitConfig>("/api/settings/split", config);
}