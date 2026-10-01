// Detailed sections — presentation only. Every row/total/percentage/sign
// class arrives pre-computed on report.detailed (server DTO — see
// src/budget_api/models/reports.py + src/v4_pipeline/accounting.py section
// builders). No grouping, category aggregation, paired-reimbursement
// matching, or percent math happens here (PR3 of
// monthly-reports-logic-migration — see docs/design/monthly-reports-logic-migration.md).
//
// Per-transaction drill-downs under each section are restored in PR5 via
// SectionDrilldowns.tsx (verbatim port of the pre-PR3 code): they read
// `normalized_transactions` routed by `detailed_section_mapping`, additive
// display only — every table row/total still comes from `detailed.*` DTOs.
// Uses shared SCSS classes (.legacy-section, .legacy-table, .legacy-total,
// .drilldown, .drilldown-card, .tx-table).

import { Fragment, useMemo, type ReactNode } from "react";

import { HorizontalBarChart } from "@/components/reports/charts/HorizontalBarChart";
import {
  CcPaymentsDrilldown,
  DrilldownCard,
  fmt,
  groupTxnsBySection,
  incomeTxnsOf,
  readMapping,
  SavingsDrilldown,
  SectionDrilldown,
  type NormTxn,
} from "@/components/reports/SectionDrilldowns";
import { SIGN_CLASS, signOf } from "@/components/reports/signClasses";
import { detailedSectionLabel, type DetailedSection } from "@/types/category_mappings";
import type {
  CcPaymentsSection as CcPaymentsSectionDto,
  DetailedSavingsSection as DetailedSavingsSectionDto,
  ExcludedSection as ExcludedSectionDto,
  IncomeRow,
  IncomeSection as IncomeSectionDto,
  NetSection as NetSectionDto,
  PairedReimbursementRow as PairedReimbursementRowDto,
  PersonalSection as PersonalSectionDto,
  ReportResponse,
  SavingsPartnerRow,
  SignClass,
  SplitSection as SplitSectionDto,
} from "@/types/report";

// Percent cell — null denominator (division by 0 server-side) -> em-dash,
// never a fabricated 0%.
function pct(value: number | null): string {
  return value === null ? "—" : `${value.toFixed(1)}%`;
}

function cls(signClass: SignClass): string {
  return SIGN_CLASS[signClass];
}

// Paired-reimbursement cells preserve the old UI's explicit +/- prefix
// ("+500.00" / "-500.00"); fmt() alone drops the leading "+".
function fmtSigned(value: number): string {
  return (value > 0 ? "+" : "") + fmt(value);
}

interface DetailedSectionsProps {
  report: ReportResponse;
}

