# F2-BE Sub-feature 1 — Sync Job (DRAFT)

Status: L1 in progress. Not human-approved.
Date: 2026-08-02
Repo: Pocket-Smith-Reports
Owner: coordinator

## What this sub-feature is

The **existing** `GET /api/sync?start_month=&end_month=` already fetches PS events + transactions per month in the range and writes per-month cache files. This sub-feature **extends** that flow to also produce a per-month `bills_dashboard_YYYY-MM.json` snapshot for every month in the range.

No new endpoint. No duplicate PS calls. The bills derivations are computed in the same per-month loop, from the same PS payloads the existing sync already pulls.

The **read** of the snapshot is sub-feature 2 (dashboard). The **shape** of the snapshot file is owned here (the writer defines it; the reader consumes it).

## Related docs (cross-cutting)
- [f2-bills-index.md](f2-bills-index.md) — index + shared PS-integration notes.
- [f2-bills-dashboard.md](f2-bills-dashboard.md) — sub-feature 2, consumes the snapshot.
- [f2-bills-events.md](f2-bills-events.md) — sub-feature 3, reads events from the snapshot.
- Old docs to migrate from: [f2-bills-snapshot.md](f2-bills-snapshot.md), [f2-bills-api.md](f2-bills-api.md), [f2-bills-derivations.md](f2-bills-derivations.md).

## What the existing `/api/sync` already does (verified from [sync_runner.py:158-280](../src/budget_api/services/sync_runner.py#L158-L280))

Per month in the range:
1. `client.get_transactions(user_id, start_date, end_date)` → writes `YYYY-MM_ps_raw.json`
2. `client.get_events(user_id, start_date, end_date)` → writes `events_YYYY-MM.json`

Once per sync:
3. `client.get_budget(user_id)` → `budget_snapshot.json`
4. `client.get_categories(user_id)` → `category_catalog.json`
5. `client.get_transaction_accounts(user_id)` → `account_catalog.json` + merges into `account_mappings.json`

Status file: `.sync_status.json` with `pending → running → success | failed`. Concurrency guard: `_sync_lock` (only one sync at a time).

**This sub-feature adds step 6: bills derivations + `bills_dashboard_YYYY-MM.json` write.** All the above stays.

## PS API surface used (all already called by existing sync)

| Endpoint | Method | Already called? | Used by bills derivations for |
|---|---|---|---|
| `GET /users/{id}/events?start_date=&end_date=` | `PSClient.get_events()` | ✅ Yes — per month | Bucket-by-account filter for bills/buys/savings/salary events. |
| `GET /users/{id}/transactions?start_date=&end_date=` | `PSClient.get_transactions()` | ✅ Yes — per month | CC-account spend for `cc_usage`, `budget_usage`, savings-balance deltas. Filter to `status=posted`. |
| `GET /users/{id}/transaction_accounts` | `PSClient.get_transaction_accounts()` | ✅ Yes — once per sync | Refresh account list (current_balance, name). |
| `GET /users/{id}/categories` | `PSClient.get_categories()` | ✅ Yes — once per sync | Category tree for role filter. |
| `GET /me` | `PSClient.get_me()` | ✅ Yes — once per sync | Bootstrap `user_id`. |

**Zero new PS calls.** Bills derivations reuse the same payloads.

## Real account inventory (verified from live data)

| Partner | Bills accounts | Savings accounts | CC accounts |
|---|---|---|---|
| Fixture A | 1: `A-Check Nordic Bank` | 2: `A-Savings NB`, `A-Saving Bank B` | 3: `A-CC NB`, `A-CC Bank C`, `A-CC Bank B` |
| Fixture B | 1: `B-Check Nordic Bank` | 1: `B-Savings NB` | 1: `B-CC NB` |

