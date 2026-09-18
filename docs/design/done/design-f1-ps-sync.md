# F1 — PS Sync

Status: IN PROGRESS (design-first L1-L5)
Date: 2026-07-27
Repo: Pocket-Smith-Reports

## L1: Capabilities

### In-scope
- Pull **transactions** from PS API for all accounts → `/data/private/{YYYY-MM}_ps_raw.json`
- Pull **events** from PS API (Budget 2026 scenario) → `/data/private/events_{YYYY-MM}.json`
- Pull **budget** from PS API (per-category limits) → `/data/private/budget_snapshot.json` (one snapshot per sync, not per month — budget is not monthly)
- Pull **categories** + **accounts** catalog → refresh existing catalog files
- Manual sync trigger (GET request — always available)
- Configurable date range: `start_month` + `end_month` (YYYY-MM format)
- Store all PS responses as-is in `/private` folder (per-endpoint raw JSON, no filtering)
- Sync status (last sync date, row counts per data type)
- **Partner config** — define partners (one at a time) via API + stored locally
- **Account binding APIs** — bind account to partner + bind account to type (checking/cc/savings) + set `excluded` flag
- Account bindings stored locally (extends existing `account_mappings.json`)

### Out-of-scope (F1)
- Bill CRUD (F2)
- Budget limit editing (F3)
- Dashboard/projection (F4-F6)
- React UI (F7) — F1 provides API only
- Existing pipeline endpoints (v4/mom/mega) — future migration task
- Scheduled/auto sync — manual only

### Success criteria
- User triggers sync → all PS data pulled → saved to `/private` → status returned
- Sync works even if scenario missing (events empty, sync still succeeds)
- Idempotent (re-sync = overwrite — partial sync overwrites, no rollback needed)
- Date range flexible (month, year, custom range via start_month/end_month)
- Partners configurable via API (create one at a time)
- Account → partner binding via API
- Account → type binding via API (checking/cc/savings)
- Account → `excluded` flag via API (cannot delete binding, only change id or set excluded)
- New accounts from PS = unbound (user assigns via API)
- Accounts no longer in PS = marked `excluded: true` on next sync (rename by id, preserve binding)

### Assumptions
- PS API key in `.env` (existing pattern)
- App binds to `127.0.0.1` only — no network exposure, no auth layer (localhost + API key = threat model)
- Existing `live_sync.py` patterns reused (redirect rejection, API key, atomic writes)
- Pagination handled (existing `MAX_PAGINATION_PAGES`) — log warning when cap hit (row_counts may be partial)

