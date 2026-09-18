# F1.2 — React Pages for Monthly Reports

Status: DESIGN COMPLETE (L1-L5 written, pending final approval)
Date: 2026-07-28
Repo: Pocket-Smith-Reports

## Summary
React UI page for the monthly report pipeline. Migrate CLI report generation to API + React.
- **Monthly Reports page** — sidemenu (Radix) to pick month, renders full report via Radix UI + raw SVG
- **Backend migration** — CLI → API. Build report as JSON (pre-computed presentation views). CLI stays standalone for AI skill use.
- **PDF export** — backend WeasyPrint via shared CSS file. CLI path kept.
- **Category roles editor** — new Settings section, similar to accounts binding

## Dependencies
- F1.1 app shell (Vite + React + Router + Radix + Tailwind) — DONE
- F1.1 sync + settings pages — DONE
- Existing pipeline: `src/v4_pipeline/` (build_month_contract, accounting_html, charts)
- WeasyPrint (existing dependency)

## Decisions (from grill-me session, 2026-07-28)

| # | Decision |
|---|----------|
| Q1 | Radix UI native render + PDF export (no HTML injection) |
| Q2 | Monthly report only. Mom/mega → F1.3 |
| Q3 | API scans `data/private/*_ps_raw.json` for month list |
| Q4 | Backend stores report as JSON. FE renders with Radix. |
| Q5 | Full parity — all 8 presentation elements |
| Q6 | CLI → API migration. CLI kept for PDF + AI skill. |
| Q7 | Raw contract + pre-computed presentation views in JSON |
| Q8 | Raw SVG in React. No chart lib. |
| Q9 | Minimal theme only. Match app palette. |
| Q10 | Partner names from config (Fixture A/Fixture B). No UI editor. |
| Q11 | Excluded accounts from config (Settings F1.1). No per-report toggle. |
| Q12 | Shared JSON + shared CSS, dual render. CLI standalone. |
| Q13 | On-demand generate only. No auto-gen on sync. |
| Q14 | 404 + "Generate" button if no JSON. Regenerate for fresh data. |
| Q15 | Drop "v4" terminology. Use "monthly report". |
| Q16 | Generate returns 202 + poll status (async, like sync flow). Q28 supersedes. |
| Q17 | PDF as binary stream |
| Q18 | Stale flag: txn count in report vs ps_raw. Not equal → stale. |
| Q19 | Shared CSS file on disk. React + CLI both read it. |
| Q20 | Category roles editor in Settings (part of F1.2) |

---

## L1: Capabilities

### In-scope

#### Backend (CLI → API migration)
- **Report service** — wraps `build_month_contract()` + ports derived-view logic (`_root_totals`, `_owner_totals`, `_partner_panel`, `_category_highlights`, `_subcategory_overviews`, `_transaction_drilldowns`) → produces contract JSON with pre-computed presentation views
- **Month list endpoint** — scans `data/private/*_ps_raw.json`, returns sorted month list (newest first)
- **Report JSON endpoint** — `GET /api/reports/monthly/{month}` returns contract JSON (404 if not generated yet). Includes `stale` flag (txn count mismatch vs ps_raw)
- **Generate endpoint** — `POST /api/reports/monthly/{month}/generate` starts async generation, returns 202. Poll `GET /api/reports/monthly/{month}/status` until success/failed.
- **PDF export endpoint** — `POST /api/reports/monthly/{month}/pdf` invokes CLI/WeasyPrint, returns PDF as binary stream
- **Shared CSS extraction** — extract monthly report minimal palette CSS from `accounting_html.py` to shared SCSS file on disk. React imports (scoped), CLI/WeasyPrint reads directly.
- **CLI stays standalone** — `build.py main()` unchanged. AI skill use: CLI generates JSON + PDF without React app running.
- **Generate status endpoint** — `GET /api/reports/monthly/{month}/status` returns generation status (generating/success/failed).
- **Category mappings CRUD** — `GET /api/category-mappings` (list, merges 3 files), `PUT /api/category-mappings/{category_id}` (assign KPI role + detailed section). Reads/writes `category_roles.json` + `detailed_section_mapping.json`.

#### Frontend (React + Radix UI)
- **Monthly Reports page** — new top-nav item (Sync / Settings / Monthly Reports)
- **Sidemenu (Radix)** — lists available months from API, pick one → view report
- **Report view** — renders all 8 presentation elements via Radix UI + raw SVG charts:
  1. Overview page (header + 3 summary metrics + partner panels A+B)
  2. KPI role summary (role-based KPI matrix per partner)
  3. Category highlights (top categories with bar tracks)
  4. Subcategory overviews (nested category breakdowns)
  5. Transaction drilldowns (per-category transaction tables)
  6. Detailed sections (income, savings, legacy — routed by mapping)
  7. Reconciliation (source vs report, balanced indicator)
  8. Charts (donut, horizontal bar, partner KPI matrix — raw SVG in JSX)
- **Generate button** — shows when no JSON exists (404). Triggers `POST /generate`
- **Regenerate button** — re-runs pipeline, overwrites JSON. Shows stale badge if txn counts mismatch.
- **PDF export button** — triggers `POST /pdf` → downloads PDF file
- **Category mappings editor (Settings)** — new section in Settings page. Category list → assign KPI role + detailed section per category (2 dropdowns). Similar UX to accounts binding. Saves to `category_roles.json` + `detailed_section_mapping.json` via API.
- **Loading/error/empty states** — generating spinner, 404 generate prompt, no months (sync first), API errors

### Out-of-scope (F1.2)
- Mom (multi-month range) report page → F1.3
- Mega (configurable-period + section registry) report page → F1.3
- Theme selector (minimal only — cyberpunk/medieval/oriental stay CLI-only)
- Partner label UI editor (config-only, read from `partner_labels.json`)
- Per-report excluded accounts toggle (config-only, managed in Settings F1.1)
- Auto-generate on sync (on-demand only)
- Auth layer (localhost-only, no auth)

### Success criteria
- CLI standalone: `python -m build --month 2026-07 ...` produces JSON + PDF without React app running
- `GET /api/reports/months` returns list of months with synced data
- `GET /api/reports/monthly/{month}` returns contract JSON with pre-computed views + `stale` flag (or 404)
- `POST /api/reports/monthly/{month}/generate` starts async generation, returns 202
- `GET /api/reports/monthly/{month}/status` returns generation status
- `POST /api/reports/monthly/{month}/pdf` returns PDF binary stream
- `GET /api/category-mappings` returns category → KPI role + detailed section mapping
- `PUT /api/category-mappings/{category_id}` updates KPI role + detailed section, saves to 2 files
- React app: Monthly Reports page with sidemenu renders on `localhost:5173`
- All 8 presentation elements render from contract JSON via Radix + SVG
- Partner names from config shown, not generic labels
- Minimal theme matches F1.1 app palette
- Generate button shows on 404, Regenerate button shows on existing report
- Stale badge shows when txn count mismatch
- PDF export downloads file matching CLI output
- Category mappings editor in Settings: list categories, assign KPI role + detailed section, save
- Shared CSS file: React + CLI both use it, visual parity

