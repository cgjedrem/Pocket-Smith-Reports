// TrendBarLineChart — shadcn Chart + Recharts stacked bar + secondary line.

import {
  Bar,
  CartesianGrid,
  ComposedChart,
  LabelList,
  Line,
  XAxis,
  YAxis,
} from "recharts";

import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { cn } from "@/lib/utils";

interface TrendBarLineChartProps {
  rows: Array<Record<string, number | string>>;
  // Bar series stacked (rendered as <Bar> with stackId="bar").
  barKeys: string[];
  // Line series overlay (rendered as <Line> with yAxisId="right").
  lineKeys: string[];
  config: ChartConfig;
  xKey?: string;
  yFormatter?: (v: number) => string;
  height?: number;
  className?: string;
  // Show % share of monthly total on each bar segment.
  showPct?: boolean;
}

export function TrendBarLineChart({
  rows,
  barKeys,
  lineKeys,
  config,
  xKey = "month",
  yFormatter = (v) => v.toString(),
  height = 280,
  className,
  showPct = false,
}: TrendBarLineChartProps) {
  return (
    <ChartContainer
      config={config}
      className={cn("w-full", className)}
      style={{ height }}
    >
      <ComposedChart
        data={rows}
        margin={{ top: 8, right: 12, left: 0, bottom: 0 }}
      >
        <CartesianGrid vertical={false} strokeDasharray="3 3" />
        <XAxis
          dataKey={xKey}
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          fontSize={10}
        />
        {/* Left axis: bars (NOK) */}
        <YAxis
          yAxisId="left"
          tickFormatter={(v: number) => yFormatter(v)}
          tickLine={false}
          axisLine={false}
          width={50}
          fontSize={10}
        />
        {/* Right axis: line (cumulative NOK) */}
        {lineKeys.length > 0 && (
          <YAxis
            yAxisId="right"
            orientation="right"
            tickFormatter={(v: number) => yFormatter(v)}
            tickLine={false}
            axisLine={false}
            width={50}
            fontSize={10}
          />
        )}
        <ChartTooltip
          content={
            <ChartTooltipContent
              labelFormatter={(value) => value}
              formatter={(value, name) => [
                config[String(name)]?.label ?? String(name),
                yFormatter(Number(value)),
              ]}
            />
          }
        />
        <ChartLegend content={<ChartLegendContent />} />
        {barKeys.map((key) => (
          <Bar
            key={key}
            dataKey={key}
            stackId="bar"
            fill={`var(--color-${key})`}
            radius={[2, 2, 0, 0]}
          >
            {showPct && (
              <LabelList
                dataKey={key}
                position="center"
                content={({ x, y, width, height, value, index }: any) => {
                  if (value == null) return null;
                  const r = rows[index ?? 0] as Record<string, number>;
                  const total = barKeys.reduce(
                    (s, k) => s + (Number(r?.[k]) || 0),
                    0,
                  );
                  if (!total) return null;
                  const pct = ((Number(value) / total) * 100).toFixed(0);
                  if (Number(pct) < 8) return null; // skip tiny slices
                  return (
                    <text
                      x={(x as number) + (width as number) / 2}
                      y={(y as number) + (height as number) / 2}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      fill="white"
                      fontSize={10}
                      style={{ pointerEvents: "none" }}
                    >
                      {pct}%
                    </text>
                  );
                }}
              />
            )}
          </Bar>
        ))}
        {lineKeys.map((key) => (
          <Line
            key={key}
            dataKey={key}
            yAxisId="right"
            type="monotone"
            stroke={`var(--color-${key})`}
            strokeWidth={2}
            dot={{ r: 3, fill: `var(--color-${key})` }}
            activeDot={{ r: 5 }}
          />
        ))}
      </ComposedChart>
    </ChartContainer>
  );
}
