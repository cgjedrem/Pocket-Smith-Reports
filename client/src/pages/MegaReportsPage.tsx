// MegaReportsPage — year picker + range picker + generated reports list + report view.
// Fetches getMegaReports() + getMonths() on mount. Manages selected range state.

import { useCallback, useEffect, useState } from "react";

import { getMegaReports } from "@/api/mega_reports";
import { getMonths } from "@/api/reports";
import { ErrorAlert } from "@/components/ErrorAlert";
import { GeneratedReportsList } from "@/components/mega-reports/GeneratedReportsList";
import { MegaReportView } from "@/components/mega-reports/MegaReportView";
import { RangePicker } from "@/components/mega-reports/RangePicker";
import type { MegaReportRange } from "@/types/mega_report";

import styles from "./MegaReportsPage.module.css";

export function MegaReportsPage() {
  const [reports, setReports] = useState<MegaReportRange[]>([]);
  const [months, setMonths] = useState<string[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [start, setStart] = useState<string>("2026-01");
  const [end, setEnd] = useState<string>("2026-12");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  // Auto-pick initial range from synced months (no year filter — month pickers cover it).
  const refresh = useCallback(async () => {
    setLoadError(null);
    try {
      const [megaList, monthList] = await Promise.all([
        getMegaReports(),
        getMonths(),
      ]);
      setReports(megaList.reports);
      setMonths(monthList.months);
      // Auto-select newest generated report if any.
      if (megaList.reports.length > 0) {
        const newest = megaList.reports[0];
        setStart(newest.start);
        setEnd(newest.end);
        setSelectedKey(`${newest.start}_${newest.end}`);
      } else if (monthList.months.length > 0) {
        // Default to the newest synced YEAR's Jan–Dec. Picking a range
        // that straddles future/unsynced months would trigger the
        // missing-months warning for no reason.
        const newestMonth = monthList.months[0];
        const [y] = newestMonth.split("-").map(Number);
        setStart(`${y}-01`);
        setEnd(`${y}-12`);
        setSelectedKey(null);
      }
    } catch (err) {
      setLoadError((err as { detail?: string })?.detail ?? "Cannot reach server");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleRangeChange = useCallback((newStart: string, newEnd: string) => {
    setStart(newStart);
    setEnd(newEnd);
    setSelectedKey(null);
  }, []);

  const handleSelectReport = useCallback((s: string, e: string) => {
    setStart(s);
    setEnd(e);
    setSelectedKey(`${s}_${e}`);
  }, []);

  return (
    <div className="mx-auto max-w-6xl rounded-lg border border-border bg-card p-6">
      <header className="mb-6 flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Mega Reports</h1>
        {reports.length > 0 && (
          <span className="text-xs text-muted-foreground">
            {reports.length} generated
          </span>
        )}
      </header>

      {loadError && <ErrorAlert message={loadError} />}

      <div className={styles.page}>
        {reports.length > 0 && (
          <section
            aria-label="Generated mega reports"
            className={styles.reportsSection}
          >
            <div className={styles.reportsHeader}>
              <h3 className="text-sm font-medium text-muted-foreground">
                Generated reports
              </h3>
            </div>
            <GeneratedReportsList
              reports={reports}
              value={selectedKey}
              onChange={handleSelectReport}
            />
          </section>
        )}

        <MegaReportView
          start={start}
          end={end}
          toolbarStart={
            <RangePicker
              start={start}
              end={end}
              onChange={handleRangeChange}
              availableMonths={months}
            />
          }
        />
      </div>
    </div>
  );
}