### Assumptions
- `data/private/*_ps_raw.json` files exist (synced via F1.1)
- `account_mappings.json`, `partner_labels.json`, `detailed_section_mapping.json`, `category_catalog.json`, `category_roles.json` exist in `data/private/`
- WeasyPrint installed (existing dependency for CLI)
- React app shell exists (F1.1 built it — Vite + React + Router + Radix + Tailwind)
- Contract JSON stored at `data/private/{month}_monthly_report.json`
- Shared CSS file extracted to a known path (TBD in L2)

### Risks
- **Full parity = large frontend build** — 8 presentation elements in Radix + SVG is substantial. Risk: scope creep, long delivery.
- **Shared CSS intersection** — React (Chromium) and WeasyPrint support different CSS subsets. Must constrain to intersection for visual parity.
- **Derived-view port** — Python helper functions produce HTML strings. Porting to JSON structures requires extracting data logic from HTML generation. Risk: logic duplication or divergence.
- **Contract JSON size** — `normalized_transactions` can be large (hundreds of txns/month). JSON file could be 100KB+. Acceptable for local app.
- **Category mappings editor scope** — adds backend CRUD + frontend section. Increases F1.2 scope.

---

### Alignment check (ANSWERED 2026-07-28)

1. **Contract JSON storage** — ✅ `data/private/{month}_monthly_report.json`
2. **Generate response** — ✅ 202 + poll status (async, Q28)
3. **PDF delivery** — ✅ Binary stream
4. **Stale detection** — ✅ Txn count mismatch → `stale: true`
5. **CLI + CSS** — ✅ Shared CSS file on disk, CLI reads directly
6. **Category roles** — ✅ Include in F1.2, Settings section

---

## L2: Components

### Existing code to reuse

| File | What it does | Reuse for F1.2 |
|------|-------------|----------------|
| `src/v4_pipeline/build.py` | `build_month_html()` → dict with contract + HTML. `main()` CLI. | Programmatic entry for report service. CLI stays. |
| `src/v4_pipeline/accounting.py` | `build_month_contract()` → raw contract. Config loaders. `KPI_ROLES`, `DETAILED_CATEGORY_SECTIONS` enums. | Core data builder. Role enums. |
| `src/v4_pipeline/accounting_html.py` | `render()` → HTML. Helper functions (`_root_totals`, `_owner_totals`, `_partner_panel`, `_category_highlights`, `_subcategory_overviews`, `_transaction_drilldowns`). CSS in `_REPORT_STYLES` + theme styles. | Port derived-view logic to JSON. Extract CSS to shared SCSS. |
| `src/v4_pipeline/charts.py` | `render_horizontal_bar`, `render_partner_kpi_matrix`, donut charts. SVG strings. | Port SVG logic to React JSX. |
| `src/v4_pipeline/data_loader.py` | `load(month, data_path, excluded)` → txn list | Data loading (unchanged). |
| `src/budget_api/main.py` | FastAPI app, 6 routers mounted, CORS | Mount new report + category-mappings routers. |
| `src/budget_api/services/storage.py` | `atomic_write_json`, `read_json`, path constants | Storage layer for report JSON. |
| `client/src/router.tsx` | `createBrowserRouter` with Sync + Settings routes | Add Monthly Reports route. |
| `client/src/layouts/AppLayout.tsx` | Top nav with Sync + Settings NavLinks | Add Monthly Reports nav link. |
| `client/src/api/client.ts` | Fetch wrapper (base URL, error parsing) | Report API functions. |
| `client/src/components/` | Radix UI wrappers, ErrorAlert, EmptyState, Pagination | Reuse for report page. |
| `client/src/pages/SettingsPage.tsx` | Settings page with 4 sections | Add category roles section. |

### Proposed components

#### Backend (new)

```
src/budget_api/
  main.py                              # UPDATE: mount report + category-mappings routers
  routers/
    reports.py                         # NEW: GET /months, GET /monthly/{month}, POST /generate, GET /status, POST /pdf
    category_mappings.py               # NEW: GET /api/category-mappings, PUT /api/category-mappings/{id}
  services/
    report_builder.py                  # NEW: wraps build_month_contract() + ports derived-view logic → JSON
    report_pdf.py                      # NEW: invokes CLI/WeasyPrint for PDF export
  models/
    reports.py                         # NEW: MonthList, MonthInfo, ReportContract, ReportResponse (with stale flag)
    category_mappings.py               # NEW: CategoryMapping, CategoryMappingList, CategoryMappingUpdate
  tests/
    test_reports.py
    test_report_builder.py
    test_category_mappings.py
    test_acceptance.py
```

#### Frontend (new)

```
client/src/
  router.tsx                           # UPDATE: add /reports route
  layouts/
    AppLayout.tsx                      # UPDATE: add Monthly Reports nav link
  pages/
    MonthlyReportsPage.tsx             # NEW: sidemenu + report view container
    MonthlyReportsPage.module.css
  components/
    reports/
      MonthSidebar.tsx                 # NEW: Radix RadioGroup listing months (vertical, single-select)
      ReportView.tsx                   # NEW: renders all 8 presentation elements from contract JSON
      ReportView.module.css
      OverviewSection.tsx              # NEW: header + 3 metrics + partner panels
      KpiRoleSummary.tsx               # NEW: role-based KPI matrix
      CategoryHighlights.tsx           # NEW: top categories with bar tracks
      SubcategoryOverviews.tsx         # NEW: nested category breakdowns
      TransactionDrilldowns.tsx        # NEW: per-category transaction tables
      DetailedSections.tsx             # NEW: income, savings, legacy sections
      ReconciliationSection.tsx        # NEW: source vs report, balanced indicator
      charts/
        DonutChart.tsx                 # NEW: raw SVG donut
        HorizontalBarChart.tsx         # NEW: raw SVG horizontal bar
        PartnerKpiMatrix.tsx           # NEW: raw SVG partner KPI matrix
      GenerateButton.tsx               # NEW: generate/regenerate trigger
      StaleBadge.tsx                   # NEW: stale indicator
      PdfExportButton.tsx              # NEW: PDF download trigger
    settings/
      CategoryMappingsEditor.tsx       # NEW: category list → role dropdowns (KPI role + detailed section)
      CategoryRoleRow.tsx              # NEW: per-category role assignment
  api/
    reports.ts                         # NEW: months, get report, generate, status, pdf functions
    category_mappings.ts               # NEW: list + update mapping functions
  types/
    report.ts                          # NEW: TS types matching backend report models
    category_mappings.ts               # NEW: TS types matching category mapping models
  styles/
    report-shared.scss                 # NEW: shared minimal palette CSS (React + CLI/WeasyPrint both read)
  tests/
    MonthlyReportsPage.test.tsx
    ReportView.test.tsx
    CategoryMappingsEditor.test.tsx
```

### Component responsibilities

