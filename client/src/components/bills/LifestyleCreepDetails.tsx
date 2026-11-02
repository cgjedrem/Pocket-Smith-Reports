import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatLifestyleMoney as money, formatLifestylePercent as percent, lifestyleOutcome } from "@/lib/lifestyle-creep";
import type { ReportLifestyleCategory, ReportLifestyleGroup, MonthlyAmount } from "@/types/lifestyle-creep";
import { LifestyleTrendChart } from "./LifestyleTrendChart";

interface SamplesProps {
  samples: MonthlyAmount[];
}

function Samples({ samples }: SamplesProps) {
  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      {samples.map((sample) => (
        <div key={sample.month} className="min-w-0">
          <dt className="text-muted-foreground">{sample.month}</dt>
          <dd className="break-words tabular-nums">{money(sample.amount)}</dd>
        </div>
      ))}
    </dl>
  );
}

interface CategoryDetailsProps {
  category: ReportLifestyleCategory;
}

export function LifestyleCreepDetails({ category }: CategoryDetailsProps) {
  const comparison = category.comparison;
  const outcome = lifestyleOutcome(category);
  const categoryLabel = `${category.category_title || category.category_id} (ID ${category.category_id})`;
  // Lazy: the graph mounts only while this disclosure is open.
  const [open, setOpen] = useState(false);
  return (
    <details className="min-w-0 rounded-md border p-3 text-sm" onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary className="cursor-pointer rounded-sm font-medium focus-visible:outline-2 focus-visible:outline-ring">
        Target comparison: {categoryLabel}
      </summary>
      <div className="mt-4 space-y-4">
        <p>{outcome}</p>
        <Samples samples={category.samples} />
        {open && <LifestyleTrendChart samples={category.samples} comparison={comparison} categoryLabel={categoryLabel} />}
        <section className="min-w-0 rounded-md bg-muted/40 p-3">
          <h4 className="font-semibold">{comparison.month} target versus reference-period average</h4>
          <dl className="mt-2 space-y-2">
            <div><dt>Reference months</dt><dd>{comparison.baseline_months.join(", ")}</dd></div>
            <div><dt>Reference-period average</dt><dd className="break-words">{money(comparison.baseline_amount)}</dd></div>
            <div><dt>Target-month spending</dt><dd className="break-words">{money(comparison.spending_amount)}</dd></div>
            <div><dt>Change from reference average</dt><dd className="break-words">{money(comparison.change_amount, true)}</dd></div>
            <div><dt>Growth versus reference average</dt><dd>{percent(comparison.growth_percent, "nonpositive reference baseline")}</dd></div>
          </dl>
        </section>
        {category.latest_month_over_month_percent !== null && category.samples.length > 1 && (
          <p>
            Actual month-over-month ({comparison.month} vs {category.samples.at(-2)!.month}):{" "}
            {percent(category.latest_month_over_month_percent, "previous month is zero")}.
            {" "}This compares adjacent months, not the reference-period average.
          </p>
        )}
      </div>
    </details>
  );
}

interface GroupDetailsProps {
  group: ReportLifestyleGroup;
  hiddenCategoryIds: ReadonlySet<string>;
  showHidden: boolean;
  onHide: (categoryId: string) => void;
  onRestore: (categoryId: string) => void;
  onRestoreAll: () => void;
  onToggleShowHidden: () => void;
}

