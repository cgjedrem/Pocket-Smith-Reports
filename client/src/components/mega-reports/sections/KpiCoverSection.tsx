// KpiCoverSection — KPI grid + bar chart (full width) + 3 line charts in 1 row.

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { TrendBarLineChart } from "@/components/mega-reports/charts/TrendBarLineChart";
import { TrendLineChart } from "@/components/mega-reports/charts/TrendLineChart";
import { compactNOK, formatNOK, partnerLabel, sumArr } from "@/components/mega-reports/sections/helpers";
import type { MegaReportResponse, SplitSection } from "@/types/mega_report";

import styles from "./KpiCoverSection.module.css";

interface KpiCoverSectionProps {
  report: MegaReportResponse;
}

function KpiCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-border bg-muted/30 p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-lg font-semibold tabular-nums">{formatNOK(value)}</div>
    </div>
  );
}

// Common-economy split summary — compact per-category breakdown + a totals
// row as the table's last row + the settlement headline ("X pays Y …")
// RESTORED (user request 2026-10-01) BELOW the totals row — totals row
// keeps the numeric who-owes-who signal, the sentence spells it out in
// words. Mirrors the backend twin restoration
// (build_mega.py::_render_split_summary), but keeps the original React
// wording ("{from} pays {to} {amount}") — NOT the backend's "owes"
// phrasing. Same DTO shape as monthly detailed.split, aggregated across
// the mega window (mega_builder.py, same compute_split() + label
// resolution).
interface SplitSummaryCardProps {
  splitSummary: SplitSection;
  aLabel: string;
  bLabel: string;
}

// b-side (actual_b/fair_b/delta_b) cell helper — null/undefined on stored
// CALCULATION_VERSION=9 rows persisted before the b-side columns existed
// (backend Optional[float] = None). Em-dash, never a fabricated 0 —
// same convention as the monthly DetailedSections.tsx split table.
function fmtBNOK(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : formatNOK(value);
}

// Totals-only float-dust snap: |v| < half-cent → 0, so a balanced split's
// delta total never prints a negative-zero. Data rows untouched. Twin of
// backend mega build_mega.py::_render_split_summary grand-totals table.
function snapDust(value: number): number {
  return Math.abs(value) < 0.005 ? 0 : value;
}

// Raw-sum one split column across every row. Any null/undefined
// contributor (stale stored v9 rows, b-side fields) → null → the totals
// cell renders em-dash, never a fabricated 0 (same convention as fmtBNOK).
function sumSplitColumn(
  rows: SplitSection["rows"],
  key: "actual" | "fair" | "delta" | "actual_b" | "fair_b" | "delta_b",
): number | null {
  let sum = 0;
  for (const row of rows) {
    const value = row[key];
    if (value === null || value === undefined) return null;
    sum += value;
  }
  return sum;
}

