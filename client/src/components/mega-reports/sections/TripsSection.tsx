// TripsSection — shadcn Card + common-only overview table + per-partner stacked bar chart.
// Mirrors PDF section_trips.py + src/mom/trips.py derivation.
//   - Info + period-total note: full trip cost (Common + Personal), unchanged.
//   - Overview table: Common-only per trip. Per-partner = NET of common-cat
//     reimbursements (paid - received within Common Trip cat). Trips with no
//     common portion are hidden.
//   - Stacked bar chart: full per-partner split per trip (all 10 trips), unchanged.

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { compactNOK, formatNOK, partnerLabel } from "@/components/mega-reports/sections/helpers";
import type { MegaReportResponse, Trip } from "@/types/mega_report";
import {
  Bar,
  BarChart,
  CartesianGrid,
  XAxis,
  YAxis,
} from "recharts";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";

interface TripsSectionProps {
  report: MegaReportResponse;
}

function tripDates(
  start: string | null,
  end: string | null,
): string {
  if (!start && !end) return "—";
  if (start && end) return `${start} → ${end}`;
  return start ?? end ?? "—";
}

export function TripsSection({ report }: TripsSectionProps) {
  const trips = report.detail_agg.trips ?? [];
  const aLabel = partnerLabel(report, "partner_a");
  const bLabel = partnerLabel(report, "partner_b");

  // Period totals (all cats) — drives header note + chart.
  const grandTotal = trips.reduce((s, t) => s + t.total, 0);
  const grandA = trips.reduce((s, t) => s + t.partner_a_paid, 0);
  const grandB = trips.reduce((s, t) => s + t.partner_b_paid, 0);
  const grandAPct = grandTotal ? (grandA / grandTotal) * 100 : 0;
  const grandBPct = grandTotal ? (grandB / grandTotal) * 100 : 0;

  // Stacked-bar chart data: one bar per trip, two stacked segments.
  const aKey = "partnerAStack";
  const bKey = "partnerBStack";
  const chartData = trips.map((t) => ({
    trip: t.label,
    [aKey]: t.partner_a_paid,
    [bKey]: t.partner_b_paid,
  }));

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">8. Trips</CardTitle>
        {trips.length > 0 && (
          <>
            <p className="text-xs text-muted-foreground italic">
              A single trip = a set of transactions sharing the same PS label.
              Per-trip cost split between {aLabel} and {bLabel}. Paired
              transfers between them are netted out.
            </p>
            <p className="text-sm text-muted-foreground">
              Total trip cost: <b>{formatNOK(grandTotal)} NOK</b> ({aLabel}{" "}
              paid {formatNOK(grandA)} = {grandAPct.toFixed(1)}% | {bLabel} paid{" "}
              {formatNOK(grandB)} = {grandBPct.toFixed(1)}%)
            </p>
          </>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {trips.length === 0 ? (
          <p className="text-sm text-muted-foreground">No trips in this range.</p>
        ) : (
          <>
            <div>
              <h3
                id="trips-common-overview"
                className="text-sm font-semibold text-foreground scroll-mt-20"
              >
                Trips overview — common only
              </h3>
              <TripsCommonTable trips={trips} aLabel={aLabel} bLabel={bLabel} />
            </div>

            <div>
              <TripsBarChart
                data={chartData}
                aKey={aKey}
                bKey={bKey}
                aLabel={aLabel}
                bLabel={bLabel}
              />
            </div>

            <div>
              <TripsSubcatBlocks
                trips={trips}
                aLabel={aLabel}
                bLabel={bLabel}
              />
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

// --- Common-only overview table -------------------------------------------

interface CommonTripRow {
  label: string;
  date_start: string | null;
  date_end: string | null;
  total: number;
  partner_a_paid: number;
  partner_b_paid: number;
  txn_count: number;
}

interface TripsCommonTableProps {
  trips: Trip[];
  aLabel: string;
  bLabel: string;
}

// Derive per-trip common-cat totals with per-partner NET of reimbursements.
// Mirrors src/mom/trips.py:cat_breakdown + partner_a/b_paid logic:
//   common_total   = sum abs(amount) of common-cat outflows (cat_breakdown key)
//   common_a_paid  = a_gross_outflows - a_inflows (per-partner net of reimbs)
//   common_b_paid  = b_gross_outflows - b_inflows
// Transfers (is_transfer) are excluded from the per-partner counts.
function commonRowForTrip(trip: Trip): CommonTripRow | null {
  const common = trip.cat_breakdown?.["Common Trip"] ?? 0;
  if (common <= 0) return null;
  let aGross = 0;
  let aIn = 0;
  let bGross = 0;
  let bIn = 0;
  let count = 0;
  for (const raw of trip.txns ?? []) {
    const t = raw as {
      amount_in_base_currency?: number;
      category?: { title?: string };
      owner?: string;
      is_transfer?: boolean;
    };
    if (t.category?.title !== "Common Trip") continue;
    if (t.is_transfer) continue;
    count += 1;
    const amt = t.amount_in_base_currency ?? 0;
    if (amt < 0) {
      if (t.owner === "partner_a") aGross += Math.abs(amt);
      else if (t.owner === "partner_b") bGross += Math.abs(amt);
    } else if (amt > 0) {
      if (t.owner === "partner_a") aIn += amt;
      else if (t.owner === "partner_b") bIn += amt;
    }
  }
  return {
    label: trip.label,
    date_start: trip.date_start,
    date_end: trip.date_end,
    total: common,
    partner_a_paid: aGross - aIn,
    partner_b_paid: bGross - bIn,
    txn_count: count,
  };
}

function TripsCommonTable({ trips, aLabel, bLabel }: TripsCommonTableProps) {
  const rows = trips
    .map(commonRowForTrip)
    .filter((r): r is CommonTripRow => r !== null);

  if (rows.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No common-trip expenses in this range.
      </p>
    );
  }

  const grandTotal = rows.reduce((s, r) => s + r.total, 0);
  const grandA = rows.reduce((s, r) => s + r.partner_a_paid, 0);
  const grandB = rows.reduce((s, r) => s + r.partner_b_paid, 0);
  const grandNet = grandA + grandB;
  const grandTxns = rows.reduce((s, r) => s + r.txn_count, 0);
  const grandAPct = grandNet > 0 ? (grandA / grandNet) * 100 : 0;
  const grandBPct = grandNet > 0 ? (grandB / grandNet) * 100 : 0;

  // CSS hsl() alpha MUST live INSIDE the function — template literals like
  // `${aColor} / 0.06` produce invalid CSS that the browser ignores.
  const aBg = "hsl(189 78% 26% / 0.06)";
  const bBg = "hsl(14 64% 56% / 0.06)";
  const tBg = "hsl(142 52% 36% / 0.05)";

  const aBorder35 = "hsl(189 78% 26% / 0.35)";
  const bBorder35 = "hsl(14 64% 56% / 0.35)";
  const tBorder35 = "hsl(142 52% 36% / 0.35)";
  const sBorder35 = "hsl(262 52% 50% / 0.35)";

  const aBorder45 = "hsl(189 78% 26% / 0.45)";

  const aBorder60 = "hsl(189 78% 26% / 0.6)";
  const bBorder50 = "hsl(14 64% 56% / 0.5)";
  const tBorder50 = "hsl(142 52% 36% / 0.5)";

  return (
    <div className="rounded-md border border-border overflow-hidden">
      <Table>
        <colgroup>
          <col style={{ width: "16%" }} />
          <col style={{ width: "12%", backgroundColor: aBg }} />
          <col style={{ width: "12%", backgroundColor: bBg }} />
          <col style={{ width: "12%", backgroundColor: tBg }} />
          <col style={{ width: "10%", backgroundColor: aBg }} />
          <col style={{ width: "10%", backgroundColor: bBg }} />
          <col style={{ width: "16%" }} />
          <col style={{ width: "12%" }} />
        </colgroup>
        <TableHeader>
          <TableRow>
            <TableHead rowSpan={1} className="border-r border-border">
              Trip
            </TableHead>
            <TableHead
              colSpan={2}
              className="text-center border-b border-r border-border"
              style={{ borderBottomColor: aBorder35 }}
            >
              Per partner
            </TableHead>
            <TableHead
              colSpan={1}
              rowSpan={1}
              className="text-right border-r border-border"
              style={{ borderRightColor: tBorder35 }}
            >
              Total
            </TableHead>
            <TableHead
              colSpan={2}
              className="text-center border-b border-r border-border"
              style={{ borderBottomColor: sBorder35 }}
            >
              Share
            </TableHead>
            <TableHead rowSpan={1} className="border-r border-border">
              Dates
            </TableHead>
            <TableHead className="text-right">Txns</TableHead>
          </TableRow>
          <TableRow>
            <TableHead
              className="border-r border-border"
              style={{ visibility: "hidden" }}
            >
              —
            </TableHead>
            <TableHead
              className="text-right"
              style={{ borderLeft: `2px solid ${aBorder45}` }}
            >
              {aLabel}
            </TableHead>
            <TableHead
              className="text-right"
              style={{
                borderLeft: `1px solid ${bBorder35}`,
                borderRight: `1px solid ${bBorder35}`,
              }}
            >
              {bLabel}
            </TableHead>
            <TableHead
              className="text-right"
              style={{ borderRight: `1px solid ${tBorder35}` }}
            >
              NOK
            </TableHead>
            <TableHead
              className="text-right"
              style={{ borderLeft: `2px solid ${aBorder45}` }}
            >
              {aLabel} %
            </TableHead>
            <TableHead
              className="text-right"
              style={{
                borderLeft: `1px solid ${bBorder35}`,
                borderRight: `1px solid ${bBorder35}`,
              }}
            >
              {bLabel} %
            </TableHead>
            <TableHead
              className="border-r border-border"
              style={{ visibility: "hidden" }}
            >
              —
            </TableHead>
            <TableHead className="text-right" style={{ visibility: "hidden" }}>
              —
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => {
            // Share % = each partner's share of the NET (a+b), so 100% reconciles
            // per row. Common-cat total can exceed a+b when a partner received a
            // reimb within the same cat — that gap is silently absorbed in Total.
            const netSum = r.partner_a_paid + r.partner_b_paid;
            const aPct = netSum > 0 ? (r.partner_a_paid / netSum) * 100 : 0;
            const bPct = netSum > 0 ? (r.partner_b_paid / netSum) * 100 : 0;
            return (
              <TableRow
                key={r.label}
                className="hover:bg-muted/30 even:bg-muted/10"
              >
                <TableCell className="font-semibold border-r border-border">
                  {r.label}
                </TableCell>
                <TableCell
                  className="text-right tabular-nums"
                  style={{ borderLeft: `2px solid ${aBorder45}` }}
                >
                  {formatNOK(r.partner_a_paid)}
                </TableCell>
                <TableCell
                  className="text-right tabular-nums"
                  style={{
                    borderLeft: `1px solid ${bBorder35}`,
                    borderRight: `1px solid ${bBorder35}`,
                  }}
                >
                  {formatNOK(r.partner_b_paid)}
                </TableCell>
                <TableCell
                  className="text-right tabular-nums font-semibold"
                  style={{ borderRight: `1px solid ${tBorder35}` }}
                >
                  {formatNOK(r.total)}
                </TableCell>
                <TableCell
                  className="text-right tabular-nums"
                  style={{ borderLeft: `2px solid ${aBorder45}` }}
                >
                  {aPct.toFixed(1)}%
                </TableCell>
                <TableCell
                  className="text-right tabular-nums"
                  style={{
                    borderLeft: `1px solid ${bBorder35}`,
                    borderRight: `1px solid ${bBorder35}`,
                  }}
                >
                  {bPct.toFixed(1)}%
                </TableCell>
                <TableCell className="border-r border-border text-xs">
                  {tripDates(r.date_start, r.date_end)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {r.txn_count}
                </TableCell>
              </TableRow>
            );
          })}
          <TableRow className="font-semibold bg-muted/50 border-t-2 border-border">
            <TableCell className="border-r border-border">Period total</TableCell>
            <TableCell
              className="text-right tabular-nums"
              style={{ borderLeft: `2px solid ${aBorder60}` }}
            >
              {formatNOK(grandA)}
            </TableCell>
            <TableCell
              className="text-right tabular-nums"
              style={{
                borderLeft: `1px solid ${bBorder50}`,
                borderRight: `1px solid ${bBorder50}`,
              }}
            >
              {formatNOK(grandB)}
            </TableCell>
            <TableCell
              className="text-right tabular-nums"
              style={{ borderRight: `1px solid ${tBorder50}` }}
            >
              {formatNOK(grandTotal)}
            </TableCell>
            <TableCell
              className="text-right tabular-nums"
              style={{ borderLeft: `2px solid ${aBorder60}` }}
            >
              {grandAPct.toFixed(1)}%
            </TableCell>
            <TableCell
              className="text-right tabular-nums"
              style={{
                borderLeft: `1px solid ${bBorder50}`,
                borderRight: `1px solid ${bBorder50}`,
              }}
            >
              {grandBPct.toFixed(1)}%
            </TableCell>
            <TableCell className="border-r border-border" />
            <TableCell className="text-right tabular-nums">{grandTxns}</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>
  );
}

// --- Per-trip sub-category blocks (PDF parity) ----------------------------

interface SubcatRow {
  cat: string;
  partner_a: number;
  partner_b: number;
  total: number;
  typeLabel: string;
  // Tailwind class for row tint, mirrors PDF (common / partner-a / partner-b).
  tint: "common" | "partner-a" | "partner-b";
}

interface TripsSubcatBlocksProps {
  trips: Trip[];
  aLabel: string;
  bLabel: string;
}

// Per-trip sub-cat breakdown. Mirrors src/mom/sections/section_trips.py:
// render_trip_subcat_table.
//   For each trip: per-partner per-cat value = -(sum of amount). Debits
//   (amount<0) become positive; credits (amount>0) reduce the partner's net.
//   This matches the PDF "paid" semantics (paid minus received).
//   Rows sorted by abs(total) desc. "Total" footer row sums all cats.
function subcatRowsForTrip(
  trip: Trip,
  aLabel: string,
  bLabel: string,
): SubcatRow[] {
  const buckets: Record<string, { a: number; b: number }> = {};
  for (const raw of trip.txns ?? []) {
    const t = raw as {
      amount_in_base_currency?: number;
      amount?: number;
      category?: { title?: string };
      owner?: string;
      is_transfer?: boolean;
    };
    if (t.is_transfer) continue;
    const cat = t.category?.title ?? "Uncategorised";
    const amt = t.amount_in_base_currency ?? t.amount ?? 0;
    if (!amt) continue;
    if (!buckets[cat]) buckets[cat] = { a: 0, b: 0 };
    if (t.owner === "partner_a") buckets[cat].a -= amt;
    else if (t.owner === "partner_b") buckets[cat].b -= amt;
  }
  const rows: SubcatRow[] = Object.entries(buckets)
    .map(([cat, v]) => {
      const l = cat.toLowerCase();
      const aL = aLabel.toLowerCase();
      const bL = bLabel.toLowerCase();
      let tint: SubcatRow["tint"] = "common";
      let typeLabel = "Common";
      if (l.includes("personal") && l.includes(bL)) {
        tint = "partner-b";
        typeLabel = `${bLabel} personal`;
      } else if (l.includes("personal") && l.includes(aL)) {
        tint = "partner-a";
        typeLabel = `${aLabel} personal`;
      } else if (l.includes("personal")) {
        // Personal cat without name in title — fall back to who paid.
        tint = v.a >= v.b ? "partner-a" : "partner-b";
        typeLabel = `${v.a >= v.b ? aLabel : bLabel} personal`;
      }
      return {
        cat,
        partner_a: v.a,
        partner_b: v.b,
        total: v.a + v.b,
        typeLabel,
        tint,
      };
    })
    // Mirrors src/mom/sections/section_trips.py: render_trip_subcat_table.
    // Python sorts by -sum(row[1].values()) — descending SIGNED sum (a+b),
    // i.e. biggest spending at the top. Math.abs(total) would surface large
    // net-negative reimbursements at the top, breaking PDF parity.
    .sort((x, y) => y.total - x.total);
  return rows;
}

function TripsSubcatBlocks({ trips, aLabel, bLabel }: TripsSubcatBlocksProps) {
  // Drop trips with no txns (matches PDF guard).
  const blocks = trips
    .map((t) => ({ trip: t, rows: subcatRowsForTrip(t, aLabel, bLabel) }))
    .filter((b) => b.rows.length > 0);
  if (blocks.length === 0) return null;

  // CSS hsl() alpha MUST live INSIDE the function — template literals like
  // `${aColor} / 0.06` produce invalid CSS that the browser ignores.
  const bBorder35 = "hsl(14 64% 56% / 0.35)";
  const tBorder35 = "hsl(142 52% 36% / 0.35)";

  const aBorder45 = "hsl(189 78% 26% / 0.45)";

  const aBorder60 = "hsl(189 78% 26% / 0.6)";
  const bBorder50 = "hsl(14 64% 56% / 0.5)";
  const tBorder50 = "hsl(142 52% 36% / 0.5)";
  const tintBg: Record<SubcatRow["tint"], string> = {
    common: "",
    "partner-a": "bg-[hsl(189_78%_26%/0.06)]",
    "partner-b": "bg-[hsl(14_64%_56%/0.06)]",
  };

  return (
    <div className="flex flex-col gap-4">
      <h3
        id="trips-by-subcategory"
        className="text-sm font-semibold text-foreground pt-2 scroll-mt-20"
      >
        Trips by sub-category (per trip)
      </h3>
      {blocks.map(({ trip, rows }) => {
        const grandTotal = rows.reduce((s, r) => s + r.total, 0);
        const grandA = rows.reduce((s, r) => s + r.partner_a, 0);
        const grandB = rows.reduce((s, r) => s + r.partner_b, 0);
        return (
          <div key={trip.label} className="flex flex-col gap-2">
            <h4 className="text-sm font-semibold text-foreground">
              {trip.label}{" "}
              <span className="text-muted-foreground font-normal">
                ({formatNOK(grandTotal)} NOK)
              </span>
            </h4>
            <div className="rounded-md border border-border overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Sub-category</TableHead>
                    <TableHead className="text-right">{aLabel}</TableHead>
                    <TableHead className="text-right">{bLabel}</TableHead>
                    <TableHead className="text-right">Total</TableHead>
                    <TableHead className="text-right">{aLabel} %</TableHead>
                    <TableHead className="text-right">{bLabel} %</TableHead>
                    <TableHead>Type</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((r) => (
                    <TableRow
                      key={r.cat}
                      className={`hover:bg-muted/30 even:bg-muted/10 ${tintBg[r.tint]}`}
                    >
                      <TableCell className="font-medium">{r.cat}</TableCell>
                      <TableCell
                        className="text-right tabular-nums"
                        style={{ borderLeft: `2px solid ${aBorder45}` }}
                      >
                        {formatNOK(r.partner_a)}
                      </TableCell>
                      <TableCell
                        className="text-right tabular-nums"
                        style={{ borderRight: `1px solid ${bBorder35}` }}
                      >
                        {formatNOK(r.partner_b)}
                      </TableCell>
                      <TableCell
                        className="text-right tabular-nums font-semibold"
                        style={{ borderRight: `1px solid ${tBorder35}` }}
                      >
                        {formatNOK(r.total)}
                      </TableCell>
                      <TableCell
                        className="text-right tabular-nums"
                        style={{ borderLeft: `2px solid ${aBorder45}` }}
                      >
                        {r.total ? ((r.partner_a / r.total) * 100).toFixed(1) : "0.0"}%
                      </TableCell>
                      <TableCell
                        className="text-right tabular-nums"
                        style={{ borderRight: `1px solid ${bBorder35}` }}
                      >
                        {r.total ? ((r.partner_b / r.total) * 100).toFixed(1) : "0.0"}%
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {r.typeLabel}
                      </TableCell>
                    </TableRow>
                  ))}
                  <TableRow className="font-semibold bg-muted/50 border-t-2 border-border">
                    <TableCell>Total</TableCell>
                    <TableCell
                      className="text-right tabular-nums"
                      style={{ borderLeft: `2px solid ${aBorder60}` }}
                    >
                      {formatNOK(grandA)}
                    </TableCell>
                    <TableCell
                      className="text-right tabular-nums"
                      style={{ borderRight: `1px solid ${bBorder50}` }}
                    >
                      {formatNOK(grandB)}
                    </TableCell>
                    <TableCell
                      className="text-right tabular-nums"
                      style={{ borderRight: `1px solid ${tBorder50}` }}
                    >
                      {formatNOK(grandTotal)}
                    </TableCell>
                    <TableCell
                      className="text-right tabular-nums"
                      style={{ borderLeft: `2px solid ${aBorder60}` }}
                    >
                      {grandTotal ? ((grandA / grandTotal) * 100).toFixed(1) : "0.0"}%
                    </TableCell>
                    <TableCell
                      className="text-right tabular-nums"
                      style={{ borderRight: `1px solid ${bBorder50}` }}
                    >
                      {grandTotal ? ((grandB / grandTotal) * 100).toFixed(1) : "0.0"}%
                    </TableCell>
                    <TableCell />
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// --- Stacked bar chart (unchanged scope) -----------------------------------

interface TripsBarChartProps {
  data: Array<Record<string, number | string>>;
  aKey: string;
  bKey: string;
  aLabel: string;
  bLabel: string;
}

function TripsBarChart({ data, aKey, bKey, aLabel, bLabel }: TripsBarChartProps) {
  const config = {
    [aKey]: { label: aLabel, color: "hsl(189 78% 26%)" },
    [bKey]: { label: bLabel, color: "hsl(14 64% 56%)" },
  } as const;

  return (
    <div>
      <h3
        id="trips-by-partner"
        className="text-sm font-semibold text-foreground pb-1 scroll-mt-20"
      >
        Trips by partner
      </h3>
      <TripsStackedBar data={data} aKey={aKey} bKey={bKey} config={config} />
    </div>
  );
}

function TripsStackedBar({
  data,
  aKey,
  bKey,
  config,
}: {
  data: Array<Record<string, number | string>>;
  aKey: string;
  bKey: string;
  config: ChartConfig;
}) {
  return (
    <ChartContainer
      config={config}
      className="w-full min-w-0"
      style={{ height: 420 }}
    >
      <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 50 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="trip"
          tickLine={false}
          axisLine={false}
          tickMargin={12}
          fontSize={10}
          angle={-30}
          textAnchor="end"
          interval={0}
        />
        <YAxis
          tickFormatter={(v: number) => compactNOK(v)}
          tickLine={false}
          axisLine={false}
          fontSize={10}
        />
        <ChartTooltip
          content={
            <ChartTooltipContent
              formatter={(value) => compactNOK(Number(value))}
            />
          }
        />
        <ChartLegend content={<ChartLegendContent />} />
        <Bar dataKey={aKey} stackId="bar" fill={`var(--color-${aKey})`} />
        <Bar
          dataKey={bKey}
          stackId="bar"
          fill={`var(--color-${bKey})`}
          radius={[2, 2, 0, 0]}
        />
      </BarChart>
    </ChartContainer>
  );
}
