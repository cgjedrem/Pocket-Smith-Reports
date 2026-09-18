// AppendicesSection — full per-section transaction detail tables.
// Mirrors src/mom/sections/section_appendices.py: Section → Main category
// → Subcategory → table (Date | Payee | Account | Amount + subtotal).
//
// Data source: `report.appendix_transactions[month] = [AppendixTransaction...]`.
// Each txn carries `_detailed_section`, `_main_category`, `_subcategory` routing
// tags built by src/mega/build_mega.py::_appendix_transactions.

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { compactNOK, partnerLabel, slugify } from "@/components/mega-reports/sections/helpers";
import type {
  AppendixTransaction,
  MegaReportResponse,
  Trip,
} from "@/types/mega_report";

interface AppendicesSectionProps {
  report: MegaReportResponse;
}

// Same section order as src/mom/sections/section_appendices.py.
// Personal labels resolve from report.partner_labels — no hardcoded names.
function sectionOrder(report: MegaReportResponse): { id: string; label: string }[] {
  return [
    { id: "income", label: "Income" },
    { id: "savings", label: "Savings" },
    { id: "home", label: "Home" },
    { id: "common", label: "Common" },
    { id: "personal_partner_a", label: `Personal — ${partnerLabel(report, "partner_a")}` },
    { id: "personal_partner_b", label: `Personal — ${partnerLabel(report, "partner_b")}` },
    { id: "trips", label: "Trips" },
  ];
}

interface GroupedTxn {
  txn: AppendixTransaction;
  subKey: string; // "root" or "<id>::<title>"
  subTitle: string;
}

function groupForSection(txns: AppendixTransaction[]): Map<string, Map<string, AppendixTransaction[]>> {
  // mainKey -> subKey -> txns
  const out = new Map<string, Map<string, AppendixTransaction[]>>();
  for (const txn of txns) {
    const main = txn._main_category;
    const sub = txn._subcategory;
    const mainKey = `${main?.id ?? "0"}::${main?.title ?? "Uncategorised"}`;
    const subKey = sub
      ? `${sub.id}::${sub.title}`
      : "root::" + (main?.title ?? "Uncategorised");
    const subTitle = sub?.title ?? "(root)";
    const group: GroupedTxn = { txn, subKey, subTitle };
    if (!out.has(mainKey)) out.set(mainKey, new Map());
    const inner = out.get(mainKey)!;
    if (!inner.has(subKey)) inner.set(subKey, []);
    inner.get(subKey)!.push(group.txn);
  }
  return out;
}

function sortedMainEntries(
  groups: Map<string, Map<string, AppendixTransaction[]>>,
): Array<[string, string, Map<string, AppendixTransaction[]>]> {
  // Mirrors src/mom/sections/section_appendices.py:68-70 — sort main cats by
  // title first, then id. (Previous sort by full `id::title` string effectively
  // sorted by id first, breaking PDF/CLI ordering for same-title cats.)
  return Array.from(groups.entries())
    .map(([mainKey, inner]) => {
      const [id, ...rest] = mainKey.split("::");
      const title = rest.join("::") || mainKey;
      return { mainKey, id, title, inner };
    })
    .sort((x, y) => {
      const t = x.title.localeCompare(y.title);
      return t !== 0 ? t : x.id.localeCompare(y.id);
    })
    .map(({ mainKey, title, inner }) => [mainKey, title, inner] as const);
}

function sortedSubEntries(
  inner: Map<string, AppendixTransaction[]>,
): Array<[string, string, AppendixTransaction[]]> {
  return Array.from(inner.entries())
    // root entries (no subcat) first, then by title.
    .sort(([a], [b]) => {
      const aRoot = a.startsWith("root::");
      const bRoot = b.startsWith("root::");
      if (aRoot !== bRoot) return aRoot ? -1 : 1;
      return a.localeCompare(b);
    })
    .map(([k, v]) => {
      const title = k.startsWith("root::") ? k.slice("root::".length) : k.split("::")[1] ?? k;
      return [k, title, v] as const;
    });
}