export function DetailedSections({ report }: DetailedSectionsProps) {
  const detailed = report.detailed;
  const paLabel = report.partner_labels.partner_a;
  const pbLabel = report.partner_labels.partner_b;

  // Drill-down grouping — txns routed to sections by the mapping (display
  // only; section tables read detailed.*). Memoized on the raw inputs.
  const txns = report.normalized_transactions as unknown as NormTxn[];
  const mapping = readMapping(report.detailed_section_mapping);
  const sectionTxns = useMemo(() => groupTxnsBySection(txns, mapping), [txns, mapping]);
  const incomeTxns = useMemo(() => incomeTxnsOf(sectionTxns), [sectionTxns]);

  if (!detailed) {
    return (
      <div>
        <h3>Detailed Sections</h3>
        <p className="empty" role="status">
          Detailed sections unavailable. Regenerate this report to view section detail.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h3>Detailed Sections</h3>

      <IncomeSection
        section={detailed.income}
        paLabel={paLabel}
        pbLabel={pbLabel}
        drilldown={<DrilldownCard txns={incomeTxns} paLabel={paLabel} />}
      />

      <SavingsSection
        section={detailed.savings}
        paLabel={paLabel}
        pbLabel={pbLabel}
        drilldown={<SavingsDrilldown txns={sectionTxns["savings"] ?? []} paLabel={paLabel} />}
      />

      <NetSection
        num="3"
        title="Home"
        section={detailed.home}
        paLabel={paLabel}
        pbLabel={pbLabel}
        drilldown={<SectionDrilldown txns={sectionTxns["home"] ?? []} />}
      />

      <NetSection
        num="4"
        title="Common"
        section={detailed.common}
        paLabel={paLabel}
        pbLabel={pbLabel}
        chartTitle="Common spending by category"
        drilldown={<SectionDrilldown txns={sectionTxns["common"] ?? []} />}
      />

      <PersonalSection
        num="5"
        partnerLabel={paLabel}
        paLabel={paLabel}
        pbLabel={pbLabel}
        section={detailed.personal_partner_a}
        drilldown={<SectionDrilldown txns={sectionTxns["personal_partner_a"] ?? []} />}
      />

      <PersonalSection
        num="6"
        partnerLabel={pbLabel}
        paLabel={paLabel}
        pbLabel={pbLabel}
        section={detailed.personal_partner_b}
        drilldown={<SectionDrilldown txns={sectionTxns["personal_partner_b"] ?? []} />}
      />

      <NetSection
        num="7"
        title="Trips (Common + Personal)"
        section={detailed.trips}
        paLabel={paLabel}
        pbLabel={pbLabel}
        chartTitle="Trips spending by category"
        drilldown={<SectionDrilldown txns={sectionTxns["trips"] ?? []} />}
      />

      <CcPaymentsSection
        section={detailed.cc_payments}
        paLabel={paLabel}
        pbLabel={pbLabel}
        drilldown={<CcPaymentsDrilldown txns={sectionTxns["cc_payments"] ?? []} paLabel={paLabel} />}
      />

      <ExcludedSection
        section={detailed.excluded}
        paLabel={paLabel}
        pbLabel={pbLabel}
        drilldown={<SectionDrilldown txns={sectionTxns["excluded"] ?? []} />}
      />

      <CommonEconomySplitSection section={detailed.split ?? null} paLabel={paLabel} pbLabel={pbLabel} />
    </div>
  );
}

// 1. Income — salary vs third-party split.
interface IncomeSectionProps {
  section: IncomeSectionDto | null;
  paLabel: string;
  pbLabel: string;
  drilldown?: ReactNode;
}

function IncomeSection({ section, paLabel, pbLabel, drilldown }: IncomeSectionProps) {
  if (!section) {
    return (
      <section className="report-section legacy-section">
        <h2>1. Income</h2>
        <p className="empty" role="status">No income this month.</p>
      </section>
    );
  }

  const row = (label: string, r: IncomeRow) => (
    <tr key={label}>
      <td>{label}</td>
      <td className={cls(r.partner_a_class)}>{fmt(r.partner_a)}</td>
      <td className={cls(r.partner_b_class)}>{fmt(r.partner_b)}</td>
      <td className={cls(r.total_class)}>
        <b>{fmt(r.total)}</b>
      </td>
      <td>
        <b>{pct(r.row_pct_partner_a)}</b>
      </td>
      <td>
        <b>{pct(r.row_pct_partner_b)}</b>
      </td>
      <td>
        <b>{pct(r.household_pct)}</b>
      </td>
    </tr>
  );

  return (
    <section className="report-section legacy-section">
      <h2>1. Income</h2>
      <table className="legacy-table income-table">
        <thead>
          <tr>
            <th>Source</th>
            <th>{paLabel}</th>
            <th>{pbLabel}</th>
            <th>Total</th>
            <th>% {paLabel}</th>
            <th>% {pbLabel}</th>
            <th>% of income</th>
          </tr>
        </thead>
        <tbody>
          {row("Salary", section.salary)}
          {row("Third Party Income", section.third_party)}
          <tr className="legacy-total">
            <td>Total Income</td>
            <td className={cls(section.total_partner_a_class)}>{fmt(section.total_partner_a)}</td>
            <td className={cls(section.total_partner_b_class)}>{fmt(section.total_partner_b)}</td>
            <td className={cls(section.total_income_class)}>{fmt(section.total_income)}</td>
            {/* Total row has no row_pct fields in the DTO (only per-source rows do). */}
            <td>—</td>
            <td>—</td>
            <td>100.0%</td>
          </tr>
        </tbody>
      </table>
      {drilldown}
    </section>
  );
}

// 2. Savings — to savings (in) / from savings (out) / net saved / income / rate.
interface SavingsSectionProps {
  section: DetailedSavingsSectionDto | null;
  paLabel: string;
  pbLabel: string;
  drilldown?: ReactNode;
}

function SavingsSection({ section, paLabel, pbLabel, drilldown }: SavingsSectionProps) {
  const row = (label: string, r: SavingsPartnerRow, isTotal = false) => (
    <tr key={label} className={isTotal ? "legacy-total" : undefined}>
      <td>{label}</td>
      <td className={cls(r.to_savings_class)}>{fmt(r.to_savings)}</td>
      <td className={cls(r.from_savings_class)}>{fmt(r.from_savings)}</td>
      <td className={cls(r.net_saved_class)}>
        <b>{fmt(r.net_saved)}</b>
      </td>
      <td className={cls(r.income_class)}>{fmt(r.income)}</td>
      <td>{pct(r.rate)}</td>
    </tr>
  );

  return (
    <section className="report-section legacy-section">
      <h2>2. Savings</h2>
      <table className="legacy-table savings-table">
        <thead>
          <tr>
            <th>Partner</th>
            <th>To savings (in)</th>
            <th>From savings (out)</th>
            <th>Net saved</th>
            <th>Income</th>
            <th>Savings rate</th>
          </tr>
        </thead>
        <tbody>
          {!section && (
            <tr>
              <td colSpan={6} role="status">
                Savings summary unavailable. Regenerate this report to view savings values.
              </td>
            </tr>
          )}
          {section && (
            <>
              {row(paLabel, section.partner_a)}
              {row(pbLabel, section.partner_b)}
              {row("Household", section.household, true)}
            </>
          )}
        </tbody>
      </table>
      {drilldown}
    </section>
  );
}

// 3/4/7. Net sections — Home, Common, Trips. Per-category net in ONE table:
// each category row is immediately followed by its paired reimbursement rows
// (class "reimb-row", signed +/- amounts — mirrors the HTML renderer).
interface NetSectionProps {
  num: string;
  title: string;
  section: NetSectionDto | null;
  paLabel: string;
  pbLabel: string;
  chartTitle?: string;
  drilldown?: ReactNode;
}

function NetSection({
  num,
  title,
  section,
  paLabel,
  pbLabel,
  chartTitle,
  drilldown,
}: NetSectionProps) {
  if (!section || (section.rows.length === 0 && section.paired_reimbursements.length === 0)) {
    return (
      <section className="report-section legacy-section">
        <h2>
          {num}. {title}
        </h2>
        <p className="empty">No data this month.</p>
      </section>
    );
  }

  const chartData = section.rows
    .filter((r) => r.total > 0)
    .map((r) => ({ label: r.category_title, value: r.total }));

  // v8 DTO: pairs nested per category row. Stored v7 reports only carry the
  // section-level flattened list — fall back to rendering it after all
  // category rows, still inside the main table.
  const hasNested = section.rows.some((r) => (r.paired_reimbursements?.length ?? 0) > 0);

  const reimbRow = (r: PairedReimbursementRowDto, key: string) => (
    <tr key={key} className="reimb-row">
      <td>
        <i>{r.category_title} (paired reimbursement)</i>
      </td>
      <td className={cls(r.partner_a_class)}>{fmtSigned(r.partner_a)}</td>
      <td className={cls(r.partner_b_class)}>{fmtSigned(r.partner_b)}</td>
      <td className={cls(r.total_class)}>
        <b>{fmt(r.total)}</b>
      </td>
      <td />
    </tr>
  );

  return (
    <section className="report-section legacy-section">
      <h2>
        {num}. {title}
      </h2>
      <table className="legacy-table net-table">
        <thead>
          <tr>
            <th>Category</th>
            <th>{paLabel} net</th>
            <th>{pbLabel} net</th>
            <th>Total</th>
            <th>
              % {paLabel} / {pbLabel}
            </th>
          </tr>
        </thead>
        <tbody>
          {section.rows.map((r) => (
            <Fragment key={r.category_title}>
              <tr>
                <td>{r.category_title}</td>
                <td className={cls(r.partner_a_net_class)}>{fmt(r.partner_a_net)}</td>
                <td className={cls(r.partner_b_net_class)}>{fmt(r.partner_b_net)}</td>
                <td className={cls(r.total_class)}>
                  <b>{fmt(r.total)}</b>
                </td>
                <td>
                  <b>
                    {pct(r.g_share_partner_a)} / {pct(r.g_share_partner_b)}
                  </b>
                </td>
              </tr>
              {(r.paired_reimbursements ?? []).map((p, i) =>
                reimbRow(p, `${r.category_title}-reimb-${i}`),
              )}
            </Fragment>
          ))}
          {!hasNested &&
            section.paired_reimbursements.map((r, i) => reimbRow(r, `section-reimb-${i}`))}
          <tr className="legacy-total">
            <td>Total</td>
            <td className={cls(section.total_partner_a_class)}>{fmt(section.total_partner_a)}</td>
            <td className={cls(section.total_partner_b_class)}>{fmt(section.total_partner_b)}</td>
            <td className={cls(section.total_class)}>{fmt(section.total)}</td>
            <td>
              {pct(section.share_partner_a)} / {pct(section.share_partner_b)}
            </td>
          </tr>
        </tbody>
      </table>
      {chartTitle && chartData.length > 0 && (
        <div className="legacy-chart">
          <HorizontalBarChart data={chartData} title={chartTitle} />
        </div>
      )}
      {drilldown}
    </section>
  );
}

// 5/6. Personal sections — partner A / partner B.
interface PersonalSectionProps {
  num: string;
  partnerLabel: string;
  paLabel: string;
  pbLabel: string;
  section: PersonalSectionDto | null;
  drilldown?: ReactNode;
}

function PersonalSection({
  num,
  partnerLabel,
  paLabel,
  pbLabel,
  section,
  drilldown,
}: PersonalSectionProps) {
  const title = `${num}. ${partnerLabel} personal spending`;

  if (!section || section.rows.length === 0) {
    return (
      <section className="report-section legacy-section">
        <h2>{title}</h2>
        <p className="empty">No personal spending this month.</p>
      </section>
    );
  }

  const chartData = section.rows
    .filter((r) => r.total > 0)
    .map((r) => ({ label: r.category_title, value: r.total }));

  // FIX 1 (PR5): Subtotal = this section's own row-total sum, not the shared
  // personal_total (combined across both partners — PR4 parity bug). null on
  // pre-PR5 stored reports -> fall back to personal_total; class falls back
  // to signOf (same convention as kpis net_cash_class).
  const subtotal = section.subtotal ?? section.personal_total;
  const subtotalClass = section.subtotal_class ?? signOf(subtotal);

  return (
    <section className="report-section legacy-section">
      <h2>{title}</h2>
      <table className="legacy-table personal-table">
        <thead>
          <tr>
            <th>Category</th>
            <th>{paLabel} paid</th>
            <th>{pbLabel} paid</th>
            <th>Total</th>
            <th>% of personal</th>
            <th>% of total spending</th>
          </tr>
        </thead>
        <tbody>
          {section.rows.map((r) => (
            <tr key={r.category_title}>
              <td>{r.category_title}</td>
              <td className={cls(r.paid_partner_a_class)}>{fmt(r.paid_partner_a)}</td>
              <td className={cls(r.paid_partner_b_class)}>{fmt(r.paid_partner_b)}</td>
              <td className={cls(r.total_class)}>
                <b>{fmt(r.total)}</b>
              </td>
              <td>
                <b>{pct(r.pct_personal)}</b>
              </td>
              <td>
                <b>{pct(r.pct_household)}</b>
              </td>
            </tr>
          ))}
          <tr className="legacy-total">
            <td>Subtotal</td>
            <td></td>
            <td></td>
            <td className={cls(subtotalClass)}>{fmt(subtotal)}</td>
            <td>{pct(section.pct_personal)}</td>
            <td>{pct(section.pct_household)}</td>
          </tr>
        </tbody>
      </table>
      {chartData.length > 0 && (
        <div className="legacy-chart">
          <HorizontalBarChart data={chartData} title={`${partnerLabel} personal by category`} />
        </div>
      )}
      {drilldown}
    </section>
  );
}

// 8. CC payments — per-owner paid sums.
interface CcPaymentsSectionProps {
  section: CcPaymentsSectionDto | null;
  paLabel: string;
  pbLabel: string;
  drilldown?: ReactNode;
}

function CcPaymentsSection({ section, paLabel, pbLabel, drilldown }: CcPaymentsSectionProps) {
  if (!section) {
    return (
      <section className="report-section legacy-section">
        <h2>8. CC Payments</h2>
        <p className="empty">No CC payments this month.</p>
      </section>
    );
  }

  return (
    <section className="report-section legacy-section">
      <h2>8. CC Payments</h2>
      <table className="legacy-table cc-payment-table">
        <thead>
          <tr>
            <th>Owner</th>
            <th>CC paid</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>{paLabel}</td>
            <td className={cls(section.partner_a_paid_class)}>{fmt(section.partner_a_paid)}</td>
          </tr>
          <tr>
            <td>{pbLabel}</td>
            <td className={cls(section.partner_b_paid_class)}>{fmt(section.partner_b_paid)}</td>
          </tr>
          <tr className="legacy-total">
            <td>Household</td>
            <td className={cls(section.household_paid_class)}>{fmt(section.household_paid)}</td>
          </tr>
        </tbody>
      </table>
      {drilldown}
    </section>
  );
}

// 9. Excluded categories — paid-only, no net column.
interface ExcludedSectionProps {
  section: ExcludedSectionDto | null;
  paLabel: string;
  pbLabel: string;
  drilldown?: ReactNode;
}

function ExcludedSection({ section, paLabel, pbLabel, drilldown }: ExcludedSectionProps) {
  if (!section || section.rows.length === 0) {
    return (
      <section className="report-section legacy-section">
        <h2>9. Excluded categories</h2>
        <p className="empty">No excluded categories this month.</p>
      </section>
    );
  }

  return (
    <section className="report-section legacy-section">
      <h2>9. Excluded categories</h2>
      <table className="legacy-table excluded-table">
        <thead>
          <tr>
            <th>Category</th>
            <th>{paLabel} paid</th>
            <th>{pbLabel} paid</th>
            <th>Total</th>
          </tr>
        </thead>
        <tbody>
          {section.rows.map((r) => (
            <tr key={r.category_title}>
              <td>{r.category_title}</td>
              <td className={cls(r.paid_partner_a_class)}>{fmt(r.paid_partner_a)}</td>
              <td className={cls(r.paid_partner_b_class)}>{fmt(r.paid_partner_b)}</td>
              <td className={cls(r.total_class)}>{fmt(r.total)}</td>
            </tr>
          ))}
          <tr className="legacy-total">
            <td>Total Excluded</td>
            <td></td>
            <td></td>
            <td className={cls(section.total_class)}>{fmt(section.total)}</td>
          </tr>
        </tbody>
      </table>
      <p className="note">Only categories explicitly mapped to Excluded appear here.</p>
      {drilldown}
    </section>
  );
}

// 10. Common economy split (calculation_version 9, additive). Per-category
// actual/fair/delta (partner_a) + actual_b/fair_b/delta_b (partner_b,
// additive complement columns) + a grand-totals row as the table's LAST
// row (across all section groups, not per group). The settlement sentence
// ("X pays Y …") is RESTORED (user request 2026-10-01) BELOW the table,
// after the totals row — totals row keeps the numeric who-owes-who
// signal, the sentence spells it out in words. Mirrors the backend twin
// restoration (accounting_html.py::_legacy_split_section), but keeps the
// original React wording/direction ("{from} pays {to} {amount}") — NOT
// the backend's "Settlement: {from} owes {to} N." phrasing. Omit the
// whole section — no block, no em-dash
// placeholder — when split is null/undefined (feature off, no config, or
// a stored v7/v8 payload that predates the field). Never fabricate a
// table with no underlying data.
//
// Rows group under a per-section subheading (row.section, category-level
// split selection Gate 2 — a category can now live in any detailed
// section, not just home/common/trips) using the same section->label
// resolver the category-mapping editor uses (detailedSectionLabel —
// personal_partner_a/b render "Personal — {label}", everything else
// renders its raw section key verbatim; mirrors that existing convention,
// doesn't invent a new one). Group order follows `section.sections`
// (server-canonical order); any row whose section is somehow missing from
// that list still renders, appended in first-seen order (defensive, not
// expected given the backend contract).
interface CommonEconomySplitSectionProps {
  section: SplitSectionDto | null;
  // partner_a's real display label — rows are partner_a's perspective
  // (see compute_split() docstring); backend HTML/PDF twin
  // (accounting_html.py::_legacy_split_section) labels these same 3
  // columns "{label_a} actual/fair share/delta" using
  // partner_labels["partner_a"], not the settlement (settlement can be
  // null when already even). Mirror that here.
  paLabel: string;
  // partner_b's real display label — resolves the "Personal — {label}"
  // subheading for personal_partner_b groups AND labels the b-side
  // actual/fair share/delta columns (HTML twin: label_b, same 3-column
  // pattern mirrored for partner_b).
  pbLabel: string;
}

// b-side (actual_b/fair_b/delta_b) cell helpers — null/undefined on
// stored CALCULATION_VERSION=9 rows persisted before the b-side columns
// existed (backend Optional[float] = None, see SplitCategoryRow docstring
// in reports.py). Em-dash, never a fabricated 0 — same convention as
// pct() above.
function fmtB(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : fmt(value);
}
function fmtSignedB(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : fmtSigned(value);
}
function clsB(value: number | null | undefined): string {
  return value === null || value === undefined ? "" : cls(signOf(value));
}

// Group rows by row.section, ordered per section.sections (server-
// canonical order) with any stray section appended in first-seen order.
// row.section is null on stored v9 rows (predates the derived section key,
// calculation_version 10) — group those under a fallback heading; the
// report is stale+regenerable, so this only needs to not crash.
const UNKNOWN_SPLIT_SECTION = "unknown";
function groupSplitRows(
  section: SplitSectionDto,
): { key: string; rows: SplitSectionDto["rows"] }[] {
  const bySection = new Map<string, SplitSectionDto["rows"]>();
  for (const row of section.rows) {
    const key = row.section ?? UNKNOWN_SPLIT_SECTION;
    const list = bySection.get(key) ?? [];
    list.push(row);
    bySection.set(key, list);
  }
  const order = [...section.sections];
  for (const key of bySection.keys()) {
    if (!order.includes(key)) order.push(key);
  }
  return order.filter((key) => bySection.has(key)).map((key) => ({ key, rows: bySection.get(key)! }));
}

// Totals-only float-dust snap: |v| < half-cent → 0, so a balanced split's
// delta total never prints "-0.00". Data rows untouched. Twin of backend
// accounting_html.py::_split_total_cell.
function snapDust(value: number): number {
  return Math.abs(value) < 0.005 ? 0 : value;
}

// Raw-sum one split column across every row. Any null/undefined
// contributor (stale stored v9 rows, b-side fields) → null → the totals
// cell renders em-dash, never a fabricated 0 (same convention as fmtB).
function sumSplitColumn(
  rows: SplitSectionDto["rows"],
  key: "actual" | "fair" | "delta" | "actual_b" | "fair_b" | "delta_b",
): number | null {
  let sum = 0;
  for (const row of rows) {
    const value = row[key];
    if (value === null || value === undefined) return null;
    sum += value;
  }
  return sum;
}

function CommonEconomySplitSection({ section, paLabel, pbLabel }: CommonEconomySplitSectionProps) {
  if (!section) return null;

  const groups = groupSplitRows(section);
  const partnerLabels = { partner_a: paLabel, partner_b: pbLabel };
  // Grand totals across ALL groups — summed once from ungrouped rows,
  // snapped, formatted with the same formatters as the data rows.
  const totals = {
    actual: sumSplitColumn(section.rows, "actual"),
    fair: sumSplitColumn(section.rows, "fair"),
    delta: sumSplitColumn(section.rows, "delta"),
    actual_b: sumSplitColumn(section.rows, "actual_b"),
    fair_b: sumSplitColumn(section.rows, "fair_b"),
    delta_b: sumSplitColumn(section.rows, "delta_b"),
  };
  const totalActual = totals.actual === null ? null : snapDust(totals.actual);
  const totalFair = totals.fair === null ? null : snapDust(totals.fair);
  const totalDelta = totals.delta === null ? null : snapDust(totals.delta);
  const totalActualB = totals.actual_b === null ? null : snapDust(totals.actual_b);
  const totalFairB = totals.fair_b === null ? null : snapDust(totals.fair_b);
  const totalDeltaB = totals.delta_b === null ? null : snapDust(totals.delta_b);

  // Settlement sentence below the totals row — original React wording
  // ("{from} pays {to} {fmt(amount)}"), restored verbatim from the
  // pre-removal rendering. settlement is null when balanced (real rows →
  // original em-dash wording "—") or when there is nothing to settle
  // (zero rows → render NOTHING; never fabricate a 0.00 transfer).
  // Backend twin says "owes" / "Settlement: — (already even)." — not
  // mirrored: React surface keeps its own phrasing.
  const settlement = section.settlement;
  const settlementText = settlement
    ? `${settlement.from_partner} pays ${settlement.to_partner} ${fmt(settlement.amount)}`
    : section.rows.length > 0
      ? "—"
      : null;

  return (
    <section className="report-section legacy-section">
      <h2>10. Common Economy Split</h2>
      <table className="legacy-table split-table">
        <thead>
          <tr>
            <th>Category</th>
            <th>{paLabel} actual</th>
            <th>{paLabel} fair share</th>
            <th>{paLabel} delta</th>
            <th>{pbLabel} actual</th>
            <th>{pbLabel} fair share</th>
            <th>{pbLabel} delta</th>
          </tr>
        </thead>
        <tbody>
          {section.rows.length === 0 ? (
            <tr>
              <td colSpan={7} role="status">
                No categories in the selected split sections this month.
              </td>
            </tr>
          ) : (
            <>
              {groups.map((group) => (
              <Fragment key={group.key}>
                <tr className="split-section-heading">
                  <td colSpan={7}>
                    {detailedSectionLabel(group.key as DetailedSection, partnerLabels)}
                  </td>
                </tr>
                {group.rows.map((r) => (
                  <tr key={r.category_id}>
                    <td>{r.label}</td>
                    <td className={cls(signOf(r.actual))}>{fmt(r.actual)}</td>
                    <td className={cls(signOf(r.fair))}>{fmt(r.fair)}</td>
                    <td className={cls(signOf(r.delta))}>{fmtSigned(r.delta)}</td>
                    <td className={clsB(r.actual_b)}>{fmtB(r.actual_b)}</td>
                    <td className={clsB(r.fair_b)}>{fmtB(r.fair_b)}</td>
                    <td className={clsB(r.delta_b)}>{fmtSignedB(r.delta_b)}</td>
                  </tr>
                ))}
              </Fragment>
              ))}
              {/* Grand totals — LAST row of the table, across all groups
                  (not per group). Uses the table's existing .legacy-total
                  idiom (same class as every other section's totals row). */}
              <tr className="legacy-total">
                <td>Total</td>
                <td className={clsB(totalActual)}>{fmtB(totalActual)}</td>
                <td className={clsB(totalFair)}>{fmtB(totalFair)}</td>
                <td className={clsB(totalDelta)}>{fmtSignedB(totalDelta)}</td>
                <td className={clsB(totalActualB)}>{fmtB(totalActualB)}</td>
                <td className={clsB(totalFairB)}>{fmtB(totalFairB)}</td>
                <td className={clsB(totalDeltaB)}>{fmtSignedB(totalDeltaB)}</td>
              </tr>
            </>
          )}
        </tbody>
      </table>
      {/* Settlement sentence — AFTER the table (below the totals row).
          .split-settlement re-bolds over the base .note style. */}
      {settlementText !== null && (
        <p className="note split-settlement">{settlementText}</p>
      )}
    </section>
  );
}
