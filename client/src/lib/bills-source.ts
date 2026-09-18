// Source module — single swap point for the existing component tree.
// Components still call getMonths() / getAllEvents() synchronously at render.
// This module re-exports from mock fallback when no hydration has happened,
// or returns live mapped data after hydrate() is called by the hook.

import {
  getAllEvents as mockGetAllEvents,
  getMonths as mockGetMonths,
} from "@/components/bills/finance-data";
import type { FinanceEvent, MonthData } from "@/types/api";

let monthlyDataList: MonthData[] = [];
let eventsList: FinanceEvent[] = [];
const subscribers = new Set<() => void>();

// Subscribe to hydrate notifications. Returns cleanup function.
export function subscribe(listener: () => void): () => void {
  subscribers.add(listener);
  return () => {
    subscribers.delete(listener);
  };
}

// Returns hydrated months if any, otherwise mock fallback (12 months).
export function getMonths(): MonthData[] {
  return monthlyDataList.length > 0 ? monthlyDataList : mockGetMonths();
}

// Returns events if hydrated, otherwise mock fallback.
export function getAllEvents(): FinanceEvent[] {
  return eventsList.length > 0 ? eventsList : mockGetAllEvents();
}

// Hydrate source with mapped months (1..N). Triggers re-render.
// Idempotent — same input → same output, safe under StrictMode double-mount.
export function hydrate(months: MonthData[], events: FinanceEvent[]): void {
  monthlyDataList = months;
  eventsList = events;
  subscribers.forEach((fn) => fn());
}

// Reset to mock fallback (used on error / 404 — keeps existing tests passing).
export function reset(): void {
  monthlyDataList = [];
  eventsList = [];
  subscribers.forEach((fn) => fn());
}

// Test-only: peek current hydrated state.
export function _peek(): {
  monthsCount: number;
  eventsCount: number;
} {
  return { monthsCount: monthlyDataList.length, eventsCount: eventsList.length };
}
