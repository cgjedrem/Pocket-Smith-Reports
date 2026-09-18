// RangePicker — two MonthPicker components (start + end). Validates start ≤ end.
// Shows missing-months warning if any month in range has no synced data.

import { MonthPicker } from "@/components/MonthPicker";

interface RangePickerProps {
  start: string;
  end: string;
  onChange: (start: string, end: string) => void;
  availableMonths: string[];
}

// Build list of months between start and end (inclusive).
function monthsInRange(start: string, end: string): string[] {
  const [sy, sm] = start.split("-").map(Number);
  const [ey, em] = end.split("-").map(Number);
  const out: string[] = [];
  let y = sy;
  let m = sm;
  while (y < ey || (y === ey && m <= em)) {
    out.push(`${y}-${String(m).padStart(2, "0")}`);
    m += 1;
    if (m > 12) {
      m = 1;
      y += 1;
    }
  }
  return out;
}

export function RangePicker({ start, end, onChange, availableMonths }: RangePickerProps) {
  const startLEnd = start <= end;
  const missing = startLEnd
    ? monthsInRange(start, end).filter((m) => !availableMonths.includes(m))
    : [];

  return (
    <div className="flex flex-wrap items-end gap-4">
      <MonthPicker
        label="Start month"
        value={start}
        onChange={(v) => onChange(v, end)}
      />
      <MonthPicker
        label="End month"
        value={end}
        onChange={(v) => onChange(start, v)}
      />
      {!startLEnd && (
        <p className="text-sm text-destructive">Start must be before or equal to end.</p>
      )}
      {startLEnd && missing.length > 0 && (
        <p className="text-sm text-destructive" role="alert">
          Missing: {missing.join(", ")}. Sync these first.
        </p>
      )}
    </div>
  );
}