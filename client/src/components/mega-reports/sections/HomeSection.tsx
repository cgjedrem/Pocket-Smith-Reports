// HomeSection — shadcn Card + PartnerSplitTable + TrendLineChart.

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendLineChart } from "@/components/mega-reports/charts/TrendLineChart";
import { compactNOK, partnerLabel, sumArr } from "@/components/mega-reports/sections/helpers";
import { PartnerSplitTable, type PartnerSplitRow } from "@/components/mega-reports/sections/PartnerSplitTable";
import type { MegaReportResponse } from "@/types/mega_report";

interface HomeSectionProps {
  report: MegaReportResponse;
}

export function HomeSection({ report }: HomeSectionProps) {
  const { detail_agg: d } = report;
  const months = d.months;
  const aLabel = partnerLabel(report, "partner_a");
  const bLabel = partnerLabel(report, "partner_b");

  const cumA = months.map((_, i) => sumArr(d.series.real_spend.partner_a.slice(0, i + 1)));
  const cumB = months.map((_, i) => sumArr(d.series.real_spend.partner_b.slice(0, i + 1)));
  const cumTotal = months.map((_, i) => sumArr(d.series.real_spend.total.slice(0, i + 1)));

  const tableRows: PartnerSplitRow[] = months.map((m, i) => ({
    month: m.slice(2).replace("-", "/"),
    partnerA: d.series.real_spend.partner_a[i] ?? 0,
    partnerB: d.series.real_spend.partner_b[i] ?? 0,
    total: d.series.real_spend.total[i] ?? 0,
    cumulativeA: cumA[i],
    cumulativeB: cumB[i],
    cumulativeTotal: cumTotal[i],
  }));

  // Keys are stable ids (partner_a / partner_b) — NOT display labels — so the
  // chart CSS-var generator (`--color-${key}`) always emits valid identifiers.
  const chartRows = months.map((m, i) => ({
    month: m.slice(2).replace("-", "/"),
    partner_a: cumA[i],
    partner_b: cumB[i],
    Household: cumTotal[i],
  }));

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">4. Home</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <PartnerSplitTable
          aLabel={aLabel}
          bLabel={bLabel}
          rows={tableRows}
          showCumulative
          showShare="home"
          footerLabel="Period total"
        />

        <TrendLineChart
          rows={chartRows}
          seriesKeys={["partner_a", "partner_b", "Household"]}
          xKey="month"
          yFormatter={compactNOK}
          height={220}
          config={{
            partner_a: { label: aLabel, color: "hsl(189 78% 26%)" },
            partner_b: { label: bLabel, color: "hsl(14 64% 56%)" },
            Household: { label: "Household", color: "hsl(142 52% 36%)" },
          }}
        />
      </CardContent>
    </Card>
  );
}
