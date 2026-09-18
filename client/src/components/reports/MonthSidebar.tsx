// Month selector — Radix Select dropdown.
// Trigger shows selected month. Opens list of all months.

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface MonthSidebarProps {
  months: string[];
  value: string | null;
  onChange: (month: string) => void;
}

export function MonthSidebar({ months, value, onChange }: MonthSidebarProps) {
  return (
    <Select value={value ?? undefined} onValueChange={onChange}>
      <SelectTrigger className="w-full">
        <SelectValue placeholder="Select month" />
      </SelectTrigger>
      <SelectContent>
        {months.map((m) => (
          <SelectItem key={m} value={m}>
            {m}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}