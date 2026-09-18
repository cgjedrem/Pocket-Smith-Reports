// GeneratedReportsList — shadcn ButtonGroup of buttons (single-select visual state).
// Carousel: pages of PAGE_SIZE buttons, prev/next arrows scroll through.

import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ButtonGroup } from "@/components/ui/button-group";
import { cn } from "@/lib/utils";
import type { MegaReportRange } from "@/types/mega_report";

interface GeneratedReportsListProps {
  reports: MegaReportRange[];
  value: string | null; // "{start}_{end}"
  onChange: (start: string, end: string) => void;
}

const PAGE_SIZE = 8;

function rangeKey(r: MegaReportRange): string {
  return `${r.start}_${r.end}`;
}

export function GeneratedReportsList({ reports, value, onChange }: GeneratedReportsListProps) {
  const [page, setPage] = useState(0);

  const totalPages = Math.max(1, Math.ceil(reports.length / PAGE_SIZE));

  // Clamp page when reports shrink (e.g. report deleted).
  useEffect(() => {
    if (page > totalPages - 1) setPage(totalPages - 1);
  }, [page, totalPages]);

  // Reports already come newest-first from the API; slice current page.
  const pageReports = useMemo(() => {
    const start = page * PAGE_SIZE;
    return reports.slice(start, start + PAGE_SIZE);
  }, [reports, page]);

  if (reports.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No reports generated yet.</p>
    );
  }

  const canPrev = page > 0;
  const canNext = page < totalPages - 1;

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="icon-sm"
          onClick={() => setPage((p) => Math.max(0, p - 1))}
          disabled={!canPrev}
          aria-label="Previous reports page"
        >
          <ChevronLeft />
        </Button>

        <ButtonGroup
          orientation="horizontal"
          aria-label="Generated mega reports"
          className="flex-wrap"
        >
          {pageReports.map((r) => {
            const key = rangeKey(r);
            const isActive = value === key;
            return (
              <Button
                key={key}
                type="button"
                variant={isActive ? "default" : "outline"}
                size="sm"
                onClick={() => onChange(r.start, r.end)}
                aria-pressed={isActive}
                className={cn("font-mono text-xs")}
              >
                {r.start} → {r.end}
              </Button>
            );
          })}
        </ButtonGroup>

        <Button
          type="button"
          variant="outline"
          size="icon-sm"
          onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
          disabled={!canNext}
          aria-label="Next reports page"
        >
          <ChevronRight />
        </Button>
      </div>

      <p className="text-xs text-muted-foreground" aria-live="polite">
        {reports.length === 0
          ? "0 reports"
          : `Showing ${page * PAGE_SIZE + 1}–${Math.min((page + 1) * PAGE_SIZE, reports.length)} of ${reports.length} · Page ${page + 1}/${totalPages}`}
      </p>
    </div>
  );
}
