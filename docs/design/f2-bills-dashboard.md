# F2-BE Sub-feature 2 — Dashboard Read (APPROVED L1-L5)

Status: All 5 levels approved. Implementation in progress.
Date: 2026-08-02
Repo: Pocket-Smith-Reports
Owner: coordinator

## What this sub-feature is

The read endpoint that serves a per-month bills dashboard snapshot to the FE. Reads `data/private/bills_dashboard_YYYY-MM.json` (written by sub-feature 1) and returns it as the `GET /api/bills/dashboard?month=YYYY-MM` response. No PS calls. Pure file read + JSON response.

## Snapshot creation path (provenance)

The snapshot is produced by sub-feature 1 inside the **existing** `GET /api/sync?start_month=&end_month=` endpoint. The flow:

```
FE Sync button
  → GET /api/sync?start_month=YYYY-MM&end_month=YYYY-MM  (existing endpoint, extended by sub-feature 1)
    → sync_runner.sync_all(start, end)
      → for each month: bills_builder.build_bills_snapshot(...)
      → storage.atomic_write_json(bills_dashboard_path(month), snapshot)
```

The 404 message in this endpoint points the user to that sync endpoint to generate the file.

## Related docs
- [f2-bills-sync.md](f2-bills-sync.md) — sub-feature 1, produces the snapshot.
- [f2-bills-events.md](f2-bills-events.md) — sub-feature 3, paginated events list.
- Old docs to clean up in this sub-feature: [f2-bills-api.md](f2-bills-api.md), [f2-bills-snapshot.md](f2-bills-snapshot.md).

---

# L1 — Capabilities (APPROVED)

## In-scope

1. **`GET /api/bills/dashboard?month=YYYY-MM`** — returns full snapshot for the requested month. HTTP 200 on success.

2. **Read from `data/private/bills_dashboard_YYYY-MM.json`** on disk via `storage.bills_dashboard_path(month)`. No PS calls. No caching layer. Pure file read → JSON response.

3. **Return the snapshot shape exactly as written by sub-feature 1** — month-level envelope (`month`, `month_label`, `is_past`, `is_current`, `is_future`, `synced_at`, `warnings`), month-level aggregates (`bills_count`, `buys_count`), per-partner derived fields (12 fields: `salary`, `bills`, `everyday_budget`, `savings_transfer`, `savings_delta`, `savings_balance`, `estimated_cc_bill`, `real_cc_bill`, `cc_usage`, `budget_usage`, `net`, `status`), and per-event list (`events[]` with `is_cc_payment`, `is_matched`). Plus `source_counts`.

4. **400** on invalid month format. `month` must match `^\d{4}-\d{2}$`. Response: `{"detail": "invalid month format"}`.

5. **404** when no snapshot exists for the requested month. Response: `{"detail": "No snapshot for {month}. Run GET /api/sync?start_month={month}&end_month={month} to generate one."}`. FE renders as an error page with Sync button.

6. **500** on true internal errors only (OSError reading the file, JSON decode errors, path traversal attempts, unexpected exceptions). Response: `{"detail": "internal error reading snapshot"}`. Detail logged to stderr.

7. **Warnings stay in 200 payload.** `warnings[]` in body is informational; FE renders fidelity banner (e.g. "Prior month auto-fetched").

8. **Support past, current, and future months.** The snapshot already carries `is_past` / `is_current` / `is_future` flags. The read endpoint serves what's on disk.

9. **Respond within 200ms p99** for a typical snapshot file (~50KB). No PS calls, no computation — pure file read + JSON parse + HTTP response.

10. **One router** — `routers/bills.py` — stubbed with this one endpoint. Sub-feature 3 adds `GET /api/bills/events` to the same file.

11. **Doc cleanup in this sub-feature:**
    - `docs/design/f2-bills-api.md` — replace async `POST /api/sync/bills` + `bills_sync_jobs/*.json` model with reality: existing `GET /api/sync` does it. Mark `GET /api/sync/bills/status` as superseded.
    - `docs/design/f2-bills-snapshot.md` — replace async job lifecycle with reality: snapshot written synchronously inside sub-feature 1's per-month loop. No `bills_sync_jobs/` dir. `ps_window_start` / `ps_window_end` removed.

## Out-of-scope

1. No PS calls.
2. No computation / no field derivation.
3. No auto-sync on 404.
4. No pagination (sub-feature 3).
5. No field transformation.
6. No in-memory cache.
7. No range queries.
8. No Pydantic validate on read.
9. No auth (single-user app).
10. No events endpoint (sub-feature 3).
11. No FE changes.

## Success criteria

| Outcome | Measure |
|---|---|
| User opens dashboard for current month after sync | `GET /api/bills/dashboard?month=2026-07` returns 200 + full snapshot in <200ms. |
| User navigates to a past month | 200 + snapshot with `is_past: true`, `real_cc_bill` populated, `estimated_cc_bill: null`. |
| User navigates to a future month | 200 + snapshot with `is_future: true`, `estimated_cc_bill` populated, `real_cc_bill: null`. |
| User navigates to a month with no snapshot | 404 + `{"detail": "No snapshot for 2026-03. Run GET /api/sync?start_month=2026-03&end_month=2026-03 to generate one."}`. |
| User sends `month=foo` | 400 + `{"detail": "invalid month format"}`. |
| Snapshot file is corrupt | 500 + `{"detail": "internal error reading snapshot"}`. Detail logged to stderr. |
| Snapshot has `warnings=["Prior month auto-fetched"]` | 200 + warnings in body. FE shows banner. |
| File system error (disk gone, permissions) | 500 + `{"detail": "internal error reading snapshot"}`. |
| Path traversal attempt (`month=../../../etc/passwd`) | 400 (regex fails) or 500 (file not found inside data dir). |

## L1 assumptions + risks

### Assumptions

