// F2 — sortable / filterable / paginated table view of all events. Read-only.

import { useMemo, useState } from "react";
import { ArrowUpDown, ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { FinanceEvent } from "@/types/api";
import { cn } from "@/lib/utils";

import {
  byDisplayOrder,
  formatDate,
  formatKr,
  IDENTITY_NEUTRAL_HINT,
  isIdentityNeutral,
  partnerDotClass,
} from "./finance-data";
import { useBillsSourceSubscription } from "@/hooks/useBillsSourceSubscription";
import { getAllEvents } from "@/lib/bills-source";

type Row = FinanceEvent & { monthLabel: string };
type SortKey = "date" | "type" | "title" | "account" | "partner" | "amount";
type SortDir = "asc" | "desc";

const PAGE_SIZE = 50;

const columns: { key: SortKey; label: string; className?: string }[] = [
  { key: "date", label: "Date" },
  { key: "type", label: "Type" },
  { key: "title", label: "Title" },
  { key: "account", label: "Account" },
  { key: "partner", label: "Partner" },
  { key: "amount", label: "Amount", className: "text-right" },
];

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="font-medium text-muted-foreground">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-8 rounded-md border border-input bg-card px-2 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function TableView({
  onEventClick,
}: {
  onEventClick?: (eventId: string) => void;
} = {}) {
  const version = useBillsSourceSubscription();
  const allRows = useMemo<Row[]>(() => getAllEvents(), [version]);
  const months = useMemo(
    () => Array.from(new Set(allRows.map((r) => r.monthLabel))),
    [allRows],
  );
  // US4: identity-neutral when no row carries a semantic partner id
  // (legacy payload) — filter hidden, neutral styling, re-sync hint.
  const neutral = useMemo(() => isIdentityNeutral(allRows), [allRows]);
  // Filter options keyed by semantic identity, display order by slot.
  // Labels are config display strings — for display only.
  const partnerOptions = useMemo(() => {
    const seen = new Map<string, (typeof allRows)[number]["partner"]>();
    for (const r of allRows) {
      const key = r.partner.partner_id;
      if (key !== "" && !seen.has(key)) seen.set(key, r.partner);
    }
    return byDisplayOrder(
      [...seen.values()].map((p) => ({ partner: p })),
    ).map(({ partner }) => ({
      value: partner.partner_id,
      label: partner.label,
    }));
  }, [allRows]);

  const [typeFilter, setTypeFilter] = useState("all");
  const [partnerFilter, setPartnerFilter] = useState("all");
  const [monthFilter, setMonthFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("date");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    const rows = allRows.filter((r) => {
      if (typeFilter !== "all" && r.type !== typeFilter) return false;
      if (partnerFilter !== "all" && r.partner.partner_id !== partnerFilter)
        return false;
      if (monthFilter !== "all" && r.monthLabel !== monthFilter) return false;
      return true;
    });
    rows.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "date":
          cmp = a.date.localeCompare(b.date);
          break;
        case "amount":
          cmp = a.amount - b.amount;
          break;
        case "partner":
          cmp = a.partner.label.localeCompare(b.partner.label);
          break;
        default:
          cmp = String(a[sortKey]).localeCompare(String(b[sortKey]));
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return rows;
  }, [allRows, typeFilter, partnerFilter, monthFilter, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const start = (currentPage - 1) * PAGE_SIZE;
  const pageRows = filtered.slice(start, start + PAGE_SIZE);

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
    setPage(1);
  }

  return (
    <div className="rounded-lg border bg-card shadow-sm">
      {/* Filter row */}
      <div className="flex flex-wrap items-end gap-3 border-b p-4">
        <Select
          label="Month range"
          value={monthFilter}
          onChange={(v) => {
            setMonthFilter(v);
            setPage(1);
          }}
          options={[
            { value: "all", label: "All months" },
            ...months.map((m) => ({ value: m, label: m })),
          ]}
        />
        <Select
          label="Type"
          value={typeFilter}
          onChange={(v) => {
            setTypeFilter(v);
            setPage(1);
          }}
          options={[
            { value: "all", label: "All" },
            { value: "bill", label: "Bills" },
            { value: "buy", label: "Buys" },
          ]}
        />
        {/* Partner filter only in identity mode — legacy payloads render
            neutral + hint instead (no positional inference). */}
        {!neutral && (
          <Select
            label="Partner"
            value={partnerFilter}
            onChange={(v) => {
              setPartnerFilter(v);
              setPage(1);
            }}
            options={[
              { value: "all", label: "All partners" },
              ...partnerOptions,
            ]}
          />
        )}
        {neutral && (
          <p role="note" className="pb-1 text-xs text-muted-foreground">
            {IDENTITY_NEUTRAL_HINT}
          </p>
        )}
      </div>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((col) => (
              <TableHead
                key={col.key}
                className={cn(
                  "h-10 px-4 font-medium",
                  col.className,
                )}
              >
                <button
                  type="button"
                  onClick={() => toggleSort(col.key)}
                  className={cn(
                    "inline-flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground",
                    col.className === "text-right" && "flex-row-reverse",
                    sortKey === col.key && "text-foreground",
                  )}
                >
                  {col.label}
                  <ArrowUpDown className="size-3" />
                </button>
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {pageRows.map((row) => {
            const isBuy = row.type === "buy";
            return (
              <TableRow
                key={row.id}
                className="border-b border-border/60 hover:bg-muted/40"
              >
                <TableCell className="whitespace-nowrap px-4 tabular-nums">
                  {formatDate(row.date)}
                </TableCell>
                <TableCell className="px-4">
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[11px] font-medium",
                      isBuy
                        ? "bg-savings/25 text-savings-foreground"
                        : "bg-secondary text-muted-foreground",
                    )}
                  >
                    {isBuy ? "Buy" : "Bill"}
                  </span>
                </TableCell>
                <TableCell className="px-4 font-medium">
                  <button
                    type="button"
                    className={cn(
                      "text-left",
                      onEventClick &&
                        "cursor-pointer hover:underline focus-visible:rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
                    )}
                    onClick={onEventClick ? () => onEventClick(row.id) : undefined}
                    disabled={!onEventClick}
                  >
                    {row.title}
                  </button>
                </TableCell>
                <TableCell className="px-4 text-muted-foreground">
                  {row.account}
                </TableCell>
                <TableCell className="px-4">
                  <span className="inline-flex items-center gap-1.5">
                    <span
                      className={cn(
                        "size-2 rounded-full",
                        // Accent by BE-assigned slot ("" → neutral gray).
                        partnerDotClass(row.partner.partner_slot),
                      )}
                      aria-hidden="true"
                    />
                    {row.partner.label}
                  </span>
                </TableCell>
                <TableCell
                  className={cn(
                    "px-4 text-right font-semibold tabular-nums",
                    row.amount > 0 ? "text-income" : "text-shortfall",
                  )}
                >
                  {row.amount > 0 ? "+" : "−"}
                  {formatKr(Math.abs(row.amount))}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>

      {/* Pagination */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t p-4 text-sm text-muted-foreground">
        <span>
          Showing{" "}
          <span className="font-medium text-foreground">
            {filtered.length === 0 ? 0 : start + 1}–
            {Math.min(start + PAGE_SIZE, filtered.length)}
          </span>{" "}
          of{" "}
          <span className="font-medium text-foreground">
            {filtered.length}
          </span>
        </span>
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="icon-sm"
            disabled={currentPage <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            aria-label="Previous page"
          >
            <ChevronLeft />
          </Button>
          {Array.from({ length: totalPages }, (_, i) => i + 1)
            .filter(
              (n) =>
                Math.abs(n - currentPage) <= 2 || n === 1 || n === totalPages,
            )
            .map((n, idx, arr) => (
              <span key={n} className="flex items-center">
                {idx > 0 && arr[idx - 1] !== n - 1 && (
                  <span className="px-1 text-border">…</span>
                )}
                <Button
                  variant={n === currentPage ? "default" : "ghost"}
                  size="icon-sm"
                  onClick={() => setPage(n)}
                  aria-label={`Page ${n}`}
                  aria-current={n === currentPage}
                >
                  {n}
                </Button>
              </span>
            ))}
          <Button
            variant="outline"
            size="icon-sm"
            disabled={currentPage >= totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            aria-label="Next page"
          >
            <ChevronRight />
          </Button>
        </div>
      </div>
    </div>
  );
}