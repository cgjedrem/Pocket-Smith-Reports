// MonthliesSection — per-month KPI cards from report.monthly_kpi_pages.
// For each month: income, real spend, net cash, net savings per partner + household.

import { formatNOK, partnerLabel } from "@/components/mega-reports/sections/helpers";
import type { MegaReportResponse, MonthlyKpiPartner } from "@/types/mega_report";

interface MonthliesSectionProps {
  report: MegaReportResponse;
}

function KpiRow({ label, kpis }: { label: string; kpis: MonthlyKpiPartner }) {
  return (
    <tr className="border-b border-border">
      <td className="py-1">{label}</td>
      <td className="py-1 text-right">{formatNOK(kpis.income)}</td>
      <td className="py-1 text-right">{formatNOK(kpis.real_spend)}</td>
      <td className="py-1 text-right">{formatNOK(kpis.net_cash)}</td>
      <td className="py-1 text-right">{formatNOK(kpis.net_savings)}</td>
      <td className="py-1 text-right">{formatNOK(kpis.investment ?? 0)}</td>
    </tr>
  );
}

export function MonthliesSection({ report }: MonthliesSectionProps) {
  const pages = report.monthly_kpi_pages;
  const aLabel = partnerLabel(report, "partner_a");
  const bLabel = partnerLabel(report, "partner_b");

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold">10. Monthly Reports</h2>

      {pages.length === 0 ? (
        <p className="text-sm text-muted-foreground">No monthly KPI pages.</p>
      ) : (
        <div className="flex flex-col gap-4">
          {pages.map((page) => (
            <div key={page.month} className="rounded-md border border-border bg-muted/30 p-3">
              <h3 className="mb-2 font-semibold">{page.month}</h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left">
                    <th className="py-1">Partner</th>
                    <th className="py-1 text-right">Income</th>
                    <th className="py-1 text-right">Real spend</th>
                    <th className="py-1 text-right">Net cash</th>
                    <th className="py-1 text-right">Net savings</th>
                    <th className="py-1 text-right">Investment</th>
                  </tr>
                </thead>
                <tbody>
                  <KpiRow label={aLabel} kpis={page.kpis.partner_a} />
                  <KpiRow label={bLabel} kpis={page.kpis.partner_b} />
                  <KpiRow label="Household" kpis={page.kpis.total} />
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}