// Trip appendix layout — group txns by trip label (PS labels[0]).
// Order matches report.detail_agg.trips where available, so the appendix
// mirrors the main TripsSection. Untagged txns (no PS label) go last.
function groupTripsByLabel(
  txns: AppendixTransaction[],
  trips: Trip[],
): Array<{ label: string; txns: AppendixTransaction[] }> {
  const buckets = new Map<string, AppendixTransaction[]>();
  for (const t of txns) {
    const label = t._trip_label?.trim() || "(no trip label)";
    if (!buckets.has(label)) buckets.set(label, []);
    buckets.get(label)!.push(t);
  }
  const order = trips.map((t) => t.label);
  const sortedLabels = Array.from(buckets.keys()).sort((a, b) => {
    // Order using the trips[] list if both labels appear there.
    const ai = order.indexOf(a);
    const bi = order.indexOf(b);
    if (ai !== -1 && bi !== -1) return ai - bi;
    if (ai !== -1) return -1;
    if (bi !== -1) return 1;
    // Untagged always last.
    if (a === "(no trip label)") return 1;
    if (b === "(no trip label)") return -1;
    return a.localeCompare(b);
  });
  return sortedLabels.map((label) => ({ label, txns: buckets.get(label)! }));
}

function AppendicesTable({
  txns,
  label,
  anchorId,
  showLabel = true,
}: {
  txns: AppendixTransaction[];
  label: string;
  anchorId: string;
  showLabel?: boolean;
}) {
  // Sort by date asc, then id for stable order.
  const sorted = [...txns].sort((a, b) => {
    const d = a.date.localeCompare(b.date);
    if (d !== 0) return d;
    return String(a.id ?? "").localeCompare(String(b.id ?? ""));
  });
  const subtotal = sorted.reduce((s, t) => s + t.amount, 0);

  return (
    <div className="space-y-1">
      {showLabel && (
        <h4
          id={anchorId}
          className="text-sm font-semibold text-foreground scroll-mt-24"
        >
          {label}
        </h4>
      )}
      {!showLabel && <span id={anchorId} className="block scroll-mt-24" />}
      <div className="rounded-md border border-border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[100px]">Date</TableHead>
              <TableHead>Payee</TableHead>
              <TableHead>Account</TableHead>
              <TableHead className="text-right">Amount</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((t, idx) => (
              <TableRow
                key={`${t.id ?? "txn"}-${idx}`}
                className="hover:bg-muted/30 even:bg-muted/10"
              >
                <TableCell className="text-xs tabular-nums">{t.date}</TableCell>
                <TableCell className="max-w-[420px] truncate" title={t.payee}>
                  {t.payee || "—"}
                </TableCell>
                <TableCell className="text-xs">{t.account?.name ?? "—"}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {compactNOK(t.amount)}
                </TableCell>
              </TableRow>
            ))}
            <TableRow className="font-semibold bg-muted/50 border-t-2 border-border">
              <TableCell colSpan={3}>Subtotal</TableCell>
              <TableCell className="text-right tabular-nums">
                {compactNOK(subtotal)}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

export function AppendicesSection({ report }: AppendicesSectionProps) {
  const appendix = report.appendix_transactions ?? null;
  // Flatten all months into one array.
  const allTxns: AppendixTransaction[] = appendix
    ? Object.values(appendix).flat()
    : [];

  // Group by _detailed_section, preserving fixed section order.
  const bySection = new Map<string, AppendixTransaction[]>();
  for (const txn of allTxns) {
    const sec = txn._detailed_section ?? "unknown";
    if (!bySection.has(sec)) bySection.set(sec, []);
    bySection.get(sec)!.push(txn);
  }

  const totalTxns = allTxns.length;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">13. Appendices</CardTitle>
        <p className="text-sm font-semibold text-foreground">
          Appendices — full transaction detail
        </p>
        {appendix && totalTxns > 0 && (
          <p className="text-xs text-muted-foreground">
            {totalTxns.toLocaleString("nb-NO")} transactions across{" "}
            {Object.keys(appendix).length} months.
          </p>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        {!appendix || totalTxns === 0 ? (
          <p className="text-sm text-muted-foreground">
            No appendix transactions in this report. Re-generate the mega
            report to populate appendix tables.
          </p>
        ) : (
          sectionOrder(report).map(({ id, label }) => {
            const txns = bySection.get(id) ?? [];
            if (txns.length === 0) return null;
            const sectionTotal = txns.reduce((s, t) => s + t.amount, 0);
            const sectionAnchor = `appendices-section-${id}`;
            // Trips are grouped by PS trip label (one table per trip)
            // instead of by main category — matches TripsSection layout.
            if (id === "trips") {
              const grouped = groupTripsByLabel(txns, report.detail_agg.trips ?? []);
              return (
                <div key={id} className="flex flex-col gap-3">
                  <div className="flex items-baseline gap-3 border-b border-border pb-1">
                    <h3
                      id={sectionAnchor}
                      className="text-sm font-semibold text-foreground scroll-mt-24"
                    >
                      {label}
                    </h3>
                    <span className="text-xs text-muted-foreground tabular-nums">
                      {txns.length} txns · {compactNOK(sectionTotal)} NOK
                    </span>
                  </div>
                  {grouped.map(({ label: tripLabel, txns: tripTxns }, tripIdx) => {
                    const tripSlug = slugify(tripLabel);
                    const tripAnchor = `appendices-cat-${id}-${tripSlug}`;
                    return (
                      <div
                        // key includes section id + tripSlug + index to survive
                        // duplicate trip labels across the trip loop.
                        key={`trip-${id}-${tripSlug}-${tripIdx}`}
                        className="flex flex-col gap-3 pl-3"
                      >
                        <h4
                          id={tripAnchor}
                          className="text-sm font-medium text-foreground scroll-mt-24"
                        >
                          {tripLabel}
                        </h4>
                        <div className="pl-3">
                          <AppendicesTable
                            txns={tripTxns}
                            label=""
                            anchorId={`appendices-subcat-${id}-${tripSlug}-root`}
                            showLabel={false}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              );
            }
            const groups = groupForSection(txns);
            return (
              <div key={id} className="flex flex-col gap-3">
                <div className="flex items-baseline gap-3 border-b border-border pb-1">
                  <h3
                    id={sectionAnchor}
                    className="text-sm font-semibold text-foreground scroll-mt-24"
                  >
                    {label}
                  </h3>
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {txns.length} txns · {compactNOK(sectionTotal)} NOK
                  </span>
                </div>
                {sortedMainEntries(groups).map(([mainKey, mainTitle, inner]) => {
                  const mainSlug = slugify(mainTitle);
                  const mainAnchor = `appendices-cat-${id}-${mainSlug}`;
                  return (
                    <div key={mainKey} className="flex flex-col gap-3 pl-3">
                      <h4
                        id={mainAnchor}
                        className="text-sm font-medium text-foreground scroll-mt-24"
                      >
                        {mainTitle}
                      </h4>
                      {sortedSubEntries(inner).map(([subKey, subDisplayTitle, subTxns], subIdx) => {
                        const isRoot = subKey.startsWith("root::");
                        const anchorSubSlug = isRoot ? "root" : slugify(subDisplayTitle);
                        const anchorId = `appendices-subcat-${id}-${mainSlug}-${anchorSubSlug}`;
                        return (
                          <div
                            // subKey can collide across main cats (same
                            // subcategory title in two main cats) — use
                            // mainSlug + subIdx for a stable, unique key.
                            key={`sub-${mainSlug}-${subIdx}-${anchorSubSlug}`}
                            className="pl-3"
                          >
                            <AppendicesTable
                              txns={subTxns}
                              label={subDisplayTitle}
                              anchorId={anchorId}
                              showLabel={!isRoot}
                            />
                          </div>
                        );
                      })}
                    </div>
                  );
                })}
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