#### Backend
- **report_builder.py** — `build_report(month) → dict`. Calls `build_month_contract()`, then ports `_root_totals`, `_owner_totals`, `_partner_panel`, `_category_highlights`, `_subcategory_overviews`, `_transaction_drilldowns` logic to produce JSON structures (not HTML). Returns full contract + pre-computed views. Writes to `{month}_monthly_report.json`.
- **report_pdf.py** — `generate_pdf(month) → bytes`. Invokes CLI path (`build_month_html()` → `render_html()` → WeasyPrint). Returns PDF bytes. Uses shared SCSS from `client/src/styles/report-shared.scss`.
- **routers/reports.py** — 5 endpoints: `GET /api/reports/months` (scan ps_raw files), `GET /api/reports/monthly/{month}` (read JSON + stale check), `POST /api/reports/monthly/{month}/generate` (async 202 + concurrent guard), `GET /api/reports/monthly/{month}/status` (generation status), `POST /api/reports/monthly/{month}/pdf` (PDF binary stream).
- **routers/category_mappings.py** — `GET /api/category-mappings` (merge `category_roles.json` + `detailed_section_mapping.json` + `category_catalog.json`), `PUT /api/category-mappings/{category_id}` (update KPI role + detailed section, write 2 files).
- **report-shared.scss** — Extracted minimal palette CSS. React imports via Vite SCSS. CLI/WeasyPrint reads file directly from `client/src/styles/report-shared.scss`. Constrained to CSS intersection of Chromium + WeasyPrint.

#### Frontend
- **MonthlyReportsPage.tsx** — Layout: MonthSidebar (left) + ReportView (right). Fetches month list on mount. Manages selected month state.
- **MonthSidebar.tsx** — Radix RadioGroup (vertical, single-select). Lists months (newest first). Click → set selected month. Minimal design.
- **ReportView.tsx** — Fetches `GET /api/reports/monthly/{month}`. On 404 → show GenerateButton. On 200 → render all 8 sections. On stale → show StaleBadge + RegenerateButton. PDF export button always visible.
- **OverviewSection.tsx** — Header (month), 3 summary metrics (paid/received/net), partner panels (A+B side by side with rows).
- **KpiRoleSummary.tsx** — Role-based KPI matrix per partner. Reads `kpis` from contract. Groups by KPI_ROLES.
- **CategoryHighlights.tsx** — Top categories with bar tracks. Reads pre-computed highlights.
- **SubcategoryOverviews.tsx** — Nested category breakdowns. Reads pre-computed subcat data.
- **TransactionDrilldowns.tsx** — Per-category transaction tables. Expandable. Reads pre-computed drilldowns.
- **DetailedSections.tsx** — Income, savings, legacy sections. Routed by `detailed_section_mapping`. Groups by DETAILED_CATEGORY_SECTIONS (mother categories).
- **ReconciliationSection.tsx** — Source vs report, balanced indicator.
- **charts/DonutChart.tsx** — Raw SVG donut. Port of `charts.py` donut logic to JSX.
- **charts/HorizontalBarChart.tsx** — Raw SVG horizontal bar. Port of `render_horizontal_bar`.
- **charts/PartnerKpiMatrix.tsx** — Raw SVG partner KPI matrix. Port of `render_partner_kpi_matrix`.
- **CategoryMappingsEditor.tsx** — Settings section. Fetches `GET /api/category-mappings` + `GET /api/categories`. Renders category list with two dropdowns per row: KPI role (6 values) + detailed section (10 values). Save → `PUT /api/category-mappings/{id}`. Groups by mother categories like the report.

### Category role enums (from existing code)

```python
# KPI roles (category_roles.json) — 6 values
KPI_ROLES = {"income", "savings", "spend", "personal_spend", "investment", "exclude"}

# Detailed section mapping (detailed_section_mapping.json) — 10 values
DETAILED_CATEGORY_SECTIONS = {
    "income_salary", "income_third_party", "savings", "home", "common",
    "personal_partner_a", "personal_partner_b", "trips", "cc_payments", "excluded"
}
```

Category roles editor assigns BOTH per category:
- KPI role (drives KPI summary section)
- Detailed section (drives detailed sections — the "mother categories" grouping)

### What we do NOT create
- No database (files only)
- No auth (localhost-only)
- No WebSocket (poll-based status, like sync flow)
- No mom/mega report pages (F1.3)
- No theme selector (minimal only)
- No partner label editor (config-only)
- No per-report excluded accounts toggle (config-only)

---

### Alignment check (ANSWERED 2026-07-28)

1. **Shared CSS location** — ✅ `client/src/styles/report-shared.scss`. CLI reads from there.
2. **Report builder** — ✅ New service file `report_builder.py` (clean separation).
3. **Category roles enum** — ✅ KPI_ROLES (6) + DETAILED_CATEGORY_SECTIONS (10). Editor assigns both. Groups by mother categories like report.
4. **MonthSidebar** — ✅ Radix RadioGroup (vertical, single-select, minimal design).
5. **Rename v4 → monthly** — ✅ Rename user-facing references. Pipeline dir `src/v4_pipeline/` kept as-is (actual path, too risky to rename mid-project).

---

## L3: Interactions

### Main flow — view monthly report

```
User navigates to /reports (Monthly Reports page)
  │
  ▼
MonthlyReportsPage mounts
  │
  ▼
GET /api/reports/months
  │
  ├─ 200 (empty) → EmptyState: "No synced months. Run sync first."
  ├─ 200 (list)  → MonthSidebar renders months (newest first)
  └─ 500         → ErrorAlert: "Cannot reach server"
  │
  ▼
User clicks month in MonthSidebar (Radix RadioGroup)
  │
  ▼
ReportView fetches GET /api/reports/monthly/{month}
  │
  ├─ 200 (not stale) → render all 8 sections + PDF export button + Regenerate button
  ├─ 200 (stale)     → render all 8 sections + StaleBadge + Regenerate button + PDF export
  ├─ 404             → show GenerateButton ("No report generated yet")
  ├─ 500             → ErrorAlert
  └─ network error   → ErrorAlert "Cannot reach server"
```

### Generate flow (async + poll, like sync flow)

```
[If 404] User clicks Generate button
  OR
[If stale] User clicks Regenerate button
  │
  ▼
POST /api/reports/monthly/{month}/generate
  │
  ├─ 202 → generation started, begin polling
  ├─ 400 → ErrorAlert (invalid month format)
  ├─ 500 → ErrorAlert (pipeline error — missing data, config error)
  └─ network → ErrorAlert "Cannot reach server"
  │
  ▼
[While generating] poll GET /api/reports/monthly/{month}/status every 2s
  │
  ├─ status="generating" → show spinner + "Generating report..."
  ├─ status="success"    → stop polling, fetch GET /api/reports/monthly/{month} → render all 8 sections
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
POST /api/reports/monthly/{month}/pdf
  │
  ├─ 200 (application/pdf) → browser downloads monthly_report_{month}.pdf
  ├─ 404                   → ErrorAlert "Generate report first"
  ├─ 500                   → ErrorAlert "PDF generation failed" (WeasyPrint error)
  └─ network               → ErrorAlert "Cannot reach server"
  │
  ▼
[Backend] report_pdf.py:
  build_month_html(month, ...) → render_html() → WeasyPrint → PDF bytes
  Reads shared SCSS from client/src/styles/report-shared.scss
  Returns StreamingResponse (application/pdf)
  Content-Disposition: attachment; filename="monthly_report_{month}.pdf"
```

