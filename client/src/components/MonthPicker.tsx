// Month picker — Popover + two Selects (month + year). No day grid.
// Output: yyyy-MM string.

import { useState } from "react";
import { CalendarIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

// Year range: 2020 → current year + `futureYears` (default 10).
// Built per-instance so test mocks of `new Date()` work and we
// can vary the future window per consumer.
function buildYears(futureYears: number): number[] {
  const now = new Date();
  const cap = now.getFullYear() + futureYears;
  const years: number[] = [];
  for (let y = 2020; y <= cap; y++) years.push(y);
  return years;
}

interface MonthPickerProps {
  label: string;
  value: string; // "yyyy-MM"
  onChange: (value: string) => void;
  disabled?: boolean;
  /**
   * How many years past `currentYear` to include. Default 10 so the
   * SyncPage end-month picker can target future years (e.g. 2027-12
   * for annual planning). Pass 0 to cap at the current year.
   */
  futureYears?: number;
}

export function MonthPicker({
  label,
  value,
  onChange,
  disabled,
  futureYears = 10,
}: MonthPickerProps) {
  const years = buildYears(futureYears);
  // Parse yyyy-MM → year + month index (0-based).
  const [year, month] = value.split("-").map(Number);
  const hasValue = !isNaN(year) && !isNaN(month);

  const [open, setOpen] = useState(false);

  const handleSelect = (newYear: number, newMonth: number) => {
    const mm = String(newMonth + 1).padStart(2, "0");
    onChange(`${newYear}-${mm}`);
  };

  return (
    <div className="flex flex-col gap-1">
      <span className="text-sm text-muted-foreground">{label}</span>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            disabled={disabled}
            className={cn(
              "w-[10rem] justify-start text-left font-normal",
              !hasValue && "text-muted-foreground",
            )}
          >
            <CalendarIcon className="size-4" />
            {hasValue ? value : "Pick month"}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-3" align="start">
          <div className="flex gap-2">
            <Select
              value={hasValue ? String(month - 1) : undefined}
              onValueChange={(v) => {
                const m = Number(v);
                handleSelect(hasValue ? year : years[years.length - 1], m);
              }}
            >
              <SelectTrigger className="w-[7rem]">
                <SelectValue placeholder="Month" />
              </SelectTrigger>
              <SelectContent>
                {MONTHS.map((m, i) => (
                  <SelectItem key={m} value={String(i)}>
                    {m}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={hasValue ? String(year) : undefined}
              onValueChange={(v) => {
                const y = Number(v);
                handleSelect(y, hasValue ? month - 1 : 0);
              }}
            >
              <SelectTrigger className="w-[6rem]">
                <SelectValue placeholder="Year" />
              </SelectTrigger>
              <SelectContent>
                {years.map((y) => (
                  <SelectItem key={y} value={String(y)}>
                    {y}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}