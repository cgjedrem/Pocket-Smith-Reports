# F1.1 — React Page for F1 (PS Sync + Settings)

Status: DESIGN COMPLETE (L1-L5 approved 2026-07-27, ready for implementation)
Date: 2026-07-27
Repo: Pocket-Smith-Reports

## Summary
React UI pages for F1 PS Sync backend + finish F1 backend (routers, ps_client, sync_runner).
Two pages + nav:
1. **Sync page** — trigger manual sync, configure date range, view sync status + row counts
2. **Settings page** — partner CRUD, account binding (partner + type + excluded), PS API key binding, category tree view
3. **Navigation/menu** — app shell with nav between pages (F1.1 bootstraps Vite+React+routing)

## Dependencies
- F1 backend PARTIALLY DONE: models + storage + main.py skeleton exist. MISSING: routers/, ps_client.py, sync_runner.py. F1.1 must finish these.
- F7 app shell NOT BUILT — F1.1 bootstraps it (Vite + React + routing + layout + nav)

## Decisions (from user, 2026-07-27)
- F1.1 bootstraps Vite+React+routing itself (absorbs F7 app shell scope)
- F1.1 finishes F1 backend (routers, ps_client, sync_runner) — not just frontend
- Settings page includes PS API key binding (set/update `.env` API_KEY via UI)
- Navigation + menu come in here (app shell with nav)
- Sync UX: poll `/api/sync/status` (status: "running" → poll until "success"/"failed")
- Date range: two `<input type="month">` pickers (start_month + end_month)
- Also env var set via Settings page (PS API key stored in `.env`)
- Account table: ~10 accounts per page, simple pagination fine (no virtualization)
- Styling: Tailwind v4 + CSS modules, minimal design matching v4 monthly report theme
  - v4 minimal palette: bg `#eef3f4`, surface `#ffffff`, ink `#19303d`, muted `#5d6c75`, rule `#d8e3ec`, accent `#0f6b78`, header border `#d4664d`
  - Font: Aptos / DejaVu Sans sans-serif, Georgia / DejaVu Serif for headings

## L1-L5: COMPLETE

---

## L1: Capabilities

### In-scope

#### Backend (finish F1)
- **ps_client.py** — PS API wrapper (GET only): `get_transactions`, `get_events`, `get_budget`, `get_categories`, `get_accounts`, `get_transaction_accounts`. Reuses `live_sync.py` patterns (redirect rejection, API key from `.env`, pagination via Link header, `per_page=1000`).
- **sync_runner.py** — Orchestrator: `sync_all(start_month, end_month)`, writes `.sync_status.json` with `status: "running"` before sync, `"success"`/`"failed"` after. Merges accounts (new=unbound, gone=excluded). `owner`→`partner_id` migration on first sync.
- **routers/sync.py** — `GET /api/sync?start_month=YYYY-MM&end_month=YYYY-MM`
- **routers/status.py** — `GET /api/sync/status`
- **routers/partners.py** — CRUD `/api/partners` (slugify id, delete guards)
- **routers/accounts.py** — `GET /api/accounts`, `PUT /api/accounts/{id}/binding`
- **routers/settings.py** (NEW) — `GET /api/settings/api-key`, `PUT /api/settings/api-key` — read/write PS API key in `.env`
- **routers/categories.py** (NEW) — `GET /api/categories` (list), `GET /api/categories/{id}` (detail with children + parent path) — read-only, reads `category_catalog.json`
- Mount all routers in `main.py`

#### Frontend (React app shell + pages)
- **App shell** — Vite + React + React Router, layout with top nav menu (Sync / Settings), minimal theme matching v4 monthly report
- **Sync page** — two `<input type="month">` pickers (start + end), Sync button, triggers async sync (202), poll `/api/sync/status` while `status: "running"`, display row counts + last sync timestamp + error list
- **Settings page** — four sections:
  1. **PS API Key** — "✓ Configured" badge if set (masked dots, no raw key), "Change" button reveals password input + "Save". If not set: empty input + "Save".
  2. **Partners** — list + add/edit/delete with guard error display (bound accounts, last partner)
  3. **Accounts** — table with ~10 per page pagination, columns: name, partner (dropdown), type (dropdown: checking/cc/savings/none), excluded (toggle), save per row
  4. **Categories** — tree view (id, title, parent_id) with hierarchy drilldown. GET list + GET /{id} detail (children, parent path). Read-only (synced from PS, overwritten on re-sync)
- **Loading/error/empty states** — 3 sync states (404=never synced, 200+failed=show errors, 200+success=show counts), API errors, no partners, no accounts, no categories, key not set

### Out-of-scope (F1.1)
- Bill CRUD (F2)
- Budget limit editing (F3)
- Dashboard/projection/CC usage (F4-F6)
- v4/mom/mega report pages (F1.2)
- Auth layer (localhost-only, no auth)
- Scheduled/auto sync (manual trigger only)
- Real-time sync progress (poll-based, not WebSocket)

### Success criteria
- `uvicorn budget_api.main:app` starts with all routers mounted
- `GET /api/sync?start_month=2026-07&end_month=2026-07` returns 202 (async), poll `/api/sync/status` until success → writes `/private`
- `GET /api/sync/status` returns last sync metadata with `status` field
- `GET /api/settings/api-key` returns `{configured: true/false}` (never returns raw key)
- `PUT /api/settings/api-key {api_key: "..."}` writes to `.env`, validates via PS `/me`, sync works after
- `GET /api/categories` returns CategoryList (after sync)
- `GET /api/categories/{id}` returns CategoryDetail with children + parent path
- Partner CRUD works (create/update/delete with guards, slugify id)
- Account binding works (partner + type + excluded, merge on re-sync)
- Accounts gone from PS auto-set `excluded: true`
- React app runs on `localhost:5173`, navigates between Sync + Settings
- Sync page polls status while running, shows row counts on completion
- Settings page saves API key, manages partners, binds accounts, shows category tree
- Minimal theme matches v4 monthly report palette