### Risks
- PS API rate limits — **RESOLVED: PS error docs (https://developers.pocketsmith.com/docs/errors) list 400/401/403/404/405/422/500/503. No 429 documented. Keep defensive 429 handling but unlikely.**
- Large history = slow sync (mitigate: date range param, `per_page=1000`)
- Scenario missing = events empty but sync still succeeds
- PS API contracts — **RESOLVED: see L1.1 PS API Research below**

## L1.1: PS API Research (verified 2026-07-27)

Sources: https://developers.pocketsmith.com/docs/pagination, /docs/budgeting, /docs/errors, /reference

### Endpoints (F1 uses)

| Data | Endpoint | Params | Paginated |
|------|----------|--------|-----------|
| Current user | `GET /me` | — | No |
| Accounts | `GET /users/{id}/accounts` | — | No |
| Transaction accounts | `GET /users/{id}/transaction_accounts` | — | No |
| Transactions (user) | `GET /users/{id}/transactions` | `start_date`, `end_date`, `page`, `per_page` | Yes |
| Transactions (per acct) | `GET /transaction_accounts/{id}/transactions` | `start_date`, `end_date`, `page`, `per_page` | Yes |
| Categories | `GET /users/{id}/categories` | — | No |
| Events (user) | `GET /users/{id}/events` | `start_date` (req), `end_date` (req) | No |
| Budget | `GET /users/{id}/budget` | `roll_up` (bool) | No |

### Key findings (change design)

1. **No `/scenarios` endpoint exists.** Scenarios are embedded in account objects (`scenarios` array per account). F1 does NOT need scenario lookup — use `GET /users/{id}/events` directly (user-scoped, not scenario-scoped).
2. **Events require `start_date` + `end_date`** (both required). No `scenario_id` param on user-level events endpoint. Simplifies F1 — drop scenario logic entirely.
3. **Budget = `GET /users/{id}/budget`** with only `roll_up` bool param. No date params. Confirms snapshot approach. Returns array of budget analysis packages (one per category). Not paginated.
4. **Pagination**: `Per-Page`, `Total`, `Link` headers (RFC 5988). `per_page` 10-1000 (default 30). Use `per_page=1000` to minimize calls. Follow `Link: rel="next"` header (existing `live_sync.py` pattern correct).
5. **Error format**: PS returns `{"error": "message"}` (not `detail`). Our FastAPI returns `{"detail": ...}` — translate at ps_client boundary.
6. **No 429 in PS error docs**. Rate limiting not documented. Keep defensive handling but low priority.
7. **PS error codes**: 400, 401, 403, 404, 405, 422, 500, 503. Map: 401→auth failed, 403→forbidden, 500/503→unavailable.

### Design changes from research

- **DROP**: `get_scenarios()`, scenario_id lookup, `get_events(month, scenario_id)` → use `get_events(start_date, end_date)`
- **KEEP**: `get_budget()` snapshot (no date param, confirmed)
- **ADD**: `per_page=1000` on all paginated calls
- **SIMPLIFY**: events flow — no scenario branch, always pull user events for date range

## L2: Components

### Existing code to reuse
| File | What it does | Reuse for F1 |
|------|-------------|---------------|
| `src/live_sync.py` | PS API client, pagination, redirect rejection, atomic writes, API key from `.env` | Core sync engine |
| `src/input_contract.py` | Monthly filename helper | File naming |
| `src/v4_pipeline/accounting.py` | Account mapping loader | Account catalog refresh |
| `data/private/account_mappings.json` | Account → partner mapping (currently `owner` field, not `partner_id`) | Reference (extend with `type` + `partner_id`, migrate `owner`→`partner_id`) |

### Proposed components
```
src/budget_api/                    (NEW — FastAPI app)
  __init__.py
  main.py                          FastAPI app, CORS, router mount
  routers/
    sync.py                         GET /api/sync endpoint
    status.py                       GET /api/sync/status endpoint
    partners.py                     CRUD /api/partners (define names, count)
    accounts.py                     CRUD /api/accounts/{id}/binding (partner + type)
  services/
    ps_client.py                    PS API wrapper (extends live_sync patterns)
      - get_transactions(start_date, end_date)   # per_page=1000, follow Link header
      - get_events(start_date, end_date)          # user-scoped, no scenario_id
      - get_budget()                              # snapshot, roll_up=false
      - get_categories()
      - get_accounts()
      - get_transaction_accounts()
      # NOTE: no get_scenarios() — PS has no /scenarios endpoint (see L1.1)
    sync_runner.py                  Orchestrates sync: calls ps_client → writes /private
      - sync_all(start_month, end_month)
      - sync_transactions(month)
      - sync_events(month)
      - sync_budget()               (snapshot, stamped with last sync timestamp)
      - sync_catalogs()
    storage.py                      Atomic write helpers (reuse live_sync._atomic_write)
  models/
    sync.py                         Pydantic models (SyncRequest, SyncStatus, SyncResult)
    partners.py                     Pydantic models (PartnerConfig, Partner)
    accounts.py                     Pydantic models (AccountBinding, AccountType)
  tests/
    test_sync.py
    test_ps_client.py
    test_storage.py
    test_partners.py
    test_accounts.py
```

### Partner config
- `data/private/partners.json` — defines partners (one at a time)
- API: `GET /api/partners`, `POST /api/partners`, `PUT /api/partners/{id}`, `DELETE /api/partners/{id}`
- Default seed: Fixture A (partner_a), Fixture B (partner_b)
- `id` generated by slugifying `label` (e.g. "Partner A" → `partner_a`)

### Account binding APIs
- `GET /api/accounts` — list all accounts (from PS sync) with current bindings
- `PUT /api/accounts/{id}/binding` — set partner + type + excluded for account
- Binding fields: `partner_id` (ref partners.json), `type` (checking|cc|savings|null), `excluded` (bool)
- Cannot delete a binding — only change `partner_id`/`type` or set `excluded: true`
- Stored in `account_mappings.json` (extend existing with `type` + `partner_id` fields)
- Sync pulls accounts from PS, merges with existing local bindings
- New accounts from PS = unbound (partner=null, type=null, excluded=false)
- Existing bindings preserved on re-sync
- Accounts no longer in PS = `excluded: true` set automatically on next sync (binding preserved, renamed by id)

### Component responsibilities
- `ps_client.py` — PS API wrapper (GET only for F1). Reuses live_sync patterns. Returns raw JSON.
- `sync_runner.py` — Orchestrator. Calls ps_client → writes /private. Handles missing scenario.
- `storage.py` — Atomic write helpers. Reuses live_sync._atomic_write.
- `routers/sync.py` — GET /api/sync endpoint.
- `routers/status.py` — GET /api/sync/status endpoint.

### What we do NOT create
- No database (files only — single-user app, `.json` storage)
- No auth (localhost-only app, `.env` API key to PS = threat model)
- No background workers (sync is synchronous)
- No existing pipeline wrappers (future task)
- No scenarios endpoint in F1 (deferred — see L3 open question)

## L3: Interactions

### Sync flow (main path)
```
React (F7) / curl
  │
  ▼
GET /api/sync?start_month=YYYY-MM&end_month=YYYY-MM
  │
  ▼
routers/sync.py
  │  validates start_month ≤ end_month (YYYY-MM regex)
  ▼
storage.write_sync_status({status: "running", ...})   ← write BEFORE sync
  ▼
sync_runner.sync_all(start_month, end_month)
  │
  ├──► for each month in range:
  │    ├──► ps_client.get_transactions(month_start, month_end)
  │    │    └─ paginate via Link header, per_page=1000 (MAX_PAGINATION_PAGES cap)
  │    │       └─ log warning if cap hit (row_counts may be partial)
  │    └──► ps_client.get_events(month_start, month_end)
  │         └─ user-scoped events, no scenario_id needed
  │
  ├──► ps_client.get_budget()        ← snapshot, roll_up=false, no date param
  ├──► ps_client.get_categories()
  ├──► ps_client.get_accounts()
  ├──► ps_client.get_transaction_accounts()
  │
  ▼
storage.py (atomic write per file)
  ├── {YYYY-MM}_ps_raw.json
  ├── events_{YYYY-MM}.json
  ├── budget_snapshot.json          ← single snapshot, stamped with sync timestamp
  ├── category_catalog.json (overwrite)
  ├── account_catalog.json (overwrite)
  └── .sync_status.json (metadata — update to status: "success" or "failed")
  │
  ▼
return SyncResult { months_synced, row_counts, errors, timestamp }
```

**On failure:** `.sync_status.json` updated to `status: "failed"` with errors populated. Partial files already written remain (overwrite semantics — next sync fixes).

### Partner config flow
```
GET /api/partners → read partners.json → return list
POST /api/partners {label} → slugify label → append partner → atomic write partners.json
PUT /api/partners/{id} {label} → update → atomic write
DELETE /api/partners/{id} → remove → atomic write
  └─ reject if accounts still bound to this partner (409 Conflict)
  └─ reject if last partner (409 Conflict)
```

### Account binding flow
```
GET /api/accounts → merge account_catalog.json + account_mappings.json → return list with bindings
PUT /api/accounts/{id}/binding {partner_id, type, excluded}
  ├─ validate partner_id exists in partners.json (400 if not)
  ├─ validate type in {checking, cc, savings, null} (400 if not)
  ├─ merge into account_mappings.json (preserve existing fields)
  └─ atomic write account_mappings.json
  NOTE: cannot delete binding — only change id/type or set excluded=true
```

### Sync merge rule (accounts)
- For each PS account in fresh `account_catalog.json`:
  - If exists in `account_mappings.json` → preserve `partner_id`, `type`, `excluded`; update `name` from PS
  - If new → add entry with `partner_id=null`, `type=null`, `excluded=false`
- For each local account NOT in fresh PS catalog → set `excluded: true` (preserve binding, rename by id)

### Failure + retry behavior

| Failure | Behavior |
|---------|----------|
| PS API 401 (bad key) | 502 Bad Gateway, "PS API auth failed" |
| PS API 403 (forbidden) | 502 Bad Gateway, "PS API forbidden" |
| PS API 429 (rate limit) | 502 Bad Gateway, "PS API rate limited" (undocumented but defensive — forward `Retry-After` if present) |
| PS API 500/503 | 502 Bad Gateway, "PS API unavailable" |
| PS API 422 | 502 Bad Gateway, "PS API validation error: {message}" |
| PS API redirect | reject (reuse _NoRedirectHandler), 502 |
| PS API timeout (30s) | 504 Gateway Timeout |
| Events empty (no budget events in range) | sync succeeds, events row_count = 0 |
| .env missing API key | 500 Internal Error, "API key not configured" |
| Invalid date range | 400 Bad Request, "start_month must be ≤ end_month" |
| Atomic write fails | 500 Internal Error, "storage write failed" |
| Network error | 502 Bad Gateway, "PS API unreachable" |

**No retry logic in F1.** User re-triggers sync manually. Keeps MVP simple.

### Observability touchpoints

| Touchpoint | What | Where |
|-----------|------|-------|
| Sync start log | timestamp, range, user agent | FastAPI access log |
| Sync result | months_synced, row_counts, errors, duration | SyncResult response + .sync_status.json |
| PS API call log | endpoint, page, status_code, duration | ps_client internal log (stdout) |
| Error log | failure type, message, traceback | FastAPI exception handler (stderr) |
| Storage write log | filename, bytes, duration | storage.py internal log (stdout) |

### `.sync_status.json` schema
```json
{
  "status": "running",
  "last_sync": "2026-07-27T14:30:00Z",
  "start_month": "2025-08",
  "end_month": "2026-07",
  "months_synced": 12,
  "row_counts": {
    "transactions": 1234,
    "events": 45,
    "budget": 30,
    "categories": 40,
    "accounts": 14
  },
  "errors": [],
  "duration_ms": 8500
}
```
- `status`: `"running"` (written before sync starts) → `"success"` or `"failed"` (updated after)
- Written BEFORE sync begins; updated on completion or failure

## L4: Contracts

### API endpoints

#### Sync

```
GET /api/sync?start_month=YYYY-MM&end_month=YYYY-MM
```
- Query params: `start_month` (required, YYYY-MM regex `^\d{4}-\d{2}$`), `end_month` (required, same)
- Validation: start_month ≤ end_month
- Response 200: SyncResult
- Response 400: {"detail": "start_month must be ≤ end_month"} or {"detail": "invalid month format"}
- Response 500: {"detail": "API key not configured"} or {"detail": "storage write failed"}
- Response 502: {"detail": "PS API auth failed" | "PS API forbidden" | "PS API rate limited" | "PS API unavailable" | "PS API unreachable"}
- Response 504: {"detail": "PS API timeout"}

```
GET /api/sync/status
```
- No params
- Response 200: SyncStatus (or 404 if never synced: {"detail": "no sync has been run yet"})

#### Partners

```
GET /api/partners
```
- Response 200: PartnerList

```
POST /api/partners
```
- Body: PartnerCreate {"label": str (required, 1-100 chars)}
- Response 201: Partner (with auto-generated id)
- Response 400: {"detail": "label is required"}

```
PUT /api/partners/{partner_id}
```
- Path: partner_id (string)
- Body: PartnerUpdate {"label": str (required, 1-100 chars)}
- Response 200: Partner
- Response 404: {"detail": "partner not found"}

```
DELETE /api/partners/{partner_id}
```
- Response 204: no body
- Response 404: {"detail": "partner not found"}
- Response 409: {"detail": "cannot delete partner — accounts still bound"}

#### Accounts

```
GET /api/accounts
```
- Response 200: AccountList (merged from account_catalog.json + account_mappings.json)

```
PUT /api/accounts/{account_id}/binding
```
- Path: account_id (string, PS account ID)
- Body: AccountBindingUpdate {"partner_id": str|null, "type": "checking"|"cc"|"savings"|null}
- Validation: partner_id must exist in partners.json (if not null)
- Validation: type must be in {checking, cc, savings, null}
- Response 200: Account (updated)
- Response 400: {"detail": "invalid partner_id" | "invalid type"}
- Response 404: {"detail": "account not found"}

### Pydantic models

```python
# models/sync.py
class RowCounts(BaseModel):
    transactions: int = 0
    events: int = 0
    budget: int = 0
    categories: int = 0
    accounts: int = 0

class SyncResult(BaseModel):
    timestamp: str          # ISO 8601
    start_month: str        # YYYY-MM
    end_month: str          # YYYY-MM
    months_synced: int
    row_counts: RowCounts
    errors: list[str]       # empty if success
    duration_ms: int

class SyncStatus(BaseModel):
    status: Literal["running", "success", "failed"]
    last_sync: str          # ISO 8601
    start_month: str
    end_month: str
    months_synced: int
    row_counts: RowCounts
    errors: list[str]
    duration_ms: int

# models/partners.py
class Partner(BaseModel):
    id: str                 # slugified from label, e.g. "partner_a"
    label: str               # e.g. "Fixture A"

class PartnerCreate(BaseModel):
    label: str               # 1-100 chars

class PartnerUpdate(BaseModel):
    label: str               # 1-100 chars

class PartnerList(BaseModel):
    partners: list[Partner]

# models/accounts.py
class AccountBindingUpdate(BaseModel):
    partner_id: str | None = None
    type: Literal["checking", "cc", "savings"] | None = None
    excluded: bool = False

class Account(BaseModel):
    id: str                  # PS account ID
    name: str                # from PS
    partner_id: str | None    # from account_mappings.json
    type: str | None          # checking/cc/savings/null
    excluded: bool            # from account_mappings.json (auto-set true if account gone from PS)

class AccountList(BaseModel):
    accounts: list[Account]
```

### Data schemas (file storage)

#### `data/private/partners.json`
```json
{
  "partners": [
    {"id": "partner_a", "label": "Fixture A"},
    {"id": "partner_b", "label": "Fixture B"}
  ]
}
```
- Invariant: ids unique (slugified from label)
- Invariant: at least 1 partner (reject delete last)

#### `data/private/account_mappings.json`
```json
{
  "1100001": {
    "name": "A-Check Nordic Bank",
    "partner_id": "partner_a",
    "type": "checking",
    "excluded": false
  }
}
```
- Invariant: keys = PS account IDs (strings)
- Invariant: partner_id must exist in partners.json (or null)
- Invariant: type in {checking, cc, savings, null}
- Sync merge rule: preserve existing partner_id + type + excluded; update name from PS; auto-set `excluded: true` if account gone from PS

#### `data/private/.sync_status.json`
```json
{
  "status": "success",
  "last_sync": "2026-07-27T14:30:00Z",
  "start_month": "2025-08",
  "end_month": "2026-07",
  "months_synced": 12,
  "row_counts": {"transactions": 1234, "events": 45, "budget": 30, "categories": 40, "accounts": 14},
  "errors": [],
  "duration_ms": 8500
}
```

### Error model (unified)
```python
class ErrorResponse(BaseModel):
    detail: str
```
All non-2xx responses return `{"detail": "message"}`.

### Backward compatibility
- Existing `account_mappings.json` has `owner` field (not `partner_id`). Migration: on first sync, rename `owner` → `partner_id` if `owner` exists. Preserve `excluded`.
  - **RESOLVED: existing `owner` values are already `partner_a`/`partner_b` (not freeform strings). Migration = rename field `owner` → `partner_id`, keep value as-is.**
  - **BUT: F1 partner ids use the internal keys (`partner_a`, `partner_b`), consistent with historical config. No ID change needed.**
  - Migration runs once on first sync after `partners.json` seeded. If `partners.json` has different ids than mapping expects, log warning + skip migration (manual fix).
- Existing `account_owners.json` (separate file) — not touched by F1. Future cleanup.
- Existing `category_catalog.json` format unchanged (overwrite with fresh PS data).
- Existing `v4_pipeline/accounting.py` `PARTNERS = ("partner_a", "partner_b")` hardcoded — **BREAKING**: F1 changes partner ids to slugified labels. **DECISION: Option A — slugify ids.** `accounting.py` must be updated to read partners from `partners.json` dynamically (task T9b).

### Testable acceptance criteria

| # | Test | Expected |
|---|------|----------|
| AC1 | GET /api/sync?start_month=2026-07&end_month=2026-07 | 200, SyncResult with row_counts populated |
| AC2 | GET /api/sync?start_month=2026-07&end_month=2025-01 | 400, "start_month must be ≤ end_month" |
| AC3 | GET /api/sync?start_month=invalid | 400, "invalid month format" |
| AC4 | GET /api/sync/status (never synced) | 404, "no sync has been run yet" |
| AC5 | GET /api/sync/status (after sync) | 200, SyncStatus matches last sync |
| AC6 | GET /api/partners | 200, PartnerList with ≥1 partner |
| AC7 | POST /api/partners {label: "Test"} | 201, Partner with auto-generated id |
| AC8 | POST /api/partners {label: ""} | 400, "label is required" |
| AC9 | PUT /api/partners/partner_a {label: "Bob"} | 200, updated Partner |
| AC10 | PUT /api/partners/nonexistent {label: "X"} | 404, "partner not found" |
| AC11 | DELETE /api/partners/partner_a (accounts bound) | 409, "cannot delete partner" |
| AC12 | DELETE /api/partners/partner_b (no accounts bound) | 204 |
| AC13 | DELETE /api/partners/{last remaining id} | 409, "cannot delete last partner" |
| AC14 | GET /api/accounts | 200, AccountList with all PS accounts + bindings |
| AC15 | PUT /api/accounts/1100001/binding {partner_id: "partner_a", type: "checking", excluded: false} | 200, updated Account |
| AC16 | PUT /api/accounts/1100001/binding {partner_id: "nonexistent", type: "checking"} | 400, "invalid partner_id" |
| AC17 | PUT /api/accounts/1100001/binding {partner_id: null, type: "invalid"} | 400, "invalid type" |
| AC18 | PUT /api/accounts/nonexistent/binding {...} | 404, "account not found" |
| AC19 | Sync with no events in date range | 200, events row_count = 0 |
| AC20 | Sync with bad API key | 502, "PS API auth failed" |
| AC21 | Re-sync same month | 200, files overwritten (idempotent) |
| AC22 | Sync merges new account (not in mappings) | account appears with partner_id=null, type=null, excluded=false |
| AC23 | Sync marks account gone from PS as excluded | account in mappings but not in PS catalog → excluded=true |
| AC24 | Sync writes .sync_status.json status="running" before sync, "success" after | status field transitions correctly |
| AC25 | Sync failure sets status="failed" with errors populated | .sync_status.json reflects failure |

## L5: Implementation Plan

### Ordered task list

| # | Task | Files | Depends on | Est |
|---|------|-------|-----------|-----|
| T0 | ~~Research PS API contracts~~ **DONE** (see L1.1 in design doc) | — | — | 0h |
| T1 | FastAPI app skeleton + `.gitignore` + `.env.example` | `src/budget_api/__init__.py`, `main.py`, `pyproject.toml`, `.gitignore`, `.env.example` | — | 1h |
| T2 | Pydantic models (RowCounts, SyncResult, SyncStatus, Partner, Account) | `models/sync.py`, `models/partners.py`, `models/accounts.py` | T1 | 1h |
| T3 | Storage service (atomic write + sync status writer) | `services/storage.py` | T1 | 1h |
| T4 | PS client (GET wrapper) | `services/ps_client.py` | T0, T1 | 2h |
| T5 | Sync runner (orchestrator + status:running/failed) | `services/sync_runner.py` | T3, T4 | 2h |
| T6 | Sync router | `routers/sync.py`, `routers/status.py` | T2, T5 | 1h |
| T7 | Partners router + service (slugify id) | `routers/partners.py` | T2, T3 | 1h |
| T8 | Accounts router + binding (excluded field) | `routers/accounts.py` | T2, T3 | 1h |
| T9 | `owner` → `partner_id` migration (already uses `partner_a`/`partner_b` in existing config) | `services/sync_runner.py` | T5 | 0.5h |
| T9b | Update `v4_pipeline/accounting.py` to read partners from `partners.json` dynamically (drop hardcoded `PARTNERS`) | `src/v4_pipeline/accounting.py` | T9 | 1h |
| T10 | Seed `partners.json` default | `data/private/partners.json` | T7 | 0.5h |
| T11 | Unit tests — ps_client | `tests/test_ps_client.py` | T4 | 2h |
| T12 | Unit tests — sync_runner (status transitions, merge, excluded) | `tests/test_sync.py` | T5 | 2h |
| T13 | Unit tests — partners | `tests/test_partners.py` | T7 | 1h |
| T14 | Unit tests — accounts | `tests/test_accounts.py` | T8 | 1h |
| T15 | Integration tests (AC1-AC25) | `tests/test_acceptance.py` | T6-T8 | 2h |
| T16 | Regression gate — run existing v4/mom/mega test suites | `pytest src/` | T5 | 0.5h |

**Total estimate: ~20h** (T0 research done, T9b accounting.py refactor added)

### Incremental delivery slices

**Slice 0 — Research (T0):** ~~PS API contracts documented~~ **DONE** — see L1.1 in design doc.

**Slice 1 — Foundation (T1-T3):** FastAPI app runs, models defined, storage works, `.gitignore` + `.env.example` in place. No PS calls yet. Verify: `uvicorn budget_api.main:app` starts, `/health` returns 200, `/private` gitignored.

**Slice 2 — PS Sync (T4-T6):** Full sync works end-to-end with status transitions. Verify: `GET /api/sync?start_month=2026-07&end_month=2026-07` pulls real PS data → writes files → returns SyncResult. `GET /api/sync/status` returns metadata with `status` field.

**Slice 3 — Partners + Accounts (T7-T10):** Partner CRUD (slugify id) + account binding (excluded field). Verify: create partner, bind account, re-sync preserves binding, gone account → excluded.

**Slice 4 — Tests (T11-T15):** All 25 ACs pass. Verify: `pytest src/budget_api/tests/ -v` green.

**Slice 5 — Regression (T16):** Existing v4/mom/mega pipelines still pass. Verify: `pytest src/` green.

### Risk controls

| Risk | Mitigation | Rollback |
|------|-----------|----------|
| PS API rate limit during dev | Use cached `/private` data for tests, mock PS API | Revert to cached data |
| `owner` → `partner_id` migration breaks existing reports | Migration only renames field in `account_mappings.json`; existing `account_owners.json` untouched | Restore `account_mappings.json` from git |
| FastAPI port conflict | Configurable port (default 8000) | Change port |
| Atomic write race condition | Single-user app, localhost-only, no concurrency expected | N/A |
| PS API schema change | `ps_client.py` returns raw JSON, no schema assumptions | Update ps_client only |
| `owner` → `partner_id` freeform string mismatch | **RESOLVED: existing values are `partner_a`/`partner_b`, not freeform. Migration maps to slugified ids.** | Manual edit |
| `accounting.py` PARTNERS hardcoded breakage | **RESOLVED: Option A — slugify ids. Update `accounting.py` to read partners from `partners.json` dynamically (T9b). Regression gate T16 covers this.** | Revert partner ids |
| Pydantic v1/v2 conflict | Check existing `input_contract.py` pydantic version before adding `pydantic>=2` | Pin compatible version |

### Test plan

| Layer | Tool | Coverage |
|-------|------|----------|
| Unit — ps_client | pytest + httpx mock | All PS endpoints, pagination, error codes, cap-hit warning |
| Unit — sync_runner | pytest + mock ps_client | Orchestration, missing scenario, merge logic, status transitions, excluded auto-set |
| Unit — partners | pytest + tmp_path | CRUD, slugify id, delete-reject-bound, delete-reject-last |
| Unit — accounts | pytest + tmp_path | Binding validation, merge, new account, excluded field |
| Integration | pytest + TestClient | AC1-AC25 (all acceptance criteria) |
| Regression | pytest | Existing v4/mom/mega suites still green |
| E2E (manual) | curl / browser | Real PS API sync, verify files on disk |

### Dependencies to install

```
# pyproject.toml additions
fastapi
uvicorn  # bare uvicorn, no websockets needed for sync API
pydantic>=2  # CHECK: verify existing input_contract.py pydantic version first
httpx  # for TestClient
pytest
pytest-asyncio
```

### File manifest (new files)

```
src/budget_api/
  __init__.py
  main.py
  routers/
    __init__.py
    sync.py
    status.py
    partners.py
    accounts.py
  services/
    __init__.py
    ps_client.py
    sync_runner.py
    storage.py
  models/
    __init__.py
    sync.py
    partners.py
    accounts.py
  tests/
    __init__.py
    test_ps_client.py
    test_sync.py
    test_partners.py
    test_accounts.py
    test_acceptance.py

data/private/
  partners.json          (seed: partner_a=Fixture A, partner_b=Fixture B)

.env.example            (API_KEY=your-ps-api-key)
```

### Definition of done

- [ ] All 25 ACs pass (`pytest test_acceptance.py -v`)
- [ ] `GET /api/sync` pulls real PS data → writes to `/private`
- [ ] `GET /api/sync/status` returns last sync metadata with `status` field
- [ ] `.sync_status.json` written with `status: "running"` before sync, `"success"`/`"failed"` after
- [ ] Partner CRUD works (create/update/delete with guards, slugify id)
- [ ] Account binding works (partner + type + excluded, merge on re-sync)
- [ ] Accounts gone from PS auto-set `excluded: true`
- [ ] `owner` → `partner_id` migration runs (already uses consistent internal keys)
- [ ] `v4_pipeline/accounting.py` reads partners from `partners.json` dynamically (no hardcoded PARTNERS)
- [ ] `partners.json` seeded with Fixture A + Fixture B
- [ ] `.gitignore` excludes `/private` and `.env`
- [ ] No existing `src/` pipelines broken (regression gate T16 green)
- [ ] `uvicorn budget_api.main:app` starts without errors
- [ ] PS API contracts researched (T0 doc complete)