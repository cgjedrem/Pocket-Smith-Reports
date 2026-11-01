import { useId } from "react";
import { ErrorAlert } from "@/components/ErrorAlert";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RunwaySettings } from "@/components/bills/RunwaySettings";
import { useRunway } from "@/hooks/useRunway";
import { useAmountsHidden } from "@/lib/privacy-store";
import { runwayDate, runwayIssueText, runwayMoney, runwayMonth } from "@/lib/runway";
import type { RunwayIssue, RunwayMeasures, RunwayResponse } from "@/types/runway";

interface IssuesProps {
  issues: RunwayIssue[];
  data: RunwayResponse;
}

function Issues({ issues, data }: IssuesProps) {
  const messages = [...new Set(issues.map((issue) =>
    runwayIssueText(issue, data.owners.map((entry) => entry.owner), data.selected_accounts),
  ))];
  if (!messages.length) return null;
  return <ul className="mt-2 list-inside list-disc space-y-1 text-xs text-muted-foreground">{messages.map((text) => <li key={text}>{text}</li>)}</ul>;
}

interface MeasuresProps {
  label: string;
  measures: RunwayMeasures;
  data: RunwayResponse;
}

function Measures({ label, measures, data }: MeasuresProps) {
  const id = useId();
  return (
    <section aria-label={`${label} runway`} className="min-w-0 rounded-lg border bg-background p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id={id} className="font-semibold">{label}</h3>
        <Badge variant="outline">{measures.status === "available" ? "Available" : measures.status === "qualified" ? "Qualified" : "Unavailable"}</Badge>
      </div>
      <p className="my-3 text-2xl font-semibold tabular-nums">
        {measures.runway_display === null ? "Unavailable" : `${measures.runway_display} months`}
      </p>
      <dl className="space-y-2 text-sm">
        <div><dt>Selected liquid reserves</dt><dd className="font-medium tabular-nums">{runwayMoney(measures.reserves, measures.reserves_currency_code)}</dd></div>
        <div><dt>Average monthly recorded spending</dt><dd className="font-medium tabular-nums">{runwayMoney(measures.average_monthly_spending, measures.spending_currency_code)}</dd></div>
      </dl>
      <p className="mt-2 text-xs text-muted-foreground">{measures.selected_account_ids.length} selected accounts · Currency: {measures.currency_code ?? "Unverified (household display unit)"} · {measures.currency_status}</p>
      <Issues issues={measures.issues} data={data} />
    </section>
  );
}

