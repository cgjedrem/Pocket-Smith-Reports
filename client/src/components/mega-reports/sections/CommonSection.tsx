// CommonSection — shadcn Card + PartnerSplitTable + TrendBarLineChart.
// Mirrors PDF section_common.py: Common = sum of "common"-section cats
// (partner_a_paid - partner_a_received) per partner, with running cumulative
// and per-month share %.

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendBarLineChart } from "@/components/mega-reports/charts/TrendBarLineChart";
import {
  compactNOK,
  formatNOK,
  partnerLabel,
  slugify,
  sumArr,
} from "@/components/mega-reports/sections/helpers";
import { PartnerSplitTable, type PartnerSplitRow } from "@/components/mega-reports/sections/PartnerSplitTable";
import type { CategoryAgg, MegaReportResponse } from "@/types/mega_report";

interface CommonSectionProps {
  report: MegaReportResponse;
}

export function CommonSection({ report }: CommonSectionProps) {
  const { detail_agg: d } = report;
  const months = d.months;
  const aLabel = partnerLabel(report, "partner_a");
  const bLabel = partnerLabel(report, "partner_b");

  // Common series — sum of cats where section === "common".
  // Per-month partner values: paid - received for that partner.
  // Per-month total: paid - received (sum across both partners).
  const commonCats: CategoryAgg[] = Object.values(d.cats).filter(
    (c) => c.section === "common",
  );

  const seriesPartnerA: number[] = months.map(
    (_, i) =>
      commonCats.reduce(
        (s, c) => s + ((c.partner_a_paid[i] ?? 0) - (c.partner_a_received[i] ?? 0)),
        0,
      ),
  );
  const seriesPartnerB: number[] = months.map(
    (_, i) =>
      commonCats.reduce(
        (s, c) => s + ((c.partner_b_paid[i] ?? 0) - (c.partner_b_received[i] ?? 0)),
        0,
      ),
  );
  // Monthly net = partnerA + partnerB (paired reimbs already moved between partners).
  const seriesTotal: number[] = months.map(
    (_, i) => seriesPartnerA[i] + seriesPartnerB[i],
  );

  const cumA = months.map((_, i) => sumArr(seriesPartnerA.slice(0, i + 1)));
  const cumB = months.map((_, i) => sumArr(seriesPartnerB.slice(0, i + 1)));
  const cumTotal = months.map((_, i) => sumArr(seriesTotal.slice(0, i + 1)));

  const grandTotal = sumArr(seriesTotal);
  const grandPartnerA = sumArr(seriesPartnerA);
  const grandPartnerB = sumArr(seriesPartnerB);

  const tableRows: PartnerSplitRow[] = months.map((m, i) => ({
    month: m.slice(2).replace("-", "/"),
    partnerA: seriesPartnerA[i],
    partnerB: seriesPartnerB[i],
    total: seriesTotal[i],
    cumulativeA: cumA[i],
    cumulativeB: cumB[i],
    cumulativeTotal: cumTotal[i],
  }));

  const chartRows = months.map((m, i) => ({
    month: m.slice(2).replace("-", "/"),
    [aLabel]: seriesPartnerA[i],
    [bLabel]: seriesPartnerB[i],
    Cumulative: cumTotal[i],
  }));

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">5. Common</CardTitle>
        <p className="text-sm text-muted-foreground">
          Period total: <b>{formatNOK(grandTotal)} NOK</b> ({aLabel}{" "}
          {formatNOK(grandPartnerA)} | {bLabel} {formatNOK(grandPartnerB)})
        </p>
        <p className="text-xs text-muted-foreground italic">
          Per-partner % = partner / monthly net (paired reimbs already moved).
          Total % = month / period total.
        </p>
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

        <TrendBarLineChart
          rows={chartRows}
          barKeys={[aLabel, bLabel]}
          lineKeys={["Cumulative"]}
          xKey="month"
          yFormatter={compactNOK}
          showPct
          config={{
            [aLabel]: { label: aLabel, color: "hsl(189 78% 26%)" },
            [bLabel]: { label: bLabel, color: "hsl(14 64% 56%)" },
            Cumulative: { label: "Cumulative", color: "hsl(142 52% 36%)" },
          }}
        />

        {/* Sub-categories — sorted by total spend desc, skip empty + reimbs. */}
        {commonCats
          .filter(
            (c) =>
              !c.is_reimbursement &&
              (c.total.some((v) => v) ||
                c.partner_a_paid.some((v) => v) ||
                c.partner_b_paid.some((v) => v)),
          )
          .sort((a, b) => sumArr(b.total) - sumArr(a.total))
          .map((c, idx) => {
            const catPartnerA = months.map(
              (_, i) =>
                (c.partner_a_paid[i] ?? 0) - (c.partner_a_received[i] ?? 0),
            );
            const catPartnerB = months.map(
              (_, i) =>
                (c.partner_b_paid[i] ?? 0) - (c.partner_b_received[i] ?? 0),
            );
            const catTotal = c.total;
            const catCumA = months.map((_, i) => sumArr(catPartnerA.slice(0, i + 1)));
            const catCumB = months.map((_, i) => sumArr(catPartnerB.slice(0, i + 1)));
            const catCumT = months.map((_, i) => sumArr(catTotal.slice(0, i + 1)));
            const catRows: PartnerSplitRow[] = months.map((m, i) => ({
              month: m.slice(2).replace("-", "/"),
              partnerA: catPartnerA[i],
              partnerB: catPartnerB[i],
              total: catTotal[i] ?? 0,
              cumulativeA: catCumA[i],
              cumulativeB: catCumB[i],
              cumulativeTotal: catCumT[i],
            }));
            const catChartRows = months.map((m, i) => ({
              month: m.slice(2).replace("-", "/"),
              [aLabel]: catPartnerA[i],
              [bLabel]: catPartnerB[i],
              Cumulative: catCumT[i],
            }));
            return (
              <div
                key={c.title}
                className="space-y-3 pt-4 border-t border-border/40"
              >
                <h3
                  id={`common-subcat-${slugify(c.title)}`}
                  className="text-sm font-semibold text-foreground scroll-mt-20"
                >
                  {c.title} per month (by partner)
                </h3>
                <PartnerSplitTable
                  aLabel={aLabel}
                  bLabel={bLabel}
                  rows={catRows}
                  showCumulative
                  showShare="home"
                  footerLabel="Period total"
                />
                <TrendBarLineChart
                  rows={catChartRows}
                  barKeys={[aLabel, bLabel]}
                  lineKeys={["Cumulative"]}
                  xKey="month"
                  yFormatter={compactNOK}
                  showPct
                  height={200}
                  config={{
                    [aLabel]: { label: aLabel, color: "hsl(189 78% 26%)" },
                    [bLabel]: { label: bLabel, color: "hsl(14 64% 56%)" },
                    Cumulative: {
                      label: "Cumulative",
                      color: "hsl(142 52% 36%)",
                    },
                  }}
                />
              </div>
            );
          })}
      </CardContent>
    </Card>
  );
}
