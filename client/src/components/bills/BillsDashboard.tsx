// F2 — top-level dashboard. 3-view toggle (Grid/Graph/Table). Read-only.
// View + expanded month are mirrored to query params (?view=, ?expandedKey=).

import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { BarChart3, LayoutGrid, Table2 } from "lucide-react";

import {
  ToggleGroup,
  ToggleGroupItem,
} from "@/components/ui/toggle-group";

import { byDisplayOrder, isIdentityNeutral } from "./finance-data";
import { GraphView } from "./GraphView";
import { MonthCard } from "./MonthCard";
import type { SparklineSeries } from "./SavingsSparkline";
import { TableView } from "./TableView";
import { useBillsSourceSubscription } from "@/hooks/useBillsSourceSubscription";
import { getMonths } from "@/lib/bills-source";
import type { F2PartnerIdentity } from "@/types/api";

type View = "grid" | "graph" | "table";

// Invalid/missing params fall back to the default ("grid").
function parseView(raw: string | null): View {
  return raw === "graph" || raw === "table" ? raw : "grid";
}

export function BillsDashboard({
  onEventClick,
}: {
  onEventClick?: (eventId: string) => void;
} = {}) {
  const version = useBillsSourceSubscription();
  const months = useMemo(() => getMonths(), [version]);
  const [searchParams, setSearchParams] = useSearchParams();
  const [view, setViewState] = useState<View>(() =>
    parseView(searchParams.get("view")),
  );
  const [expandedKey, setExpandedKey] = useState<string | null>(() => {
    const fromUrl = searchParams.get("expandedKey");
    return fromUrl && months.some((m) => m.key === fromUrl)
      ? fromUrl
      : (months[0]?.key ?? null);
  });

  // Savings trajectory per partner across the loaded window — index-aligned
  // with `months`, null where a partner is missing from a month. Feeds the
  // sparkline in every month card header. Identity-neutral payloads (legacy)
  // → single combined neutral series; no per-partner breakdown, no
  // positional inference.
  const savingsSeries = useMemo<SparklineSeries[]>(() => {
    const allPartners = months.flatMap((m) => m.partners);
    if (allPartners.length === 0) return [];
    if (isIdentityNeutral(allPartners)) {
      return [
        {
          name: "Savings",
          color: "var(--color-muted-foreground)",
          values: months.map((m) =>
            m.partners.reduce((sum, p) => sum + p.savingsBalance, 0),
          ),
        },
      ];
    }
    const identities = new Map<string, F2PartnerIdentity>();
    for (const p of allPartners) {
      if (!identities.has(p.partner.partner_id)) {
        identities.set(p.partner.partner_id, p.partner);
      }
    }
    return byDisplayOrder(
      [...identities.values()].map((partner) => ({ partner })),
    ).map(({ partner }) => ({
      name: partner.label,
      color:
        partner.partner_slot === "a"
          ? "var(--color-partner-a)"
          : "var(--color-partner-b)",
      values: months.map(
        (m) =>
          m.partners.find(
            (p) => p.partner.partner_id === partner.partner_id,
          )?.savingsBalance ?? null,
      ),
    }));
  }, [months]);

  const handleViewChange = (v: View) => {
    setViewState(v);
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (v === "grid") next.delete("view");
        else next.set("view", v);
        return next;
      },
      { replace: true },
    );
  };

  const handleToggleMonth = (key: string) => {
    const nextKey = expandedKey === key ? null : key;
    setExpandedKey(nextKey);
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (nextKey) next.set("expandedKey", nextKey);
        else next.delete("expandedKey");
        return next;
      },
      { replace: true },
    );
  };

  return (
    <main className="mx-auto w-full max-w-5xl">
      {/* View toggle — read-only, no add/edit/delete actions. */}
      <header className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <ToggleGroup
          type="single"
          value={view}
          onValueChange={(v) => v && handleViewChange(v as View)}
          variant="outline"
          spacing={0}
          className="border bg-card p-0.5 shadow-sm"
        >
          <ToggleGroupItem
            value="grid"
            aria-label="Grid view"
            className="gap-1.5 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground"
          >
            <LayoutGrid className="size-4" />
            Grid
          </ToggleGroupItem>
          <ToggleGroupItem
            value="graph"
            aria-label="Graph view"
            className="gap-1.5 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground"
          >
            <BarChart3 className="size-4" />
            Graph
          </ToggleGroupItem>
          <ToggleGroupItem
            value="table"
            aria-label="Table view"
            className="gap-1.5 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground"
          >
            <Table2 className="size-4" />
            Table
          </ToggleGroupItem>
        </ToggleGroup>
      </header>

      {/* View body */}
      {view === "grid" && (
        <div className="flex flex-col gap-3">
          {months.map((month) => (
            <MonthCard
              key={month.key}
              month={month}
              expanded={expandedKey === month.key}
              onToggle={() => handleToggleMonth(month.key)}
              onEventClick={onEventClick}
              savingsSeries={savingsSeries}
            />
          ))}
        </div>
      )}
      {view === "graph" && <GraphView onEventClick={onEventClick} />}
      {view === "table" && (
        <TableView onEventClick={onEventClick} />
      )}
    </main>
  );
}