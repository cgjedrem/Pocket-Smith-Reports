// InvestmentTable — shadcn Table for monthly investment net movement.
// Columns: Month | Partner A | Partner B | Total.

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

// Partner A (teal), B (orange), T = household total (green).
// CSS hsl() alpha MUST live INSIDE the function — template literals like
// `${COLOR} / 0.06` produce invalid CSS that the browser ignores.
const A_BG = "hsl(189 78% 26% / 0.06)";
const B_BG = "hsl(14 64% 56% / 0.06)";
const T_BG = "hsl(142 52% 36% / 0.05)";

const A_BORDER_35 = "hsl(189 78% 26% / 0.35)";
const B_BORDER_35 = "hsl(14 64% 56% / 0.35)";
const T_BORDER_35 = "hsl(142 52% 36% / 0.35)";

const A_BORDER_45 = "hsl(189 78% 26% / 0.45)";
const T_BORDER_45 = "hsl(142 52% 36% / 0.45)";

const B_BORDER_50 = "hsl(14 64% 56% / 0.5)";

const A_BORDER_60 = "hsl(189 78% 26% / 0.6)";
const T_BORDER_60 = "hsl(142 52% 36% / 0.6)";

function fmt(n: number): string {
  return n.toLocaleString("nb-NO", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export interface InvestmentRow {
  month: string; // already "YY/MM"
  partnerA: number;
  partnerB: number;
  total: number;
}

interface InvestmentTableProps {
  aLabel: string;
  bLabel: string;
  rows: InvestmentRow[];
  footerLabel?: string;
}

export function InvestmentTable({
  aLabel,
  bLabel,
  rows,
  footerLabel = "Net",
}: InvestmentTableProps) {
  const sumA = rows.reduce((s, r) => s + r.partnerA, 0);
  const sumB = rows.reduce((s, r) => s + r.partnerB, 0);
  const sumT = rows.reduce((s, r) => s + r.total, 0);

  return (
    <div className="rounded-md border border-border overflow-hidden">
      <Table>
        <colgroup>
          <col style={{ width: "20%" }} />
          <col style={{ width: "26%", backgroundColor: A_BG }} />
          <col
            style={{
              width: "26%",
              backgroundColor: B_BG,
            }}
          />
          <col
            style={{
              width: "28%",
              backgroundColor: T_BG,
            }}
          />
        </colgroup>
        <TableHeader>
          <TableRow>
            <TableHead rowSpan={1} className="border-r border-border">
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
              rowSpan={1}
              className="text-right border-border"
              style={{ borderLeft: `1px solid ${T_BORDER_35}` }}
            >
              Total
            </TableHead>
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
              style={{ borderRight: `2px solid ${T_BORDER_45}` }}
            >
              NOK
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={r.month} className="hover:bg-muted/30 even:bg-muted/10">
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
                style={{ borderRight: `2px solid ${T_BORDER_45}` }}
              >
                {fmt(r.total)}
              </TableCell>
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
              style={{ borderRight: `2px solid ${T_BORDER_60}` }}
            >
              {fmt(sumT)}
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>
  );
}