### Assumptions
- PS API key in `.env` (existing pattern from `live_sync.py` — manual parse, no python-dotenv)
- App binds to `127.0.0.1` only — no network exposure, no auth
- CORS already configured in `main.py` for `localhost:5173` + `127.0.0.1:5173` (verified)
- Sync is **async** — `GET /api/sync` returns 202 immediately (sync started), frontend polls `/api/sync/status` every 2s for progress
- `.env` file read/written directly (no dotenv lib) — matches `live_sync.py` pattern
- API key write: read `.env` lines, replace `API_KEY=...` line or append, atomic write

### Risks
- F1 backend not done — F1.1 must build routers + ps_client + sync_runner before frontend can work
- `.env` write from API — security-sensitive, must atomic write, never expose key in GET response
- Sync can take 10+ seconds for large ranges — async + poll avoids HTTP timeout (no blocking request)
- Tailwind v4 + CSS modules coexistence — need `@tailwindcss/vite` plugin + CSS module imports
- v4 monthly report theme is print-oriented (A4, pt units) — React app is screen-oriented (px/rem), palette transfers but not all CSS

---

### Alignment check (ANSWERED 2026-07-27)

1. **API key endpoint** — ✅ `GET` returns `{configured: bool}` only, `PUT` writes `.env`
2. **Poll interval** — ✅ 2 seconds
3. **`.env` write safety** — ✅ atomic write, preserve other vars, create if missing
4. **Account table pagination** — ✅ client-side slice (~10 total)
5. **Router** — ✅ React Router v6 (`createBrowserRouter` + `RouterProvider`)
6. **Language** — ✅ TypeScript

---

## L2: Components

### Existing code to reuse

| File | What it does | Reuse for F1.1 |
|------|-------------|----------------|
| `src/budget_api/main.py` | FastAPI app + CORS (localhost:5173 already allowed) | Mount new routers |
| `src/budget_api/models/sync.py` | RowCounts, SyncResult, SyncStatus | Sync router responses |
| `src/budget_api/models/partners.py` | Partner, PartnerCreate, PartnerUpdate, PartnerList | Partners router |
| `src/budget_api/models/accounts.py` | AccountBindingUpdate, Account, AccountList | Accounts router |
| `src/budget_api/models/errors.py` | ErrorResponse | Unified error model |
| `src/budget_api/services/storage.py` | atomic_write_json, read_json, write_sync_status, read_sync_status, path constants | Storage layer |
| `src/live_sync.py` | PS API patterns: `_read_env_api_key`, `ps_get`, `_NoRedirectHandler`, pagination via Link header, `MAX_PAGINATION_PAGES` | ps_client.py base |
| `src/v4_pipeline/accounting_html.py` | Minimal theme palette (bg `#eef3f4`, ink `#19303d`, accent `#0f6b78`, etc.) | Tailwind theme tokens |
| `data/private/account_mappings.json` | Existing account→owner mappings | Migration source |

### Proposed components

#### Backend (finish F1)

```
src/budget_api/
  main.py                          # UPDATE: mount routers
  routers/                         # NEW
    __init__.py
    sync.py                        # GET /api/sync
    status.py                      # GET /api/sync/status
    partners.py                    # CRUD /api/partners
    accounts.py                    # GET /api/accounts, PUT /api/accounts/{id}/binding
    settings.py                    # NEW: GET/PUT /api/settings/api-key
    categories.py                  # NEW: GET /api/categories, GET /api/categories/{id}
  services/
    ps_client.py                   # NEW: PS API wrapper (extends live_sync patterns)
    sync_runner.py                 # NEW: orchestrator + status transitions + merge + migration
    env_writer.py                  # NEW: atomic .env read/write (API_KEY line)
  models/
    settings.py                    # NEW: ApiKeyStatus, ApiKeyUpdate
    categories.py                  # NEW: Category, CategoryDetail, CategoryList
  tests/
    test_sync.py
    test_ps_client.py
    test_partners.py
    test_accounts.py
    test_settings.py
    test_categories.py
    test_acceptance.py
```

#### Frontend (React app shell + pages)

```
client/                           # NEW — Vite + React + TS
  package.json
  vite.config.ts
  tsconfig.json
  index.html
  src/
    main.tsx                      # Entry: RouterProvider + router
    router.tsx                    # createBrowserRouter with routes
    layouts/
      AppLayout.tsx               # Shell: top nav menu + Outlet
      AppLayout.module.css
    pages/
      SyncPage.tsx                # Sync trigger + status poll + row counts
      SyncPage.module.css
      SettingsPage.tsx            # API key + partners + accounts sections
      SettingsPage.module.css
    components/
      MonthPicker.tsx             # <input type="month"> wrapper
      StatusBadge.tsx             # running/success/failed badge
      RowCountTable.tsx           # row counts display
      PartnerList.tsx             # partner CRUD list
      PartnerForm.tsx             # add/edit partner inline form
      AccountTable.tsx            # account binding table (~10/page)
      AccountRow.tsx              # per-row dropdowns + save
      CategoryTree.tsx            # category tree view (hierarchy)
      CategoryDetail.tsx          # category detail (children + parent path)
      ApiKeySection.tsx           # API key set/update section
      Pagination.tsx              # simple prev/next client-side
      ErrorAlert.tsx              # error display
      EmptyState.tsx              # empty state wrapper
    api/
      client.ts                   # fetch wrapper (base URL, error parsing)
      sync.ts                     # sync + status API functions
      partners.ts                 # partner CRUD functions
      accounts.ts                 # account + binding functions    categories.ts               # category list + detail functions      settings.ts                 # API key functions
    types/
      api.ts                      # TS types matching backend models
    styles/
      theme.css                    # Tailwind import + CSS vars from v4 minimal palette
  tests/
    SyncPage.test.tsx
    SettingsPage.test.tsx
    PartnerList.test.tsx
    AccountTable.test.tsx
```

### Component responsibilities

