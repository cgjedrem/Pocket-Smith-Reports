# F2 — Bills & Scheduled Buys — Source of Truth (DRAFT)

Status: L1 in progress. Not human-approved.
Date: 2026-08-02
Repo: Pocket-Smith-Reports
Owner: coordinator

## What this doc is

The contract between FE and BE. L1 below defines what the solution must do, grounded in what the PocketSmith API actually supports. L2-L5 live in companion docs.

**Conventions:**
- Field labels are **Title Case** in this doc (human contract).
- Field names in code / API are **snake_case** (see [f2-bills-api.md](f2-bills-api.md)).
- Derived formulas (math) live in [f2-bills-derivations.md](f2-bills-derivations.md).
- PS-specific quirks live in [f2-bills-ps-integration.md](f2-bills-ps-integration.md).

## Companion docs
- [f2-bills-derivations.md](f2-bills-derivations.md) — math, edge cases, presentation sub-derivations.
- [f2-bills-api.md](f2-bills-api.md) — endpoint contracts, request/response shapes.
- [f2-bills-snapshot.md](f2-bills-snapshot.md) — snapshot file shape, async job lifecycle.
- [f2-bills-ps-integration.md](f2-bills-ps-integration.md) — PS account types, role filters, sign-convention note.
- [f2-bills-test-plan.md](f2-bills-test-plan.md) — per-scenario test list (L5).

