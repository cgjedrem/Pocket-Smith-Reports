// F2 grid R4 — "Budget" tab inside expanded month cards. Side-by-side
// partner columns (partner A | partner B), each with 3 ALWAYS-visible groups
// derived purely from already-loaded MonthData (no new fetches):
//  BILLS — planned per bill category, plus a Total row (every month) and
//     a past-months-only "real paid of planned" header bar (realBills
//     null-gate). Excludes salary/savings events (round-4 mapper fix).
//  CC — planned per buy category vs REAL posted usage in that category
//     (partner.ccUsageByCategory, budget-based — same category txn goes
//     to same category planned). ccUsageByCategory null (future/stale)
//     → "planned" only, fill 0.
//  FREE — real card USAGE per category (partner.ccUsageByCategory, raw),
//     EXCLUDING categories already covered by a planned CC buy in the CC
//     group above (round-4.7: budget-based split, a category is either a
//     planned buy or free spend, never both — no per-title subtraction).
//     Muted fallback line when ccUsageByCategory is null (stale
//     snapshot / no real CC activity).
// Empty groups render one muted line instead of vanishing — round-4 fix
// for "CC budget is not there at all" confusion.

import { cn } from "@/lib/utils";
import type {
  F2PartnerIdentity,
  FinanceEvent,
  MonthData,
  PartnerEconomy,
} from "@/types/api";

import {
  byDisplayOrder,
  formatKr,
  formatSignedKr,
  partnerDotClass,
  samePartnerIdentity,
} from "./finance-data";

type RowTone = "income" | "neutral" | "shortfall";

const TONE_FILL: Record<RowTone, string> = {
  income: "bg-income",
  neutral: "bg-foreground/30",
  shortfall: "bg-shortfall",
};

const pct = (ratio: number) =>
  `${Math.max(0, Math.min(ratio, 1)) * 100}%`;

// One filled-bar row: category label left, "X kr of Y kr" right.
function BudgetBarRow({
  label,
  valueLabel,
  fill,
  tone,
  over,
}: {
  label: string;
  valueLabel: string;
  fill: string; // CSS width, 0–100%
  tone: RowTone;
  // Amount over the planned/budget figure — appended to valueLabel in
  // text-shortfall. Omit/0 when not over.
  over?: number;
}) {
  return (
    <div className="flex flex-col gap-1 py-0.5">
      <div className="flex items-baseline justify-between gap-2 text-[11px]">
        <span className="truncate text-foreground/80">{label}</span>
        <span className="shrink-0 tabular-nums text-muted-foreground">
          {valueLabel}
          {over != null && over > 0 && (
            <span className="text-shortfall"> (+{formatSignedKr(over).replace(/^\+/, "")} over)</span>
          )}
        </span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-muted"
        aria-hidden="true"
      >
        <div
          className={cn("h-full rounded-full", TONE_FILL[tone])}
          style={{ width: fill }}
        />
      </div>
    </div>
  );
}

// Muted single-line placeholder for an empty group — group headers stay
// visible even with zero rows (round-4: never silently omit a section).
function EmptyLine({ text }: { text: string }) {
  return (
    <p className="px-1 py-1 text-[11px] text-muted-foreground/70">{text}</p>
  );
}

// Planned sums per buy category, one partner only (round-4.7: budget-based
// numerator now comes from ccUsageByCategory in Section B directly, per
// user rule "do not use matched, but budget based — same category txn
// go to same category planned").
function groupBuysByCategory(
  events: FinanceEvent[],
  partner: F2PartnerIdentity,
): { category: string; planned: number }[] {
  const byCat = new Map<string, number>();
  for (const e of events) {
    if (e.type !== "buy" || !samePartnerIdentity(e.partner, partner)) continue;
    const key = e.title || "Uncategorized";
    byCat.set(key, (byCat.get(key) ?? 0) + Math.abs(e.amount));
  }
  return Array.from(byCat, ([category, planned]) => ({ category, planned })).sort(
    (a, b) => b.planned - a.planned,
  );
}

// Sum of salary-type events for one partner (no matching — is_matched
// is null on salary events, so this is a plain informational total).
function sumSalary(events: FinanceEvent[], partner: F2PartnerIdentity): number {
  return events
    .filter((e) => e.type === "salary" && samePartnerIdentity(e.partner, partner))
    .reduce((sum, e) => sum + Math.abs(e.amount), 0);
}

