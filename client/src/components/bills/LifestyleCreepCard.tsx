import { useId, useState } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { lifestyleEvidenceMonths } from "@/lib/lifestyle-creep";
import { useAmountsHidden } from "@/lib/privacy-store";
import type { ApiError } from "@/types/api";
import type { HistoryIssue, HistoryReason, ReportLifestyleCreepResponse } from "@/types/lifestyle-creep";
import { LifestyleGroupDetails } from "./LifestyleCreepDetails";
import { LifestyleCreepControls, type LifestyleCreepControlsProps } from "./LifestyleCreepControls";

const issueMessages: Record<HistoryIssue["code"], string> = {
  missing_snapshot: "Saved month is missing",
  legacy_history: "Legacy history lacks report-group evidence; explicitly re-sync the selected months",
  partial_month: "Month is open or stored history is partial",
  missing_partner_identity: "Partner identity is missing",
  missing_partner: "Partner is missing from this month",
  unavailable_history: "History is unavailable",
  scope_changed: "Spending scope changed; re-sync in one run under a consistent configuration",
  no_stable_partners: "No stable partners could be established",
};
const reasonMessages: Record<NonNullable<HistoryReason>, string> = {
  open_month: "Month is still open or history was acquired while open; wait until it closes, then re-sync if needed",
  future_month: "Source month was in the future",
  no_cc_accounts: "No eligible credit-card accounts",
  missing_source_context: "Report classification or source completion context is missing",
  invalid_source: "Source or report classification input could not be validated",
};

export interface LifestyleCreepCardProps extends LifestyleCreepControlsProps {
  data: ReportLifestyleCreepResponse | null;
  loading: boolean;
  error: ApiError | null;
  onRetry: () => void;
}

export function LifestyleCreepCard({ data, ...props }: LifestyleCreepCardProps) {
  useAmountsHidden();
  const [hiddenCategories, setHiddenCategories] = useState<Map<string, Set<string>>>(() => new Map());
  const [showHiddenGroups, setShowHiddenGroups] = useState<Set<string>>(() => new Set());
  const titleId = useId();
  function setCategoryHidden(groupId: string, categoryId: string, hidden: boolean) {
    setHiddenCategories((previous) => {
      const next = new Map(previous);
      const categories = new Set(previous.get(groupId));
      if (hidden) categories.add(categoryId);
      else categories.delete(categoryId);
      next.set(groupId, categories);
      return next;
    });
  }
  const result = !props.loading && !props.error ? data : null;
  const referenceLabel = `${props.referenceStart} through ${props.referenceEnd}`;
  const targetLabel = props.targetMonth;
  const requiredEvidenceCount = lifestyleEvidenceMonths(
    props.referenceStart, props.referenceEnd, props.targetMonth,
  ).length;
  return (
    <section aria-labelledby={titleId} aria-busy={props.loading} className="min-w-0">
      <Card className="min-w-0 break-words">
        <CardHeader>
          <h2 id={titleId} className="text-xl font-semibold">Lifestyle creep detector</h2>
          <p className="text-sm text-muted-foreground">
            Report-grouped spending across included checking and card accounts, paid minus received.
            Shared economy includes Home + Common only. Personal categories follow the report sections, not the payer.
            Trips, savings, income, excluded and credit-card payment sections are omitted. Not financial advice.
          </p>
          <LifestyleCreepControls {...props} />
          <p className="text-sm">Selected target month: {targetLabel}</p>
          <p className="text-sm">Selected reference period: {referenceLabel} (inclusive).</p>
          <p className="text-sm">Applied threshold: {props.appliedThreshold}%</p>
          <p className="text-sm text-muted-foreground">
            Required evidence: reference months {referenceLabel}, plus target {targetLabel} ({requiredEvidenceCount} months).
            {" "}Months between the reference period and target are not required.
          </p>
          <p className="text-sm text-muted-foreground">
            A category is above threshold only when the server finds sufficient positive reference history and target growth strictly above the applied threshold.
            A zero or negative reference baseline, or fewer than two reference months with positive spending, suppresses the outcome.
            Refunds can make net spending negative.
          </p>
        </CardHeader>
        <CardContent className="min-w-0 space-y-5">
          {props.loading && (
            <p role="status">Loading target {targetLabel} against reference months {referenceLabel} at {props.appliedThreshold}%…</p>
          )}
          {!props.loading && props.error && (
            <p role="alert" className="rounded-md border border-destructive/50 p-3 text-sm">
              {props.error.status === 400
                ? "Selection was rejected. Check the target month, reference period, and threshold, then retry."
                : "Could not load lifestyle history. No conclusion is available. Retry to read the saved history again."}
            </p>
          )}
          {!props.loading && !props.error && !result && <p role="status">No history result loaded.</p>}
          {result && (
            <>
              <p className="text-sm">
                Required evidence months: {result.window_months.join(", ")}.
                {" "}Selected target: {result.evaluation_months[0]}.
              </p>
              <p role="status" className={result.status === "ready" ? "font-medium" : "rounded-md border border-amber-500/50 bg-amber-500/10 p-3 font-medium"}>
                {result.status === "insufficient_history" ? "Insufficient history — no reliable conclusion."
                    : `Ready — ${result.window_months.length} required evidence months are comparable.`}
              </p>
              {result.status !== "ready" && (
                <div className="space-y-2 text-sm">
                  <ul className="list-disc space-y-1 pl-5">
                    {result.issues.map((issue) => {
                      const label = issue.group_id
                        ? result.groups.find((group) => group.group_id === issue.group_id)?.label || issue.group_id
                        : "All report groups";
                      return (
                        <li key={`${issue.month}:${issue.group_id}:${issue.partner_id}:${issue.code}:${issue.reason}`}>
                          {issue.month} · {label}: {issueMessages[issue.code]}
                          {issue.reason ? ` — ${reasonMessages[issue.reason]}` : ""}.
                        </li>
                      );
                    })}
                  </ul>
                  <p>{result.history_guidance || "Check report mappings, then explicitly re-sync every selected completed reference and target month with one consistent configuration. Retry only reads saved history."}</p>
                  <Link className="font-medium underline underline-offset-4" to="/sync">Open sync to repair history</Link>
                </div>
              )}
              {result.status === "ready"
                && !result.groups.some((group) => group.categories.some((category) => category.is_above_threshold))
                && <p>No category was flagged above threshold in the covered report-grouped spending.</p>}
              {result.groups.map((group) => (
                <LifestyleGroupDetails
                  key={group.group_id}
                  group={group}
                  hiddenCategoryIds={hiddenCategories.get(group.group_id) ?? new Set()}
                  showHidden={showHiddenGroups.has(group.group_id)}
                  onHide={(categoryId) => setCategoryHidden(group.group_id, categoryId, true)}
                  onRestore={(categoryId) => setCategoryHidden(group.group_id, categoryId, false)}
                  onRestoreAll={() => setHiddenCategories((previous) => {
                    const next = new Map(previous);
                    next.delete(group.group_id);
                    return next;
                  })}
                  onToggleShowHidden={() => setShowHiddenGroups((previous) => {
                    const next = new Set(previous);
                    if (next.has(group.group_id)) next.delete(group.group_id);
                    else next.add(group.group_id);
                    return next;
                  })}
                />
              ))}
            </>
          )}
          {!props.loading && (
            <div className="flex flex-wrap items-center gap-3">
              <Button type="button" variant="outline" onClick={props.onRetry}>Retry history</Button>
              <span className="text-xs text-muted-foreground">Read saved history only; Retry never starts sync.</span>
            </div>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