### Category roles editor flow (Settings page)

```
User navigates to Settings → Category Roles section
  │
  ▼
GET /api/category-mappings (merged with category_catalog for display)
  │
  ├─ 200 (list) → render CategoryMappingsEditor (category list with 2 dropdowns per row)
  ├─ 200 (empty) → EmptyState: "No categories. Run sync first."
  └─ 500 → ErrorAlert
  │
  ▼
Per row: category title + KPI role dropdown (6 values) + detailed section dropdown (10 values)
  │
  ▼
User changes dropdown → clicks "Save" (per-row, like accounts binding)
  │
  ▼
PUT /api/category-mappings/{category_id} {kpi_role, detailed_section}
  │
  ├─ 200 → show "Saved" on row
  ├─ 400 → ErrorAlert (invalid role / section)
  ├─ 404 → ErrorAlert (category not found)
  └─ 500 → ErrorAlert (write failed)
  │
  ▼
Next report regenerate picks up new roles
```

### Stale detection (backend)

```
GET /api/reports/monthly/{month}
  │
  ▼
Read {month}_monthly_report.json
  │
  ▼
Read {month}_ps_raw.json
  │
  ▼
Compare: report.txn_count vs len(ps_raw transactions)
  │
  ├─ equal   → stale: false
  └─ not equal → stale: true
  │
  ▼
Return ReportResponse { ...contract, stale: bool }
```

### Generate status lifecycle

```
[before generate]  no status file (404 on status endpoint)
[during generate]  status: "generating"  ← written by report_builder BEFORE building
[on success]       status: "success"     ← updated after JSON written
[on failure]       status: "failed"      ← updated on exception, errors populated
```

Status stored in `{month}_monthly_report_status.json` (separate from report JSON).

### Failure + retry behavior

| Failure | Backend behavior | Frontend display |
|---------|-------------------|-------------------|
| Month not synced (no ps_raw) | 404 "no data for this month" | ErrorAlert + link to Sync page |
| Report not generated (no JSON) | 404 "no report generated yet" | GenerateButton |
| Generate already running | 202 (already generating, resume polling) | spinner |
| Pipeline error (missing config) | status="failed", errors=["..."] | ErrorAlert with errors |
| WeasyPrint error (PDF) | 500 "PDF generation failed" | ErrorAlert |
| Invalid month format | 400 "invalid month format" | ErrorAlert |
| Category mappings file missing | 404 "no categories — run sync first" | EmptyState |
| Category not found (roles) | 404 "category not found" | ErrorAlert on row |
| Invalid KPI role | 400 "invalid kpi_role" | ErrorAlert on row |
| Invalid detailed section | 400 "invalid detailed_section" | ErrorAlert on row |
| Atomic write fails | 500 "storage write failed" | ErrorAlert |
| Network error (FE→BE) | N/A | ErrorAlert "Cannot reach server" |

**No retry logic.** User re-triggers manually.

### Observability touchpoints

| Touchpoint | What | Where |
|-----------|------|-------|
| Report generate start | month, timestamp | FastAPI access log + status file |
| Report generate result | month, duration, txn_count, status | status file + stdout |
| Report read | month, stale, txn_count | FastAPI access log |
| PDF generate | month, duration, bytes | FastAPI access log + stdout |
| Category mapping update | category_id, old_role, new_role | FastAPI access log |
| Pipeline error | failure type, message, traceback | FastAPI exception handler (stderr) |
| Storage write | filename, bytes | storage.py stdout log |
| Frontend fetch | endpoint, status, duration | browser devtools (no custom logging) |

### Data flow summary

```
CLI standalone (AI skill):
  build_month_contract() → JSON file
  render_html() + shared SCSS → WeasyPrint → PDF
  No React needed.

React app (UI):
  GET /api/reports/months → MonthSidebar
  GET /api/reports/monthly/{month} → ReportView (8 sections via Radix + SVG)
  POST /api/reports/monthly/{month}/generate → 202 → poll /status every 2s → success → fetch report
  POST /api/reports/monthly/{month}/pdf → PDF download (monthly_report_{month}.pdf)
  GET /api/category-mappings → CategoryMappingsEditor
  PUT /api/category-mappings/{id} → save mapping

Shared resources:
  data/private/{month}_monthly_report.json         ← report JSON (generated on demand)
  data/private/{month}_monthly_report_status.json   ← generate status (running/success/failed)
  data/private/{month}_ps_raw.json                  ← raw sync data (from F1.1)
  data/private/category_roles.json                  ← KPI role mapping (editable via Settings)
  data/private/detailed_section_mapping.json        ← section mapping (editable via Settings)
  client/src/styles/report-shared.scss              ← shared CSS (React + CLI both read)
```

---

### Alignment check (ANSWERED 2026-07-28)

1. **Detailed section mapping editor** — ✅ Yes, also edit `detailed_section_mapping.json` via Settings UI. Two editors.
2. **PDF filename** — ✅ `monthly_report_{month}.pdf`
3. **Generate async** — ✅ Async + poll like sync flow. POST returns 202, poll `/status` every 2s.
4. **Category roles dropdowns** — ✅ Two dropdowns per row (KPI role + detailed section).

---

## L4: Contracts

### API endpoints (full)

#### Reports — month list

```
GET /api/reports/months
```
- No params
- Scans `data/private/` for `*_ps_raw.json` files
- Response 200: `{"months": ["2026-07", "2026-06", "2026-05", ...]}` (sorted descending)
- Response 200 (empty): `{"months": []}`

#### Reports — get monthly report

```
GET /api/reports/monthly/{month}
```
- Path: `month` (required, `^\d{4}-\d{2}$`)
- Reads `{month}_monthly_report.json` + compares txn count vs `{month}_ps_raw.json`
- Response 200: `ReportResponse` (contract + pre-computed views + `stale: bool`)
- Response 404: `{"detail": "no report generated yet"}`
- Response 400: `{"detail": "invalid month format"}`

#### Reports — generate (async)

```
POST /api/reports/monthly/{month}/generate
```
- Path: `month` (required, `^\d{4}-\d{2}$`)
- **Async**: starts generation in background, returns 202 immediately
- Concurrent guard: if status="generating" → return 202 with current status (no new generation)
- Response 202: `GenerateStatus` (status="generating")
- Response 400: `{"detail": "invalid month format"}`
- Response 404: `{"detail": "no data for this month"}` (no ps_raw file)
- Response 500: `{"detail": "generation failed to start"}`

#### Reports — generate status