function SplitSummaryCard({ splitSummary, aLabel, bLabel }: SplitSummaryCardProps) {
  // Grand totals over the flat row list — summed raw, snapped, formatted
  // once with the same formatNOK formatter as the data rows. This table is
  // flat (no per-section grouping like the monthly table), so the totals
  // row lives in-table as the last tbody row.
  const totals = {
    actual: sumSplitColumn(splitSummary.rows, "actual"),
    fair: sumSplitColumn(splitSummary.rows, "fair"),
    delta: sumSplitColumn(splitSummary.rows, "delta"),
    actual_b: sumSplitColumn(splitSummary.rows, "actual_b"),
    fair_b: sumSplitColumn(splitSummary.rows, "fair_b"),
    delta_b: sumSplitColumn(splitSummary.rows, "delta_b"),
  };
  // Settlement sentence below the totals row — original React wording
  // ("{from} pays {to} {formatNOK(amount)}") and original headline
  // styling, restored verbatim from the pre-removal rendering. null =
  // balanced (rows present → original em-dash wording "—") or nothing
  // to settle (zero rows → render NOTHING; never fabricate a 0,00
  // transfer). Backend twin says "owes" / "NOK." — not mirrored.
  const settlement = splitSummary.settlement;
  const settlementText = settlement
    ? `${settlement.from_partner} pays ${settlement.to_partner} ${formatNOK(settlement.amount)}`
    : splitSummary.rows.length > 0
      ? "—"
      : null;
  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="text-sm font-medium">Common economy split</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {splitSummary.rows.length > 0 && (
          <>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="py-1 text-left">Category</th>
                  <th className="py-1 text-right">{aLabel} actual</th>
                  <th className="py-1 text-right">{aLabel} fair share</th>
                  <th className="py-1 text-right">{aLabel} delta</th>
                  <th className="py-1 text-right">{bLabel} actual</th>
                  <th className="py-1 text-right">{bLabel} fair share</th>
                  <th className="py-1 text-right">{bLabel} delta</th>
                </tr>
              </thead>
              <tbody>
                {splitSummary.rows.map((r) => (
                  <tr key={r.category_id} className="border-b border-border">
                    <td className="py-1">{r.label}</td>
                    <td className="py-1 text-right tabular-nums">{formatNOK(r.actual)}</td>
                    <td className="py-1 text-right tabular-nums">{formatNOK(r.fair)}</td>
                    <td className="py-1 text-right tabular-nums">{formatNOK(r.delta)}</td>
                    <td className="py-1 text-right tabular-nums">{fmtBNOK(r.actual_b)}</td>
                    <td className="py-1 text-right tabular-nums">{fmtBNOK(r.fair_b)}</td>
                    <td className="py-1 text-right tabular-nums">{fmtBNOK(r.delta_b)}</td>
                  </tr>
                ))}
                {/* Totals row — last tbody row; bold + top border (this
                    table has no prior totals-row idiom; plain tailwind
                    classes consistent with the existing row styling). */}
                <tr className="border-t-2 border-border font-semibold">
                  <td className="py-1">Total</td>
                  <td className="py-1 text-right tabular-nums">
                    {totals.actual === null ? "—" : formatNOK(snapDust(totals.actual))}
                  </td>
                  <td className="py-1 text-right tabular-nums">
                    {totals.fair === null ? "—" : formatNOK(snapDust(totals.fair))}
                  </td>
                  <td className="py-1 text-right tabular-nums">
                    {totals.delta === null ? "—" : formatNOK(snapDust(totals.delta))}
                  </td>
                  <td className="py-1 text-right tabular-nums">
                    {fmtBNOK(totals.actual_b === null ? null : snapDust(totals.actual_b))}
                  </td>
                  <td className="py-1 text-right tabular-nums">
                    {fmtBNOK(totals.fair_b === null ? null : snapDust(totals.fair_b))}
                  </td>
                  <td className="py-1 text-right tabular-nums">
                    {fmtBNOK(totals.delta_b === null ? null : snapDust(totals.delta_b))}
                  </td>
                </tr>
              </tbody>
            </table>
            {/* Rows are partner_a's perspective — shares sum to 100%, so
                partner_b's numbers are the exact complement (see backend
                compute_split() docstring). Spell that out so the {aLabel}
                columns don't read as "the only partner who split anything". */}
            <p className="text-xs text-muted-foreground">
              Actual/fair/delta shown from {aLabel}&apos;s perspective — a positive delta
              means {aLabel} paid more than their fair share (owed by {bLabel}); negative
              means the reverse.
            </p>
          </>
        )}
        {/* Settlement sentence — AFTER the table (below the totals row),
            same <p> headline styling as the removed pre-removal callout. */}
        {settlementText !== null && (
          <p className="text-sm font-semibold">{settlementText}</p>
        )}
      </CardContent>
    </Card>
  );
}

