// F2 — Graph view. 4 recharts charts + partner toggle.
// Chart 1: Salary coverage (stacked bar + salary line)
// Chart 2: Planned vs Actual (grouped bars, future hatched)
// Chart 3: CC usage vs budget (bar + budget line, tone fill)
// Chart 4: Savings balance (cumulative line + delta bars)
// US4: toggle/order key on partner identity + BE slot; legacy payloads
// render a single combined, identity-neutral view + re-sync hint.

import { useMemo, useState } from "react";
import { BarChart3 } from "lucide-react";
import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  ToggleGroup,
  ToggleGroupItem,
} from "@/components/ui/toggle-group";

import { useBillsSourceSubscription } from "@/hooks/useBillsSourceSubscription";
import { getMonths } from "@/lib/bills-source";
import type { F2PartnerIdentity, PartnerEconomy } from "@/types/api";
import {
  byDisplayOrder,
  IDENTITY_NEUTRAL_HINT,
  isIdentityNeutral,
} from "./finance-data";

// Theme hex — match CSS vars in theme.css.
// --income green, --shortfall red, --savings amber, --warning yellow, --partner-a teal, --partner-b violet
const C = {
  income: "hsl(142 52% 36%)",
  shortfall: "hsl(0 72% 51%)",
  savings: "hsl(33 90% 50%)",
  warning: "hsl(48 96% 53%)",
  partnerA: "hsl(189 78% 26%)",
  partnerB: "hsl(262 52% 50%)",
  ccUsage: "hsl(262 52% 50%)",
  grid: "hsl(0 0% 90%)",
  // Neutral fill for identity-neutral mode (legacy payload).
  neutral: "hsl(0 0% 45%)",
};

const fmt = (n: number | null | undefined): string => {
  if (n == null || Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("no-NO", { maximumFractionDigits: 0 }).format(n);
};

const kr = (n: number): string => `${fmt(n)} kr`;

interface ChartRow {
  label: string;
  // Chart 1 — salary coverage (bills + actual cc bill)
  bills: number;
  ccBill: number; // realCcBill ?? estimatedCcBill
  estimatedCcBill: number;
  ccUsage: number;
  estimatedSalary: number;
  // Chart 2 — planned vs actual
  planned: number;
  actual: number | null;
  displayActual: number; // actual ?? planned (so future bars render hatched)
  isFuture: boolean; // actual == null
  // Chart 3 — cc usage vs budget.
  // F2 §8: BE everyday_budget, null on last sync-window month →
  // recharts skips the point/bar for that month.
  budget: number | null;
  // Chart 4 — savings
  savingsBalance: number;
  // F2 §13 revised: null on future / missing live anchor → bar skipped.
  savingsDelta: number | null;
  // raw for tooltips
  realBills: number | null;
  realCcBill: number | null;
}

// Gap row — a month has no entry for this partner identity. Renders as
// zero-filled with null-gated fields left null. Never inferred positionally.
const zeroRow = (label: string): ChartRow => ({
  label,
  bills: 0,
  ccBill: 0,
  estimatedCcBill: 0,
  ccUsage: 0,
  estimatedSalary: 0,
  planned: 0,
  actual: null,
  displayActual: 0,
  isFuture: false,
  budget: null,
  savingsBalance: 0,
  savingsDelta: null,
  realBills: null,
  realCcBill: null,
});

const mapToRow = (p: PartnerEconomy, label: string): ChartRow => ({
  label,
  bills: p.bills,
  ccBill: p.realCcBill ?? p.estimatedCcBill,
  estimatedCcBill: p.estimatedCcBill,
  ccUsage: p.ccUsage,
  estimatedSalary: p.estimatedSalary,
  planned: p.bills + p.estimatedCcBill,
  actual: p.realBills != null && p.realCcBill != null
    ? p.realBills + p.realCcBill
    : null,
  displayActual: p.realBills != null && p.realCcBill != null
    ? p.realBills + p.realCcBill
    : p.bills + p.estimatedCcBill,
  isFuture: !(p.realBills != null && p.realCcBill != null),
  budget: p.budget,
  savingsBalance: p.savingsBalance,
  savingsDelta: p.savingsDelta,
  realBills: p.realBills,
  realCcBill: p.realCcBill,
});

// Savings delta cell fill — exported so tests pin the production mapping
// instead of duplicating it (PR63 review).
export const savingsDeltaFill = (delta: number | null): string =>
  delta == null ? "transparent" : delta >= 0 ? C.income : C.shortfall;

// CC budget tone: green <50%, amber 50-80%, orange 80-100%, red overspent
const ccTone = (usage: number, budget: number | null): string => {
  // Null budget (last sync-window month): gap the budget LINE only —
  // the usage BAR is real data and must stay visible (neutral income tone).
  if (budget == null) return C.income;
  if (budget <= 0) return C.shortfall; // no budget = over by default
  const ratio = usage / budget;
  if (ratio > 1) return C.shortfall; // overspent
  if (ratio >= 0.8) return C.savings; // orange, near limit
  if (ratio >= 0.5) return C.warning; // amber
  return C.income; // green
};

// Tooltip — salary + bills + cc bill + total + delta
const SalaryTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const row: ChartRow = payload[0]?.payload ?? {};
  const total = row.bills + row.ccBill;
  const delta = row.estimatedSalary - total;
  const ccLabel = row.realCcBill != null ? "Real CC bill" : "Est CC bill";
  return (
    <div className="rounded-md border bg-popover p-3 text-xs shadow-md">
      <div className="mb-1 font-semibold">{label}</div>
      <div className="space-y-0.5">
        <div>Salary: <span className="font-medium">{kr(row.estimatedSalary)}</span></div>
        <div>Bills: <span className="font-medium">{kr(row.bills)}</span></div>
        <div>{ccLabel}: <span className="font-medium">{kr(row.ccBill)}</span></div>
        <div className="border-t pt-0.5">Total out: <span className="font-medium">{kr(total)}</span></div>
        <div className={delta >= 0 ? "text-income" : "text-shortfall"}>
          {delta >= 0 ? "Surplus: " : "Shortfall: "}{kr(Math.abs(delta))}
        </div>
      </div>
    </div>
  );
};