```
GET /api/reports/monthly/{month}/status
```
- Path: `month` (required, `^\d{4}-\d{2}$`)
- Reads `{month}_monthly_report_status.json`
- Response 200: `GenerateStatus`
- Response 404: `{"detail": "no generation has been run yet"}`

#### Reports — PDF export

```
POST /api/reports/monthly/{month}/pdf
```
- Path: `month` (required, `^\d{4}-\d{2}$`)
- Response 200: `application/pdf` binary stream, `Content-Disposition: attachment; filename="monthly_report_{month}.pdf"`
- Response 404: `{"detail": "no report generated yet"}`
- Response 400: `{"detail": "invalid month format"}`
- Response 500: `{"detail": "PDF generation failed"}`

#### Category mappings — list

```
GET /api/category-mappings
```
- Merges `category_roles.json` (KPI roles) + `detailed_section_mapping.json` (sections) + `category_catalog.json` (titles)
- Response 200: `CategoryMappingList`
- Response 404: `{"detail": "no categories — run sync first"}`

#### Category mappings — update

```
PUT /api/category-mappings/{category_id}
```
- Path: `category_id` (string, PS category ID)
- Body: `CategoryMappingUpdate` `{"kpi_role": "...", "detailed_section": "..."}`
- Validation: `kpi_role` in KPI_ROLES, `detailed_section` in DETAILED_CATEGORY_SECTIONS
- Writes to `category_roles.json` (kpi_role) + `detailed_section_mapping.json` (detailed_section)
- Response 200: `CategoryMapping` (updated)
- Response 400: `{"detail": "invalid kpi_role"}` or `{"detail": "invalid detailed_section"}`
- Response 404: `{"detail": "category not found"}`

### Pre-computed view JSON shapes

#### root_totals
```json
{
  "paid": 45000.00,
  "received": 42000.00,
  "net": -3000.00,
  "count": 127
}
```
From `_root_totals()`: sum of paid/received/net/count across root categories (parent_id is None).

#### owner_totals
```json
{
  "partner_a": {"paid": 25000.00, "received": 22000.00, "net": -3000.00},
  "partner_b": {"paid": 20000.00, "received": 20000.00, "net": 0.00}
}
```
From `_owner_totals()`: per-partner sum of paid/received/net across root categories.

#### partner_panels
```json
{
  "partner_a": {
    "label": "Fixture A",
    "paid": 25000.00,
    "received": 22000.00,
    "net": -3000.00,
    "net_class": "neg"
  },
  "partner_b": {
    "label": "Fixture B",
    "paid": 20000.00,
    "received": 20000.00,
    "net": 0.00,
    "net_class": "pos"
  }
}
```
From `_partner_panel()`: label from `partner_labels.json`, values from `owner_totals`, `net_class` = "pos" if net >= 0 else "neg".

#### category_highlights
```json
[
  {
    "title": "Groceries",
    "net": -4500.00,
    "bar_width_pct": 100.0
  },
  {
    "title": "Rent",
    "net": -3200.00,
    "bar_width_pct": 71.1
  }
]
```
From `_category_highlights()`: top 5 root categories by abs(net), sorted descending. `bar_width_pct` = abs(net) / largest_abs_net * 100.

#### subcategory_overviews
```json
[
  {
    "root_title": "Groceries",
    "root_id": "34025245",
    "children": [
      {
        "title": "Supermarket",
        "net": -2800.00,
        "bar_width_pct": 100.0
      },
      {
        "title": "Convenience",
        "net": -1700.00,
        "bar_width_pct": 60.7
      }
    ]
  }
]
```
From `_subcategory_overviews()`: per root category with children, children sorted by abs(net) descending. `bar_width_pct` = abs(net) / largest_child_abs_net * 100. Only roots that have children included.

#### transaction_drilldowns
```json
[
  {
    "root": {"id": "34025245", "title": "Groceries"},
    "leaf": {"id": "34025255", "title": "Supermarket"},
    "title": "Groceries / Supermarket",
    "records": [
      {
        "date": "2026-07-03",
        "payee": "Rema 1000",
        "owner": "Fixture A",
        "note": "Weekly shop",
        "amount": -450.50
      },
      {
        "date": "2026-07-10",
        "payee": "Kiwi",
        "owner": "Fixture B",
        "note": "-",
        "amount": -320.00
      }
    ]
  }
]
```
From `_transaction_drilldowns()`: grouped by (root_id, leaf_id). `title` = leaf title if root==leaf, else "root / leaf". Records sorted by (date, id). `owner` = partner_labels[record["owner"]] (name, not key). `payee` = "Unspecified" if null. `note` = "-" if null.

### Raw contract shapes (from `build_month_contract()`)

#### normalized_transactions (list)
```json
[
  {
    "id": "txn_123",
    "date": "2026-07-03",
    "amount": -450.50,
    "payee": "Rema 1000",
    "note": "Weekly shop",
    "account_id": "acc_1",
    "account_name": "Checking",
    "owner": "partner_a",
    "category_path": [
      {"id": "34025245", "title": "Groceries"},
      {"id": "34025255", "title": "Supermarket"}
    ],
    "is_transfer": false
  }
]
```

#### categories (list)
```json
[
  {
    "id": "34025245",
    "title": "Groceries",
    "parent_id": null,
    "path": [{"id": "34025245", "title": "Groceries"}],
    "paid": 4500.00,
    "received": 0.00,
    "net": -4500.00,
    "count": 15,
    "owners": {
      "partner_a": {"paid": 2800.00, "received": 0.00, "net": -2800.00},
      "partner_b": {"paid": 1700.00, "received": 0.00, "net": -1700.00}
    }
  }
]
```

#### reconciliation
```json
{
  "source": 42000.00,
  "report": 42000.00,
  "difference": 0.00
}
```

#### kpis (optional, if category_roles configured)
```json
{
  "income": {"paid": 0.00, "received": 42000.00, "net": 42000.00},
  "savings": {"paid": 5000.00, "received": 0.00, "net": -5000.00},
  "spend": {"paid": 30000.00, "received": 0.00, "net": -30000.00},
  "personal_spend": {"paid": 7000.00, "received": 0.00, "net": -7000.00},
  "investment": {"paid": 0.00, "received": 0.00, "net": 0.00},
  "exclude": {"paid": 0.00, "received": 0.00, "net": 0.00}
}
```

### Pydantic models (new)