#### Backend
- **ps_client.py** — PS API GET wrapper. Reuses `live_sync.py` patterns: `_read_env_api_key()`, `ps_get()`, redirect rejection, Link header pagination (`per_page=1000`). Uses **urllib** (not httpx — matches live_sync.py). Returns raw JSON. Methods: `get_me`, `get_transactions`, `get_events`, `get_budget`, `get_categories`, `get_accounts`, `get_transaction_accounts`.
- **sync_runner.py** — Orchestrator. `sync_all(start_month, end_month)` → writes `.sync_status.json` status="running" before, calls ps_client per month, writes raw JSON to `/private`, merges accounts (new=unbound, gone=excluded), runs `owner`→`partner_id` migration on first sync, updates status="success"/"failed" after.
- **env_writer.py** — Atomic `.env` read/write **only** (no validation). `read_api_key_configured() → bool` (checks if API_KEY line exists + non-empty). `write_api_key(key) → None` (atomic write, preserve other lines, create file if missing). Validation done by routers/settings.py via ps_client.get_me().
- **routers/sync.py** — `GET /api/sync?start_month&end_month` → validates → calls sync_runner → returns SyncResult.
- **routers/status.py** — `GET /api/sync/status` → reads `.sync_status.json` → returns SyncStatus or 404.
- **routers/partners.py** — CRUD with slugify id, delete guards (bound accounts, last partner).
- **routers/accounts.py** — `GET /api/accounts` (merge catalog + mappings), `PUT /api/accounts/{id}/binding`.
- **routers/settings.py** — `GET /api/settings/api-key` → `{configured: bool}`. `PUT /api/settings/api-key` → writes `.env` via env_writer.
- **routers/categories.py** — `GET /api/categories` → reads `category_catalog.json` → returns CategoryList. `GET /api/categories/{id}` → returns Category with children + parent path.

#### Frontend
- **AppLayout.tsx** — Top nav bar (Sync / Settings links), minimal theme, `<Outlet />` for page content.
- **SyncPage.tsx** — Two MonthPicker components, Sync button, polls `/api/sync/status` every 2s while running, StatusBadge + RowCountTable + error list.
- **SettingsPage.tsx** — Four sections: ApiKeySection (password input + save), PartnerList (CRUD), AccountTable (binding with pagination), CategoryTree (tree view + detail).
- **api/client.ts** — Fetch wrapper: base URL from `VITE_API_URL` env var (default `http://localhost:8000`), JSON parsing, error extraction (`detail` field), typed responses.
- **types/api.ts** — TS interfaces matching Pydantic models (SyncResult, SyncStatus, Partner, Account, Category, CategoryDetail, etc.).

### What we do NOT create
- No database (files only)
- No auth (localhost-only)
- No background workers (sync runs in FastAPI background task, poll-based status)
- No WebSocket (poll-based)
- No existing pipeline wrappers (F1.2)
- No bill/budget/dashboard UI (F2-F6)

---

### Alignment check (ANSWERED 2026-07-27)

1. **Task ordering** — ✅ backend first, then frontend
2. **env_writer.py** — ✅ new file
3. **API base URL** — ✅ `VITE_API_URL` env var with default `http://localhost:8000`
4. **Tailwind v4** — ✅ `@tailwindcss/vite` + `@import "tailwindcss"` + CSS modules
5. **Frontend tests** — ✅ Vitest + Testing Library
6. **Account save UX** — ✅ per-row save

---

## L3: Interactions

### Sync flow (main path — async)

```
User opens SyncPage
  │
  ▼
GET /api/sync/status                    ← on mount, check if sync already running
  │
  ├─ 404 (never synced) → show empty state "No sync yet"
  ├─ 200 status="running" → start polling (sync in progress)
  ├─ 200 status="failed" → show errors from last sync
  └─ 200 status="success" → show row counts + timestamp
  │
  ▼
User picks start_month + end_month (two <input type="month">)
  │
  ▼
User clicks "Sync" button
  │
  ▼
GET /api/sync?start_month=YYYY-MM&end_month=YYYY-MM
  │
  ├─ 400 → show error (invalid range/format)
  ├─ 500 → show error (API key not configured / storage fail)
  ├─ 502 → show error (PS API failure)
  ├─ 504 → show error (timeout)
  └─ 202 → sync started, begin polling
  │
  ▼
[While sync running] poll GET /api/sync/status every 2s
  │
  ├─ status="running" → show spinner + "Syncing..." badge
  ├─ status="success" → show row counts + timestamp, stop polling
  └─ status="failed" → show errors, stop polling
```

**Note:** `GET /api/sync` is **async** — returns 202 immediately (sync started in background). Frontend polls `/api/sync/status` every 2s for progress. If user navigates away and back, mount-time status check picks up `status: "running"` and resumes polling.

### Settings — API key flow

```
User opens SettingsPage → ApiKeySection
  │
  ▼
GET /api/settings/api-key
  │
  ├─ 200 {configured: true} → show "✓ Configured" badge + "Change" button
  └─ 200 {configured: false} → show "No API key set" + empty input + "Save"
  │
  ▼
[If configured] User clicks "Change" → reveal password input + "Save" button
  │
  ▼
User types new key → clicks "Save"
  │
  ▼
PUT /api/settings/api-key {api_key: "..."}
  │
  ├─ 200 → show "Saved" confirmation, refresh configured status
  ├─ 400 → show error ("api_key is required" / "PS API rejected key" / "PS API unreachable")
  └─ 500 → show error "Failed to write .env"
```

### Settings — Partner CRUD flow

```
GET /api/partners → list partners
  │
  ▼
User clicks "Add Partner" → inline form (label input)
  │
  ▼
POST /api/partners {label: "..."}
  ├─ 201 → refresh list
  └─ 400 → show error (label required)
  │
  ▼
User clicks "Edit" on partner → inline form (label input)
  │
  ▼
PUT /api/partners/{id} {label: "..."}
  ├─ 200 → refresh list
  ├─ 404 → show error (not found)
  └─ 400 → show error (label required)
  │
  ▼
User clicks "Delete" on partner
  │
  ▼
DELETE /api/partners/{id}
  ├─ 204 → refresh list
  ├─ 404 → show error (not found)
  └─ 409 → show error (accounts bound / last partner)
```

### Settings — Account binding flow

