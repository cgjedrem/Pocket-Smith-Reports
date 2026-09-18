// ReportView — fetch report, 404→GenerateButton, 409→StaleBadge+Regenerate
// (contract mismatch), stale→StaleBadge+Regenerate, PDF export always
// visible. Poll status during generate (every 2s). Renders all 8 sections
// on 200.

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { exportPdf, generateReport, getReport, getStatus } from "@/api/reports";
import { ErrorAlert } from "@/components/ErrorAlert";
import { GenerateButton } from "@/components/reports/GenerateButton";
import { PdfExportButton } from "@/components/reports/PdfExportButton";
import { StaleBadge } from "@/components/reports/StaleBadge";
import { OverviewSection } from "@/components/reports/OverviewSection";
import { KpiRoleSummary } from "@/components/reports/KpiRoleSummary";
import { DetailedSections } from "@/components/reports/DetailedSections";
import { ReconciliationSection } from "@/components/reports/ReconciliationSection";
import { BillsWarningBanner } from "@/components/bills/BillsWarningBanner";
import type { ReportResponse } from "@/types/report";

// Shared report SCSS — Vite compiles via sass.
import "@/styles/report-shared.scss";

import styles from "./ReportView.module.css";

// Poll interval — 2s per design.
const POLL_MS = 2000;

interface ReportViewProps {
  month: string;
  toolbarStart?: ReactNode;
}

type ViewState =
  | "loading"
  | "not_generated"
  | "ready"
  | "error"
  // BE contract marker missing/!= current → 409. Same UX path as stale:
  // badge + Regenerate affordance.
  | "contract_mismatch";

export function ReportView({ month, toolbarStart }: ReportViewProps) {
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [viewState, setViewState] = useState<ViewState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [contractError, setContractError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string[] | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  // Fetch report JSON — 404 → not_generated, 409 → contract_mismatch,
  // 200 → ready.
  const fetchReport = useCallback(async () => {
    setViewState("loading");
    setError(null);
    setContractError(null);
    try {
      const r = await getReport(month);
      setReport(r);
      setViewState("ready");
    } catch (err) {
      const detail = (err as { detail?: string; status?: number })?.detail;
      const status = (err as { status?: number })?.status;
      if (status === 409) {
        setContractError(
          detail ??
            `Report for ${month} predates the current contract — regenerate.`,
        );
        setViewState("contract_mismatch");
      } else if (status === 404 || (detail && detail.includes("no report"))) {
        setViewState("not_generated");
      } else {
        setError(detail ?? "Cannot reach server");
        setViewState("error");
      }
    }
  }, [month]);

  // Poll status — stop on success/failed.
  const startPoll = useCallback(() => {
    stopPoll();
    pollRef.current = setInterval(async () => {
      try {
        const s = await getStatus(month);
        if (s.status === "success") {
          stopPoll();
          setGenerating(false);
          setGenError(null);
          fetchReport();
        } else if (s.status === "failed") {
          stopPoll();
          setGenerating(false);
          setGenError(s.errors.length ? s.errors : ["Generation failed"]);
        }
        // generating → keep polling.
      } catch {
        // network blip — keep polling.
      }
    }, POLL_MS);
  }, [month, stopPoll, fetchReport]);

  // Mount: fetch report + check status (resume polling if generating).
  useEffect(() => {
    let cancelled = false;
    setReport(null);
    setGenError(null);
    setGenerating(false);

    (async () => {
      // Check status first — resume polling if generating.
      try {
        const s = await getStatus(month);
        if (cancelled) return;
        if (s.status === "generating") {
          setGenerating(true);
          startPoll();
          // Still try fetch — may be stale from previous run.
          try {
            const r = await getReport(month);
            if (!cancelled) {
              setReport(r);
              setViewState("ready");
            }
          } catch {
            if (!cancelled) setViewState("not_generated");
          }
          return;
        }
        if (s.status === "failed") {
          setGenError(s.errors.length ? s.errors : ["Generation failed"]);
        }
      } catch {
        // 404 status — never generated, fall through to fetchReport.
      }
      if (cancelled) return;
      fetchReport();
    })();

    return () => {
      cancelled = true;
      stopPoll();
    };
  }, [month, fetchReport, startPoll, stopPoll]);

  // Generate handler — POST /generate, 202 → poll.
  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    setGenError(null);
    setError(null);
    try {
      await generateReport(month);
      startPoll();
    } catch (err) {
      setGenerating(false);
      const detail = (err as { detail?: string })?.detail;
      setGenError([detail ?? "Cannot reach server"]);
    }
  }, [month, startPoll]);

  // PDF export handler — POST /pdf → download blob.
  const handleExportPdf = useCallback(async () => {
    setExporting(true);
    setExportError(null);
    try {
      const blob = await exportPdf(month);
      // Trigger browser download.
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `monthly_report_${month}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      const detail = (err as { detail?: string })?.detail;
      setExportError(detail ?? "Cannot reach server");
    } finally {
      setExporting(false);
    }
  }, [month]);

  return (
    <div className={styles.reportView}>
      <div className={styles.toolbar} role="toolbar" aria-label="Report controls">
        {toolbarStart}
        <h2>Report — {month}</h2>
        {report?.stale && <StaleBadge />}
        {viewState === "ready" && (
          <div className={styles.toolbarActions}>
            <PdfExportButton onClick={handleExportPdf} disabled={exporting} />
            <GenerateButton
              onClick={handleGenerate}
              disabled={generating}
              label="Regenerate"
              size="default"
            />
          </div>
        )}
      </div>

      {exportError && <ErrorAlert message={exportError} />}
      {error && <ErrorAlert message={error} />}
      {genError && <ErrorAlert errors={genError} />}

      {viewState === "ready" && report && (
        <BillsWarningBanner warnings={report.warnings ?? []} />
      )}

      {viewState === "loading" && (
        <p className="text-sm text-muted-foreground">Loading report...</p>
      )}

      {viewState === "not_generated" && (
        <div className="rounded-md border border-dashed border-border bg-muted/30 p-6 text-center">
          <p className="mb-4 text-muted-foreground">
            No report generated yet for {month}.
          </p>
          <GenerateButton
            onClick={handleGenerate}
            disabled={generating}
            label="Generate report"
          />
        </div>
      )}

      {viewState === "contract_mismatch" && (
        <div className="rounded-md border border-dashed border-border bg-muted/30 p-6 text-center">
          <div className="mb-2 flex items-center justify-center gap-2">
            <StaleBadge />
            <p className="text-muted-foreground">
              {contractError ??
                `Report for ${month} predates the current contract — regenerate.`}
            </p>
          </div>
          <GenerateButton
            onClick={handleGenerate}
            disabled={generating}
            label="Regenerate"
          />
        </div>
      )}

      {generating && viewState !== "ready" && (
        <p className="text-sm text-muted-foreground">Generating report...</p>
      )}

      {viewState === "ready" && report && (
        <>
          <section className={styles.section}>
            <OverviewSection report={report} />
          </section>
          {report.kpis && (
            <section className={styles.section}>
              <KpiRoleSummary report={report} />
            </section>
          )}
          {report.detailed_section_mapping && (
            <section className={styles.section}>
              <DetailedSections report={report} />
            </section>
          )}
          <section className={styles.section}>
            <ReconciliationSection report={report} />
          </section>
        </>
      )}
    </div>
  );
}