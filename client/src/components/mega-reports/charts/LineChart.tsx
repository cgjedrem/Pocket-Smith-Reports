// LineChart — compact raw SVG line chart. No rotated y-axis label, no per-point labels by default.

interface LineChartProps {
  xLabels: string[];
  series: Record<string, (number | null)[]>;
  title: string;
  yLabel?: string;
  width?: number;
  height?: number;
  showValueLabels?: boolean;
}

const COLORS = {
  grid: "#e0e0e0",
  axis: "#888",
  text: "#222",
};

const PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"];

// Compact number format — M/k/integer.
function formatY(v: number): string {
  const a = Math.abs(v);
  if (a >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (a >= 1_000) return `${(v / 1_000).toFixed(0)}k`;
  return `${v.toFixed(0)}`;
}

function autoYBounds(valuesLists: (number | null)[][], padPct = 0.1): [number, number] {
  const all: number[] = [];
  for (const lst of valuesLists) for (const v of lst) if (v !== null) all.push(v);
  if (all.length === 0) return [0, 1];
  const lo = Math.min(...all);
  const hi = Math.max(...all);
  if (lo === hi) {
    return [lo !== 0 ? lo * 0.9 : -1, hi !== 0 ? hi * 1.1 : 1];
  }
  const pad = (hi - lo) * padPct;
  return [lo - pad, hi + pad];
}

export function LineChart({
  xLabels,
  series,
  title,
  yLabel = "NOK",
  width = 380,
  height = 180,
  showValueLabels = false,
}: LineChartProps) {
  if (xLabels.length === 0 || Object.keys(series).length === 0) {
    return <p className="text-sm text-muted-foreground">No data for line chart.</p>;
  }

  const n = xLabels.length;
  // Tighter margins — no rotated y-label, no big legend row, no per-point labels.
  const margin = { top: 30, right: 12, bottom: 30, left: 48 };
  const plotW = width - margin.left - margin.right;
  const plotH = height - margin.top - margin.bottom;

  const xPositions = Array.from(
    { length: n },
    (_, i) => margin.left + (plotW * i) / Math.max(n - 1, 1)
  );

  let [yMin, yMax] = autoYBounds(Object.values(series));
  if (yMax > 0) yMax *= 1.05;
  if (yMin < 0) yMin *= 1.05;

  const yPos = (v: number): number => {
    if (yMax === yMin) return margin.top + plotH / 2;
    return margin.top + plotH * (1 - (v - yMin) / (yMax - yMin));
  };

  const seriesNames = Object.keys(series);
  const rotateX = n > 8 ? -30 : 0;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      preserveAspectRatio="xMidYMid meet"
      style={{ fontFamily: "sans-serif", display: "block", margin: "0 auto", width: "100%", height: "auto", maxWidth: width }}
    >
      <title>{title}</title>

      {/* Title (small, top-left) */}
      <text x={margin.left} y={14} textAnchor="start" fontSize={11} fontWeight="600" fill={COLORS.text}>
        {title}
      </text>

      {/* Inline legend (top-right) */}
      {(() => {
        let lx = width - margin.right;
        return seriesNames.map((name, idx) => {
          const color = PALETTE[idx % PALETTE.length];
          const w = Math.max(50, name.length * 5.5 + 18);
          lx -= w;
          return (
            <g key={`legend-${name}`}>
              <rect x={lx} y={9} width={8} height={8} fill={color} />
              <text x={lx + 12} y={15} fontSize={9} fill={COLORS.text}>{name}</text>
            </g>
          );
        });
      })()}

      {/* Y-axis unit label (horizontal, top-left next to title) — skipped to save space */}

      {/* Grid lines (4) + y tick labels */}
      {Array.from({ length: 5 }, (_, i) => {
        const y = margin.top + (plotH * i) / 4;
        const v = yMax - ((yMax - yMin) * i) / 4;
        return (
          <g key={`grid-${i}`}>
            <line x1={margin.left} y1={y} x2={margin.left + plotW} y2={y} stroke={COLORS.grid} strokeWidth={0.5} />
            <text x={margin.left - 4} y={y + 3} textAnchor="end" fontSize={9} fill={COLORS.axis}>
              {formatY(v)}
            </text>
          </g>
        );
      })}

      {/* X-axis labels (skip some if too many) */}
      {xLabels.map((label, i) => {
        const short = label.length >= 7 ? label.slice(2).replace("-", "/") : label;
        // Densify: show every label if n<=8, else every 2nd.
        if (n > 8 && i % 2 !== 0 && i !== n - 1) return null;
        const x = xPositions[i];
        const yText = margin.top + plotH + 12;
        if (rotateX) {
          return (
            <text
              key={`x-${i}`}
              x={x}
              y={yText}
              textAnchor="end"
              fontSize={9}
              fill={COLORS.axis}
              transform={`rotate(${rotateX} ${x} ${yText})`}
            >
              {short}
            </text>
          );
        }
        return (
          <text key={`x-${i}`} x={x} y={yText} textAnchor="middle" fontSize={9} fill={COLORS.axis}>
            {short}
          </text>
        );
      })}

      {/* Y-axis unit (small, rotated -90 on far left) */}
      <text
        x={12}
        y={margin.top + plotH / 2}
        textAnchor="middle"
        fontSize={9}
        fill={COLORS.axis}
        transform={`rotate(-90 12 ${margin.top + plotH / 2})`}
      >
        {yLabel}
      </text>

      {/* Series lines + dots + optional value labels */}
      {seriesNames.map((name, idx) => {
        const vals = series[name];
        const color = PALETTE[idx % PALETTE.length];
        const pathParts: string[] = [];
        vals.forEach((v, i) => {
          if (v === null) return;
          pathParts.push(`${pathParts.length === 0 ? "M" : "L"} ${xPositions[i].toFixed(1)} ${yPos(v).toFixed(1)}`);
        });
        return (
          <g key={`series-${name}`}>
            {pathParts.length > 0 && (
              <path d={pathParts.join(" ")} fill="none" stroke={color} strokeWidth={1.5} />
            )}
            {vals.map((v, i) => {
              if (v === null) return null;
              const y = yPos(v);
              const labelY = idx === 0 ? y - 6 : y + 12;
              return (
                <g key={`pt-${name}-${i}`}>
                  <circle cx={xPositions[i]} cy={y} r={2.5} fill={color} />
                  {showValueLabels && (
                    <text x={xPositions[i]} y={labelY} textAnchor="middle" fontSize={8} fill={color} fontWeight="bold">
                      {formatY(v)}
                    </text>
                  )}
                </g>
              );
            })}
          </g>
        );
      })}
    </svg>
  );
}