```
GET /api/accounts → merged list (PS catalog + local bindings)
  │
  ▼
AccountTable renders (~10 per page, client-side pagination)
  │
  ▼
Per row: partner dropdown (from partners list) + type dropdown (checking/cc/savings/none) + excluded toggle
  │
  ▼
User edits row → clicks "Save" (per-row)
  │
  ▼
PUT /api/accounts/{id}/binding {partner_id, type, excluded}
  ├─ 200 → show "Saved" on row, refresh row + re-fetch partners list
  ├─ 400 → show error (invalid partner_id / type)
  └─ 404 → show error (account not found)
```

### Settings — Category view flow

```
GET /api/categories → list from category_catalog.json
  │
  ├─ 200 (empty) → show "No categories — run sync first"
  └─ 200 (list) → render CategoryTree (hierarchy: root > parent > child)
  │
  ▼
User clicks category → GET /api/categories/{id}
  │
  ├─ 200 → show CategoryDetail (children list + parent path)
  └─ 404 → show error "category not found"
```

Read-only. No create/edit/delete — categories synced from PS, overwritten on re-sync.

### Sync merge rule (accounts, backend)

- For each PS account in fresh `account_catalog.json`:
  - Exists in `account_mappings.json` → preserve `partner_id`, `type`, `excluded`; update `name` from PS
  - New → add entry with `partner_id=null`, `type=null`, `excluded=false`
- For each local account NOT in fresh PS catalog → set `excluded: true` (preserve binding, rename by id)

### Failure + retry behavior

| Failure | Backend behavior | Frontend display |
|---------|-------------------|-------------------|
| PS API 401 (bad key) | 502 "PS API auth failed" | ErrorAlert on SyncPage |
| PS API 403 | 502 "PS API forbidden" | ErrorAlert |
| PS API 429 | 502 "PS API rate limited" | ErrorAlert |
| PS API 500/503 | 502 "PS API unavailable" | ErrorAlert |
| PS API timeout (30s) | 504 "PS API timeout" | ErrorAlert |
| Events empty | sync succeeds, events=0 | row_counts shows 0 |
| `.env` missing API key | 500 "API key not configured" | ErrorAlert + link to Settings |
| Invalid date range | 400 "start_month must be ≤ end_month" | ErrorAlert |
| Atomic write fails | 500 "storage write failed" | ErrorAlert |
| Network error (FE→BE) | N/A | ErrorAlert "Cannot reach server" |
| `.env` write fails (settings) | 500 "Failed to write .env" | ErrorAlert on ApiKeySection |
| Partner delete (bound) | 409 "cannot delete partner" | ErrorAlert on PartnerList |
| Partner delete (last) | 409 "cannot delete last partner" | ErrorAlert |
| Invalid partner_id (binding) | 400 "invalid partner_id" | ErrorAlert on AccountRow |
| Account not found | 404 "account not found" | ErrorAlert on AccountRow |
| Categories never synced | 404 "no categories — run sync first" | EmptyState on CategoryTree |
| Category not found | 404 "category not found" | ErrorAlert on CategoryDetail |

**No retry logic.** User re-triggers manually.

### Observability touchpoints

| Touchpoint | What | Where |
|-----------|------|-------|
| Sync start | timestamp, range | FastAPI access log + `.sync_status.json` |
| Sync result | months_synced, row_counts, errors, duration | SyncResult response + `.sync_status.json` |
| PS API call | endpoint, page, status_code, duration | ps_client stdout log |
| Error log | failure type, message, traceback | FastAPI exception handler (stderr) |
| Storage write | filename, bytes | storage.py stdout log |
| `.env` write | success/fail | env_writer stdout log |
| Frontend fetch | endpoint, status, duration | browser devtools (no custom logging) |

### `.sync_status.json` lifecycle

```
[before sync]  status: "running"     ← written by sync_runner BEFORE first PS call
[during sync]  status: "running"      ← unchanged (poll reads this)
[on success]   status: "success"     ← updated after all writes complete
[on failure]   status: "failed"      ← updated on exception, errors populated
```

---

### Alignment check (ANSWERED 2026-07-27)

1. **Sync call** — ✅ **async** (GET /api/sync returns 202 immediately, poll status for progress, navigate-away safe)
2. **Concurrent sync guard** — ✅ return 202 with current SyncStatus (already running), no new sync started
3. **API key validation** — ✅ validate by doing a test sync (PS API `/me` call). Reject if PS rejects key.
4. **Partner dropdown** — ✅ refresh partners list on account save (re-fetch after binding save)
5. **Excluded toggle** — ✅ stay visible, greyed row, reversible
6. **Partial sync failure** — ✅ partial files remain, status="failed", re-sync overwrites, no cleanup

### Categories sync (from F1 design, not lost)

Categories sync IS part of F1 (inherited by F1.1). The sync flow includes:

```
sync_runner.sync_all()
  ├──► for each month:
  │    ├──► ps_client.get_transactions()  → {YYYY-MM}_ps_raw.json
  │    └──► ps_client.get_events()        → events_{YYYY-MM}.json
  ├──► ps_client.get_budget()            → budget_snapshot.json
  ├──► ps_client.get_categories()        → category_catalog.json (overwrite)
  ├──► ps_client.get_accounts()           → account_catalog.json (overwrite)
  └──► ps_client.get_transaction_accounts() → (merged into account_catalog)
```

RowCounts includes `categories` count:
```python
class RowCounts(BaseModel):
    transactions: int = 0
    events: int = 0
    budget: int = 0
    categories: int = 0   # ← this one
    accounts: int = 0
```

Frontend SyncPage RowCountTable shows all 5 row types including categories. No separate categories UI — just a row count in the sync result.

---

## L4: Contracts

### API endpoints (full)

#### Sync

```
GET /api/sync?start_month=YYYY-MM&end_month=YYYY-MM
```
- Query params: `start_month` (required, `^\d{4}-\d{2}$`), `end_month` (required, same)
- Validation: start_month ≤ end_month
- **Async**: starts sync in background, returns 202 immediately
- Concurrent guard: if `.sync_status.json` status="running" → return 202 with current SyncStatus (no new sync started)
- Response 202: `{"status": "running", ...}` (sync started or already running)
- Response 400: `{"detail": "start_month must be ≤ end_month"}` or `{"detail": "invalid month format"}`
- Response 500: `{"detail": "API key not configured"}` or `{"detail": "storage write failed"}`
- Response 502: `{"detail": "PS API auth failed" | "PS API forbidden" | "PS API rate limited" | "PS API unavailable" | "PS API unreachable"}`
- Response 504: `{"detail": "PS API timeout"}`

