# F2-CRUD — In-App Bills + Salary + Savings Event Management (L1 DRAFT)

Status: ROUGH DRAFT — L1 only. Not human-approved.
Date: 2026-08-01
Repo: Pocket-Smith-Reports
Owner: coordinator

## What this is

Sister design to the F2-BE dashboard read path. The dashboard (F2-BE) reads
events from PS and renders them. This doc covers the **future task**: managing
salary, savings, bills, and scheduled buys **from inside our app**, instead of
going to the PocketSmith web UI.

Why separate? Different scope, different risk surface, different endpoint
shape. The read path is GET-only; this would be the first **write** surface
in our API.

## Goals (L1)

1. Users can create, edit, and delete **salary / income events** for each
   partner without leaving the app.
2. Users can create, edit, and delete **scheduled savings transfers** for
   each partner.
3. Users can create, edit, and delete **bills and scheduled CC buys** (this
   is already half-built in the FE — the dialog exists, the BE is missing).
4. All writes go through to PocketSmith. Our DB has **no local events table**.
5. Optimistic UI: the local view updates immediately, then reconciles with the
   PS response. Roll back on failure.

## Non-goals

- Bulk import/export of events.
- Multi-event templates (e.g. "create 12 monthly rent events at once").
- Recurrence-rule editor beyond what PS supports (weekly/monthly/yearly).
- Sharing events across partners (PS doesn't model this — each event belongs to
  one transaction account which has one owner).

## Source-of-truth matrix (same bucketing rule as F2-BE)

> **Correction vs. earlier design.** Events are NOT created via `POST /users/{id}/events` — that endpoint does not exist in the PS API. Events are created via `POST /scenarios/{id}/events`. The BE must first resolve the scenario id for the target account via `GET /accounts/{id}` (which returns embedded `primary_scenario.id`).

| Action | Endpoint | PS endpoint | Notes |
|---|---|---|---|
| Create salary | `POST /api/bills/events` | `POST /scenarios/{primary_scenario_id}/events` | Body: `category_id` (income role), `date`, `amount`, `repeat_type`. Optional: `repeat_interval` (default 1), `note`. **No `payee`, no `transaction_account_id`** on the event — bound via scenario. |
| Edit salary | `PUT /api/bills/events/{ps_event_id}` | `PUT /events/{id}` | Body: optional `amount`, `repeat_type`, `repeat_interval`, `note`. **`behaviour` required** (`"one" \| "forward" \| "all"`). Cannot change `category_id` or `date` via this endpoint. |
| Delete salary | `DELETE /api/bills/events/{ps_event_id}` | `DELETE /events/{id}?behaviour=...` | `behaviour` is a **required query param**. Returns 204. |
| Create savings transfer | `POST /api/bills/events` | same | `category_id` (savings role), on a savings-account scenario. |
| Edit/delete savings transfer | same | same | |
| Create bill | `POST /api/bills/events` | same | `category_id` (spend role), on a bills-account scenario. |
| Edit/delete bill | same | same | |
| Create one-off transaction (raw) | `POST /api/bills/transactions` | `POST /transaction_accounts/{id}/transactions` | Body: required `payee`, `amount`, `date`. Optional: `category_id`, `note`, `memo`, `cheque_number`, `labels` (comma-separated string), `is_transfer`, `needs_review`. |

> Single endpoint `/api/bills/events` per CRUD verb for events; `/api/bills/transactions` for raw transactions. The `category_id` and the target scenario determine whether it's a salary, savings, or bill.

## What changes vs F2-BE

### PSClient becomes read-write

- Add `create_event`, `update_event`, `delete_event` methods to
  [src/budget_api/services/ps_client.py](../src/budget_api/services/ps_client.py).
  All new methods validate URLs (same `_validated_api_url` pattern as existing
  GETs).
- Add `_post`, `_put`, `_delete` helpers. URL validation must extend to allow
  `/scenarios/{id}/events` and `/events/{id}` paths.
- Add `get_account` method to fetch the `primary_scenario.id` (not currently
  exposed — `get_accounts` returns the list but not the embedded primary
  scenario in detail). Verify PS docs — `GET /accounts/{id}` returns the full
  account with embedded `primary_scenario`.

### FastAPI gets POST/PUT/DELETE handlers

- `POST /api/bills/events` — body shape mirrors PS events API.
- `PUT /api/bills/events/{ps_event_id}` — same body shape.
- `DELETE /api/bills/events/{ps_event_id}` — 204.

