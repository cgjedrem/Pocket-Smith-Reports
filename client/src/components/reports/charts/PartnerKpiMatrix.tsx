// Partner KPI matrix — raw SVG in JSX. Port of charts.py render_partner_kpi_matrix.
// Three fixed-position KPI comparisons in one chart. Rail style (minimal theme).

interface MatrixRow {
  label: string;
  value: number;
  color: string;
}

interface MatrixSeries {
  title: string;
  data: MatrixRow[];
}

interface PartnerKpiMatrixProps {
  series: MatrixSeries[];
  width?: number;
}

// Theme colors — minimal theme.
const THEME = {
  ink: "#19303d",
  muted: "#5d6c75",
  rule: "#d8e3ec",
  track: "#e7eef3",
};

export function PartnerKpiMatrix({ series, width = 720 }: PartnerKpiMatrixProps) {
  const columnWidth = (width - 56) / series.length;
  const barWidth = columnWidth - 32;
  const height = 225;

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
    >
      {series.map((col, column) => {
        const left = 28 + column * columnWidth;
        const scale =
          Math.max(...col.data.map((d) => Math.abs(d.value)), 0) || 1;
        const shareTotal = col.data.reduce((s, d) => s + Math.abs(d.value), 0);

        return (
          <g key={col.title}>
            <text
              x={left.toFixed(1)}
              y={30}
              fontSize={17}
              fontWeight={400}
              fill={THEME.ink}
            >
              {col.title}
            </text>
            <line
              x1={left.toFixed(1)}
              y1={42}
              x2={(left + columnWidth - 18).toFixed(1)}
              y2={42}
              stroke={THEME.rule}
              strokeWidth={1}
            />
            {col.data.map((row, index) => {
              const y = 60 + index * 72;
              const share =
                shareTotal > 0 ? (Math.abs(row.value) / shareTotal) * 100 : 0;
              const fillWidth = (Math.abs(row.value) / scale) * barWidth;
              return (
                <g key={row.label}>
                  <circle
                    cx={left + 5}
                    cy={y + 5}
                    r={5}
                    fill={row.color}
                  />
                  <text
                    x={left + 17}
                    y={y + 10}
                    fontSize={13}
                    fontWeight={400}
                    fill={THEME.ink}
                  >
                    {row.label}
                  </text>
                  <rect
                    x={left.toFixed(1)}
                    y={y + 22}
                    width={barWidth.toFixed(1)}
                    height={14}
                    rx={7}
                    fill={THEME.track}
                  />
                  <rect
                    x={left.toFixed(1)}
                    y={y + 22}
                    width={fillWidth.toFixed(1)}
                    height={14}
                    rx={7}
                    fill={row.color}
                  />
                  <text
                    x={left.toFixed(1)}
                    y={y + 57}
                    fontSize={15}
                    fontWeight={400}
                    fill={THEME.ink}
                  >
                    {row.value.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                  </text>
                  <text
                    x={(left + barWidth).toFixed(1)}
                    y={y + 57}
                    textAnchor="end"
                    fontSize={13}
                    fontWeight={400}
                    fill={THEME.muted}
                  >
                    {share.toFixed(1)}%
                  </text>
                </g>
              );
            })}
          </g>
        );
      })}
    </svg>
  );
}