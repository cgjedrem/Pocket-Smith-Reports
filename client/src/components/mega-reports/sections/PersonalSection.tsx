// PersonalSection — shadcn Card + PersonalTable + 2 charts + per-subcat tables.
// Mirrors PDF section_personal.py for one partner (A or B, labels from
// report.partner_labels — never hardcoded).

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendLineChart } from "@/components/mega-reports/charts/TrendLineChart";
import { SubcatPeriodPie } from "@/components/mega-reports/sections/SubcatPeriodPie";
import { PersonalTable, type PersonalRow } from "@/components/mega-reports/sections/PersonalTable";
import {
  compactNOK,
  formatNOK,
  partnerLabel,
  slugify,
  sumArr,
} from "@/components/mega-reports/sections/helpers";
import type { CategoryAgg, MegaReportResponse } from "@/types/mega_report";

interface PersonalSectionProps {
  report: MegaReportResponse;
  partner: "partner_a" | "partner_b";
}

const SECTION_KEY = {
  partner_a: "personal_partner_a",
  partner_b: "personal_partner_b",
} as const;

const SECTION_NUM = {
  partner_a: 6,
  partner_b: 7,
} as const;

export function PersonalSection({ report, partner }: PersonalSectionProps) {
  const { detail_agg: d } = report;
  const months = d.months;
  const ownerLabel = partnerLabel(report, partner);
  const normalized = SECTION_KEY[partner];
  const sectionNumber = SECTION_NUM[partner];
  // Title from configured partner label — no hardcoded names.
  const sectionTitle = `Personal ${ownerLabel}`;

  // Personal cats for this owner
  const personalCats: CategoryAgg[] = Object.values(d.cats).filter(
    (c) => c.section === normalized,
  );

  // Per-month owner values: paid - received for the owner.
  // The other partner is always 0 for personal sections.
  const ownerValues: number[] = months.map((_, i) =>
    personalCats.reduce(
      (s, c) =>
        s +
        ((partner === "partner_a"
          ? (c.partner_a_paid[i] ?? 0) - (c.partner_a_received[i] ?? 0)
          : (c.partner_b_paid[i] ?? 0) - (c.partner_b_received[i] ?? 0))),
      0,
    ),
  );

  // Per-month section total (same as ownerValues, since other partner is 0)
  const totalValues: number[] = ownerValues;
  const grandTotal = sumArr(totalValues);
  const ownerNet = sumArr(ownerValues);

  // Per-month household (real_spend) for the "owner % of total spend" col
  const householdTotal: number[] = d.series.real_spend.total;

  // Build table rows
  let runningTotal = 0;
  const tableRows: PersonalRow[] = months.map((m, i) => {
    const ownerVal = ownerValues[i];
    const t = totalValues[i];
    runningTotal += t;
    const ownerPct =
      householdTotal[i] && householdTotal[i] !== 0
        ? (ownerVal / householdTotal[i]) * 100
        : 0;
    const totalPct = grandTotal ? (t / grandTotal) * 100 : 0;
    return {
      month: m.slice(2).replace("-", "/"),
      ownerValue: ownerVal,
      runningTotal,
      ownerPctOfHousehold: ownerPct,
      totalPctOfPeriod: totalPct,
    };
  });

  // Owner % of total household spend for the period
  const hhPeriod = sumArr(householdTotal);
  const ownerPctOfHouseholdPeriod =
    hhPeriod && ownerNet ? (ownerNet / hhPeriod) * 100 : null;

  // Chart 1: NOK line (cumulative)
  const nokRows = months.map((m, i) => ({
    month: m.slice(2).replace("-", "/"),
    [ownerLabel]: ownerValues[i],
    "Running total": tableRows[i].runningTotal,
  }));

  // Chart 2: Sub-category period pie
  // For each non-empty non-reimb cat: amount = paid - received (owner only)
  const subcatAmounts: Array<{ name: string; value: number }> = personalCats
    .filter((c) => !c.is_reimbursement)
    .map((c) => {
      const vals = months.map(
        (_, i) =>
          (partner === "partner_a"
            ? (c.partner_a_paid[i] ?? 0) - (c.partner_a_received[i] ?? 0)
            : (c.partner_b_paid[i] ?? 0) - (c.partner_b_received[i] ?? 0)),
      );
      return { name: c.title, value: sumArr(vals) };
    })
    .filter((d) => d.value > 0)
    .sort((a, b) => b.value - a.value);

  // Per-subcat tables (using same PersonalTable shape, 1 owner)
  const subcatBlocks = personalCats
    .filter((c) => !c.is_reimbursement)
    .filter((c) => {
      const vals = months.map(
        (_, i) =>
          (partner === "partner_a"
            ? (c.partner_a_paid[i] ?? 0) - (c.partner_a_received[i] ?? 0)
            : (c.partner_b_paid[i] ?? 0) - (c.partner_b_received[i] ?? 0)),
      );
      return vals.some((v) => v !== 0);
    })
    .map((c, idx) => {
      const catOwnerVals = months.map(
        (_, i) =>
          (partner === "partner_a"
            ? (c.partner_a_paid[i] ?? 0) - (c.partner_a_received[i] ?? 0)
            : (c.partner_b_paid[i] ?? 0) - (c.partner_b_received[i] ?? 0)),
      );
      const catTotal = sumArr(catOwnerVals);
      let catRunning = 0;
      const catRows: PersonalRow[] = months.map((m, i) => {
        catRunning += catOwnerVals[i];
        return {
          month: m.slice(2).replace("-", "/"),
          ownerValue: catOwnerVals[i],
          runningTotal: catRunning,
          ownerPctOfHousehold:
            householdTotal[i] && householdTotal[i] !== 0
              ? (catOwnerVals[i] / householdTotal[i]) * 100
              : 0,
          totalPctOfPeriod: catTotal ? (catOwnerVals[i] / catTotal) * 100 : 0,
        };
      });
      const catHhPct = hhPeriod && catTotal ? (catTotal / hhPeriod) * 100 : null;
      return (
        <div
          key={c.title}
          className="space-y-2 pt-4 border-t border-border/40"
        >
          <h3
            id={`personal-subcat-${partner === "partner_a" ? "partner-a" : "partner-b"}-${slugify(c.title)}-${idx}`}
            className="text-sm font-semibold text-foreground scroll-mt-20"
          >
            {c.title} per month ({ownerLabel} only)
          </h3>
          <PersonalTable
            ownerLabel={ownerLabel}
            rows={catRows}
            grandTotal={catTotal}
            ownerNet={catTotal}
            ownerPctOfHouseholdPeriod={catHhPct}
          />
        </div>
      );
    });

  if (grandTotal === 0) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">
            {sectionNumber}. {sectionTitle}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No data for this section.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">
          {sectionNumber}. {sectionTitle}
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          Period total: <b>{formatNOK(grandTotal)} NOK</b> ({ownerLabel} paid{" "}
          {formatNOK(ownerNet)})
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <PersonalTable
          ownerLabel={ownerLabel}
          rows={tableRows}
          grandTotal={grandTotal}
          ownerNet={ownerNet}
          ownerPctOfHouseholdPeriod={ownerPctOfHouseholdPeriod}
        />

        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-foreground">
            Monthly {ownerLabel} personal spend (NOK) — Total is running cumulative
          </h3>
          <TrendLineChart
            rows={nokRows}
            seriesKeys={[ownerLabel, "Running total"]}
            xKey="month"
            yFormatter={compactNOK}
            height={220}
            config={{
              [ownerLabel]: {
                label: ownerLabel,
                color: "hsl(189 78% 26%)",
              },
              "Running total": {
                label: "Running total",
                color: "hsl(142 52% 36%)",
              },
            }}
          />
        </div>

        {subcatAmounts.length > 0 && (
          <SubcatPeriodPie
            data={subcatAmounts}
            title={`${ownerLabel} sub-category % of personal period total`}
          />
        )}

        {subcatBlocks}
      </CardContent>
    </Card>
  );
}
