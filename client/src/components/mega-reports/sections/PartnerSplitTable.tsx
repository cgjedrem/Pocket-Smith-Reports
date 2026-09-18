// PartnerSplitTable — shadcn Table with partner-grouped visual structure.
// Two-tier header: "Per partner" (A+B cols) | "Total" | optional "Cumulative" + "Share".
// Colgroup tints (teal/orange/green) + colored borders per zone.

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export interface PartnerSplitRow {
  month: string; // already "YY/MM"
  partnerA: number;
  partnerB: number;
  total: number;
  cumulativeA?: number;
  cumulativeB?: number;
  cumulativeTotal?: number;
}

interface PartnerSplitTableProps {
  aLabel: string;
  bLabel: string;
  rows: PartnerSplitRow[];
  // Total column behavior: "monthly" shows the per-month total;
  // "cumulative" shows the running cumulative total (PDF savings behavior).
  totalMode?: "monthly" | "cumulative";
  // When true, adds a per-row Cumulative A | Cumulative B | Cumulative Total
  // group on the right (used by Savings/Home/Common).
  showCumulative?: boolean;
  // Adds a per-row share group.
  //   - "savings" → A % | B % (signed, |A|+|B|) | Δ MoM (current / prior cum)
  //   - "home"    → A % | B % (monthly share c/t) | Total % (month / period)
  // Both "home" and the Common section use the same A%/B%/Total% layout
  // (no Δ MoM), so CommonSection just passes "home".
  showShare?: false | "savings" | "home";
  // Subtitle on the cumulative footer row (e.g. "Cumulative" / "Net").
  footerLabel?: string;
}

// CSS hsl() alpha MUST live INSIDE the function — template literals like
// `${COLOR} / 0.06` produce invalid CSS that the browser ignores.
const A_BG = "hsl(189 78% 26% / 0.06)";
const B_BG = "hsl(14 64% 56% / 0.06)";
const T_BG = "hsl(142 52% 36% / 0.05)";
const S_BG = "hsl(262 52% 50% / 0.05)";

const A_BORDER_35 = "hsl(189 78% 26% / 0.35)";
const B_BORDER_35 = "hsl(14 64% 56% / 0.35)";
const T_BORDER_35 = "hsl(142 52% 36% / 0.35)";
const S_BORDER_35 = "hsl(262 52% 50% / 0.35)";

const A_BORDER_45 = "hsl(189 78% 26% / 0.45)";
const T_BORDER_45 = "hsl(142 52% 36% / 0.45)";
const S_BORDER_45 = "hsl(262 52% 50% / 0.45)";

const A_BORDER_60 = "hsl(189 78% 26% / 0.6)";
const T_BORDER_60 = "hsl(142 52% 36% / 0.6)";
const S_BORDER_60 = "hsl(262 52% 50% / 0.6)";

const B_BORDER_50 = "hsl(14 64% 56% / 0.5)";
const T_BORDER_50 = "hsl(142 52% 36% / 0.5)";

