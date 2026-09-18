// KPI role summary — role-based KPI matrix per partner.
// Reads kpis from contract. Shows 5 metric cards + personal share +
// partner panels + chart. Sign classes: net_saved comes from
// detailed.savings.<partner>.net_saved_class when available (falls back to
// local classification only when detailed.savings is null — e.g. savings
// summary unavailable). net_cash uses kpis.<partner>.net_cash_class
// (accounting.py _role_kpis, server-computed — same pos/neg/zero convention),
// falling back to local signOf() only for reports generated before this
// field existed.

import type { Kpis, ReportResponse, SignClass } from "@/types/report";
import { PartnerKpiMatrix } from "@/components/reports/charts/PartnerKpiMatrix";
import { SIGN_CLASS, signOf } from "@/components/reports/signClasses";

function fmt(value: number): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

// Percent cell — null denominator (income = 0) -> em-dash, never a
// fabricated 0%.
function pct(value: number | null): string {
  return value === null ? "—" : `${value.toFixed(1)}%`;
}

interface KpiRoleSummaryProps {
  report: ReportResponse;
}

// KPI summary — 5 cards + partner panels + matrix chart.
export function KpiRoleSummary({ report }: KpiRoleSummaryProps) {
  const kpis = report.kpis;
  if (!kpis) return null;

  const total = kpis.total;
  const netMovement = report.root_totals.net;
  const pa = report.partner_panels.partner_a;
  const pb = report.partner_panels.partner_b;

  const cards: Array<{ label: string; value: number }> = [
    { label: "Total income", value: total.income },
    { label: "Real spend", value: total.real_spend },
    { label: "Net movement", value: netMovement },
    { label: "Net cash", value: total.net_cash },
    { label: "Net savings", value: total.net_savings },
  ];

  // Household personal-spend share — server-computed
  // (personal_spend / real_spend * 100), null when real_spend is 0.
  const personalShare = report.personal_share ?? null;

  // Matrix series — 3 charts: income, real_spend, net_savings.
  const series = [
    {
      title: "1. Income",
      data: [
        { label: pa.label, value: kpis.partner_a.income, color: "#1f77b4" },
        { label: pb.label, value: kpis.partner_b.income, color: "#ff7f0e" },
      ],
    },
    {
      title: "2. Real spend",
      data: [
        { label: pa.label, value: kpis.partner_a.real_spend, color: "#1f77b4" },
        { label: pb.label, value: kpis.partner_b.real_spend, color: "#ff7f0e" },
      ],
    },
    {
      title: "3. Net savings",
      data: [
        { label: pa.label, value: kpis.partner_a.net_savings, color: "#1f77b4" },
        { label: pb.label, value: kpis.partner_b.net_savings, color: "#ff7f0e" },
      ],
    },
  ];

  return (
    <div>
      <h3>KPI Role Summary</h3>

      {/* 5 metric cards */}
      <div className="summary">
        {cards.map((c) => (
          <div
            key={c.label}
            className={c.value < 0 ? "metric net-negative" : "metric"}
          >
            <span className="metric-label">{c.label}</span>
            <span className="metric-value">{fmt(c.value)}</span>
          </div>
        ))}
        {/* Household personal-spend share — server-computed, single figure;
            per-partner shares render inside each partner panel. */}
        <div className="metric">
          <span className="metric-label">Personal share</span>
          <span className="metric-value">{pct(personalShare)}</span>
        </div>
      </div>

      {/* Partner panels with KPI detail */}
      <div className="partner-row">
        <KpiPartnerPanel
          label={pa.label}
          cssClass="partner-a"
          values={kpis.partner_a}
          personalShare={report.personal_share_partner_a ?? null}
          netSavedClass={report.detailed?.savings?.partner_a.net_saved_class ?? null}
        />
        <KpiPartnerPanel
          label={pb.label}
          cssClass="partner-b"
          values={kpis.partner_b}
          personalShare={report.personal_share_partner_b ?? null}
          netSavedClass={report.detailed?.savings?.partner_b.net_saved_class ?? null}
        />
      </div>

      {/* KPI matrix chart */}
      <div className="overview-chart overview-matrix">
        <PartnerKpiMatrix series={series} />
      </div>
    </div>
  );
}

// KPI partner panel — income/real spend/personal/net cash/net saved.
interface KpiPartnerPanelProps {
  label: string;
  cssClass: string;
  values: Kpis["partner_a"];
  // Server-computed per-partner personal share (household denominator);
  // null for reports predating the field — the panel shows the amount alone.
  personalShare: number | null;
  // Server sign class for net_saved (detailed.savings.<partner>.net_saved_class),
  // null when detailed.savings is unavailable — falls back to local sign
  // classification in that case.
  netSavedClass: SignClass | null;
}

function KpiPartnerPanel({
  label,
  cssClass,
  values,
  personalShare,
  netSavedClass,
}: KpiPartnerPanelProps) {
  // Fallback to local classification when net_cash_class is absent (report
  // generated before this field existed — same convention as netSavedClass).
  const cashClass = SIGN_CLASS[values.net_cash_class ?? signOf(values.net_cash)];
  const savingsClass = SIGN_CLASS[netSavedClass ?? signOf(values.net_savings)];

  return (
    <div className={`partner-box ${cssClass}`}>
      <h3>{label}</h3>
      <div className="row">
        <span className="label">Income</span>
        <span className="val">{fmt(values.income)}</span>
      </div>
      <div className="row">
        <span className="label">Real spend</span>
        <span className="val">{fmt(values.real_spend)}</span>
      </div>
      <div className="row">
        <span className="label">Personal spend</span>
        <span className="val">
          {fmt(values.personal_spend)}
          {personalShare !== null && ` (${personalShare.toFixed(1)}%)`}
        </span>
      </div>
      <div className="row">
        <span className="label">Net cash</span>
        <span className={`val ${cashClass}`}>{fmt(values.net_cash)}</span>
      </div>
      <div className="row">
        <span className="label">Net saved</span>
        <span className={`val ${savingsClass}`}>{fmt(values.net_savings)}</span>
      </div>
    </div>
  );
}