- **Snapshot file exists** for the requested month (written by sub-feature 1's sync job).
- **Snapshot file is valid JSON** (sync job validates with Pydantic before atomic write).
- **Single-user app** — no per-user authorization on top of the API.
- **File size is small** (~50KB per month) — disk read is fast.
- **Path traversal blocked by regex** — `^\d{4}-\d{2}$` rejects `..`, `/`, etc. Worst-case file is in `data/private/`, which is private data the user owns anyway.
- **Dev server picks up new code on restart** — confirmed working as of this session.

### Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Snapshot file is missing (user hasn't synced) | Medium | 404 with clear message. FE renders error page with Sync button. |
| Snapshot file is corrupt (rare — atomic write protects) | Low | 500 with "internal error" message. Logged to stderr. |
| Snapshot file is stale (synced days ago) | Medium | `synced_at` field in response — FE can show "last synced X hours ago". No auto-refresh. |
| Multiple FE clients read the same file concurrently | Low | File reads are concurrent-safe on all OSes. No write lock needed for reads. |
| FE requests a month far in the future with no snapshot | Medium | 404. Same as "no snapshot". |
| Disk full / permission denied | Low | 500 with "internal error". Logged to stderr. |

## L1 checkpoint — locked decisions

Original 5 questions in the draft L1, now resolved:

1. ~~Is "no auto-sync on missing snapshot" the right call?~~ **Locked: yes, 404.**
2. ~~Should the read endpoint validate against the Pydantic model?~~ **Locked: no, trust the file.**
3. ~~Should the response include `source_counts`?~~ **Locked: yes, kept in body.**
4. ~~Should there be a `GET /api/bills/dashboard` (no month param) that defaults to the current month?~~ **Locked: no, explicit month only.**
5. ~~Is 200ms realistic?~~ **Locked: yes.**

Plus clarifications from this session:
- 6. **404 for missing snapshot** (overrides draft's 422).
- 7. **500 only for true internal errors; warnings stay in 200 payload.**
- 8. **One router, one endpoint (stub for sub-feature 3).**
- 9. **Doc cleanup in scope (f2-bills-api.md + f2-bills-snapshot.md).**
- 10. **Snapshot creation path = sub-feature 1's extension of `GET /api/sync`.**

---

# L2 — Components (APPROVED — pending Q1 message style)

## Existing components (reuse-first)

| Component | File | Role in this sub-feature |
|---|---|---|
| **Storage** | [services/storage.py](../src/budget_api/services/storage.py) | Reuses `bills_dashboard_path(month) -> Path` (added by sub-feature 1) and `read_json(path) -> Any` (existing). No new helpers needed. |
| **Models (read-side)** | [models/bills.py](../src/budget_api/models/bills.py) | The `BillsSnapshot` Pydantic model exists from sub-feature 1. Sub-feature 2 does **not** import/validate against it on read (L1 out-of-scope #8: trust the file). |
| **FastAPI app** | [main.py](../src/budget_api/main.py) | Mounts the new `bills.router` under `/api`. Existing 422→400 exception handler stays. |
| **Error response shape** | [main.py:18-29](../src/budget_api/main.py#L18-L29) | All error responses use `{"detail": "string"}`. The new endpoint follows this convention. |
| **Existing router pattern** | [routers/sync.py](../src/budget_api/routers/sync.py), [routers/accounts.py](../src/budget_api/routers/accounts.py) | Pattern: `router = APIRouter()` + decorated handler functions. |

## New components

| Component | File (proposed) | Role |
|---|---|---|
| **Bills router** | `routers/bills.py` (new) | One `APIRouter()`. One endpoint: `GET /api/bills/dashboard?month=YYYY-MM`. Stub for sub-feature 3. |
| **Dashboard read handler** | same file (`routers/bills.py`) | `def dashboard(month: str = Query(..., pattern=r"^\d{4}-\d{2}$")) -> dict:` — sync, inline file read, ~25 lines. |
| **Router mount** | `main.py` (edit, one line) | `app.include_router(bills.router, prefix="/api")  # /api/bills/dashboard`. |
| **Tests** | `tests/bills/test_dashboard.py` (new, one file) | All dashboard tests in one file. Uses `tmp_private_dir` + `client` fixtures from existing `conftest.py`. |

## Component boundaries

```
GET /api/bills/dashboard?month=YYYY-MM
  │
  ▼
routers/bills.py: dashboard(month: str = Query(..., pattern=r"^\d{4}-\d{2}$"))
  │
  ├── FastAPI validates pattern → 422 (main.py rewrites to 400 with auto-gen message)
  │   OR handler raises HTTPException(400, "invalid month format") if we override
  │
  ├── path = storage.bills_dashboard_path(month)
  │
  ├── try:
  │     raw = path.read_text(encoding="utf-8")
  │   except FileNotFoundError:
  │     raise HTTPException(404, detail=f"No snapshot for {month}. Run GET /api/sync?start_month={month}&end_month={month} to generate one.")
  │   except OSError:
  │     print(traceback.format_exc(), file=sys.stderr)
  │     raise HTTPException(500, detail="internal error reading snapshot")
  │
  ├── try:
  │     return json.loads(raw)
  │   except json.JSONDecodeError:
  │     print(traceback.format_exc(), file=sys.stderr)
  │     raise HTTPException(500, detail="internal error reading snapshot")
  │
  └── (FastAPI serializes the dict to JSON; 200 OK)
```

**No I/O outside `data/private/`.** Path is built by `storage.bills_dashboard_path(month)` which constructs `PRIVATE_DATA_DIR / f"bills_dashboard_{month}.json"`. `PRIVATE_DATA_DIR = REPOSITORY_ROOT / "data" / "private"`. Even if the regex fails to catch a path-traversal attempt, the path is rooted at `data/private/`, the user's own private data.

## Reuse-first rationale

| New component | Why not reuse existing? |
|---|---|
| `routers/bills.py` | No existing bills router. Stubbing now keeps URL namespace clean for sub-feature 3. |
| `routers/bills_dashboard.py` (rejected) | Per L1 decision #10, one bills router for all bills endpoints. |
| `services/dashboard_reader.py` (rejected) | No business logic. Pure file read. Inline is ~25 lines, more readable than split. |
| `BillsSnapshot` Pydantic on read (rejected) | Per L1 out-of-scope #8. Trust the file. |
| `storage.read_json` (rejected for direct use) | Existing helper returns `None` for missing files. We need 404 on missing, so we want `FileNotFoundError`. Use `path.read_text` + `json.loads` for explicit error control. |
| `asyncio.to_thread` (rejected) | ~50KB file read blocks for microseconds. Sync handler matches existing storage code. |

## L2 checkpoint — locked decisions

1. **Month validation = FastAPI `Query(..., pattern=r"^\d{4}-\d{2}$")`** — declarative, FastAPI handles the check.
2. **Handler = sync `def`** — file read blocks ~microseconds, matches existing storage code.
3. **File read = inline in `routers/bills.py`** — no helper, ~25 lines, more readable.
4. **500 = generic, no leak** — `{"detail": "internal error reading snapshot"}`. Real error logged to stderr.
5. **Tests = one file `tests/bills/test_dashboard.py`** — single endpoint, single test file.

---

# L3 — Interactions (APPROVED)

## Request flow

```
HTTP GET /api/bills/dashboard?month=2026-07
  │
  ├── FastAPI routing → routers/bills.py: dashboard(month)
  │     │
  │     ├── Query param validation: pattern check
  │     │   └── fail → 422 → main.py rewrites to 400
  │     │
  │     ├── path = storage.bills_dashboard_path("2026-07")
  │     │   = data/private/bills_dashboard_2026-07.json
  │     │
  │     ├── raw = path.read_text(encoding="utf-8")
  │     │   ├── FileNotFoundError → 404 with sync hint
  │     │   ├── OSError → stderr log + 500
  │     │   └── other Exception → stderr log + 500
  │     │
  │     ├── snapshot = json.loads(raw)
  │     │   ├── JSONDecodeError → stderr log + 500
  │     │   └── other Exception → stderr log + 500
  │     │
  │     └── return snapshot  (FastAPI → 200 + JSON body)
  │
  └── HTTP response (200/400/404/500)
```

**No external calls.** No PS. No network. No other BE endpoints. Pure file I/O.

## Failure modes (recap from L1 + L2 + L3)

| Failure | HTTP | Body | Logged to stderr? |
|---|---|---|---|
| `month` not `^\d{4}-\d{2}$` | 400 | `{"detail": "invalid month format"}` (Q1=a1: FastAPI auto-gen if accepted) | No |
| Snapshot file doesn't exist | 404 | `{"detail": "No snapshot for {month}. Run GET /api/sync?start_month={month}&end_month={month} to generate one."}` | No |
| `OSError` reading file (permissions, disk) | 500 | `{"detail": "internal error reading snapshot"}` | Yes (full traceback) |
| `JSONDecodeError` (corrupt snapshot, includes empty file) | 500 | `{"detail": "internal error reading snapshot"}` | Yes (full traceback) |
| Unexpected `Exception` | 500 | `{"detail": "internal error reading snapshot"}` | Yes (full traceback) |
| Read during write (mid-sync) | 500 (race) | `{"detail": "internal error reading snapshot"}` | Yes — rare; atomic write minimizes window |
| Logged success | — | — | No (Q3: no log on 200) |
| Logged `warnings[]` non-empty | — | — | No (Q2: no double-log) |
| Correlation ID on response | — | — | No (Q3: not used) |
| `HEAD /api/bills/dashboard` | — | — | Not supported (Q5: out of scope) |

**No retries.** Read endpoint is idempotent. Client decides to retry on 500 (none defined yet). The 404 message tells the user what to do (run sync). The 500 is "ask the dev, check the logs".

## Observability

| Touchpoint | Where | What | Why |
|---|---|---|---|
| **Stderr** | `routers/bills.py: dashboard()` | Full traceback on `OSError` / `JSONDecodeError` / unexpected `Exception` | Dev debugging. No metrics, no structured logging (matches existing codebase). |
| **`.sync_status.json`** | (sub-feature 1) | `bills_warnings: [...]` for fidelity issues | Already exists; this endpoint just surfaces it via the snapshot. |
| **Per-snapshot `warnings[]`** | Inside the served `BillsSnapshot` | Per-month fidelity warnings (missing salary, unmapped bank, prior-month auto-fetched) | FE renders banner. |
| **No new logging framework** | — | — | Matches existing codebase (no structlog, no loguru). |
| **No request log on 200** | — | — | Existing routers do not log on success. Match. |

## Concurrency

- **Reads are concurrent-safe** on all OSes. No write lock needed for reads.
- **Read-during-write race**: `storage.atomic_write_json` uses temp + rename. The rename is atomic on the same filesystem. Window for partial read is microseconds. Probability of catching it is negligible. Mitigation: 500 + log if it happens.
- **Multiple FE clients** read the same file: safe. No coordination needed.

## Security

- **Path traversal blocked by regex** `^\d{4}-\d{2}$`. No `/`, no `..`, no null bytes. Even if regex fails, path is rooted at `data/private/`.
- **No auth** (single-user app). No session, no token. Matches existing routers.
- **CORS** handled by existing middleware in `main.py`. No new headers.
- **No user input** beyond `month` param, which is regex-validated.
- **500 leaks no file path or error detail.** Body is generic.

## L3 checkpoint — locked decisions

1. **No log on 200** — match existing routers.
2. **No log on warnings[]** — FE has them, no double-log.
3. **No correlation ID on 500** — over-engineering for single-user app.
4. **Empty file = 500 generic** — no special message; log shows `JSONDecodeError`.
5. **No `HEAD` support** — out of scope.

---

# L4 — Contracts (APPROVED — L2 Q1 final=override custom msg)

## New endpoint

### `GET /api/bills/dashboard`

| Aspect | Value |
|---|---|
| **Path** | `/api/bills/dashboard` |
| **Method** | `GET` |
| **Query params** | `month: str` — `pattern=r"^\d{4}-\d{2}$"`, required |
| **Auth** | None |
| **Cache-Control** | `no-store` — always fresh (L4 Q4=b) |
| **Accept negotiation** | Always JSON, no 406 (L4 Q3=a) |
| **Mounted at** | `routers/bills.router` in `main.py` with `prefix="/api"` |

## Request

```
GET /api/bills/dashboard?month=YYYY-MM HTTP/1.1
Host: localhost:8000
```

| Param | Type | Required | Validation | On fail |
|---|---|---|---|---|
| `month` | string | yes | `^\d{4}-\d{2}$` | 400 (FastAPI pattern validator → main.py 422→400 rewrite) |

## Response shapes

### 200 OK — happy path

```http
HTTP/1.1 200 OK
Content-Type: application/json
Cache-Control: no-store
```

Body: **exactly the contents of `data/private/bills_dashboard_YYYY-MM.json`**, all fields sub-feature 1 wrote. No transformation. No Pydantic validate.

```json
{
  "schema_version": 1,
  "month": "2026-07",
  "month_label": "July 2026",
  "is_past": false,
  "is_current": true,
  "is_future": false,
  "synced_at": "2026-08-02T12:00:00Z",
  "bills_count": 12,
  "buys_count": 3,
  "warnings": [],
  "partners": [
    {
      "partner": "Fixture A",
      "salary": 42000,
      "bills": 15500,
      "everyday_budget": 8200,
      "savings_transfer": 5000,
      "savings_delta": 2000,
      "savings_balance": 32000,
      "estimated_cc_bill": 9800,
      "real_cc_bill": null,
      "cc_usage": 4200,
      "budget_usage": 4200,
      "net": 16700,
      "status": "covered",
      "events": [
        {
          "id": "evt-123",
          "date": "2026-07-25",
          "day": 25,
          "title": "Salary — Fixture A",
          "type": "bill",
          "category": "Income",
          "partner": "Fixture A",
          "amount": 42000,
          "is_cc_payment": false,
          "is_matched": null
        }
      ]
    }
  ],
  "source_counts": {
    "ps_events_fetched": 142,
    "ps_transactions_fetched": 38,
    "events_kept_after_filter": 22
  }
}
```

**No field transformation. No field stripping. No Pydantic validate.** Whatever sync wrote, read serves.

### 400 Bad Request — invalid month format

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json
```

Body: depends on which 400 case triggered:
- `{"detail": "invalid month format"}` (custom — handler raises `HTTPException` after regex fails).
- `{"detail": "query -> month: Field required"}` (FastAPI auto-gen via main.py's `RequestValidationError` handler — missing or empty `month` query param).

Triggered by:
- `month=foo` → `{"detail": "invalid month format"}` (handler raises 400)
- `month=2026-7` (single-digit month) → `{"detail": "invalid month format"}`
- `month=../../etc/passwd` → `{"detail": "invalid month format"}`
- `month=` (empty) → `{"detail": "query -> month: ..."}` (FastAPI auto-gen → main.py rewrites to 400)
- `month` missing entirely → `{"detail": "query -> month: Field required"}` (FastAPI auto-gen → main.py rewrites to 400)

**Note:** `2026-13` passes the regex (L4 Q1=a); reaches file read; file doesn't exist → 404.

### 404 Not Found — missing snapshot

Body: `{"detail": "No snapshot for 2026-03. Run GET /api/sync?start_month=2026-03&end_month=2026-03 to generate one."}` (L4 Q2=a, exact URL).

Triggered by:
- `month=2026-03` (user never synced March)
- `month=2026-13` (regex matches but file doesn't exist)
- Snapshot file deleted manually
- Sync hasn't completed for that month

### 500 Internal Server Error

```http
HTTP/1.1 500 Internal Server Error
Content-Type: application/json
```

Body:
```json
{"detail": "internal error reading snapshot"}
```

Triggered by:
- `OSError` reading the file (disk error, permission denied)
- `JSONDecodeError` (corrupt file, empty file, partial file from killed write)
- Any unexpected `Exception` (defensive catch)

Full traceback logged to stderr with the request context (month, path).

## Backward compatibility

- **No existing endpoint affected.** New endpoint, new router.
- **No client types affected.** FE will add a new `api.bills.dashboard(month)` call separately.
- **Pydantic model `BillsSnapshot`** is the **writer's** contract (sub-feature 1 validates on write). The **reader's** contract is "trust the file" (L1 out-of-scope #8). This means: if sub-feature 1 ever changes the schema, sub-feature 2's read will reflect that change automatically. The FE's TypeScript types are the binding contract.
- **Breaking change risk**: if sync ever writes a snapshot that violates the FE's TypeScript types, the FE breaks. That's a sync problem, not a read problem.

## Testable acceptance criteria

| AC | Test |
|---|---|
| `GET ?month=2026-07` with valid snapshot | 200 + body matches file content exactly |
| `GET ?month=2026-07` past month | 200 + `is_past: true` |
| `GET ?month=2026-08` future month | 200 + `is_future: true` |
| `GET ?month=2026-07` with `warnings` non-empty in file | 200 + `warnings` array present in body |
| `GET ?month=2026-03` no snapshot | 404 + `{"detail": "..."}` |
| `GET ?month=foo` | 400 + `{"detail": "invalid month format"}` (custom — handler raises `HTTPException`) |
| `GET ?month=` (empty) | 400 + `{"detail": "query -> month: ..."}` (FastAPI auto-gen via main.py exception handler) |
| `GET` (no `month` param) | 400 + `{"detail": "query -> month: Field required"}` (FastAPI auto-gen via main.py exception handler) |
| `GET ?month=../../etc/passwd` | 400 (regex fail) |
| Snapshot file contains invalid JSON | 500 + `{"detail": "internal error reading snapshot"}` + stderr traceback |
| Snapshot file is 0 bytes (empty) | 500 + same as corrupt |
| File does not exist | 404 |
| `os.chmod 000` on file (permission denied, Unix-only) | 500 + `OSError` logged |
| Concurrent reads (10 parallel clients) | All 200, no errors |
| Read during write (hard to test reliably) | Best-effort: 500 if caught; otherwise 200 |
| `Cache-Control: no-store` header present | Verified in test response headers |

## L4 checkpoint — locked decisions

1. **`2026-13` → 404** (L4 Q1=a) — keep validation simple, regex only.
2. **404 message includes exact sync URL** (L4 Q2=a) — copy-paste-able.
3. **No `Accept` content negotiation** (L4 Q3=a) — always JSON.
4. **`Cache-Control: no-store`** (L4 Q4=b) — always fresh, no caching layer.

---

# L5 — Implementation Plan (APPROVED)

## File manifest

| File | Action | Approx lines |
|---|---|---|
| `src/budget_api/routers/bills.py` | **CREATE** | ~45 |
| `src/budget_api/main.py` | **EDIT** (1 line) | +1 |
| `src/budget_api/tests/bills/test_dashboard.py` | **CREATE** | ~150 |
| `docs/design/f2-bills-api.md` | **EDIT** (cleanup) | ~-30 (net reduction) |
| `docs/design/f2-bills-snapshot.md` | **EDIT** (cleanup) | ~-40 (net reduction) |

**Total: 2 creates, 3 edits, ~+126 net lines.**

## Ordered execution plan

### Step 1: Branch (manual)

```bash
git checkout main
git pull
git checkout -b feat/f2-bills-dashboard-subfeature-2
```

### Step 2: Implement router + mount (agent-driven, no commit)

- Create `src/budget_api/routers/bills.py` with `GET /api/bills/dashboard`.
- Edit `src/budget_api/main.py` to import and mount the router.
- One commit: `feat(bills): dashboard read endpoint`.

### Step 3: Implement tests (agent-driven, no commit)

- Create `src/budget_api/tests/bills/test_dashboard.py` covering 17 ACs above.
- Run `pytest src/budget_api/tests/bills/test_dashboard.py -q` until green.
- Verify: full test suite still green (`pytest src/budget_api/tests src/mega/tests src/v4_pipeline/tests src/mom/tests src/budget_api/tests -q`).
- One commit: `test(bills): dashboard read endpoint + 17 acceptance tests`.

### Step 4: Doc cleanup (separate commits, not stacked with code)

- Edit `docs/design/f2-bills-api.md`: replace `POST /api/sync/bills` + `bills_sync_jobs/*.json` with reality.
- Edit `docs/design/f2-bills-snapshot.md`: replace async job lifecycle with reality.
- One commit: `docs(f2-bills): clean up old API + snapshot drafts`.

### Step 5: Manual smoke test

- Restart dev server (pick up new code).
- `GET /api/bills/dashboard?month=2026-05` → expect 200 + valid JSON body.
- `GET /api/bills/dashboard?month=2026-13` → expect 404 with sync URL hint.
- `GET /api/bills/dashboard?month=foo` → expect 400 with invalid month format.
- `GET /api/bills/dashboard` (no month) → expect 400.
- Verify `Cache-Control: no-store` header in 200 response.

### Step 6: Push + open PR

- `git push -u origin feat/f2-bills-dashboard-subfeature-2`
- `gh pr create` with body linking to `f2-bills-dashboard.md` design doc.

## Test plan (testing-strategy)

| Test | Type | Coverage |
|---|---|---|
| Happy path: 200 with full body | Integration (TestClient + tmp_private_dir) | AC1, AC4 |
| Past/future months: 200 with correct flags | Integration | AC2, AC3 |
| Missing snapshot: 404 with sync URL | Integration | AC5 |
| Invalid month: 400 with custom msg | Integration | AC6, AC7, AC8, AC9, AC10 |
| Corrupt JSON: 500 with stderr log | Integration + caplog | AC11 |
| Empty file: 500 with stderr log | Integration + caplog | AC12 |
| Permission denied: 500 (Unix-only, skip on Windows) | Integration + chmod | AC13 |
| Cache-Control header present | Integration | AC17 |
| Concurrent reads: 10 parallel | Integration + ThreadPoolExecutor | AC14 |
| Read-during-write race: best-effort | Integration (flaky, mark xfail) | AC15 |

**Total: ~17 tests, ~150 lines.** Target: all pass on Windows + Ubuntu CI.

## Risk controls

| Risk | Mitigation |
|---|---|
| L1 out-of-scope #8 drift (accidentally add Pydantic validate) | L4 contracts explicitly say "no transformation". Tests assert response body == file content. |
| Forgetting to mount router in `main.py` | Test imports the FastAPI app via `TestClient` and asserts 200 — fails if not mounted. |
| Path-traversal regression | Test: `?month=../../etc/passwd` → 400. |
| Stale dev server (the bug we hit this session) | Step 5 manual smoke test catches it. |
| Sub-feature 1 schema change breaking the read endpoint | Tests assert specific field presence; if sync adds a field, the test still passes (it asserts on the fields L4 specifies). If sync removes a field, the test fails — that's a sync regression. |
| Concurrent file write during test | Tests use `tmp_private_dir` (a tmpfs-equivalent); no shared state. |

## Rollback strategy

- Revert PR. No DB migration, no data migration. Just a router file + 1 line in `main.py` + tests.
- Sub-feature 1's sync continues to write snapshots. Read endpoint simply goes back to 404.
- No FE dependency yet (sub-feature 2 is FE-driven, FE consumes the endpoint only after this lands).

## Incremental delivery slices

| Slice | What ships | Risk |
|---|---|---|
| Slice 1: Router + main.py mount | Endpoint returns 404 (no snapshot) or 500 (no test data). Smoke test only. | Low — surface area is tiny. |
| Slice 2: Add tests | Slice 1 + 17 test cases. CI green. | Low — no new behavior. |
| Slice 3: Doc cleanup | Slice 2 + 2 design doc edits. | Low — docs only. |

Each slice is independently shippable. Could ship slice 1 + 2 as one PR, doc cleanup as a separate PR (or same PR, depending on preference).

## L5 checkpoint — locked decisions

1. **One PR** (L5 Q1=a) — router + tests + docs together.
2. **`test(bills): dashboard read endpoint + 17 acceptance tests`** (L5 Q2=a) — subject ~50 chars, body lists ACs.
3. **Release-please auto** (L5 Q3=a) — verify during Step 1 by checking `.github/workflows/`.
4. **Manual smoke test** (L5 Q4=a) — you click in browser after branch pushed.

---

# Sub-feature 3 - Events List Filter (APPROVED L1-L5)

Status: All 5 levels approved. Implementation in progress.
Date: 2026-08-02
Owner: backend-dev

## What this sub-feature is

The read endpoint that serves a filtered, sorted list of events from a per-month bills dashboard snapshot to the FE. Reads `data/private/bills_dashboard_YYYY-MM.json` (same file sub-feature 2 returns wholesale), flattens `partners[].events[]`, applies optional filters, sorts, and returns `{events: [...], total: N}`. No PS calls. Pure file read + in-memory filter + JSON response.

## Relationship to sub-feature 2

Same file (`routers/bills.py`). Same snapshot. Sub-feature 2 returns the whole snapshot; sub-feature 3 returns a slice. Both endpoints share storage path, error handling pattern, and Cache-Control middleware.

```
GET /api/bills/dashboard?month=YYYY-MM           (sub-feature 2 - full snapshot)
GET /api/bills/dashboard/events?month=YYYY-MM... (sub-feature 3 - filtered events)
```

## Related docs
- [f2-bills-dashboard.md](f2-bills-dashboard.md) - sub-feature 2 (parent).
- [f2-bills-sync.md](f2-bills-sync.md) - sub-feature 1, produces the snapshot.

---

# L1 - Capabilities (APPROVED)

## In-scope

1. **GET /api/bills/dashboard/events?month=YYYY-MM[&filters...]** - returns filtered + sorted events for the requested month. HTTP 200 on success (even when result is empty).

2. **Read from `data/private/bills_dashboard_YYYY-MM.json`** on disk via `storage.bills_dashboard_path(month)`. No PS calls. No caching layer. Pure file read -> in-memory filter -> JSON response.

3. **Flatten** `partners[].events[]` into one list. Each event keeps its 10 fields exactly as written by sub-feature 1 (id, date, day, title, type, category, partner, amount, is_cc_payment, is_matched).

4. **Filters (all AND, all optional, all exact-match except dates):**
   - partner - string, exact match on `event["partner"]`.
   - type - must be one of `{bill, buy, savings, salary}` (model Literal). Invalid -> 400.
   - category - string, exact match (case-sensitive). No validation.
   - from - ISO date `YYYY-MM-DD`, inclusive lower bound on `event["date"]`.
   - to - ISO date `YYYY-MM-DD`, inclusive upper bound on `event["date"]`.
   - Empty filter value (`?partner=`) -> treated as None (no filter).

5. **Sort:** `?order=asc|desc`, default `asc`. Sort key: `(date, partner, id)`. `desc` reverses on date only; partner and id stay asc as tiebreakers.

6. **Limit:** `?limit=N`, default 500, silent clamp to 1000 cap. `limit<1` -> 400. Non-numeric -> 400.

7. **Response:** `{"events": [...], "total": N}`. `total` = count AFTER filters, BEFORE limit clamp.

8. **Empty result** -> 200 + `{"events": [], "total": 0}`. NOT 404.

9. **Cache-Control: no-store** on ALL responses (200, 400, 404, 500) via middleware.

10. **Same router** (`routers/bills.py`) - additive handler. No refactor of sub-feature 2.

11. **Error mirrors sub-feature 2:**
    - 400 -> `{"detail": ["err1", "err2", ...]}` - **list of strings** (diverges from sub-feature 2 single string).
    - 404 -> `{"detail": "No snapshot for {month}. Run GET /api/sync?start_month={month}&end_month={month} to generate one."}` - same as sub-feature 2.
    - 500 -> `{"detail": "internal error reading snapshot"}` for OSError/JSON errors. Specific shape errors get suffix: `internal error reading snapshot: missing partners` or `... events is not a list`.

## Out-of-scope

1. No PS calls.
2. No aggregation / no grouping.
3. No pagination cursor - offset-style limit only.
4. No multi-partner filter (one value only).
5. No fuzzy / substring search.
6. No sort-by-other-field (date/partner/id only).
7. No in-memory cache.
8. No FE changes.
9. No auth (single-user app).
10. No sub-feature 2 refactor.

## Success criteria

| Outcome | Measure |
|---|---|
| FE requests all events for a month | GET /api/bills/dashboard/events?month=2026-07 returns 200, all events sorted asc, total=count. |
| FE filters by partner | `?partner=Fixture A` returns only Fixture A's events. |
| FE filters by type | `?type=bill` returns only bills. |
| FE filters by date range | `?from=2026-07-15&to=2026-07-20` returns events in [15, 20] inclusive. |
| FE paginates | `?limit=10&order=desc` returns first 10, descending. |
| Filter excludes everything | 200 + `{events: [], total: 0}`. |
| User sends `?type=income` (not in allow-list) | 400 + `{"detail": ["invalid type: income"]}`. |
| User sends `?from=foo` | 400 + `{"detail": ["invalid from date: foo"]}`. |
| User sends `?limit=0` | 400 + `{"detail": ["limit must be >= 1"]}`. |
| User sends `?limit=10000` | 200, capped to 1000. `total` reflects pre-clamp count. |
| Multiple invalid params | 400 with all errors in alphabetical order: category, from, limit, month, order, partner, to, type. |
| Snapshot missing | 404 with sync URL hint. |
| Snapshot corrupt | 500 generic + stderr traceback. |
| Snapshot has wrong shape (no `partners` key) | 500 + `internal error reading snapshot: missing partners`. |
| Snapshot has `partners[].events` not a list | 500 + `internal error reading snapshot: events is not a list`. |
| 200, 400, 404, 500 all carry Cache-Control: no-store. | Verified in tests. |

## L1 assumptions + risks

### Assumptions

- **Snapshot file exists** for the requested month (written by sub-feature 1 sync job).
- **Snapshot file is valid JSON** (sync job validates with Pydantic before atomic write).
- **Events list is small** per month (< 10K typical). Linear in-memory filter is fine.
- **type Literal is stable** at the 4 values: bill, buy, savings, salary.
- **Single-user app** - no per-user authorization.

### Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Events list grows large (100K+) | Very low | Silent 1000-cap on limit prevents response bloat. `total` still accurate for FE pagination UI. |
| User sends `?order=foo` | Low | 400 with specific message. |
| Multiple invalid params confuse the user | Low | Collect all errors in alphabetical order. Single response with full list. |
| Shape regression in snapshot | Very low | Defensive isinstance check -> 500 with specific message. |
| `HTTPException` strips `Response.headers` | Medium (known FastAPI gotcha) | Middleware sets `Cache-Control: no-store` on all `/api/bills/*` paths after handler runs. Covers 200, 400, 404, 500. |

## L1 checkpoint - locked decisions

1. **Response shape = `{events: [...], total: N}`** (Q1).
2. **Type allow-list = `{bill, buy, savings, salary}`** (Q2) - mirrors model Literal.
3. **Date range inclusive both ends** (Q3).
4. **Silent clamp to 1000; `limit<1` -> 400** (Q4).
5. **Empty result = 200 + empty events** (Q5) - NOT 404.
6. **`?order=asc|desc`, default `asc`** (Q6).
7. **Category match = exact, case-sensitive** (Q7).
8. **Partner = single value only** (Q8).

---

# L2 - Components (APPROVED)

## Existing components (reuse-first)

| Component | File | Role in this sub-feature |
|---|---|---|
| **Storage** | [services/storage.py](../src/budget_api/services/storage.py) | Reuses `bills_dashboard_path(month) -> Path`. Same as sub-feature 2. |
| **Models** | [models/bills.py](../src/budget_api/models/bills.py) | `BillsEvent`, `BillsSnapshot` exist. Handler does NOT import/validate against them (matches sub-feature 2 trust-the-file pattern). |
| **FastAPI app** | [main.py](../src/budget_api/main.py) | Adds middleware for `Cache-Control: no-store` on `/api/bills/*` (covers sub-feature 2 + 3). |
| **Existing router pattern** | `routers/bills.py` (from sub-feature 2) | Same file, new handler. |

## New components

| Component | File | Role |
|---|---|---|
| **events handler** | `routers/bills.py` (extend) | `def events(month, partner, type, category, from_, to, order, limit) -> dict` - sync, ~80 lines. |
| **`_match` helper** | same file | `def _match(event, partner, type_, category, parsed_from, parsed_to) -> bool` - AND of all filter conditions. |
| **No-store middleware** | `main.py` (extend) | `@app.middleware("http")` sets `Cache-Control: no-store` on all `/api/bills/*` responses. |
| **Tests** | `tests/bills/test_events.py` (new) | 43 acceptance tests. Reuses `client`, `tmp_private_dir` from conftest. |

## Component boundaries

```
GET /api/bills/dashboard/events?month=YYYY-MM&partner=X&type=...
  |
  v
routers/bills.py: events(month, partner, type, category, from_, to, order, limit)
  |
  +-- Validate (alphabetical: category, from, limit, month, order, partner, to, type)
  |   +-- errors collected into list[str]; raise 400 with detail=list if non-empty
  |
  +-- Normalize: empty string -> None
  |
  +-- Clamp limit silently to 1000 cap
  |
  +-- path = storage.bills_dashboard_path(month)
  |
  +-- read + parse + shape check (same try/except pattern as sub-feature 2)
  |   +-- FileNotFoundError -> 404
  |   +-- OSError / JSONDecodeError -> 500 + stderr
  |   +-- not isinstance(snapshot, dict) -> 500 + "missing partners"
  |   +-- not isinstance(partners, list) -> 500 + "missing partners"
  |   +-- not isinstance(partner_block, dict) -> 500 + "partner block is not a dict"
  |   +-- any partner["events"] not list -> 500 + "events is not a list"
  |
  +-- Flatten: for partner_block in partners: for event in events
  |
  +-- Filter: _match(event, partner, type, category, parsed_from, parsed_to)
  |
  +-- Sort: stable sort (partner, id) asc, then sort by date with order direction
  |   (date flips with `?order=desc`; partner/id always asc as tiebreakers)
  |
  +-- Clamp: [:effective_limit]
  |
  +-- return {"events": [...], "total": len(sorted_pre_clamp)}
```

## Reuse-first rationale

| New component | Why not reuse existing? |
|---|---|
| events in `routers/bills.py` (vs new file) | Sub-feature 2 says "one bills router". Stub was placed for sub-feature 3 explicitly. |
| `_match` as private function | Inline in handler = 5 if-statements; helper = 1 call. Helper reads cleaner. |
| No Pydantic validate on events | Trust the file matches sub-feature 2. Pydantic adds 1 import + 1 model + error shape change. No win. |
| `Query` with `pattern=` for date params | Date format needs custom error message (`invalid from date: foo`), not FastAPI auto-gen. Manual `date.fromisoformat()` + `ValueError` catch. |
| `Query` with `pattern=` for order | Same - custom error message. Manual `not in (...)` check. |
| `Query` with `int` for limit | FastAPI auto-gen 422 -> main.py 400 rewrite gives `{"detail": "query -> limit: ..."}`. We need `{"detail": ["invalid limit: abc"]}`. Manual `int(limit)` + `ValueError` catch. |
| `response: Response` for Cache-Control | `HTTPException` strips it. Middleware survives. |

## L2 checkpoint - locked decisions

1. **Validate manually** (not FastAPI `Query(pattern=)`) - control over error message format (list of strings).
2. **`limit` is a string param** - manual parse to control error message.
3. **`from` is Python keyword** - `Query(alias="from")` + `from_` internal name.
4. **`type` shadows builtin** - accept (no alias), use as-is, lint comment.
5. **Errors collected in alphabetical order** - category, from, limit, month, order, partner, to, type.
6. **400 `detail` is a LIST** - diverges from sub-feature 2 single string.
7. **Cache-Control via middleware** - `HTTPException` strips `Response.headers`.
8. **No `_SnapshotShapeError` exception class** - raise `HTTPException` directly (simpler, no need to plumb through handler).
9. **Sort is two-pass stable** - `(partner, id)` asc first, then `date` with caller-chosen direction. Stable sort preserves the first pass within equal-date ties, so partner/id stay asc regardless of `?order`.

---

# L3 - Interactions (APPROVED)

## Request flow

```
HTTP GET /api/bills/dashboard/events?month=2026-07&partner=Fixture A&type=bill&limit=10
  |
  v
FastAPI routing -> routers/bills.py: events(...)
  |
  +-- Validate (alphabetical):
  |   +-- category, from, limit, month, order, partner, to, type
  |   +-- errors -> raise 400 {detail: [err1, err2, ...]}
  |
  +-- Read + parse + shape check (same as sub-feature 2 + isinstance checks)
  |   +-- FileNotFoundError -> 404 with sync hint
  |   +-- OSError / JSON -> 500 + stderr
  |   +-- isinstance failures -> 500 with specific suffix
  |
  +-- Flatten partners[].events[]
  |
  +-- Filter via _match (AND of all conditions)
  |
  +-- Sort: stable (partner, id) asc, then sort by date with order direction
  |
  +-- Slice [:effective_limit] (silent clamp to 1000)
  |
  +-- return {"events": [...], "total": N}
  |
  v
main.py: no-store middleware sets Cache-Control: no-store on response
  |
  v
HTTP 200 / 400 / 404 / 500 with body + Cache-Control header
```

## Failure modes

| Failure | HTTP | Body | Logged? |
|---|---|---|---|
| month not `^\d{4}-\d{2}$` | 400 | `{"detail": ["invalid month format"]}` | No |
| type not in allow-list | 400 | `{"detail": ["invalid type: X"]}` | No |
| from/to not ISO date | 400 | `{"detail": ["invalid from date: X"]}` | No |
| limit not parseable int | 400 | `{"detail": ["invalid limit: X"]}` | No |
| limit < 1 | 400 | `{"detail": ["limit must be >= 1"]}` | No |
| order not asc/desc | 400 | `{"detail": ["invalid order: X"]}` | No |
| Multiple invalid params | 400 | `{"detail": [err1, err2, ...]}` alphabetical | No |
| Snapshot missing | 404 | `{"detail": "No snapshot for {month}. Run ..."}` | No |
| OSError reading file | 500 | `{"detail": "internal error reading snapshot"}` | Yes (traceback) |
| JSONDecodeError | 500 | `{"detail": "internal error reading snapshot"}` | Yes (traceback) |
| snapshot not a dict | 500 | `{"detail": "internal error reading snapshot: missing partners"}` | Yes (one-liner) |
| partners not a list | 500 | `{"detail": "internal error reading snapshot: missing partners"}` | Yes (one-liner) |
| partner_block not a dict | 500 | `{"detail": "internal error reading snapshot: partner block is not a dict"}` | Yes (one-liner) |
| partners[].events not a list | 500 | `{"detail": "internal error reading snapshot: events is not a list"}` | Yes (one-liner) |
| Filter excludes everything | 200 | `{"events": [], "total": 0}` | No |
| Empty filter value (`?partner=`) | 200 | filter ignored | No |
| 200 / 400 / 404 / 500 all | - | - | `Cache-Control: no-store` always present |

## Concurrency

- **Reads concurrent-safe** on all OSes.
- **Read-during-write race**: same as sub-feature 2. Atomic write protects.
- **Multiple FE clients** can read same file safely.

## Security

- **Path traversal** blocked by month regex (same as sub-feature 2).
- **No user input** beyond query params, all validated.
- **500 body** has no file path / no error detail.
- **No auth** (single-user app).

## L3 checkpoint - locked decisions

1. **No log on 200** - match existing routers.
2. **No log on `warnings[]`** - FE has them.
3. **No correlation ID** - over-engineering for single-user app.
4. **Empty result = 200** (not 404) - distinguish "no events match" from "no snapshot at all".
5. **Filter `from > to` = 200 + empty** - no validation, matches Postgres range behavior intuition.

---

# L4 - Contracts (APPROVED)

## New endpoint

### GET /api/bills/dashboard/events

| Aspect | Value |
|---|---|
| **Path** | /api/bills/dashboard/events |
| **Method** | GET |
| **Query params** | month (required, regex); partner, type, category, from, to, order, limit (all optional) |
| **Auth** | None |
| **Cache-Control** | no-store - always fresh, set by middleware on all responses |
| **Mounted at** | `routers/bills.router` in main.py with `prefix="/api"` |

## Request

```
GET /api/bills/dashboard/events?month=YYYY-MM&partner=X&type=bill&from=2026-07-01&to=2026-07-31&order=asc&limit=10
```

| Param | Type | Required | Validation | Empty value | On fail |
|---|---|---|---|---|---|
| month | string | yes | `^\d{4}-\d{2}$` | n/a | 400 `["invalid month format"]` |
| partner | string | no | exact match (no allow-list) | treat as None | filter ignores |
| type | string | no | one of `{bill, buy, savings, salary}` | treat as None | 400 `["invalid type: X"]` |
| category | string | no | exact match (case-sensitive) | treat as None | filter ignores |
| from | ISO date YYYY-MM-DD | no | `date.fromisoformat()` | treat as None | 400 `["invalid from date: X"]` |
| to | ISO date YYYY-MM-DD | no | `date.fromisoformat()` | treat as None | 400 `["invalid to date: X"]` |
| order | enum | no | one of `{asc, desc}`, default `asc` | default | 400 `["invalid order: X"]` |
| limit | int | no | parseable int, >=1, default 500, silent clamp to 1000 | default | 400 `["invalid limit: X"]` or `["limit must be >= 1"]` |

**Validation order** (alphabetical): category, from, limit, month, order, partner, to, type.

## Response shapes

### 200 OK - happy path

```
HTTP/1.1 200 OK
Content-Type: application/json
Cache-Control: no-store
```

Body:
```json
{
  "events": [
    {
      "id": "evt-123",
      "date": "2026-07-15",
      "day": 15,
      "title": "Salary - Fixture A",
      "type": "salary",
      "category": "Income",
      "partner": "Fixture A",
      "amount": 42000.0,
      "is_cc_payment": false,
      "is_matched": null
    }
  ],
  "total": 5
}
```

`total` = count after filters, before limit clamp.

### 200 OK - empty result

```json
{"events": [], "total": 0}
```

### 400 Bad Request

Body: `{"detail": ["err1", "err2", ...]}` - **list of strings** in alphabetical order.

Single error:
- `{"detail": ["invalid month format"]}`
- `{"detail": ["invalid type: income"]}`
- `{"detail": ["invalid from date: foo"]}`
- `{"detail": ["invalid limit: abc"]}`
- `{"detail": ["limit must be >= 1"]}`
- `{"detail": ["invalid order: foo"]}`
- `{"detail": ["invalid to date: 2026-02-30"]}`

Multi-error (alphabetical):
- `{"detail": ["invalid from date: bad", "limit must be >= 1", "invalid type: income"]}` (from, limit, type alphabetical)

### 404 Not Found

Body: `{"detail": "No snapshot for {month}. Run GET /api/sync?start_month={month}&end_month={month} to generate one."}`

**Same as sub-feature 2.** Sub-feature 2 string shape preserved.

### 500 Internal Server Error

Generic (OSError, JSON):
- `{"detail": "internal error reading snapshot"}` (full traceback to stderr)

Shape error:
- `{"detail": "internal error reading snapshot: missing partners"}` (one-liner log to stderr)
- `{"detail": "internal error reading snapshot: events is not a list"}` (one-liner log to stderr)
- `{"detail": "internal error reading snapshot: partner block is not a dict"}` (one-liner log to stderr)

## Backward compatibility

- **No existing endpoint affected.** New endpoint, same router.
- **Sub-feature 2 `dashboard()` handler unchanged** in shape, only removed `response: Response` param (now redundant with middleware).
- **`routers/bills.py` import of `Response` removed** (no longer used).
- **main.py adds 1 middleware** - no change to existing handlers/middleware.
- **Pydantic models** unaffected (no new model).
- **No client types affected** (FE will add new call in a separate sub-task).

## Testable acceptance criteria (43 tests)

| AC | Test |
|---|---|
| 200 + all events + total=5 | `test_events_happy_path_all_events` |
| Default sort asc by (date, partner, id) | `test_events_no_filters_default_order_asc` |
| `?order=desc` reverses date | `test_events_order_desc_reverses_date_first` |
| Same-date tiebreak: partner/id stay asc on `?order=desc` | `test_events_order_desc_same_date_partner_asc` |
| `?partner=Fixture A` | `test_events_filter_partner` |
| `?partner=Nobody` -> 200 empty | `test_events_filter_partner_no_match` |
| `?type=bill` | `test_events_filter_type_bill` |
| `?type=income` -> 400 | `test_events_filter_type_invalid` |
| `?category=Income` | `test_events_filter_category_income` |
| `?category=income` case-sensitive | `test_events_filter_category_case_sensitive` |
| `?from=&to=` window | `test_events_filter_date_range_inclusive` |
| `?from=to=` same day | `test_events_filter_date_same_day` |
| `?from>to` -> 200 empty | `test_events_filter_date_from_greater_than_to` |
| `?from=foo` -> 400 | `test_events_filter_date_invalid_format` |
| `?from=2026-13-99` -> 400 | `test_events_filter_date_invalid_calendar` |
| `?to=2026-02-30` -> 400 | `test_events_filter_date_invalid_feb_30` |
| `?limit=2` -> 2 events, total=5 | `test_events_limit_first_n` |
| `?limit=0` -> 400 | `test_events_limit_zero` |
| `?limit=-1` -> 400 | `test_events_limit_negative` |
| `?limit=abc` -> 400 | `test_events_limit_non_numeric` |
| `?limit=10000` -> 1000 cap, total=1100 | `test_events_limit_clamp_silently` |
| `?order=foo` -> 400 | `test_events_order_invalid` |
| All filters combined | `test_events_combined_filters` |
| 3 errors alphabetical | `test_events_multi_error_collection` |
| Month + type errors alphabetical | `test_events_multi_error_month_and_type` |
| No snapshot -> 404 | `test_events_snapshot_missing_404` |
| Corrupt JSON -> 500 | `test_events_corrupt_json_500` |
| Empty file -> 500 | `test_events_empty_file_500` |
| Missing partners -> 500 | `test_events_shape_missing_partners_500` |
| events not list -> 500 | `test_events_shape_events_not_list_500` |
| partner_block not dict -> 500 | `test_events_shape_partner_block_not_dict_500` |
| 10 sequential reads all 200 | `test_events_repeated_10x` |
| Cache-Control 200 | `test_events_cache_control_on_200` |
| Cache-Control 400 | `test_events_cache_control_on_400` |
| Cache-Control 404 | `test_events_cache_control_on_404` |
| `?partner=` empty | `test_events_empty_partner_value` |
| `?category=` empty | `test_events_empty_category_value` |
| `?type=` empty | `test_events_empty_type_value` |
| `total` pre-clamp | `test_events_total_reflects_pre_clamp` |
| Default limit 500 | `test_events_default_limit_500` |
| `?from=` empty -> no filter | `test_events_empty_from_value` |
| `?to=` empty -> no filter | `test_events_empty_to_value` |
| `?limit=` empty -> default | `test_events_empty_limit_value` |
| Cache-Control on 500 | `test_events_cache_control_on_500` |

## L4 checkpoint - locked decisions

1. **400 detail is LIST** (L2 Q3) - diverges from sub-feature 2 string.
2. **Multi-error alphabetical** (L4 Q2) - predictable for FE.
3. **Cache-Control on ALL responses** (L3 Q1) - via middleware.
4. **Empty filter = no filter** (L4 Q1) - `?partner=` -> all events.
5. **Sort: date direction flips, tiebreakers stable** (C1 fix) - same-date partner/id stays asc on `?order=desc`.
6. **Partner block type-checked** (C2 fix) - defensive `isinstance` guard prevents AttributeError leak.

---

# L5 - Implementation Plan (APPROVED)

## File manifest

| File | Action | Approx lines |
|---|---|---|
| src/budget_api/routers/bills.py | EDIT (extend) | +175 |
| src/budget_api/main.py | EDIT (add middleware) | +14 |
| src/budget_api/tests/bills/test_events.py | CREATE | ~970 |
| docs/design/f2-bills-dashboard.md | EDIT (append) | ~470 |

**Total: 1 create, 3 edits, ~+1629 net lines.**

## Ordered execution plan

### Step 1: Branch (already on feat/f2-bills-dashboard-subfeature-2)

### Step 2: Implement handler + middleware (agent-driven, no commit)

- Edit `routers/bills.py`: add `events()` handler, `_match()` helper, sort constants.
- Edit `main.py`: add no-store middleware for `/api/bills/*`.
- Combined with Step 3 in one commit.

### Step 3: Implement tests (agent-driven, no commit)

- Create `tests/bills/test_events.py` covering 43 ACs above.
- Run `pytest src/budget_api/tests/bills/test_events.py -q` until green.
- Verify full suite green: `pytest src/budget_api/tests -q`.

### Step 4: Doc append (same commit as code per L5 Q1)

- Append sub-feature 3 sections to `docs/design/f2-bills-dashboard.md`.

### Step 5: Address review feedback (same branch)

- C1 fix: sort by `(partner, id)` asc first (stable), then by date with order direction.
- C2 fix: `isinstance(partner_block, dict)` guard before `.get()`.
- C3 fix: regression test for same-date tiebreak behavior.
- C4 fix: scrub corrupted chars from doc appendix.

## Test plan

| Test | Type | Coverage |
|---|---|---|
| Happy path + all filters | Integration (TestClient + tmp_private_dir) | AC 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 22, 34, 35, 36, 38, 39, 40 |
| Validation errors | Integration | AC 7, 13, 14, 15, 17, 18, 19, 21, 23, 24 |
| Limit logic | Integration | AC 16, 20, 37, 38 |
| Error paths | Integration | AC 25, 26, 27, 28, 29, 30 |
| Concurrency | Integration (ThreadPoolExecutor) | AC 31 |
| Headers | Integration | AC 32, 33, 34, 42 |

**Total: 43 tests, ~970 lines.**

## Risk controls

| Risk | Mitigation |
|---|---|
| `HTTPException` strips `Response.headers` (Cache-Control missing on 400/404/500) | Middleware sets header after `call_next`. Verified by tests 32, 33, 42. |
| Forgetting alphabetical validation order | Multi-error tests 23, 24 assert exact list. |
| Limit clamp regression | Test 20 uses 1100 events, asserts cap=1000. |
| `total` not pre-clamp | Test 37 asserts total=100, events.length=10. |
| `type` builtin shadowing lints | `# noqa: A002` comment + comment in handler. |
| `from` keyword conflict | `Query(alias="from")` + `from_` internal name. |
| Same-date tiebreak flipped by `?order=desc` | Two-pass stable sort + regression test 3b. |
| Partner block not a dict -> AttributeError | `isinstance` guard before `.get()` + test 30. |

## Rollback strategy

- Revert PR. Sub-feature 2 keeps working (middleware additive, removes cleanly).
- No DB migration, no data migration.
- No FE dependency yet.

## L5 checkpoint - locked decisions

1. **One combined commit** (L5 Q1) - handler + tests + doc in one atomic commit.
2. **43 tests** (L5 Q2 + C3 regression guard) - covers all 42 original ACs plus same-date tiebreak.
3. **No new dependencies** - uses only stdlib (`re`, `sys`, `traceback`, `json`, `date`) + existing FastAPI.
4. **Middleware instead of Response param** - survives `HTTPException` raise.
5. **Two-pass stable sort** (C1 fix) - guarantees partner/id tiebreak asc regardless of `?order`.
6. **Defensive isinstance guards** (C2 fix) - prevents AttributeError leak on shape errors.

---

# Sub-feature 4 - Event Detail Endpoint (APPROVED L1-L5)

Status: All 5 levels approved. Implementation in progress.
Date: 2026-08-02
Owner: backend-dev

## What this sub-feature is

The read endpoint that returns one event by `id` for a given month, served from the per-month bills dashboard snapshot. Reads `data/private/bills_dashboard_YYYY-MM.json`, walks `partners[].events[]`, returns the first match as a bare event dict. No PS calls. Pure file read + in-memory lookup + JSON response.

## Relationship to sub-features 2 + 3

Same file (`routers/bills.py`). Same snapshot. New handler on same router.

```
GET /api/bills/dashboard?month=YYYY-MM           (sub-feature 2 - full snapshot)
GET /api/bills/dashboard/events?month=YYYY-MM... (sub-feature 3 - filtered events)
GET /api/bills/dashboard/event?id=X&month=YYYY-MM (sub-feature 4 - one event by id)
```

Sub-feature 4 reuses sub-feature 3's read + parse + shape-guard logic via a new private helper `_read_snapshot(month) -> dict`. Both `events()` and `event_detail()` call it.

## Related docs
- [f2-bills-dashboard.md](f2-bills-dashboard.md) - sub-features 2 (parent) + 3.
- [f2-bills-sync.md](f2-bills-sync.md) - sub-feature 1, produces the snapshot.

---

# L1 - Capabilities (APPROVED)

## In-scope

1. **GET /api/bills/dashboard/event?id={event_id}&month=YYYY-MM** - returns one event as a bare dict. HTTP 200 on success, 404 if id not in snapshot.

2. **Read from `data/private/bills_dashboard_YYYY-MM.json`** on disk via `storage.bills_dashboard_path(month)`. No PS calls. Pure file read.

3. **First-match-wins** across partners. If the same id appears in two partner blocks, the first occurrence in snapshot order wins.

4. **`id` regex:** `^[A-Za-z0-9_-]{1,64}$` - alphanumeric + `_` + `-`, 1-64 chars. Invalid -> 400 with `invalid event id format`.

5. **`month` regex:** `^\d{4}-\d{2}$` (reuse `_MONTH_PATTERN`). Invalid -> 400 with `invalid month format`.

6. **Response:** bare event dict (the 10 BillsEvent fields). No envelope. No `event` wrapper. No `total`.

7. **Missing `id`** (no param at all) -> 400 from FastAPI auto-gen (`Field required` via main.py 422->400 rewrite). Empty `id` (`?id=`) -> 400 + `["invalid event id format"]` (regex fail).

8. **Same router** (`routers/bills.py`) - additive handler. Refactor of `events()` to share `_read_snapshot()` helper.

9. **Cache-Control: no-store** on ALL responses (200, 400, 404, 500) via middleware (path added to `_NO_STORE_PATHS` in `main.py`).

10. **Error model:**
    - 400 -> `{"detail": ["err1", "err2", ...]}` - list of strings in alphabetical order (id, month). Diverges from sub-feature 2 string. Matches sub-feature 3 list.
    - 404 snapshot-missing -> sync-URL body (same as sub-features 2 + 3).
    - 404 event-not-found -> `{"detail": "Event {id} not found in {month}"}` - **distinct** body so FE can tell snapshot-missing from event-missing.
    - 500 -> generic + shape suffixes (same as sub-feature 3).

## Out-of-scope

1. No PS calls.
2. No aggregation / no joins.
3. No related-event lookup (e.g. partner=Fixture A when id=foo).
4. No fuzzy / substring id match - exact only.
5. No listing endpoints (sub-feature 3 already covers that).
6. No FE changes.
7. No auth (single-user app).
8. No new Pydantic model - trust the file like sub-features 2 + 3.

## Success criteria

| Outcome | Measure |
|---|---|
| FE requests one event by id | `GET /api/bills/dashboard/event?id=c1&month=2026-07` returns 200 + bare event dict. |
| Event exists in any partner block | 200 + that event's exact 10 fields. |
| Duplicate id across partners | 200 + first match in snapshot order. |
| Event not in snapshot | 404 + `{"detail": "Event {id} not found in {month}"}`. |
| Snapshot missing | 404 + sync-URL body. |
| `id` empty (`?id=`) | 400 + `["invalid event id format"]` (regex fail). |
| `id` has invalid chars (`/`, `.`, `\n`, etc.) | 400 + `["invalid event id format"]`. |
| `id` length 65 | 400 + `["invalid event id format"]`. |
| `month=foo` | 400 + `["invalid month format"]`. |
| Both `id` and `month` invalid | 400 with both errors in alphabetical order. |
| Snapshot corrupt | 500 generic + stderr traceback. |
| Snapshot has wrong shape (no `partners` key) | 500 + `internal error reading snapshot: missing partners`. |
| 200, 400, 404, 500 all carry Cache-Control: no-store. | Verified in tests. |

## L1 assumptions + risks

### Assumptions

- **Snapshot file exists** for the requested month.
- **Snapshot file is valid JSON** (sync job validates with Pydantic before write).
- **Event ids are unique within a single partner** - first-match-wins only matters across partners. (In practice ids are unique per partner block.)
- **`id` is a short string** (1-64 chars) - PS event ids are URL-safe.
- **Single-user app** - no per-user authorization.

### Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Same id across two partners (sync bug) | Very low | First-match-wins is deterministic. Documented in L4. |
| `id` regex rejects legitimate ids (spaces, colons, etc.) | Low | `id` from sync = PS event id, known to be URL-safe. |
| `id` shadows builtin `id()` | Low (lint only) | `# noqa: A002` comment matches sub-feature 3's `type` pattern. |
| 404 vs sync-URL 404 ambiguity for FE | Low | Distinct bodies - FE can branch on body text. |
| 500 body leak from shared `_read_snapshot` | Low | `_read_snapshot` raises same exceptions as `events()` did. No new failure modes. |

## L1 checkpoint - locked decisions

1. **Response = bare event dict** (Q1) - no envelope.
2. **`id` regex = `^[A-Za-z0-9_-]{1,64}$`** (Q2).
3. **`month` regex = `^\d{4}-\d{2}$` reuse** (Q3).
4. **First-match-wins across partners** (Q4) - deterministic, no error.
5. **404 snapshot-missing body = sync-URL** (Q5) - same as sub 2 + 3.
6. **404 event-not-found body = `Event {id} not found in {month}`** (Q6) - distinct from snapshot-missing.
7. **400 detail is LIST (alphabetical id, month)** (Q7) - matches sub 3, diverges from sub 2 string.
8. **Refactor: extract `_read_snapshot(month) -> dict`** (Q8) - shared by `events()` and `event_detail()`.

---

# L2 - Components (APPROVED)

## Existing components (reuse-first)

| Component | File | Role in this sub-feature |
|---|---|---|
| **Storage** | [services/storage.py](../src/budget_api/services/storage.py) | Reuses `bills_dashboard_path(month) -> Path`. |
| **Models** | [models/bills.py](../src/budget_api/models/bills.py) | `BillsEvent` exists. Handler does NOT import/validate against it (matches sub 2 + 3 trust-the-file pattern). |
| **FastAPI app** | [main.py](../src/budget_api/main.py) | Add `/api/bills/dashboard/event` to `_NO_STORE_PATHS` frozenset. |
| **`_MONTH_PATTERN`** | [routers/bills.py](../src/budget_api/routers/bills.py) | Reuse for `month` validation. |
| **Existing router pattern** | `routers/bills.py` (from sub 2 + 3) | Same file, new handler. |

## New components

| Component | File | Role |
|---|---|---|
| **`event_detail` handler** | `routers/bills.py` (extend) | `def event_detail(id, month) -> dict` - sync, ~30 lines. |
| **`_EVENT_ID_PATTERN` constant** | same file | `re.compile(r"^[A-Za-z0-9_-]{1,64}$")` next to `_MONTH_PATTERN`. |
| **`_read_snapshot(month) -> dict` helper** | same file (extract from `events()`) | Read + parse + shape-guard. Shared by `events()` and `event_detail()`. |
| **No-store path** | `main.py` (extend frozenset) | Add `"/api/bills/dashboard/event"` to `_NO_STORE_PATHS`. |
| **Tests** | `tests/bills/test_event_detail.py` (new) | 20 acceptance tests. Reuses helpers from `test_events.py` (copied for isolation). |

## Component boundaries

```
GET /api/bills/dashboard/event?id=X&month=YYYY-MM
  |
  v
routers/bills.py: event_detail(id, month)
  |
  +-- Validate (alphabetical: id, month)
  |   +-- errors collected into list[str]; raise 400 with detail=list if non-empty
  |
  +-- snapshot = _read_snapshot(month)  # shared helper
  |   +-- FileNotFoundError -> 404 with sync hint
  |   +-- OSError / JSON / shape -> 500 + stderr
  |
  +-- for partner_block in snapshot["partners"]:
  |   for event in partner_block.get("events", []):
  |     if event.get("id") == id:
  |       return event  # first-match-wins
  |
  +-- raise 404 {"detail": f"Event {id} not found in {month}"}
  |
  v
main.py: no-store middleware sets Cache-Control: no-store
  |
  v
HTTP 200 / 400 / 404 / 500 with body + Cache-Control header
```

## Reuse-first rationale

| New component | Why not reuse existing? |
|---|---|
| `event_detail` in `routers/bills.py` (vs new file) | Sub-feature 2 says "one bills router". All 3 endpoints co-locate. |
| `_read_snapshot` extracted (vs duplicate logic) | `events()` and `event_detail()` share read + parse + shape-guard. Extract to avoid divergence. |
| `id` builtin shadowing | Accept (no alias), use as-is, `# noqa: A002` comment. Matches sub 3's `type` pattern. |
| `Query` with `pattern=` for `id` | Need list-style error (`["invalid event id format"]`), not FastAPI auto-gen. Manual regex check. |
| Pydantic validate the returned event | Trust the file matches sub 2 + 3. No win. |

## L2 checkpoint - locked decisions

1. **Validate manually** (not FastAPI `Query(pattern=)`) - control over list-style error.
2. **`id` is a string query param** - no alias, `# noqa: A002`.
3. **Refactor: extract `_read_snapshot(month) -> dict`** - shared by `events()` and `event_detail()`.
4. **400 `detail` is a LIST** - diverges from sub 2 string, matches sub 3 list.
5. **Cache-Control via middleware** - add path to `_NO_STORE_PATHS` frozenset.
6. **No `_SnapshotShapeError` exception class** - raise `HTTPException` directly (matches sub 3).
7. **First-match-wins via file iteration order** - no sort needed (snapshot order is deterministic).

---

# L3 - Interactions (APPROVED)

## Request flow

```
HTTP GET /api/bills/dashboard/event?id=c1&month=2026-07
  |
  v
FastAPI routing -> routers/bills.py: event_detail(id, month)
  |
  +-- Validate (alphabetical: id, month)
  |   +-- errors -> raise 400 {detail: [err1, err2, ...]}
  |
  +-- snapshot = _read_snapshot(month)
  |   +-- FileNotFoundError -> 404 with sync hint
  |   +-- OSError / JSON -> 500 + stderr
  |   +-- isinstance failures -> 500 with specific suffix
  |
  +-- for partner_block in snapshot["partners"]:
  |   for event in partner_block.get("events", []):
  |     if event.get("id") == id:
  |       return event
  |
  +-- raise 404 {detail: f"Event {id} not found in {month}"}
  |
  v
main.py: no-store middleware sets Cache-Control: no-store
  |
  v
HTTP 200 / 400 / 404 / 500 with body + Cache-Control header
```

## Failure modes

| Failure | HTTP | Body | Logged? |
|---|---|---|---|
| `id` regex fail | 400 | `{"detail": ["invalid event id format"]}` | No |
| `month` regex fail | 400 | `{"detail": ["invalid month format"]}` | No |
| `id` empty / missing | 400 | `{"detail": "query -> id: Field required"}` (FastAPI auto-gen via main.py) | No |
| `month` empty / missing | 400 | `{"detail": "query -> month: Field required"}` (FastAPI auto-gen via main.py) | No |
| Both `id` and `month` bad | 400 | `{"detail": ["invalid event id format", "invalid month format"]}` alphabetical | No |
| Snapshot missing | 404 | `{"detail": "No snapshot for {month}. Run ..."}` | No |
| Event not in snapshot | 404 | `{"detail": "Event {id} not found in {month}"}` | No |
| OSError reading file | 500 | `{"detail": "internal error reading snapshot"}` | Yes (traceback) |
| JSONDecodeError | 500 | `{"detail": "internal error reading snapshot"}` | Yes (traceback) |
| snapshot not a dict | 500 | `{"detail": "internal error reading snapshot: missing partners"}` | Yes (one-liner) |
| partners not a list | 500 | `{"detail": "internal error reading snapshot: missing partners"}` | Yes (one-liner) |
| partner_block not a dict | 500 | `{"detail": "internal error reading snapshot: partner block is not a dict"}` | Yes (one-liner) |
| partners[].events not a list | 500 | `{"detail": "internal error reading snapshot: events is not a list"}` | Yes (one-liner) |
| 200 / 400 / 404 / 500 all | - | - | `Cache-Control: no-store` always present |

## Concurrency

- **Reads concurrent-safe** on all OSes (same as sub 2 + 3).
- **Read-during-write race**: same as sub 2 + 3. Atomic write protects.

## Security

- **Path traversal** blocked by `id` regex (1-64 chars, no `/`, `..`, null bytes) and `month` regex.
- **No user input** beyond query params, all validated.
- **500 body** has no file path / no error detail.
- **No auth** (single-user app).
- **Bare event response** = no sensitive aggregate / no PII beyond what the snapshot already contains.

## L3 checkpoint - locked decisions

1. **No log on 200** - match existing routers.
2. **No log on event-not-found** - 404 is normal FE control flow.
3. **No correlation ID** - over-engineering for single-user app.
4. **First-match-wins via iteration order** - no sort, no error.
5. **Snapshot-missing vs event-not-found have distinct 404 bodies** - FE can branch.

---

# L4 - Contracts (APPROVED)

## New endpoint

### GET /api/bills/dashboard/event

| Aspect | Value |
|---|---|
| **Path** | /api/bills/dashboard/event |
| **Method** | GET |
| **Query params** | `id` (required, regex); `month` (required, regex) |
| **Auth** | None |
| **Cache-Control** | no-store - always fresh, set by middleware on all responses |
| **Mounted at** | `routers/bills.router` in main.py with `prefix="/api"` |

## Request

```
GET /api/bills/dashboard/event?id=c1&month=2026-07 HTTP/1.1
Host: localhost:8000
```

| Param | Type | Required | Validation | On fail |
|---|---|---|---|---|
| `id` | string | yes | `^[A-Za-z0-9_-]{1,64}$` | 400 `["invalid event id format"]` or FastAPI auto-gen for empty/missing |
| `month` | string | yes | `^\d{4}-\d{2}$` | 400 `["invalid month format"]` or FastAPI auto-gen for empty/missing |

**Validation order** (alphabetical): id, month.

## Response shapes

### 200 OK - happy path

```http
HTTP/1.1 200 OK
Content-Type: application/json
Cache-Control: no-store
```

Body: **bare event dict** (10 fields, exactly as written by sub-feature 1). No envelope. No `event` wrapper. No `total`.

```json
{
  "id": "c1",
  "date": "2026-07-10",
  "day": 10,
  "title": "Test event",
  "type": "bill",
  "category": "Bills",
  "partner": "Fixture A",
  "amount": 100.0,
  "is_cc_payment": false,
  "is_matched": null
}
```

### 400 Bad Request

Body: `{"detail": ["err1", "err2", ...]}` - **list of strings** in alphabetical order.

Single error:
- `{"detail": ["invalid event id format"]}`
- `{"detail": ["invalid month format"]}`

Multi-error (alphabetical):
- `{"detail": ["invalid event id format", "invalid month format"]}`

FastAPI auto-gen (empty / missing param):
- `{"detail": "query -> id: Field required"}` (main.py rewrites 422 -> 400)
- `{"detail": "query -> month: Field required"}` (main.py rewrites 422 -> 400)

### 404 Not Found - snapshot missing

Body: `{"detail": "No snapshot for {month}. Run GET /api/sync?start_month={month}&end_month={month} to generate one."}`

**Same as sub-features 2 + 3.** Triggered when the snapshot file does not exist on disk.

### 404 Not Found - event not in snapshot

Body: `{"detail": "Event {id} not found in {month}"}`

**Distinct from snapshot-missing 404.** Triggered when snapshot exists but no event has the requested id.

### 500 Internal Server Error

Generic (OSError, JSON):
- `{"detail": "internal error reading snapshot"}` (full traceback to stderr)

Shape error:
- `{"detail": "internal error reading snapshot: missing partners"}` (one-liner log)
- `{"detail": "internal error reading snapshot: events is not a list"}` (one-liner log)
- `{"detail": "internal error reading snapshot: partner block is not a dict"}` (one-liner log)

## Backward compatibility

- **No existing endpoint affected.** New endpoint, same router.
- **Sub-feature 3 `events()` handler refactored** to use `_read_snapshot(month)` helper. Behavior unchanged.
- **main.py adds 1 path to `_NO_STORE_PATHS`** - no other change.
- **Pydantic models** unaffected (no new model).
- **No client types affected** (FE will add new call in a separate sub-task).

## Testable acceptance criteria (20 tests)

| AC | Test |
|---|---|
| 200 + bare event + id=c1 | `test_event_detail_happy_path` |
| 200 + all 10 BillsEvent fields | `test_event_detail_full_event_body` |
| Duplicate id across partners, first wins | `test_event_detail_first_match_wins` |
| 404 + `Event {id} not found in {month}` body | `test_event_detail_not_found_404` |
| Snapshot missing 404 + sync-URL body | `test_event_detail_snapshot_missing_404` |
| Missing `id` -> 400 (FastAPI auto-gen) | `test_event_detail_missing_id_400` |
| Missing `month` -> 400 (FastAPI auto-gen) | `test_event_detail_missing_month_400` |
| Empty `id` -> 400 (FastAPI auto-gen) | `test_event_detail_empty_id_400` |
| Path-traversal chars in `id` -> 400 | `test_event_detail_path_traversal_id_400` |
| `id` length 65 -> 400 | `test_event_detail_id_too_long_400` |
| `month=foo` -> 400 | `test_event_detail_bad_month_400` |
| Both `id` + `month` bad, alphabetical | `test_event_detail_multi_error_alphabetical` |
| Corrupt JSON -> 500 + stderr traceback | `test_event_detail_corrupt_json_500` |
| Empty file -> 500 + stderr traceback | `test_event_detail_empty_file_500` |
| Missing partners -> 500 + shape suffix | `test_event_detail_shape_missing_partners_500` |
| events not list -> 500 + shape suffix | `test_event_detail_shape_events_not_list_500` |
| partner_block not dict -> 500 + shape suffix | `test_event_detail_shape_partner_block_not_dict_500` |
| 10 parallel reads all 200 | `test_event_detail_concurrent_reads` |
| Cache-Control on 200 | `test_event_detail_cache_control_on_200` |
| Cache-Control on 400/404/500 | `test_event_detail_cache_control_on_errors` |

## L4 checkpoint - locked decisions

1. **Bare event response** (Q1) - no envelope, no `event` wrapper.
2. **`id` 1-64 chars, URL-safe** (Q2) - rejects spaces, slashes, dots, newlines.
3. **First-match-wins across partners** (Q3) - deterministic, no error.
4. **Snapshot-missing vs event-not-found have distinct 404 bodies** (Q4) - FE can branch.
5. **400 detail is LIST (alphabetical id, month)** (Q5) - matches sub 3.
6. **Cache-Control on ALL responses** (Q6) - via middleware.
7. **`id` builtin shadowing accepted** (Q7) - `# noqa: A002` + comment.
8. **Empty `id` -> 400 via FastAPI auto-gen** (Q8) - not custom.

---

# L5 - Implementation Plan (APPROVED)

## File manifest

| File | Action | Approx lines |
|---|---|---|
| src/budget_api/routers/bills.py | EDIT (extract helper + add handler) | +95 |
| src/budget_api/main.py | EDIT (add path to no-store set) | +2 |
| src/budget_api/tests/bills/test_event_detail.py | CREATE | ~310 |
| docs/design/f2-bills-dashboard.md | EDIT (append) | ~400 |

**Total: 1 create, 3 edits, ~+807 net lines.**

## Ordered execution plan

### Step 1: Branch (already on feat/f2-bills-dashboard-subfeature-2)

### Step 2: Refactor + handler (agent-driven, no commit)

- Edit `routers/bills.py`:
  - Add `_EVENT_ID_PATTERN` constant next to `_MONTH_PATTERN`.
  - Extract `_read_snapshot(month) -> dict` from `events()`.
  - Refactor `events()` to call `_read_snapshot(month)`.
  - Add `event_detail(id, month)` handler.
- Edit `main.py`: add `"/api/bills/dashboard/event"` to `_NO_STORE_PATHS`.

### Step 3: Tests (agent-driven, no commit)

- Create `tests/bills/test_event_detail.py` covering 20 ACs above.
- Run `pytest src/budget_api/tests/bills/test_event_detail.py -q` until green.
- Verify full suite green: `pytest src/budget_api/tests src/mega/tests src/v4_pipeline/tests src/mom/tests -q`.
- Target: 594 baseline + 20 new = 614 passed.

### Step 4: Doc append (same commit as code per L5 Q1)

- Append sub-feature 4 sections to `docs/design/f2-bills-dashboard.md`.

## Test plan

| Test | Type | Coverage |
|---|---|---|
| Happy path + full body | Integration | AC 1, 2 |
| First-match-wins | Integration | AC 3 |
| 404 distinct bodies | Integration | AC 4, 5 |
| Missing/empty params | Integration | AC 6, 7, 8 |
| Path traversal | Integration | AC 9 |
| Length + bad month | Integration | AC 10, 11 |
| Multi-error alphabetical | Integration | AC 12 |
| Corrupt JSON / empty file | Integration + capsys | AC 13, 14 |
| Shape errors | Integration | AC 15, 16, 17 |
| Concurrency | Integration + ThreadPoolExecutor | AC 18 |
| Headers | Integration | AC 19, 20 |

**Total: 20 tests, ~310 lines.**

## Risk controls

| Risk | Mitigation |
|---|---|
| `_read_snapshot` extraction breaks `events()` tests | Run full suite after refactor. 594 baseline must hold before adding new tests. |
| `id` builtin shadowing lints | `# noqa: A002` comment + comment in handler. |
| First-match-wins surprises FE | Documented in L4 + test 3 asserts order. |
| Snapshot-missing vs event-not-found body confuses FE | Distinct bodies + tests 4 + 5 assert exact strings. |
| `HTTPException` strips `Cache-Control` | Middleware sets header after `call_next`. Verified by tests 19, 20. |

## Rollback strategy

- Revert PR. Sub-features 2 + 3 keep working (extracted helper is internal).
- No DB migration, no data migration.
- No FE dependency yet.

## L5 checkpoint - locked decisions

1. **One combined commit** (L5 Q1) - refactor + handler + tests + doc in one atomic commit.
2. **20 tests** (L5 Q2) - covers all 20 ACs in L4.
3. **No new dependencies** - uses only stdlib + existing FastAPI (same as sub 3).
4. **Middleware path addition** (L5 Q3) - survives `HTTPException` raise.
5. **Refactor `_read_snapshot` is a single commit** (L5 Q4) - no `events()` behavior change. Baseline 594 must hold.
6. **Test helpers copied, not imported** (L5 Q5) - matches sub 3 isolation pattern; one extra ~50 lines.