```python
# models/reports.py
from typing import Literal
from pydantic import BaseModel

class MonthList(BaseModel):
    months: list[str]

class GenerateStatus(BaseModel):
    status: Literal["generating", "success", "failed"]
    errors: list[str] = []
    started_at: str | None = None
    completed_at: str | None = None

class ReportResponse(BaseModel):
    month: str
    stale: bool
    txn_count: int
    # Raw contract
    normalized_transactions: list[dict]
    categories: list[dict]
    reconciliation: dict
    detailed_section_mapping: dict | None = None
    kpis: dict | None = None
    # Pre-computed presentation views
    root_totals: dict
    owner_totals: dict
    partner_panels: dict
    category_highlights: list[dict]
    subcategory_overviews: list[dict]
    transaction_drilldowns: list[dict]
    partner_labels: dict

# models/category_mappings.py
KPI_ROLES = {"income", "savings", "spend", "personal_spend", "investment", "exclude"}
DETAILED_CATEGORY_SECTIONS = {
    "income_salary", "income_third_party", "savings", "home", "common",
    "personal_partner_a", "personal_partner_b", "trips", "cc_payments", "excluded"
}

class CategoryMapping(BaseModel):
    category_id: str
    category_title: str
    kpi_role: str | None
    detailed_section: str | None

class CategoryMappingList(BaseModel):
    categories: list[CategoryMapping]

class CategoryMappingUpdate(BaseModel):
    kpi_role: str
    detailed_section: str
```

### TypeScript types (frontend)

```typescript
// types/report.ts
export interface MonthList {
  months: string[];
}

export interface GenerateStatus {
  status: "generating" | "success" | "failed";
  errors: string[];
  started_at: string | null;
  completed_at: string | null;
}

export interface RootTotals {
  paid: number;
  received: number;
  net: number;
  count: number;
}

export interface OwnerTotals {
  partner_a: { paid: number; received: number; net: number };
  partner_b: { paid: number; received: number; net: number };
}

export interface PartnerPanel {
  label: string;
  paid: number;
  received: number;
  net: number;
  net_class: "pos" | "neg";
}

export interface CategoryHighlight {
  title: string;
  net: number;
  bar_width_pct: number;
}

export interface SubcategoryOverview {
  root_title: string;
  root_id: string;
  children: CategoryHighlight[];
}

export interface TransactionDrilldown {
  root: { id: string; title: string };
  leaf: { id: string; title: string };
  title: string;
  records: {
    date: string;
    payee: string;
    owner: string;
    note: string;
    amount: number;
  }[];
}

export interface ReportResponse {
  month: string;
  stale: boolean;
  txn_count: number;
  normalized_transactions: Record<string, unknown>[];
  categories: Record<string, unknown>[];
  reconciliation: { source: number; report: number; difference: number };
  detailed_section_mapping: Record<string, unknown> | null;
  kpis: Record<string, { paid: number; received: number; net: number }> | null;
  root_totals: RootTotals;
  owner_totals: OwnerTotals;
  partner_panels: { partner_a: PartnerPanel; partner_b: PartnerPanel };
  category_highlights: CategoryHighlight[];
  subcategory_overviews: SubcategoryOverview[];
  transaction_drilldowns: TransactionDrilldown[];
  partner_labels: Record<string, string>;
}

// types/category_mappings.ts
export type KpiRole = "income" | "savings" | "spend" | "personal_spend" | "investment" | "exclude";
export type DetailedSection = "income_salary" | "income_third_party" | "savings" | "home" | "common" | "personal_partner_a" | "personal_partner_b" | "trips" | "cc_payments" | "excluded";

export interface CategoryMapping {
  category_id: string;
  category_title: string;
  kpi_role: KpiRole | null;
  detailed_section: DetailedSection | null;
}

export interface CategoryMappingList {
  categories: CategoryMapping[];
}

export interface CategoryMappingUpdate {
  kpi_role: KpiRole;
  detailed_section: DetailedSection;
}
```

### Data schemas (file storage)

- `data/private/{month}_monthly_report.json` — report contract + pre-computed views
- `data/private/{month}_monthly_report_status.json` — generate status
- `data/private/{month}_ps_raw.json` — raw transactions (from F1.1 sync)
- `data/private/category_roles.json` — KPI role mapping (editable)
- `data/private/detailed_section_mapping.json` — section mapping (editable)
- `data/private/category_catalog.json` — category hierarchy (from sync)
- `data/private/account_mappings.json` — account bindings (from F1.1)
- `data/private/partner_labels.json` — partner names (from sync)
- `client/src/styles/report-shared.scss` — shared CSS

### Error model (unified)

All non-2xx responses: `{"detail": "message"}` (FastAPI default, matches F1.1).

### Testable acceptance criteria

| # | Test | Expected |
|---|------|----------|
| AC1 | GET /api/reports/months (months synced) | 200, months list sorted descending |
| AC2 | GET /api/reports/months (no sync) | 200, `{"months": []}` |
| AC3 | GET /api/reports/monthly/2026-07 (not generated) | 404, "no report generated yet" |
| AC4 | GET /api/reports/monthly/2026-07 (generated, not stale) | 200, ReportResponse with stale=false |
| AC5 | GET /api/reports/monthly/2026-07 (generated, stale) | 200, ReportResponse with stale=true |
| AC6 | GET /api/reports/monthly/invalid | 400, "invalid month format" |
| AC7 | POST /api/reports/monthly/2026-07/generate | 202, status="generating" |
| AC8 | POST /api/reports/monthly/2026-07/generate (already generating) | 202, current status (no new generation) |
| AC9 | POST /api/reports/monthly/2026-07/generate (no ps_raw) | 404, "no data for this month" |
| AC10 | GET /api/reports/monthly/2026-07/status (never generated) | 404, "no generation has been run yet" |
| AC11 | GET /api/reports/monthly/2026-07/status (generating) | 200, status="generating" |
| AC12 | GET /api/reports/monthly/2026-07/status (success) | 200, status="success" |
| AC13 | GET /api/reports/monthly/2026-07/status (failed) | 200, status="failed", errors populated |
| AC14 | POST /api/reports/monthly/2026-07/pdf (generated) | 200, application/pdf, Content-Disposition: monthly_report_2026-07.pdf |
| AC15 | POST /api/reports/monthly/2026-07/pdf (not generated) | 404, "no report generated yet" |
| AC16 | GET /api/category-mappings (categories synced) | 200, CategoryMappingList with titles + roles |
| AC17 | GET /api/category-mappings (no categories) | 404, "no categories — run sync first" |
| AC18 | PUT /api/category-mappings/{id} {kpi_role: "income", detailed_section: "income_salary"} | 200, updated CategoryMapping |
| AC19 | PUT /api/category-mappings/{id} {kpi_role: "invalid"} | 400, "invalid kpi_role" |
| AC20 | PUT /api/category-mappings/{id} {detailed_section: "invalid"} | 400, "invalid detailed_section" |
| AC21 | PUT /api/category-mappings/nonexistent {...} | 404, "category not found" |
| AC22 | CLI standalone: python -m build --month 2026-07 ... | produces JSON + PDF without React |
| AC23 | React app: /reports renders MonthlyReportsPage with MonthSidebar | page loads, months listed |
| AC24 | React app: click month → report renders all 8 sections | all sections visible via Radix + SVG |
| AC25 | React app: 404 → GenerateButton shows | button visible |
| AC26 | React app: click Generate → 202 → poll status → success → report renders | async flow works |
| AC27 | React app: stale badge shows when stale=true | badge visible |
| AC28 | React app: click Regenerate → 202 → poll → success → re-render | regenerate works |
| AC29 | React app: click Export PDF → downloads monthly_report_{month}.pdf | file downloads |
| AC30 | React app: configured partner names shown | matches seed from `partners.json` |
| AC31 | React app: Settings → Category Mappings editor renders | category list with 2 dropdowns per row |
| AC32 | React app: change KPI role dropdown → Save → "Saved" | per-row save works |
| AC33 | React app: change detailed section dropdown → Save → "Saved" | per-row save works |
| AC34 | React app: regenerate report after mapping change → new roles reflected | KPI + sections update |
| AC35 | Shared SCSS: React + CLI both use it | visual parity between screen + PDF |
| AC36 | Generate status transitions: generating → success | status file transitions correctly |
| AC37 | Generate status transitions: generating → failed (errors) | status file reflects failure |
| AC38 | Navigate away during generate → back → resumes polling | navigate-away safe |

