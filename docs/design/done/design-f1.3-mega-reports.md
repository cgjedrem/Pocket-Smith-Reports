# F1.3 — React Page for Mega Reports

Status: DESIGN COMPLETE (L1-L5 written, pending final approval)
Date: 2026-07-29
Repo: Pocket-Smith-Reports

## Summary
React UI page for the mega report pipeline. Migrate mega CLI report generation to API + React.
- **Mega Reports page** — year picker + dual month picker (start/end) + generated reports list. Renders all 13 sections via Radix UI + raw SVG.
- **Backend migration** — CLI → API. Build report as JSON (pre-computed presentation views). CLI stays standalone for AI skill use.
- **PDF export** — backend reuses mega CLI `assemble_html()` + WeasyPrint. CLI path kept.
- **All 13 sections** — full parity with CLI: kpi_cover, income, savings, home, common, personal_partner_a, personal_partner_b, trips, recommendations, monthlies, cc_paydowns, excluded, appendices.

## Dependencies
- F1.1 app shell (Vite + React + Router + Radix + Tailwind) — DONE
- F1.2 monthly reports (reports router, report_builder, MonthlyReportsPage, chart components) — DONE
- Existing pipeline: `src/mega/` (build_mega, registry, build_context, assemble_html)
- `src/mom/` (compare.aggregate_normalized_months, sections/, line_chart, stacked_bar_line)
- WeasyPrint (existing dependency)

## Decisions (from grill-me session, 2026-07-29)

| # | Decision |
|---|----------|
| Q1 | Full JSON port (F1.2 pattern). Backend ports detail_agg + section data to JSON. React renders with Radix + SVG. |
| Q2 | Year picker + dual month picker (start/end) + generated reports list. Year fills Jan–Dec, dual picker overrides for custom range. |
| Q3 | Report storage key: `{start}_{end}_mega_report.json`. Human-readable, matches F1.2 pattern. |
| Q4 | All 13 sections in v1. Full parity with CLI. |
| Q5 | Stale detection: per-month txn count + calculation_version. Any month mismatch OR version bump → stale. |
| Q6 | Async + poll (same as F1.2). POST returns 202, poll /status every 2s. Navigate-away safe. |
| Q7 | PDF export reuses mega CLI `assemble_html()` + WeasyPrint. CLI stays standalone. |
| Q8 | New top-nav item "Mega Reports" at `/mega-reports`. 4 nav items total. |
| Q9 | Recommendations: backend reads `data/private/recommendations.json` if exists. Empty state if absent. No upload/generation UI. |
| Q10 | Strict month validation — all months in range must be synced. 400 if any missing. |
| Q11 | Port mega's chart generators to JSX (LineChart, StackedBarLineChart, MegaBarChart). Raw SVG, no chart lib. |
| Q12 | Tailwind for React styling. CLI keeps `sections/css.py` for PDF. No shared SCSS. |
| Q13 | CLI stays standalone. `python -m mega.build_mega` works without React. |
| Q14 | Config paths hardcoded to `data/private/`. No config params in API request. |
| Q15 | Always render all 13 sections. No section filter, no anchor nav. |

---

## L1: Capabilities

### In-scope

#### Backend (CLI → API migration)
- **Mega report service** — `mega_builder.py` wraps `build_context()` + ports `detail_agg` data to JSON structures (series, cumulative, cats, cc_paydowns, trips, excluded, salary_allocation, recommendations). Writes `{start}_{end}_mega_report.json` + status file.
- **Generated reports list endpoint** — `GET /api/mega-reports` scans `data/private/*_mega_report.json`, returns list of ranges (sorted newest first).
- **Mega report JSON endpoint** — `GET /api/mega-reports/{start}/{end}` returns contract JSON (404 if not generated yet). Includes `stale` flag (per-month txn count + calculation_version check).
- **Generate endpoint** — `POST /api/mega-reports/{start}/{end}/generate` starts async generation, returns 202. Poll `GET /api/mega-reports/{start}/{end}/status` until success/failed.
- **Generate status endpoint** — `GET /api/mega-reports/{start}/{end}/status` returns generation status (generating/success/failed).
- **PDF export endpoint** — `POST /api/mega-reports/{start}/{end}/pdf` invokes mega CLI `assemble_html()` + WeasyPrint, returns PDF as binary stream.
- **Month validation** — backend validates all months in range have `ps_raw.json` files. 400 if any missing.
- **Config resolution** — `mega_builder.py` resolves config from `data/private/` (category_roles.json, account_mappings.json, detailed_section_mapping.json, category_catalog.json, partner_labels.json). Bridges account_mappings partner_id schema → mega expected format (same as F1.2).
- **CLI stays standalone** — `python -m mega.build_mega --start ... --end ...` unchanged. AI skill use without React.

#### Frontend (React + Radix UI)
- **Mega Reports page** — new top-nav item (Sync / Monthly Reports / Mega Reports / Settings)
- **Year picker** — select year (e.g. 2026) → fills start=Jan, end=Dec. Quick preset.
- **Dual month picker** — start + end MonthPicker components. Override year preset for custom range. Backend validates start ≤ end.
- **Generated reports list** — sidebar listing already-generated mega reports (keyed by `{start}_{end}` range). Click one → view that report.
- **Report view** — renders all 13 sections via Radix UI + raw SVG charts:
  1. KPI Cover (6 KPI cards + 4 charts: stacked bar, line x3 + salary allocation table)
  2. Income (per-month table + stacked bar chart + cumulative line)
  3. Savings (table + line chart)
  4. Home (table + chart)
  5. Common spending (table + chart)
  6. Personal spending - Partner A (table + chart)
  7. Personal spending - Partner B (table + chart)
  8. Trips (clustered trip cards)
  9. Recommendations (cards from recommendations.json, or empty state)
  10. Monthly KPI pages (per-month KPI cards, all months in range)
  11. Credit-card paydowns (table per card per month)
  12. Excluded categories (table of excluded transactions)
  13. Appendices (placeholder, same as CLI)
- **Generate button** — shows when no JSON exists (404). Triggers `POST /generate`.
- **Regenerate button** — re-runs pipeline, overwrites JSON. Shows stale badge if txn counts mismatch or calc version bump.
- **PDF export button** — triggers `POST /pdf` → downloads PDF file.
- **Loading/error/empty states** — generating spinner, 404 generate prompt, no months (sync first), API errors, missing months warning.

### Out-of-scope (F1.3)
- Mom (multi-month range) report page → separate feature
- Section filter / `--only` in React (CLI-only)
- Recommendations upload/generation UI (read-only)
- Theme selector (minimal only)
- Anchor nav sidebar (all 13 sections render sequentially)
- Auth layer (localhost-only, no auth)

### Success criteria
- CLI standalone: `python -m mega.build_mega --start 2026-01 --end 2026-07 ...` produces PDF without React app running
- `GET /api/mega-reports` returns list of generated mega report ranges
- `GET /api/mega-reports/{start}/{end}` returns contract JSON with pre-computed views + `stale` flag (or 404)
- `POST /api/mega-reports/{start}/{end}/generate` starts async generation, returns 202
- `GET /api/mega-reports/{start}/{end}/status` returns generation status
- `POST /api/mega-reports/{start}/{end}/pdf` returns PDF binary stream
- `GET /api/mega-reports/{start}/{end}` returns 400 if any month in range has no synced data
- React app: Mega Reports page with year picker + dual month picker + generated reports list renders on `localhost:5173/mega-reports`
- All 13 sections render from contract JSON via Radix + SVG
- Partner names from config shown, not generic labels
- Generate button shows on 404, Regenerate button shows on existing report
- Stale badge shows when txn count mismatch or calc version bump
- PDF export downloads file matching CLI output
- Recommendations section shows cards if `recommendations.json` exists, empty state if absent

