// Reconciliation section — source vs report, balanced indicator.
// Uses shared SCSS classes (.reconciliation-ok, .reconciliation-review).

import type { ReportResponse } from "@/types/report";
import { maskAmount } from "@/lib/privacy-store";

// Masked last-mile — privacy toggle swaps amounts for "****".
function fmt(value: number): string {
  return maskAmount(
    value.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }),
  );
}

interface ReconciliationSectionProps {
  report: ReportResponse;
}

export function ReconciliationSection({ report }: ReconciliationSectionProps) {
  const { reconciliation } = report;
  // Server-computed (reconciliation.difference === 0); fall back to local
  // compare only for reports persisted before this field existed.
  const balanced = report.balanced ?? reconciliation.difference === 0;

  return (
    <div>
      <h3>Reconciliation</h3>
      <table className="legacy-table">
        <thead>
          <tr>
            <th>Source total</th>
            <th>Report total</th>
            <th>Difference</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>{fmt(reconciliation.source)}</td>
            <td>{fmt(reconciliation.report)}</td>
            <td>{fmt(reconciliation.difference)}</td>
            <td>
              {balanced ? (
                <span className="reconciliation-ok">Balanced</span>
              ) : (
                <span className="reconciliation-review">Review needed</span>
              )}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
