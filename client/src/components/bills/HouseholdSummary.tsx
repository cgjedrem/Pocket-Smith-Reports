// Household summary strip — current-month planned expenses, saveable
// total, and end-of-window savings balance, aggregated purely client-side
// over the hydrated MonthData window. Sticky under the page header.

import { useMemo } from "react";

import { useBillsSourceSubscription } from "@/hooks/useBillsSourceSubscription";
import { getMonths } from "@/lib/bills-source";
import { cn } from "@/lib/utils";

import { formatKr } from "./finance-data";

// Always the current local month (same convention as BillsPage).
// Re-derived per render so month-rollover picks up the new value.
function currentMonthKey(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function Figure({
  label,
  value,
  valueClassName,
}: {
  label: string;
  value: string;
  valueClassName?: string;
}) {
  return (
    <span className="flex items-baseline gap-1.5">
      <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <span className={cn("text-sm font-bold tabular-nums", valueClassName)}>
        {value}
      </span>
    </span>
  );
}

export function HouseholdSummary() {
  const version = useBillsSourceSubscription();
  const months = useMemo(() => getMonths(), [version]);
  if (months.length === 0) return null;

  const currentKey = currentMonthKey();
  // Defensive fallback: the fetch window is always anchored on the current
  // month, but if it isn't loaded (e.g. mock window drift) use the first.
  const current = months.find((m) => m.key === currentKey) ?? months[0];
  const last = months[months.length - 1];

  // Total planned outflow this month: bills + estimated CC bill per partner.
  const plannedExpenses = current.partners.reduce(
    (sum, p) => sum + p.bills + p.estimatedCcBill,
    0,
  );
  // What salary leaves over after the planned outflow.
  const saveable = current.partners.reduce(
    (sum, p) => sum + (p.estimatedSalary - p.bills - p.estimatedCcBill),
    0,
  );
  // Household savings balance at the last loaded month.
  const trajectory = last.partners.reduce(
    (sum, p) => sum + p.savingsBalance,
    0,
  );

  return (
    <section
      aria-label="Household summary"
      className="sticky top-0 z-10 flex flex-wrap items-center gap-x-6 gap-y-1 border-b bg-background/80 py-2 backdrop-blur"
    >
      <Figure
        label={`Planned expenses · ${current.label}`}
        value={formatKr(plannedExpenses)}
      />
      <Figure
        label={`Saveable · ${current.label}`}
        value={formatKr(saveable)}
        valueClassName={saveable >= 0 ? "text-income" : "text-shortfall"}
      />
      <Figure
        label={`Savings by ${last.label}`}
        value={formatKr(trajectory)}
      />
    </section>
  );
}