export function LifestyleGroupDetails({
  group, hiddenCategoryIds, showHidden, onHide, onRestore, onRestoreAll, onToggleShowHidden,
}: GroupDetailsProps) {
  const label = group.label || group.group_id;
  const hiddenCount = group.categories.filter((category) => hiddenCategoryIds.has(category.category_id)).length;
  const visibleCategories = group.categories.filter((category) => showHidden || !hiddenCategoryIds.has(category.category_id));
  return (
    <section aria-label={`${label} category comparisons`} data-group-id={group.group_id} className="min-w-0 space-y-3">
      <h3 className="flex flex-wrap items-center gap-2 font-semibold">
        {label} <Badge variant="secondary">{group.status === "ready" ? "Ready" : "Insufficient history"}</Badge>
      </h3>
      {group.status === "insufficient_history" ? (
        <p className="text-sm text-muted-foreground">No category verdicts — complete, comparable report history is required for this group. Check mappings and explicitly re-sync the selected completed months; missing evidence is not zero spending.</p>
      ) : (
        <>
          {group.categories.length === 0 ? (
            <p className="text-sm">No categorized spending observed in the required evidence months.</p>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span role="status">{hiddenCount} of {group.categories.length} categories hidden in this view.</span>
                <Button type="button" variant="outline" aria-pressed={showHidden} onClick={onToggleShowHidden}>
                  Show hidden categories
                </Button>
                {hiddenCategoryIds.size > 0 && (
                  <Button type="button" variant="outline" onClick={onRestoreAll}>Restore all</Button>
                )}
              </div>
              <p className="text-xs text-muted-foreground">
                Hiding categories changes only this visit's rows and details, not the assessment across all covered categories.
              </p>
              {visibleCategories.length === 0 ? (
                <p className="text-sm">All categories are hidden in this view. Show hidden categories or Restore all to recover them.</p>
              ) : (
                <>
                  <Table aria-label={`${label} target category comparisons`}>
                    <TableHeader><TableRow>
                      <TableHead scope="col">Category</TableHead>
                      <TableHead scope="col">Target spend</TableHead>
                      <TableHead scope="col">Reference average</TableHead>
                      <TableHead scope="col">Change</TableHead>
                      <TableHead scope="col">Growth</TableHead>
                      <TableHead scope="col">Outcome</TableHead>
                      <TableHead scope="col">Visibility</TableHead>
                    </TableRow></TableHeader>
                    <TableBody>
                      {visibleCategories.map((category) => {
                        const comparison = category.comparison;
                        const hidden = hiddenCategoryIds.has(category.category_id);
                        const categoryLabel = `${category.category_title || category.category_id} (ID ${category.category_id})`;
                        return (
                          <TableRow key={category.category_id} className={hidden ? "bg-muted/50" : undefined}>
                            <TableHead scope="row" className="whitespace-normal">
                              <span>{category.category_title || category.category_id}</span>
                              <span className="block text-xs text-muted-foreground">ID {category.category_id}</span>
                              {hidden && <Badge variant="outline">Hidden</Badge>}
                            </TableHead>
                            <TableCell>{money(comparison.spending_amount)}</TableCell>
                            <TableCell>{money(comparison.baseline_amount)}</TableCell>
                            <TableCell>{money(comparison.change_amount, true)}</TableCell>
                            <TableCell>{percent(comparison.growth_percent, "nonpositive reference baseline")}</TableCell>
                            <TableCell><Badge variant={category.is_above_threshold ? "default" : "secondary"}>{lifestyleOutcome(category)}</Badge></TableCell>
                            <TableCell>
                              <Button
                                type="button" variant="outline" size="sm"
                                aria-label={`${hidden ? "Restore" : "Hide"} ${categoryLabel}`}
                                onClick={() => hidden ? onRestore(category.category_id) : onHide(category.category_id)}
                              >
                                {hidden ? "Restore" : "Hide"}
                              </Button>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                  {visibleCategories.map((category) => <LifestyleCreepDetails key={category.category_id} category={category} />)}
                </>
              )}
            </>
          )}
          <details className="rounded-md border p-3 text-sm">
            <summary className="cursor-pointer rounded-sm font-medium focus-visible:outline-2 focus-visible:outline-ring">
              Uncategorized report-grouped spending — {group.uncategorized_samples.length} required evidence months
            </summary>
            <div className="mt-3"><Samples samples={group.uncategorized_samples} /></div>
          </details>
          {group.uncategorized_samples.some((sample) => /[1-9]/.test(sample.amount)) && (
            <p className="text-sm text-muted-foreground">
              Uncategorized net spending assigned to this report group is present and excluded from category-threshold outcomes.
              Categorized results do not cover these amounts.
            </p>
          )}
        </>
      )}
    </section>
  );
}
