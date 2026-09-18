// MegaReportView — fetch mega report, 404→GenerateButton, 409→StaleBadge+Regenerate (contract mismatch), stale→StaleBadge+Regenerate,
// PDF export always visible. Poll status during generate (every 2s).
// Renders all 13 sections on 200. Mirrors ReportView.tsx pattern w/ {start, end}.

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import {
  generateMegaReport,
  getMegaReport,
  getMegaStatus,
} from "@/api/mega_reports";
import { ErrorAlert } from "@/components/ErrorAlert";
import { GenerateButton } from "@/components/reports/GenerateButton";
import { StaleBadge } from "@/components/reports/StaleBadge";
import { BillsWarningBanner } from "@/components/bills/BillsWarningBanner";
import { KpiCoverSection } from "@/components/mega-reports/sections/KpiCoverSection";
import { IncomeSection } from "@/components/mega-reports/sections/IncomeSection";
import { SavingsSection } from "@/components/mega-reports/sections/SavingsSection";
import { HomeSection } from "@/components/mega-reports/sections/HomeSection";
import { CommonSection } from "@/components/mega-reports/sections/CommonSection";
import { PersonalSection } from "@/components/mega-reports/sections/PersonalSection";
import { TripsSection } from "@/components/mega-reports/sections/TripsSection";
import { RecommendationsSection } from "@/components/mega-reports/sections/RecommendationsSection";
import { MonthliesSection } from "@/components/mega-reports/sections/MonthliesSection";
import { CcPaydownsSection } from "@/components/mega-reports/sections/CcPaydownsSection";
import { ExcludedSection } from "@/components/mega-reports/sections/ExcludedSection";
import { AppendicesSection } from "@/components/mega-reports/sections/AppendicesSection";
import { MegaReportNav } from "@/components/mega-reports/MegaReportNav";
import { MegaReportExportDialog } from "@/components/mega-reports/MegaReportExportDialog";
import type { MegaReportResponse } from "@/types/mega_report";

import styles from "./MegaReportView.module.css";

// Poll interval — 2s per design.
const POLL_MS = 2000;