### Assumptions
- `data/private/*_ps_raw.json` files exist (synced via F1.1)
- `account_mappings.json`, `partner_labels.json`, `detailed_section_mapping.json`, `category_catalog.json`, `category_roles.json` exist in `data/private/`
- WeasyPrint installed (existing dependency for CLI)
- React app shell exists (F1.1 built it — Vite + React + Router + Radix + Tailwind)
- F1.2 monthly reports infrastructure exists (reports router, report_builder, storage, chart components)
- Contract JSON stored at `data/private/{start}_{end}_mega_report.json`
- Status file at `data/private/{start}_{end}_mega_report_status.json`
- `data/private/recommendations.json` may or may not exist (optional)

### Risks
- **13 sections = very large frontend build** — biggest scope yet. ~96h estimate. Risk: scope creep, long delivery.
- **detail_agg serialization** — `_detail_agg()` in build_mega.py already returns a dict. Risk is JSON serialization correctness, not HTML extraction. Verify JSON round-trips match Python dict.
- **Chart port complexity** — 4 new chart types (line, stacked bar+line, horizontal bar, subcat stacked bar). Each has SVG generation logic in Python. Port to JSX requires careful math translation.
- **Contract JSON size** — 12 months of transactions + per-category per-month series. JSON could be 500KB+. Acceptable for local app.
- **Month validation UX** — strict validation means user must sync all months. Could be frustrating if range has gaps. Mitigated by missing-months warning in UI.
- **Recommendations dependency** — section is empty without external AI agent generating the artifact. Acceptable — empty state is clear.

---

### Alignment check (ANSWERED 2026-07-29)

1. **JSON port approach** — ✅ Full JSON port, same as F1.2
2. **Period selection** — ✅ Year picker + dual month picker + generated reports list
3. **Storage key** — ✅ `{start}_{end}_mega_report.json`
4. **Section scope** — ✅ All 13 sections
5. **Stale detection** — ✅ Per-month txn count + calculation_version
6. **Generate flow** — ✅ Async + poll, same as F1.2
7. **PDF export** — ✅ Reuse mega CLI assemble_html() + WeasyPrint
8. **Navigation** — ✅ New top-nav item "Mega Reports" at /mega-reports
9. **Recommendations** — ✅ Read if exists, empty state if absent
10. **Month validation** — ✅ Strict, 400 if any missing
11. **Charts** — ✅ Port to JSX (LineChart, StackedBarLineChart, MegaBarChart)
12. **CSS** — ✅ Tailwind for React, sections/css.py for CLI PDF
13. **CLI standalone** — ✅ CLI stays standalone
14. **Config paths** — ✅ Hardcode to data/private/
15. **Section filter** — ✅ All 13 always render, no filter

---

## L2: Components

### Existing code to reuse

| File | What it does | Reuse for F1.3 |
|------|-------------|----------------|
| `src/mega/build_mega.py` | `build_context(args: argparse.Namespace)` → detail_agg + salary_allocation + recommendations. `assemble_html(context, args)` → HTML. `main()` CLI. | Programmatic entry for mega_builder service. Must construct argparse.Namespace with config paths from `data/private/`. CLI stays. |
| `src/mega/registry.py` | 13 section registry (SECTIONS, active_sections, numbered_sections) | Section metadata for frontend (titles, order, optional flag). |
| `src/mom/compare.py` | `aggregate_normalized_months()` → multi-month aggregation | Core aggregator (unchanged). |
| `src/mom/line_chart.py` | `render_line_chart()` → SVG line chart string | Port SVG logic to JSX LineChart.tsx. |
| `src/mom/stacked_bar_line.py` | `render_stacked_bar_with_line()` → SVG stacked bar + cumulative line | Port SVG logic to JSX StackedBarLineChart.tsx. |
| `src/mom/bar_chart.py` | Horizontal bar chart SVG | Check if F1.2 `HorizontalBarChart.tsx` can be reused. If yes, skip port. If no, port to JSX MegaBarChart.tsx. |
| `src/mom/sections/section_income.py` | Income section renderer (table + chart) | Port data extraction to JSON. |
| `src/mom/sections/section_savings.py` | Savings section renderer | Port data extraction to JSON. |
| `src/mom/sections/section_home.py` | Home section renderer | Port data extraction to JSON. |
| `src/mom/sections/section_common.py` | Common spending renderer | Port data extraction to JSON. |
| `src/mom/sections/section_personal.py` | Personal spending renderer (partner A/B) — uses subcat stacked bar + period pie | Port data extraction to JSON. |
| `src/mom/sections/section_trips.py` | Trips section renderer | Port data extraction to JSON. |
| `src/mom/sections/section_cc_paydowns.py` | CC paydowns renderer | Port data extraction to JSON. |
| `src/mom/sections/section_excluded.py` | Excluded categories renderer | Port data extraction to JSON. |
| `src/mega/build_mega.py` `_render_kpi_cover()` | KPI cover renderer (6 cards + 4 charts + salary allocation) — mega uses this, NOT `section_kpi_cover.py` | Port data extraction to JSON from `_render_kpi_cover()`. |
| `src/mom/sections/css.py` | `get_css()` — mega CSS for PDF | CLI PDF only. React uses Tailwind. |
| `src/mom/recommendations.py` | `generate_observations()` — aggregate observations | Observations generator NOT used. Artifact loader (`_load_requested_recommendations()` inside `build_context()`) IS used. |
| `src/budget_api/main.py` | FastAPI app, routers mounted, CORS | Mount new mega-reports router. |
| `src/budget_api/services/storage.py` | `atomic_write_json`, `read_json`, path constants | Storage layer for mega report JSON. |
| `src/budget_api/services/report_builder.py` | F1.2 monthly report builder, config bridging | Reuse config bridging pattern (`_load_excluded_account_ids`, `_load_account_owners`). |
| `src/budget_api/routers/reports.py` | F1.2 reports router (months, get, generate, status, pdf) | Pattern reference for mega-reports router. |
| `client/src/router.tsx` | `createBrowserRouter` with Sync + Reports + Settings routes | Add Mega Reports route. |
| `client/src/layouts/AppLayout.tsx` | Top nav with Sync + Monthly Reports + Settings NavLinks | Add Mega Reports nav link. |
| `client/src/api/client.ts` | Fetch wrapper (base URL, error parsing) | Mega report API functions. |
| `client/src/components/MonthPicker.tsx` | Month picker component | Reuse for start/end month pickers. |
| `client/src/components/reports/charts/` | F1.2 chart components (DonutChart, HorizontalBarChart, PartnerKpiMatrix) | Pattern reference for new chart components. |
| `client/src/components/reports/GenerateButton.tsx` | Generate button component | Reuse or adapt for mega. |
| `client/src/components/reports/StaleBadge.tsx` | Stale badge component | Reuse for mega. |
| `client/src/components/reports/PdfExportButton.tsx` | PDF export button | Reuse or adapt for mega. |
| `client/src/components/EmptyState.tsx` | Empty state component | Reuse. |
| `client/src/components/ErrorAlert.tsx` | Error alert component | Reuse. |

### Proposed components

#### Backend (new)

```
src/budget_api/
  main.py                              # UPDATE: mount mega-reports router
  routers/
    mega_reports.py                    # NEW: GET /mega-reports, GET /mega-reports/{start}/{end}, POST /generate, GET /status, POST /pdf
  services/
    mega_builder.py                    # NEW: constructs argparse.Namespace from data/private/ + calls build_context() + serializes detail_agg to JSON. Writes report + status.
    mega_pdf.py                        # NEW: constructs argparse.Namespace + calls build_context() + assemble_html() + WeasyPrint. Returns PDF bytes.
  models/
    mega_reports.py                    # NEW: MegaReportList, MegaReportRange, MegaReportResponse. GenerateStatus imported from models/reports.py (F1.2).
  tests/
    test_mega_reports.py
    test_mega_builder.py
    test_mega_acceptance.py
```