export function RunwayPanel() {
  useAmountsHidden();
  const state = useRunway();
  const id = useId();
  const { data, loading, error } = state;
  const ownerLabel = (partnerId: string | null) =>
    data?.owners.find((entry) => entry.owner.partner_id === partnerId)?.owner.label ?? partnerId ?? "Owner unknown";

  return (
    <section aria-labelledby={id} className="min-w-0 rounded-xl border bg-card p-4 text-card-foreground shadow-sm sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id={id} className="text-xl font-semibold">Runway &amp; Burn Rate</h2>
        <Button type="button" size="sm" variant="outline" disabled={loading || state.saving} onClick={() => void state.refresh()}>
          {error ? "Retry runway" : "Refresh runway"}
        </Button>
      </div>
      <p className="mt-2 text-sm">Average monthly recorded spending (gross burn). Selected liquid reserves divided by past recorded spending; income and positive refunds are not subtracted.</p>
      <p className="mt-2 text-sm text-muted-foreground">Account-owner-based, not a fair-share allocation. Household compares only selected reserves with all configured owners’ spending, not all household assets.</p>
      <div className="mt-4 space-y-4">
        {loading && <p role="status">{data ? "Refreshing runway… Previous result shown below." : "Loading runway…"}</p>}
        {error && <ErrorAlert message={error} />}
        {data && (
          <>
            <p className="text-xs text-muted-foreground">Results use the last loaded saved selection, not unsaved choices.{error ? " Refresh failed; previous result retained." : ""}</p>
            {(data.selection_status === "empty" || data.selection_status === "unconfigured") && <p className="font-medium">Select liquid accounts</p>}
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {data.owners.map((entry) => <Measures key={entry.owner.partner_id} label={entry.owner.label} measures={entry} data={data} />)}
              <Measures label="Household" measures={data.household} data={data} />
            </div>
            {data.owners.length === 0 && <p>No configured account owners available. See source limitations.</p>}
            <Issues issues={data.issues} data={data} />
            <div className="text-sm">
              <p>As of {runwayMonth(data.as_of_month)} · {data.included_month_count} of 3 completed months included.</p>
              <p>Candidate months: {data.candidate_months.map(runwayMonth).join(", ")}.</p>
              <p>Included months: {data.included_months.length ? data.included_months.map(runwayMonth).join(", ") : "None"}. At least two required; no older backfill.</p>
              <p className="mt-1 text-xs text-muted-foreground">Independent of the Bills display window. Calculated: {runwayDate(data.calculated_at)}. This is not a source collection date.</p>
              <p className="text-xs text-muted-foreground">Catalog collected: {runwayDate(data.catalog_collected_at)} · {data.catalog_freshness}. Recalculation does not refresh underlying data.</p>
            </div>
            <div>
              <h3 className="mb-2 font-semibold">Monthly recorded spending</h3>
              <div className="grid gap-3 lg:grid-cols-3">
                {data.observations.map((row) => (
                  <section key={row.month} aria-label={`${runwayMonth(row.month)} observation`} className="min-w-0 rounded-lg border p-3 text-sm">
                    <h4 className="font-medium">{runwayMonth(row.month)}</h4>
                    <p>{row.status === "included" ? "Included" : "Excluded"} · Coverage: {row.coverage}</p>
                    <dl className="mt-2 space-y-1">
                      {row.owners.map((entry) => <div key={entry.partner_id} className="flex flex-wrap justify-between gap-2"><dt>{ownerLabel(entry.partner_id)}</dt><dd className="tabular-nums">{runwayMoney(entry.spending, entry.currency_code)}</dd></div>)}
                      <div className="flex flex-wrap justify-between gap-2 font-medium"><dt>Household</dt><dd className="tabular-nums">{runwayMoney(row.household_spending, row.household_currency_code)}</dd></div>
                    </dl>
                    <p className="mt-2 text-xs text-muted-foreground">Collected: {runwayDate(row.collected_at)} · {row.freshness}</p>
                    <p className="text-xs text-muted-foreground">Coverage dates: {runwayDate(row.coverage_start)} – {runwayDate(row.coverage_end)}</p>
                    <Issues issues={row.issues} data={data} />
                  </section>
                ))}
              </div>
            </div>
            <div>
              <h3 className="mb-2 font-semibold">Selected reserve accounts</h3>
              <p className="text-xs text-muted-foreground">Current recorded signed balances only — not historical runway or projected savings.</p>
              {data.selected_accounts.length === 0 && <p className="mt-2 text-sm">{data.selected_account_ids === null ? "Saved selection unavailable." : "No selected reserve accounts."}</p>}
              <ul className="mt-2 grid gap-3 md:grid-cols-2">
                {data.selected_accounts.map((account) => (
                  <li key={account.id} className="min-w-0 rounded-lg border p-3 text-sm">
                    <p className="break-words font-medium">{account.name} · {ownerLabel(account.partner_id)}</p>
                    <p>Account {account.id} · {account.type ?? "Unknown type"} · {account.eligible ? "Eligible" : "Invalid selection"}</p>
                    <p className="my-1 font-medium tabular-nums">{runwayMoney(account.balance, account.currency_code)}</p>
                    <p className="text-xs text-muted-foreground">Currency: {account.currency_code ?? "Unknown"} · {account.currency_status}</p>
                    <p className="text-xs text-muted-foreground">Balance date: {runwayDate(account.balance_date)}{account.balance_date_precision === "date" ? " (date only)" : ""} · {account.balance_freshness}</p>
                    <Issues issues={account.issues} data={data} />
                  </li>
                ))}
              </ul>
            </div>
          </>
        )}
        {!data && !loading && !error && <p>Result not loaded. Refresh runway to read the saved selection.</p>}
        <RunwaySettings state={state} />
        <p className="text-xs text-muted-foreground">Descriptive observations, not a forecast, financial advice, or a recommendation. Ignores future income and spending changes; no safe spending level or guaranteed duration. Recorded classification may miss unmarked transfers. Transfers, savings, investments, and identified card repayments are excluded from gross burn; source limitations remain visible above.</p>
      </div>
    </section>
  );
}