---

### Alignment check (ANSWERED 2026-07-28)

1. **ReportResponse shape** — ✅ Flat top-level fields. OK for now.
2. **Category mappings endpoint** — ✅ Renamed to `/api/category-mappings`. One PUT updates both.
3. **38 ACs** — ✅ Enough.
4. **Pre-computed views** — ✅ Defined exact JSON shapes above.

---

## L5: Implementation Plan

### Ordered task list

| # | Task | Files | Depends on | Est |
|---|------|-------|-----------|-----|
| **Backend (report service + API)** | | | | |
| B1 | Extract shared SCSS from `accounting_html.py` → `client/src/styles/report-shared.scss`. Update `accounting_html.py` to import it. | `client/src/styles/report-shared.scss`, `accounting_html.py` | — | 2h |
| B2 | `report_builder.py` — wraps `build_month_contract()` + ports `_root_totals`, `_owner_totals`, `_partner_panel`, `_category_highlights`, `_subcategory_overviews`, `_transaction_drilldowns` → JSON structures. Writes `{month}_monthly_report.json` + status file. | `services/report_builder.py` | — | 4h |
| B3 | `report_pdf.py` — invokes `build_month_html()` → `render_html()` → WeasyPrint. Reads shared SCSS. Returns PDF bytes. | `services/report_pdf.py` | B1 | 2h |
| B4 | `models/reports.py` — MonthList, GenerateStatus, ReportResponse | `models/reports.py` | — | 1h |
| B5 | `models/category_mappings.py` — CategoryMapping, CategoryMappingList, CategoryMappingUpdate + KPI_ROLES + DETAILED_CATEGORY_SECTIONS | `models/category_mappings.py` | — | 1h |
| B6 | `routers/reports.py` — GET /months, GET /monthly/{month} (stale check), POST /generate (async 202 + concurrent guard), GET /status, POST /pdf | `routers/reports.py` | B2, B3, B4 | 3h |
| B7 | `routers/category_mappings.py` — GET /api/category-mappings (merge 3 files), PUT /api/category-mappings/{id} (write 2 files) | `routers/category_mappings.py` | B5 | 2h |
| B8 | `main.py` — mount report + category-mappings routers | `main.py` (update) | B6, B7 | 0.5h |
| B9 | Backend unit tests — report_builder (derived views, stale check, status transitions) | `tests/test_report_builder.py` | B2 | 3h |
| B10 | Backend unit tests — reports router (months, get, generate async, status, pdf) | `tests/test_reports.py` | B6 | 3h |
| B11 | Backend unit tests — category_mappings (list, update, validation, 404) | `tests/test_category_mappings.py` | B7 | 2h |
| B12 | Integration tests — AC1-AC22 (backend acceptance) | `tests/test_acceptance.py` | B6-B8 | 3h |
| **Frontend (report page + components)** | | | | |
| F1 | API client + types — `api/reports.ts`, `api/category_mappings.ts`, `types/report.ts`, `types/category_mappings.ts` | `client/src/api/`, `client/src/types/` | B8 | 2h |
| F2 | Router + AppLayout — add /reports route, Monthly Reports nav link | `client/src/router.tsx`, `client/src/layouts/AppLayout.tsx` | F1 | 1h |
| F3 | MonthlyReportsPage + MonthSidebar (Radix RadioGroup, month list, selected state) | `client/src/pages/MonthlyReportsPage.tsx`, `client/src/components/reports/MonthSidebar.tsx` | F2 | 2h |
| F4 | ReportView container — fetch report, 404→GenerateButton, stale→StaleBadge+Regenerate, PDF export button, poll status during generate | `client/src/components/reports/ReportView.tsx`, `GenerateButton.tsx`, `StaleBadge.tsx`, `PdfExportButton.tsx` | F3 | 3h |
| F5 | OverviewSection — header + 3 metrics + partner panels | `client/src/components/reports/OverviewSection.tsx` | F4 | 2h |
| F6 | KpiRoleSummary — role-based KPI matrix per partner | `client/src/components/reports/KpiRoleSummary.tsx` | F4 | 2h |
| F7 | CategoryHighlights — top categories with bar tracks | `client/src/components/reports/CategoryHighlights.tsx` | F4 | 1.5h |
| F8 | SubcategoryOverviews — nested category breakdowns | `client/src/components/reports/SubcategoryOverviews.tsx` | F4 | 1.5h |
| F9 | TransactionDrilldowns — per-category transaction tables (expandable) | `client/src/components/reports/TransactionDrilldowns.tsx` | F4 | 2h |
| F10 | DetailedSections — income, savings, legacy (routed by mapping) | `client/src/components/reports/DetailedSections.tsx` | F4 | 3h |
| F11 | ReconciliationSection — source vs report, balanced indicator | `client/src/components/reports/ReconciliationSection.tsx` | F4 | 1h |
| F12 | Charts — DonutChart, HorizontalBarChart, PartnerKpiMatrix (raw SVG in JSX, port from `charts.py`) | `client/src/components/reports/charts/*.tsx` | F4 | 4h |
| F13 | Shared SCSS import — Vite SCSS config, import `report-shared.scss` in ReportView | `client/src/components/reports/ReportView.module.css` → import shared | B1, F4 | 1h |
| F14 | CategoryMappingsEditor — Settings section, category list, 2 dropdowns per row, per-row save | `client/src/components/settings/CategoryMappingsEditor.tsx`, `CategoryRoleRow.tsx`, `SettingsPage.tsx` (update) | F1 | 3h |
| F15 | Frontend unit tests — MonthlyReportsPage (month list, select, 404, generate flow, stale) | `client/tests/MonthlyReportsPage.test.tsx` | F4 | 2h |
| F16 | Frontend unit tests — ReportView (all 8 sections render, charts render) | `client/tests/ReportView.test.tsx` | F5-F12 | 2h |
| F17 | Frontend unit tests — CategoryMappingsEditor (list, dropdowns, save) | `client/tests/CategoryMappingsEditor.test.tsx` | F14 | 1.5h |
| **Regression** | | | | |
| R1 | Run existing pipeline test suites | `pytest src/v4_pipeline/tests/` | B12 | 0.5h |
| R2 | Run existing F1.1 tests (sync, settings, partners, accounts, categories) | `pytest src/budget_api/tests/` | B12 | 0.5h |

