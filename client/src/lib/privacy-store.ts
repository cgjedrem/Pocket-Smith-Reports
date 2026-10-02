// Privacy store — global "hide amounts" flag (contracts/privacy-store.md §1).
// Module-store pattern like lib/bills-source.ts: plain module state +
// subscribe + snapshot getter, wrapped for React via useSyncExternalStore.
// Format functions read the store at render time — no prop drilling.
// I-4: touches localStorage only; no network, no financial-data access.

import { useSyncExternalStore } from "react";

// Replacement text for any masked monetary amount.
export const AMOUNT_MASK = "****";

// Persisted flag key. "1" = hidden; anything else = visible.
const STORAGE_KEY = "psr:hide-amounts";

// null = not yet read (lazy init — module import never touches storage,
// so jsdom/SSR/disabled storage can't throw at import time).
let hidden: boolean | null = null;
const subscribers = new Set<() => void>();

// I-2: "1" → hidden; anything else/unavailable → visible. Never throws.
function readPersisted(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

// Best-effort persist. Never throws (storage disabled/full).
function writePersisted(value: boolean): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, value ? "1" : "0");
  } catch {
    // In-memory state still works without storage.
  }
}

function current(): boolean {
  if (hidden === null) hidden = readPersisted();
  return hidden;
}

// Subscribe to flag changes. Returns cleanup function.
export function subscribe(listener: () => void): () => void {
  subscribers.add(listener);
  return () => {
    subscribers.delete(listener);
  };
}

// Snapshot getter — boolean primitive, referentially stable between
// mutations (I-1, useSyncExternalStore-safe).
export function isAmountsHidden(): boolean {
  return current();
}

// I-3: write storage BEFORE notifying subscribers.
function mutate(next: boolean): void {
  hidden = next;
  writePersisted(next);
  subscribers.forEach((fn) => fn());
}

export function toggleAmountsHidden(): void {
  mutate(!current());
}

export function setAmountsHidden(value: boolean): void {
  mutate(value);
}

// React hook wrapper — re-renders the caller on toggle.
export function useAmountsHidden(): boolean {
  return useSyncExternalStore(subscribe, isAmountsHidden, isAmountsHidden);
}

// Last-mile masking for format functions. "" stays "" — an absent value
// must never become a mask.
export function maskAmount(formatted: string): string {
  if (formatted === "") return "";
  return current() ? AMOUNT_MASK : formatted;
}
