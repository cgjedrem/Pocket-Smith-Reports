import { apiDelete, apiGet, apiPost, apiPut } from "./client";
import type { Partner, PartnerCreate, PartnerList, PartnerUpdate } from "@/types/api";

// List partners.
export function listPartners(): Promise<PartnerList> {
  return apiGet<PartnerList>("/api/partners");
}

// Create partner.
export function createPartner(label: string): Promise<Partner> {
  const body: PartnerCreate = { label };
  return apiPost<Partner>("/api/partners", body);
}

// Update partner label.
export function updatePartner(id: string, label: string): Promise<Partner> {
  const body: PartnerUpdate = { label };
  return apiPut<Partner>(`/api/partners/${encodeURIComponent(id)}`, body);
}

// Delete partner.
export function deletePartner(id: string): Promise<void> {
  return apiDelete<void>(`/api/partners/${encodeURIComponent(id)}`);
}