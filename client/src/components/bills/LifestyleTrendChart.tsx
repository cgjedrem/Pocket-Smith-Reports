import { useId } from "react";
import { CartesianGrid, ComposedChart, Line, ReferenceLine, XAxis, YAxis } from "recharts";
import { ChartContainer, ChartTooltip, type ChartConfig } from "@/components/ui/chart";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatLifestyleMoney as money } from "@/lib/lifestyle-creep";
import { useAmountsHidden } from "@/lib/privacy-store";
import {
  TRAILING_MINIMUM, TRAILING_WINDOW, lifestyleTrend,
  type LifestyleTrendPoint, type LifestyleTrendRow,
} from "@/lib/lifestyle-trend";
import type { LifestyleComparison, MonthlyAmount } from "@/types/lifestyle-creep";

export const TRAILING_AVERAGE_LABEL = "Trailing average (up to 3 prior months)";

const CONFIG = {
  usage: { label: "Monthly net usage", color: "hsl(var(--chart-1))" },
  average: { label: TRAILING_AVERAGE_LABEL, color: "hsl(var(--chart-4))" },
  above: { label: "Above trailing average", color: "hsl(var(--chart-2))" },
} satisfies ChartConfig;

export function trendMonthTick(key: string): string {
  return key.startsWith("gap:") ? "…" : key;
}

interface DotProps {
  cx?: number;
  cy?: number;
  index?: number;
  payload?: LifestyleTrendRow;
}

function UsageDot({ cx, cy, index, payload }: DotProps) {
  if (cx == null || cy == null || payload?.kind !== "sample" || payload.usage === null) {
    return <g key={`usage-dot-${index}`} />;
  }
  return (
    <g key={`usage-dot-${index}`} data-trend-month={payload.month}>
      {payload.isAboveTrailingAverage ? (
        <path
          data-trend-marker="above"
          d={`M${cx},${cy - 7} L${cx + 7},${cy + 5} L${cx - 7},${cy + 5} Z`}
          fill="var(--color-above)" stroke="var(--background, #fff)" strokeWidth={1}
        />
      ) : (
        <circle data-trend-marker="usage" cx={cx} cy={cy} r={3.5} fill="var(--color-usage)" />
      )}
      {payload.isTarget && (
        <rect
          data-trend-marker="target"
          x={cx - 10} y={cy - 10} width={20} height={20}
          fill="none" stroke="currentColor" strokeWidth={1.5}
        />
      )}
    </g>
  );
}

function AverageDot({ cx, cy, index, payload }: DotProps) {
  if (cx == null || cy == null || payload?.kind !== "sample" || payload.average === null) {
    return <g key={`average-dot-${index}`} />;
  }
  return (
    <line
      key={`average-dot-${index}`} data-trend-marker="average"
      x1={cx - 7} x2={cx + 7} y1={cy} y2={cy} stroke="var(--color-average)" strokeWidth={3}
    />
  );
}

function statusText(point: LifestyleTrendPoint): string {
  if (point.trailingAverage === null) {
    return `No trailing average — fewer than ${TRAILING_MINIMUM} consecutive prior months in this evidence`;
  }
  return point.isAboveTrailingAverage ? "Above trailing average (▲)" : "Not above trailing average";
}

function TrendTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload?: LifestyleTrendRow }> }) {
  const row = payload?.[0]?.payload;
  if (!active || row?.kind !== "sample") return null;
  return (
    <div className="grid min-w-48 gap-1 rounded-lg border bg-background px-2.5 py-1.5 text-xs shadow-xl">
      <p className="font-medium">{row.month}{row.isTarget ? " (selected target)" : ""}</p>
      <p>Monthly net usage: {money(row.amount)}</p>
      <p>{TRAILING_AVERAGE_LABEL}: {row.trailingAverage === null ? "not shown" : money(row.trailingAverage)}</p>
      <p>{statusText(row)}</p>
    </div>
  );
}

