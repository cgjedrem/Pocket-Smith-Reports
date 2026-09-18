// SavingsSection — shadcn Card + PartnerSplitTable + InvestmentTable +
// 2 TrendLineCharts (NOK cumulative + share %).
// Mirrors PDF section_savings.py.

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendLineChart } from "@/components/mega-reports/charts/TrendLineChart";
import {
  compactNOK,
  formatNOK,
  partnerLabel,
  sumArr,
} from "@/components/mega-reports/sections/helpers";
import { InvestmentTable, type InvestmentRow } from "@/components/mega-reports/sections/InvestmentTable";
import { PartnerSplitTable, type PartnerSplitRow } from "@/components/mega-reports/sections/PartnerSplitTable";
import type { MegaReportResponse } from "@/types/mega_report";

interface SavingsSectionProps {
  report: MegaReportResponse;
}

export function SavingsSection({ report }: SavingsSectionProps) {
  const { detail_agg: d } = report;
  const cum = d.cumulative;
  const months = d.months;
  const aLabel = partnerLabel(report, "partner_a");
  const bLabel = partnerLabel(report, "partner_b");

  // Savings series (already cumulative per-month totals in series.savings)
  // Keys are stable ids (partner_a / partner_b) — NOT display labels — so the
  // chart CSS-var generator (`--color-${key}`) always emits valid identifiers.
  const cumA = months.map((_, i) => sumArr(d.series.savings.net_partner_a.slice(0, i + 1)));
  const cumB = months.map((_, i) => sumArr(d.series.savings.net_partner_b.slice(0, i + 1)));
  const cumTotal = months.map((_, i) => sumArr(d.series.savings.total.slice(0, i + 1)));

  // Investment series
  const invA = d.series.savings.investment_net_partner_a ?? [];
  const invB = d.series.savings.investment_net_partner_b ?? [];
  const invT = d.series.savings.investment_net_total ?? [];
  const invCumA = cum.savings.investment_net_partner_a ?? 0;
  const invCumB = cum.savings.investment_net_partner_b ?? 0;
  const invCumT = cum.savings.investment_net_total ?? 0;

  const tableRows: PartnerSplitRow[] = months.map((m, i) => ({
    month: m.slice(2).replace("-", "/"),
    partnerA: d.series.savings.net_partner_a[i] ?? 0,
    partnerB: d.series.savings.net_partner_b[i] ?? 0,
    total: d.series.savings.total[i] ?? 0,
    cumulativeA: cumA[i],
    cumulativeB: cumB[i],
    cumulativeTotal: cumTotal[i],
  }));

  const investmentRows: InvestmentRow[] = months.map((m, i) => ({
    month: m.slice(2).replace("-", "/"),
    partnerA: invA[i] ?? 0,
    partnerB: invB[i] ?? 0,
    total: invT[i] ?? 0,
  }));

  // Share % (signed: A / (|A| + |B|))
  // Keys are stable ids — NOT label-derived — so the chart CSS-var generator
  // (`--color-${key}`) always emits valid identifiers regardless of label
  // content (spaces, '&', accents, etc.).
  const aPctKey = "partner_a_pct";
  const bPctKey = "partner_b_pct";
  const totalKey = "total";
  const shareRows = months.map((m, i) => {
    const a = d.series.savings.net_partner_a[i] ?? 0;
    const b = d.series.savings.net_partner_b[i] ?? 0;
    const absT = Math.abs(a) + Math.abs(b);
    return {
      month: m.slice(2).replace("-", "/"),
      [aPctKey]: absT ? (a / absT) * 100 : 0,
      [bPctKey]: absT ? (b / absT) * 100 : 0,
    };
  });

  // NOK cumulative chart rows
  const nokRows = months.map((m, i) => ({
    month: m.slice(2).replace("-", "/"),
    partner_a: cumA[i],
    partner_b: cumB[i],
    [totalKey]: cumTotal[i],
  }));

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">3. Savings</CardTitle>
        <p className="text-sm text-muted-foreground">
          Period net savings:{" "}
          <b>{formatNOK(cum.savings.total)} NOK</b> ({aLabel}{" "}
          {formatNOK(cum.savings.net_partner_a)} | {bLabel}{" "}
          {formatNOK(cum.savings.net_partner_b)})
        </p>
        <p className="text-sm text-muted-foreground">
          Investment net: <b>{formatNOK(invCumT)} NOK</b> ({aLabel}{" "}
          {formatNOK(invCumA)} | {bLabel} {formatNOK(invCumB)})
        </p>
        <p className="text-xs text-muted-foreground italic">
          Per-partner % = partner / sum of absolute partner values, sign follows
          own net. Total column = running cumulative. Δ MoM = current month
          total / prior cumulative.
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-foreground">
            Net savings per month (by partner)
          </h3>
          <PartnerSplitTable
            aLabel={aLabel}
            bLabel={bLabel}
            rows={tableRows}
            totalMode="cumulative"
            showShare="savings"
            footerLabel="Net"
          />
        </div>

        <div className="space-y-1">
          <h3
            id="investment-net-per-month"
            className="text-sm font-semibold text-foreground scroll-mt-20"
          >
            Investment net per month
          </h3>
          <InvestmentTable
            aLabel={aLabel}
            bLabel={bLabel}
            rows={investmentRows}
            footerLabel="Net"
          />
        </div>

        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-foreground">
            Monthly net savings (NOK) — Total is running cumulative
          </h3>
          <TrendLineChart
            rows={nokRows}
            seriesKeys={["partner_a", "partner_b", totalKey]}
            xKey="month"
            yFormatter={compactNOK}
            height={220}
            config={{
              partner_a: { label: aLabel, color: "hsl(189 78% 26%)" },
              partner_b: { label: bLabel, color: "hsl(14 64% 56%)" },
              [totalKey]: {
                label: "Total (cumulative)",
                color: "hsl(142 52% 36%)",
              },
            }}
          />
        </div>

        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-foreground">
            Net savings share by partner (%) — signed (matches table)
          </h3>
          <TrendLineChart
            rows={shareRows}
            seriesKeys={[aPctKey, bPctKey]}
            xKey="month"
            yFormatter={(v) => `${v.toFixed(0)}%`}
            height={200}
            config={{
              [aPctKey]: {
                label: `${aLabel} %`,
                color: "hsl(189 78% 26%)",
              },
              [bPctKey]: {
                label: `${bLabel} %`,
                color: "hsl(14 64% 56%)",
              },
            }}
          />
        </div>
      </CardContent>
    </Card>
  );
}
