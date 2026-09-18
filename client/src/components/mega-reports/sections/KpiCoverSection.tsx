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
import type { MegaReportResponse } from "@/types/mega_report";

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
