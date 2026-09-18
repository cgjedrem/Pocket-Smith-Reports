// TrendLineChart — shadcn Chart + Recharts line chart for one or more series.

import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";

import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { cn } from "@/lib/utils";

interface TrendLineChartProps {
  // rows: [{ month: "2025-08", partnerA: 1234, partnerB: 5678, Household: 6912 }, ...]
  rows: Array<Record<string, number | string>>;
  // seriesKeys: list of series keys to render (in order).
  seriesKeys: string[];
  // colors per series (must match the keys in `config`).
  config: ChartConfig;
  // xAxis key (default "month").
  xKey?: string;
  // Optional y-axis formatter (e.g. currency compact).
  yFormatter?: (v: number) => string;
  // Optional height (default 180).
  height?: number;
  // ClassName passthrough.
  className?: string;
}

export function TrendLineChart({
  rows,
  seriesKeys,
  config,
  xKey = "month",
  yFormatter = (v) => v.toString(),
  height = 180,
  className,
}: TrendLineChartProps) {
  return (
    <ChartContainer
      config={config}
      className={cn("w-full", className)}
      style={{ height }}
    >
      <LineChart
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
        <YAxis
          tickFormatter={(v: number) => yFormatter(v)}
          tickLine={false}
          axisLine={false}
          width={42}
          fontSize={10}
        />
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
        {seriesKeys.map((key) => (
          <Line
            key={key}
            dataKey={key}
            type="linear"
            stroke={`var(--color-${key})`}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 3 }}
          />
        ))}
      </LineChart>
    </ChartContainer>
  );
}
