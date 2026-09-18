// StackedBarLineChart — compact raw SVG stacked bar + cumulative line. No rotated y-axis labels, no per-point value labels by default.

interface StackedBarLineChartProps {
  months: string[];
  partnerA: number[];
  partnerB: number[];
  cumulative: number[];
  title: string;
  yLabel?: string;
  width?: number;
  height?: number;
  showValueLabels?: boolean;
  showPct?: boolean;
  partnerALabel?: string;
  partnerBLabel?: string;
}

const COLORS = {
  partner_a: "#1f77b4",
  partner_b: "#ff7f0e",
  cumulative: "#2ca02c",
  grid: "#e0e0e0",
  axis: "#888",
  text: "#222",
  bar_label: "#fff",
};

function formatY(v: number): string {
  const a = Math.abs(v);
  if (a >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (a >= 1_000) return `${(v / 1_000).toFixed(0)}k`;
  return `${v.toFixed(0)}`;
}

function paddedBounds(low: number, high: number): [number, number] {
  const span = high - low;
  if (span === 0) return [-1, 1];
  return [low - span * 0.08, high + span * 0.08];
}

export function StackedBarLineChart({
  months,
  partnerA,
  partnerB,
  cumulative,
  title,
  yLabel = "NOK",
  width = 760,
  height = 240,
  showValueLabels = false,
  showPct = false,
  partnerALabel = "Partner A",
  partnerBLabel = "Partner B",
}: StackedBarLineChartProps) {
  const n = months.length;
  if (
    n === 0 ||
    partnerA.length !== n ||
    partnerB.length !== n ||
    cumulative.length !== n
  ) {
    return <p className="text-sm text-muted-foreground">No data for stacked bar chart.</p>;
  }

  // Tighter margins — no rotated y-labels, no big legend row.
  const margin = { top: 32, right: 48, bottom: 32, left: 48 };
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;

  const barValues = [...partnerA, ...partnerB].map((v) => v || 0);
  const lineValues = cumulative.map((v) => v || 0);
  const barMin = Math.min(0, ...barValues);
  const barMax = Math.max(0, ...barValues);
  const lineMin = Math.min(0, ...lineValues);
  const lineMax = Math.max(0, ...lineValues);

  const [yMinBar, yMaxBar] = paddedBounds(barMin, barMax);
  const [yMinLine, yMaxLine] = paddedBounds(lineMin, lineMax);

  const yBar = (v: number): number =>
    margin.top + plotH - ((v - yMinBar) / (yMaxBar - yMinBar)) * plotH;
  const yLine = (v: number): number =>
    margin.top + plotH - ((v - yMinLine) / (yMaxLine - yMinLine)) * plotH;

  const barW = (plotW / n) * 0.7;
  const barGap = (plotW / n) * 0.3;
  const nTicks = 4;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      preserveAspectRatio="xMidYMid meet"
      style={{ fontFamily: "sans-serif", display: "block", margin: "0 auto", width: "100%", height: "auto", maxWidth: width }}
    >
      <title>{title}</title>

      {/* Title (top-left) */}
      <text x={margin.left} y={14} textAnchor="start" fontSize={11} fontWeight="600" fill={COLORS.text}>
        {title}
      </text>

      {/* Inline legend (top-right) */}
      {(() => {
        const items: Array<{ name: string; color: string; line: boolean }> = [
          { name: partnerALabel, color: COLORS.partner_a, line: false },
          { name: partnerBLabel, color: COLORS.partner_b, line: false },
          { name: "Cumulative", color: COLORS.cumulative, line: true },
        ];
        const widths = items.map((it) => Math.max(50, it.name.length * 5.5 + 18));
        const total = widths.reduce((a, b) => a + b, 0);
        const startX = width - margin.right - total;
        return items.map((item, i) => {
          const x = startX + widths.slice(0, i).reduce((a, b) => a + b, 0);
          return (
            <g key={`legend-${i}`}>
              {item.line ? (
                <line x1={x} y1={13} x2={x + 10} y2={13} stroke={item.color} strokeWidth={1.5} />
              ) : (
                <rect x={x} y={9} width={8} height={8} fill={item.color} opacity={0.85} />
              )}
              <text x={x + 14} y={13} fontSize={9} fill={COLORS.text}>{item.name}</text>
            </g>
          );
        });
      })()}

      {/* Left y-axis grid + labels (bars) */}
      {Array.from({ length: nTicks + 1 }, (_, i) => {
        const y = margin.top + plotH - (i / nTicks) * plotH;
        const v = yMinBar + ((yMaxBar - yMinBar) * i) / nTicks;
        return (
          <g key={`grid-${i}`}>
            <line x1={margin.left} y1={y} x2={margin.left + plotW} y2={y} stroke={COLORS.grid} strokeWidth={0.5} />
            <text x={margin.left - 4} y={y + 3} textAnchor="end" fontSize={9} fill={COLORS.axis}>
              {formatY(v)}
            </text>
          </g>
        );
      })}

      {/* Right y-axis labels (cumulative, smaller, vertical line breaks) */}
      {Array.from({ length: nTicks + 1 }, (_, i) => {
        const y = margin.top + plotH - (i / nTicks) * plotH;
        const v = yMinLine + ((yMaxLine - yMinLine) * i) / nTicks;
        return (
          <text key={`rgrid-${i}`} x={margin.left + plotW + 4} y={y + 3} textAnchor="start" fontSize={9} fill={COLORS.cumulative}>
            {formatY(v)}
          </text>
        );
      })}

      {/* Zero baseline */}
      <line x1={margin.left} y1={yBar(0)} x2={margin.left + plotW} y2={yBar(0)} stroke={COLORS.axis} strokeWidth={1} />

      {/* Bars */}
      {months.map((m, i) => {
        const c = partnerA[i] || 0;
        const r = partnerB[i] || 0;
        const x = margin.left + i * (barW + barGap) + barGap / 2;
        let posStack = 0;
        let negStack = 0;
        let cStart: number, cEnd: number;
        if (c >= 0) {
          cStart = posStack;
          cEnd = posStack + c;
          posStack = cEnd;
        } else {
          cStart = negStack;
          cEnd = negStack + c;
          negStack = cEnd;
        }
        let rStart: number, rEnd: number;
        if (r >= 0) {
          rStart = posStack;
          rEnd = posStack + r;
          posStack = rEnd;
        } else {
          rStart = negStack;
          rEnd = negStack + r;
          negStack = rEnd;
        }
        const cYStart = yBar(cStart);
        const cYEnd = yBar(cEnd);
        const rYStart = yBar(rStart);
        const rYEnd = yBar(rEnd);
        const aH = Math.abs(cYEnd - cYStart);
        const bH = Math.abs(rYEnd - rYStart);
        const aY = Math.min(cYStart, cYEnd);
        const bY = Math.min(rYStart, rYEnd);
        return (
          <g key={`bar-${i}`}>
            <rect x={x} y={aY} width={barW} height={aH} fill={COLORS.partner_a} opacity={0.85} />
            <rect x={x} y={bY} width={barW} height={bH} fill={COLORS.partner_b} opacity={0.85} />
            {/* X-axis tick label (skip some if too many) */}
            {((n <= 8 || i % 2 === 0 || i === n - 1)) && (
              <text
                x={x + barW / 2}
                y={margin.top + plotH + 12}
                textAnchor="middle"
                fontSize={9}
                fill={COLORS.axis}
              >
                {m.slice(2).replace("-", "/")}
              </text>
            )}
            {/* Per-bar value labels — only when showValueLabels */}
            {showValueLabels && aH > 14 && (
              <text x={x + barW / 2} y={aY + aH / 2 + 3} textAnchor="middle" fontSize={8} fill={COLORS.bar_label}>
                {formatY(c)}
              </text>
            )}
            {showValueLabels && bH > 14 && (
              <text x={x + barW / 2} y={bY + bH / 2 + 3} textAnchor="middle" fontSize={8} fill={COLORS.bar_label}>
                {formatY(r)}
              </text>
            )}
          </g>
        );
      })}

      {/* Cumulative line + points */}
      {(() => {
        const points = cumulative.map((cv, i) => {
          const x = margin.left + i * (barW + barGap) + barGap / 2 + barW / 2;
          const y = yLine(cv || 0);
          return `${x.toFixed(1)},${y.toFixed(1)}`;
        });
        return (
          <>
            <polyline points={points.join(" ")} fill="none" stroke={COLORS.cumulative} strokeWidth={1.5} />
            {cumulative.map((cv, i) => {
              const x = margin.left + i * (barW + barGap) + barGap / 2 + barW / 2;
              const y = yLine(cv || 0);
              return (
                <circle key={`cum-${i}`} cx={x} cy={y} r={2.5} fill={COLORS.cumulative} />
              );
            })}
          </>
        );
      })()}

      {/* Axis unit labels (tiny, top corners) */}
      <text x={margin.left - 4} y={margin.top - 4} textAnchor="end" fontSize={8} fill={COLORS.axis}>
        {yLabel}
      </text>
      <text x={margin.left + plotW + 4} y={margin.top - 4} textAnchor="start" fontSize={8} fill={COLORS.cumulative}>
        {yLabel} (cum)
      </text>
    </svg>
  );
}