// Tooltip — planned + actual + variance
const PlannedTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const row: ChartRow = payload[0]?.payload ?? {};
  const hasActual = row.actual != null;
  const variance = hasActual ? ((row.actual as number) - row.planned) : 0;
  return (
    <div className="rounded-md border bg-popover p-3 text-xs shadow-md">
      <div className="mb-1 font-semibold">{label}</div>
      <div className="space-y-0.5">
        <div>Planned: <span className="font-medium">{kr(row.planned)}</span></div>
        {hasActual ? (
          <>
            <div>Actual: <span className="font-medium">{kr(row.actual ?? 0)}</span></div>
            <div className={variance > 0 ? "text-shortfall" : "text-income"}>
              {variance > 0 ? "Overspent: " : "Underspent: "}{kr(Math.abs(variance))}
            </div>
          </>
        ) : (
          <div className="text-muted-foreground">Actual: not yet (future)</div>
        )}
      </div>
    </div>
  );
};

// Tooltip — cc usage + budget + over/under
const CcTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const row: ChartRow = payload[0]?.payload ?? {};
  const diff = row.ccUsage - (row.budget ?? 0);
  return (
    <div className="rounded-md border bg-popover p-3 text-xs shadow-md">
      <div className="mb-1 font-semibold">{label}</div>
      <div className="space-y-0.5">
        <div>CC usage: <span className="font-medium">{kr(row.ccUsage)}</span></div>
        {/* Null budget (last sync-window month) → "—", no over/under verdict. */}
        <div>Budget: <span className="font-medium">{row.budget != null ? kr(row.budget) : "—"}</span></div>
        {row.budget != null && (
          <div className={diff > 0 ? "text-shortfall" : "text-income"}>
            {diff > 0 ? "Over: " : "Under: "}{kr(Math.abs(diff))}
          </div>
        )}
      </div>
    </div>
  );
};

