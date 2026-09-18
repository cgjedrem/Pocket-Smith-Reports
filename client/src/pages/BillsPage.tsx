// Bills page — wraps BillsDashboard. Window picker (past/future months) +
// explicit Apply button. Month is always the current local month — no
// selector. Committed window is mirrored to query params (?past=, ?future=).

import { useCallback, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ErrorAlert } from "@/components/ErrorAlert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import { BillsDashboard } from "@/components/bills/BillsDashboard";
import { BillsMonthSelect } from "@/components/bills/BillsMonthSelect";
import { HouseholdSummary } from "@/components/bills/HouseholdSummary";
import { BillsNotFoundAlert } from "@/components/bills/BillsNotFoundAlert";
import { BillsStaleBadge } from "@/components/bills/BillsStaleBadge";
import { BillsWarningBanner } from "@/components/bills/BillsWarningBanner";
import { EventDetailDialog } from "@/components/bills/EventDetailDialog";

import { useBillsEvents, useBillsSnapshot } from "@/hooks/useBills";

function currentMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

const DEFAULT_PAST = 3;
const DEFAULT_FUTURE = 12;

// Invalid/missing params fall back to the defaults. Range mirrors
// BillsMonthSelect's clamp (integer 0–240).
function parseWindowParam(raw: string | null, fallback: number): number {
  if (raw == null) return fallback;
  const n = Number(raw);
  return Number.isInteger(n) && n >= 0 && n <= 240 ? n : fallback;
}

export function BillsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Always the current local month. Re-derive each render so month-rollover
  // (e.g. tab open across midnight) picks up the new value on next paint.
  const month = useMemo(() => currentMonth(), []);

  // Committed window — fed to BE fetch. Update only via "Apply" or Enter.
  // Initialised from query params, defaults 3/12.
  const [pastMonths, setPastMonths] = useState(() =>
    parseWindowParam(searchParams.get("past"), DEFAULT_PAST),
  );
  const [futureMonths, setFutureMonths] = useState(() =>
    parseWindowParam(searchParams.get("future"), DEFAULT_FUTURE),
  );
  // Pending window — what the number inputs are bound to. Decoupled so the
  // user can tweak without triggering a re-fetch on every keystroke.
  const [pendingPast, setPendingPast] = useState(pastMonths);
  const [pendingFuture, setPendingFuture] = useState(futureMonths);

  const windowDirty =
    pendingPast !== pastMonths || pendingFuture !== futureMonths;

  const applyWindow = useCallback(() => {
    if (!windowDirty) return;
    setPastMonths(pendingPast);
    setFutureMonths(pendingFuture);
    // Mirror the committed window to the URL — defaults are omitted to
    // keep the query string clean.
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (pendingPast === DEFAULT_PAST) next.delete("past");
        else next.set("past", String(pendingPast));
        if (pendingFuture === DEFAULT_FUTURE) next.delete("future");
        else next.set("future", String(pendingFuture));
        return next;
      },
      { replace: true },
    );
  }, [windowDirty, pendingPast, pendingFuture, setSearchParams]);

  const resetWindow = useCallback(() => {
    setPendingPast(pastMonths);
    setPendingFuture(futureMonths);
  }, [pastMonths, futureMonths]);

  const {
    snapshots,
    loading,
    error,
    notFound,
    refetch,
  } = useBillsSnapshot(month, pastMonths, futureMonths);

  const [dialogState, setDialogState] = useState<{
    open: boolean;
    eventId: string | null;
  }>({ open: false, eventId: null });

  const openDialog = useCallback((eventId: string) => {
    setDialogState({ open: true, eventId });
  }, []);

  const closeDialog = useCallback(() => {
    setDialogState({ open: false, eventId: null });
  }, []);

  const handleSyncClick = useCallback(
    (m: string) => {
      const params = new URLSearchParams({
        start_month: m,
        end_month: m,
      });
      navigate(`/sync?${params.toString()}`);
    },
    [navigate],
  );

  // Render branches (L3).
  if (notFound) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold">Bills</h1>
        <BillsNotFoundAlert month={month} onSyncClick={handleSyncClick} />
      </div>
    );
  }

  if (loading && snapshots.length === 0) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold">Bills</h1>
        <div className="rounded-lg border bg-card p-6 text-sm text-muted-foreground">
          Loading {month}…
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold">Bills</h1>
        <ErrorAlert message={error.detail} />
        <div>
          <Button variant="outline" onClick={refetch}>
            Retry
          </Button>
        </div>
      </div>
    );
  }

  if (snapshots.length === 0) return null;

  // Primary snapshot = current month (first in list).
  const primary = snapshots[0];
  // Aggregate warnings across all snapshots.
  const allWarnings = Array.from(
    new Set(snapshots.flatMap((s) => s.warnings)),
  );

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold">Bills</h1>
            <Badge variant="secondary" aria-label="Current month">
              {month}
            </Badge>
            <BillsStaleBadge syncedAt={primary.synced_at} />
          </div>
          <div className="text-xs text-muted-foreground">
            Last synced {new Date(primary.synced_at).toLocaleString("en-GB")}
            {" · "}
            {snapshots.length} month{snapshots.length === 1 ? "" : "s"} loaded
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <BillsMonthSelect
            disabled={loading}
            initialPastMonths={pendingPast}
            initialFutureMonths={pendingFuture}
            onPastMonthsChange={setPendingPast}
            onFutureMonthsChange={setPendingFuture}
            onApply={applyWindow}
          />
          <Button
            type="button"
            size="sm"
            disabled={!windowDirty || loading}
            onClick={applyWindow}
            aria-label="Apply window"
          >
            Apply
          </Button>
          {windowDirty ? (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              disabled={loading}
              onClick={resetWindow}
              aria-label="Reset window"
            >
              Reset
            </Button>
          ) : null}
        </div>
      </header>

      <BillsWarningBanner warnings={allWarnings} />

      <HouseholdSummary />

      <BillsDashboard onEventClick={openDialog} />

      <EventDetailDialog
        open={dialogState.open}
        id={dialogState.eventId}
        month={month}
        onClose={closeDialog}
      />
    </div>
  );
}