## Related
- FE mock layer: [client/src/components/bills/finance-data.ts](../client/src/components/bills/finance-data.ts)
- FE types: [client/src/types/api.ts:111-200](../client/src/types/api.ts#L111-L200)
- Existing bills design: [docs/design/design-f2-bills.md](../docs/design/design-f2-bills.md)

---

# L1 — Capabilities (grounded in PS API reality)

## What PS exposes for events

PocketSmith models the world as:

- **Transaction accounts** — the per-institution accounts the user transacts against (checking, savings, credit card). 11-value `type` enum: `bank | credits | cash | stocks | mortgage | loans | vehicle | property | insurance | other_asset | other_liability`. **There is no separate "checking" or "savings" sub-type — both live under `type=bank`** and are distinguished by the account's `name` (e.g. "Chr Check Handelsbanken" vs "Chr Savings Handelsbanken").
- **Scenarios** — PS's "budget" concept. Every account has a `primary_scenario` (and may have more). Events are created **on a scenario**, not directly on a transaction account.
- **Events** — scheduled future entries. Either a one-off (`repeat_type: "once"`) or a recurring series. `repeat_type` enum: `once | daily | weekly | fortnightly | monthly | yearly | each weekday`. `repeat_interval` is a multiplier (e.g. `weekly + repeat_interval: 2` = every 2 weeks).
- **Transactions** — actual posted entries with a signed amount. Pay against a `transaction_account`. Carry `category`, `payee`, `note`, `is_transfer`, `status: "pending" | "posted"`.
- **Categories** — tree with `is_bill`, `is_transfer`, `refund_behaviour`, `parent_id`.

> **The earlier design had two wrong assumptions**: (a) PS does NOT have separate `checking` / `savings` `type` values — both are `type=bank`. Local `account_mappings.json` uses `type: "checking" | "cc" | "savings"` as a local override, not a PS enum. (b) `repeat_type: "never"` does NOT exist in PS — the one-off value is `"once"`. (c) Events cannot be created via `POST /users/{id}/events` — they must be created via `POST /scenarios/{id}/events`. The CRUD design doc needs these corrections.

## What the F2-BE read path needs from PS

The existing [`PSClient`](../src/budget_api/services/ps_client.py) already covers every endpoint the read path needs:

| Endpoint | Method | Used by |
|---|---|---|
| `GET /users/{id}/events?start_date=&end_date=` | `PSClient.get_events()` (line 227) | Bucket-by-account filter for bills/buys/savings/salary events. |
| `GET /users/{id}/transactions?start_date=&end_date=` | `PSClient.get_transactions()` (line 201) | CC-account spend for `cc_usage`, `budget_usage`, savings-balance deltas. |
| `GET /transaction_accounts/{id}/transactions` | `PSClient.get_transactions_for_account()` (line 215) | Per-account spend during sync window. |
| `GET /users/{id}/transaction_accounts` | `PSClient.get_transaction_accounts()` (line 189) | List to find bills/CC/savings accounts per partner. |
| `GET /users/{id}/categories` | `PSClient.get_categories()` (line 246) | Category tree for role filter (`spend` / `savings` / `income` / `is_transfer`). |
| `GET /me` | `PSClient.get_me()` (line 182) | Bootstrap `user_id` for the sync job. |

No F2-BE gaps in the PS client. The design doc's [PS-integration §"API client reference"](../designs/f2-bills-ps-integration.md) is accurate.

## What F2-CRUD (future task) would need from PS

The CRUD design doc's endpoint matrix references `POST /users/{id}/events` — that endpoint does **not exist** in the PS API. The real paths are:

| What CRUD wants | Real PS path | Method | Status in code |
|---|---|---|---|
| Create event | `POST /scenarios/{id}/events` | needs body: `category_id`, `date`, `amount`, `repeat_type` (+optional `repeat_interval`, `note`) | ❌ no `_post` helper in `PSClient` |
| Update event | `PUT /events/{id}` | body: optional `amount`, `repeat_type`, `repeat_interval`, `note` — **`behaviour` required** (`"one" \| "forward" \| "all"`) | ❌ no `_put` helper |
| Delete event | `DELETE /events/{id}?behaviour=...` | `behaviour` is a **required query param** | ❌ no `_delete` helper |
| Create transaction | `POST /transaction_accounts/{id}/transactions` | body: required `payee`, `amount`, `date` (+optional `category_id`, `note`, etc.) | ❌ no `_post` helper |
| Discover scenario for create | `GET /accounts/{id}` | returns embedded `primary_scenario.id` | ✅ exists |

Plus quality-of-life gaps in the existing client:

- 429 retry strategy: not implemented. Design doc marks TBD.
- 422 / 409 body parsing: client raises `PSClientError(f"PS API error: {status} {body}")` but does not extract the `{"error": "..."}` field. CRUD's optimistic UI needs the actual message.
- `GET /users/{id}/events` does **not** support `search=` (only `transactions` does). CRUD's payee-search dialog would need a different strategy.

**F2-CRUD is NOT in scope for this design.** Listing it here only so the L1 capabilities below don't lock out the future.

---

## In-scope

The F2-BE bills dashboard backend must:

1. **Read all event data from PocketSmith** for a requested month. Source = PS events + transactions scoped by date window wider than the calendar month (buffer for estimate math). PS is read-only — no POST/PUT/DELETE.

2. **Produce a per-month snapshot file** (`data/private/bills_dashboard_YYYY-MM.json`) that the FE reads on every dashboard load. The snapshot is the single source of truth at runtime.

3. **Generate the snapshot via an async sync job** triggered by `POST /api/sync/bills` (returns `{job_id, status: "pending"}` immediately). Status-check via `GET /api/sync/bills/status?job_id=...`. Duplicate POSTs while a job is pending/running return the same `job_id`. Pattern follows the existing `/api/sync` and `/api/generate-report` flows.

4. **Serve the snapshot via a read endpoint** `GET /api/bills/dashboard?month=YYYY-MM` that returns the per-month payload plus per-partner derived fields. Past months use real data; current + future months use estimates.

5. **Paginate the events list** via `GET /api/bills/events?month=...&page=N&pageSize=M` (default `pageSize=12`, max `100`). Out-of-range page returns empty `events[]` with accurate `total`.

6. **Bucket events by transaction account `type`**, not by `repeat_type`. The PS enum value is `type=bank` for bills AND savings; the local `account_mappings.json: type: "checking" | "savings"` override tells us which `bank` account is which. Buckets:
   - bills-account events → **bills**
   - credits-account events → **scheduled CC buys**
   - savings-account events → **savings transfers**
   - bills-account income events → **salary**
   - refunds on bills-account → **bills** with positive amount
   - transfer categories (`is_transfer=true`) → **excluded**

7. **Include both recurring and one-off events.** `repeat_type: "once"` is the one-off value; everything else is recurring. No filter on this field — bucketing is by account.

8. **Compute the status label** per partner (`covered` / `partial` / `shortfall`) and return it in the response.

9. **Surface PS data fidelity issues** to the FE as warnings (e.g. salary missing for the month).

10. **Return explicit error responses** (HTTP 422) for:
    - No snapshot exists for the requested month → "Run POST /api/sync/bills to generate one."
    - No bills/checking account mapped for a partner → "Fixture A has no bills/checking account mapped."
    The FE renders these as an error page, not a 404.

11. **Match scheduled CC buys against real CC transactions** by date + amount, setting `is_matched: true` on the matched buy. Suppress matched buys from the upcoming-bill expectation.

12. **Cap the forward projection window at 12 months** from the current month. Past months are valid indefinitely.

13. **Use atomic file writes** (temp file + rename) so a killed sync doesn't leave a partial snapshot on disk.

## Out of scope

The F2-BE bills dashboard backend must NOT:

1. **Write to PS in any way.** No POST/PUT/DELETE on events, transactions, categories, accounts. The PS API is read-only for F2-BE.

2. **Maintain its own event database.** No SQLite, no JSON event log beyond per-month snapshots. PS is the canonical event store.

3. **Implement CRUD on events.** Salary creation, savings-transfer creation, bill/buy creation all stay in the PS web UI for now. (Future task — see [f2-bills-crud.md](f2-bills-crud.md). When F2-CRUD starts, it will need new `PSClient` POST/PUT/DELETE helpers.)

4. **Compute FE presentation sub-derivations** (capsule sub-widths, savings-box tone, etc.). The FE computes these from the high-level fields per [derivations §17](f2-bills-derivations.md).

5. **Provide real-time PS data on dashboard load.** The dashboard reads a pre-computed snapshot. Sync is on-demand, not push-based.

6. **Auto-sync on every PS event.** Editing an event in PS does not trigger a sync. The user clicks the existing Sync button.

7. **Prune or archive old snapshots** in v1. Files overwrite in place.

8. **Translate between the FE form's binary "recurring/one-off" toggle and PS's 7-value `repeat_type` enum.** That translation is F2-CRUD scope. The FE form's toggle stays inert in F2-BE.

## Success criteria

| Outcome | Measure |
|---|---|
| User opens the bills dashboard and sees current month data | First dashboard load returns the snapshot for the current month within 200ms (no PS calls in the read path). |
| User clicks Sync and the data refreshes | `POST /api/sync/bills` returns `{job_id, status: "pending"}` within 100ms; polling shows `completed` within 30s for a typical month. |
| User navigates to a past month and sees real data | `GET /api/bills/dashboard?month=YYYY-MM` (past) returns real CC bill + real budget usage, no estimate. |
| User navigates to a future month and sees estimates | `GET /api/bills/dashboard?month=YYYY-MM` (future) returns estimate only, `real_cc_bill: null`. |
| User walks 12 months forward and the savings balance is projected | All 12 future months return a `savings_balance` value derived from current + projected transfers. The 13th month returns an error. |
| User paginates through a long event list | `GET /api/bills/events` returns up to 100 events per page with accurate `total`. |
| User with no bills account sees a clear error | Response is HTTP 422 with `{detail: "...Fixture A has no bills/checking account mapped..."}`. |
| User navigates to a month with no snapshot | Response is HTTP 422 with `{detail: "...No snapshot for YYYY-MM. Run POST /api/sync/bills..."}`. FE renders an error page. |
| Sync survives a kill mid-write | The existing snapshot file is byte-for-byte unchanged if the sync process dies before the atomic rename. |

## L1 assumptions + risks

### Assumptions

- **PS API is reachable.** Sync requires the existing PS developer key in `.env`.
- **Account mappings are populated.** `data/private/account_mappings.json` has `partner_id` and the local `type: "checking" | "cc" | "savings"` override for each account the user wants to see.
- **Category roles are populated.** `data/private/category_roles.json` has `spend` / `savings` / `income` tags for the partner's categories.
- **Every bills/savings account has a `primary_scenario`** that the events are written to. (Used by future F2-CRUD; for F2-BE read-only, the scenario is embedded in event responses.)
- **Single-user app.** Both partners are owned by the same user; no per-user authorization on top of PS API key auth.

### Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| PS API rate limit (429) during sync | Medium | Document retry strategy in ps-integration.md. Job status reports the failure; user retries. |
| Snapshot file write is killed mid-write | Low | Atomic write pattern (temp file + rename). |
| User navigates 24 months back and one month has no snapshot | Medium | FE error page for 422. Clear message about running Sync. |
| PS transaction sign convention differs from events | Low | Both events and transactions use signed amounts in PS (positive=credit, negative=debit). Verified from live `2026-07_ps_raw.json`. |
| `is_bill` flag on PS categories is unused | Low | Bucketing is by `transaction_account.type == "bank"` + local override, not by `Category.is_bill`. |
| Local `events_*.json` cache files are empty | Medium | Current cache is empty (4 bytes per file). Sync must populate them; otherwise future reads of the cache miss. |
| `account_mappings.type: "cc"` doesn't match PS enum `"credits"` | Low | The local mapping overrides PS — already in place. Documented as local convention. |

## L1 checkpoint

Per the design-first skill, alignment check before moving to L2:

1. **Is "read-only" the right v1 scope?** The CRUD design doc says CRUD is future — but PS's API does support POST/PUT/DELETE on events. Are we locking out something that should be in v1?

2. **Are there capabilities missing?** E.g. should the dashboard show a "stale data" indicator when `synced_at` is older than N hours?

3. **Are any in-scope items actually out-of-scope?** E.g. is the 12-month forward cap arbitrary — could it be 6 or 24?

4. **Are the success-criteria numbers realistic?** 200ms first load, 30s sync, 100-event pages.

5. **PS API quirks surfaced** — do any need to be in scope (e.g. adding a search endpoint for the FE)?

6. **Risks unmitigated?** Anything here we should escalate or defer?

Approve L1, or call out changes.