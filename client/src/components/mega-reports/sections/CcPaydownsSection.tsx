// CcPaydownsSection — shadcn Card + 3 sub-blocks matching PDF:
//   1. CC paydowns overview — 5-col table per card.
//   2. CC paydowns by card with cumulative total — stacked bar + cumulative line.
//   3. CC paydowns per month (per card, NOK) — matrix table card x month.

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
} from "@/components/mega-reports/sections/helpers";
import type { MegaReportResponse } from "@/types/mega_report";
import type { ChartConfig } from "@/components/ui/chart";

interface CcPaydownsSectionProps {
  report: MegaReportResponse;
}

interface CardRow {
  card: string;
  monthsWithPaydown: number;
  total: number;
  avgPerMonth: number;
}

export function CcPaydownsSection({ report }: CcPaydownsSectionProps) {
  const ccPaydowns = report.detail_agg.cc_paydowns;

  // Sorted cards (by total desc) drive row order everywhere.
  const rows: CardRow[] = Object.entries(ccPaydowns)
    .map(([card, byMonth]) => {
      const values = Object.values(byMonth);
      const total = values.reduce((a, v) => a + v, 0);
      const monthsWithPaydown = values.filter((v) => v > 0).length;
      const avgPerMonth = monthsWithPaydown > 0 ? total / monthsWithPaydown : 0;
      return { card, monthsWithPaydown, total, avgPerMonth };
    })
    .sort((a, b) => b.total - a.total);

  // Union of months across cards, sorted.
  const monthSet = new Set<string>();
  for (const byMonth of Object.values(ccPaydowns)) {
    for (const m of Object.keys(byMonth)) monthSet.add(m);
  }
  const months = Array.from(monthSet).sort();
  const monthCount = months.length;
  const grandTotal = rows.reduce((s, r) => s + r.total, 0);

  // Chart config — one color per card (teal/orange/violet/amber).
  // Cumulative line uses green (hsl(142 52% 36%)).
  const cardColors = [
    "hsl(189 78% 26%)",
    "hsl(14 64% 56%)",
    "hsl(262 52% 50%)",
    "hsl(33 90% 50%)",
  ];
  const chartConfig: ChartConfig = {};
  const chartBarKeys: string[] = [];
  rows.forEach((r, i) => {
    const key = `card_${i}`;
    chartBarKeys.push(key);
    chartConfig[key] = {
      label: r.card,
      color: cardColors[i % cardColors.length],
    };
  });
  chartConfig.cumulative = {
    label: "Cumulative CC paydowns (right axis)",
    color: "hsl(142 52% 36%)",
  };

  // Build chart rows: { month, card_0, card_1, ..., cumulative }
  let runningCum = 0;
  const chartRows: Array<Record<string, number | string>> = months.map((m) => {
    const r: Record<string, number | string> = { month: m };
    let monthTotal = 0;
    rows.forEach((row, i) => {
      const v = ccPaydowns[row.card]?.[m] ?? 0;
      r[`card_${i}`] = v;
      monthTotal += v;
    });
    runningCum += monthTotal;
    r.cumulative = runningCum;
    return r;
  });

  if (rows.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">10. Credit-card paydowns</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No CC paydowns in this range.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">10. Credit-card paydowns</CardTitle>
        <p className="text-sm font-semibold text-foreground">CC paydowns overview</p>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        {/* Block 1: per-card overview */}
        <div className="rounded-md border border-border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>CC card</TableHead>
                <TableHead className="text-right">Months with paydown</TableHead>
                <TableHead className="text-right">Total paydown</TableHead>
                <TableHead className="text-right">Avg / month</TableHead>
                <TableHead className="text-right">% of all paydowns</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => {
                const pct = grandTotal > 0 ? (r.total / grandTotal) * 100 : 0;
                return (
                  <TableRow
                    key={r.card}
                    className="hover:bg-muted/30 even:bg-muted/10"
                  >
                    <TableCell className="font-medium">{r.card}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {r.monthsWithPaydown}
                    </TableCell>
                    <TableCell className="text-right tabular-nums font-semibold">
                      {formatNOK(r.total)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatNOK(r.avgPerMonth)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {pct.toFixed(1)}%
                    </TableCell>
                  </TableRow>
                );
              })}
              <TableRow className="font-semibold bg-muted/50 border-t-2 border-border">
                <TableCell>Total</TableCell>
                <TableCell />
                <TableCell className="text-right tabular-nums">
                  {formatNOK(grandTotal)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatNOK(monthCount > 0 ? grandTotal / monthCount : 0)}
                </TableCell>
                <TableCell className="text-right tabular-nums">100.0%</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        {/* Block 2: stacked bar + cumulative line chart */}
        <div className="flex flex-col gap-2">
          <h3
            id="cc-paydowns-by-card"
            className="text-sm font-semibold text-foreground scroll-mt-20"
          >
            CC paydowns by card with cumulative total
          </h3>
          <TrendBarLineChart
            rows={chartRows}
            barKeys={chartBarKeys}
            lineKeys={["cumulative"]}
            config={chartConfig}
            xKey="month"
            yFormatter={(v) => compactNOK(v)}
            height={340}
          />
        </div>

        {/* Block 3: per-month matrix */}
        <div className="flex flex-col gap-2">
          <h3
            id="cc-paydowns-per-month"
            className="text-sm font-semibold text-foreground scroll-mt-20"
          >
            CC paydowns per month (per card, NOK)
          </h3>
          <div className="rounded-md border border-border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="sticky left-0 bg-card">CC card</TableHead>
                  {months.map((m) => (
                    <TableHead key={m} className="text-right">
                      {m}
                    </TableHead>
                  ))}
                  <TableHead className="text-right">Total</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow
                    key={r.card}
                    className="hover:bg-muted/30 even:bg-muted/10"
                  >
                    <TableCell className="font-medium sticky left-0 bg-card">
                      {r.card}
                    </TableCell>
                    {months.map((m) => {
                      const v = ccPaydowns[r.card]?.[m];
                      return (
                        <TableCell
                          key={m}
                          className="text-right tabular-nums"
                        >
                          {v !== undefined && v > 0
                            ? formatNOK(v)
                            : "—"}
                        </TableCell>
                      );
                    })}
                    <TableCell className="text-right tabular-nums font-semibold">
                      {formatNOK(r.total)}
                    </TableCell>
                  </TableRow>
                ))}
                <TableRow className="font-semibold bg-muted/50 border-t-2 border-border">
                  <TableCell className="sticky left-0 bg-muted/50">Total</TableCell>
                  {months.map((m) => {
                    const total = rows.reduce(
                      (s, r) => s + (ccPaydowns[r.card]?.[m] ?? 0),
                      0,
                    );
                    return (
                      <TableCell
                        key={m}
                        className="text-right tabular-nums"
                      >
                        {formatNOK(total)}
                      </TableCell>
                    );
                  })}
                  <TableCell className="text-right tabular-nums">
                    {formatNOK(grandTotal)}
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
