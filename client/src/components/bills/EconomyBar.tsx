// F2 — economy capsule bar. Pre-computed values come from finance-data.ts
// (or eventually from FastAPI /api/events month summary).

import {
  CircleDollarSign,
  CreditCard,
  PiggyBank,
  Receipt,
  Wallet,
} from "lucide-react";

import type {
  F2EconomyStatus,
  PartnerEconomy,
} from "@/types/api";
import { cn } from "@/lib/utils";

import { formatKr, partnerDotClass } from "./finance-data";

const STATUS: Record<
  F2EconomyStatus,
  { outline: string; badge: string; label: string; salaryFill: string }
> = {
  covered: {
    outline: "border-income",
    badge: "bg-income/15 text-income",
    label: "CC bill covered by salary",
    salaryFill: "bg-income/30",
  },
  partial: {
    outline: "border-savings shadow-[0_0_18px_-4px_var(--savings)]",
    badge: "bg-savings/25 text-savings-foreground",
    label: "Covered by savings",
    salaryFill: "bg-savings/35",
  },
  shortfall: {
    outline: "border-shortfall",
    badge: "bg-shortfall/15 text-shortfall",
    label: "Not covered",
    salaryFill: "bg-shortfall/30",
  },
};

function Zone({
  icon: Icon,
  title,
  valueLabel,
  accent,
  tint,
  iconColor,
  className,
  style,
  children,
  ariaLabel,
}: {
  icon: typeof Receipt;
  title: string;
  valueLabel: string;
  accent: string;
  tint: string;
  iconColor: string;
  className?: string;
  style?: React.CSSProperties;
  children?: React.ReactNode;
  // Override for screen readers. Use when `children` adds extra content
  // (e.g. bills zone adds est. CC bill sub-bar) so the accessible
  // label covers everything, not just the default bills value.
  ariaLabel?: string;
}) {
  return (
    <div
      className={cn(
        "relative flex min-w-0 items-center gap-2 pl-4 pr-3",
        tint,
        className,
      )}
      style={style}
      title={`${title}: ${valueLabel}`}
      aria-label={ariaLabel ?? `${title}: ${valueLabel}`}
    >
      {/* Accent rail on the left edge. */}
      <span
        className={cn(
          "absolute inset-y-2 left-0 w-1 rounded-full",
          accent,
        )}
        aria-hidden="true"
      />
      <Icon
        className={cn("size-4 shrink-0", iconColor)}
        aria-hidden="true"
      />
      {children ? (
        // F2-A: caller-supplied content (used by the bills zone to add
        // a fill bar + a sub-label below the main row). Skips the
        // default title + value block so the caller owns the layout.
        // Icon is rendered above so the visual contract holds.
        children
      ) : (
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="truncate text-[10px] font-medium uppercase tracking-wide leading-none text-foreground/60">
            {title}
          </span>
          <span className="whitespace-nowrap text-sm font-semibold leading-none tabular-nums text-foreground">
            {valueLabel}
          </span>
        </div>
      )}
    </div>
  );
}

// F2: Labels list row. Used by the "small bar" branch — a flat row of
// icon + label + value, rendered outside the capsule so it's never
// clipped by fill width.
function LabelsListRow({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Receipt;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-baseline gap-2 text-[11px]">
      <Icon
        className="size-3.5 shrink-0 text-foreground/70"
        aria-hidden="true"
      />
      <span className="flex-1 truncate text-foreground/70">{label}</span>
      <span className="font-semibold tabular-nums text-foreground">
        {value}
      </span>
    </div>
  );
}

