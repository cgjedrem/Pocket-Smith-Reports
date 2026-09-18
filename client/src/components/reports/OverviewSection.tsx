// Overview section — header only (Monthly Report + month).

import type { ReportResponse } from "@/types/report";

interface OverviewSectionProps {
  report: ReportResponse;
}

export function OverviewSection({ report }: OverviewSectionProps) {
  return (
    <div className="overview-page">
      <header>
        <h1>Monthly Report</h1>
        <p className="period">{report.month}</p>
      </header>
    </div>
  );
}