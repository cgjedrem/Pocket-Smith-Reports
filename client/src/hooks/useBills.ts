// Hooks — fetch from /api/bills/* endpoints + auto-hydrate bills-source on snapshot success.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { getEvent, getEvents, getSnapshot } from "@/api/bills";
import { ApiError } from "@/types/api";
import type {
  BillsEvent,
  BillsEventList,
  BillsEventsFilters,
  BillsSnapshot,
} from "@/types/bills";

import {
  mapSnapshotToEvents,
  mapSnapshotToMonthData,
} from "@/lib/bills-mapper";
import { hydrate } from "@/lib/bills-source";

// Generate a list of YYYY-MM strings centered on `month`.
// `pastMonths` backward + `futureMonths` forward. Current month included.
function expandMonthRange(
  month: string,
  pastMonths: number,
  futureMonths: number,
): string[] {
  const out: string[] = [];
  const [yStr, mStr] = month.split("-");
  const baseYear = Number(yStr);
  const baseMonth = Number(mStr) - 1; // 0-based
  for (let i = -pastMonths; i <= futureMonths; i++) {
    const d = new Date(baseYear, baseMonth + i, 1);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    out.push(`${y}-${m}`);
  }
  return out;
}

export interface BillsSnapshotState {
  months: string[]; // months being fetched
  snapshots: BillsSnapshot[];
  loading: boolean;
  error: ApiError | null;
  notFound: boolean;
  refetch: () => void;
}

// Fetch /api/bills/dashboard for `pastMonths + 1 + futureMonths` months.
// On 200 for all → hydrate bills-source with array of MonthData.
// 404 for the current month = page takeover. Missing adjacent months = skipped.
export function useBillsSnapshot(
  month: string,
  pastMonths = 3,
  futureMonths = 12,
): BillsSnapshotState {
  const targetMonths = useMemo(
    () => expandMonthRange(month, pastMonths, futureMonths),
    [month, pastMonths, futureMonths],
  );

  const [snapshots, setSnapshots] = useState<BillsSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [tick, setTick] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;

    let cancelled = false;
    setLoading(true);
    setError(null);
    setNotFound(false);
    setSnapshots([]);

    Promise.all(
      targetMonths.map((m) =>
        getSnapshot(m).then(
          (s) => ({ ok: true as const, month: m, snapshot: s }),
          // Normalize plain Error (e.g. network) into ApiError so consumers
          // can read `.status` safely. Unknown status = 0 (non-HTTP sentinel).
          (err: unknown) => ({
            ok: false as const,
            month: m,
            err:
              err instanceof ApiError
                ? err
                : new ApiError(
                    err instanceof Error ? err.message : "Network error",
                    0,
                  ),
          }),
        ),
      ),
    )
      .then((results) => {
        if (cancelled) return;
        const okResults = results.filter(
          (r): r is { ok: true; month: string; snapshot: BillsSnapshot } => r.ok,
        );
        const primaryResult = results.find((r) => r.month === month);

        // Primary month 404 → page takeover.
        if (
          primaryResult &&
          !primaryResult.ok &&
          primaryResult.err.status === 404
        ) {
          setNotFound(true);
          setError(null);
          hydrate([], []);
          return;
        }

        // Primary month errored (non-404) → surface error.
        if (primaryResult && !primaryResult.ok) {
          setError(primaryResult.err);
          setNotFound(false);
          return;
        }

        const snapList = okResults.map((r) => r.snapshot);
        setSnapshots(snapList);
        setNotFound(false);
        // Sort by month for chronological rendering. No next-month
        // plumbing — BE everyday_budget already encodes m+1 inputs.
        const sorted = [...snapList].sort((a, b) =>
          a.month.localeCompare(b.month),
        );
        const mappedMonths = sorted.map(mapSnapshotToMonthData);
        const allEvents = snapList.flatMap(mapSnapshotToEvents);
        hydrate(mappedMonths, allEvents);
      })
      .catch((err: ApiError) => {
        if (cancelled) return;
        setError(err);
        setNotFound(false);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [month, pastMonths, futureMonths, tick]);

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  return {
    months: targetMonths,
    snapshots,
    loading,
    error,
    notFound,
    refetch,
  };
}

export interface BillsEventsState {
  events: BillsEvent[];
  total: number;
  loading: boolean;
  error: ApiError | null;
  refetch: () => void;
}

// Fetch /api/bills/dashboard/events?month=X[&filters].
export function useBillsEvents(
  month: string,
  filters?: BillsEventsFilters,
): BillsEventsState {
  const [list, setList] = useState<BillsEventList>({ events: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [tick, setTick] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  // Stringify filters for stable dep tracking.
  const filterKey = filters ? JSON.stringify(filters) : "";

  useEffect(() => {
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;

    let cancelled = false;
    setLoading(true);
    setError(null);

    getEvents(month, filters)
      .then((res) => {
        if (cancelled) return;
        setList(res);
      })
      .catch((err: ApiError) => {
        if (cancelled) return;
        setError(err);
        setList({ events: [], total: 0 });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
      ac.abort();
    };
    // filterKey is the dep — JSON.stringify above is stable per filter object.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [month, filterKey, tick]);

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  return {
    events: list.events,
    total: list.total,
    loading,
    error,
    refetch,
  };
}

export interface BillsEventState {
  event: BillsEvent | null;
  loading: boolean;
  error: ApiError | null;
  notFound: boolean;
  refetch: () => void;
}

// Fetch /api/bills/dashboard/event?id=X&month=Y.
// Only fires when `open === true` (saves bandwidth when dialog closed).
export function useBillsEvent(
  id: string | null,
  month: string,
  open: boolean,
): BillsEventState {
  const [event, setEvent] = useState<BillsEvent | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [tick, setTick] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    abortRef.current?.abort();
    if (!open || !id) {
      setEvent(null);
      setError(null);
      setNotFound(false);
      setLoading(false);
      return;
    }

    const ac = new AbortController();
    abortRef.current = ac;

    let cancelled = false;
    setLoading(true);
    setError(null);
    setNotFound(false);

    getEvent(id, month)
      .then((ev) => {
        if (cancelled) return;
        setEvent(ev);
      })
      .catch((err: ApiError) => {
        if (cancelled) return;
        if (err.status === 404) {
          setNotFound(true);
          setError(null);
        } else {
          setError(err);
          setNotFound(false);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [id, month, open, tick]);

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  return { event, loading, error, notFound, refetch };
}