export function EconomyBar({
  economy,
}: {
  economy: PartnerEconomy;
}) {
  const {
    partner,
    status,
    estimatedSalaryLabel,
    billsLabel,
    budgetLabel,
    ccUsageLabel,
    ccUsageIsFree,
    estimatedCcBillLabel,
    savingsBalanceLabel,
    savingsContributionLabel,
    savingsPlannedLabel,
    savingsDeltaLabel,
    realBills,
    realBillsLabel,
    realCcBill,
    realCcBillLabel,
    plannedCcBuys,
    plannedCcBuysLabel,
    bar,
  } = economy;
  // F2-UI L2 amendment 2026-08-03: past-only actuals render only in
  // the labels-list (small bar) branch. Both null for current/future.
  const showRealCcBill = realCcBill != null;
  const showRealBills = realBills != null;
  // F2 grid R2: "Planned buys" line — current/future only (realBills is
  // the past-month gate; actuals supersede the planned sum there).
  // plannedCcBuys is null on stale snapshots lacking the BE field.
  const showPlannedBuys = realBills == null && plannedCcBuys != null;
  // F2 §8: BE everyday_budget is null on the last sync-window month
  // (no m+1 data) → hide the budget zone entirely. Same null-gate
  // pattern as realBills. Negative budget is legal → renders.
  const showBudget = economy.budget != null;

  // F2 §13 revised: savings box is a planned-vs-actual pair (same
  // mental model as the budget zone). Null delta (future / no live
  // anchor) → fill + Δ value hidden, envelope still shown.
  // Null never reaches here via TS, but the mapper contract guarantees
  // "" + neutral tone + 0% width when null — belt and braces gate.
  const showSavingsFill = economy.savingsDelta != null;

  const s = STATUS[status];
  // Accent dot by BE-assigned slot ("" → neutral gray).
  const dotClass = partnerDotClass(partner.partner_slot);
  // Total bills = bills + estimated CC bill. Drives the "TOTAL BILLS"
  // pill in the capsule (big bar) or the labels list header (small bar).
  const upperBarTotalLabel = formatKr(economy.bills + economy.estimatedCcBill);
  // When bills/salary < 30% the bills bar is too short to host inline
  // labels cleanly. Swap the capsule out for a labels list with the same
  // numbers — total as header, four label rows, salary pill below.
  const showLabelsList = bar.billsFillSmall;

  return (
    // F2 layout: header on top, then a single row with capsule+salary
    // stacked on the left and the savings box filling the row height
    // on the right. Capsule is h-28, salary pill is h-9 (sits flush
    // below the capsule), savings box is h-full of the row so its
    // top aligns with the capsule's top and its bottom aligns with
    // the salary pill's bottom.
    <div className="flex flex-col gap-2">
      {/* Header — partner name + status badge. */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span
            className={cn("inline-block size-2.5 rounded-full", dotClass)}
            aria-hidden="true"
          />
          <span className="text-sm font-semibold">{partner.label}</span>
        </div>
        <span
          className={cn(
            "rounded-full px-2.5 py-0.5 text-xs font-semibold",
            s.badge,
          )}
        >
          {s.label} · net {bar.netLabel}
        </span>
      </div>

      {/* Main row — capsule (or labels list) on the left, savings box on
          the right. Savings box always present. Left side swaps to a
          labels list when bills/salary < 30% (bar too short for inline
          labels). items-stretch gives savings the full cross-axis height
          regardless of which left branch is rendered. */}
      <div className="flex items-stretch gap-2">
        {showLabelsList ? (
          /* === Labels list branch (small bar) ===
             Replaces the capsule entirely. TOTAL BILLS header on top,
             four labelled rows (icon + label + value), salary pill below.
             Same vertical envelope as the capsule branch so the savings
             box height stays consistent. */
          <div className="flex min-w-0 flex-1 flex-col gap-2">
            {/* Header: TOTAL BILLS pill. Mirrors the capsule pill but
                lives outside the bar zone so it's always legible. */}
            <div className="flex items-center self-start rounded-full bg-card px-3 py-1 shadow-sm border">
              <span className="text-[10px] font-bold uppercase tracking-wide text-foreground/85">
                Total bills
              </span>
              <span className="ml-2 text-xs font-semibold tabular-nums text-foreground">
                {upperBarTotalLabel}
              </span>
            </div>
            {/* Label rows. Black labels + black values, monospace
                numbers, icons from lucide for visual scanability.
                Past months add 2 rows: Real cc bill (paired with
                Estimated cc bill) and Real bills (paired with Bills). */}
            <div className="flex flex-1 flex-col justify-center gap-1.5">
              <LabelsListRow icon={Receipt} label="Bills" value={billsLabel} />
              {showRealBills && (
                <LabelsListRow
                  icon={Receipt}
                  label="Real bills"
                  value={realBillsLabel}
                />
              )}
              <LabelsListRow
                icon={Receipt}
                label="Estimated total bills"
                value={upperBarTotalLabel}
              />
              <LabelsListRow
                icon={CreditCard}
                label="Estimated cc bill"
                value={estimatedCcBillLabel}
              />
              {showRealCcBill && (
                <LabelsListRow
                  icon={CreditCard}
                  label="Real cc bill"
                  value={realCcBillLabel}
                />
              )}
              {showPlannedBuys && (
                <LabelsListRow
                  icon={CreditCard}
                  label="Planned buys"
                  value={plannedCcBuysLabel ?? ""}
                />
              )}
              {showBudget && (
                <LabelsListRow
                  icon={CircleDollarSign}
                  label="Budget"
                  value={budgetLabel}
                />
              )}
              <LabelsListRow
                icon={CreditCard}
                label={ccUsageIsFree ? "Free CC usage" : "CC usage"}
                value={ccUsageLabel}
              />
            </div>
            {/* Estimated salary coverage bar — unchanged. */}
            <div className="relative overflow-hidden rounded-full border bg-muted/30">
              <div
                className={cn(
                  "flex h-9 items-center gap-2 pl-4 pr-3",
                  s.salaryFill,
                )}
                style={{ width: bar.salaryWidth }}
              >
                <Wallet
                  className="size-4 shrink-0 text-foreground/70"
                  aria-hidden="true"
                />
                <span className="truncate text-[11px] font-medium leading-none text-foreground">
                  Estimated salary {estimatedSalaryLabel}
                </span>
              </div>
              <span
                className="pointer-events-none absolute inset-y-1 right-24 w-px bg-border"
                aria-hidden="true"
              />
              <span
                className={cn(
                  "pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-[10px] font-semibold uppercase tracking-wide tabular-nums",
                  bar.remainingTone === "income"
                    ? "text-income"
                    : "text-shortfall",
                )}
              >
                {bar.remainingLabel}
              </span>
            </div>
          </div>
        ) : (
          // === Capsule branch (big bar) ===
          // F2 redesign: capsule holds ONLY bills zone (TOTAL BILLS pill
          // + bills/estCcBill row). The budget bar is now a sibling of
          // the capsule + savings box, sitting between them. This keeps
          // the capsule's width math simple (no flex-2.2 vs fixed-width
          // budget zone fighting) and matches the F2 design where the
          // budget bar is its own column.
          <div className="flex min-w-0 flex-[4] flex-col gap-2">
            {/* Capsule — bills zone only. Width scales against
                max(outflow, salary) so it stays inside the salary
                column when covered, overflows when short. */}
            <div
              className="overflow-hidden rounded-[28px] border-2 bg-card shadow-sm"
              style={{ width: bar.upperBarWidth, position: "relative" }}
            >
              <div className="flex h-28">
                {/* Bills zone. F2-A: nested fill bar + est. cc bill sub-label. */}
                <Zone
                  icon={Receipt}
                  title="Bills"
                  valueLabel={billsLabel}
                  accent="bg-shortfall"
                  tint="bg-shortfall/10"
                  iconColor="text-shortfall"
                  className="shrink-0 grow overflow-hidden pt-8 pb-3"
                  style={{ width: bar.billsWidth, minWidth: "6rem", paddingLeft: "1.25rem" }}
                  ariaLabel={`Bills: ${billsLabel}; Estimated cc bill: ${estimatedCcBillLabel}`}
                >
                  {/* Total bills badge — two-row pill anchored to the
                      bills zone. Row 1 = TOTAL BILLS + combined total.
                      Row 2 = ESTIMATED TOTAL BILLS + planned bills.
                      Same badge styling as before (rounded-full, card
                      bg, shadow), just stacked instead of single-line. */}
                  <div className="pointer-events-none absolute left-3 top-2 z-10 flex flex-col items-start gap-0.5 rounded-2xl bg-card/90 px-2.5 py-1 shadow-sm backdrop-blur-sm">
                    <div className="flex items-baseline gap-1.5">
                      <span className="whitespace-nowrap text-[10px] font-bold uppercase tracking-wide text-foreground/85">
                        Total bills
                      </span>
                      <span className="whitespace-nowrap text-xs font-semibold tabular-nums text-foreground">
                        {upperBarTotalLabel}
                      </span>
                    </div>
                    <div className="flex items-baseline gap-1.5">
                      <span className="whitespace-nowrap text-[9px] font-medium uppercase tracking-wide text-foreground/60">
                        Estimated total bills
                      </span>
                      <span className="whitespace-nowrap text-[10px] font-semibold tabular-nums text-foreground/70">
                        {billsLabel}
                      </span>
                    </div>
                  </div>
                  {/* Left-to-right red fill = bills / (bills + estCcBill).
                      Bills label+value sit on the red (left), est. cc bill
                      label+value sit in the muted remainder (right). */}
                  <div
                    className="pointer-events-none absolute inset-y-0 left-0 bg-shortfall/40"
                    style={{ width: bar.billsFillWidth }}
                    aria-hidden="true"
                  />
                  <div className="relative z-10 flex min-w-0 flex-1 items-baseline justify-between gap-2 mt-6">
                    <div className="flex min-w-0 items-baseline gap-1.5">
                      <span className="text-[10px] font-medium uppercase tracking-wide leading-none text-shortfall-foreground/80">
                        Bills
                      </span>
                      <span className="text-sm font-semibold tabular-nums text-shortfall-foreground">
                        {billsLabel}
                      </span>
                    </div>
                    {/* Right side — past months show planned-vs-actual
                        cc pair stacked: Estimated cc bill on top,
                        Real cc bill below. Current/future months show
                        only the Estimated cc bill (single row). */}
                    <div className="flex min-w-0 flex-col items-end gap-1">
                      <div className="flex min-w-0 items-baseline gap-1.5">
                        <span className="text-[9px] font-medium uppercase tracking-wide leading-none text-foreground/60">
                          Estimated cc bill
                        </span>
                        <span className="text-[10px] font-semibold tabular-nums text-foreground/70">
                          {estimatedCcBillLabel}
                        </span>
                      </div>
                      {showRealCcBill && (
                        <div className="flex min-w-0 items-baseline gap-1.5">
                          <span className="text-[9px] font-medium uppercase tracking-wide leading-none text-foreground/60">
                            Real cc bill
                          </span>
                          <span className="text-[10px] font-semibold tabular-nums text-foreground/70">
                            {realCcBillLabel}
                          </span>
                        </div>
                      )}
                      {showPlannedBuys && (
                        <div className="flex min-w-0 items-baseline gap-1.5">
                          <span className="text-[9px] font-medium uppercase tracking-wide leading-none text-foreground/60">
                            Planned buys
                          </span>
                          <span className="text-[10px] font-semibold tabular-nums text-foreground/70">
                            {plannedCcBuysLabel}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                </Zone>
              </div>
            </div>

          {/* Estimated salary coverage bar — width scales with salary vs outflows. */}
          <div className="relative overflow-hidden rounded-full border bg-muted/30">
            <div
              className={cn(
                "flex h-9 items-center gap-2 pl-4 pr-3",
                s.salaryFill,
              )}
              style={{ width: bar.salaryWidth }}
            >
              <Wallet
                className="size-4 shrink-0 text-foreground/70"
                aria-hidden="true"
              />
              <span className="truncate text-[11px] font-medium leading-none text-foreground">
                Estimated salary {estimatedSalaryLabel}
              </span>
            </div>
            <span
              className="pointer-events-none absolute inset-y-1 right-24 w-px bg-border"
              aria-hidden="true"
            />
            <span
              className={cn(
                "pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-[10px] font-semibold uppercase tracking-wide tabular-nums",
                bar.remainingTone === "income"
                  ? "text-income"
                  : "text-shortfall",
              )}
            >
              {bar.remainingLabel}
            </span>
          </div>
          </div>
        )}

        {/* F2-B: budget bar — extracted from the capsule and placed
            between the capsule + savings box. Fixed width column so
            the capsule's flex math stays simple. Vertical fill grows
            bottom→top; overspent tints the whole bar red.
            F2 §8: hidden entirely when BE everyday_budget is null. */}
        {showBudget && (
        <div
          className={cn(
            "relative flex shrink-0 flex-col overflow-hidden rounded-2xl border pl-4 pr-3 py-2",
            // Only tint red when the over-spend is real AND budget is
            // positive. Negative budget would always trip overspent →
            // bg permanently red even when cc_usage is small, which is
            // misleading. Skip tint when budget <= 0 (label already
            // negative, deficit surfaced there).
            bar.budgetOverspent && (economy.budget ?? 0) > 0
              ? "bg-shortfall/15"
              : "bg-muted/40",
          )}
          style={{ width: "8rem" }}
        >
          <span
            className="absolute inset-y-2 left-0 z-10 w-1 rounded-full bg-foreground/30"
            aria-hidden="true"
          />

          {/* Top row — "Budget" label stacked above the budget amount. */}
          <div className="relative z-10 flex flex-col gap-0.5 pb-1">
            <span className="flex items-center gap-2 text-[10px] font-medium uppercase tracking-wide leading-none text-foreground/60">
              <CreditCard
                className="size-4 shrink-0 text-foreground/70"
                aria-hidden="true"
              />
              <span>Budget</span>
            </span>
            <span className="text-sm font-semibold leading-none tabular-nums text-foreground">
              {budgetLabel}
            </span>
          </div>

          {/* F2-B: vertical fill bar. The "CC usage" label + value
              sit inside the bar itself, anchored to the bottom so
              they stay visible as the bar grows. When the bar is
              too short to contain the text, the text renders just
              above the fill (in the muted remainder). */}
          <div className="relative z-0 basis-14 grow min-h-14">
            {/* Fill (decorative). */}
            <div
              className={cn(
                "absolute inset-x-0 bottom-0 rounded-t-md",
                bar.budgetFillTone === "income" && "bg-income",
                bar.budgetFillTone === "warning" && "bg-warning",
                bar.budgetFillTone === "shortfall" && "bg-shortfall",
              )}
              style={{ height: bar.budgetUsageWidth }}
              aria-hidden="true"
            />
            {/* CC usage label + value overlay. Anchored to the
                bottom of the wrapper so it always sits at the
                baseline of the fill region, regardless of fill %. */}
            <div className="absolute inset-x-0 bottom-0 z-10 flex items-baseline justify-end gap-1.5 px-2 pb-1">
              <span className="text-[9px] font-medium uppercase tracking-wide text-foreground/45">
                {ccUsageIsFree ? "Free CC usage" : "CC usage"}
              </span>
              <span
                className={cn(
                  "text-[10px] font-semibold tabular-nums",
                  // Fill bg X → value text X-foreground.
                  // income/warning on muted bg → foreground (dark).
                  // shortfall on red → shortfall-foreground (white).
                  bar.budgetFillTone === "shortfall"
                    ? "text-shortfall-foreground"
                    : bar.budgetFillTone === "warning"
                      ? "text-warning-foreground"
                      : "text-foreground",
                )}
              >
                {ccUsageLabel}
              </span>
            </div>
          </div>
        </div>
        )}

        {/* F2-C: savings box. flex-1 takes the remaining ~20% of the
            row width. min-w-[10rem] prevents squeezing the value
            below readability. items-stretch on the row gives it the
            full cross-axis height (capsule + salary + gap). Contains
            label, total savings balance, delta value (signed), and
            a vertical status bar on the left edge of the bottom row. */}
        <div className="relative flex min-w-[10rem] flex-1 flex-col gap-2 overflow-hidden rounded-2xl border bg-income/10 px-3 py-2">
          <span
            className="pointer-events-none absolute inset-y-2 left-0 w-1 rounded-full bg-income"
            aria-hidden="true"
          />
          <PiggyBank
            className="pointer-events-none absolute right-3 top-3 size-4 shrink-0 text-income"
            aria-hidden="true"
          />

          {/* Top: label + balance. Right padding matches the PiggyBank
              icon gutter so text doesn't overlap the icon. */}
          <div className="flex flex-col gap-0.5 pl-1.5 pr-6">
            <span className="text-[9px] font-medium uppercase tracking-wide leading-none text-foreground/60">
              Savings
            </span>
            <span className="text-lg font-semibold leading-tight tabular-nums text-foreground">
              {savingsBalanceLabel}
            </span>
          </div>

          {/* Bottom: vertical envelope+fill bar (left) + label/value
              to the right. Mirrors the budget zone's envelope/fill
              pattern: the track is the savings balance, the envelope
              marker is the planned savings (budget width analog), and
              the fill is the actual delta growing bottom→top. Null
              delta → fill + value hidden, envelope still shown. */}
          <div className="flex flex-1 items-stretch gap-2 pl-1.5 pr-6">
            {/* Vertical track — self-stretch fills the cross-axis of
                the row. Envelope (planned) renders as a border marker
                at its height; fill (actual delta) clamps inside it. */}
            <div
              className="relative w-3 shrink-0 self-stretch overflow-hidden rounded-full bg-foreground/10"
              aria-hidden="true"
            >
              {/* Envelope = planned share of balance. 0 planned (no
                  plan known) → marker sits at 0% (empty envelope). */}
              <div
                className="absolute inset-x-0 bottom-0 rounded-full border-2 border-income/60"
                style={{ height: bar.savingsPlannedWidth }}
                aria-hidden="true"
                data-testid="savings-envelope"
              />
              {showSavingsFill && (
                <div
                  className={cn(
                    "absolute inset-x-0 bottom-0 rounded-full",
                    bar.savingsDeltaTone === "income" && "bg-income",
                    bar.savingsDeltaTone === "shortfall" && "bg-shortfall",
                    bar.savingsDeltaTone === "neutral" && "bg-transparent",
                  )}
                  style={{ height: bar.savingsDeltaWidth }}
                />
              )}
            </div>
            {/* Δ savings label + value. Bottom-anchored via justify-end
                so it sits at the baseline of the bar. Null delta →
                value hidden (planned label still shown above). */}
            <div className="flex flex-1 flex-col justify-end gap-0.5 pb-1 pr-6">
              <span className="text-[9px] font-medium uppercase tracking-wide leading-none text-foreground/45">
                Δ savings
              </span>
              {showSavingsFill ? (
                <span
                  className={cn(
                    "text-sm font-semibold leading-none tabular-nums",
                    bar.savingsDeltaTone === "income" && "text-income",
                    bar.savingsDeltaTone === "shortfall" && "text-shortfall",
                    bar.savingsDeltaTone === "neutral" && "text-foreground/60",
                  )}
                >
                  {savingsDeltaLabel}
                </span>
              ) : (
                <span className="text-[10px] tabular-nums text-foreground/45">
                  planned {savingsPlannedLabel}
                </span>
              )}
            </div>
          </div>

          {/* F2 grid R2: scheduled savings transfer — mapped from BE
              savings_transfer but never rendered before. */}
          <span className="pl-1.5 text-[10px] tabular-nums text-foreground/45">
            Scheduled transfer: {savingsContributionLabel}
          </span>
        </div>
      </div>
    </div>
  );
}