```
GET /api/sync/status
```
- No params
- Response 200: SyncStatus
- Response 404: `{"detail": "no sync has been run yet"}`

#### Settings (API key)

```
GET /api/settings/api-key
```
- No params
- Response 200: `{"configured": true}` or `{"configured": false}`
- Never returns raw key value

```
PUT /api/settings/api-key
```
- Body: `{"api_key": string}` (required, non-empty)
- Validation: writes `.env` atomically (overwrite API_KEY line, preserve other lines, create if missing), then test-validates by calling PS API `/me`
  - If PS `/me` returns 200 → key valid, response 200
  - If PS `/me` returns 401/403 → response 400 `{"detail": "PS API rejected key"}` (key already written — user fixes by saving correct key)
  - If PS `/me` unreachable (ConnectionError or timeout) → response 400 `{"detail": "PS API unreachable — cannot validate key"}` (key already written — user retries when PS available)
  - **No rollback.** Clean cut: key written to `.env` immediately. If invalid, user saves correct key. Simpler than rollback.
- Response 200: `{"configured": true}`
- Response 400: `{"detail": "api_key is required"}` or `{"detail": "PS API rejected key"}` or `{"detail": "PS API unreachable — cannot validate key"}`
- Response 500: `{"detail": "Failed to write .env"}`

#### Partners

```
GET /api/partners
```
- Response 200: PartnerList

```
POST /api/partners
```
- Body: PartnerCreate `{"label": string}` (1-100 chars, stripped)
- Response 201: Partner (with auto-generated slug id)
- Response 400: `{"detail": "label is required"}`

```
PUT /api/partners/{partner_id}
```
- Path: partner_id (string)
- Body: PartnerUpdate `{"label": string}` (1-100 chars)
- Response 200: Partner
- Response 404: `{"detail": "partner not found"}`

```
DELETE /api/partners/{partner_id}
```
- Response 204: no body
- Response 404: `{"detail": "partner not found"}`
- Response 409: `{"detail": "cannot delete partner — accounts still bound"}` or `{"detail": "cannot delete last partner"}`

#### Accounts

```
GET /api/accounts
```
- Response 200: AccountList (merged from account_catalog.json + account_mappings.json)

```
PUT /api/accounts/{account_id}/binding
```
- Path: account_id (string, PS account ID)
- Body: AccountBindingUpdate `{"partner_id": str|null, "type": "checking"|"cc"|"savings"|null, "excluded": bool}` — **full replace** (all 3 fields required in body, not partial merge)
- Validation: partner_id must exist in partners.json (if not null)
- Validation: type must be in {checking, cc, savings, null}
- Response 200: Account (updated)
- Response 400: `{"detail": "invalid partner_id"}` or `{"detail": "invalid type"}`
- Response 404: `{"detail": "account not found"}`

#### Categories (read-only)

```
GET /api/categories
```
- No params
- Reads `category_catalog.json` (written by sync_runner)
- Response 200: CategoryList (flat list with parent_id for tree building)
- Response 404: `{"detail": "no categories — run sync first"}` (catalog file missing)

```
GET /api/categories/{category_id}
```
- Path: category_id (string, PS category ID)
- Response 200: CategoryDetail (category + children list + parent path array)
- Response 404: `{"detail": "category not found"}`

### Pydantic models (existing + new)

Existing (from F1):
```python
# models/sync.py — RowCounts, SyncResult, SyncStatus (unchanged)
# models/partners.py — Partner, PartnerCreate, PartnerUpdate, PartnerList (unchanged)
# models/accounts.py — AccountBindingUpdate, Account, AccountList (unchanged)
# models/errors.py — ErrorResponse (unchanged)
```

New:
```python
# models/settings.py
class ApiKeyStatus(BaseModel):
    configured: bool

class ApiKeyUpdate(BaseModel):
    api_key: str = Field(min_length=1)

    @field_validator("api_key")
    @classmethod
    def _validate_key(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("api_key is required")
        return value.strip()

# models/categories.py
class Category(BaseModel):
    id: str                  # PS category ID
    title: str               # from PS
    parent_id: str | None    # None = root

class CategoryDetail(BaseModel):
    id: str
    title: str
    parent_id: str | None
    children: list[Category]       # direct children
    parent_path: list[Category]   # root > ... > parent (excluding self)

class CategoryList(BaseModel):
    categories: list[Category]
```

### TypeScript types (frontend)

```typescript
// types/api.ts
export interface RowCounts {
  transactions: number;
  events: number;
  budget: number;
  categories: number;
  accounts: number;
}

export interface SyncResult {
  timestamp: string;
  start_month: string;
  end_month: string;
  months_synced: number;
  row_counts: RowCounts;
  errors: string[];
  duration_ms: number;
}

export interface SyncStatus {
  status: "running" | "success" | "failed";
  last_sync: string;
  start_month: string;
  end_month: string;
  months_synced: number;
  row_counts: RowCounts;
  errors: string[];
  duration_ms: number;
}

export interface Partner {
  id: string;
  label: string;
}

export interface PartnerCreate {
  label: string;
}

export interface Account {
  id: string;
  name: string;
  partner_id: string | null;
  type: "checking" | "cc" | "savings" | null;
  excluded: boolean;
}

export interface AccountBindingUpdate {
  partner_id: string | null;
  type: "checking" | "cc" | "savings" | null;
  excluded: boolean;
}

export interface ApiKeyStatus {
  configured: boolean;
}

export interface ApiKeyUpdate {
  api_key: string;
}

export interface Category {
  id: string;
  title: string;
  parent_id: string | null;
}

export interface CategoryDetail {
  id: string;
  title: string;
  parent_id: string | null;
  children: Category[];
  parent_path: Category[];
}

export interface CategoryList {
  categories: Category[];
}

export interface ApiError {
  detail: string;
}
```

### Data schemas (file storage — from F1, unchanged)

