// Donut chart — raw SVG in JSX. Port of charts.py render_donut_single.
// Single-tier donut with on-chart % labels + center text.

interface DonutSlice {
  label: string;
  value: number;
  color: string;
}

interface DonutChartProps {
  data: DonutSlice[];
  title?: string;
  size?: number;
  minPctLabel?: number;
  centerLabel?: string;
  centerValue?: string;
}

// Arc path — SVG path for donut slice.
function arcPath(
  cx: number,
  cy: number,
  rOuter: number,
  rInner: number,
  startAngle: number,
  endAngle: number
): string {
  const a0 = ((startAngle - 90) * Math.PI) / 180;
  const a1 = ((endAngle - 90) * Math.PI) / 180;
  const x0o = cx + rOuter * Math.cos(a0);
  const y0o = cy + rOuter * Math.sin(a0);
  const x1o = cx + rOuter * Math.cos(a1);
  const y1o = cy + rOuter * Math.sin(a1);
  const x0i = cx + rInner * Math.cos(a0);
  const y0i = cy + rInner * Math.sin(a0);
  const x1i = cx + rInner * Math.cos(a1);
  const y1i = cy + rInner * Math.sin(a1);
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  return (
    `M ${x0o.toFixed(2)} ${y0o.toFixed(2)} ` +
    `A ${rOuter} ${rOuter} 0 ${largeArc} 1 ${x1o.toFixed(2)} ${y1o.toFixed(2)} ` +
    `L ${x1i.toFixed(2)} ${y1i.toFixed(2)} ` +
    `A ${rInner} ${rInner} 0 ${largeArc} 0 ${x0i.toFixed(2)} ${y0i.toFixed(2)} Z`
  );
}

export function DonutChart({
  data,
  title,
  size = 600,
  minPctLabel = 0.04,
  centerLabel,
  centerValue,
}: DonutChartProps) {
  const cx = size / 2;
  const cy = size / 2;
  const rOuter = size / 2 - 30;
  const rInner = Math.floor(rOuter * 0.5);

  const total = data.reduce((sum, d) => sum + d.value, 0);

  if (total === 0) {
    return (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox={`0 0 ${size} ${size}`}
        width={size}
        height={size}
      >
        {title && (
          <text
            x={cx}
            y={34}
            textAnchor="middle"
            fontSize={20}
            fontWeight={600}
            fill="#222"
          >
            {title}
          </text>
        )}
        <text
          x={cx}
          y={cy}
          textAnchor="middle"
          fontSize={22}
          fill="#999"
        >
          No data
        </text>
      </svg>
    );
  }

  let angle = 0;
  const slices: React.ReactNode[] = [];
  data.forEach((d, i) => {
    if (d.value <= 0) return;
    const sweep = (d.value / total) * 360;
    const endAngle = angle + sweep;
    const path = arcPath(cx, cy, rOuter, rInner, angle, endAngle);
    slices.push(
      <path
        key={`slice-${i}`}
        d={path}
        fill={d.color}
        stroke="white"
        strokeWidth={1.5}
      />
    );
    const pct = d.value / total;
    if (pct >= minPctLabel) {
      const midAngle = (angle + endAngle) / 2;
      const tx = cx + rOuter * 0.75 * Math.cos((midAngle * Math.PI) / 180 - Math.PI / 2);
      const ty = cy + rOuter * 0.75 * Math.sin((midAngle * Math.PI) / 180 - Math.PI / 2);
      slices.push(
        <text
          key={`label-${i}`}
          x={tx.toFixed(1)}
          y={ty.toFixed(1)}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize={14}
          fontWeight={600}
          fill="white"
        >
          {(pct * 100).toFixed(0)}%
        </text>
      );
    }
    angle = endAngle;
  });

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox={`0 0 ${size} ${size}`}
      width={size}
      height={size}
    >
      {title && (
        <text
          x={cx}
          y={34}
          textAnchor="middle"
          fontSize={20}
          fontWeight={600}
          fill="#222"
        >
          {title}
        </text>
      )}
      {slices}
      {centerLabel && (
        <text
          x={cx}
          y={cy - 12}
          textAnchor="middle"
          fontSize={14}
          fill="#666"
        >
          {centerLabel}
        </text>
      )}
      <text
        x={cx}
        y={cy + 16}
        textAnchor="middle"
        fontSize={26}
        fontWeight={700}
        fill="#222"
      >
        {centerValue ?? total.toLocaleString("en-US", { maximumFractionDigits: 0 })}
      </text>
    </svg>
  );
}