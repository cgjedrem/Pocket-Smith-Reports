// API client — 3 thin wrappers around apiGet for the bills dashboard endpoints.
// All endpoints serve from the per-month snapshot written by sub-feature 1 sync.

import { apiGet } from "./client";
import type {
  BillsEvent,
  BillsEventList,
  BillsEventsFilters,
  BillsSnapshot,
} from "@/types/bills";

// GET /api/bills/dashboard?month=YYYY-MM
// 200 → BillsSnapshot
// 404 → throws ApiError (snapshot missing — page should show Run sync)
// 400/500 → throws ApiError
export function getSnapshot(month: string): Promise<BillsSnapshot> {
  return apiGet<BillsSnapshot>(
    `/api/bills/dashboard?month=${encodeURIComponent(month)}`,
  );
}

// GET /api/bills/dashboard/events?month=YYYY-MM[&partner_id=&type=&category=&from=&to=&order=&limit=]
// 200 → BillsEventList (events + total)
// 400 → throws ApiError with detail as string[] (validation errors)
// 404/500 → throws ApiError
export function getEvents(
  month: string,
  filters?: BillsEventsFilters,
): Promise<BillsEventList> {
  const params = new URLSearchParams({ month });
  // Identity key — supersedes the legacy `partner=` label param server-side.
  if (filters?.partner_id) params.set("partner_id", filters.partner_id);
  if (filters?.type) params.set("type", filters.type);
  if (filters?.category) params.set("category", filters.category);
  if (filters?.from) params.set("from", filters.from);
  if (filters?.to) params.set("to", filters.to);
  if (filters?.order) params.set("order", filters.order);
  if (filters?.limit !== undefined) params.set("limit", String(filters.limit));
  return apiGet<BillsEventList>(`/api/bills/dashboard/events?${params.toString()}`);
}

// GET /api/bills/dashboard/event?id=X&month=YYYY-MM
// 200 → BillsEvent (bare dict)
// 404 → throws ApiError("Event {id} not found in {month}")
// 400/500 → throws ApiError
export function getEvent(id: string, month: string): Promise<BillsEvent> {
  const params = new URLSearchParams({ id, month });
  return apiGet<BillsEvent>(`/api/bills/dashboard/event?${params.toString()}`);
}