// Planned sums per bill category, one partner only. Round-4: explicit
// salary/savings exclusion (belt-and-braces on top of the mapper fix —
// the mapper no longer coerces those types to "bill", but this filter
// guards against any future BE type drift).
function groupBillsByCategory(
  events: FinanceEvent[],
  partner: F2PartnerIdentity,
): { category: string; planned: number }[] {
  const byCat = new Map<string, number>();
  for (const e of events) {
    if (
      e.type !== "bill" ||
      !samePartnerIdentity(e.partner, partner) ||
      // Round-4.9: CC paydown is not a bill — the "CC bill" est-vs-real
      // row already represents it; including it here duplicates the value
      // and inflates the Planned bills total.
      e.isCcPayment === true
    )
      continue;
    const key = e.title || "Uncategorized";
    byCat.set(key, (byCat.get(key) ?? 0) + Math.abs(e.amount));
  }
  return Array.from(byCat, ([category, planned]) => ({ category, planned })).sort(
    // Round-4.9: smallest → largest, same order as the FREE group.
    (a, b) => a.planned - b.planned,
  );
}

// Small partner tag — same dot+name vocabulary as MathBreakdown.
// Accent by BE-assigned slot ("" → neutral gray), never a hardcoded label.
function PartnerTag({ partner }: { partner: F2PartnerIdentity }) {
  return (
    <div className="flex items-center gap-1.5">
      <span
        className={cn(
          "inline-block size-1.5 rounded-full",
          partnerDotClass(partner.partner_slot),
        )}
        aria-hidden="true"
      />
      <span className="text-[11px] font-semibold text-foreground/80">
        {partner.label}
      </span>
    </div>
  );
}

// Group header — ALWAYS visible (round-4: no more silent omission).
function GroupHeader({ title }: { title: string }) {
  return (
    <div className="border-b border-border/60 px-1 pb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
      {title}
    </div>
  );
}

