// SubcatStackedBarChart — raw SVG stacked bar. Port of subcat_charts.py render_subcat_stacked_bar().
// Months on x-axis, sub-cats stacked as colored segments. 16-color palette.

interface SubcatStackedBarChartProps {
  months: string[];
  subcatAmounts: Record<string, number[]>;
  title: string;
  width?: number;
  height?: number;
}

const PALETTE = [
  "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b",
  "#e377c2", "#7f7f7f", "#bcbd22", "#17becf", "#aec7e8", "#ffbb78",
  "#98df8a", "#ff9896", "#c5b0d5", "#c49c94",
];

function formatY(v: number): string {
  const a = Math.abs(v);
  if (a >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (a >= 1_000) return `${(v / 1_000).toFixed(0)}k`;
  return `${v.toFixed(0)}`;
}

export function SubcatStackedBarChart({
  months,
  subcatAmounts,
  title,
  width = 760,
  height = 360,
}: SubcatStackedBarChartProps) {
  if (months.length === 0 || Object.keys(subcatAmounts).length === 0) {
    return <p className="text-sm text-muted-foreground">No data for stacked bar.</p>;
  }

  const n = months.length;
  const catNames = Object.keys(subcatAmounts);

  // Month totals + y_max.
  const monthTotals = new Array(n).fill(0);
  for (const cat of catNames) {
    const vals = subcatAmounts[cat];
    for (let i = 0; i < n; i++) {
      monthTotals[i] += vals[i] ?? 0;
    }
  }
  const yMax = Math.max(Math.max(...monthTotals), 1);

  const margin = { top: 50, right: 30, bottom: 110, left: 80 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;
  const barW = (innerW / n) * 0.7;
  const barGap = (innerW / n) * 0.3;
  const nGrid = 5;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      xmlns="http://www.w3.org/2000/svg"
      preserveAspectRatio="xMidYMid meet"
      style={{ display: "block", margin: "0 auto", width: "100%", height: "auto", maxWidth: width }}
    >
      {/* Title */}
      <text x={width / 2} y={20} textAnchor="middle" fontSize={13} fontWeight="bold" fill="#333">
        {title}
      </text>

      {/* Y-axis grid + labels */}
      {Array.from({ length: nGrid + 1 }, (_, i) => {
        const yVal = (yMax * i) / nGrid;
        const yPos = margin.top + innerH - (yVal / yMax) * innerH;
        return (
          <g key={`grid-${i}`}>
            <line x1={margin.left} y1={yPos} x2={margin.left + innerW} y2={yPos} stroke="#e0e0e0" strokeWidth={1} />
            <text x={margin.left - 5} y={yPos + 4} textAnchor="end" fontSize={9} fill="#666">
              {formatY(yVal)}
            </text>
          </g>
        );
      })}

      {/* Stacked bars */}
      {months.map((m, i) => {
        const x = margin.left + i * (innerW / n) + barGap / 2;
        let yOffset = margin.top + innerH; // bottom of bar
        return (
          <g key={`bar-${i}`}>
            {catNames.map((cat, j) => {
              const vals = subcatAmounts[cat];
              const v = vals[i] ?? 0;
              if (v === 0) return null;
              const segH = Math.max(0, (Number(v) / yMax) * innerH);
              const color = PALETTE[j % PALETTE.length];
              yOffset -= segH;
              const textFill = j % 2 === 0 ? "white" : "#333";
              return (
                <g key={`seg-${i}-${j}`}>
                  <rect x={x} y={yOffset} width={barW} height={segH} fill={color} stroke="white" strokeWidth={0.5} />
                  {segH > 14 && (
                    <text x={x + barW / 2} y={yOffset + segH / 2 + 3} textAnchor="middle" fontSize={8} fill={textFill}>
                      {formatY(v)}
                    </text>
                  )}
                </g>
              );
            })}
            {/* X-axis label */}
            {(() => {
              const xLabel = m.length === 7 ? m.slice(2).replace("-", "/") : m;
              const lx = x + barW / 2;
              const ly = margin.top + innerH + 12;
              if (xLabel.length > 8) {
                return (
                  <text
                    x={lx}
                    y={ly}
                    textAnchor="end"
                    fontSize={9}
                    fill="#333"
                    transform={`rotate(-30 ${lx} ${ly})`}
                  >
                    {xLabel}
                  </text>
                );
              }
              return (
                <text x={lx} y={ly + 2} textAnchor="middle" fontSize={9} fill="#333">
                  {xLabel}
                </text>
              );
            })()}
          </g>
        );
      })}

      {/* Y-axis label */}
      <text
        x={margin.left - 60}
        y={margin.top + innerH / 2}
        textAnchor="middle"
        fontSize={10}
        fill="#666"
        transform={`rotate(-90 ${margin.left - 60} ${margin.top + innerH / 2})`}
      >
        NOK
      </text>
    </svg>
  );
}