#### Frontend (new)

```
client/src/
  router.tsx                           # UPDATE: add /mega-reports route
  layouts/
    AppLayout.tsx                      # UPDATE: add Mega Reports nav link
  pages/
    MegaReportsPage.tsx                # NEW: year picker + dual month picker + generated reports list + report view container
    MegaReportsPage.module.css
  components/
    mega-reports/
      YearPicker.tsx                   # NEW: year selector (fills start=Jan, end=Dec)
      RangePicker.tsx                  # NEW: dual MonthPicker (start + end), validates start ≤ end
      GeneratedReportsList.tsx         # NEW: sidebar listing generated mega reports (ranges)
      MegaReportView.tsx               # NEW: renders all 13 sections from contract JSON
      MegaReportView.module.css
      sections/
        KpiCoverSection.tsx            # NEW: 6 KPI cards + 4 charts + salary allocation table
        IncomeSection.tsx              # NEW: per-month table + stacked bar chart + cumulative line
        SavingsSection.tsx             # NEW: table + line chart
        HomeSection.tsx                # NEW: table + chart
        CommonSection.tsx              # NEW: table + chart
        PersonalSection.tsx            # NEW: table + chart (parameterized by partner)
        TripsSection.tsx               # NEW: clustered trip cards
        RecommendationsSection.tsx     # NEW: recommendation cards or empty state
        MonthliesSection.tsx           # NEW: per-month KPI cards (all months in range)
        CcPaydownsSection.tsx          # NEW: CC paydown table per card per month
        ExcludedSection.tsx            # NEW: excluded transactions table
        AppendicesSection.tsx          # NEW: placeholder (same as CLI)
      MegaGenerateButton.tsx          # NEW: generate/regenerate trigger
      MegaStaleBadge.tsx              # NEW: stale indicator (reuse StaleBadge or adapt)
      MegaPdfExportButton.tsx         # NEW: PDF download trigger
      charts/
        LineChart.tsx                  # NEW: raw SVG line chart (port from line_chart.py)
        StackedBarLineChart.tsx        # NEW: raw SVG stacked bar + cumulative line (port from stacked_bar_line.py)
        MegaBarChart.tsx              # NEW: raw SVG horizontal bar chart (reuse F1.2 HorizontalBarChart if compatible, else port from bar_chart.py)
        SubcatStackedBarChart.tsx      # NEW: raw SVG subcat stacked bar (port from subcat_charts.py render_subcat_stacked_bar)
  api/
    mega_reports.ts                    # NEW: list, get report, generate, status, pdf functions
  types/
    mega_report.ts                     # NEW: TS types matching backend mega report models
  tests/
    MegaReportsPage.test.tsx
    MegaReportView.test.tsx
```

### Component responsibilities

#### Backend
- **mega_builder.py** — `build_mega_report(start, end) → dict`. Constructs `argparse.Namespace` with config paths from `data/private/` (start, end, data_dir, input_kind=live, category_role_map, account_owner_map, detailed_section_map, category_catalog, partner_label_map, recommendations_artifact). Calls `build_context(args)` which returns `detail_agg` as a dict. Serializes `detail_agg` to JSON: series (income, savings, real_spend, net_cash), cumulative, cats (per-category per-month), cc_paydowns, trips, excluded_transactions, salary_allocation, recommendations. Writes to `{start}_{end}_mega_report.json` + status file. Includes `calculation_version` + `txn_counts` per month for stale detection.
- **mega_pdf.py** — `generate_pdf(start, end) → bytes`. Constructs `argparse.Namespace` (same as mega_builder). Calls `build_context(args)` → `assemble_html(context, args)` → WeasyPrint. Returns PDF bytes. Uses mega's own CSS (`sections/css.py`).
- **routers/mega_reports.py** — 5 endpoints: `GET /api/mega-reports` (scan mega_report files), `GET /api/mega-reports/{start}/{end}` (read JSON + stale check), `POST /api/mega-reports/{start}/{end}/generate` (async 202 + concurrent guard), `GET /api/mega-reports/{start}/{end}/status` (generation status), `POST /api/mega-reports/{start}/{end}/pdf` (PDF binary stream).
- **models/mega_reports.py** — Pydantic models: `MegaReportList`, `MegaReportRange`, `MegaReportResponse`. `GenerateStatus` imported from `models/reports.py` (F1.2) — no redefinition.

#### Frontend
- **MegaReportsPage.tsx** — Layout: top row (YearPicker + RangePicker) + left sidebar (GeneratedReportsList) + right (MegaReportView). Fetches generated reports list on mount. Manages selected range state.
- **YearPicker.tsx** — Year dropdown. Derives available years from `GET /api/reports/months` (F1.2 endpoint — cross-endpoint call). Select → fills start=Jan-{year}, end=Dec-{year}.
- **RangePicker.tsx** — Two MonthPicker components (start + end). Validates start ≤ end. Fetches available months from `GET /api/reports/months` (F1.2 endpoint — cross-endpoint call) to show missing-months warning if any month in range has no synced data.
- **GeneratedReportsList.tsx** — Radix RadioGroup (vertical, single-select). Lists generated mega report ranges (newest first). Click → set selected range → fetch report.
- **MegaReportView.tsx** — Fetches `GET /api/mega-reports/{start}/{end}`. On 404 → show MegaGenerateButton. On 200 → render all 13 sections. On stale → show MegaStaleBadge + Regenerate button. PDF export button always visible.
- **KpiCoverSection.tsx** — 6 KPI cards (income, real spend, net cash, net savings, partner A income, partner B income) + 4 charts (stacked bar income, line real spend, line net cash, line savings cumulative) + salary allocation table.
- **IncomeSection.tsx** — Per-month income table (months as rows, partner A/B/total as columns, cumulative total column) + stacked bar chart with cumulative line.
- **SavingsSection.tsx** — Savings table + line chart.
- **HomeSection.tsx** — Home spending table + chart.
- **CommonSection.tsx** — Common spending table + chart.
- **PersonalSection.tsx** — Personal spending table + SubcatStackedBarChart. Parameterized by partner (partner_a or partner_b).
- **TripsSection.tsx** — Clustered trip cards (trips grouped by label, with dates, amounts, owner).
- **RecommendationsSection.tsx** — Recommendation cards (title, body, severity, evidence) if `recommendations` in JSON. Empty state: "No recommendations available."
- **MonthliesSection.tsx** — Per-month KPI cards. For each month in range: income, real spend, net cash, net savings per partner + household.
- **CcPaydownsSection.tsx** — Table of CC paydowns per card per month.
- **ExcludedSection.tsx** — Table of excluded transactions (date, description, category, owner, amount).
- **AppendicesSection.tsx** — Placeholder text (same as CLI).
- **charts/LineChart.tsx** — Raw SVG line chart. Port of `line_chart.py` `render_line_chart()`. Multi-series, x-axis = months, y-axis = NOK.
- **charts/StackedBarLineChart.tsx** — Raw SVG stacked bar + cumulative line. Port of `stacked_bar_line.py` `render_stacked_bar_with_line()`. Dual y-axis.
- **charts/MegaBarChart.tsx** — Raw SVG horizontal bar chart. Reuse F1.2 `HorizontalBarChart.tsx` if compatible. Else port from `bar_chart.py`.
- **charts/SubcatStackedBarChart.tsx** — Raw SVG subcat stacked bar. Port of `subcat_charts.py` `render_subcat_stacked_bar()`. Months on x-axis, sub-cats stacked as colored segments.

