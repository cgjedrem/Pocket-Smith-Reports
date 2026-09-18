import { apiGet, apiPut } from "./client";
import type { ApiKeyStatus, ApiKeyUpdate } from "@/types/api";

// API key configured status — never returns raw key.
export function getApiKeyStatus(): Promise<ApiKeyStatus> {
  return apiGet<ApiKeyStatus>("/api/settings/api-key");
}

// Save API key — writes .env, validates via PS /me.
export function updateApiKey(key: string): Promise<ApiKeyStatus> {
  const body: ApiKeyUpdate = { api_key: key };
  return apiPut<ApiKeyStatus>("/api/settings/api-key", body);
}