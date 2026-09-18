// F2 — finance formatters. Re-exports formatKr/formatDate from finance-data
// and adds ordinalDay. Kept separate so the data file stays pure logic.

export { formatKr, formatDate } from "./finance-data";

// English ordinal suffix: 1 → "1st", 22 → "22nd", 23 → "23rd".
export function ordinalDay(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return `${n}${s[(v - 20) % 10] ?? s[v] ?? s[0]}`;
}