interface MegaReportViewProps {
  start: string;
  end: string;
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

export function MegaReportView({ start, end, toolbarStart }: MegaReportViewProps) {
  const [report, setReport] = useState<MegaReportResponse | null>(null);
  const [viewState, setViewState] = useState<ViewState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [contractError, setContractError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string[] | null>(null);
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
      const r = await getMegaReport(start, end);
      setReport(r);
      setViewState("ready");
    } catch (err) {
      const detail = (err as { detail?: string; status?: number })?.detail;
      const status = (err as { status?: number })?.status;
      if (status === 409) {
        setContractError(
          detail ??
            `Report for ${start} → ${end} predates the current contract — regenerate.`,
        );
        setViewState("contract_mismatch");
      } else if (status === 404 || (detail && detail.includes("no report"))) {
        setViewState("not_generated");
      } else {
        setError(detail ?? "Cannot reach server");
        setViewState("error");
      }
    }
  }, [start, end]);

  // Poll status — stop on success/failed.
  const startPoll = useCallback(() => {
    stopPoll();
    pollRef.current = setInterval(async () => {
      try {
        const s = await getMegaStatus(start, end);
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
  }, [start, end, stopPoll, fetchReport]);

  // Mount: fetch report + check status (resume polling if generating).
  useEffect(() => {
    let cancelled = false;
    setReport(null);
    setGenError(null);
    setGenerating(false);

    (async () => {
      // Check status first — resume polling if generating.
      try {
        const s = await getMegaStatus(start, end);
        if (cancelled) return;
        if (s.status === "generating") {
          setGenerating(true);
          startPoll();
          // Still try fetch — may be stale from previous run.
          try {
            const r = await getMegaReport(start, end);
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
  }, [start, end, fetchReport, startPoll, stopPoll]);

  // Generate handler — POST /generate, 202 → poll.
  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    setGenError(null);
    setError(null);
    try {
      await generateMegaReport(start, end);
      startPoll();
    } catch (err) {
      setGenerating(false);
      const detail = (err as { detail?: string })?.detail;
      setGenError([detail ?? "Cannot reach server"]);
    }
  }, [start, end, startPoll]);

  return (
    <div className={styles.megaReportView}>
      <div className={styles.toolbar} role="toolbar" aria-label="Mega report controls">
        <div className={styles.toolbarRange}>{toolbarStart}</div>
        <div className={styles.toolbarRight}>
          {report?.stale && <StaleBadge />}
          {viewState === "ready" && (
            <div className={styles.toolbarActions}>
              <MegaReportExportDialog
                start={start}
                end={end}
                onError={(msg) => setExportError(msg)}
                onSuccess={() => setExportError(null)}
              />
              <GenerateButton
                onClick={handleGenerate}
                disabled={generating}
                label="Regenerate"
                size="default"
              />
            </div>
          )}
        </div>
      </div>

      {exportError && <ErrorAlert message={exportError} />}
      {error && <ErrorAlert message={error} />}
      {genError && <ErrorAlert errors={genError} />}

      {viewState === "ready" && report && (
        <BillsWarningBanner warnings={report.warnings ?? []} />
      )}

      {viewState === "loading" && (
        <p className="text-sm text-muted-foreground">Loading mega report...</p>
      )}

      {viewState === "not_generated" && (
        <div className="rounded-md border border-dashed border-border bg-muted/30 p-6 text-center">
          <p className="mb-4 text-muted-foreground">
            No mega report generated yet for {start} → {end}.
          </p>
          <GenerateButton
            onClick={handleGenerate}
            disabled={generating}
            label="Generate mega report"
          />
        </div>
      )}

      {viewState === "contract_mismatch" && (
        <div className="rounded-md border border-dashed border-border bg-muted/30 p-6 text-center">
          <div className="mb-2 flex items-center justify-center gap-2">
            <StaleBadge />
            <p className="text-muted-foreground">
              {contractError ??
                `Report for ${start} → ${end} predates the current contract — regenerate.`}
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
        <p className="text-sm text-muted-foreground">Generating mega report...</p>
      )}

      {viewState === "ready" && report && !report.detail_agg && (
        <ErrorAlert message="Report data is incomplete (missing detail_agg). Re-generate the mega report." />
      )}

      {viewState === "ready" && report && report.detail_agg && (
        <>
          <div className={styles.layout}>
            <div className={styles.content}>
              <section id="kpi" data-section-id="kpi" className={styles.section}>
                <KpiCoverSection report={report} />
              </section>
              <section id="income" data-section-id="income" className={styles.section}>
                <IncomeSection report={report} />
              </section>
              <section id="savings" data-section-id="savings" className={styles.section}>
                <SavingsSection report={report} />
              </section>
              <section id="home" data-section-id="home" className={styles.section}>
                <HomeSection report={report} />
              </section>
              <section id="common" data-section-id="common" className={styles.section}>
                <CommonSection report={report} />
              </section>
              <section id="personal-partner-a" data-section-id="personal-partner-a" className={styles.section}>
                <PersonalSection report={report} partner="partner_a" />
              </section>
              <section id="personal-partner-b" data-section-id="personal-partner-b" className={styles.section}>
                <PersonalSection report={report} partner="partner_b" />
              </section>
              <section id="trips" data-section-id="trips" className={styles.section}>
                <TripsSection report={report} />
              </section>
              <section id="recommendations" data-section-id="recommendations" className={styles.section}>
                <RecommendationsSection report={report} />
              </section>
              <section id="monthlies" data-section-id="monthlies" className={styles.section}>
                <MonthliesSection report={report} />
              </section>
              <section id="cc-paydowns" data-section-id="cc-paydowns" className={styles.section}>
                <CcPaydownsSection report={report} />
              </section>
              <section id="excluded" data-section-id="excluded" className={styles.section}>
                <ExcludedSection report={report} />
              </section>
              <section id="appendices" data-section-id="appendices" className={styles.section}>
                <AppendicesSection report={report} />
              </section>
            </div>
          </div>
        </>
      )}
      {report && report.detail_agg && <MegaReportNav report={report} />}
    </div>
  );
}