// ExcludedSection — per-month grouping of excluded transactions.
// Mirrors PDF section_excluded.render: h3 per month + table + month subtotal row.
// Columns: date, description, category, owner, amount.
//
// Visual parity with other sections: shadcn Table primitives (FE-M1),
// scroll-mt-20 on month headings (FE-L2), max-w truncate on description
// for PDF pagination safety (FE-H2), t.id key fallback (FE-H1).

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatNOK, partnerLabel, slugify } from "@/components/mega-reports/sections/helpers";
import type { ExcludedTransaction, MegaReportResponse } from "@/types/mega_report";

interface ExcludedSectionProps {
  report: MegaReportResponse;
}

// Map owner key → display label.
function ownerLabel(report: MegaReportResponse, owner: string): string {
  if (owner === "partner_a" || owner === "partner_b") return partnerLabel(report, owner);
  return owner;
}

export function ExcludedSection({ report }: ExcludedSectionProps) {
  const excluded = report.detail_agg.excluded_transactions;
  // Use months in detail_agg ordering (chronological) to match PDF.
  const months = report.detail_agg.months.filter((m) =>
    (excluded[m] ?? []).length > 0
  );
  const totalCount = months.reduce((sum, m) => sum + (excluded[m]?.length ?? 0), 0);

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold">12. Excluded categories</h2>

      {totalCount === 0 ? (
        <p className="text-sm text-muted-foreground">No excluded transactions.</p>
      ) : (
        months.map((month) => {
          const txns = excluded[month] ?? [];
          const subtotal = txns.reduce((s, t) => s + (t.amount ?? 0), 0);
          const monthId = `excluded-month-${slugify(month)}`;
          return (
            <div key={month} className="flex flex-col gap-2">
              <h3
                id={monthId}
                className="text-sm font-semibold text-foreground scroll-mt-20"
              >
                {month}
              </h3>
              <div className="rounded-md border border-border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow className="border-b border-border">
                      <TableHead className="py-1 text-left">Date</TableHead>
                      <TableHead className="py-1 text-left">Description</TableHead>
                      <TableHead className="py-1 text-left">Category</TableHead>
                      <TableHead className="py-1 text-left">Owner</TableHead>
                      <TableHead className="py-1 text-right">Amount</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {txns.map((t: ExcludedTransaction, i) => (
                      <TableRow key={t.id ?? `${month}-${i}`} className="border-b border-border">
                        <TableCell className="py-1">{t.date}</TableCell>
                        <TableCell
                          className="py-1 max-w-[420px] truncate"
                          title={t.description}
                        >
                          {t.description}
                        </TableCell>
                        <TableCell className="py-1">{t.category}</TableCell>
                        <TableCell className="py-1">{ownerLabel(report, t.owner)}</TableCell>
                        <TableCell className="py-1 text-right tabular-nums">
                          {formatNOK(t.amount)}
                        </TableCell>
                      </TableRow>
                    ))}
                    <TableRow className="border-b border-border bg-muted/50">
                      <TableCell colSpan={4} className="py-1 font-semibold">
                        Month subtotal
                      </TableCell>
                      <TableCell className="py-1 text-right tabular-nums font-semibold">
                        {formatNOK(subtotal)}
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}