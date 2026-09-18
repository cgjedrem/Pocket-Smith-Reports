// Row counts table — 5 row types.

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { RowCounts } from "@/types/api";

const ROWS: Array<{ key: keyof RowCounts; label: string }> = [
  { key: "transactions", label: "Transactions" },
  { key: "events", label: "Events" },
  { key: "budget", label: "Budget" },
  { key: "categories", label: "Categories" },
  { key: "accounts", label: "Accounts" },
];

interface RowCountTableProps {
  rowCounts: RowCounts;
}

export function RowCountTable({ rowCounts }: RowCountTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Type</TableHead>
          <TableHead className="text-right">Count</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {ROWS.map(({ key, label }) => (
          <TableRow key={key}>
            <TableCell>{label}</TableCell>
            <TableCell className="text-right font-mono">
              {rowCounts[key]}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}