export function KpiCoverSection({ report }: KpiCoverSectionProps) {
  const { detail_agg: d, salary_allocation: sal } = report;
  const cum = d.cumulative;
  const months = d.months;
  const aLabel = partnerLabel(report, "partner_a");
  const bLabel = partnerLabel(report, "partner_b");

  const incomeTotal = cum.income.total;
  const realSpendTotal = cum.real_spend.total;
  const netCashTotal = cum.net_cash.total;
  const netSavingsTotal = cum.savings.total;
  const aIncome = cum.income.partner_a;
  const bIncome = cum.income.partner_b;

  // Income chart rows + cumulative.
  // Keys are stable ids (partner_a / partner_b) — NOT display labels — so the
  // chart CSS-var generator (`--color-${key}`) always emits valid identifiers.
  const incomeRows = months.map((m, i) => {
    let cumTotal = 0;
    for (let j = 0; j <= i; j++) cumTotal += d.series.income.total[j] ?? 0;
    return {
      month: m.slice(2).replace("-", "/"),
      partner_a: d.series.income.partner_a[i] ?? 0,
      partner_b: d.series.income.partner_b[i] ?? 0,
      Cumulative: cumTotal,
    };
  });

  // Real spend rows.
  const realSpendRows = months.map((m, i) => ({
    month: m.slice(2).replace("-", "/"),
    partner_a: d.series.real_spend.partner_a[i] ?? 0,
    partner_b: d.series.real_spend.partner_b[i] ?? 0,
    Household: d.series.real_spend.total[i] ?? 0,
  }));

  // Net cash rows.
  const netCashRows = months.map((m, i) => ({
    month: m.slice(2).replace("-", "/"),
    partner_a: d.series.net_cash.partner_a[i] ?? 0,
    partner_b: d.series.net_cash.partner_b[i] ?? 0,
    Household: d.series.net_cash.total[i] ?? 0,
  }));

  // Savings cumulative rows.
  const savingsRows = months.map((m, i) => ({
    month: m.slice(2).replace("-", "/"),
    Household: sumArr(d.series.savings.total.slice(0, i + 1)),
  }));

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">1. KPI Cover</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {/* KPI grid */}
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
          <KpiCard label="Income" value={incomeTotal} />
          <KpiCard label="Real spend" value={realSpendTotal} />
          <KpiCard label="Net cash" value={netCashTotal} />
          <KpiCard label="Net savings" value={netSavingsTotal} />
          <KpiCard label={`${aLabel} income`} value={aIncome} />
          <KpiCard label={`${bLabel} income`} value={bIncome} />
        </div>

        {/* Common-economy split summary — additive (mega calculation_version
            2; b-side columns in 3), aggregated across the window.
            Null/undefined -> feature off,
            no config, or a pre-field stored report; omit the whole block,
            never a fabricated em-dash placeholder (same convention as the
            monthly detailed.split renderer). */}
        {report.split_summary && (
          <SplitSummaryCard splitSummary={report.split_summary} aLabel={aLabel} bLabel={bLabel} />
        )}

        {/* Bar chart — full width */}
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-sm font-medium">Income (stacked) with cumulative line</CardTitle>
          </CardHeader>
          <CardContent>
            <TrendBarLineChart
              rows={incomeRows}
              barKeys={["partner_a", "partner_b"]}
              lineKeys={["Cumulative"]}
              xKey="month"
              yFormatter={compactNOK}
              config={{
                partner_a: { label: aLabel, color: "hsl(189 78% 26%)" },
                partner_b: { label: bLabel, color: "hsl(14 64% 56%)" },
                Cumulative: { label: "Cumulative", color: "hsl(142 52% 36%)" },
              }}
            />
          </CardContent>
        </Card>

        {/* 3 line charts in one row */}
        <div className={styles.threeCol}>
          <Card className="min-w-0">
            <CardHeader className="pb-1 px-4 pt-4">
              <CardTitle className="text-sm font-medium">Real spend</CardTitle>
            </CardHeader>
            <CardContent className="px-2 pb-2">
              <TrendLineChart
                rows={realSpendRows}
                seriesKeys={["partner_a", "partner_b", "Household"]}
                xKey="month"
                yFormatter={compactNOK}
                config={{
                  partner_a: { label: aLabel, color: "hsl(189 78% 26%)" },
                  partner_b: { label: bLabel, color: "hsl(14 64% 56%)" },
                  Household: { label: "Household", color: "hsl(142 52% 36%)" },
                }}
              />
            </CardContent>
          </Card>

          <Card className="min-w-0">
            <CardHeader className="pb-1 px-4 pt-4">
              <CardTitle className="text-sm font-medium">Net cash</CardTitle>
            </CardHeader>
            <CardContent className="px-2 pb-2">
              <TrendLineChart
                rows={netCashRows}
                seriesKeys={["partner_a", "partner_b", "Household"]}
                xKey="month"
                yFormatter={compactNOK}
                config={{
                  partner_a: { label: aLabel, color: "hsl(189 78% 26%)" },
                  partner_b: { label: bLabel, color: "hsl(14 64% 56%)" },
                  Household: { label: "Household", color: "hsl(142 52% 36%)" },
                }}
              />
            </CardContent>
          </Card>

          <Card className="min-w-0">
            <CardHeader className="pb-1 px-4 pt-4">
              <CardTitle className="text-sm font-medium">Savings cumulative</CardTitle>
            </CardHeader>
            <CardContent className="px-2 pb-2">
              <TrendLineChart
                rows={savingsRows}
                seriesKeys={["Household"]}
                xKey="month"
                yFormatter={compactNOK}
                config={{
                  Household: { label: "Household", color: "hsl(142 52% 36%)" },
                }}
              />
            </CardContent>
          </Card>
        </div>

        {/* Salary allocation table — mirrors PDF _render_salary_allocation.
            Anchored by id="salary-allocation" + scroll-mt-20 for nav linking. */}
        <div className="pt-4 border-t border-border/40">
          <h3
            id="salary-allocation"
            className="mb-2 text-sm font-semibold text-foreground scroll-mt-20"
          >
            Salary allocation
          </h3>
          {sal.unavailable_reason ? (
            <p className="text-sm text-muted-foreground">{sal.unavailable_reason}</p>
          ) : sal.income <= 0 ? (
            <p className="text-sm text-muted-foreground">
              Income is 0 — percentages unavailable.
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="py-1 text-left">Allocation</th>
                  <th className="py-1 text-right">Amount</th>
                  <th className="py-1 text-right">Percent of income</th>
                </tr>
              </thead>
              <tbody>
                {sal.entries.map((e) => (
                  <tr key={e.id} className="border-b border-border">
                    <td className="py-1">{e.title}</td>
                    <td className="py-1 text-right tabular-nums">{formatNOK(e.amount)}</td>
                    <td className="py-1 text-right tabular-nums">
                      {sal.income ? `${((e.amount / sal.income) * 100).toFixed(1)}%` : "—"}
                    </td>
                  </tr>
                ))}
                {(() => {
                  const allocated = sal.entries.reduce((s, e) => s + (e.amount ?? 0), 0);
                  const remaining = sal.income - allocated;
                  const remainingLabel =
                    remaining >= 0
                      ? "Remaining income after listed allocations"
                      : "Listed allocations exceed income";
                  return (
                    <>
                      <tr className="border-b border-border bg-muted/50">
                        <td className="py-1 font-semibold">Listed allocations</td>
                        <td className="py-1 text-right tabular-nums font-semibold">
                          {formatNOK(allocated)}
                        </td>
                        <td className="py-1 text-right tabular-nums font-semibold">
                          {sal.income ? `${((allocated / sal.income) * 100).toFixed(1)}%` : "—"}
                        </td>
                      </tr>
                      <tr className="border-b border-border bg-muted/50">
                        <td className="py-1 font-semibold">{remainingLabel}</td>
                        <td className="py-1 text-right tabular-nums font-semibold">
                          {formatNOK(Math.abs(remaining))}
                        </td>
                        <td className="py-1 text-right tabular-nums font-semibold">
                          {sal.income
                            ? `${((Math.abs(remaining) / sal.income) * 100).toFixed(1)}%`
                            : "—"}
                        </td>
                      </tr>
                    </>
                  );
                })()}
              </tbody>
            </table>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