- `data/private/partners.json` — partner list
- `data/private/account_mappings.json` — account bindings (keyed by PS account ID)
- `data/private/.sync_status.json` — sync status
- `data/private/{YYYY-MM}_ps_raw.json` — raw transactions per month
- `data/private/events_{YYYY-MM}.json` — events per month
- `data/private/budget_snapshot.json` — budget snapshot
- `data/private/category_catalog.json` — categories (overwritten on sync)
- `data/private/account_catalog.json` — accounts (overwritten on sync)
- `.env` — `API_KEY=...` (read/written by env_writer.py)

### Error model (unified)

All non-2xx responses: `{"detail": "message"}` (FastAPI default, matches ErrorResponse).

### Testable acceptance criteria

| # | Test | Expected |
|---|------|----------|
| AC1 | GET /api/sync?start_month=2026-07&end_month=2026-07 | 202, sync started, poll status until success |
| AC2 | GET /api/sync?start_month=2026-07&end_month=2025-01 | 400, "start_month must be ≤ end_month" |
| AC3 | GET /api/sync?start_month=invalid | 400, "invalid month format" |
| AC4 | GET /api/sync/status (never synced) | 404, "no sync has been run yet" |
| AC5 | GET /api/sync/status (after sync) | 200, SyncStatus matches last sync |
| AC6 | GET /api/sync while status="running" | 202, returns current SyncStatus (no new sync started) |
| AC7 | GET /api/settings/api-key (key set) | 200, {"configured": true} |
| AC8 | GET /api/settings/api-key (key not set) | 200, {"configured": false} |
| AC9 | PUT /api/settings/api-key {api_key: "valid"} | 200, {"configured": true} (PS /me validates) |
| AC10 | PUT /api/settings/api-key {api_key: ""} | 400, "api_key is required" |
| AC11 | PUT /api/settings/api-key {api_key: "bad"} | 400, "PS API rejected key" (key written, user saves correct key) |
| AC11b | PUT /api/settings/api-key {api_key: "x"} (PS unreachable: ConnectionError or timeout) | 400, "PS API unreachable — cannot validate key" (key written, user retries) |
| AC12 | GET /api/partners | 200, PartnerList with ≥1 partner |
| AC13 | POST /api/partners {label: "Test"} | 201, Partner with auto-generated id |
| AC14 | POST /api/partners {label: ""} | 400, "label is required" |
| AC15 | PUT /api/partners/partner_a {label: "FA"} | 200, updated Partner |
| AC16 | PUT /api/partners/nonexistent {label: "X"} | 404, "partner not found" |
| AC17 | DELETE /api/partners/partner_a (accounts bound) | 409, "cannot delete partner" |
| AC18 | DELETE /api/partners/partner_b (no accounts bound) | 204 |
| AC19 | DELETE /api/partners/{last remaining id} | 409, "cannot delete last partner" |
| AC20 | GET /api/accounts | 200, AccountList with all PS accounts + bindings |
| AC21 | PUT /api/accounts/{first_id}/binding {partner_id: "partner_a", type: "checking", excluded: false} | 200, updated Account (use dynamic ID from GET /api/accounts) |
| AC22 | PUT /api/accounts/{first_id}/binding {partner_id: "nonexistent", type: "checking"} | 400, "invalid partner_id" |
| AC23 | PUT /api/accounts/{first_id}/binding {partner_id: null, type: "invalid"} | 400, "invalid type" |
| AC24 | PUT /api/accounts/nonexistent/binding {...} | 404, "account not found" |
| AC25 | Sync with no events in date range | 202, poll until success, events row_count = 0 |
| AC26 | Sync with bad API key | 202, poll until failed, errors=["PS API auth failed"] |
| AC27 | Re-sync same month | 202, poll until success, files overwritten (idempotent) |
| AC28 | Sync merges new account (not in mappings) | 202, poll until success, account appears with partner_id=null, type=null, excluded=false |
| AC29 | Sync marks account gone from PS as excluded | 202, poll until success, account in mappings but not in PS catalog → excluded=true |
| AC30 | Sync writes .sync_status.json status="running" before sync, "success" after | poll status field transitions correctly |
| AC31 | Sync failure sets status="failed" with errors populated | poll status reflects failure |
| AC32 | Sync writes category_catalog.json | categories row_count > 0 |
| AC33 | React app loads on localhost:5173 | SyncPage + SettingsPage render with nav |
| AC34 | SyncPage polls status every 2s while running | poll stops on success/failed |
| AC35 | SettingsPage API key save → .env written → sync works after | end-to-end |
| AC36 | SettingsPage partner CRUD → list updates | end-to-end |
| AC37 | SettingsPage account binding save → row updates | end-to-end |
| AC38 | Excluded account shows greyed in table | visual, reversible toggle |
| AC39 | GET /api/categories (after sync) | 200, CategoryList with categories populated |
| AC40 | GET /api/categories (never synced) | 404, "no categories — run sync first" |
| AC41 | GET /api/categories/{id} (valid) | 200, CategoryDetail with children + parent_path |
| AC42 | GET /api/categories/{id} (not found) | 404, "category not found" |
| AC43 | SettingsPage category tree renders hierarchy | root > parent > child visible |
| AC44 | SettingsPage category click → detail view | children + parent path displayed |

### Alignment check (ANSWERED 2026-07-27)

1. **API key validation** — ✅ reject on unreachable (rollback `.env`, return 400)
2. **Concurrent sync guard** — ✅ return 202 with current SyncStatus (already running), no new sync started
3. **AC count** — ✅ 44 ACs is enough
4. **`.env` write** — ✅ overwrite key (clean cut, no rollback). If invalid, user saves correct key.
5. **Frontend tests** — ✅ Vitest unit + integration only, no E2E
6. **Ready for L5** — ✅ proceed

---

## L5: Implementation Plan

### Ordered task list

