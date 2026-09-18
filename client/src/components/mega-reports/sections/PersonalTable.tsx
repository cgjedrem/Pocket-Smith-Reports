// PersonalTable — shadcn Table for monthly personal spend (single owner).
// Columns: Month | <owner> | Running total | <owner> % of total spend | Total %

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

// CSS hsl() alpha MUST live INSIDE the function — template literals like
// `${COLOR} / 0.06` produce invalid CSS that the browser ignores.
const A_BG = "hsl(189 78% 26% / 0.06)";
const T_BG = "hsl(142 52% 36% / 0.05)";
const S_BG = "hsl(262 52% 50% / 0.05)";

const A_BORDER_35 = "hsl(189 78% 26% / 0.35)";
const T_BORDER_35 = "hsl(142 52% 36% / 0.35)";
const S_BORDER_35 = "hsl(262 52% 50% / 0.35)";

const A_BORDER_45 = "hsl(189 78% 26% / 0.45)";
const S_BORDER_45 = "hsl(262 52% 50% / 0.45)";

const A_BORDER_60 = "hsl(189 78% 26% / 0.6)";
const T_BORDER_50 = "hsl(142 52% 36% / 0.5)";
const S_BORDER_60 = "hsl(262 52% 50% / 0.6)";

function fmt(n: number): string {
  return n.toLocaleString("nb-NO", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export interface PersonalRow {
  month: string;
  ownerValue: number;
  runningTotal: number;
  ownerPctOfHousehold: number; // signed +X.X% of household real_spend for that month
  totalPctOfPeriod: number; // X.X% of personal period total
}

interface PersonalTableProps {
  ownerLabel: string;
  rows: PersonalRow[];
  grandTotal: number;
  ownerNet: number;
  ownerPctOfHouseholdPeriod: number | null;
}

export function PersonalTable({
  ownerLabel,
  rows,
  grandTotal,
  ownerNet,
  ownerPctOfHouseholdPeriod,
}: PersonalTableProps) {
  return (
    <div className="rounded-md border border-border overflow-hidden">
      <Table>
        <colgroup>
          <col style={{ width: "16%" }} />
          <col
            style={{ width: "22%", backgroundColor: A_BG }}
          />
          <col
            style={{ width: "22%", backgroundColor: T_BG }}
          />
          <col
            style={{ width: "22%", backgroundColor: A_BG }}
          />
          <col
            style={{ width: "18%", backgroundColor: S_BG }}
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
              Monthly
            </TableHead>
            <TableHead
              colSpan={2}
              className="text-center border-b border-border"
              style={{ borderBottomColor: S_BORDER_35 }}
            >
              Share
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
              {ownerLabel}
            </TableHead>
            <TableHead
              className="text-right"
              style={{
                borderLeft: `1px solid ${T_BORDER_35}`,
                borderRight: `1px solid ${T_BORDER_35}`,
              }}
            >
              Running total
            </TableHead>
            <TableHead
              className="text-right"
              style={{ borderLeft: `2px solid ${A_BORDER_45}` }}
            >
              {ownerLabel} % of total spend
            </TableHead>
            <TableHead
              className="text-right"
              style={{ borderRight: `2px solid ${S_BORDER_45}` }}
            >
              Total %
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
                {fmt(r.ownerValue)}
              </TableCell>
              <TableCell
                className="text-right tabular-nums font-semibold"
                style={{
                  borderLeft: `1px solid ${T_BORDER_35}`,
                  borderRight: `1px solid ${T_BORDER_35}`,
                }}
              >
                {fmt(r.runningTotal)}
              </TableCell>
              <TableCell
                className="text-right tabular-nums"
                style={{ borderLeft: `2px solid ${A_BORDER_45}` }}
              >
                {r.ownerPctOfHousehold === 0
                  ? "—"
                  : `${r.ownerPctOfHousehold >= 0 ? "+" : ""}${r.ownerPctOfHousehold.toFixed(1)}%`}
              </TableCell>
              <TableCell
                className="text-right tabular-nums"
                style={{ borderRight: `2px solid ${S_BORDER_45}` }}
              >
                {r.totalPctOfPeriod === 0 ? "—" : `${r.totalPctOfPeriod.toFixed(1)}%`}
              </TableCell>
            </TableRow>
          ))}
          <TableRow className="font-semibold bg-muted/50 border-t-2 border-border">
            <TableCell className="border-r border-border">Period total</TableCell>
            <TableCell
              className="text-right tabular-nums"
              style={{ borderLeft: `2px solid ${A_BORDER_60}` }}
            >
              {fmt(ownerNet)}
            </TableCell>
            <TableCell
              className="text-right tabular-nums"
              style={{
                borderLeft: `1px solid ${T_BORDER_50}`,
                borderRight: `1px solid ${T_BORDER_50}`,
              }}
            >
              {fmt(grandTotal)}
            </TableCell>
            <TableCell
              className="text-right tabular-nums"
              style={{ borderLeft: `2px solid ${A_BORDER_60}` }}
            >
              {ownerPctOfHouseholdPeriod === null
                ? "—"
                : `${ownerPctOfHouseholdPeriod >= 0 ? "+" : ""}${ownerPctOfHouseholdPeriod.toFixed(1)}%`}
            </TableCell>
            <TableCell
              className="text-right tabular-nums"
              style={{ borderRight: `2px solid ${S_BORDER_60}` }}
            >
              100.0%
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>
  );
}