Plus 8 excluded accounts (pensions, mortgages, stocks, property, loans) — invisible to F2-BE. Use `account_mappings.json` (NOT `account_owners.json` — that file has a dangling `5245500` reference and isn't written by sync).

## Prior-month data for estimates

Bills derivations for month `m` need neighbouring months' data for:
- `estimated_cc_bill` (previous month's posted CC spend; envelope model
  per [f2-bills-derivations.md](f2-bills-derivations.md) §9 round 6)
- `everyday_budget` (m+1 formula per §8 round 4: `salary(m+1) − bills(m+1)
  − scheduledCcBuys(m+1)`; last sync-window month → null. Needs NEXT
  month's events, not previous)
- Savings projection (sums across future months)

Two strategies:
- **A1.** The existing sync's per-month loop already processes months in order. When deriving bills for month `m`, the previous month's PS payloads (`events_{m-1}.json` + `{m-1}_ps_raw.json`) are **already on disk** (just written in the prior loop iteration). Read from disk — no extra PS call.
- **A2.** If the user syncs a single month with no prior-month cache, fall back to a one-time PS call for just that prior month. Or surface a warning "Prior month not synced — estimates may be incomplete".

**L1 locks A1** (read from disk). A2 is a degraded fallback, decided in L3.

---

# L1 — Capabilities

## In-scope

The sync job (existing + bills extension) must:

1. **Continue to accept `GET /api/sync?start_month=YYYY-MM&end_month=YYYY-MM`** — no new endpoint. The FE's existing Sync button already calls this.

2. **Reuse the existing `_sync_lock`** for concurrency. Only one sync at a time. A second request while one is running returns the current status (existing behavior, [sync_runner.py:24-91](../src/budget_api/routers/sync.py#L24-L91)).

3. **For every month in the range, after writing `events_YYYY-MM.json` and `YYYY-MM_ps_raw.json` (existing steps), also compute the bills derivations and write `bills_dashboard_YYYY-MM.json`.** This is the new step 6 in the per-month loop.

4. **Read prior-month data from disk** for the estimate math. If `events_{m-1}.json` or `{m-1}_ps_raw.json` is missing, surface a warning in that month's snapshot: `"Prior month not synced — estimates may be incomplete"`. Do NOT make an extra PS call. (Degraded mode — the user can re-sync with a wider range.)

5. **Filter transactions to `status=posted` only** for the bills derivations. Pending transactions may be superseded by their posted counterparts — including them would double-count. (The existing `YYYY-MM_ps_raw.json` cache keeps all transactions; the filter happens at derivation time.)

6. **Bucket events by transaction account `type` + local `account_mappings.json` override.** PS `type=bank` covers both checking and savings — local `type: "checking" | "savings"` is the discriminator. Buckets:
   - bills-account events → bills
   - credits-account events → scheduled CC buys
   - savings-account events → savings transfers
   - bills-account income events → salary
   - refunds on bills-account → bills with positive amount
   - `is_transfer=true` categories → excluded
   - `excluded=true` accounts → invisible

7. **Aggregate per partner across multiple accounts of the same type.** Fixture A's 3 CC accounts roll up into one `estimated_cc_bill`; his 2 savings accounts roll up into one `savings_transfer` + `savings_balance`.

8. **Compute the per-partner derived fields** documented in [f2-bills-derivations.md §1-§13](f2-bills-derivations.md) (salary, bills, savings transfer, savings delta, savings balance, est/real CC bill, CC usage, budget usage, net, status). Per-month, per-partner.

9. **Compute the per-event derived flags**: `is_cc_payment` (true on bills-side CC-paydown events), `is_matched` (true on scheduled CC buys that match a real CC transaction by date + amount). Other event types leave these as `null` / `false`.

10. **Write `bills_dashboard_YYYY-MM.json` atomically** (temp file + rename, same as existing `storage.atomic_write_json`) so a killed sync leaves the previous snapshot byte-for-byte unchanged.

11. **Surface a per-month warning list in each `bills_dashboard_*.json`** for fidelity issues:
    - Salary missing for the month (fallback used: prior month's salary)
    - Prior month not synced (estimates incomplete)
    - Unmapped `bank` account (no local `type` override — events on it are invisible until the user maps it)
    - CC account with no `primary_scenario` (rare; should not happen but sync should not crash)

12. **Fail loudly on hard errors.** If no bills/checking account is mapped for a partner, the **existing sync still succeeds** (it writes `events_*.json` etc.) but that month's `bills_dashboard_*.json` is **not written** and a warning is added to the sync status: `"Bills snapshot for 2026-07 skipped: Fixture A has no bills/checking account mapped"`. The user fixes the mapping and re-syncs.

13. **Respect PS rate limits.** If PS returns 429, the existing sync's error handling kicks in — the whole sync transitions to `failed`. No bills-specific retry. (Existing behavior unchanged.)

14. **Extend the existing `.sync_status.json`** with a `bills_snapshots_written` count and a `bills_warnings` list, so the FE can show "12 months synced, 11 bills snapshots written, 1 skipped (no bills account)".

## Out of scope

The sync job must NOT:

1. **Add a new endpoint.** No `POST /api/sync/bills`. The existing `GET /api/sync` is the only entry point.
2. **Retry on 429 automatically.** Existing behavior: fail. User re-syncs.
3. **Write to PS in any way.** Read-only.
4. **Make extra PS calls for prior-month data.** Read from disk; fall back to degraded mode if missing.
5. **Prune or archive old snapshots.** Files overwrite in place. Pruning is a future task.
6. **Push updates to the FE.** Existing polling on `GET /api/sync/status` is enough.
7. **Compute FE presentation sub-derivations.** Capsule sub-widths, savings-box tone, etc. are FE-side per [derivations §17](f2-bills-derivations.md).
8. **Run on a schedule.** No cron. The user clicks the button.
9. **Queue multiple syncs.** Existing `_sync_lock` rejects concurrent syncs.
10. **Write bills snapshots for months outside the requested range.** If the user syncs `2026-07..2026-07`, only `bills_dashboard_2026-07.json` is written.

## Success criteria

| Outcome | Measure |
|---|---|
| User clicks Sync for `2026-01..2026-07` | After sync completes, `bills_dashboard_2026-01.json` through `bills_dashboard_2026-07.json` all exist. |
| Sync duration with bills extension | ≤ 35s for a 7-month range (existing 30s + ~5s derivation overhead). |
| User syncs a single month with no prior-month cache | `bills_dashboard_*.json` is written with `warnings: ["Prior month not synced — estimates may be incomplete"]`. |
| Sync is killed mid-write | Previous `bills_dashboard_*.json` for the month being written is byte-for-byte unchanged (atomic write). |
| PS returns 429 mid-sync | Existing sync transitions to `failed`; any `bills_dashboard_*.json` already written in prior loop iterations survive. |
| Fixture A has 3 CC accounts | `bills_dashboard_*.json`'s `estimated_cc_bill` for Fixture A sums across all 3; `events[]` shows each per-account. |
| A partner has no bills account | That month's `bills_dashboard_*.json` is **not written**; sync status includes `"Bills snapshot for 2026-07 skipped: Fixture A has no bills/checking account mapped"`. Other months' snapshots are unaffected. |
| Sync detects an unmapped bank account | `bills_dashboard_*.json`'s `warnings[]` includes `"Unmapped bank account: <name>"`; events from that account are excluded. |
| Sync completes after a previous failure | Fresh `GET /api/sync` overwrites all `bills_dashboard_*.json` in the range. |
| User polls `GET /api/sync/status` | Response includes `bills_snapshots_written: N` and `bills_warnings: [...]`. |

## L1 assumptions + risks

### Assumptions

- **PS API is reachable** — sync requires the existing PS developer key in `.env`.
- **Account mappings are populated** — `account_mappings.json` has `partner_id` and local `type` for each visible account.
- **Category roles are populated** — `category_roles.json` tags categories with `spend` / `savings` / `income`.
- **Single-user app** — both partners share the same PS API key.
- **Prior-month data on disk** — when the user syncs a range, each month's derivations read the previous month's cache (just written in the prior loop iteration). Single-month sync may have no prior cache → degraded mode.
- **Existing sync's per-month loop is sequential** — months are processed in order, so `events_{m-1}.json` is on disk before we derive bills for month `m`.

### Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Bills derivations slow down the existing sync | Low | Derivations are pure Python math on already-fetched data. Target: <1s per month. |
| Prior-month cache missing for single-month sync | Medium | Degraded mode: write snapshot with warning. User re-syncs with a wider range to fill the gap. |
| PS rate limit during a wide range sync | Medium | Existing behavior: fail loudly. No bills-specific change. |
| `bills_dashboard_*.json` write fails (disk full) | Low | Atomic write — previous snapshot survives. Existing sync's error handling catches `OSError`. |
| Bills derivations throw on unexpected PS payload shape | Medium | Wrap derivation in try/except per month. On failure, skip that month's bills snapshot, add warning to sync status, continue with other months. |
| Existing sync is already long-running; adding bills makes it longer | Low | ~5s overhead for 7 months. Acceptable. |
| User syncs a range that starts at the current month — no prior month for estimates | Medium | Degraded mode warning. User can re-sync with `start_month = current - 1`. |

## L1 checkpoint — 6 questions for you

1. **Is "extend existing sync" the right call?** The big win: one button, no duplicate PS calls. The cost: existing sync gets slower and its error surface grows. Confirm.

2. **Degraded mode for missing prior-month** — write snapshot with warning, or skip that month's bills snapshot entirely?

3. **No-bills-account is a per-month skip, not a whole-sync fail** — confirm? (The existing sync still writes `events_*.json` for that month; just the bills snapshot is skipped.)

4. **Should the sync status (`GET /api/sync/status`) include a per-month bills breakdown** (which months got snapshots, which were skipped), or just aggregate counts?

5. **Should bills derivations run in the same thread/process as the existing sync**, or be a separate background task kicked off after the existing sync finishes?

6. **If the user syncs `2026-07..2026-07` (single month) and there's no `events_2026-06.json` on disk**, should the sync auto-fetch just the prior month (one extra PS call), or stay in degraded mode?

Approve L1, or call out changes.

---

# L2 — Components

## Existing components (reuse-first)

| Component | File | Role in this sub-feature |
|---|---|---|
| **Sync router** | [routers/sync.py](../src/budget_api/routers/sync.py) | No changes. Existing `GET /api/sync` already kicks off `sync_runner.sync_all` via `BackgroundTasks`. |
| **Sync runner** | [services/sync_runner.py](../src/budget_api/services/sync_runner.py) | **Extended.** The per-month loop (line 187-200) gets a new step 6 after `events_*.json` + `*_ps_raw.json` writes: call `bills_builder.build_bills_snapshot(month, events, transactions, ...)`. |
| **PS client** | [services/ps_client.py](../src/budget_api/services/ps_client.py) | No changes. All needed GET methods exist. The auto-fetch-prior-month (Q6 decision) reuses `get_events` + `get_transactions` — already implemented. |
| **Storage** | [services/storage.py](../src/budget_api/services/storage.py) | **Extended.** Add `bills_dashboard_path(month) -> Path` helper + `bills_sync_warnings` accumulator on the status dict. Existing `atomic_write_json` reused as-is. |
| **Sync models** | [models/sync.py](../src/budget_api/models/sync.py) | **Extended.** `RowCounts` gets `bills_snapshots: int = 0`. `SyncStatus` gets `bills_snapshots_written: int = 0` + `bills_warnings: list[str] = []`. |
| **Concurrency lock** | `routers/sync.py:24` `_sync_lock` | No changes. Existing lock covers the extended sync. |
| **Month validation** | `routers/sync.py:21-29` `_valid_month` | No changes. Reused for the auto-fetch-prior-month path. |

## New components

| Component | File (proposed) | Role |
|---|---|---|
| **Bills builder** | `services/bills_builder.py` (new) | Pure-function module. Entry point: `build_bills_snapshot(month, events, transactions, account_mappings, category_roles, prior_events, prior_transactions) -> dict`. Returns the snapshot dict; the sync runner writes it via `storage.atomic_write_json`. No I/O of its own (except reading `account_mappings.json` + `category_roles.json` which the sync runner passes in). |
| **Bills derivations** | `services/bills_derivations.py` (new) | Per-field math functions. One function per derivation: `compute_salary(events, mappings, roles)`, `compute_bills(...)`, `compute_savings_transfer(...)`, `compute_savings_delta(...)`, `compute_savings_balance(...)`, `compute_estimated_cc_bill(...)`, `compute_real_cc_bill(...)`, `compute_cc_usage(...)`, `compute_budget_usage(...)`, `compute_net(...)`, `compute_status(...)`. Called by `bills_builder`. Pure functions — no I/O. |
| **Bills event classifier** | `services/bills_classifier.py` (new) | Bucketing logic. `classify_event(event, account_mappings, category_roles) -> Bucket` where `Bucket = "bill" \| "buy" \| "savings" \| "salary" \| "excluded"`. Also `is_cc_payment(event, cc_payment_category_id) -> bool` and `match_scheduled_buys(events, transactions) -> events_with_is_matched`. Called by `bills_builder`. |
| **Bills models** | `models/bills.py` (new) | Pydantic models for the snapshot: `BillsSnapshot`, `PartnerBills`, `BillsEvent`, `BillsWarning`. Used for validation before atomic write. |
| **Prior-month auto-fetch** | `services/bills_builder.py` (new) | Helper `ensure_prior_month(client, user_id, month, warnings) -> (prior_events, prior_transactions)`. Checks if `events_{m-1}.json` + `{m-1}_ps_raw.json` exist on disk; if not, calls `client.get_events` + `client.get_transactions` for just that month, writes cache files via `storage.atomic_write_json`, appends warning to shared `warnings` list. Takes `client` + `user_id` as params (impure — does I/O — but colocated with the builder for cohesion). |

## Component boundaries

```
GET /api/sync
  │
  ▼
routers/sync.py (existing, no change)
  │ BackgroundTasks.add_task(sync_runner.sync_all, start, end)
  ▼
sync_runner.sync_all(start, end)  (extended)
  │
  ├── for each month in range:
  │   ├── client.get_transactions → write {month}_ps_raw.json  (existing)
  │   ├── client.get_events → write events_{month}.json  (existing)
  │   ├── _ensure_prior_month(client, user_id, month)  (NEW)
  │   │   └── if prior cache missing: fetch + write + warn
  │   └── bills_builder.build_bills_snapshot(month, events, txns, ...)  (NEW)
  │       ├── bills_classifier.classify_event(...)  (NEW)
  │       ├── bills_derivations.compute_salary(...)  (NEW)
  │       ├── bills_derivations.compute_bills(...)  (NEW)
  │       ├── ... (all per-partner + per-event derivations)
  │       └── returns snapshot dict
  │       └── storage.atomic_write_json(bills_dashboard_path(month), snapshot)
  │
  ├── client.get_budget → budget_snapshot.json  (existing)
  ├── client.get_categories → category_catalog.json  (existing)
  ├── client.get_transaction_accounts → account_catalog.json  (existing)
  └── merge into account_mappings.json  (existing)
  │
  └── write .sync_status.json with bills_snapshots_written + bills_warnings  (extended)
```

## Reuse-first rationale

| New component | Why not reuse existing? |
|---|---|
| `bills_builder.py` | No existing "derive + write snapshot" module. `sync_runner` is the orchestrator, not a derivation engine. Separation keeps `sync_runner` from growing to 500 lines. |
| `bills_derivations.py` | No existing math module for bills fields. The existing `report_builder.py` + `mega_builder.py` are for PDF reports, not dashboard snapshots. Different output shape. |
| `bills_classifier.py` | No existing bucketing logic. The existing report code at [src/mom/data.py](../src/mom/data.py) uses category roles but doesn't bucket by account type. New logic. |
| `models/bills.py` | No existing Pydantic models for `FinanceEvent` / `PartnerEconomy` / `MonthData`. The FE has TypeScript types; the BE needs its own. |
| `_ensure_prior_month` | Lives inside `sync_runner.py` because it needs the `client` + `user_id` which the sync runner already has. No separate module. |

## What does NOT become a new component

| Considered | Rejected because |
|---|---|
| Separate `bills_sync_runner.py` | Q5 decision: same thread/process. The bills extension is just a new step in the existing loop, not a separate job. |
| New router `routers/bills_sync.py` | Q1 decision: no new endpoint. The existing `routers/sync.py` handles everything. |
| New status file `bills_sync_status.json` | Reuse `.sync_status.json` with extended fields. |
| `bills_storage.py` | `storage.py` already has `atomic_write_json` + `read_json`. Just add `bills_dashboard_path(month)`. |

## L2 checkpoint — 5 questions

1. **Is `bills_derivations.py` the right split from `bills_builder.py`?** Alternative: one module `bills_builder.py` with everything. Pro of split: derivations are pure functions, testable in isolation. Con: more files.

2. **Should `bills_classifier.py` be a separate module or just functions inside `bills_builder.py`?** The classifier is ~50 lines. Might not warrant its own file.

3. **Should `models/bills.py` validate the snapshot before write, or is the dict good enough?** Pro: catches shape errors early. Con: adds a Pydantic dependency to the sync path.

4. **`_ensure_prior_month` inside `sync_runner.py`** — or a helper in `bills_builder.py`? The sync runner owns the `client`; the builder is pure-function.

5. **Should the bills snapshot path helper live in `storage.py`** (alongside `monthly_ps_raw_path`, `monthly_report_path`), or in a new `bills_storage.py`?

Answer these, then I move to L3 (Interactions).

---

# L3 — Interactions

## Primary flow: sync with bills extension

```
User clicks Sync (FE)
  │
  ▼
GET /api/sync?start_month=2026-01&end_month=2026-07
  │
  ▼
routers/sync.py: _sync_lock acquired
  ├── read .sync_status.json → if "running" → return current status (202)
  ├── check API key configured → if not → 500
  └── BackgroundTasks.add_task(sync_runner.sync_all, "2026-01", "2026-07")
      │
      ▼ (lock released; bg task runs)
sync_runner.sync_all("2026-01", "2026-07")
  │
  ├── write .sync_status.json: {status: "running", ...}
  │
  ├── api_key = _read_api_key()
  ├── client = PSClient(api_key)
  ├── user = client.get_me()
  ├── user_id = str(user["id"])
  │
  ├── for month in ["2026-01", ..., "2026-07"]:
  │   │
  │   ├── EXISTING: client.get_transactions(user_id, start, end)
  │   │   └── storage.atomic_write_json({month}_ps_raw.json, transactions)
  │   │
  │   ├── EXISTING: client.get_events(user_id, start, end)
  │   │   └── storage.atomic_write_json(events_{month}.json, events)
  │   │
  │   ├── NEW: bills_builder.ensure_prior_month(client, user_id, month, warnings)
  │   │   ├── prior = month - 1
  │   │   ├── if events_{prior}.json exists AND {prior}_ps_raw.json exists:
  │   │   │   └── pass (no-op)
  │   │   ├── else:
  │   │   │   ├── client.get_events(user_id, prior_start, prior_end)
  │   │   │   ├── client.get_transactions(user_id, prior_start, prior_end)
  │   │   │   ├── storage.atomic_write_json(events_{prior}.json, ...)
  │   │   │   ├── storage.atomic_write_json({prior}_ps_raw.json, ...)
  │   │   │   └── warnings.append(f"Prior month {prior} auto-fetched during sync")
  │   │   └── return (prior_events, prior_transactions)
  │   │
  │   ├── NEW: snapshot = bills_builder.build_bills_snapshot(
  │   │     month, events, transactions,
  │   │     account_mappings, category_roles,
  │   │     prior_events, prior_transactions,
  │   │     warnings
  │   │   )
  │   │   │
  │   │   ├── bills_classifier.classify_event(e, mappings, roles) for each e
  │   │   ├── bills_classifier.is_cc_payment(e, cc_cat_id) for bills-account txns
  │   │   ├── bills_classifier.match_scheduled_buys(events, transactions)
  │   │   ├── bills_derivations.compute_salary(classified_events, partner)
  │   │   ├── bills_derivations.compute_bills(classified_events, partner)
  │   │   ├── bills_derivations.compute_savings_transfer(...)
  │   │   ├── bills_derivations.compute_savings_delta(...)
  │   │   ├── bills_derivations.compute_savings_balance(...)
  │   │   ├── bills_derivations.compute_estimated_cc_bill(...)
  │   │   ├── bills_derivations.compute_real_cc_bill(...)
  │   │   ├── bills_derivations.compute_cc_usage(...)
  │   │   ├── bills_derivations.compute_budget_usage(...)
  │   │   ├── bills_derivations.compute_net(...)
  │   │   ├── bills_derivations.compute_status(...)
  │   │   └── models/bills.py: BillsSnapshot.model_validate(snapshot_dict)
  │   │
  │   ├── NEW: storage.atomic_write_json(bills_dashboard_path(month), snapshot)
  │   └── bills_snapshots_written += 1
  │
  ├── EXISTING: client.get_budget → budget_snapshot.json
  ├── EXISTING: client.get_categories → category_catalog.json
  ├── EXISTING: client.get_transaction_accounts → account_catalog.json
  ├── EXISTING: _merge_accounts_into_mappings → account_mappings.json
  │
  └── write .sync_status.json: {
      status: "success" | "failed",
      bills_snapshots_written: N,
      bills_warnings: [...],
      ...
    }
```

## Failure + retry behavior

| Failure point | What happens | Retry |
|---|---|---|
| **PS 429 (rate limited)** during any `client.get_*` | `PSClientError("PS API rate limited")` raised. Sync runner catches it, writes `.sync_status.json` with `status: "failed"`. Any `bills_dashboard_*.json` already written in prior loop iterations survive. | User clicks Sync again. |
| **PS timeout (30s)** | Same as 429 — `PSClientError("PS API timeout")`. | User clicks Sync again. |
| **No bills account for a partner** | `bills_builder.build_bills_snapshot` raises `NoBillsAccountError(partner)`. Sync runner catches it per-month, appends `f"Bills snapshot for {month} skipped: {partner} has no bills/checking account mapped"` to `bills_warnings`. That month's `bills_dashboard_*.json` is **not written**. Other months continue. | User maps the account in Settings, clicks Sync again. |
| **Bills derivation throws** (unexpected PS payload shape) | Sync runner catches per-month via try/except around `build_bills_snapshot`. Appends `f"Bills snapshot for {month} failed: {error}"` to `bills_warnings`. That month skipped. Other months continue. | User clicks Sync again (may need to report the error). |
| **Atomic write fails** (disk full / permissions) | `OSError` raised. Sync runner's existing `except (PSClientError, ValueError, OSError)` catches it. Whole sync transitions to `failed`. | User fixes disk, clicks Sync again. |
| **Pydantic validation fails** (snapshot shape wrong) | `ValidationError` raised inside `build_bills_snapshot` before the atomic write. Sync runner catches per-month. Snapshot not written. Warning appended. | Developer fixes the model; user re-syncs. |
| **Prior-month auto-fetch fails** (429 or timeout) | `PSClientError` raised inside `ensure_prior_month`. Sync runner catches per-month. That month's bills snapshot is skipped with warning `f"Bills snapshot for {month} skipped: prior month fetch failed: {error}"`. Other months continue. | User clicks Sync again. |

## Observability touchpoints

| Touchpoint | Where | What |
|---|---|---|
| **`.sync_status.json`** | `data/private/.sync_status.json` | Existing. Extended with `bills_snapshots_written` + `bills_warnings`. FE reads via `GET /api/sync/status`. |
| **Per-snapshot `warnings[]`** | Inside each `bills_dashboard_YYYY-MM.json` | Per-month fidelity warnings (missing salary, unmapped bank account, prior-month auto-fetched, etc.). FE reads via `GET /api/bills/dashboard`. |
| **`stderr` traceback** | `sync_runner.py` existing `print(traceback.format_exc(), file=sys.stderr)` | Unexpected exceptions during bills derivations print to stderr (same pattern as existing sync). |
| **`source_counts` in snapshot** | Inside each `bills_dashboard_*.json` | `ps_events_fetched`, `ps_transactions_fetched`, `events_kept_after_filter`. Debug aid for "why is this number wrong?" |
| **No new logging framework** | — | Existing `print()` to stderr is the only log channel. No structured logging, no metrics. Matches existing codebase. |

## Data flow: what the builder reads vs writes

### Reads (inputs to `build_bills_snapshot`)

| Input | Source | Passed by |
|---|---|---|
| `events` | `client.get_events()` result (already in memory) | sync_runner |
| `transactions` | `client.get_transactions()` result (already in memory) | sync_runner |
| `account_mappings` | `storage.read_json(ACCOUNT_MAPPING_PATH)` | sync_runner |
| `category_roles` | `storage.read_json(CATEGORY_ROLES_PATH)` | sync_runner |
| `prior_events` | `storage.read_json(events_{m-1}.json)` or auto-fetched | `ensure_prior_month` |
| `prior_transactions` | `storage.read_json({m-1}_ps_raw.json)` or auto-fetched | `ensure_prior_month` |
| `warnings` | mutable list | sync_runner (shared across months) |

### Writes (outputs)

| Output | Destination | How |
|---|---|---|
| `bills_dashboard_YYYY-MM.json` | `storage.bills_dashboard_path(month)` | `storage.atomic_write_json` (temp + rename) |
| Prior-month cache (if auto-fetched) | `events_{m-1}.json` + `{m-1}_ps_raw.json` | `storage.atomic_write_json` |
| `bills_warnings` entries | appended to shared `warnings` list | sync_runner writes to `.sync_status.json` at end |

### Does NOT write

- `account_mappings.json` (existing sync step handles this)
- `category_catalog.json` (existing sync step)
- `account_catalog.json` (existing sync step)
- Anything to PS

## L3 checkpoint — 5 questions

1. **Per-month try/except around `build_bills_snapshot`** — should a bills-derivation failure for one month abort the whole sync, or just skip that month? L3 says skip (append warning, continue). Confirm.

2. **`ensure_prior_month` in `bills_builder.py`** — it needs the `client` + `user_id`. The builder is supposed to be pure-function (no I/O). Passing the `client` as a parameter breaks purity. Two options:
   - **3a.** `ensure_prior_month` lives in `bills_builder.py` but takes `client` + `user_id` as params (impure but colocated).
   - **3b.** `ensure_prior_month` lives in `sync_runner.py` (which already has the client) and passes prior_events + prior_transactions to the builder as plain dicts (builder stays pure).

3. **`warnings` list** — should it be per-month (each snapshot has its own `warnings[]`) or per-sync (one global list in `.sync_status.json`)? L3 has both. Is that right?

4. **`source_counts` in the snapshot** — useful debug aid, or noise? Keep or drop?

5. **No structured logging** — the existing codebase uses `print()` to stderr. Should bills derivations add anything beyond that (e.g. a per-month log line `"Bills snapshot for 2026-07: 18 events, 2 partners, 1 warning"`)?

Answer these, then I move to L4 (Contracts).

---

# L4 — Contracts

## Extended: `GET /api/sync` (existing, no new endpoint)

No changes to the request/response shape. The existing `GET /api/sync?start_month=YYYY-MM&end_month=YYYY-MM` already returns `SyncStatus` (202). The bills extension runs inside the existing background task.

## Extended: `GET /api/sync/status` (existing)

Response shape extended with bills fields. **Backward-compatible** — new fields default to 0 / empty.

```json
{
  "status": "running | success | failed",
  "last_sync": "2026-08-02T12:00:00Z",
  "start_month": "2026-01",
  "end_month": "2026-07",
  "months_synced": 7,
  "row_counts": {
    "transactions": 154,
    "events": 142,
    "budget": 1,
    "categories": 62,
    "accounts": 17,
    "bills_snapshots": 7
  },
  "errors": [],
  "duration_ms": 32000,
  "bills_snapshots_written": 7,
  "bills_warnings": []
}
```

New fields:
- `row_counts.bills_snapshots: int = 0` — count of `bills_dashboard_*.json` files written this sync.
- `bills_snapshots_written: int = 0` — same number at top level (FE convenience).
- `bills_warnings: list[str] = []` — aggregate warnings across all months (e.g. `"Bills snapshot for 2026-07 skipped: Fixture A has no bills/checking account mapped"`, `"Prior month 2026-06 auto-fetched during sync"`).

## New: `bills_dashboard_YYYY-MM.json` snapshot shape

Written by the sync runner to `data/private/bills_dashboard_YYYY-MM.json`. Read by sub-feature 2 (dashboard).

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

### Field invariants

| Field | Type | Invariant |
|---|---|---|
| `schema_version` | `int` | Always `1` for v1. |
| `month` | `string` | `YYYY-MM` format. Matches the request month. |
| `is_past` / `is_current` / `is_future` | `bool` | Exactly one is `true`. Computed from `month` vs current calendar month. |
| `bills_count` | `int` | ≥ 0. Count of `type=bill` events across both partners. |
| `buys_count` | `int` | ≥ 0. Count of `type=buy` events across both partners. |
| `warnings` | `string[]` | May be empty. Each string is a human-readable fidelity issue. |
| `partners` | `array` | Exactly 2 entries (Fixture A + Fixture B). Each has the fields below. |
| `partner.salary` | `number` | ≥ 0. Sum of income events on bills account. |
| `partner.bills` | `number` | ≥ 0. Sum of spend events on bills account (absolute value). |
| `partner.estimated_cc_bill` | `number \| null` | Populated for current + future months. `null` for past months. |
| `partner.real_cc_bill` | `number \| null` | Populated for past months. `null` for current + future. |
| `partner.net` | `number` | `salary − bills − (estimated_cc_bill ?? real_cc_bill)`. |
| `partner.status` | `"covered" \| "partial" \| "shortfall"` | Computed per derivations §15. |
| `events[].is_cc_payment` | `bool` | `true` only on bills-account CC-paydown transactions. `false` otherwise. |
| `events[].is_matched` | `bool \| null` | `true` on matched CC buys. `null` on non-buy events. `false` on unmatched buys. |
| `source_counts.ps_events_fetched` | `int` | Count of raw PS events fetched for this month (before filtering). |
| `source_counts.events_kept_after_filter` | `int` | Count of events after bucketing + exclusion. ≤ `ps_events_fetched`. |

## New: Pydantic models (`models/bills.py`)

```python
from pydantic import BaseModel
from typing import Literal

class BillsEvent(BaseModel):
    id: str
    date: str  # YYYY-MM-DD
    day: int  # 1-31
    title: str
    type: Literal["bill", "buy"]
    category: str
    partner: str
    amount: float
    is_cc_payment: bool = False
    is_matched: bool | None = None

class PartnerBills(BaseModel):
    partner: str
    salary: float
    bills: float
    everyday_budget: float
    savings_transfer: float
    savings_delta: float
    savings_balance: float
    estimated_cc_bill: float | None
    real_cc_bill: float | None
    cc_usage: float
    budget_usage: float
    net: float
    status: Literal["covered", "partial", "shortfall"]
    events: list[BillsEvent]

class SourceCounts(BaseModel):
    ps_events_fetched: int
    ps_transactions_fetched: int
    events_kept_after_filter: int

class BillsSnapshot(BaseModel):
    schema_version: int = 1
    month: str
    month_label: str
    is_past: bool
    is_current: bool
    is_future: bool
    synced_at: str
    bills_count: int
    buys_count: int
    warnings: list[str]
    partners: list[PartnerBills]
    source_counts: SourceCounts
```

## New: Python function signatures

### `services/bills_builder.py`

```python
def build_bills_snapshot(
    month: str,                          # "2026-07"
    events: list[dict],                   # raw PS events for this month
    transactions: list[dict],             # raw PS transactions for this month
    account_mappings: dict,              # account_mappings.json content
    category_roles: dict,                # category_roles.json content
    prior_events: list[dict] | None,     # raw PS events for month-1 (or None)
    prior_transactions: list[dict] | None,
    warnings: list[str],                 # mutable; appended to
) -> dict:
    """Returns the snapshot dict. Raises NoBillsAccountError on hard failure."""

def ensure_prior_month(
    client: PSClient,
    user_id: str,
    month: str,
    warnings: list[str],
) -> tuple[list[dict], list[dict]]:
    """Returns (prior_events, prior_transactions). Reads from disk if cache
    exists; auto-fetches from PS if not. Appends warning if auto-fetched."""
```

### `services/bills_classifier.py`

```python
Bucket = Literal["bill", "buy", "savings", "salary", "excluded"]

def classify_event(
    event: dict,
    account_mappings: dict,
    category_roles: dict,
) -> Bucket: ...

def is_cc_payment(
    event: dict,
    cc_payment_category_id: int,
) -> bool: ...

def match_scheduled_buys(
    events: list[dict],          # all events (will mutate is_matched on buys)
    transactions: list[dict],     # posted CC transactions
) -> list[dict]: ...             # returns events with is_matched populated
```

### `services/bills_derivations.py`

```python
def compute_salary(classified_events: list[dict], partner: str) -> float: ...
def compute_bills(classified_events: list[dict], partner: str) -> float: ...
def compute_savings_transfer(
    scheduled_savings: float,
    bills_account_balance_delta: float,
    salary: float,
    bills: float,
) -> float: ...
def compute_savings_delta(savings_transfer: float, scheduled_savings: float) -> float: ...
def compute_savings_balance(
    partner: str,
    month: str,
    account_mappings: dict,
    account_catalog: dict,
    is_current: bool,
    is_future: bool,
    savings_transfer: float = 0,
    salary: float = 0,
    bills: float = 0,
    estimated_cc_bill: float = 0,
    prev_savings_balance: float = 0,
) -> float:
    """Current month: savings_account.current_balance + bills_account.current_balance.
    Future month m: prev_savings_balance + savings_transfer(m) + (salary(m) - bills(m) - estimated_cc_bill(m)).
    Past month: TBD (rework during L2 of savings-projection sub-feature)."""
def compute_estimated_cc_bill(
    partner: str,
    prior_transactions: list[dict],
    events: list[dict],
    account_mappings: dict,
) -> float: ...
def compute_real_cc_bill(
    partner: str,
    transactions: list[dict],
    account_mappings: dict,
    cc_payment_category_id: int,
) -> float: ...
def compute_cc_usage(
    partner: str,
    transactions: list[dict],
    account_mappings: dict,
) -> float: ...
def compute_budget_usage(
    partner: str,
    transactions: list[dict],
    account_mappings: dict,
) -> float: ...
def compute_net(
    salary: float,
    bills: float,
    estimated_cc_bill: float | None,
    real_cc_bill: float | None,
) -> float: ...
def compute_status(
    salary: float,
    bills: float,
    estimated_cc_bill: float | None,
    real_cc_bill: float | None,
    savings_balance: float,
) -> Literal["covered", "partial", "shortfall"]: ...
```

### `services/storage.py` (extended)

```python
def bills_dashboard_path(month: str) -> Path:
    """bills_dashboard_YYYY-MM.json — per-month bills snapshot."""
    return PRIVATE_DATA_DIR / f"bills_dashboard_{month}.json"
```

## New: error model

Errors split into two categories: **warnings** (user-fixable, per-month skip, sync continues) and **500 errors** (BE bugs, whole sync fails).

### Warnings (per-month skip, sync continues)

| Error | Raised by | Behavior | Message shape |
|---|---|---|---|
| `NoBillsAccountError(partner)` | `bills_builder.build_bills_snapshot` | That month's `bills_dashboard_*.json` not written. Warning appended to `bills_warnings`. Other months continue. | `f"Bills snapshot for {month} skipped: {partner} has no bills/checking account mapped"` |
| Prior-month fetch failure | `bills_builder.ensure_prior_month` | That month's bills snapshot skipped. Warning appended. Other months continue. | `f"Bills snapshot for {month} skipped: prior month fetch failed: {error}"` |

### 500 errors (whole sync fails, `.sync_status.json` → `status: "failed"`)

| Error | Raised by | Behavior |
|---|---|---|
| `ValidationError` (Pydantic) | `BillsSnapshot.model_validate` | Unexpected snapshot shape — BE bug. Whole sync fails. `print(traceback.format_exc(), file=sys.stderr)`. |
| Unexpected `Exception` in derivation math | `bills_derivations.compute_*` | BE bug. Whole sync fails. `print(traceback.format_exc(), file=sys.stderr)`. |
| `PSClientError` (429/timeout) | `PSClient.get_*` | Existing behavior — whole sync fails. No bills-specific change. |
| `OSError` (disk write failure) | `storage.atomic_write_json` | Existing behavior — whole sync fails. |

### Rule

- **User-fixable** (no bills account, prior month missing) → **warning**, per-month skip, sync continues.
- **BE bug** (validation error, crash in derivation math) → **500**, whole sync fails, stderr traceback.

## Backward-compatibility

- Existing `GET /api/sync` and `GET /api/sync/status` consumers see new fields (`bills_snapshots_written`, `bills_warnings`, `row_counts.bills_snapshots`) but defaults are 0 / empty. **No FE breakage** if FE ignores unknown fields.
- Existing `events_*.json` + `*_ps_raw.json` files are still written in the same format. Bills extension is additive.
- `account_mappings.json` + `category_catalog.json` unchanged.

## L4 checkpoint — 4 questions

1. **`BillsSnapshot` Pydantic model** — should it be the **source of truth** (builder constructs the model, then `.model_dump()` for JSON write), or should the builder construct a plain dict and the model is only for validation? Pro of model-as-source: type safety throughout. Con: Pydantic overhead in the sync path.

2. **`is_matched` mutation vs return** — `match_scheduled_buys` currently mutates the events list in place. Should it return a new list instead (pure function) or mutate (simpler)?

3. **`compute_savings_balance` signature** — it takes `prior_events` + `prior_transactions` for the projection math. Should it also take the `current_month` + a `projection_window` param, or is that hardcoded to 12 months inside the function?

4. **Error model** — all bills errors are caught per-month and appended to warnings. Should any of them also be **logged to stderr** (existing `print(traceback.format_exc())` pattern), or just silently appended to warnings?

Answer these, then I move to L5 (Implementation Plan).

---

# L5 — Implementation Plan

## Ordered task list

| # | Task | Depends on | Files | Risk |
|---|---|---|---|---|
| 1 | **Add `bills_dashboard_path(month)` to `storage.py`** | — | `src/budget_api/services/storage.py` | Low — one-liner. |
| 2 | **Extend `models/sync.py`** with `bills_snapshots` on `RowCounts` + `bills_snapshots_written` + `bills_warnings` on `SyncStatus` | — | `src/budget_api/models/sync.py` | Low — additive fields with defaults. |
| 3 | **Create `models/bills.py`** — Pydantic models (`BillsSnapshot`, `PartnerBills`, `BillsEvent`, `SourceCounts`) | — | `src/budget_api/models/bills.py` (new) | Low — type definitions only. |
| 4 | **Create `services/bills_classifier.py`** — `classify_event`, `is_cc_payment`, `match_scheduled_buys` | — | `src/budget_api/services/bills_classifier.py` (new) | Medium — bucketing logic is the core. |
| 5 | **Create `services/bills_derivations.py`** — all `compute_*` functions | 4 (uses classifier) | `src/budget_api/services/bills_derivations.py` (new) | Medium — math per derivations doc. |
| 6 | **Create `services/bills_builder.py`** — `build_bills_snapshot` + `ensure_prior_month` | 3, 4, 5 | `src/budget_api/services/bills_builder.py` (new) | Medium — orchestrates everything. |
| 7 | **Extend `sync_runner.py`** — add bills step to per-month loop + wire `_ensure_prior_month` + write `bills_snapshots_written` to status | 1, 2, 6 | `src/budget_api/services/sync_runner.py` | Medium — touches existing code. Rollback: guard with feature flag. |
| 8 | **Unit tests: classifier** | 4 | `src/budget_api/tests/bills/test_classifier.py` (new) | Low. |
| 9 | **Unit tests: derivations** | 5 | `src/budget_api/tests/bills/test_derivations.py` (new) | Low. |
| 10 | **Unit tests: builder** | 6 | `src/budget_api/tests/bills/test_builder.py` (new) | Low. |
| 11 | **Integration tests: sync extension** | 7 | `src/budget_api/tests/bills/test_sync_extension.py` (new) | Medium — mocks PS client, asserts snapshot written. |
| 12 | **Integration tests: prior-month auto-fetch** | 7 | `src/budget_api/tests/bills/test_prior_month.py` (new) | Medium. |
| 13 | **Integration tests: error handling** | 7 | `src/budget_api/tests/bills/test_errors.py` (new) | Medium — no-bills-account warning + validation-error 500. |
| 14 | **Conftest fixtures for bills tests** | — | `src/budget_api/tests/bills/conftest.py` (new) | Low — sample PS events, transactions, mappings. |

## Risk controls

| Risk | Control |
|---|---|
| Existing sync breaks | Guard the bills step with a feature flag (`BILLS_SYNC_ENABLED=true`). If false, sync runs as before. |
| Bills derivation is slow | Wrap in `time.monotonic()`. If > 5s per month, log warning to stderr. |
| Pydantic validation rejects valid PS data | Start with `model_dump(skip_validation=True)` during dev; tighten to full validation after first integration test passes. |
| `ensure_prior_month` triggers unexpected PS rate limit | Only auto-fetches one month. If PS returns 429, caught as warning, month skipped. |
| Sync runner grows too large | Keep `sync_runner.py` thin — delegate to `bills_builder`. The runner just calls `build_bills_snapshot` + `ensure_prior_month` + `atomic_write_json`. |

## Rollback strategy

1. **Feature flag**: `BILLS_SYNC_ENABLED=false` → sync runs existing steps only, no bills snapshots. Existing outputs unaffected.
2. **Per-month try/except**: bills step is wrapped. If it throws (non-500), that month's snapshot is skipped, sync continues.
3. **Atomic write**: `bills_dashboard_*.json` write is temp + rename. Previous snapshot survives any failure.
4. **Git revert**: if the whole extension is broken, revert the `sync_runner.py` changes. The new files (`bills_builder.py`, `bills_derivations.py`, `bills_classifier.py`, `models/bills.py`) are unused — harmless dead code.

## Test plan

### Unit tests (pure functions, no I/O)

**`test_classifier.py`** (task 8):
- `test_classify_bill_on_checking_account`
- `test_classify_buy_on_credits_account`
- `test_classify_savings_on_savings_account`
- `test_classify_salary_income_on_checking`
- `test_classify_excluded_on_excluded_account`
- `test_classify_excluded_on_transfer_category`
- `test_classify_excluded_on_unmapped_bank_account`
- `test_is_cc_payment_true_on_matching_category`
- `test_is_cc_payment_false_on_other_category`
- `test_match_scheduled_buys_finds_match_by_date_amount`
- `test_match_scheduled_buys_no_match_returns_false`
- `test_match_scheduled_buys_does_not_mutate_non_buy_events`

**`test_derivations.py`** (task 9):
- `test_compute_salary_sums_income_events`
- `test_compute_salary_falls_back_to_prior_month`
- `test_compute_bills_sums_spend_events`
- `test_compute_savings_transfer_signed`
- `test_compute_savings_delta_zero_when_aligned`
- `test_compute_savings_delta_positive_when_oversaved`
- `test_compute_savings_delta_negative_when_undersaved`
- `test_compute_savings_balance_current_includes_bills_balance`
- `test_compute_savings_balance_future_projection`
- `test_compute_estimated_cc_bill_from_prior_month`
- `test_compute_real_cc_bill_from_cc_payment_events`
- `test_compute_cc_usage_current_month_only`
- `test_compute_budget_usage_excludes_cc_and_savings`
- `test_compute_net_current_month`
- `test_compute_net_past_month_uses_real_cc_bill`
- `test_compute_status_covered`
- `test_compute_status_partial`
- `test_compute_status_shortfall`

**`test_builder.py`** (task 10):
- `test_build_bills_snapshot_returns_valid_dict`
- `test_build_bills_snapshot_validates_with_pydantic`
- `test_build_bills_snapshot_raises_no_bills_account_error`
- `test_build_bills_snapshot_aggregates_multiple_cc_accounts`
- `test_build_bills_snapshot_aggregates_multiple_savings_accounts`
- `test_build_bills_snapshot_includes_warnings`
- `test_ensure_prior_month_reads_from_disk_if_exists`
- `test_ensure_prior_month_auto_fetches_if_missing`
- `test_ensure_prior_month_appends_warning_on_auto_fetch`

### Integration tests (mocked PS client, real storage)

**`test_sync_extension.py`** (task 11):
- `test_sync_writes_bills_dashboard_for_each_month`
- `test_sync_status_includes_bills_snapshots_written`
- `test_sync_status_includes_bills_warnings`
- `test_sync_atomic_write_survives_kill`

**`test_prior_month.py`** (task 12):
- `test_sync_auto_fetches_prior_month_when_missing`
- `test_sync_skips_bills_when_prior_fetch_fails`

**`test_errors.py`** (task 13):
- `test_no_bills_account_appends_warning_sync_continues`
- `test_validation_error_fails_whole_sync`
- `test_ps_429_fails_whole_sync`

## Incremental delivery slices

| Slice | What ships | Reviewable checkpoint |
|---|---|---|
| **Slice 1** | Tasks 1-3 (storage path + models + Pydantic) | Dead code — no behavior change. PR reviewable alone. |
| **Slice 2** | Tasks 4-5 + 8-9 (classifier + derivations + unit tests) | Pure functions with tests. No sync integration. PR reviewable alone. |
| **Slice 3** | Task 6 + 10 (builder + unit tests) | `build_bills_snapshot` works in isolation. PR reviewable alone. |
| **Slice 4** | Task 7 + 11-14 (sync extension + integration tests + conftest) | End-to-end sync writes snapshots. Feature flag off by default. PR reviewable alone. |
| **Slice 5** | Enable feature flag + FE wiring | Dashboard reads real snapshots. Full E2E. |

Each slice is independently reviewable and revertable.

## L5 checkpoint — final approval

1. **Are the 5 slices the right granularity?** Too coarse / too fine?
2. **Feature flag `BILLS_SYNC_ENABLED`** — good idea, or just ship it on?
3. **14 test files** — too many? Or right coverage?
4. **Is the rollback strategy sufficient?** (feature flag + per-month try/except + atomic write + git revert)
5. **Approve implementation now?**