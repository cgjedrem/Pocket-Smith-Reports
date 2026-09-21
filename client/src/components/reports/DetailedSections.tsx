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

import { useMemo, type ReactNode } from "react";

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
import type {
  CcPaymentsSection as CcPaymentsSectionDto,
  DetailedSavingsSection as DetailedSavingsSectionDto,
  ExcludedSection as ExcludedSectionDto,
  IncomeRow,
  IncomeSection as IncomeSectionDto,
  NetSection as NetSectionDto,
  PersonalSection as PersonalSectionDto,
  ReportResponse,
  SavingsPartnerRow,
  SignClass,
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
        note="The Home reimbursement rows show both cash legs. They cancel in household total, while the partner net columns show who actually paid after reimbursement."
        drilldown={<SectionDrilldown txns={sectionTxns["home"] ?? []} />}
      />

      <NetSection
        num="4"
        title="Common"
        section={detailed.common}
        paLabel={paLabel}
        pbLabel={pbLabel}
        note="The Common net columns subtract reimbursements from the recipient and add them to the sender. No 50/50 split is assumed."
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

// 3/4/7. Net sections — Home, Common, Trips. Per-category net + paired
// reimbursements (rendered as their own block — the DTO no longer carries
// the transaction-level position needed to interleave them with their
// category row) + optional chart.
interface NetSectionProps {
  num: string;
  title: string;
  section: NetSectionDto | null;
  paLabel: string;
  pbLabel: string;
  note?: string;
  chartTitle?: string;
  drilldown?: ReactNode;
}

function NetSection({
  num,
  title,
  section,
  paLabel,
  pbLabel,
  note,
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
            <tr key={r.category_title}>
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
          ))}
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
      {note && <p className="note">{note}</p>}
      {section.paired_reimbursements.length > 0 && (
        <table className="legacy-table net-table">
          <caption>Paired reimbursements (net 0, shown for transparency)</caption>
          <thead>
            <tr>
              <th>Category</th>
              <th>{paLabel}</th>
              <th>{pbLabel}</th>
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            {section.paired_reimbursements.map((r, i) => (
              <tr key={`${r.category_title}-${i}`} className="reimb-row">
                <td>
                  <i>{r.category_title} (paired reimbursement)</i>
                </td>
                <td className={cls(r.partner_a_class)}>{fmtSigned(r.partner_a)}</td>
                <td className={cls(r.partner_b_class)}>{fmtSigned(r.partner_b)}</td>
                <td className={cls(r.total_class)}>
                  <b>{fmt(r.total)}</b>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
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