// Chart 1 — salary coverage stacked + line
function SalaryChart({
  data,
}: {
  data: ChartRow[];
}) {
  return (
    <div>
      <div className="mb-2">
        <h3 className="text-sm font-semibold">Salary coverage</h3>
        <p className="text-xs text-muted-foreground">
          Stacked bars = bills + CC bill (real if past, est if future).
          Line = salary. Bars above line = salary doesn&apos;t cover outflows.
        </p>
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={C.grid} />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => fmt(v)} />
          <Tooltip content={<SalaryTooltip />} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="bills" name="Bills" stackId="a" fill={C.shortfall} />
          <Bar dataKey="ccBill" name="CC bill" stackId="a" fill={C.savings} />
          <Line
            type="monotone"
            dataKey="estimatedSalary"
            name="Salary"
            stroke={C.income}
            strokeWidth={2}
            strokeDasharray="5 5"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

// Combine same-month rows across partners — identity-neutral mode only
// (no per-partner breakdown on legacy payloads). Numeric sums; null-gated
// fields stay null unless every partner carries them.
function combineRows(label: string, parts: ChartRow[]): ChartRow {
  const sum = (pick: (r: ChartRow) => number) =>
    parts.reduce((s, r) => s + pick(r), 0);
  const sumNullable = (pick: (r: ChartRow) => number | null) =>
    parts.length > 0 && parts.every((r) => pick(r) != null)
      ? parts.reduce((s, r) => s + (pick(r) as number), 0)
      : null;
  const actual = sumNullable((r) => r.actual);
  return {
    label,
    bills: sum((r) => r.bills),
    ccBill: sum((r) => r.ccBill),
    estimatedCcBill: sum((r) => r.estimatedCcBill),
    ccUsage: sum((r) => r.ccUsage),
    estimatedSalary: sum((r) => r.estimatedSalary),
    planned: sum((r) => r.planned),
    actual,
    displayActual: actual ?? sum((r) => r.planned),
    isFuture: actual == null,
    budget: sumNullable((r) => r.budget),
    savingsBalance: sum((r) => r.savingsBalance),
    savingsDelta: sumNullable((r) => r.savingsDelta),
    realBills: sumNullable((r) => r.realBills),
    realCcBill: sumNullable((r) => r.realCcBill),
  };
}

// Chart 2 — planned vs actual grouped bars, future hatched
function PlannedChart({ data, neutral = false }: { data: ChartRow[]; neutral?: boolean }) {
  // Per-cell fill: null actual → hatched pattern (defined in defs)
  return (
    <div>
      <div className="mb-2">
        <h3 className="text-sm font-semibold">Planned vs actual spend</h3>
        <p className="text-xs text-muted-foreground">
          Planned = estimated bills + est CC bill. Actual = real bills +
          real CC bill (past months only). Hatched = future projection.
        </p>
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <defs>
            <pattern
              id="hatch-future"
              patternUnits="userSpaceOnUse"
              width={6}
              height={6}
              patternTransform="rotate(45)"
            >
              <rect width={6} height={6} fill="hsl(0 0% 90%)" />
              <line x1="0" y1="0" x2="0" y2={6} stroke="hsl(0 0% 60%)" strokeWidth={1} />
            </pattern>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={C.grid} />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => fmt(v)} />
          <Tooltip content={<PlannedTooltip />} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="planned" name="Planned" fill={neutral ? C.neutral : C.partnerA} radius={[3, 3, 0, 0]} />
          <Bar dataKey="displayActual" name="Actual" radius={[3, 3, 0, 0]}>
            {data.map((row, i) => (
              <Cell
                key={i}
                fill={row.isFuture ? "url(#hatch-future)" : C.income}
              />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

// Chart 3 — cc usage bars + budget line, tone fill per bar
function CcChart({ data }: { data: ChartRow[] }) {
  return (
    <div>
      <div className="mb-2">
        <h3 className="text-sm font-semibold">CC usage vs budget</h3>
        <p className="text-xs text-muted-foreground">
          Bars = real CC card spend. Line = CC budget envelope. Red =
          overspent, orange = 80-100%, amber = 50-80%, green &lt; 50%.
        </p>
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={C.grid} />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => fmt(v)} />
          <Tooltip content={<CcTooltip />} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="ccUsage" name="CC usage" radius={[3, 3, 0, 0]}>
            {data.map((row, i) => (
              <Cell key={i} fill={ccTone(row.ccUsage, row.budget)} />
            ))}
          </Bar>
          <Line
            type="monotone"
            dataKey="budget"
            name="Budget"
            stroke={C.income}
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={{ r: 3, fill: C.income }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

// Chart 4 — savings cumulative line + delta bars
function SavingsChart({ data }: { data: ChartRow[] }) {
  return (
    <div>
      <div className="mb-2">
        <h3 className="text-sm font-semibold">Savings balance</h3>
        <p className="text-xs text-muted-foreground">
          Line = cumulative savings balance. Bars = monthly delta
          (green grew, red drained).
        </p>
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={C.grid} />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => fmt(v)} />
          <Tooltip content={<SavingsTooltip />} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="savingsDelta" name="Monthly delta" radius={[3, 3, 0, 0]}>
            {data.map((row, i) => (
              <Cell
                key={i}
                // Null delta (future / no anchor) → no bar rendered.
                // Recharts skips null values; fill is a fallback only.
                fill={savingsDeltaFill(row.savingsDelta)}
              />
            ))}
          </Bar>
          <Line
            type="monotone"
            dataKey="savingsBalance"
            name="Savings balance"
            stroke={C.savings}
            strokeWidth={2}
            dot={{ r: 3, fill: C.savings }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

// Tooltip — savings balance + delta
const SavingsTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const row: ChartRow = payload[0]?.payload ?? {};
  return (
    <div className="rounded-md border bg-popover p-3 text-xs shadow-md">
      <div className="mb-1 font-semibold">{label}</div>
      <div className="space-y-0.5">
        <div>Balance: <span className="font-medium">{kr(row.savingsBalance)}</span></div>
        {row.savingsDelta != null ? (
          <div className={row.savingsDelta >= 0 ? "text-income" : "text-shortfall"}>
            {row.savingsDelta >= 0 ? "Grew: " : "Drained: "}{kr(Math.abs(row.savingsDelta))}
          </div>
        ) : (
          <div className="text-muted-foreground">Delta: not yet (future)</div>
        )}
      </div>
    </div>
  );
};

export function GraphView(_: { onEventClick?: (eventId: string) => void } = {}) {
  const version = useBillsSourceSubscription();
  const months = useMemo(() => getMonths(), [version]);
  // Partner identities keyed by semantic id, display order by BE slot.
  // Labels are config display strings — never identity.
  const partnerIdentities = useMemo(() => {
    const seen = new Map<string, F2PartnerIdentity>();
    for (const m of months) {
      for (const p of m.partners) {
        const key = p.partner.partner_id;
        if (key !== "" && !seen.has(key)) seen.set(key, p.partner);
      }
    }
    return byDisplayOrder(
      [...seen.values()].map((partner) => ({ partner })),
    ).map((x) => x.partner);
  }, [months]);
  // Legacy payload → identity-neutral: no toggle, combined rows.
  const neutral = useMemo(
    () =>
      months.length > 0 &&
      isIdentityNeutral(months.flatMap((m) => m.partners)),
    [months],
  );
  const [partnerId, setPartnerId] = useState<string | null>(null);
  const selected = partnerId ?? partnerIdentities[0]?.partner_id ?? "";

  // Build chart rows per partner identity. A month lacking the identity
  // renders an explicit zero row — never a positional fallback.
  const rowsByPartner = useMemo(
    () =>
      new Map(
        partnerIdentities.map((identity) => [
          identity.partner_id,
          months.map((m) => {
            const p = m.partners.find(
              (q) => q.partner.partner_id === identity.partner_id,
            );
            return p ? mapToRow(p, m.label) : zeroRow(m.label);
          }),
        ]),
      ),
    [months, partnerIdentities],
  );

  const singleData = useMemo(() => {
    if (!neutral) return rowsByPartner.get(selected) ?? [];
    // Combined rows across all of a month's partners (sums) — legacy
    // payloads get no per-partner breakdown.
    return months.map((m) =>
      combineRows(
        m.label,
        m.partners.map((p) => mapToRow(p, m.label)),
      ),
    );
  }, [neutral, rowsByPartner, selected, months]);

  return (
    <section className="rounded-xl border bg-card p-4 shadow-sm sm:p-6">
      {/* Header + partner toggle */}
      <div className="mb-6 flex flex-col gap-4">
        <div>
          <h2 className="flex items-center gap-2 text-base font-semibold">
            <BarChart3 className="size-4" />
            Monthly economy
          </h2>
          <p className="text-sm text-muted-foreground">
            Salary vs outflows, planned vs actual spend, and CC budget
            adherence across the year
          </p>
        </div>

        {/* Partner toggle keyed by semantic identity — identity mode
            only. Legacy payloads render combined + a hint instead. */}
        {!neutral && partnerIdentities.length > 0 && (
          <ToggleGroup
            type="single"
            value={selected}
            onValueChange={(v) => v && setPartnerId(v)}
            variant="outline"
            spacing={0}
            className="border bg-card p-0.5 shadow-sm w-fit"
          >
            {partnerIdentities.map((identity) => (
              <ToggleGroupItem
                key={identity.partner_id}
                value={identity.partner_id}
                aria-label={`Show ${identity.label}`}
                className="gap-1.5 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground"
              >
                {identity.label}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        )}
        {neutral && (
          <p role="note" className="text-xs text-muted-foreground">
            {IDENTITY_NEUTRAL_HINT}
          </p>
        )}
      </div>

      {/* Charts */}
      <div className="flex flex-col gap-8">
        <SalaryChart data={singleData} />
        <PlannedChart data={singleData} neutral={neutral} />
        <CcChart data={singleData} />
        <SavingsChart data={singleData} />
      </div>
    </section>
  );
}