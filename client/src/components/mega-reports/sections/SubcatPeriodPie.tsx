// SubcatPeriodPie — shadcn Card + ChartContainer + Recharts PieChart.

import { Cell, Pie, PieChart, Tooltip, type PieLabelRenderProps } from "recharts";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ChartContainer,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { formatNOK } from "@/components/mega-reports/sections/helpers";

interface SubcatPeriodPieProps {
  data: Array<{ name: string; value: number }>;
  title: string;
}

const PALETTE = [
  "hsl(204 70% 50%)",
  "hsl(28 80% 52%)",
  "hsl(142 52% 36%)",
  "hsl(0 70% 50%)",
  "hsl(262 52% 50%)",
  "hsl(20 50% 40%)",
  "hsl(330 60% 50%)",
  "hsl(110 40% 45%)",
  "hsl(50 60% 50%)",
  "hsl(190 60% 45%)",
  "hsl(15 70% 55%)",
  "hsl(80 50% 45%)",
  "hsl(240 50% 55%)",
  "hsl(340 50% 50%)",
  "hsl(160 50% 45%)",
  "hsl(45 70% 50%)",
];

export function SubcatPeriodPie({ data, title }: SubcatPeriodPieProps) {
  const sorted = [...data].sort((a, b) => b.value - a.value);
  const total = sorted.reduce((s, d) => s + d.value, 0);

  // Build shadcn ChartConfig so each slice gets a CSS var.
  const config: ChartConfig = {};
  sorted.forEach((d, i) => {
    const key = `slice_${i}`;
    config[key] = { label: d.name, color: PALETTE[i % PALETTE.length] };
  });

  // Add a synthetic row that the pie can read: each slice uses its own data key.
  // Recharts Pie takes `data` as rows + `dataKey` to compute slice sizes.
  // We'll map each row to use its slice_<i> key for color lookups.
  const chartData = sorted.map((d, i) => ({
    sliceKey: `slice_${i}`,
    name: d.name,
    value: d.value,
  }));

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ChartContainer
          config={config}
          className="w-full min-w-0"
          style={{ height: 480 }}
        >
          <PieChart>
            <Pie
              data={chartData}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              outerRadius={180}
              label={({ value }: PieLabelRenderProps) => {
                if (!total || typeof value !== "number") return "";
                const pct = (value / total) * 100;
                return `${pct.toFixed(0)}%`;
              }}
              labelLine={false}
              isAnimationActive={false}
            >
              {chartData.map((d) => (
                <Cell key={d.sliceKey} fill={`var(--color-${d.sliceKey})`} />
              ))}
            </Pie>
            <Tooltip
              content={
                <ChartTooltipContent
                  formatter={(value) =>
                    `${formatNOK(Number(value))} (${
                      total ? ((Number(value) / total) * 100).toFixed(1) : "0"
                    }%)`
                  }
                />
              }
            />
          </PieChart>
        </ChartContainer>
        <div className="flex flex-wrap gap-3 justify-center text-xs pt-2">
          {sorted.map((d, i) => (
            <div key={d.name} className="flex items-center gap-1.5">
              <span
                className="inline-block w-3 h-3 rounded-sm"
                style={{ backgroundColor: PALETTE[i % PALETTE.length] }}
              />
              <span>{d.name}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
