"""CSS for the MoM report — professional design.

Goals:
  - Clean, minimal typography
  - Per-section color coding (income=green, savings=blue, home=orange, etc.)
  - Tables that don't overflow horizontally
  - Charts with proper margins, no overlapping labels
  - Per-partner color coding (Partner A=blue, Partner B=orange)
"""

import sys

# Per-section accent colors
_SECTION_COLORS = {
    "kpi": "#2c3e50",
    "income": "#27ae60",
    "savings": "#2980b9",
    "home": "#e67e22",
    "common": "#9b59b6",
    "personal_partner_a": "#1f77b4",
    "personal_partner_b": "#ff7f0e",
    "excluded": "#95a5a6",
    "cc_paydowns": "#34495e",
    "trips": "#16a085",
    "observations": "#34495e",
    "actions": "#27ae60",
}


def section_color(name: str) -> str:
    return _SECTION_COLORS.get(name, "#333")


# ============================================================
# Build the full CSS
# ============================================================


def get_css() -> str:
    s = """
@page { size: A4; margin: 14mm 12mm; }
@page landscape { size: A4 landscape; margin: 10mm 12mm; }

* { box-sizing: border-box; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  color: #2c3e50;
  margin: 0;
  padding: 0;
  background: #fff;
  font-size: 11pt;
  line-height: 1.4;
}

/* -------- Page break rules -------- */
h1, h2 { page-break-after: avoid; }
/* h2 no longer forces a page break — it sits on the same page as its content
   (table + chart) wrapped in a landscape-page div. Per THEK 2026-07-23. */
h2.section-income, h2.section-savings { page-break-before: avoid; }
table, svg, .kpi-card { page-break-inside: avoid; }

h2 { margin-top: 0; padding-top: 10px; }

.landscape-page {
  page: landscape;
}
.income-print-safe {
  break-inside: avoid-page;
  page-break-inside: avoid;
}
.income-print-safe > h3,
.income-print-safe > table,
.income-print-safe > .stacked-bar-line {
  break-inside: avoid-page;
  page-break-inside: avoid;
}
.landscape-page table {
  font-size: 9px;
  line-height: 1.2;
}
.landscape-page th, .landscape-page td {
  padding: 2px 4px;
}

.two-col {
  display: flex;
  flex-direction: row;
  gap: 12px;
  page-break-inside: avoid;
  margin-bottom: 12px;
}
.two-col > div {
  flex: 1;
  min-width: 0;
}

/* -------- Headings -------- */
h1 {
  font-size: 22pt;
  font-weight: 700;
  margin: 0 0 4px 0;
  text-align: center;
  color: #2c3e50;
  letter-spacing: -0.5px;
}
.subtitle { text-align: center; color: #7f8c8d; font-size: 10pt; margin: 0 0 24px 0; }

h2 {
  font-size: 18pt;
  font-weight: 600;
  margin: 0 0 12px 0;
  padding-bottom: 6px;
  border-bottom: 3px solid #3498db;
  color: #2c3e50;
}
h2.section-income    { border-bottom-color: #27ae60; }
h2.section-savings   { border-bottom-color: #2980b9; }
h2.section-home      { border-bottom-color: #e67e22; }
h2.section-common    { border-bottom-color: #9b59b6; }
h2.section-personal_partner_a { border-bottom-color: #1f77b4; }
h2.section-personal_partner_b { border-bottom-color: #ff7f0e; }
h2.section-excluded  { border-bottom-color: #95a5a6; }
h2.section-cc_paydowns { border-bottom-color: #34495e; }
h2.section-trips     { border-bottom-color: #16a085; }
h2.section-observations { border-bottom-color: #34495e; }
h2.section-actions   { border-bottom-color: #27ae60; }

h3 {
  font-size: 12pt;
  font-weight: 600;
  margin: 12px 0 6px 0;
  color: #34495e;
}

/* -------- KPI cover -------- */
.kpi-cover { padding: 0; margin: 0; }
.period-banner {
  text-align: center;
  background: #ecf0f1;
  padding: 10px;
  border-radius: 4px;
  margin: 0 0 20px 0;
  font-size: 11pt;
  color: #34495e;
}
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin: 0 0 20px 0;
}
.kpi-grid-8 { grid-template-columns: repeat(4, 1fr); }
.kpi-card {
  background: #fff;
  border: 1px solid #e0e6ed;
  border-top: 4px solid #3498db;
  border-radius: 4px;
  padding: 14px 12px;
  text-align: center;
}
.kpi-card.kpi-income    { border-top-color: #27ae60; }
.kpi-card.kpi-spend     { border-top-color: #e67e22; }
.kpi-card.kpi-cash      { border-top-color: #2980b9; }
.kpi-card.kpi-saved     { border-top-color: #16a085; }
.kpi-card.kpi-home      { border-top-color: #d35400; }
.kpi-card.kpi-common    { border-top-color: #8e44ad; }
.kpi-card.kpi-pfxa      { border-top-color: #1f77b4; }
.kpi-card.kpi-pfxb      { border-top-color: #ff7f0e; }
.kpi-label { font-size: 9pt; color: #7f8c8d; text-transform: uppercase; letter-spacing: 0.5px; }
.kpi-section-summary .note { font-size: 10pt; color: #34495e; margin: 4px 0; }
.kpi-section-summary .note-small { font-size: 8.5pt; color: #7f8c8d; font-style: italic; margin: 2px 0 8px 0; }
.kpi-value { font-size: 22pt; font-weight: 700; color: #2c3e50; margin: 6px 0; }
.kpi-pct { font-size: 9pt; color: #555; }
.kpi-pct .partner-a { color: #1f77b4; font-weight: 600; }
.kpi-pct .partner-b { color: #ff7f0e; font-weight: 600; }

.partner-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin: 0 0 16px 0;
}
.partner-box {
  border: 1px solid #e0e6ed;
  border-radius: 4px;
  padding: 12px 16px;
}
.partner-box.partner-a { border-left: 4px solid #1f77b4; }
.partner-box.partner-b { border-left: 4px solid #ff7f0e; }
.partner-title { font-size: 11pt; font-weight: 600; margin: 0 0 8px 0; }
.partner-row { display: flex; justify-content: space-between; font-size: 10pt; padding: 2px 0; }
.partner-row .label { color: #7f8c8d; }
.partner-row .value { font-weight: 600; color: #2c3e50; }
.partner-row .negative { color: #c0392b; }

/* Personal mini-card nested inside partner box */
.personal-card {
  margin-top: 10px;
  padding: 10px 12px;
  background: #fafbfc;
  border-radius: 4px;
  border: 1px dashed #bdc3c7;
}
.personal-card-label {
  font-size: 9pt;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #7f8c8d;
  margin-bottom: 4px;
}
.personal-card-total {
  font-size: 16pt;
  font-weight: 700;
  color: #2c3e50;
  margin-bottom: 6px;
}
.personal-card-rows { font-size: 9pt; }
.personal-row {
  display: flex;
  justify-content: space-between;
  padding: 2px 0;
  color: #555;
}
.personal-row b { color: #2c3e50; }
.partner-box.partner-a .personal-card { border-left: 3px solid #1f77b4; }
.partner-box.partner-b .personal-card { border-left: 3px solid #ff7f0e; }

/* -------- Chart data table (below each chart) -------- */
.chart-data-table {
  margin: 6px 0 18px 0;
  page-break-inside: avoid;
}
.chart-data-table h4 {
  font-size: 9.5pt;
  font-weight: 600;
  color: #34495e;
  margin: 4px 0 4px 0;
  text-align: center;
}
.chart-data-table .data-table {
  width: 100%;
  font-size: 8pt;
  margin: 0 0 14px 0;
}
.chart-data-table .data-table th,
.chart-data-table .data-table td {
  padding: 3px 4px;
  text-align: right;
  border-bottom: 1px solid #ecf0f1;
}
.chart-data-table .data-table th.row-label,
.chart-data-table .data-table td.row-label {
  text-align: left;
  font-weight: 600;
  white-space: nowrap;
  width: 90px;
}
.chart-data-table .data-table th {
  background: #f7f9fa;
  color: #34495e;
}

/* -------- Tables -------- */
table {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0 14px 0;
  font-size: 9pt;
  table-layout: fixed;
}
th, td {
  padding: 4px 4px;
  text-align: left;
  border-bottom: 1px solid #ecf0f1;
  word-wrap: break-word;
  overflow-wrap: break-word;
}
th { font-size: 7.5pt; }
.overview-table th, .overview-table td { padding: 4px 4px; font-size: 8.5pt; }
.overview-table th { font-size: 7pt; }
.per-cat-table th, .per-cat-table td { padding: 3px 2px; font-size: 7.5pt; }
th {
  background: #f8f9fa;
  font-weight: 600;
  color: #34495e;
  text-transform: uppercase;
  font-size: 8.5pt;
  letter-spacing: 0.3px;
  border-bottom: 2px solid #bdc3c7;
}
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
td.row-label, th.row-label { font-weight: 500; }
th.month { background: #ecf0f1; }
th.total-col, td.total-col { background: #f8f9fa; font-weight: 600; }
th.partner-a-col { background: #e8f0fe; color: #1f77b4; }
th.partner-b-col { background: #fef0e0; color: #ff7f0e; }
td.partner-a-col { background: #f7faff; }
td.partner-b-col { background: #fff7ed; }

.overview-table tr.row-partner-a td { border-left: 3px solid #1f77b4; }
.overview-table tr.row-partner-b td { border-left: 3px solid #ff7f0e; }
.overview-table tr.row-total td { background: #f8f9fa; font-weight: 600; border-top: 2px solid #34495e; }
.overview-table tr.bold td { font-weight: 600; }

.per-cat-table tr.cat-reimb td.row-label { color: #16a085; font-style: italic; }
.per-cat-table tr.subtotal-row td { background: #ecf0f1; border-top: 2px solid #34495e; }

/* Appendix tables — 4 columns, fit on portrait A4 */
.appendix-table {
  font-size: 8pt;
  table-layout: fixed;
  margin: 4px 0 8px 0;
}
.appendix-table th {
  font-size: 7.5pt;
  padding: 3px 4px;
}
.appendix-table td {
  padding: 3px 4px;
  font-size: 8pt;
  word-wrap: break-word;
  overflow-wrap: break-word;
}
.appendix-table th:nth-child(1), .appendix-table td:nth-child(1) { width: 14%; }  /* Date */
.appendix-table th:nth-child(2), .appendix-table td:nth-child(2) { width: 45%; }  /* Payee */
.appendix-table th:nth-child(3), .appendix-table td:nth-child(3) { width: 26%; }  /* Account */
.appendix-table th:nth-child(4), .appendix-table td:nth-child(4) { width: 15%; }  /* Amount */
.appendix-table tr.subtotal-row td {
  background: #ecf0f1;
  border-top: 1.5px solid #34495e;
  font-style: italic;
  font-size: 8pt;
}
h4.appendix-month {
  font-size: 11pt;
  margin: 14px 0 4px 0;
  page-break-after: avoid;
  color: #2c3e50;
}
h5.appendix-subcat {
  font-size: 9pt;
  margin: 8px 0 2px 0;
  page-break-after: avoid;
  color: #555;
}
p.appendix-month-total {
  font-size: 9pt;
  margin: 4px 0 12px 0;
  padding: 4px 8px;
  background: #eaf2f8;
  border-left: 3px solid #2980b9;
}

/* -------- Recommendations / Actions -------- */
.recommendation, .action {
  padding: 10px 14px;
  margin: 6px 0;
  border-radius: 4px;
  font-size: 10pt;
  line-height: 1.5;
}
.recommendation {
  background: #f8f9fa;
  border-left: 4px solid #34495e;
}
.recommendation .num {
  display: inline-block;
  width: 24px;
  height: 24px;
  background: #34495e;
  color: #fff;
  border-radius: 50%;
  text-align: center;
  font-weight: 700;
  font-size: 10pt;
  margin-right: 8px;
  line-height: 24px;
}
.action {
  background: #eafaf1;
  border-left: 4px solid #27ae60;
}
.action .num {
  display: inline-block;
  width: 24px;
  height: 24px;
  background: #27ae60;
  color: #fff;
  border-radius: 50%;
  text-align: center;
  font-weight: 700;
  font-size: 10pt;
  margin-right: 8px;
  line-height: 24px;
}

.note { font-size: 9pt; color: #7f8c8d; font-style: italic; margin: 0 0 8px 0; }
.empty { color: #95a5a6; font-style: italic; font-size: 9pt; }

/* -------- Trip-specific -------- */
.trip-charts { display: flex; gap: 16px; flex-wrap: wrap; }
.trip-charts > * { flex: 1; min-width: 320px; }

/* -------- SVG charts -------- */
svg { max-width: 100%; height: auto; }
svg text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
"""
    return s
