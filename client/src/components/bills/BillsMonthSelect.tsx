// Window picker — two number inputs (past / future months).
// Feeds pending values to parent via onPastMonthsChange / onFutureMonthsChange.
// Parent decides when to commit via onApply (Enter inside the inputs or
// its own button). Auto-commit on every keystroke is intentionally avoided.

import { useState } from "react";
import type React from "react";

interface BillsMonthSelectProps {
  disabled?: boolean;
  // Initial values for the local number inputs.
  initialPastMonths?: number;
  initialFutureMonths?: number;
  // Callback when user changes the past-months window.
  onPastMonthsChange?: (n: number) => void;
  // Callback when user changes the future-months window.
  onFutureMonthsChange?: (n: number) => void;
  // Optional apply trigger — fired on Enter inside the window inputs.
  // Parent decides when to commit pending values to the BE fetch.
  onApply?: () => void;
}

const MIN_WINDOW = 0;
const MAX_WINDOW = 240;

function clampWindow(n: number): number {
  if (!Number.isFinite(n)) return 0;
  return Math.max(MIN_WINDOW, Math.min(MAX_WINDOW, Math.floor(n)));
}

export function BillsMonthSelect({
  disabled,
  initialPastMonths = 3,
  initialFutureMonths = 12,
  onPastMonthsChange,
  onFutureMonthsChange,
  onApply,
}: BillsMonthSelectProps) {
  const [pastMonths, setPastMonths] = useState(
    clampWindow(initialPastMonths),
  );
  const [futureMonths, setFutureMonths] = useState(
    clampWindow(initialFutureMonths),
  );

  function handlePastChange(n: number) {
    setPastMonths(n);
    onPastMonthsChange?.(n);
  }

  function handleFutureChange(n: number) {
    setFutureMonths(n);
    onFutureMonthsChange?.(n);
  }

  // Enter inside a number input — commit pending window. Belt + braces:
  // explicit Apply button is the primary path; this is the keyboard one.
  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      onApply?.();
    }
  }

  return (
    <div className="flex items-center gap-2">
      <label className="flex items-center gap-2 text-sm text-muted-foreground">
        Past
        <input
          type="number"
          min={MIN_WINDOW}
          max={MAX_WINDOW}
          step={1}
          value={pastMonths}
          disabled={disabled}
          onChange={(e) =>
            handlePastChange(clampWindow(Number(e.target.value)))
          }
          onKeyDown={handleKeyDown}
          className="h-9 w-[5rem] rounded-md border border-input bg-card px-2 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
          aria-label="Past months"
        />
      </label>

      <label className="flex items-center gap-2 text-sm text-muted-foreground">
        Future
        <input
          type="number"
          min={MIN_WINDOW}
          max={MAX_WINDOW}
          step={1}
          value={futureMonths}
          disabled={disabled}
          onChange={(e) =>
            handleFutureChange(clampWindow(Number(e.target.value)))
          }
          onKeyDown={handleKeyDown}
          className="h-9 w-[5rem] rounded-md border border-input bg-card px-2 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
          aria-label="Future months"
        />
      </label>
    </div>
  );
}