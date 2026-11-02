import { useId } from "react";

import { ErrorAlert } from "@/components/ErrorAlert";
import { Button } from "@/components/ui/button";
import { useRunway } from "@/hooks/useRunway";
import { runwayDate, runwayIssueText, runwayMonth } from "@/lib/runway";
import type { RunwayIssue } from "@/types/runway";

interface CoverageIssuesProps {
  issues: RunwayIssue[];
  data: NonNullable<ReturnType<typeof useRunway>["data"]>;
}

function CoverageIssues({ issues, data }: CoverageIssuesProps) {
  const messages = [...new Set(issues.map((entry) =>
    runwayIssueText(entry, data.owners.map((owner) => owner.owner), data.selected_accounts),
  ))];
  if (!messages.length) return null;
  return (
    <ul className="mt-2 list-inside list-disc space-y-1 text-xs text-muted-foreground">
      {messages.map((message) => <li key={message}>{message}</li>)}
    </ul>
  );
}

export function DataCoveragePage() {
  const state = useRunway();
  const headingId = useId();
  const { data, loading, error } = state;

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 id={headingId} className="text-2xl font-semibold">Data coverage</h1>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
            Month-by-month coverage and source provenance for the Runway figures. These diagnostics describe recorded local data; refreshing recalculates but does not collect new transactions.
          </p>
        </div>
        <Button type="button" size="sm" variant="outline" disabled={loading} onClick={() => void state.refresh()}>
          {error ? "Retry data coverage" : "Refresh coverage"}
        </Button>
      </header>

      {loading && <p role="status">{data ? "Refreshing data coverage… Previous result shown below." : "Loading data coverage…"}</p>}
      {error && <ErrorAlert message={error} />}

      {data && (
        <div className="flex flex-col gap-4">
          <section aria-label="Runway source window" className="rounded-lg border bg-card p-4 text-sm">
            <h2 className="font-semibold">Runway source window</h2>
            <p className="mt-2">As of {runwayMonth(data.as_of_month)} · {data.included_month_count} of 3 completed months included.</p>
            <p>Candidate months: {data.candidate_months.map(runwayMonth).join(", ")}.</p>
            <p>Included months: {data.included_months.length ? data.included_months.map(runwayMonth).join(", ") : "None"}. At least two required; no older backfill.</p>
            <p className="mt-2 text-xs text-muted-foreground">Runway calculated: {runwayDate(data.calculated_at)}. Catalog collected: {runwayDate(data.catalog_collected_at)} · {data.catalog_freshness}. Calculation and catalog dates do not certify transaction collection dates.</p>
            <CoverageIssues issues={data.issues} data={data} />
          </section>

          <section aria-labelledby={`${headingId}-months`}>
            <h2 id={`${headingId}-months`} className="mb-2 text-lg font-semibold">Monthly source coverage</h2>
            {!data.observations.length ? (
              <p className="rounded-lg border p-4 text-sm text-muted-foreground">No monthly coverage observations available.</p>
            ) : (
              <div className="grid gap-3 lg:grid-cols-3">
                {data.observations.map((row) => (
                  <section key={row.month} aria-label={`${runwayMonth(row.month)} coverage`} className="min-w-0 rounded-lg border p-4 text-sm">
                    <h3 className="font-semibold">{runwayMonth(row.month)}</h3>
                    <p className="mt-2">{row.status === "included" ? "Included" : "Excluded"} · Coverage: {row.coverage}</p>
                    <p className="mt-2 text-xs text-muted-foreground">Source collected: {runwayDate(row.collected_at)} · {row.freshness}</p>
                    <p className="text-xs text-muted-foreground">Coverage dates: {runwayDate(row.coverage_start)} – {runwayDate(row.coverage_end)}</p>
                    <CoverageIssues issues={row.issues} data={data} />
                  </section>
                ))}
              </div>
            )}
          </section>
        </div>
      )}

      {!data && !loading && !error && <p className="text-sm text-muted-foreground">Coverage result not loaded. Refresh to read local sources.</p>}
    </section>
  );
}