// SECTION A — bills budget per category (+ Total row every month,
// + past-only real-vs-planned bar, + Salary context row, + CC bill
// est-vs-real row). Salary/savings events excluded from the bill
// category rows and the Total sum — round-4.6 adds Salary/CC bill as
// separate informational rows, not folded into the bill total.
function BillsBudgetGroup({
  partner,
  month,
  isPast,
}: {
  partner: PartnerEconomy;
  month: MonthData;
  isPast: boolean;
}) {
  const rows = groupBillsByCategory(month.events, partner.partner);
  const total = rows.reduce((sum, r) => sum + r.planned, 0);
  const showReal = partner.realBills != null && partner.bills > 0;
  const salaryTotal = sumSalary(month.events, partner.partner);
  const showSalary = salaryTotal > 0;

  // CC bill: PAST months only show real-vs-est (realCcBill is also set on
  // CURRENT months by the CC-payment event override — PR65 review: that
  // must still render as a current-style est-only row, so gate on isPast).
  const estCcBill = partner.estimatedCcBill;
  const realCcBill = isPast ? partner.realCcBill : null;
  const showCcBill = estCcBill > 0 || realCcBill != null;
  const ccOver =
    realCcBill != null && realCcBill > estCcBill
      ? realCcBill - estCcBill
      : undefined;

  if (rows.length === 0 && !showReal && !showSalary && !showCcBill) {
    return (
      <div className="flex flex-col gap-1">
        <GroupHeader title="Bills" />
        <EmptyLine text="No bill budgets" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1">
      <GroupHeader title="Bills" />
      {/* Salary first — income context. Shared row shape (neutral, fill
          0) keeps row height consistent with siblings; no matching since
          is_matched is null on salary events. Omitted when 0. */}
      {showSalary && (
        <BudgetBarRow
          label="Salary"
          valueLabel={formatKr(salaryTotal)}
          fill="0%"
          tone="neutral"
        />
      )}
      {/* Every month: filtered-sum total row (excludes salary/savings/CC
          bill — bill categories only, round-4 behavior unchanged). */}
      <div className="flex items-baseline justify-between gap-2 px-1 text-[11px] font-medium">
        <span className="text-foreground/70">Planned bills</span>
        <span className="tabular-nums text-foreground/70">
          {formatKr(total)}
        </span>
      </div>
      {/* Past months only (realBills null-gate, same pattern as
          MathBreakdown): real paid vs planned, green when under. */}
      {showReal && (
        <BudgetBarRow
          label="Real paid"
          valueLabel={`${partner.realBillsLabel} of ${partner.billsLabel} planned`}
          fill={pct((partner.realBills ?? 0) / partner.bills)}
          tone={partner.realBills! <= partner.bills ? "income" : "shortfall"}
          over={
            partner.realBills! > partner.bills
              ? partner.realBills! - partner.bills
              : undefined
          }
        />
      )}
      {rows.map((r) => (
        <BudgetBarRow
          key={r.category}
          label={r.category}
          valueLabel={formatKr(r.planned)}
          fill={pct(total > 0 ? r.planned / total : 0)}
          tone="neutral"
        />
      ))}
      {/* CC bill last — estimated vs real card bill (round-4.6). Past
          (realCcBill != null): fill = real/est clamped, over indicator
          when real exceeds est. Current/future: est-only "planned" row,
          fill 0, neutral tone — same pattern as Section B rows. */}
      {showCcBill &&
        (realCcBill != null ? (
          <BudgetBarRow
            label="CC bill"
            valueLabel={`${formatKr(realCcBill)} of ${formatKr(estCcBill)} planned`}
            fill={pct(estCcBill > 0 ? realCcBill / estCcBill : 0)}
            tone={realCcBill > estCcBill ? "shortfall" : "income"}
            over={ccOver}
          />
        ) : (
          <BudgetBarRow
            label="CC bill"
            valueLabel={`${formatKr(estCcBill)} planned`}
            fill="0%"
            tone="neutral"
          />
        ))}
    </div>
  );
}

// SECTION B — CC budgets per category, budget-based (round-4.7): numerator
// is real posted usage in that category from partner.ccUsageByCategory —
// same category txn goes to same category planned.
// Past/current (ccUsageByCategory non-null): "usage of planned", fill =
// usage/planned. ccUsageByCategory null (future/stale): "planned" only,
// fill 0.
function CcBudgetGroup({
  partner,
  month,
}: {
  partner: PartnerEconomy;
  month: MonthData;
}) {
  const rows = groupBuysByCategory(month.events, partner.partner);
  const byCategory = partner.ccUsageByCategory;
  // Round-4.9: Total row — usage sum vs planned sum, over indicator when
  // the envelope is exceeded (aggregate of the rows above).
  const plannedTotal = rows.reduce((s, r) => s + r.planned, 0);
  const usageTotal =
    byCategory == null
      ? null
      : rows.reduce((s, r) => s + (byCategory[r.category] ?? 0), 0);
  const totalOver =
    usageTotal != null && usageTotal > plannedTotal
      ? usageTotal - plannedTotal
      : undefined;
  return (
    <div className="flex flex-col gap-1">
      <GroupHeader title="CC" />
      {rows.length === 0 ? (
        <EmptyLine text="No CC budgets" />
      ) : (
        <>
          {rows.map((r) => {
            const usage = byCategory == null ? null : byCategory[r.category] ?? 0;
            const over =
              usage != null && usage > r.planned ? usage - r.planned : undefined;
            return (
              <BudgetBarRow
                key={r.category}
                label={r.category}
                valueLabel={
                  usage != null
                    ? `${formatKr(usage)} of ${formatKr(r.planned)} planned`
                    : `${formatKr(r.planned)} planned`
                }
                fill={pct(r.planned > 0 ? (usage ?? 0) / r.planned : 0)}
                tone={over != null ? "shortfall" : usage != null ? "income" : "neutral"}
                over={over}
              />
            );
          })}
          <BudgetBarRow
            label="Total"
            valueLabel={
              usageTotal != null
                ? `${formatKr(usageTotal)} of ${formatKr(plannedTotal)} planned`
                : `${formatKr(plannedTotal)} planned`
            }
            fill={pct(plannedTotal > 0 ? (usageTotal ?? 0) / plannedTotal : 0)}
            tone={
              totalOver != null
                ? "shortfall"
                : usageTotal != null
                  ? "income"
                  : "neutral"
            }
            over={totalOver}
          />
        </>
      )}
    </div>
  );
}

// SECTION C — free budget: real card USAGE per category, EXCLUDING
// categories that have planned buys in Section B (round-4.7: budget-based
// split — a category is either a planned CC buy or unplanned free spend,
// never both). Round-4.8: per-row "of budget" denominator dropped (user:
// "this values are completely useless") — rows are plain amounts, sorted
// smallest→largest, with all sub-500kr categories merged into one "Other"
// row. A single "Total" row at the bottom carries the budget comparison
// for the whole group. Muted fallback when ccUsageByCategory is null (BE
// sends None on stale snapshots / no real CC activity / future months).
const FREE_BUCKET_THRESHOLD = 500;

function FreeBudgetGroup({
  partner,
  month,
}: {
  partner: PartnerEconomy;
  month: MonthData;
}) {
  const byCategory = partner.ccUsageByCategory;
  const plannedCategories = new Set(
    groupBuysByCategory(month.events, partner.partner).map((r) => r.category),
  );
  // Round-4.9: drop CC-Payment rows that duplicate Section B "CC bill".
  // realCcBill (when non-null) already IS the CC-paydown sum, shown as the
  // "X of Y planned" bar in Section A; rendering it again in FREE is the
  // same number twice. Exclude only when the amount equals realCcBill —
  // any other usage of that category stays a plain free-spend row.
  const realCcBill = partner.realCcBill;
  const shouldMergeCcPayment =
    realCcBill != null && !plannedCategories.has("CC Payment (paired)");

  let body: React.ReactNode;
  if (byCategory == null) {
    body = <EmptyLine text="No free-budget data" />;
  } else {
    // Rounding guard: drop rows whose value is ~0 to keep the list clean.
    // Also drop categories already covered by a planned CC buy row.
    const included = Object.entries(byCategory).filter(([category, real]) => {
      if (Math.abs(real) < 0.005) return false;
      if (plannedCategories.has(category)) return false;
      if (
        shouldMergeCcPayment &&
        category === "CC Payment (paired)" &&
        Math.abs(real - realCcBill) < 0.005
      ) {
        return false;
      }
      return true;
    });

    if (included.length === 0) {
      body = <EmptyLine text="No free-budget spend" />;
    } else {
      // Bucket every category under the threshold into one "Other" row.
      const big = included.filter(([, real]) => real >= FREE_BUCKET_THRESHOLD);
      const small = included.filter(([, real]) => real < FREE_BUCKET_THRESHOLD);
      const rows: { label: string; value: number }[] = big.map(([category, real]) => ({
        label: category,
        value: real,
      }));
      if (small.length === 1) {
        rows.push({ label: small[0][0], value: small[0][1] });
      } else if (small.length > 1) {
        const sum = small.reduce((s, [, real]) => s + real, 0);
        rows.push({ label: `Other (${small.length})`, value: sum });
      }
      rows.sort((a, b) => a.value - b.value);

      const total = included.reduce((s, [, real]) => s + real, 0);
      const budget = partner.budget;
      const hasBudget = budget != null && budget > 0;
      const maxValue = Math.max(...rows.map((r) => r.value));

      body = (
        <>
          {rows.map((r) => (
            <BudgetBarRow
              key={r.label}
              label={r.label}
              valueLabel={formatKr(r.value)}
              fill={pct(maxValue > 0 ? r.value / maxValue : 0)}
              tone="neutral"
            />
          ))}
          {hasBudget ? (
            <BudgetBarRow
              label="Total"
              valueLabel={`${formatKr(total)} of ${formatKr(budget)} budget`}
              fill={pct(total / budget)}
              tone={total > budget ? "shortfall" : "income"}
              over={total > budget ? total - budget : undefined}
            />
          ) : (
            <BudgetBarRow
              label="Total"
              valueLabel={formatKr(total)}
              fill="0%"
              tone="neutral"
            />
          )}
        </>
      );
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <GroupHeader title="Free" />
      {body}
    </div>
  );
}

// One partner column: header + BILLS/CC/FREE groups in fixed order.
function PartnerColumn({
  partner,
  month,
  isPast,
}: {
  partner: PartnerEconomy;
  month: MonthData;
  isPast: boolean;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-md border border-border/40 p-2">
      <PartnerTag partner={partner.partner} />
      <BillsBudgetGroup partner={partner} month={month} isPast={isPast} />
      <CcBudgetGroup partner={partner} month={month} />
      <FreeBudgetGroup partner={partner} month={month} />
    </div>
  );
}

export function BudgetTab({
  month,
  isPast,
}: {
  month: MonthData;
  // month.key < current local YYYY-MM — gates BILLS's real-paid header
  // and the CC bill's real-vs-est row (current-month override sets
  // realCcBill too, but must render current-style — PR65 review).
  isPast: boolean;
}) {
  return (
    <div className="grid grid-cols-1 gap-3 rounded-lg border bg-card p-2 sm:grid-cols-2">
      {/* Column order by slot; legacy payloads fall back to label order. */}
      {byDisplayOrder(month.partners).map((p) => (
        <PartnerColumn
          key={p.partner.partner_id || p.partner.label}
          partner={p}
          month={month}
          isPast={isPast}
        />
      ))}
    </div>
  );
}
