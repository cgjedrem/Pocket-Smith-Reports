import { shiftLifestyleMonth } from "./lifestyle-creep";
import type { DecimalString, LifestyleComparison, MonthlyAmount } from "@/types/lifestyle-creep";

// Descriptive trailing average for the category chart. The server's
// target-versus-reference verdict stays authoritative and is not changed here.
export const TRAILING_WINDOW = 3;
export const TRAILING_MINIMUM = 2;
const AVERAGE_FRACTION_DIGITS = 6;

interface ExactDecimal {
  units: bigint;
  scale: number;
}

export interface LifestyleTrendPoint {
  kind: "sample";
  key: string;
  month: string;
  amount: DecimalString;
  priorMonths: string[];
  trailingAverage: DecimalString | null;
  isAboveTrailingAverage: boolean;
  isTarget: boolean;
  usage: number | null;
  average: number | null;
}

export interface LifestyleTrendGap {
  kind: "gap";
  key: string;
  afterMonth: string;
  beforeMonth: string;
  missingMonths: number;
  usage: null;
  average: null;
}

export type LifestyleTrendRow = LifestyleTrendPoint | LifestyleTrendGap;

export type LifestyleTrend =
  | { status: "ready"; rows: LifestyleTrendRow[]; points: LifestyleTrendPoint[]; plottable: boolean }
  | { status: "invalid"; reason: string };

export function parseExactDecimal(raw: string): ExactDecimal | null {
  const match = /^([+-]?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/.exec(raw);
  if (!match) return null;
  const fraction = match[3] ?? "";
  const exponent = Number(match[4] ?? "0");
  if (!Number.isSafeInteger(exponent) || Math.abs(exponent) > 1000) return null;
  let units = BigInt(match[2] + fraction);
  let scale = fraction.length - exponent;
  if (scale < 0) {
    units *= 10n ** BigInt(-scale);
    scale = 0;
  }
  return { units: match[1] === "-" ? -units : units, scale };
}

function align(value: ExactDecimal, scale: number): bigint {
  return value.units * 10n ** BigInt(scale - value.scale);
}

function divideRounded(numerator: bigint, denominator: bigint): bigint {
  const negative = numerator < 0n;
  const magnitude = negative ? -numerator : numerator;
  const rounded = (magnitude * 2n + denominator) / (denominator * 2n);
  return negative ? -rounded : rounded;
}

function decimalString(units: bigint, scale: number): string {
  const negative = units < 0n;
  const digits = (negative ? -units : units).toString().padStart(scale + 1, "0");
  const whole = digits.slice(0, digits.length - scale);
  const fraction = digits.slice(digits.length - scale).replace(/0+$/, "");
  const text = fraction ? `${whole}.${fraction}` : whole;
  return negative && /[1-9]/.test(text) ? `-${text}` : text;
}

// Exact sum/count, rounded half away from zero only for presentation.
function averageString(values: ExactDecimal[]): string {
  const scale = Math.max(AVERAGE_FRACTION_DIGITS, ...values.map((value) => value.scale));
  const sum = values.reduce((total, value) => total + align(value, scale), 0n);
  return decimalString(divideRounded(sum, BigInt(values.length)), scale);
}

// Strict exact comparison: amount > sum(prior) / count  <=>  amount * count > sum(prior).
function exceedsAverage(amount: ExactDecimal, prior: ExactDecimal[]): boolean {
  const scale = Math.max(amount.scale, ...prior.map((value) => value.scale));
  const sum = prior.reduce((total, value) => total + align(value, scale), 0n);
  return align(amount, scale) * BigInt(prior.length) > sum;
}

// Chart coordinates only. Values that would lose precision, overflow or
// underflow make the chart unplottable instead of drawing a wrong point.
function chartNumber(raw: string, exact: ExactDecimal): number | null {
  const number = Number(raw);
  if (!Number.isFinite(number) || Math.abs(number) > Number.MAX_SAFE_INTEGER) return null;
  if ((number === 0) !== (exact.units === 0n)) return null;
  const roundTrip = parseExactDecimal(String(number));
  if (!roundTrip) return null;
  const scale = Math.max(exact.scale, roundTrip.scale);
  if (align(exact, scale) !== align(roundTrip, scale)) return null;
  return number;
}

export function lifestyleTrend(samples: MonthlyAmount[], comparison: Pick<LifestyleComparison, "month">): LifestyleTrend {
  const ordered = [...samples].sort((a, b) => a.month.localeCompare(b.month));
  const exact = new Map<string, ExactDecimal>();
  for (const sample of ordered) {
    if (shiftLifestyleMonth(sample.month, 0) !== sample.month) {
      return { status: "invalid", reason: `Sample month ${sample.month} is not a calendar month.` };
    }
    if (exact.has(sample.month)) {
      return { status: "invalid", reason: `Sample month ${sample.month} appears more than once.` };
    }
    const value = parseExactDecimal(sample.amount);
    if (!value) return { status: "invalid", reason: `The ${sample.month} amount is not an exact decimal.` };
    exact.set(sample.month, value);
  }

  let plottable = true;
  const rows: LifestyleTrendRow[] = [];
  const points: LifestyleTrendPoint[] = [];
  ordered.forEach((sample, index) => {
    const previous = ordered[index - 1];
    if (previous && shiftLifestyleMonth(previous.month, 1) !== sample.month) {
      let missingMonths = 0;
      for (let month = shiftLifestyleMonth(previous.month, 1); month && month < sample.month; month = shiftLifestyleMonth(month, 1)) {
        missingMonths += 1;
      }
      rows.push({
        kind: "gap", key: `gap:${previous.month}:${sample.month}`, afterMonth: previous.month,
        beforeMonth: sample.month, missingMonths, usage: null, average: null,
      });
    }
    const priorMonths: string[] = [];
    for (let offset = 1; offset <= TRAILING_WINDOW; offset += 1) {
      const month = shiftLifestyleMonth(sample.month, -offset);
      if (!month || !exact.has(month)) break;
      priorMonths.unshift(month);
    }
    const amount = exact.get(sample.month)!;
    const prior = priorMonths.map((month) => exact.get(month)!);
    const hasAverage = prior.length >= TRAILING_MINIMUM;
    const trailingAverage = hasAverage ? averageString(prior) : null;
    const usage = chartNumber(sample.amount, amount);
    const average = trailingAverage === null ? null : chartNumber(trailingAverage, parseExactDecimal(trailingAverage)!);
    if (usage === null || (trailingAverage !== null && average === null)) plottable = false;
    const point: LifestyleTrendPoint = {
      kind: "sample",
      key: sample.month,
      month: sample.month,
      amount: sample.amount,
      priorMonths: hasAverage ? priorMonths : [],
      trailingAverage,
      isAboveTrailingAverage: hasAverage && exceedsAverage(amount, prior),
      isTarget: sample.month === comparison.month,
      usage,
      average,
    };
    rows.push(point);
    points.push(point);
  });
  return { status: "ready", rows, points, plottable };
}
