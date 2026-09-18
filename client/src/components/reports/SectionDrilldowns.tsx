// Per-category transaction drill-downs for the detailed report sections.
// Restored PR5 (monthly-reports-logic-migration): PR3 dropped them when the
// server DTO took over the tables — smoke testing showed the UX lost.
// Ported verbatim from pre-PR3 DetailedSections.tsx
// (feature/mr-logic-pr1-contracts). Data source: report.normalized_transactions
// only, routed to sections by detailed_section_mapping.category_sections.
// Strictly presentational: grouping + sorting txns for display only — all row
// sums/totals come from the detailed.* DTO tables above; these list txns
// as-is, formatted. Uses shared SCSS classes (.drilldown, .drilldown-card,
// .tx-table).

import { useState } from "react";

import type { DetailedSection } from "@/types/category_mappings";
import type { ReportResponse } from "@/types/report";

export function fmt(value: number): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

// Normalized transaction shape — from contract.
// id is number from PS API, but TS type is loose for safety.
export interface NormTxn {
  id: string | number | null;
  date: string;
  amount: number;
  payee: string | null;
  note: string | null;
  account_id: string;
  account_name: string | null;
  owner: string;
  category_path: Array<{ id: string; title: string }>;
  is_transfer: boolean;
}

// Raw mapping shape — category leaf id -> detailed section key.
export interface DetailedSectionMapping {
  category_sections?: Record<string, string>;
  account_roles?: Record<string, string>;
}

// Income section — combines income_salary + income_third_party.
const INCOME_SECTIONS: DetailedSection[] = ["income_salary", "income_third_party"];

export function readMapping(
  raw: ReportResponse["detailed_section_mapping"]
): DetailedSectionMapping | null {
  return raw as DetailedSectionMapping | null;
}

// Transfers keep their section only when mapped to home/savings/excluded;
// all other transfers route to "excluded" — mirrors _routed_section in
// accounting.py so drilldowns agree with the section tables.
const TRANSFER_KEEP_SECTIONS = new Set(["home", "savings", "excluded"]);

// Group txns by detailed section via the mapping. Unmapped leaves -> "common"
// (old fallback, verbatim).
export function groupTxnsBySection(
  txns: NormTxn[],
  mapping: DetailedSectionMapping | null
): Record<string, NormTxn[]> {
  const groups: Record<string, NormTxn[]> = {};
  for (const t of txns) {
    const leafId = t.category_path[t.category_path.length - 1]?.id;
    const mapped = mapping?.category_sections?.[leafId] ?? "common";
    const section =
      t.is_transfer && !TRANSFER_KEEP_SECTIONS.has(mapped) ? "excluded" : mapped;
    if (!groups[section]) groups[section] = [];
    groups[section].push(t);
  }
  return groups;
}

// Income txns — both income_salary + income_third_party.
export function incomeTxnsOf(sectionTxns: Record<string, NormTxn[]>): NormTxn[] {
  return INCOME_SECTIONS.flatMap((s) => sectionTxns[s] ?? []);
}

// Shared txn sort — date asc, then id asc (stable order across sections).
function sortTxns(txns: NormTxn[]): NormTxn[] {
  return [...txns].sort((a, b) => {
    const da = a.date ?? "";
    const db = b.date ?? "";
    if (da !== db) return da.localeCompare(db);
    return String(a.id ?? "").localeCompare(String(b.id ?? ""));
  });
}

// Category group — shared shape for legacy sections.
interface CategoryGroup {
  title: string;
  paid: { partner_a: number; partner_b: number };
  received: { partner_a: number; partner_b: number };
  records: NormTxn[];
}

// Group txns by leaf category — CLI _legacy_category_groups. paid/received
// sums retained only for the net-desc sort the old UI used; the drilldown
// renders records as-is (sums for display come from detailed.* rows above).
function legacyCategoryGroups(txns: NormTxn[]): CategoryGroup[] {
  const groups: Record<string, CategoryGroup> = {};
  for (const t of txns) {
    const cat = t.category_path[t.category_path.length - 1];
    const root = t.category_path[0];
    const catTitle = root.id === cat.id ? cat.title : `${root.title} / ${cat.title}`;
    const g = groups[cat.id] ?? {
      title: catTitle,
      paid: { partner_a: 0, partner_b: 0 },
      received: { partner_a: 0, partner_b: 0 },
      records: [],
    };
    g.records.push(t);
    const owner = t.owner as "partner_a" | "partner_b";
    if (t.amount < 0) g.paid[owner] += Math.abs(t.amount);
    else g.received[owner] += Math.abs(t.amount);
    groups[cat.id] = g;
  }
  // Sort by total abs amount descending — CLI pattern.
  return Object.values(groups).sort(
    (a, b) =>
      -(a.paid.partner_a + a.paid.partner_b - a.received.partner_a - a.received.partner_b) +
      (b.paid.partner_a + b.paid.partner_b - b.received.partner_a - b.received.partner_b)
  );
}