| # | Task | Files | Depends on | Est |
|---|------|-------|-----------|-----|
| **Backend (finish F1)** | | | | |
| B1 | ps_client.py — PS API wrapper (GET: me, transactions, events, budget, categories, accounts, transaction_accounts) | `services/ps_client.py` | — | 2h |
| B2 | sync_runner.py — orchestrator + status transitions + account merge + owner→partner_id migration | `services/sync_runner.py` | B1 | 2h |
| B3 | env_writer.py — atomic .env read/write (API_KEY line) | `services/env_writer.py` | — | 1h |
| B4 | models/settings.py — ApiKeyStatus, ApiKeyUpdate | `models/settings.py` | — | 0.5h |
| B5 | routers/sync.py — GET /api/sync (async 202, concurrent guard: return 202 if running) | `routers/sync.py`, `routers/__init__.py` | B2 | 1h |
| B6 | routers/status.py — GET /api/sync/status | `routers/status.py` | B2 | 0.5h |
| B7 | routers/partners.py — CRUD with slugify + delete guards | `routers/partners.py` | — | 1h |
| B8 | routers/accounts.py — GET /api/accounts + PUT binding | `routers/accounts.py` | — | 1h |
| B8b | routers/categories.py — GET /api/categories + GET /{id} (read-only, tree build) | `routers/categories.py`, `models/categories.py` | — | 1h |
| B9 | routers/settings.py — GET/PUT api-key (PS /me validation + rollback) | `routers/settings.py` | B1, B3, B4 | 1.5h |
| B10 | main.py — mount all routers | `main.py` (update) | B5-B9 | 0.5h |
| B10b | Seed `partners.json` (Fixture A + Fixture B) + update `.gitignore` (client/node_modules) | `data/private/partners.json`, `.gitignore` | B7 | 0.5h |
| B11 | Backend unit tests — ps_client | `tests/test_ps_client.py` | B1 | 2h |
| B12 | Backend unit tests — sync_runner (status, merge, migration, excluded) | `tests/test_sync.py` | B2 | 2h |
| B13 | Backend unit tests — partners | `tests/test_partners.py` | B7 | 1h |
| B14 | Backend unit tests — accounts | `tests/test_accounts.py` | B8 | 1h |
| B14b | Backend unit tests — categories (list, detail, tree, 404) | `tests/test_categories.py` | B8b | 1h |
| B15 | Backend unit tests — settings (api-key validation, rollback, unreachable) | `tests/test_settings.py` | B9 | 1.5h |
| B16 | Integration tests — AC1-AC32 (backend acceptance) | `tests/test_acceptance.py` | B5-B10 | 2h |
| **Frontend (React app shell + pages)** | | | | |
| F1 | Vite + React + TS scaffold (package.json, vite.config.ts, tsconfig, tailwind, index.html) | `client/package.json`, `client/vite.config.ts`, `client/tsconfig.json`, `client/index.html`, `client/src/main.tsx` | B10 | 1.5h |
| F2 | Tailwind v4 + theme.css (v4 minimal palette CSS vars) + global styles | `client/src/styles/theme.css` | F1 | 0.5h |
| F3 | Router + AppLayout (nav menu: Sync / Settings) | `client/src/router.tsx`, `client/src/layouts/AppLayout.tsx`, `client/src/layouts/AppLayout.module.css` | F1 | 1h |
| F4 | API client + types | `client/src/api/client.ts`, `client/src/api/sync.ts`, `client/src/api/partners.ts`, `client/src/api/accounts.ts`, `client/src/api/categories.ts`, `client/src/api/settings.ts`, `client/src/types/api.ts` | F1 | 1.5h |
| F5 | Shared components (MonthPicker, StatusBadge, RowCountTable, ErrorAlert, EmptyState, Pagination) | `client/src/components/*.tsx` | F2, F4 | 1.5h |
| F6 | SyncPage (month pickers, sync trigger, poll status 2s, row counts, errors) | `client/src/pages/SyncPage.tsx`, `client/src/pages/SyncPage.module.css` | F5 | 2h |
| F7 | SettingsPage — ApiKeySection (password input, save, configured status) | `client/src/components/ApiKeySection.tsx`, `client/src/pages/SettingsPage.tsx` | F5 | 1h |
| F8 | SettingsPage — PartnerList + PartnerForm (CRUD inline) | `client/src/components/PartnerList.tsx`, `client/src/components/PartnerForm.tsx` | F5 | 1.5h |
| F9 | SettingsPage — AccountTable + AccountRow (per-row save, dropdowns, excluded toggle, greyed) | `client/src/components/AccountTable.tsx`, `client/src/components/AccountRow.tsx` | F5 | 2h |
| F9b | SettingsPage — CategoryTree + CategoryDetail (tree view, hierarchy drilldown, read-only) | `client/src/components/CategoryTree.tsx`, `client/src/components/CategoryDetail.tsx` | F5 | 1.5h |
| F10 | Frontend unit tests — SyncPage (poll, status, empty, error) | `client/tests/SyncPage.test.tsx` | F6 | 1.5h |
| F11 | Frontend unit tests — SettingsPage (api key, partners, accounts, categories) | `client/tests/SettingsPage.test.tsx` | F7-F9b | 1.5h |
| F12 | Frontend unit tests — PartnerList + AccountTable | `client/tests/PartnerList.test.tsx`, `client/tests/AccountTable.test.tsx` | F8-F9 | 1h |
| **Regression** | | | | |
| R1 | Run existing v4/mom/mega test suites | `pytest src/` | B16 | 0.5h |

**Total estimate: ~39h**

### Incremental delivery slices

**Slice 1 — Backend foundation (B1-B3):** ps_client + sync_runner + env_writer. No routers yet. Verify: `sync_runner.sync_all()` can be called directly, writes files to `/private`, status transitions work.

**Slice 2 — Backend routers (B4-B10):** All routers mounted. Verify: `uvicorn budget_api.main:app` starts, all endpoints respond. `GET /api/sync` pulls real PS data. `GET /api/settings/api-key` works. `PUT /api/settings/api-key` validates via PS `/me`.

**Slice 3 — Backend tests (B11-B16):** All 37 backend ACs pass (AC1-AC32 + AC11b + AC39-AC42). Verify: `pytest src/budget_api/tests/ -v` green.

**Slice 4 — Frontend scaffold (F1-F4):** Vite app runs on localhost:5173, router works, nav renders, API client connects to backend. Verify: `npm run dev` starts, SyncPage + SettingsPage render (empty), `GET /api/sync/status` fetch works.

