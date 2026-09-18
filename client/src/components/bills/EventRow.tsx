// F2 — one row in the expanded month list. Pure presentational. Read-only.

import { Check, X } from "lucide-react";

import type { FinanceEvent } from "@/types/api";
import { cn } from "@/lib/utils";

import { formatDate, formatKr, partnerDotClass } from "./finance-data";

export function EventRow({
  event,
  onView,
  showMatchChip = false,
}: {
  event: FinanceEvent;
  onView?: (eventId: string) => void;
  // Match chips are approved for PAST months only — the caller gates on
  // month state; this prop combines with isMatched != null (BE data gate).
  showMatchChip?: boolean;
}) {
  const isIncome = event.amount > 0;
  const isBuy = event.type === "buy";

  return (
    <div className="flex items-center gap-3 rounded-md px-2 py-2 transition-colors hover:bg-muted">
      <div className="flex w-12 shrink-0 flex-col items-center">
        <span className="text-sm font-semibold tabular-nums">
          {event.day}
        </span>
        <span className="text-[10px] text-muted-foreground uppercase">
          {formatDate(event.date).split(" ")[1]}
        </span>
      </div>

      <span
        className={cn(
          "inline-block size-2 shrink-0 rounded-full",
          // Accent by BE-assigned slot ("" → neutral gray).
          partnerDotClass(event.partner.partner_slot),
        )}
        title={event.partner.label}
        aria-hidden="true"
      />

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <button
            type="button"
            className={cn(
              "truncate text-left text-sm font-medium",
              onView &&
                "cursor-pointer hover:underline focus-visible:rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
            )}
            onClick={onView ? () => onView(event.id) : undefined}
            disabled={!onView}
          >
            {event.title}
          </button>
          {isBuy && (
            <span className="rounded-sm bg-secondary px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
              Buy
            </span>
          )}
          {/* Match chip (past months only — BE sets is_matched on buy
              events, but it is false rather than null on future months,
              so the caller's month gate decides visibility): ✓ found
              among posted CC txns, ✗ not found. */}
          {isBuy && showMatchChip && event.isMatched != null && (
            <span
              className={cn(
                "inline-flex items-center rounded-sm p-0.5",
                event.isMatched
                  ? "bg-income/15 text-income"
                  : "bg-shortfall/15 text-shortfall",
              )}
              role="img"
              aria-label={
                event.isMatched
                  ? "Matched to posted CC transaction"
                  : "Not found in posted CC transactions"
              }
              title={
                event.isMatched
                  ? "Matched to posted CC transaction"
                  : "Not found in posted CC transactions"
              }
            >
              {event.isMatched ? (
                <Check className="size-3" aria-hidden="true" />
              ) : (
                <X className="size-3" aria-hidden="true" />
              )}
            </span>
          )}
        </div>
        <span className="text-xs text-muted-foreground">{event.account}</span>
      </div>

      <span
        className={cn(
          "shrink-0 text-sm font-semibold tabular-nums",
          isIncome ? "text-income" : "text-shortfall",
        )}
      >
        {isIncome ? "+" : "−"}
        {formatKr(Math.abs(event.amount))}
      </span>
    </div>
  );
}