// Per-category expandable drilldown for a section's txns. Null when empty.
interface SectionDrilldownProps {
  txns: NormTxn[];
}

export function SectionDrilldown({ txns }: SectionDrilldownProps) {
  const groups = legacyCategoryGroups(txns);
  if (groups.length === 0) return null;
  return <LegacyDrilldown groups={groups} />;
}

// Legacy drilldown — per-category expandable details. Port of CLI _legacy_drilldown.
interface LegacyDrilldownProps {
  groups: CategoryGroup[];
}

export function LegacyDrilldown({ groups }: LegacyDrilldownProps) {
  return (
    <>
      {groups.map((g) => {
        const total = g.records.reduce((sum, r) => sum + Math.abs(r.amount), 0);
        const sorted = sortTxns(g.records);
        return (
          <details key={g.title} className="drilldown">
            <summary style={{ cursor: "pointer" }}>
              <b>{g.title}</b> - {fmt(total)} NOK - {g.records.length} txns
            </summary>
            <table className="tx-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Payee</th>
                  <th>Account</th>
                  <th>Note</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((r, i) => (
                  <tr key={`${r.date}-${r.payee}-${i}`}>
                    <td>{r.date}</td>
                    <td>{r.payee ?? ""}</td>
                    <td>{r.account_name ?? ""}</td>
                    <td>{r.note ?? ""}</td>
                    <td>
                      {r.amount >= 0 ? "+" : ""}
                      {fmt(r.amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        );
      })}
    </>
  );
}

// Drilldown card — expandable transaction table (used by IncomeSection).
interface DrilldownCardProps {
  txns: NormTxn[];
  paLabel: string;
}

export function DrilldownCard({ txns, paLabel }: DrilldownCardProps) {
  const [open, setOpen] = useState(false);
  if (txns.length === 0) return null;

  const sorted = sortTxns(txns);

  return (
    <div className="drilldown-card">
      <details open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
        <summary style={{ cursor: "pointer", fontWeight: 600 }}>
          Transaction details ({txns.length})
        </summary>
        {open && (
          <table className="tx-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Payee</th>
                <th>Account</th>
                <th>Note</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((r, i) => (
                <tr key={`${r.date}-${r.payee}-${i}`}>
                  <td>{r.date}</td>
                  <td>{r.payee ?? "Unspecified"}</td>
                  <td>{r.account_name ?? paLabel}</td>
                  <td>{r.note ?? "-"}</td>
                  <td>
                    {r.amount >= 0 ? "+" : ""}
                    {fmt(r.amount)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </details>
    </div>
  );
}

// Savings drilldowns — one open card per category (leaf TITLE grouping,
// always visible, not <details>) — verbatim from pre-PR3 SavingsSection.
interface SavingsDrilldownProps {
  txns: NormTxn[];
  paLabel: string;
}

export function SavingsDrilldown({ txns, paLabel }: SavingsDrilldownProps) {
  const groups: Record<string, NormTxn[]> = {};
  for (const t of txns) {
    const title = t.category_path[t.category_path.length - 1]?.title ?? "Unknown";
    if (!groups[title]) groups[title] = [];
    groups[title].push(t);
  }
  return (
    <>
      {Object.entries(groups).map(([title, groupTxns]) => {
        const total = groupTxns.reduce((sum, t) => sum + Math.abs(t.amount), 0);
        const sorted = sortTxns(groupTxns);
        return (
          <div key={title} className="drilldown-card">
            <h3>
              {title} - {fmt(total)} NOK - {groupTxns.length} txns
            </h3>
            <table className="tx-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Payee</th>
                  <th>Account</th>
                  <th>Note</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((r, i) => (
                  <tr key={`${r.date}-${r.payee}-${i}`}>
                    <td>{r.date}</td>
                    <td>{r.payee ?? "Unspecified"}</td>
                    <td>{r.account_name ?? paLabel}</td>
                    <td>{r.note ?? "-"}</td>
                    <td>
                      {r.amount >= 0 ? "+" : ""}
                      {fmt(r.amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </>
  );
}

// CC payments drilldown — "CC payment details" card. Only negative-amount
// txns (payments out); Paid column shows abs.
interface CcPaymentsDrilldownProps {
  txns: NormTxn[];
  paLabel: string;
}

export function CcPaymentsDrilldown({ txns, paLabel }: CcPaymentsDrilldownProps) {
  const payments = txns.filter((t) => t.amount < 0);
  if (payments.length === 0) return null;

  const sorted = sortTxns(payments);

  return (
    <div className="drilldown-card">
      <details>
        <summary style={{ cursor: "pointer", fontWeight: 600 }}>CC payment details</summary>
        <table className="tx-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Payee</th>
              <th>Account</th>
              <th>Paid</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r, i) => (
              <tr key={`${r.date}-${r.payee}-${i}`}>
                <td>{r.date}</td>
                <td>{r.payee ?? "Unspecified"}</td>
                <td>{r.account_name ?? paLabel}</td>
                <td>{fmt(Math.abs(r.amount))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}
