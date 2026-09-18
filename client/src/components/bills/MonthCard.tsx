// F2 — collapsible month row. Always shows 2 partner economy bars.
// Expanded state shows day-by-day event list. Read-only.

import { useState } from "react";
import { ChevronDown } from "lucide-react";

import type { FinanceEvent, MonthData } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

import { BudgetTab } from "./BudgetTab";
import { EconomyBar } from "./EconomyBar";
import { EventRow } from "./EventRow";
import { SavingsSparkline, type SparklineSeries } from "./SavingsSparkline";
import { formatKr } from "./finance-data";

// Group events by category (event.title). Categories sorted alphabetically
// (case-insensitive). Within each group events sorted by date asc, then id
// for stable order across re-renders.
function groupEventsByCategory(
  events: FinanceEvent[],
): { category: string; events: FinanceEvent[] }[] {
  const byCat = new Map<string, FinanceEvent[]>();
  for (const e of events) {
    const key = e.title || "Uncategorized";
    const arr = byCat.get(key);
    if (arr) arr.push(e);
    else byCat.set(key, [e]);
  }
  const groups = Array.from(byCat, ([category, evs]) => ({ category, events: evs }));
  groups.sort((a, b) =>
    a.category.localeCompare(b.category, undefined, { sensitivity: "base" }),
  );
  for (const g of groups) {
    g.events.sort((a, b) => {
      const d = a.date.localeCompare(b.date);
      return d !== 0 ? d : a.id.localeCompare(b.id);
    });
  }
  return groups;
}

export function MonthCard({
  month,
  expanded,
  onToggle,
  onEventClick,
  savingsSeries,
}: {
  month: MonthData;
  expanded: boolean;
  onToggle: () => void;
  onEventClick?: (eventId: string) => void;
  // Full-window savings trajectory per partner, rendered as a sparkline
  // in the header row. Optional — omitted when no data.
  savingsSeries?: SparklineSeries[];
}) {
  const netPositive = month.net >= 0;
  // R3: Events/Budget tab inside the expanded body. Local per-card state,
  // no URL persistence — resets to Events on remount.
  const [tab, setTab] = useState<"events" | "budget">("events");

  // Current local month key, re-derived per render (month-rollover safe).
  // YYYY-MM strings compare lexicographically.
  const now = new Date();
  const currentKey = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const isPlanned = month.key > currentKey;
  // Past gate — drives the isMatched chips and BudgetTab's realized fills.
  const isPast = month.key < currentKey;

  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border bg-card shadow-sm transition-shadow",
        expanded && "shadow-md",
        isPlanned && "border-dashed",
      )}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="flex w-full items-center gap-4 px-4 py-3.5 text-left transition-colors hover:bg-muted/60"
      >
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <span className="font-semibold text-base">{month.label}</span>
          {isPlanned && (
            <Badge variant="outline" className="px-1.5 py-0 text-[10px]">
              Planned
            </Badge>
          )}
        </div>

        {/* Header metrics — Net is the hero figure; Bills/Buys counts are
            demoted to small muted text. All values still present. */}
        <div className="hidden items-center gap-4 text-[11px] text-muted-foreground sm:flex">
          <span>Bills {month.billsCount}</span>
          <span className="text-border">•</span>
          <span>Buys {month.buysCount}</span>
          <span className="text-border">•</span>
          <span>
            Net{" "}
            <span
              className={cn(
                "text-sm font-bold tabular-nums",
                netPositive ? "text-income" : "text-shortfall",
              )}
            >
              {formatKr(month.net)}
            </span>
          </span>
        </div>

        {savingsSeries && savingsSeries.length > 0 && (
          <SavingsSparkline series={savingsSeries} />
        )}

        <ChevronDown
          className={cn(
            "size-5 shrink-0 text-muted-foreground transition-transform",
            expanded && "rotate-180",
          )}
        />
      </button>

      {/* Mobile stat line — below header on small screens. */}
      <div className="flex items-center gap-3 border-t px-4 py-2 text-xs text-muted-foreground sm:hidden">
        <span>Bills {month.billsCount}</span>
        <span>Buys {month.buysCount}</span>
        <span
          className={cn(
            "ml-auto font-semibold",
            netPositive ? "text-income" : "text-shortfall",
          )}
        >
          {formatKr(month.net)}
        </span>
      </div>

      {/* Partner economy bars — always visible. Only event list below
          is collapsible via `expanded`. */}
      <div className="flex flex-col gap-5 border-t bg-muted/30 px-4 py-4">
        {month.partners.map((p) => (
          <EconomyBar
            // Semantic id; label as legacy-mode fallback.
            key={p.partner.partner_id || p.partner.label}
            economy={p}
          />
        ))}
      </div>

      {expanded && (
        <div className="flex flex-col gap-3 border-t bg-muted/30 px-4 pb-4 pt-4">
          {/* Events / Budget tabs — wraps everything below. Events tab is
              the unchanged grouped event list (incl. match chips). */}
          <div
            role="tablist"
            aria-label="Expanded month details"
            className="flex gap-1 self-start rounded-md border bg-muted/40 p-0.5"
          >
            {(
              [
                ["events", "Events"],
                ["budget", "Budget"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                role="tab"
                aria-selected={tab === value}
                tabIndex={tab === value ? 0 : -1}
                onClick={() => setTab(value)}
                onKeyDown={(e) => {
                  if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
                  e.preventDefault();
                  const next = tab === "events" ? "budget" : "events";
                  setTab(next);
                  // ARIA tabs pattern: focus follows selection (PR65 review).
                  e.currentTarget.parentElement
                    ?.querySelector<HTMLButtonElement>(`[data-tab="${next}"]`)
                    ?.focus();
                }}
                data-tab={value}
                className={cn(
                  "rounded px-2.5 py-1 text-[11px] font-medium text-muted-foreground transition-colors",
                  tab === value && "bg-card text-foreground shadow-sm",
                )}
              >
                {label}
              </button>
            ))}
          </div>

          {tab === "events" ? (
            <div className="rounded-lg border bg-card p-2">
              <div className="mb-1 px-2 py-1">
                <span className="text-xs font-medium text-muted-foreground">
                  {month.events.length} events this month
                </span>
              </div>
              <div className="flex flex-col">
                {groupEventsByCategory(month.events).map((group) => (
                  <div key={group.category} className="flex flex-col">
                    <div className="sticky top-0 z-10 flex items-center justify-between border-y border-border/60 bg-muted/80 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground backdrop-blur">
                      <span>{group.category}</span>
                      <span className="font-normal normal-case">
                        {group.events.length}{" "}
                        {group.events.length === 1 ? "event" : "events"}
                      </span>
                    </div>
                    <div className="flex flex-col divide-y divide-border/60">
                      {group.events.map((event) => (
                        <EventRow
                          key={event.id}
                          event={event}
                          onView={onEventClick}
                          showMatchChip={isPast}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <BudgetTab month={month} isPast={isPast} />
          )}
        </div>
      )}
    </div>
  );
}