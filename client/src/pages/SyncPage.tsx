import { useCallback, useEffect, useRef, useState } from "react";

import { getSyncStatus, triggerSync } from "@/api/sync";
import { EmptyState } from "@/components/EmptyState";
import { ErrorAlert } from "@/components/ErrorAlert";
import { MonthPicker } from "@/components/MonthPicker";
import { RowCountTable } from "@/components/RowCountTable";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";

import type { SyncStatus } from "@/types/api";

// Poll interval — 2s per design.
const POLL_MS = 2000;

function currentMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function monthAgo(n: number): string {
  const d = new Date();
  d.setMonth(d.getMonth() - n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

type LoadState = "loading" | "empty" | "ready";

export function SyncPage() {
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [startMonth, setStartMonth] = useState(monthAgo(3));
  const [endMonth, setEndMonth] = useState(currentMonth());
  const [syncing, setSyncing] = useState(false);

  // Poll ref — cleanup on unmount.
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const startPoll = useCallback(() => {
    stopPoll();
    pollRef.current = setInterval(async () => {
      try {
        const s = await getSyncStatus();
        setStatus(s);
        if (s.status !== "running") {
          stopPoll();
          setSyncing(false);
        }
      } catch {
        // network blip — keep polling, clear on next tick.
      }
    }, POLL_MS);
  }, [stopPoll]);

  // Mount: check existing status.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await getSyncStatus();
        if (cancelled) return;
        setStatus(s);
        setLoadState("ready");
        if (s.status === "running" && !cancelled) {
          setSyncing(true);
          startPoll();
        }
      } catch (err) {
        if (cancelled) return;
        // 404 → never synced.
        const detail = (err as { detail?: string })?.detail;
        if (detail && detail.includes("no sync")) {
          setLoadState("empty");
        } else {
          setError(detail ?? "Cannot reach server");
          setLoadState("ready");
        }
      }
    })();
    return () => {
      cancelled = true;
      stopPoll();
    };
  }, [startPoll, stopPoll]);

  const handleSync = useCallback(async () => {
    setError(null);
    // Client-side guard — start must be ≤ end (YYYY-MM string compare).
    if (startMonth > endMonth) {
      setError("Start month must be before or equal to end month");
      return;
    }
    setSyncing(true);
    try {
      await triggerSync(startMonth, endMonth);
      // 202 → start polling.
      startPoll();
    } catch (err) {
      setSyncing(false);
      const detail = (err as { detail?: string })?.detail;
      setError(detail ?? "Cannot reach server");
    }
  }, [startMonth, endMonth, startPoll]);

  return (
    <div className="rounded-lg border border-border bg-card p-6">
      <h1 className="mb-4">Sync</h1>

      <div className="mb-4 flex flex-wrap items-end gap-4">
        <MonthPicker
          label="Start month"
          value={startMonth}
          onChange={setStartMonth}
          disabled={syncing}
        />
        <MonthPicker
          label="End month"
          value={endMonth}
          onChange={setEndMonth}
          disabled={syncing}
        />
        <Button type="button" onClick={handleSync} disabled={syncing} size="lg">
          {syncing ? "Syncing..." : "Sync"}
        </Button>
      </div>

      {error && <ErrorAlert message={error} />}

      {loadState === "loading" && (
        <p className="text-sm text-muted-foreground">Loading...</p>
      )}

      {loadState === "empty" && !syncing && (
        <EmptyState message="No sync yet — pick a range and click Sync." />
      )}

      {status && (
        <div className="mt-4 border-t border-border pt-4">
          <div className="mb-2 flex items-center gap-2">
            <span className="min-w-[5rem] text-sm text-muted-foreground">
              Status:
            </span>
            <StatusBadge status={status.status} />
          </div>
          {status.status === "success" && (
            <>
              <div className="mb-2 flex items-center gap-2">
                <span className="min-w-[5rem] text-sm text-muted-foreground">
                  Last sync:
                </span>
                <span>{new Date(status.last_sync).toLocaleString()}</span>
              </div>
              <div className="mb-2 flex items-center gap-2">
                <span className="min-w-[5rem] text-sm text-muted-foreground">
                  Range:
                </span>
                <span>
                  {status.start_month} → {status.end_month} ({status.months_synced} months)
                </span>
              </div>
              <RowCountTable rowCounts={status.row_counts} />
            </>
          )}
          {status.status === "failed" && <ErrorAlert errors={status.errors} />}
        </div>
      )}
    </div>
  );
}