import { formatKr, formatSignedKr } from "@/components/bills/finance-data";
import { AMOUNT_MASK, isAmountsHidden, maskAmount } from "./privacy-store";
import type { DecimalString, ReportLifestyleCategory } from "@/types/lifestyle-creep";

// Exact input bounds — digit position, not binary-float comparisons.
export function canonicalThreshold(raw: string): string | null {
  const match = /^([+-]?)(?:(\d+)(?:\.(\d*))?|\.(\d+))(?:[eE]([+-]?\d+))?$/.exec(raw);
  if (!match || match[0] !== raw || match[1] === "-") return null;
  const integer = match[2] ?? "";
  const fraction = match[3] ?? match[4] ?? "";
  const digits = integer + fraction;
  const significant = digits.replace(/^0+/, "");
  if (!significant) return null;
  const point = BigInt(integer.length - (digits.length - significant.length)) + BigInt(match[5] ?? "0");
  if (point < 1n || point > 3n) return null;
  const coefficient = significant.replace(/0+$/, "");
  if (point === 3n) return coefficient === "1" ? "100" : null;
  const position = Number(point);
  return coefficient.length <= position
    ? coefficient.padEnd(position, "0")
    : `${coefficient.slice(0, position)}.${coefficient.slice(position)}`;
}

function monthIndex(raw: string): number | null {
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(raw) || raw.length !== 7 || raw < "0001-01") return null;
  const [year, month] = raw.split("-").map(Number);
  return (year - 1) * 12 + month - 1;
}

export function currentLifestyleMonth(): string {
  const now = new Date();
  return `${String(now.getFullYear()).padStart(4, "0")}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export function shiftLifestyleMonth(month: string, offset: number): string {
  const index = monthIndex(month);
  if (index === null || !Number.isInteger(offset)) return "";
  const shifted = index + offset;
  if (shifted < 0 || shifted >= 9999 * 12) return "";
  return `${String(Math.floor(shifted / 12) + 1).padStart(4, "0")}-${String(shifted % 12 + 1).padStart(2, "0")}`;
}

export function validLifestyleMonth(raw: string, current: string): boolean {
  const index = monthIndex(raw);
  const currentIndex = monthIndex(current);
  return index !== null && currentIndex !== null && index >= 2 && index < currentIndex;
}

export function defaultLifestyleSelection(current = currentLifestyleMonth()) {
  const target = shiftLifestyleMonth(current, -1);
  return {
    target,
    referenceStart: shiftLifestyleMonth(target, -3),
    referenceEnd: shiftLifestyleMonth(target, -1),
  };
}

export function lifestyleSelectionError(
  target: string, referenceStart: string, referenceEnd: string, current: string,
): string | null {
  const targetIndex = monthIndex(target);
  const first = monthIndex(referenceStart);
  const last = monthIndex(referenceEnd);
  const currentIndex = monthIndex(current);
  if (targetIndex === null || first === null || last === null) {
    return "Choose a target month and both reference months using real calendar months.";
  }
  if (targetIndex < 2) return "Target month must be 0001-03 or later to allow two reference months.";
  if (currentIndex === null || targetIndex >= currentIndex) {
    return `Choose a completed target month before ${current}.`;
  }
  if (first > last) return "Reference start must be on or before reference end.";
  if (last >= targetIndex) return "Reference end must be earlier than target month.";
  if (last - first + 1 < 2) return "Choose at least 2 consecutive reference months.";
  if (last - first + 1 > 24) return "Choose at most 24 consecutive reference months.";
  return null;
}

export function lifestyleReferenceMonths(start: string, end: string): string[] {
  if (lifestyleSelectionError(shiftLifestyleMonth(end, 1), start, end, "9999-12") !== null) return [];
  const count = monthIndex(end)! - monthIndex(start)! + 1;
  return Array.from({ length: count }, (_, offset) => shiftLifestyleMonth(start, offset));
}

export function lifestyleEvidenceMonths(start: string, end: string, target: string): string[] {
  if (lifestyleSelectionError(target, start, end, "9999-12") !== null) return [];
  return [...lifestyleReferenceMonths(start, end), target];
}

// Presentation only — never use rounded values for verdicts.
export function formatLifestyleMoney(value: DecimalString, signed = false): string {
  if (isAmountsHidden()) return AMOUNT_MASK;
  const number = Number(value);
  if (Number.isFinite(number) && Math.abs(number) <= Number.MAX_SAFE_INTEGER) {
    return signed ? formatSignedKr(number) : formatKr(number);
  }
  const negative = value.startsWith("-");
  const [whole, fraction] = (negative ? value.slice(1) : value).split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return maskAmount(`${negative ? "-" : signed ? "+" : ""}${grouped}${fraction ? `.${fraction}` : ""} kr`);
}

export function formatLifestylePercent(value: DecimalString | null, reason: string): string {
  if (value === null) return `Not calculable — ${reason}`;
  const number = Number(value);
  return `${Number.isFinite(number)
    ? number.toLocaleString("en-US", { maximumFractionDigits: 2 })
    : value}%`;
}

export function lifestyleOutcome(category: ReportLifestyleCategory): string {
  if (category.suppression_reason === "zero_baseline") return "Suppressed — zero reference baseline";
  if (category.suppression_reason === "negative_baseline") return "Suppressed — negative reference baseline";
  if (category.suppression_reason === "low_frequency") return "Suppressed — positive spending in fewer than two reference months";
  return category.is_above_threshold ? "Above threshold" : "Below threshold";
}
