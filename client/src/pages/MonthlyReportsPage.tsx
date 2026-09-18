// Monthly Reports page — sidebar + report view container.
// Fetches months on mount. Manages selected month state.

import { useCallback, useEffect, useState } from "react";

import { getMonths } from "@/api/reports";
import { EmptyState } from "@/components/EmptyState";
import { ErrorAlert } from "@/components/ErrorAlert";
import { MonthSidebar } from "@/components/reports/MonthSidebar";
import { ReportView } from "@/components/reports/ReportView";

type LoadState = "loading" | "empty" | "ready";

export function MonthlyReportsPage() {
  const [months, setMonths] = useState<string[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const list = await getMonths();
      setMonths(list.months);
      // Auto-select newest if none selected.
      if (list.months.length > 0) {
        setSelected((prev) => prev ?? list.months[0]);
      } else {
        setLoadState("empty");
        return;
      }
      setLoadState("ready");
    } catch (err) {
      setError((err as { detail?: string })?.detail ?? "Cannot reach server");
      setLoadState("ready");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="rounded-lg border border-border bg-card p-6">
      <h1 className="mb-4">Monthly Reports</h1>

      {error && <ErrorAlert message={error} />}

      {loadState === "loading" && (
        <p className="text-sm text-muted-foreground">Loading...</p>
      )}

      {loadState === "empty" && (
        <EmptyState message="No synced months. Run sync first." />
      )}

      {loadState === "ready" && months.length > 0 && (
        selected && (
          <ReportView
            month={selected}
            toolbarStart={
              <div className="w-[200px] max-w-full shrink-0">
                <MonthSidebar
                  months={months}
                  value={selected}
                  onChange={setSelected}
                />
              </div>
            }
          />
        )
      )}
    </div>
  );
}