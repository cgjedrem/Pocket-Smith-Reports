// F2 grid redesign — tiny savings-trajectory sparkline for month card
// headers. Inline SVG (no recharts): one polyline per partner identity
// across the loaded window (identity-neutral payloads: single combined
// neutral series). Decorative — svg is aria-hidden, trend is summarised
// in visually-hidden text for screen readers.

import { formatKr } from "./finance-data";

export interface SparklineSeries {
  // Partner display name (config-provided label).
  name: string;
  // CSS color for the polyline (e.g. var(--color-partner-a)).
  color: string;
  // savingsBalance per loaded month, index-aligned with MonthData[].
  // Null = partner missing from that month → gap in the line.
  values: (number | null)[];
}

type Pt = { x: number; y: number };

export function SavingsSparkline({
  series,
  width = 90,
  height = 24,
}: {
  series: SparklineSeries[];
  width?: number;
  height?: number;
}) {
  const pad = 2;
  const all = series.flatMap((s) =>
    s.values.filter((v): v is number => v != null),
  );
  if (all.length === 0) return null;

  const min = Math.min(...all);
  const max = Math.max(...all);
  const span = max - min;
  const count = Math.max(...series.map((s) => s.values.length));
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  const xAt = (i: number) =>
    pad + (count <= 1 ? innerW / 2 : (i / (count - 1)) * innerW);
  const yAt = (v: number) =>
    pad + (span === 0 ? innerH / 2 : (1 - (v - min) / span) * innerH);

  // Runs of consecutive non-null points per series — a null (partner
  // missing for a month) breaks the line instead of drawing through 0.
  const runs = series.map((s) => {
    const segments: Pt[][] = [];
    let current: Pt[] = [];
    s.values.forEach((v, i) => {
      if (v == null) {
        if (current.length > 0) segments.push(current);
        current = [];
        return;
      }
      current.push({ x: xAt(i), y: yAt(v) });
    });
    if (current.length > 0) segments.push(current);
    return { series: s, segments };
  });

  const summary = series
    .map((s) => {
      const vals = s.values.filter((v): v is number => v != null);
      return `${s.name} from ${formatKr(vals[0])} to ${formatKr(vals[vals.length - 1])}`;
    })
    .join("; ");

  return (
    <span className="inline-flex shrink-0 items-center">
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        aria-hidden="true"
      >
        {runs.map(({ series: s, segments }) =>
          segments.map((pts, i) =>
            // A single-point run can't draw a line — dot instead.
            pts.length === 1 ? (
              <circle
                key={`${s.name}-${i}`}
                cx={pts[0].x}
                cy={pts[0].y}
                r={1.75}
                fill={s.color}
              />
            ) : (
              <polyline
                key={`${s.name}-${i}`}
                points={pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ")}
                fill="none"
                stroke={s.color}
                strokeWidth={1.5}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            ),
          ),
        )}
      </svg>
      <span className="sr-only">Savings trend: {summary}</span>
    </span>
  );
}