### What we do NOT create
- No database (files only)
- No auth (localhost-only)
- No WebSocket (poll-based status, like sync flow)
- No mom report page (separate feature)
- No section filter / `--only` in React (CLI-only)
- No recommendations upload/generation UI (read-only)
- No shared SCSS (Tailwind for React, sections/css.py for CLI)
- No anchor nav sidebar (all 13 sections render sequentially)
- No theme selector (minimal only)

---

### Alignment check (ANSWERED 2026-07-29)

1. **mega_builder.py** — ✅ New service file (clean separation, like F1.2's report_builder.py).
2. **Config bridging** — ✅ Reuse F1.2's `_load_excluded_account_ids` + `_load_account_owners` pattern.
3. **Chart components** — ✅ 3 new: LineChart, StackedBarLineChart, MegaBarChart. Port from Python SVG generators.
4. **GeneratedReportsList** — ✅ Radix RadioGroup (vertical, single-select, same as MonthSidebar).
5. **PersonalSection** — ✅ Parameterized by partner (one component, two instances).

---

## L3: Interactions

### Main flow — view mega report

```
User navigates to /mega-reports (Mega Reports page)
  │
  ▼
MegaReportsPage mounts
  │
  ▼
GET /api/mega-reports                    ← generated reports list
GET /api/reports/months                   ← F1.2 endpoint, for year picker + range validation
  │
  ├─ 200 (empty) → GeneratedReportsList shows "No reports generated yet"
  ├─ 200 (list)  → GeneratedReportsList renders ranges (newest first)
  └─ 500         → ErrorAlert: "Cannot reach server"
  │
  ▼
User picks range via YearPicker OR RangePicker OR clicks generated report
  │
  ▼
[RangePicker validates: start ≤ end, all months synced]
  │
  ├─ missing months → warning: "Missing: Jan, Feb. Sync these first."
  └─ all present   → proceed
  │
  ▼
MegaReportView fetches GET /api/mega-reports/{start}/{end}
  │
  ├─ 200 (not stale) → render all 13 sections + PDF export button + Regenerate button
  ├─ 200 (stale)     → render all 13 sections + MegaStaleBadge + Regenerate button + PDF export
  ├─ 404             → show MegaGenerateButton ("No report generated yet")
  ├─ 400             → ErrorAlert (missing months or invalid range)
  ├─ 500             → ErrorAlert
  └─ network error   → ErrorAlert "Cannot reach server"
```

### Generate flow (async + poll, like F1.2 sync flow)

```
[If 404] User clicks Generate button
  OR
[If stale] User clicks Regenerate button
  │
  ▼
POST /api/mega-reports/{start}/{end}/generate
  │
  ├─ 202 → generation started, begin polling
  ├─ 400 → ErrorAlert (missing months, invalid range)
  ├─ 404 → ErrorAlert (no data for range)
  ├─ 500 → ErrorAlert (pipeline error — missing config, build error)
  └─ network → ErrorAlert "Cannot reach server"
  │
  ▼
[While generating] poll GET /api/mega-reports/{start}/{end}/status every 2s
  │
  ├─ status="generating" → show spinner + "Generating mega report..."
  ├─ status="success"    → stop polling, fetch GET /api/mega-reports/{start}/{end} → render all 13 sections
  └─ status="failed"     → stop polling, show ErrorAlert with errors
  │
  ▼
If user navigates away and back, mount-time GET checks status:
  ├─ 200 status="generating" → resume polling
  ├─ 200 status="success"    → render report
  └─ 404                     → show GenerateButton
```

**Note:** Generate is async — POST returns 202 immediately (report built in background). Frontend polls `/status` every 2s. Navigate-away safe.

### PDF export flow

```
User clicks "Export PDF" button
  │
  ▼
POST /api/mega-reports/{start}/{end}/pdf
  │
  ├─ 200 (application/pdf) → browser downloads mega_report_{start}_{end}.pdf
  ├─ 404                   → ErrorAlert "Generate report first"
  ├─ 400                   → ErrorAlert (invalid range)
  ├─ 500                   → ErrorAlert "PDF generation failed" (WeasyPrint error)
  └─ network               → ErrorAlert "Cannot reach server"
  │
  ▼
[Backend] mega_pdf.py:
  build_context() → assemble_html() → WeasyPrint → PDF bytes
  Uses sections/css.py CSS (mega's own CSS, not shared SCSS)
  Returns StreamingResponse (application/pdf)
  Content-Disposition: attachment; filename="mega_report_{start}_{end}.pdf"
```

### Stale detection (backend)

```
GET /api/mega-reports/{start}/{end}
  │
  ▼
Read {start}_{end}_mega_report.json
  │
  ▼
Check calculation_version:
  ├─ report.calculation_version != CURRENT → stale: true
  └─ equal → check per-month txn counts
  │
  ▼
For each month in range:
  Read {month}_ps_raw.json
  Compare: report.txn_counts[month] vs len(ps_raw transactions)
  │
  ├─ all equal   → stale: false
  └─ any mismatch → stale: true
  │
  ▼
Return MegaReportResponse { ...contract, stale: bool }
```

### Generate status lifecycle

```
[before generate]  no status file (404 on status endpoint)
[during generate]  status: "generating"  ← written by mega_builder BEFORE building
[on success]       status: "success"     ← updated after JSON written
[on failure]       status: "failed"      ← updated on exception, errors populated
```

Status stored in `{start}_{end}_mega_report_status.json` (separate from report JSON).

### Failure + retry behavior

| Failure | Backend behavior | Frontend display |
|---------|-------------------|-------------------|
| Month not synced (no ps_raw) | 400 "month X has no data, sync it first" | ErrorAlert + link to Sync page |
| Report not generated (no JSON) | 404 "no report generated yet" | MegaGenerateButton |
| Generate already running | 202 (already generating, resume polling) | spinner |
| Pipeline error (missing config) | status="failed", errors=["..."] | ErrorAlert with errors |
| WeasyPrint error (PDF) | 500 "PDF generation failed" | ErrorAlert |
| Invalid range (start > end) | 400 "start must be before or equal to end" | ErrorAlert |
| Invalid month format | 400 "invalid month format" | ErrorAlert |
| Atomic write fails | 500 "storage write failed" | ErrorAlert |
| Network error (FE→BE) | N/A | ErrorAlert "Cannot reach server" |

**No retry logic.** User re-triggers manually.

### Observability touchpoints

| Touchpoint | What | Where |
|-----------|------|-------|
| Mega report generate start | range, timestamp | FastAPI access log + status file |
| Mega report generate result | range, duration, month_count, txn_count, status | status file + stdout |
| Mega report read | range, stale, txn_count | FastAPI access log |
| PDF generate | range, duration, bytes | FastAPI access log + stdout |
| Pipeline error | failure type, message, traceback | FastAPI exception handler (stderr) |
| Storage write | filename, bytes | storage.py stdout log |
| Frontend fetch | endpoint, status, duration | browser devtools (no custom logging) |

### Data flow summary

```
CLI standalone (AI skill):
  build_context() → assemble_html() + sections/css.py → WeasyPrint → PDF
  No React needed.

React app (UI):
  GET /api/mega-reports → GeneratedReportsList
  GET /api/mega-reports/{start}/{end} → MegaReportView (13 sections via Radix + SVG)
  POST /api/mega-reports/{start}/{end}/generate → 202 → poll /status every 2s → success → fetch report
  POST /api/mega-reports/{start}/{end}/pdf → PDF download (mega_report_{start}_{end}.pdf)

Shared resources:
  data/private/{start}_{end}_mega_report.json          ← report JSON (generated on demand)
  data/private/{start}_{end}_mega_report_status.json    ← generate status (running/success/failed)
  data/private/{month}_ps_raw.json                      ← raw sync data (from F1.1)
  data/private/category_roles.json                      ← KPI role mapping
  data/private/detailed_section_mapping.json            ← section mapping
  data/private/category_catalog.json                     ← category hierarchy
  data/private/account_mappings.json                    ← account bindings
  data/private/partner_labels.json                      ← partner names
  data/private/recommendations.json                     ← AI recommendations (optional)
```

---

### Alignment check (ANSWERED 2026-07-29)

1. **Generate async** — ✅ Async + poll like F1.2. POST returns 202, poll /status every 2s.
2. **PDF filename** — ✅ `mega_report_{start}_{end}.pdf`
3. **Stale detection** — ✅ Per-month txn count + calculation_version.
4. **Missing months** — ✅ 400 with month list. Frontend shows warning before generate.

---

## L4: Contracts

### API endpoints (full)

#### Mega reports — generated reports list

```
GET /api/mega-reports
```
- No params
- Scans `data/private/` for `*_mega_report.json` files using regex `^(\d{4}-\d{2})_(\d{4}-\d{2})_mega_report\.json$`
- Parses filenames → `{start}_{end}` ranges
- Response 200: `{"reports": [{"start": "2026-01", "end": "2026-07"}, ...]}` (sorted newest first)
- Response 200 (empty): `{"reports": []}`

#### Mega reports — get mega report

```
GET /api/mega-reports/{start}/{end}
```
- Path: `start` (required, `^\d{4}-\d{2}$`), `end` (required, `^\d{4}-\d{2}$`)
- Validates start ≤ end
- Validates all months in range have `ps_raw.json` files
- Reads `{start}_{end}_mega_report.json` + stale check (txn counts + calc version)
- Response 200: `MegaReportResponse` (contract + pre-computed views + `stale: bool`)
- Response 404: `{"detail": "no report generated yet"}`
- Response 400: `{"detail": "start must be before or equal to end"}` or `{"detail": "month X has no data, sync it first"}`
- Response 400: `{"detail": "invalid month format"}`

#### Mega reports — generate (async)

```
POST /api/mega-reports/{start}/{end}/generate
```
- Path: `start`, `end` (required, `^\d{4}-\d{2}$`)
- **Async**: starts generation in background, returns 202 immediately
- Concurrent guard: if status="generating" → return 202 with current status (no new generation)
- Validates all months in range have `ps_raw.json` files
- Response 202: `GenerateStatus` (status="generating")
- Response 400: `{"detail": "invalid month format"}` or `{"detail": "month X has no data, sync it first"}`
- Response 500: `{"detail": "generation failed to start"}`

#### Mega reports — generate status

```
GET /api/mega-reports/{start}/{end}/status
```
- Path: `start`, `end` (required, `^\d{4}-\d{2}$`)
- Reads `{start}_{end}_mega_report_status.json`
- Response 200: `GenerateStatus`
- Response 404: `{"detail": "no generation has been run yet"}`

#### Mega reports — PDF export

```
POST /api/mega-reports/{start}/{end}/pdf
```
- Path: `start`, `end` (required, `^\d{4}-\d{2}$`)
- Response 200: `application/pdf` binary stream, `Content-Disposition: attachment; filename="mega_report_{start}_{end}.pdf"`
- Response 404: `{"detail": "no report generated yet"}`
- Response 400: `{"detail": "invalid month format"}`
- Response 500: `{"detail": "PDF generation failed"}`

### Pre-computed view JSON shapes

#### detail_agg (core aggregation)
```json
{
  "months": ["2026-01", "2026-02", ...],
  "cats": {
    "34025255": {
      "title": "Supermarket",
      "section": "common",
      "partner_a_paid": [0.0, ...],
      "partner_b_paid": [0.0, ...],
      "partner_a_received": [0.0, ...],
      "partner_b_received": [0.0, ...],
      "partner_a_net": [0.0, ...],
      "partner_b_net": [0.0, ...],
      "total": [0.0, ...],
      "count": [0, ...],
      "is_reimbursement": false
    }
  },
  "cc_paydowns": {
    "Visa": {"2026-01": 5000.0, "2026-02": 3000.0},
    "Mastercard": {"2026-01": 2000.0}
  },
  "excluded_transactions": {
    "2026-01": [
      {"date": "2026-01-15", "description": "Transfer", "category": "Internal", "owner": "partner_a", "amount": -500.0}
    ]
  },
  "trips": [
    {"label": "Oslo trip", "transactions": [...], "total": -3500.0}
  ],
  "series": {
    "income": {"partner_a": [...], "partner_b": [...], "total": [...]},
    "savings": {"net_partner_a": [...], "net_partner_b": [...], "total": [...], "investment_net_partner_a": [...], "investment_net_partner_b": [...], "investment_net_total": [...]},
    "real_spend": {"partner_a": [...], "partner_b": [...], "total": [...]},
    "net_cash": {"partner_a": [...], "partner_b": [...], "total": [...]}
  },
  "cumulative": {
    "income": {"partner_a": 250000.0, "partner_b": 200000.0, "total": 450000.0},
    "savings": {"net_partner_a": 30000.0, "net_partner_b": 25000.0, "total": 55000.0, "investment_net_partner_a": 10000.0, "investment_net_partner_b": 8000.0, "investment_net_total": 18000.0},
    "real_spend": {"partner_a": 180000.0, "partner_b": 150000.0, "total": 330000.0},
    "net_cash": {"partner_a": 70000.0, "partner_b": 50000.0, "total": 120000.0}
  }
}
```

#### salary_allocation
```json
{
  "income": 450000.0,
  "entries": [
    {"id": "34025245", "title": "Groceries", "amount": 36000.0},
    {"id": "role-net_savings", "title": "Net savings", "amount": 55000.0}
  ],
  "unavailable_reason": null
}
```
If unavailable: `{"income": 0.0, "entries": [], "unavailable_reason": "reason string"}`.

#### recommendations (optional, null if no artifact)
```json
{
  "schema_version": "1",
  "generated_at": "2026-07-29T12:00:00Z",
  "period": {"start": "2026-01", "end": "2026-07"},
  "recommendations": [
    {
      "id": "rec_1",
      "title": "Reduce grocery spend",
      "body": "Grocery spend is 15% above average.",
      "severity": "medium",
      "evidence": ["Groceries: 36000 NOK over 7 months", "Average: 4250 NOK/month"]
    }
  ]
}
```

#### monthly_kpi_pages (per-month KPI data)
```json
[
  {
    "month": "2026-01",
    "kpis": {
      "partner_a": {"income": 35000.0, "real_spend": 28000.0, "net_cash": 7000.0, "net_savings": 3000.0, "investment": 1000.0},
      "partner_b": {"income": 30000.0, "real_spend": 25000.0, "net_cash": 5000.0, "net_savings": 2000.0, "investment": 800.0},
      "total": {"income": 65000.0, "real_spend": 53000.0, "net_cash": 12000.0, "net_savings": 5000.0, "investment": 1800.0}
    }
  }
]
```

### Pydantic models (new)

```python
# models/mega_reports.py
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class MegaReportRange(BaseModel):
    """One generated mega report range."""

    start: str
    end: str


class MegaReportList(BaseModel):
    """GET /api/mega-reports — sorted newest first."""

    reports: list[MegaReportRange]


class GenerateStatus(BaseModel):
    """GET /api/mega-reports/{start}/{end}/status — generation lifecycle."""

    status: Literal["generating", "success", "failed"]
    errors: list[str] = []
    started_at: str | None = None
    completed_at: str | None = None


class MegaReportResponse(BaseModel):
    """GET /api/mega-reports/{start}/{end} — contract + pre-computed views + stale flag."""

    start: str
    end: str
    stale: bool
    calculation_version: int
    txn_counts: dict[str, int]
    months: list[str]
    partner_labels: dict[str, str]
    # Core aggregation
    detail_agg: dict
    salary_allocation: dict
    recommendations: dict | None = None
    monthly_kpi_pages: list[dict]
    # NOTE: monthly_results (raw per-month contracts) EXCLUDED from GET response.
    # monthly_kpi_pages contains the pre-computed KPI data FE needs.
    # Raw per-month contracts contain normalized_transactions — too large for GET.
    # Add separate /detail endpoint later if needed.
```

### TypeScript types (frontend)

```typescript
// types/mega_report.ts
export interface MegaReportRange {
  start: string;
  end: string;
}

export interface MegaReportList {
  reports: MegaReportRange[];
}

export interface GenerateStatus {
  status: "generating" | "success" | "failed";
  errors: string[];
  started_at: string | null;
  completed_at: string | null;
}

export interface SalaryAllocation {
  income: number;
  entries: { id: string; title: string; amount: number }[];
  unavailable_reason: string | null;
}

export interface Recommendation {
  id: string;
  title: string;
  body: string;
  severity: "high" | "medium" | "low";
  evidence: string[];
}

export interface RecommendationsArtifact {
  schema_version: string;
  generated_at: string;
  period: { start: string; end: string };
  recommendations: Recommendation[];
}

export interface MonthlyKpiPage {
  month: string;
  kpis: {
    partner_a: { income: number; real_spend: number; net_cash: number; net_savings: number; investment?: number };
    partner_b: { income: number; real_spend: number; net_cash: number; net_savings: number; investment?: number };
    total: { income: number; real_spend: number; net_cash: number; net_savings: number; investment?: number };
  };
}

export interface DetailAgg {
  months: string[];
  cats: Record<string, {
    title: string;
    section: string;
    partner_a_paid: number[];
    partner_b_paid: number[];
    partner_a_received: number[];
    partner_b_received: number[];
    partner_a_net: number[];
    partner_b_net: number[];
    total: number[];
    count: number[];
    is_reimbursement: boolean;
  }>;
  cc_paydowns: Record<string, Record<string, number>>;
  excluded_transactions: Record<string, Array<{
    date: string;
    description: string;
    category: string;
    owner: string;
    amount: number;
  }>>;
  trips: Array<{
    label: string;
    transactions: Record<string, unknown>[];
    total: number;
  }>;
  series: {
    income: { partner_a: number[]; partner_b: number[]; total: number[] };
    savings: {
      net_partner_a: number[]; net_partner_b: number[]; total: number[];
      investment_net_partner_a: number[]; investment_net_partner_b: number[]; investment_net_total: number[];
    };
    real_spend: { partner_a: number[]; partner_b: number[]; total: number[] };
    net_cash: { partner_a: number[]; partner_b: number[]; total: number[] };
  };
  cumulative: {
    income: { partner_a: number; partner_b: number; total: number };
    savings: {
      net_partner_a: number; net_partner_b: number; total: number;
      investment_net_partner_a: number; investment_net_partner_b: number; investment_net_total: number;
    };
    real_spend: { partner_a: number; partner_b: number; total: number };
    net_cash: { partner_a: number; partner_b: number; total: number };
  };
}

export interface MegaReportResponse {
  start: string;
  end: string;
  stale: boolean;
  calculation_version: number;
  txn_counts: Record<string, number>;
  months: string[];
  partner_labels: Record<string, string>;
  detail_agg: DetailAgg;
  salary_allocation: SalaryAllocation;
  recommendations: RecommendationsArtifact | null;
  monthly_kpi_pages: MonthlyKpiPage[];
  // NOTE: monthly_results excluded from GET response (too large). monthly_kpi_pages has what FE needs.
}
```

### Data schemas (file storage)

- `data/private/{start}_{end}_mega_report.json` — report contract + pre-computed views
- `data/private/{start}_{end}_mega_report_status.json` — generate status
- `data/private/{month}_ps_raw.json` — raw transactions (from F1.1 sync)
- `data/private/category_roles.json` — KPI role mapping
- `data/private/detailed_section_mapping.json` — section mapping
- `data/private/category_catalog.json` — category hierarchy
- `data/private/account_mappings.json` — account bindings
- `data/private/partner_labels.json` — partner names
- `data/private/recommendations.json` — AI recommendations (optional)

### Error model (unified)

All non-2xx responses: `{"detail": "message"}` (FastAPI default, matches F1.1/F1.2).

### Testable acceptance criteria

| # | Test | Expected |
|---|------|----------|
| AC1 | GET /api/mega-reports (reports generated) | 200, reports list sorted newest first |
| AC2 | GET /api/mega-reports (none generated) | 200, `{"reports": []}` |
| AC3 | GET /api/mega-reports/2026-01/2026-07 (not generated) | 404, "no report generated yet" |
| AC4 | GET /api/mega-reports/2026-01/2026-07 (generated, not stale) | 200, MegaReportResponse with stale=false |
| AC5 | GET /api/mega-reports/2026-01/2026-07 (generated, stale) | 200, MegaReportResponse with stale=true |
| AC6 | GET /api/mega-reports/2026-07/2026-01 (start > end) | 400, "start must be before or equal to end" |
| AC7 | GET /api/mega-reports/invalid/2026-07 | 400, "invalid month format" |
| AC8 | GET /api/mega-reports/2026-01/2026-07 (month missing ps_raw) | 400, "month X has no data, sync it first" |
| AC9 | POST /api/mega-reports/2026-01/2026-07/generate | 202, status="generating" |
| AC10 | POST /api/mega-reports/2026-01/2026-07/generate (already generating) | 202, current status (no new generation) |
| AC11 | POST /api/mega-reports/2026-01/2026-07/generate (month missing) | 400, "month X has no data, sync it first" |
| AC12 | GET /api/mega-reports/2026-01/2026-07/status (never generated) | 404, "no generation has been run yet" |
| AC13 | GET /api/mega-reports/2026-01/2026-07/status (generating) | 200, status="generating" |
| AC14 | GET /api/mega-reports/2026-01/2026-07/status (success) | 200, status="success" |
| AC15 | GET /api/mega-reports/2026-01/2026-07/status (failed) | 200, status="failed", errors populated |
| AC16 | POST /api/mega-reports/2026-01/2026-07/pdf (generated) | 200, application/pdf, Content-Disposition: mega_report_2026-01_2026-07.pdf |
| AC17 | POST /api/mega-reports/2026-01/2026-07/pdf (not generated) | 404, "no report generated yet" |
| AC18 | CLI standalone: python -m mega.build_mega --start 2026-01 --end 2026-07 ... | produces PDF without React |
| AC19 | React app: /mega-reports renders MegaReportsPage with year picker + range picker + generated list | page loads |
| AC20 | React app: pick year → start/end filled Jan–Dec | year picker fills range |
| AC21 | React app: pick custom range via dual month picker | range updates |
| AC22 | React app: click generated report → report renders all 13 sections | all sections visible via Radix + SVG |
| AC22b | React app: click stale generated report → sections render + stale badge | stale badge visible alongside sections |
| AC23 | React app: 404 → MegaGenerateButton shows | button visible |
| AC24 | React app: click Generate → 202 → poll status → success → report renders | async flow works |
| AC25 | React app: stale badge shows when stale=true | badge visible |
| AC26 | React app: click Regenerate → 202 → poll → success → re-render | regenerate works |
| AC27 | React app: click Export PDF → downloads mega_report_{start}_{end}.pdf | file downloads |
| AC28 | React app: configured partner names shown | matches seed from `partners.json` |
| AC29 | React app: missing months warning shows before generate | warning visible |
| AC30 | React app: recommendations section shows cards if artifact exists | cards render |
| AC31 | React app: recommendations section shows empty state if no artifact | "No recommendations available" |
| AC32 | React app: all 4 chart types render (LineChart, StackedBarLineChart, MegaBarChart, SubcatStackedBarChart) | SVG charts visible |
| AC33 | React app: monthly KPI pages render for all months in range | per-month KPI cards visible |
| AC34 | React app: CC paydowns table renders per card per month | table visible |
| AC35 | React app: excluded transactions table renders | table visible |
| AC36 | React app: trips section renders clustered trip cards | cards visible |
| AC37 | React app: salary allocation table renders | table visible |
| AC38 | Generate status transitions: generating → success | status file transitions correctly |
| AC39 | Generate status transitions: generating → failed (errors) | status file reflects failure |
| AC40 | Navigate away during generate → back → resumes polling | navigate-away safe |

---

### Alignment check (ANSWERED 2026-07-29)

1. **MegaReportResponse shape** — ✅ Flat top-level fields. detail_agg as nested dict.
2. **40 ACs** — ✅ Enough.
3. **Pre-computed views** — ✅ Defined exact JSON shapes above.
4. **Recommendations null** — ✅ `null` if no artifact, object if present.

---

## L5: Implementation Plan

**Split into two sub-tasks:**
- **F1.3a — Backend** (mega report service + API + tests). ~25.5h.
- **F1.3b — Frontend** (mega report page + 13 sections + 4 charts + tests). ~51h.

F1.3b depends on F1.3a endpoints being live (B5 done). F1-F2 (API client + types + router) can start in parallel with B6-B8 (backend tests) — strict sequential is overly conservative.

---

### F1.3a — Backend (mega report service + API)

#### Ordered task list

| # | Task | Files | Depends on | Est |
|---|------|-------|-----------|-----|
| B1 | `mega_builder.py` — constructs argparse.Namespace from `data/private/` + calls `build_context()` + serializes `detail_agg` to JSON (series, cumulative, cats, cc_paydowns, trips, excluded, salary_allocation, recommendations, monthly_kpi_pages). Config bridging from `data/private/`. Writes `{start}_{end}_mega_report.json` + status file. | `services/mega_builder.py` | — | 7h |
| B2 | `mega_pdf.py` — constructs argparse.Namespace + calls `build_context()` → `assemble_html()` → WeasyPrint. Returns PDF bytes. Uses sections/css.py CSS. | `services/mega_pdf.py` | B1 | 2h |
| B3 | `models/mega_reports.py` — MegaReportList, MegaReportRange, MegaReportResponse. GenerateStatus imported from models/reports.py. | `models/mega_reports.py` | — | 0.5h |
| B4 | `routers/mega_reports.py` — GET /mega-reports, GET /mega-reports/{start}/{end} (stale check + month validation), POST /generate (async 202 + concurrent guard), GET /status, POST /pdf | `routers/mega_reports.py` | B1, B2, B3 | 4h |
| B5 | `main.py` — mount mega-reports router | `main.py` (update) | B4 | 0.5h |
| B6 | Backend unit tests — mega_builder (detail_agg port, stale check, status transitions, config bridging) | `tests/test_mega_builder.py` | B1 | 4h |
| B7 | Backend unit tests — mega_reports router (list, get, generate async, status, pdf, month validation, concurrent guard) | `tests/test_mega_reports.py` | B4 | 4h |
| B8 | Integration tests — AC1-AC18 (backend acceptance) | `tests/test_mega_acceptance.py` | B5 | 3h |
| R1 | Run existing mega pipeline test suites | `pytest src/mega/tests/` | B8 | 0.5h |
| R2 | Run existing F1.1 + F1.2 tests (sync, settings, partners, accounts, categories, monthly reports) | `pytest src/budget_api/tests/` | B8 | 0.5h |

**F1.3a total: ~26h**

#### Incremental delivery slices (F1.3a)

**Slice 1 — Backend foundation (B1-B2):** mega_builder + mega_pdf. No routers yet. Verify: `mega_builder.build_mega_report("2026-01", "2026-07")` writes JSON + status, `mega_pdf.generate_pdf("2026-01", "2026-07")` returns PDF bytes.

**Slice 2 — Backend routers (B3-B5):** All routers mounted. Verify: `uvicorn budget_api.main:app` starts, all endpoints respond. `GET /api/mega-reports` returns reports. `POST /api/mega-reports/2026-01/2026-07/generate` starts async generation. `GET /api/mega-reports/2026-01/2026-07` returns JSON.

**Slice 3 — Backend tests (B6-B8):** All 18 backend ACs pass (AC1-AC18). Verify: `pytest src/budget_api/tests/ -v` green.

**Slice 4 — Regression (R1-R2):** Existing mega + F1.1/F1.2 tests still pass. Verify: `pytest src/` green.

#### F1.3a definition of done

- [x] All 18 backend ACs pass (AC1-AC18)
- [x] CLI standalone: `python -m mega.build_mega --start 2026-01 --end 2026-07 ...` produces PDF without React
- [x] `GET /api/mega-reports` returns generated mega report ranges
- [x] `GET /api/mega-reports/{start}/{end}` returns contract JSON + stale flag (or 404)
- [x] `GET /api/mega-reports/{start}/{end}` returns 400 if any month missing
- [x] `POST /api/mega-reports/{start}/{end}/generate` starts async generation (202 + poll)
- [x] `POST /api/mega-reports/{start}/{end}/pdf` returns PDF binary stream
- [x] `pytest src/` regression green (existing mega + F1.1/F1.2)

---

### F1.3b — Frontend (mega report page + components)

**Depends on: F1.3a B5 done (endpoints live, JSON contract stable). F1-F2 can start in parallel with B6-B8 (backend tests).**

#### Ordered task list

| # | Task | Files | Depends on | Est |
|---|------|-------|-----------|-----|
| F1 | API client + types — `api/mega_reports.ts`, `types/mega_report.ts` | `client/src/api/`, `client/src/types/` | F1.3a B5 | 2h |
| F2 | Router + AppLayout — add /mega-reports route, Mega Reports nav link | `client/src/router.tsx`, `client/src/layouts/AppLayout.tsx` | F1 | 1h |
| F3 | MegaReportsPage + YearPicker + RangePicker + GeneratedReportsList | `client/src/pages/MegaReportsPage.tsx`, `client/src/components/mega-reports/YearPicker.tsx`, `RangePicker.tsx`, `GeneratedReportsList.tsx` | F2 | 4h |
| F4 | MegaReportView container — fetch report, 404→GenerateButton, stale→StaleBadge+Regenerate, PDF export button, poll status during generate | `client/src/components/mega-reports/MegaReportView.tsx`, `MegaGenerateButton.tsx`, `MegaStaleBadge.tsx`, `MegaPdfExportButton.tsx` | F3 | 3h |
| F5 | Charts — LineChart, StackedBarLineChart, MegaBarChart (reuse F1.2 if compatible), SubcatStackedBarChart (raw SVG in JSX, port from Python) | `client/src/components/mega-reports/charts/*.tsx` | F4 | 7h |
| F6 | KpiCoverSection — 6 KPI cards + 4 charts + salary allocation table | `client/src/components/mega-reports/sections/KpiCoverSection.tsx` | F4, F5 | 4h |
| F7 | IncomeSection — per-month table + stacked bar chart + cumulative line | `client/src/components/mega-reports/sections/IncomeSection.tsx` | F4, F5 | 3h |
| F8 | SavingsSection — table + line chart | `client/src/components/mega-reports/sections/SavingsSection.tsx` | F4, F5 | 2h |
| F9 | HomeSection — table + chart | `client/src/components/mega-reports/sections/HomeSection.tsx` | F4, F5 | 2h |
| F10 | CommonSection — table + chart | `client/src/components/mega-reports/sections/CommonSection.tsx` | F4, F5 | 2h |
| F11 | PersonalSection — table + SubcatStackedBarChart (parameterized by partner) | `client/src/components/mega-reports/sections/PersonalSection.tsx` | F4, F5 | 3h |
| F12 | TripsSection — clustered trip cards | `client/src/components/mega-reports/sections/TripsSection.tsx` | F4 | 2h |
| F13 | RecommendationsSection — recommendation cards or empty state | `client/src/components/mega-reports/sections/RecommendationsSection.tsx` | F4 | 1.5h |
| F14 | MonthliesSection — per-month KPI cards (all months in range) | `client/src/components/mega-reports/sections/MonthliesSection.tsx` | F4 | 3h |
| F15 | CcPaydownsSection — CC paydown table per card per month | `client/src/components/mega-reports/sections/CcPaydownsSection.tsx` | F4 | 2h |
| F16 | ExcludedSection — excluded transactions table | `client/src/components/mega-reports/sections/ExcludedSection.tsx` | F4 | 1.5h |
| F17 | AppendicesSection — placeholder | `client/src/components/mega-reports/sections/AppendicesSection.tsx` | F4 | 0.5h |
| F18 | Frontend unit tests — MegaReportsPage (year picker, range picker, generated list, 404, generate flow, stale) | `client/tests/MegaReportsPage.test.tsx` | F4 | 2h |
| F19 | Frontend unit tests — MegaReportView (all 13 sections render, charts render) | `client/tests/MegaReportView.test.tsx` | F6-F17 | 3h |

**F1.3b total: ~51h**

#### Incremental delivery slices (F1.3b)

**Slice 5 — Frontend scaffold (F1-F4):** API client + types + router + page + year/range pickers + generated list + report container. Verify: `pnpm dev` starts, /mega-reports renders, year picker fills range, generated list shows reports, clicking report fetches JSON (or shows GenerateButton on 404).

**Slice 6 — Frontend charts (F5):** 4 chart components (3 ported from Python + 1 reused from F1.2 if compatible). Verify: charts render as SVG with test data.

**Slice 7 — Frontend sections (F6-F17):** All 13 sections. Verify: full mega report renders from JSON, all sections visible, charts render, tables populate.

**Slice 8 — Frontend tests (F18-F19):** Vitest green. Verify: `pnpm test` passes.

#### F1.3b definition of done

- [x] All 22 frontend ACs pass (AC19-AC40)
- [x] React app: /mega-reports renders with year picker + range picker + generated list
- [x] All 13 sections render from contract JSON via Radix + SVG
- [x] Partner names from config shown
- [x] Generate button on 404, Regenerate button on existing, StaleBadge on stale
- [x] PDF export downloads `mega_report_{start}_{end}.pdf`
- [x] Recommendations section: cards if artifact exists, empty state if absent
- [x] Missing months warning shows before generate
- [x] All 3 chart types render (LineChart, StackedBarLineChart, MegaBarChart)
- [x] Monthly KPI pages render for all months in range
- [x] Vitest frontend tests green

### Risk controls

| Risk | Mitigation | Rollback |
|------|-----------|----------|
| detail_agg serialization correctness | detail_agg already a dict — verify JSON round-trip matches Python dict | Fall back to raw contract only (FE computes views) |
| Chart port math errors | Port one chart at a time, compare SVG output vs Python SVG | Use F1.2 chart components as fallback where possible |
| Contract JSON size (12 months) | monthly_results excluded from GET response — only monthly_kpi_pages sent | Add separate /detail endpoint if needed |
| Generate async race condition | threading.Lock guard (like F1.2), status file before build | Revert to sync generate |
| WeasyPrint PDF fails on mega CSS | Test PDF generation early (Slice 1), fix CSS before building frontend | Keep CLI PDF only, React renders without PDF export |
| Missing months UX frustration | Frontend shows missing-months warning before generate | Add "sync missing months" quick link to Sync page |
| 13 sections = long render time | Lazy-render sections (only render when scrolled into view) | Render all at once (acceptable for local app) |
| Existing mega pipeline regression | Regression gate R1 after backend changes | Revert backend changes |

### Test plan

| Layer | Tool | Coverage |
|-------|------|----------|
| Unit — mega_builder | pytest + mock data | detail_agg port, stale check, status transitions, config bridging |
| Unit — mega_reports router | pytest + TestClient | list, get, generate async, status, pdf, month validation, concurrent guard |
| Integration — backend | pytest + TestClient | AC1-AC18 (all backend acceptance criteria) |
| Unit — frontend components | Vitest + Testing Library | MegaReportsPage, MegaReportView |
| Integration — frontend API | Vitest + msw | API client fetch + error parsing |
| Regression | pytest | Existing mega + F1.1/F1.2 suites still green |

### Dependencies to install

**Backend:** No new dependencies (FastAPI, Pydantic, WeasyPrint already installed).

**Frontend:** No new dependencies (React, Radix, Tailwind, Vitest, MonthPicker already installed from F1.1/F1.2).

### File manifest (new files)

**Backend:**
```
src/budget_api/
  routers/
    mega_reports.py
  services/
    mega_builder.py
    mega_pdf.py
  models/
    mega_reports.py
  tests/
    test_mega_reports.py
    test_mega_builder.py
    test_mega_acceptance.py
```

**Frontend:**
```
client/src/
  pages/
    MegaReportsPage.tsx
    MegaReportsPage.module.css
  components/
    mega-reports/
      YearPicker.tsx
      RangePicker.tsx
      GeneratedReportsList.tsx
      MegaReportView.tsx
      MegaReportView.module.css
      sections/
        KpiCoverSection.tsx
        IncomeSection.tsx
        SavingsSection.tsx
        HomeSection.tsx
        CommonSection.tsx
        PersonalSection.tsx
        TripsSection.tsx
        RecommendationsSection.tsx
        MonthliesSection.tsx
        CcPaydownsSection.tsx
        ExcludedSection.tsx
        AppendicesSection.tsx
      MegaGenerateButton.tsx
      MegaStaleBadge.tsx
      MegaPdfExportButton.tsx
      charts/
        LineChart.tsx
        StackedBarLineChart.tsx
        MegaBarChart.tsx
  api/
    mega_reports.ts
  types/
    mega_report.ts
  tests/
    MegaReportsPage.test.tsx
    MegaReportView.test.tsx
```

### Definition of done (combined F1.3a + F1.3b)

- [x] All 40 ACs pass (AC1-AC40)
- [x] CLI standalone: `python -m mega.build_mega --start 2026-01 --end 2026-07 ...` produces PDF without React
- [x] `GET /api/mega-reports` returns generated mega report ranges
- [x] `GET /api/mega-reports/{start}/{end}` returns contract JSON + stale flag (or 404)
- [x] `GET /api/mega-reports/{start}/{end}` returns 400 if any month missing
- [x] `POST /api/mega-reports/{start}/{end}/generate` starts async generation (202 + poll)
- [x] `POST /api/mega-reports/{start}/{end}/pdf` returns PDF binary stream
- [x] React app: /mega-reports renders with year picker + range picker + generated list
- [x] All 13 sections render from contract JSON via Radix + SVG
- [x] Partner names from config shown
- [x] Generate button on 404, Regenerate button on existing, StaleBadge on stale
- [x] PDF export downloads `mega_report_{start}_{end}.pdf`
- [x] Recommendations section: cards if artifact exists, empty state if absent
- [x] Missing months warning shows before generate
- [x] All 3 chart types render (LineChart, StackedBarLineChart, MegaBarChart)
- [x] Monthly KPI pages render for all months in range
- [x] Vitest frontend tests green
- [x] `pytest src/` regression green (existing mega + F1.1/F1.2)
- [x] `.gitignore` excludes `data/private/`, `.env`, `client/node_modules`

---

### Alignment check — final approval:

1. **Split** — F1.3a backend (~25h) → F1.3b frontend (~48h). F1.3b depends on F1.3a. OK?
2. **F1.3a first** — backend service + API + tests, then F1.3b frontend. OK?
3. **Slice delivery** — 8 slices (4 backend, 4 frontend), each verifiable. OK?
4. **Approve implementation of F1.3a (backend) now?**