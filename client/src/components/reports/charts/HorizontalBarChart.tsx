// Horizontal bar chart — raw SVG in JSX. Port of charts.py render_horizontal_bar.
// Sorted by value descending. Auto-shrinks label font to fit the reserve.
// No truncation — full label is always rendered.

interface BarItem {
  label: string;
  value: number;
  color?: string;
}

interface HorizontalBarChartProps {
  data: BarItem[];
  title?: string;
  width?: number;
  barHeight?: number;
  gap?: number;
  ink?: string;
  track?: string;
}

const DEFAULT_COLORS = [
  "#1f77b4",
  "#ff7f0e",
  "#2ca02c",
  "#d62728",
  "#9467bd",
  "#8c564b",
  "#e377c2",
  "#7f7f7f",
  "#bcbd22",
  "#17becf",
];

// Auto-shrink label font so the longest label fits the 220px reserve
// at typical sans-serif glyph widths. Full label is always rendered — no truncation.
const LABEL_RESERVE_CHARS = {
  12: 33,
  11: 36,
  10: 40,
} as const;

function pickLabelFontSize(maxLabelChars: number): number {
  if (maxLabelChars <= LABEL_RESERVE_CHARS[12]) return 12;
  if (maxLabelChars <= LABEL_RESERVE_CHARS[11]) return 11;
  return 10;
}

export function HorizontalBarChart({
  data,
  title,
  width = 680,
  barHeight = 22,
  gap = 6,
  ink = "#222",
  track = "#f0f0f0",
}: HorizontalBarChartProps) {
  // Sort by value descending.
  const sorted = [...data].sort((a, b) => b.value - a.value);
  const total = sorted.reduce((sum, d) => sum + d.value, 0);

  if (total === 0) {
    return (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox={`0 0 ${width} 90`}
        width={width}
        height={90}
        preserveAspectRatio="xMidYMid meet"
        style={{ display: "block", margin: "0 auto" }}
      >
        {title && (
          <text
            x={width / 2}
            y={24}
            textAnchor="middle"
            fontSize={12}
            fontWeight={700}
            fill={ink}
          >
            {title}
          </text>
        )}
        <text
          x={width / 2}
          y={48}
          textAnchor="middle"
          fontSize={10}
          fill="#999"
        >
          No data
        </text>
      </svg>
    );
  }

  // Layout: label | bar track | value+pct.
  const labelW = 220;
  const valueW = 120;
  const barW = width - labelW - valueW - 12;
  const n = sorted.length;
  const chartH = n * (barHeight + gap) + 10;
  const svgH = chartH + (title ? 55 : 10);
  const y0 = title ? 55 : 10;
  const maxLabelChars = sorted.reduce((m, d) => Math.max(m, d.label.length), 0);
  const labelFontSize = pickLabelFontSize(maxLabelChars);

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox={`0 0 ${width} ${svgH}`}
      width={width}
      height={svgH}
      preserveAspectRatio="xMidYMid meet"
      style={{ display: "block", margin: "0 auto" }}
    >
      {title && (
        <text
          x={width / 2}
          y={24}
          textAnchor="middle"
          fontSize={12}
          fontWeight={700}
          fill={ink}
        >
          {title}
        </text>
      )}
      {sorted.map((item, i) => {
        if (item.value <= 0) return null;
        const color = item.color ?? DEFAULT_COLORS[i % DEFAULT_COLORS.length];
        const y = y0 + i * (barHeight + gap);
        const barFillW = (item.value / total) * barW;
        const pct = total > 0 ? (item.value / total) * 100 : 0;
        return (
          <g key={item.label} aria-label={item.label}>
            <title>{item.label}</title>
            <text
              x={labelW - 6}
              y={y + barHeight / 2 + 4}
              textAnchor="end"
              fontSize={labelFontSize}
              fontWeight={400}
              fill={ink}
            >
              {item.label}
            </text>
            <rect
              x={labelW}
              y={y}
              width={barW}
              height={barHeight}
              fill={track}
              rx={1}
            />
            <rect
              x={labelW}
              y={y}
              width={barFillW.toFixed(1)}
              height={barHeight}
              fill={color}
              rx={1}
            />
            <text
              x={labelW + barW + 6}
              y={y + barHeight / 2 + 4}
              fontSize={12}
              fontWeight={800}
              fill={ink}
            >
              {item.value.toLocaleString("en-US", { maximumFractionDigits: 0 })}
              {"  "}
              ({pct.toFixed(1)}%)
            </text>
          </g>
        );
      })}
    </svg>
  );
}