import { useId } from "react";
import { Link } from "react-router-dom";
import { ErrorAlert } from "@/components/ErrorAlert";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RunwaySettings } from "@/components/bills/RunwaySettings";
import { useRunway } from "@/hooks/useRunway";
import { useAmountsHidden } from "@/lib/privacy-store";
import { runwayAttributionText, runwayDate, runwayIssueText, runwayMoney, runwayMonth, runwayOwnerAttributionText } from "@/lib/runway";
import type { RunwayIssue, RunwayMeasures, RunwayOwner, RunwayResponse } from "@/types/runway";

interface IssuesProps {
  issues: RunwayIssue[];
  data: RunwayResponse;
}

function Issues({ issues, data }: IssuesProps) {
  // Source provenance belongs on Data coverage; keep result blockers and actionable qualifications here.
  const messages = [...new Set(issues
    .filter((issue) => !["coverage_unverified", "source_date_unknown", "source_times_differ", "classification_unverified"].includes(issue.code))
    .map((issue) =>
    runwayIssueText(issue, data.owners.map((entry) => entry.owner), data.selected_accounts),
  ))];
  if (!messages.length) return null;
  return <ul className="mt-2 list-inside list-disc space-y-1 text-xs text-muted-foreground">{messages.map((text) => <li key={text}>{text}</li>)}</ul>;
}

interface MeasuresProps {
  label: string;
  measures: RunwayMeasures;
  data: RunwayResponse;
  // Owner card only; household has no attribution line.
  owner?: RunwayOwner;
}

function Measures({ label, measures, data, owner }: MeasuresProps) {
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
        <div><dt>Average monthly spending (net)</dt><dd className="font-medium tabular-nums">{runwayMoney(measures.average_monthly_spending, measures.spending_currency_code)}</dd></div>
      </dl>
      {owner && <p className="mt-2 text-xs text-muted-foreground">{runwayOwnerAttributionText(data, owner)}</p>}
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
      <p className="mt-2 text-sm">Average monthly spending (net, as in Reports). Selected liquid reserves divided by past household net spending: the same total as the Reports page (home, common, personal and trips). Refunds and reimbursements reduce spending; income is not subtracted.</p>
      <p className="mt-2 text-sm text-muted-foreground">Household compares only selected reserves with the household’s net spending, not all household assets.</p>
      <div className="mt-4 space-y-4">
        {loading && <p role="status">{data ? "Refreshing runway… Previous result shown below." : "Loading runway…"}</p>}
        {error && <ErrorAlert message={error} />}
        {data && (
          <>
            <p className="text-xs text-muted-foreground">Results use the last loaded saved selection, not unsaved choices.{error ? " Refresh failed; previous result retained." : ""}</p>
            {(data.selection_status === "empty" || data.selection_status === "unconfigured") && <p className="font-medium">Select liquid accounts</p>}
            <p className="text-sm">{runwayAttributionText(data)}</p>
            <p className="text-sm">Based on recorded PocketSmith transactions for the last three completed months.</p>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {data.owners.map((entry) => <Measures key={entry.owner.partner_id} label={entry.owner.label} measures={entry} data={data} owner={entry.owner} />)}
              <Measures label="Household" measures={data.household} data={data} />
            </div>
            {data.owners.length === 0 && <p>No configured account owners available. See source limitations.</p>}
            <Issues issues={data.issues} data={data} />
            <Issues issues={data.observations.flatMap((row) => row.issues)} data={data} />
            <div className="text-sm">
              <p>As of {runwayMonth(data.as_of_month)} · {data.included_month_count} of 3 completed months included.</p>
              <p>Included months: {data.included_months.length ? data.included_months.map(runwayMonth).join(", ") : "None"}. At least two required; no older backfill.</p>
              <p className="mt-1 text-xs text-muted-foreground">Independent of the Bills display window. Month-by-month source coverage and provenance dates are on <Link className="underline" to="/data-coverage">Data coverage</Link>.</p>
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
        <p className="text-xs text-muted-foreground">Descriptive observations, not a forecast, financial advice, or a recommendation. Ignores future income and spending changes; no safe spending level or guaranteed duration. Recorded classification may miss unmarked transfers. Transfers, card repayments, savings, and excluded categories are excluded from net spending as in Reports; see Data coverage for source limitations.</p>
      </div>
    </section>
  );
}