**Slice 5 — Frontend pages (F5-F9b):** All pages functional. Verify: SyncPage triggers sync + polls, SettingsPage saves API key + manages partners + binds accounts + shows category tree.

**Slice 6 — Frontend tests (F10-F12):** Vitest green. Verify: `npm test` passes.

**Slice 7 — Regression (R1):** Existing pipelines still pass. Verify: `pytest src/` green.

### Risk controls

| Risk | Mitigation | Rollback |
|------|-----------|----------|
| PS API rate limit during dev | Use cached `/private` data for tests, mock PS API | Revert to cached data |
| `.env` write corrupts file | Atomic write (temp + replace), preserve other lines | Restore `.env` from git |
| API key invalid after write | No rollback — user saves correct key (clean cut) | User re-saves correct key |
| PS API unreachable during key validation | Return 400, key already written — user retries when PS available | User re-saves when PS up |
| CORS port mismatch | Add `localhost:5174` to CORS allow_origins (Vite fallback port) | Update CORS list |
| Tailwind v4 + CSS modules conflict | `@tailwindcss/vite` plugin handles PostCSS, CSS modules separate | Remove Tailwind, use CSS modules only |
| React Router v7 learning curve | Use `createBrowserRouter` + `RouterProvider` (standard v7 pattern) | N/A |
| Existing pipeline regression | Regression gate R1 after backend changes | Revert backend changes |
| Pydantic v1/v2 conflict | Check existing `input_contract.py` pydantic version | Pin compatible version |

### Test plan

| Layer | Tool | Coverage |
|-------|------|----------|
| Unit — ps_client | pytest + httpx mock | All PS endpoints, pagination, error codes, cap-hit warning |
| Unit — sync_runner | pytest + mock ps_client | Orchestration, merge, migration, status transitions, excluded |
| Unit — partners | pytest + tmp_path | CRUD, slugify, delete guards |
| Unit — accounts | pytest + tmp_path | Binding validation, merge, excluded |
| Unit — settings | pytest + mock ps_client | API key read/write, PS /me validation, no rollback (clean cut) |
| Unit — categories | pytest + tmp_path | List, detail, tree build, 404 (never synced, not found) |
| Integration — backend | pytest + TestClient | AC1-AC42 (all backend acceptance criteria) |
| Unit — frontend components | Vitest + Testing Library | SyncPage poll, SettingsPage sections (api key, partners, accounts, categories), PartnerList, AccountTable |
| Integration — frontend API | Vitest + msw | API client fetch + error parsing |
| Regression | pytest | Existing v4/mom/mega suites still green |

### Dependencies to install

**Backend (pyproject.toml additions):**
```
fastapi
uvicorn
pydantic>=2
httpx  # for TestClient
pytest
pytest-asyncio
```

**Frontend (client/package.json):**
```json
{
  "dependencies": {
    "react": "^19",
    "react-dom": "^19",
    "react-router-dom": "^7"
  },
  "devDependencies": {
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "@vitejs/plugin-react": "^4",
    "@tailwindcss/vite": "^4",
    "tailwindcss": "^4",
    "typescript": "^5",
    "vite": "^6",
    "vitest": "^3",
    "@testing-library/react": "^16",
    "@testing-library/jest-dom": "^6",
    "jsdom": "^25"
  }
}
```

### File manifest (new files)

**Backend:**
```
src/budget_api/
  routers/
    __init__.py
    sync.py
    status.py
    partners.py
    accounts.py
    settings.py
    categories.py
  services/
    ps_client.py
    sync_runner.py
    env_writer.py
  models/
    settings.py
    categories.py
  tests/
    __init__.py
    test_ps_client.py
    test_sync.py
    test_partners.py
    test_accounts.py
    test_settings.py
    test_categories.py
    test_acceptance.py
```

**Frontend:**
```
client/
  package.json
  vite.config.ts
  tsconfig.json
  index.html
  src/
    main.tsx
    router.tsx
    layouts/
      AppLayout.tsx
      AppLayout.module.css
    pages/
      SyncPage.tsx
      SyncPage.module.css
      SettingsPage.tsx
      SettingsPage.module.css
    components/
      MonthPicker.tsx
      StatusBadge.tsx
      RowCountTable.tsx
      PartnerList.tsx
      PartnerForm.tsx
      AccountTable.tsx
      AccountRow.tsx
      CategoryTree.tsx
      CategoryDetail.tsx
      ApiKeySection.tsx
      Pagination.tsx
      ErrorAlert.tsx
      EmptyState.tsx
    api/
      client.ts
      sync.ts
      partners.ts
      accounts.ts
      categories.ts
      settings.ts
    types/
      api.ts
    styles/
      theme.css
  tests/
    SyncPage.test.tsx
    SettingsPage.test.tsx
    PartnerList.test.tsx
    AccountTable.test.tsx
```

### Definition of done

- [ ] All 44 ACs pass (AC1-AC44)
- [ ] `uvicorn budget_api.main:app` starts with all routers mounted
- [ ] `GET /api/sync` pulls real PS data → writes to `/private` (incl. categories)
- [ ] `GET /api/sync/status` returns last sync metadata with `status` field
- [ ] `GET /api/settings/api-key` returns `{configured: bool}` only
- [ ] `PUT /api/settings/api-key` validates via PS `/me`, rollback on reject/unreachable
- [ ] Partner CRUD works (slugify id, delete guards)
- [ ] Account binding works (per-row save, merge on re-sync, excluded greyed)
- [ ] Accounts gone from PS auto-set `excluded: true`
- [ ] `owner` → `partner_id` migration runs on first sync
- [ ] React app runs on `localhost:5173` with nav (Sync / Settings)
- [ ] SyncPage polls status every 2s, shows row counts + errors
- [ ] SettingsPage saves API key, manages partners, binds accounts, shows category tree
- [ ] Vitest frontend tests green
- [ ] `pytest src/` regression green (existing v4/mom/mega)
- [ ] `.gitignore` excludes `/private`, `.env`, and `client/node_modules`
- [ ] `data/private/partners.json` seeded with Fixture A + Fixture B (default partners)
- [ ] CORS allows `localhost:5173` + `localhost:5174` (Vite fallback port)
- [ ] Minimal theme matches v4 monthly report palette