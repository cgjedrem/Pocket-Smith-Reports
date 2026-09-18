// IncomeSection — shadcn Card + Table + TrendBarLineChart.
// Mirrors PDF section_income.py: 7-col table, cumulative Total, KPI summary,
// per-bar % share. App-only enhancement: column visual grouping via
// colgroup tints + colored left borders per partner.

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TrendBarLineChart } from "@/components/mega-reports/charts/TrendBarLineChart";
import {
  compactNOK,
  formatNOK,
  partnerLabel,
} from "@/components/mega-reports/sections/helpers";
import type { MegaReportResponse } from "@/types/mega_report";

interface IncomeSectionProps {
  report: MegaReportResponse;
}

export function IncomeSection({ report }: IncomeSectionProps) {
  const { detail_agg: d } = report;
  const cum = d.cumulative;
  const months = d.months;
  const aLabel = partnerLabel(report, "partner_a");
  const bLabel = partnerLabel(report, "partner_b");

  const aSeries = d.series.income.partner_a;
  const bSeries = d.series.income.partner_b;
  const tSeries = d.series.income.total;
  const grandTotal = cum.income.total;
  const partnerA_pct = grandTotal ? (cum.income.partner_a / grandTotal) * 100 : 0;
  const partnerB_pct = grandTotal ? (cum.income.partner_b / grandTotal) * 100 : 0;

  // Chart rows with running cumulative (line series).
  // Keys are stable ids (partner_a / partner_b) — NOT display labels — so the
  // chart CSS-var generator (`--color-${key}`) always emits valid identifiers.
  const chartRows = months.map((m, i) => {
    let running = 0;
    for (let j = 0; j <= i; j++) running += tSeries[j] ?? 0;
    return {
      month: m.slice(2).replace("-", "/"),
      partner_a: aSeries[i] ?? 0,
      partner_b: bSeries[i] ?? 0,
      Cumulative: running,
    };
  });

  // Colgroup tint bands — partner A (teal), partner B (orange), total (neutral).
  // Using inline styles so it survives Tailwind v4 + shadcn Table reset.
  const aTint = "hsl(189 78% 26% / 0.06)";
  const bTint = "hsl(14 64% 56% / 0.06)";
  const tTint = "hsl(142 52% 36% / 0.05)";

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">2. Income</CardTitle>
        <p className="text-sm text-muted-foreground">
          Period total: <b>{formatNOK(grandTotal)} NOK</b> ({aLabel}{" "}
          {formatNOK(cum.income.partner_a)} = {partnerA_pct.toFixed(1)}% | {bLabel}{" "}
          {formatNOK(cum.income.partner_b)} = {partnerB_pct.toFixed(1)}%)
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="rounded-md border border-border overflow-hidden">
          <Table>
            <colgroup>
              <col style={{ width: "14%" }} />
              <col style={{ width: "13%", backgroundColor: aTint }} />
              <col style={{ width: "13%", backgroundColor: bTint }} />
              <col style={{ width: "15%", backgroundColor: tTint }} />
              <col style={{ width: "15%", backgroundColor: aTint }} />
              <col style={{ width: "15%", backgroundColor: bTint }} />
              <col style={{ width: "15%", backgroundColor: tTint }} />
            </colgroup>
            <TableHeader>
              <TableRow>
                <TableHead rowSpan={2} className="align-bottom border-r border-border">
                  Month
                </TableHead>
                <TableHead
                  colSpan={2}
                  className="text-center border-b border-r border-border"
                  style={{ borderBottomColor: "hsl(189 78% 26% / 0.35)" }}
                >
                  Per partner
                </TableHead>
                <TableHead
                  colSpan={1}
                  rowSpan={2}
                  className="text-right align-bottom border-r border-border"
                  style={{ borderRightColor: "hsl(142 52% 36% / 0.35)" }}
                >
                  Total
                </TableHead>
                <TableHead
                  colSpan={3}
                  className="text-center border-b border-border"
                  style={{ borderBottomColor: "hsl(262 52% 50% / 0.35)" }}
                >
                  Share
                </TableHead>
              </TableRow>
              <TableRow>
                <TableHead
                  className="text-right"
                  style={{ borderLeft: "2px solid hsl(189 78% 26% / 0.45)" }}
                >
                  {aLabel}
                </TableHead>
                <TableHead
                  className="text-right"
                  style={{
                    borderLeft: "1px solid hsl(14 64% 56% / 0.35)",
                    borderRight: "1px solid hsl(14 64% 56% / 0.35)",
                  }}
                >
                  {bLabel}
                </TableHead>
                <TableHead
                  className="text-right"
                  style={{ borderLeft: "2px solid hsl(189 78% 26% / 0.45)" }}
                >
                  {aLabel} %
                </TableHead>
                <TableHead
                  className="text-right"
                  style={{
                    borderLeft: "1px solid hsl(14 64% 56% / 0.35)",
                    borderRight: "1px solid hsl(14 64% 56% / 0.35)",
                  }}
                >
                  {bLabel} %
                </TableHead>
                <TableHead
                  className="text-right"
                  style={{ borderRight: "2px solid hsl(142 52% 36% / 0.45)" }}
                >
                  Total %
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(() => {
                let running = 0;
                return months.map((m, i) => {
                  const a = aSeries[i] ?? 0;
                  const b = bSeries[i] ?? 0;
                  const t = tSeries[i] ?? 0;
                  running += t;
                  const aPct = t ? (a / t) * 100 : 0;
                  const bPct = t ? (b / t) * 100 : 0;
                  const tPct = grandTotal ? (t / grandTotal) * 100 : 0;
                  return (
                    <TableRow
                      key={m}
                      className="hover:bg-muted/30 even:bg-muted/10"
                    >
                      <TableCell className="font-medium border-r border-border">
                        {m.slice(2).replace("-", "/")}
                      </TableCell>
                      <TableCell
                        className="text-right tabular-nums"
                        style={{ borderLeft: "2px solid hsl(189 78% 26% / 0.45)" }}
                      >
                        {formatNOK(a)}
                      </TableCell>
                      <TableCell
                        className="text-right tabular-nums"
                        style={{
                          borderLeft: "1px solid hsl(14 64% 56% / 0.35)",
                          borderRight: "1px solid hsl(14 64% 56% / 0.35)",
                        }}
                      >
                        {formatNOK(b)}
                      </TableCell>
                      <TableCell
                        className="text-right tabular-nums font-semibold"
                        style={{ borderRight: "1px solid hsl(142 52% 36% / 0.35)" }}
                      >
                        {formatNOK(running)}
                      </TableCell>
                      <TableCell
                        className="text-right tabular-nums"
                        style={{ borderLeft: "2px solid hsl(189 78% 26% / 0.45)" }}
                      >
                        {aPct.toFixed(1)}%
                      </TableCell>
                      <TableCell
                        className="text-right tabular-nums"
                        style={{
                          borderLeft: "1px solid hsl(14 64% 56% / 0.35)",
                          borderRight: "1px solid hsl(14 64% 56% / 0.35)",
                        }}
                      >
                        {bPct.toFixed(1)}%
                      </TableCell>
                      <TableCell
                        className="text-right tabular-nums"
                        style={{ borderRight: "2px solid hsl(142 52% 36% / 0.45)" }}
                      >
                        {tPct.toFixed(1)}%
                      </TableCell>
                    </TableRow>
                  );
                });
              })()}
              <TableRow className="font-semibold bg-muted/50 border-t-2 border-border">
                <TableCell className="border-r border-border">Period total</TableCell>
                <TableCell
                  className="text-right tabular-nums"
                  style={{ borderLeft: "2px solid hsl(189 78% 26% / 0.6)" }}
                >
                  {formatNOK(cum.income.partner_a)}
                </TableCell>
                <TableCell
                  className="text-right tabular-nums"
                  style={{
                    borderLeft: "1px solid hsl(14 64% 56% / 0.5)",
                    borderRight: "1px solid hsl(14 64% 56% / 0.5)",
                  }}
                >
                  {formatNOK(cum.income.partner_b)}
                </TableCell>
                <TableCell
                  className="text-right tabular-nums"
                  style={{ borderRight: "1px solid hsl(142 52% 36% / 0.5)" }}
                >
                  {formatNOK(grandTotal)}
                </TableCell>
                <TableCell
                  className="text-right tabular-nums"
                  style={{ borderLeft: "2px solid hsl(189 78% 26% / 0.6)" }}
                >
                  {partnerA_pct.toFixed(1)}%
                </TableCell>
                <TableCell
                  className="text-right tabular-nums"
                  style={{
                    borderLeft: "1px solid hsl(14 64% 56% / 0.5)",
                    borderRight: "1px solid hsl(14 64% 56% / 0.5)",
                  }}
                >
                  {partnerB_pct.toFixed(1)}%
                </TableCell>
                <TableCell
                  className="text-right tabular-nums"
                  style={{ borderRight: "2px solid hsl(142 52% 36% / 0.6)" }}
                >
                  100.0%
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        <TrendBarLineChart
          rows={chartRows}
          barKeys={["partner_a", "partner_b"]}
          lineKeys={["Cumulative"]}
          xKey="month"
          yFormatter={compactNOK}
          showPct
          config={{
            partner_a: { label: aLabel, color: "hsl(189 78% 26%)" },
            partner_b: { label: bLabel, color: "hsl(14 64% 56%)" },
            Cumulative: { label: "Cumulative", color: "hsl(142 52% 36%)" },
          }}
        />
      </CardContent>
    </Card>
  );
}