**Total estimate: ~58h**

### Incremental delivery slices

**Slice 1 — Backend foundation (B1-B3):** Shared SCSS + report_builder + report_pdf. No routers yet. Verify: `report_builder.build_report("2026-07")` writes JSON + status, `report_pdf.generate_pdf("2026-07")` returns PDF bytes.

**Slice 2 — Backend routers (B4-B8):** All routers mounted. Verify: `uvicorn budget_api.main:app` starts, all endpoints respond. `GET /api/reports/months` returns months. `POST /api/reports/monthly/2026-07/generate` starts async generation. `GET /api/category-mappings` returns merged list.

**Slice 3 — Backend tests (B9-B12):** All 22 backend ACs pass (AC1-AC22). Verify: `pytest src/budget_api/tests/ -v` green.

**Slice 4 — Frontend scaffold (F1-F4):** API client + types + router + page + sidebar + report container. Verify: `pnpm dev` starts, /reports renders, MonthSidebar lists months, clicking month fetches report (or shows GenerateButton on 404).

**Slice 5 — Frontend report sections (F5-F13):** All 8 sections + charts + shared SCSS. Verify: full report renders from JSON, all sections visible, charts render as SVG, visual parity with PDF.

**Slice 6 — Frontend category mappings (F14):** Settings section. Verify: category list renders, dropdowns work, save persists.

**Slice 7 — Frontend tests (F15-F17):** Vitest green. Verify: `pnpm test` passes.

**Slice 8 — Regression (R1-R2):** Existing pipelines + F1.1 tests still pass. Verify: `pytest src/` green.

### Risk controls

| Risk | Mitigation | Rollback |
|------|-----------|----------|
| Shared SCSS Chromium/WeasyPrint incompatibility | Constrain to CSS intersection, test both renderers | Revert to inline CSS in `accounting_html.py` |
| Derived-view port logic divergence | Port one function at a time, compare JSON output vs HTML output | Fall back to raw contract only (FE computes views) |
| Contract JSON size (large months) | Measure file size, consider excluding `normalized_transactions` from GET response (drilldowns have the data) | Split into summary + detail endpoints |
| Generate async race condition | threading.Lock guard (like F1.1 sync), status file before build | Revert to sync generate |
| WeasyPrint PDF fails on shared SCSS | Test PDF generation early (Slice 1), fix CSS before building frontend | Keep inline CSS for PDF, shared SCSS for React only |
| Category mappings write to 2 files atomically | Write both in sequence, rollback on failure | Split into 2 endpoints |
| Existing pipeline regression | Regression gate R1 after backend changes | Revert backend changes |
| Radix RadioGroup sidemenu styling | Prototype early in Slice 4 | Fall back to styled `<ul>` with click handlers |

### Test plan

| Layer | Tool | Coverage |
|-------|------|----------|
| Unit — report_builder | pytest + mock data | Derived views, stale check, status transitions |
| Unit — reports router | pytest + TestClient | Months, get, generate async, status, pdf, concurrent guard |
| Unit — category_mappings | pytest + tmp_path | List merge, update, validation, 404 |
| Integration — backend | pytest + TestClient | AC1-AC22 (all backend acceptance criteria) |
| Unit — frontend components | Vitest + Testing Library | MonthlyReportsPage, ReportView, CategoryMappingsEditor |
| Integration — frontend API | Vitest + msw | API client fetch + error parsing |
| Regression | pytest | Existing v4_pipeline + F1.1 suites still green |

### Dependencies to install

**Backend:** No new dependencies (FastAPI, Pydantic, WeasyPrint already installed).

**Frontend:** No new dependencies (React, Radix, Tailwind, Vitest already installed from F1.1). SCSS support via Vite built-in (`sass` if not already present).

### File manifest (new files)

**Backend:**
```
src/budget_api/
  routers/
    reports.py
    category_mappings.py
  services/
    report_builder.py
    report_pdf.py
  models/
    reports.py
    category_mappings.py
  tests/
    test_report_builder.py
    test_reports.py
    test_category_mappings.py
    test_acceptance.py
```

**Frontend:**
```
client/src/
  pages/
    MonthlyReportsPage.tsx
    MonthlyReportsPage.module.css
  components/
    reports/
      MonthSidebar.tsx
      ReportView.tsx
      ReportView.module.css
      OverviewSection.tsx
      KpiRoleSummary.tsx
      CategoryHighlights.tsx
      SubcategoryOverviews.tsx
      TransactionDrilldowns.tsx
      DetailedSections.tsx
      ReconciliationSection.tsx
      charts/
        DonutChart.tsx
        HorizontalBarChart.tsx
        PartnerKpiMatrix.tsx
      GenerateButton.tsx
      StaleBadge.tsx
      PdfExportButton.tsx
    settings/
      CategoryMappingsEditor.tsx
      CategoryRoleRow.tsx
  api/
    reports.ts
    category_mappings.ts
  types/
    report.ts
    category_mappings.ts
  styles/
    report-shared.scss
  tests/
    MonthlyReportsPage.test.tsx
    ReportView.test.tsx
    CategoryMappingsEditor.test.tsx
```

### Definition of done

- [ ] All 38 ACs pass (AC1-AC38)
- [ ] CLI standalone: `python -m build --month 2026-07 ...` produces JSON + PDF without React
- [ ] `GET /api/reports/months` returns synced months
- [ ] `GET /api/reports/monthly/{month}` returns contract JSON + stale flag (or 404)
- [ ] `POST /api/reports/monthly/{month}/generate` starts async generation (202 + poll)
- [ ] `POST /api/reports/monthly/{month}/pdf` returns PDF binary stream
- [ ] `GET /api/category-mappings` returns merged category list
- [ ] `PUT /api/category-mappings/{id}` updates KPI role + detailed section
- [ ] React app: /reports renders with MonthSidebar (Radix RadioGroup)
- [ ] All 8 presentation elements render from contract JSON via Radix + SVG
- [ ] Partner names from config shown
- [ ] Generate button on 404, Regenerate button on existing, StaleBadge on stale
- [ ] PDF export downloads `monthly_report_{month}.pdf`
- [ ] Category mappings editor in Settings: 2 dropdowns per row, per-row save
- [ ] Shared SCSS: React + CLI both use it, visual parity
- [ ] Vitest frontend tests green
- [ ] `pytest src/` regression green (existing pipeline + F1.1)
- [ ] `.gitignore` excludes `data/private/`, `.env`, `client/node_modules`

---

### Alignment check — final approval:

1. **Task ordering** — backend first (B1-B12), then frontend (F1-F17), then regression (R1-R2). OK?
2. **~58h estimate** — this is a large task. OK to proceed, or do you want to split into sub-tasks (e.g. F1.2a backend, F1.2b frontend)?
3. **Slice delivery** — 8 slices, each verifiable. OK?
4. **Approve implementation now?**