### FE dialog gets a third option

- Currently [AddEventDialog.tsx](client/src/components/bills/AddEventDialog.tsx)
  has `EntryType = "bill" | "credit-card"`. Add `"salary"` and `"savings"` as
  new options.
- The dialog's account-picker would derive its options from the user's account
  mappings:
  - `salary` → bills/checking accounts owned by this partner.
  - `savings` → savings accounts owned by this partner.
  - `bill` → bills/checking accounts.
  - `credit-card` → credits (CC) accounts.
- The category picker filters by role matching the chosen entry type.

### `schedule` toggle (recurring / one-off)

- The current FE dialog has a `schedule: "recurring" | "one-off"` toggle at
  [AddEventDialog.tsx:28](../client/src/components/bills/AddEventDialog.tsx#L28).
- This toggle is **F2-CRUD scope**, not F2-BE. The read path does not need it.
- When F2-CRUD lands, the toggle maps to PS's `repeat_type` field, but the
  mapping is non-trivial: PS's enum is `weekly | fortnightly | monthly | yearly`
  (no `once` — that's a separate flag), while the FE toggle is binary. F2-CRUD
  L2 will design this translation. For now: leave the FE toggle inert in
  F2-BE; F2-CRUD rewires it.
- The BE form payload for "create event" must include both `repeat_type`
  (from PS) and the FE-side `schedule` (binary). See f2-bills-crud.md L2 when
  it starts.

### Optimistic UI flow

1. FE submits → POST `/api/bills/events`.
2. FE immediately renders the new event in the event list with a "saving…"
   indicator.
3. BE writes to PS, returns the canonical event payload (with the real PS id).
4. FE replaces the optimistic row with the canonical row.
5. On failure → FE removes the optimistic row, shows a toast.

## Risk surface

| Risk | Mitigation |
|---|---|
| Delete salary → entire month's status flips | Show confirmation dialog with downstream impact ("This will drop Partner A's status to **shortfall**"). |
| Edit CC buy → matched flag breaks | Re-run match logic after edit (call new `POST /api/bills/match-buys?month=YYYY-MM`). |
| PS rate limit during bulk edit | Queue with backoff; show queue position in UI. |
| User changes partner on an existing event | Disallow — partner is derived from the account. Show error if mismatched. |
| Stale snapshot after a write | Trigger an automatic `POST /api/sync/bills` for the affected month after every successful write. |

## Open questions (L2 territory)

- **TBD**: confirmation flow for destructive writes (delete salary, edit savings
  transfer).
- **TBD**: how to handle PS API rate limits in the optimistic UI (queue vs
  fail-fast).
- **TBD**: do we keep a local "draft" state for partial forms (offline writes)?
- **TBD**: bulk edit (select multiple events → apply same change).
- **TBD**: undo support — PS has no rollback on DELETE. We could soft-delete in
  our snapshot and exclude from the dashboard, then hard-delete on next sync.
- **TBD**: who can create events for which partner? Today the app is
  single-user, both partners = same user. Future multi-user?

## What's already half-done (FE)

- [AddEventDialog.tsx](client/src/components/bills/AddEventDialog.tsx) — form
  exists with `bill` and `credit-card` types, recurring/one-off toggle,
  amount + day/date picker, partner selector. Comment line 1: "submit is a
  stub."
- [BillsDashboard.tsx](client/src/components/bills/BillsDashboard.tsx)
  wires the dialog with `openCreate` / `openEdit` / `dialogOpen` state.
- Type plumbing exists in [client/src/types/api.ts:111-150](../client/src/types/api.ts#L111-L150).

So the FE for `bill` and `credit-card` CRUD is mostly built. The missing
parts are: the submit handler, error handling, optimistic-UI scaffolding,
and the `salary` / `savings` types.

## Status

- **L1 (Goals)**: this doc.
- **L2 (Scenarios)**: not started.
- **L3 (API contract)**: not started.
- **L4 (Data model)**: not started.
- **L5 (Test plan)**: not started.

## Cross-references

- [f2-bills-be.md](f2-bills-be.md) — read-path index.
- [f2-bills-source-of-truth.md](f2-bills-source-of-truth.md) — bucketing rule.
- [f2-bills-derivations.md](f2-bills-derivations.md) — what the events mean
  once they land.
- [docs/design/design-f2-bills.md](../docs/design/design-f2-bills.md) — the
  original "salary + fixed bills = PS events, full CRUD via PS Events API"
  decision.