function Swatch({ kind }: { kind: "usage" | "average" | "above" | "target" }) {
  return (
    <svg aria-hidden="true" width="28" height="14" viewBox="0 0 28 14" className="shrink-0">
      {kind === "usage" && <><line x1="0" x2="28" y1="7" y2="7" stroke="var(--color-usage)" strokeWidth="2" /><circle cx="14" cy="7" r="3.5" fill="var(--color-usage)" /></>}
      {kind === "average" && <><line x1="0" x2="28" y1="7" y2="7" stroke="var(--color-average)" strokeWidth="2" strokeDasharray="6 4" /><line x1="8" x2="20" y1="7" y2="7" stroke="var(--color-average)" strokeWidth="3" /></>}
      {kind === "above" && <path d="M14,1 L21,12 L7,12 Z" fill="var(--color-above)" />}
      {kind === "target" && <rect x="7" y="0.75" width="12.5" height="12.5" fill="none" stroke="currentColor" strokeWidth="1.5" />}
    </svg>
  );
}

interface LifestyleTrendChartProps {
  samples: MonthlyAmount[];
  comparison: Pick<LifestyleComparison, "month">;
  categoryLabel: string;
}

export function LifestyleTrendChart({ samples, comparison, categoryLabel }: LifestyleTrendChartProps) {
  const hidden = useAmountsHidden();
  const captionId = useId();
  const trend = lifestyleTrend(samples, comparison);
  const heading = <p className="font-semibold">Monthly usage over the selected evidence period</p>;

  if (trend.status === "invalid") {
    return (
      <figure aria-labelledby={captionId} data-lifestyle-trend="invalid" className="min-w-0 space-y-2 rounded-md border p-3">
        <figcaption id={captionId}>{heading}</figcaption>
        <p role="status">Graph unavailable: {trend.reason} The comparison above is unchanged.</p>
      </figure>
    );
  }

  const { rows, points, plottable } = trend;
  const above = points.filter((point) => point.isAboveTrailingAverage);
  const firstAverage = points.find((point) => point.trailingAverage !== null);
  const gaps = rows.filter((row) => row.kind === "gap");
  const hasNegative = points.some((point) => (point.usage ?? 0) < 0 || (point.average ?? 0) < 0);
  const graphLabel = `${categoryLabel} monthly usage graph`;

  return (
    <figure
      aria-labelledby={captionId} data-lifestyle-trend={hidden ? "masked" : plottable ? "chart" : "unplottable"}
      className="min-w-0 space-y-3 rounded-md border p-3"
    >
      <figcaption id={captionId} className="space-y-1">
        {heading}
        <p>
          {points.length} evidence months from {points[0]?.month} to {points.at(-1)?.month}, target {comparison.month}.{" "}
          {above.length > 0
            ? `${above.length} of ${points.length} months above their trailing average: ${above.map((point) => point.month).join(", ")}.`
            : "No month is above its trailing average."}
        </p>
      </figcaption>

      {hidden ? (
        <div role="img" aria-label={`${graphLabel} hidden while amounts are hidden`}
          className="rounded-md border border-dashed bg-muted/40 p-4 text-center text-muted-foreground">
          Graph hidden while amounts are hidden. Show amounts to view it; months and above-average markers stay listed below.
        </div>
      ) : !plottable ? (
        <p role="status" className="rounded-md border border-dashed p-3">
          Graph unavailable: an amount is too large or too precise to plot without changing its value. The table below keeps the exact amounts.
        </p>
      ) : (
        <div aria-hidden="true" data-testid="lifestyle-trend-chart">
          <ChartContainer config={CONFIG} className="aspect-auto h-64 w-full" initialDimension={{ width: 640, height: 256 }}>
            <ComposedChart data={rows} margin={{ top: 12, right: 12, left: 4, bottom: 4 }} accessibilityLayer={false}>
              <CartesianGrid vertical={false} strokeDasharray="3 3" />
              <XAxis
                dataKey="key" tickLine={false} axisLine={false} tickMargin={8} fontSize={10}
                tickFormatter={trendMonthTick}
              />
              <YAxis
                tickFormatter={(value: number) => money(String(value))}
                tickLine={false} axisLine={false} width={72} fontSize={10}
              />
              {hasNegative && <ReferenceLine y={0} stroke="currentColor" strokeOpacity={0.4} />}
              <ChartTooltip content={<TrendTooltip />} />
              <Line
                dataKey="usage" name="usage" type="linear" stroke="var(--color-usage)" strokeWidth={2}
                connectNulls={false} isAnimationActive={false} dot={UsageDot} activeDot={false}
              />
              <Line
                dataKey="average" name="average" type="linear" stroke="var(--color-average)" strokeWidth={2}
                strokeDasharray="6 4" connectNulls={false} isAnimationActive={false} dot={AverageDot} activeDot={false}
              />
            </ComposedChart>
          </ChartContainer>
        </div>
      )}

      <ul aria-label="Graph legend" className="flex flex-wrap gap-x-4 gap-y-1 text-xs" style={{
        ["--color-usage" as string]: CONFIG.usage.color,
        ["--color-average" as string]: CONFIG.average.color,
        ["--color-above" as string]: CONFIG.above.color,
      }}>
        <li className="flex items-center gap-1"><Swatch kind="usage" />Solid line with dots: monthly net usage</li>
        <li className="flex items-center gap-1"><Swatch kind="average" />Dashed line with bars: {TRAILING_AVERAGE_LABEL}</li>
        <li className="flex items-center gap-1"><Swatch kind="above" />Triangle: month above its trailing average</li>
        <li className="flex items-center gap-1"><Swatch kind="target" />Square outline: selected target month</li>
      </ul>

      <div className="space-y-1 text-xs text-muted-foreground">
        <p>
          Each month is compared with the arithmetic average of up to {TRAILING_WINDOW} immediately preceding consecutive
          months shown here, excluding the month itself. The average starts once {TRAILING_MINIMUM} prior months exist
          {firstAverage ? ` (first: ${firstAverage.month})` : " — no month in this evidence has that"}; earlier months get no average or marker.
        </p>
        <p>
          A triangle means usage is strictly above that trailing average. It is descriptive only: it is not the applied
          threshold or the reference-period verdict above, and it is not a forecast.
        </p>
        {gaps.map((gap) => (
          <p key={gap.key}>
            {gap.missingMonths} calendar {gap.missingMonths === 1 ? "month" : "months"} between {gap.afterMonth} and{" "}
            {gap.beforeMonth} {gap.missingMonths === 1 ? "is" : "are"} not in the selected evidence: the lines break there
            (not zero), and {gap.beforeMonth} has no trailing average because its preceding months are missing.
          </p>
        ))}
        {hasNegative && <p>Values below zero are net refunds; they are plotted as-is.</p>}
      </div>

      <Table aria-label={`${categoryLabel} graph data`} className="text-xs">
        <TableHeader><TableRow>
          <TableHead scope="col">Month</TableHead>
          <TableHead scope="col">Monthly net usage</TableHead>
          <TableHead scope="col">{TRAILING_AVERAGE_LABEL}</TableHead>
          <TableHead scope="col">Compared with trailing average</TableHead>
        </TableRow></TableHeader>
        <TableBody>
          {points.map((point) => (
            <TableRow key={point.month} data-trend-row={point.month} data-above={point.isAboveTrailingAverage || undefined}>
              <TableHead scope="row">{point.month}{point.isTarget ? " (selected target)" : ""}</TableHead>
              <TableCell className="tabular-nums">{money(point.amount)}</TableCell>
              <TableCell className="tabular-nums">
                {point.trailingAverage === null ? "Not shown" : `${money(point.trailingAverage)} (${point.priorMonths.join(", ")})`}
              </TableCell>
              <TableCell>{statusText(point)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </figure>
  );
}