function fmt(n: number): string {
  return n.toLocaleString("nb-NO", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function fmtPctSigned(n: number): string {
  const s = n.toFixed(1);
  return n > 0 ? `+${s}%` : `${s}%`;
}

export function PartnerSplitTable({
  aLabel,
  bLabel,
  rows,
  totalMode = "monthly",
  showCumulative = false,
  showShare = false,
  footerLabel = "Cumulative",
}: PartnerSplitTableProps) {
  // Footer row sums
  const sumA = rows.reduce((s, r) => s + r.partnerA, 0);
  const sumB = rows.reduce((s, r) => s + r.partnerB, 0);
  const sumT = rows.reduce((s, r) => s + r.total, 0);

  // Pre-compute running cumulative + per-row share data.
  // Savings shareMode:
  //   A % = signed partnerA / (|partnerA| + |partnerB|)
  //   B % = signed partnerB / (|partnerA| + |partnerB|)
  //   Δ MoM = current month / prior cumulative
  // Home shareMode:
  //   A % = partnerA / (partnerA + partnerB)  — monthly share c/t
  //   B % = partnerB / (partnerA + partnerB)  — monthly share r/t
  //   Total % = current month / period total
  let running = 0;
  const enriched = rows.map((r) => {
    running += r.total;
    let aPct: number;
    let bPct: number;
    let thirdPct: number | null; // Δ MoM for savings, Total % for home
    if (showShare === "savings") {
      const absT = Math.abs(r.partnerA) + Math.abs(r.partnerB);
      aPct = absT ? (r.partnerA / absT) * 100 : 0;
      bPct = absT ? (r.partnerB / absT) * 100 : 0;
      const priorCum = running - r.total;
      thirdPct =
        r === rows[0] || priorCum === 0
          ? null
          : (r.total / priorCum) * 100;
    } else {
      // home
      const t = r.partnerA + r.partnerB;
      aPct = t ? (r.partnerA / t) * 100 : 0;
      bPct = t ? (r.partnerB / t) * 100 : 0;
      thirdPct = sumT ? (r.total / sumT) * 100 : null;
    }
    return { r, running, aPct, bPct, thirdPct };
  });

  // Footer share values.
  // savings: signed |sumA|/(|sumA|+|sumB|), |sumB|/(|sumA|+|sumB|), no Δ MoM
  // home:    sumA/(sumA+sumB), sumB/(sumA+sumB), 100.0%
  let footerAPct: number | null = null;
  let footerBPct: number | null = null;
  let footerThird: number | null = null;
  if (showShare === "savings") {
    const absT = Math.abs(sumA) + Math.abs(sumB);
    footerAPct = absT ? (sumA / absT) * 100 : 0;
    footerBPct = absT ? (sumB / absT) * 100 : 0;
    footerThird = null;
  } else if (showShare === "home") {
    const t = sumA + sumB;
    footerAPct = t ? (sumA / t) * 100 : 0;
    footerBPct = t ? (sumB / t) * 100 : 0;
    footerThird = 100.0;
  }

  // Colgroup widths
  // Every data column gets the same width so the table sums to 100%.
  // Layout (excluding Month):
  //   Base:           3 cols (A, B, Total)
  //   + showCumulative: +3 cols (A cum, B cum, Total cum)
  //   + showShare:    +3 cols (A %, B %, Total %)
  // Total data cols: 3 / 6 / 9. Each = 90% / totalDataCols.
  const monthW = "10%";
  const baseDataCols = 3;
  const cumCols = showCumulative ? 3 : 0;
  const shareCols = showShare ? 3 : 0;
  const totalDataCols = baseDataCols + cumCols + shareCols;
  const eachW = `${(90 / totalDataCols).toFixed(2)}%`;
  const aW = eachW;
  const bW = eachW;
  const tW = eachW;
  const cumAW = showCumulative ? eachW : undefined;
  const cumBW = showCumulative ? eachW : undefined;
  const cumTW = showCumulative ? eachW : undefined;
  const shareAW = showShare ? eachW : undefined;
  const shareBW = showShare ? eachW : undefined;
  const shareTW = showShare ? eachW : undefined;

  return (
    <div className="rounded-md border border-border overflow-hidden">
      <Table>
        <colgroup>
          <col style={{ width: monthW }} />
          <col style={{ width: aW, backgroundColor: A_BG }} />
          <col style={{ width: bW, backgroundColor: B_BG }} />
          <col style={{ width: tW, backgroundColor: T_BG }} />
          {showCumulative && (
            <>
              <col style={{ width: cumAW, backgroundColor: A_BG }} />
              <col style={{ width: cumBW, backgroundColor: B_BG }} />
              <col style={{ width: cumTW, backgroundColor: T_BG }} />
            </>
          )}
          {showShare && (
            <>
              <col style={{ width: shareAW, backgroundColor: A_BG }} />
              <col style={{ width: shareBW, backgroundColor: B_BG }} />
              <col style={{ width: shareTW, backgroundColor: S_BG }} />
            </>
          )}
        </colgroup>
        <TableHeader>
          <TableRow>
            <TableHead rowSpan={2} className="align-bottom border-r border-border">
              Month
            </TableHead>
            <TableHead
              colSpan={2}
              className="text-center border-b border-r border-border"
              style={{ borderBottomColor: A_BORDER_35 }}
            >
              Per partner
            </TableHead>
            <TableHead
              colSpan={1}
              rowSpan={2}
              className="text-right align-bottom border-r border-border"
              style={{ borderRightColor: T_BORDER_35 }}
            >
              Total
            </TableHead>
            {showCumulative && (
              <TableHead
                colSpan={3}
                className="text-center border-b border-r border-border"
                style={{ borderBottomColor: T_BORDER_35 }}
              >
                Cumulative
              </TableHead>
            )}
            {showShare && (
              <TableHead
                colSpan={3}
                className="text-center border-b border-border"
                style={{ borderBottomColor: S_BORDER_35 }}
              >
                Share
              </TableHead>
            )}
          </TableRow>
          <TableRow>
            <TableHead
              className="text-right"
              style={{ borderLeft: `2px solid ${A_BORDER_45}` }}
            >
              {aLabel}
            </TableHead>
            <TableHead
              className="text-right"
              style={{
                borderLeft: `1px solid ${B_BORDER_35}`,
                borderRight: `1px solid ${B_BORDER_35}`,
              }}
            >
              {bLabel}
            </TableHead>
            {showCumulative && (
              <>
                <TableHead
                  className="text-right"
                  style={{ borderLeft: `2px solid ${A_BORDER_45}` }}
                >
                  {aLabel}
                </TableHead>
                <TableHead
                  className="text-right"
                  style={{
                    borderLeft: `1px solid ${B_BORDER_35}`,
                    borderRight: `1px solid ${B_BORDER_35}`,
                  }}
                >
                  {bLabel}
                </TableHead>
                <TableHead
                  className="text-right"
                  style={{
                    borderRight: `2px solid ${T_BORDER_45}`,
                  }}
                >
                  Total
                </TableHead>
              </>
            )}
            {showShare && (
              <>
                <TableHead
                  className="text-right"
                  style={{ borderLeft: `2px solid ${A_BORDER_45}` }}
                >
                  {aLabel} %
                </TableHead>
                <TableHead
                  className="text-right"
                  style={{
                    borderLeft: `1px solid ${B_BORDER_35}`,
                    borderRight: `1px solid ${B_BORDER_35}`,
                  }}
                >
                  {bLabel} %
                </TableHead>
                <TableHead
                  className="text-right"
                  style={{ borderRight: `2px solid ${S_BORDER_45}` }}
                >
                  {showShare === "savings" ? "Δ MoM" : "Total %"}
                </TableHead>
              </>
            )}
          </TableRow>
        </TableHeader>
        <TableBody>
          {enriched.map(({ r, running, aPct, bPct, thirdPct }) => (
            <TableRow
              key={r.month}
              className="hover:bg-muted/30 even:bg-muted/10"
            >
              <TableCell className="font-medium border-r border-border">
                {r.month}
              </TableCell>
              <TableCell
                className="text-right tabular-nums"
                style={{ borderLeft: `2px solid ${A_BORDER_45}` }}
              >
                {fmt(r.partnerA)}
              </TableCell>
              <TableCell
                className="text-right tabular-nums"
                style={{
                  borderLeft: `1px solid ${B_BORDER_35}`,
                  borderRight: `1px solid ${B_BORDER_35}`,
                }}
              >
                {fmt(r.partnerB)}
              </TableCell>
              <TableCell
                className="text-right tabular-nums font-semibold"
                style={{ borderRight: `1px solid ${T_BORDER_35}` }}
              >
                {fmt(totalMode === "cumulative" ? running : r.total)}
              </TableCell>
              {showCumulative && (
                <>
                  <TableCell
                    className="text-right tabular-nums"
                    style={{ borderLeft: `2px solid ${A_BORDER_45}` }}
                  >
                    {fmt(r.cumulativeA ?? 0)}
                  </TableCell>
                  <TableCell
                    className="text-right tabular-nums"
                    style={{
                      borderLeft: `1px solid ${B_BORDER_35}`,
                      borderRight: `1px solid ${B_BORDER_35}`,
                    }}
                  >
                    {fmt(r.cumulativeB ?? 0)}
                  </TableCell>
                  <TableCell
                    className="text-right tabular-nums font-semibold"
                    style={{ borderRight: `2px solid ${T_BORDER_45}` }}
                  >
                    {fmt(r.cumulativeTotal ?? 0)}
                  </TableCell>
                </>
              )}
              {showShare && (
                <>
                  <TableCell
                    className="text-right tabular-nums"
                    style={{ borderLeft: `2px solid ${A_BORDER_45}` }}
                  >
                    {fmtPctSigned(aPct)}
                  </TableCell>
                  <TableCell
                    className="text-right tabular-nums"
                    style={{
                      borderLeft: `1px solid ${B_BORDER_35}`,
                      borderRight: `1px solid ${B_BORDER_35}`,
                    }}
                  >
                    {fmtPctSigned(bPct)}
                  </TableCell>
                  <TableCell
                    className="text-right tabular-nums"
                    style={{ borderRight: `2px solid ${S_BORDER_45}` }}
                  >
                    {thirdPct === null ? "—" : `${thirdPct.toFixed(1)}%`}
                  </TableCell>
                </>
              )}
            </TableRow>
          ))}
          <TableRow className="font-semibold bg-muted/50 border-t-2 border-border">
            <TableCell className="border-r border-border">{footerLabel}</TableCell>
            <TableCell
              className="text-right tabular-nums"
              style={{ borderLeft: `2px solid ${A_BORDER_60}` }}
            >
              {fmt(sumA)}
            </TableCell>
            <TableCell
              className="text-right tabular-nums"
              style={{
                borderLeft: `1px solid ${B_BORDER_50}`,
                borderRight: `1px solid ${B_BORDER_50}`,
              }}
            >
              {fmt(sumB)}
            </TableCell>
            <TableCell
              className="text-right tabular-nums"
              style={{ borderRight: `1px solid ${T_BORDER_50}` }}
            >
              {fmt(sumT)}
            </TableCell>
            {showCumulative && (
              <TableCell
                colSpan={3}
                className="text-right text-muted-foreground text-xs italic"
                style={{ borderRight: `2px solid ${T_BORDER_60}` }}
              >
                running totals shown above
              </TableCell>
            )}
            {showShare && (
              <>
                <TableCell
                  className="text-right tabular-nums"
                  style={{ borderLeft: `2px solid ${A_BORDER_60}` }}
                >
                  {footerAPct === null ? "—" : `${footerAPct.toFixed(1)}%`}
                </TableCell>
                <TableCell
                  className="text-right tabular-nums"
                  style={{
                    borderLeft: `1px solid ${B_BORDER_50}`,
                    borderRight: `1px solid ${B_BORDER_50}`,
                  }}
                >
                  {footerBPct === null ? "—" : `${footerBPct.toFixed(1)}%`}
                </TableCell>
                <TableCell
                  className="text-right tabular-nums"
                  style={{ borderRight: `2px solid ${S_BORDER_60}` }}
                >
                  {footerThird === null ? "—" : `${footerThird.toFixed(1)}%`}
                </TableCell>
              </>
            )}
          </TableRow>
        </TableBody>
      </Table>
    </div>
  );
}
