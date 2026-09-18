# F2 — Savings Balance Anchor (live combined, back-walk past)

Status: DRAFT — review fixes applied 2026-08-04 (pending re-review)
Date: 2026-08-04
Repo: Pocket-Smith-Reports
Parent: [design-f2-bills.md](design-f2-bills.md)
Sub-area: BE builder + derivations for `savings_balance` across past/current/future.
Predecessor: [design-f2-savings-box-c.md](design-f2-savings-box-c.md) (FE savings box, shipped)
Predecessor: L3 amendment 2026-08-04 (savings math — past cash flow, current CC, future lag model, commit `6243518`)

## Summary

Anchor the savings chain on the **current month's live combined balance** (read
from `account_catalog.json`). Current month = live figure. Past months =
back-calculated by subtracting the per-month `savings_delta` from the anchor,
working backwards month-by-month. Future months stay on the lag chain
(`prior_balance + prior_delta`).

Single source of truth (live combined), one direction for past (subtract
deltas backwards from anchor), one direction for future (lag forward).
Current month matches what the bank shows.

## Decisions (from user, 2026-08-04)

- **Current month** = live `current_balance` sum of the partner's mapped bills
  + savings accounts. No lag, no estimate.
- **Past months** = back-walk from the current-month live figure using
  `savings_delta` collected in the same sync pass. No
  `_account_end_balance_from_raw` walk — the live anchor is authoritative.
- **Future months** = lag model (`prior_balance + prior_delta`), unchanged.
- **Sign convention**: `savings_balance[m+1] = savings_balance[m] + savings_delta[m]`
  for the same partner. Back-walk: `savings_balance[m] = savings_balance[m+1] - savings_delta[m]`.
- **`savings_delta` formula** unchanged across all month kinds.
- **No schema bump.** Field shape unchanged.
- **Re-sync on disk** for all past months after the change so the new chain
  is reflected in cached snapshots.
- **Missing live data** → fall back to lag model + warning. Never silent zero.
- **Stale `current_balance_date`** (>30 days): include anyway. Live figure is
  source of truth; if bank feed is stale, user wants to see it. R9 (freshness
  filter) deferred — flag during grill-me if user objects.
- **Re-sync scope** = every past month with a saved snapshot in
  `data/private/bills_dashboard_*.json`, atomically rebuilt in one sync run.
  Confirmed via `_load_later_months_txns` path: 2025-08 → 2026-07 inclusive.

## L1 — Capabilities

### In scope

- Read live `current_balance` per partner for bills + savings accounts.
- Anchor current-month `savings_balance` on the live sum.
- Back-walk past months from the anchor using per-month `savings_delta`.
- Re-sync all past-month snapshots on disk in one sync run.
- Warn (don't fail) when live balance unavailable for a partner.

### Out of scope

- Forward-walk for future months (lag stays).
- Real-time refresh of the live catalog mid-sync (still sync-time read).
- UI changes — `savingsBalanceLabel` already reads `savings_balance` 1:1.
- `savings_transfer` field — UI compat, unchanged.
- `savings_delta` formula — unchanged.
- Schema version bump — fields preserved.

### Success criteria

- 2026-08 dashboard `savings_balance`: Fixture A = 13,917.02, Fixture B = 50,679.76
  (live combined, matches `account_catalog.json`). **Verify before lock** — the
  catalog file updates as PS data feeds refresh; the expected values will
  drift if a feed refreshes between this doc and implementation.
- 2026-07 `savings_balance`: `live − delta[2026-07]` = live − 8920.61 (Fixture A),
  live − (-726.89) (Fixture B). Re-synced on disk.
- 2026-06: walk one more step: 2026-07 balance − delta[2026-06]. Same pattern
  for every past month down to 2025-08.
- Future months (2026-09+) unchanged (lag model still applies).
- All 177+ existing bills tests still pass with updated fixtures.
- 4 new tests cover anchor + back-walk + lag fallback + full chain.

## L2 — Components

### Reuse-first

- **`_account_balance(account_catalog, account_id)`** in
  `bills_builder.py` — already reads `current_balance` for an account id.
  No new read primitive needed.
- **`compute_savings_balance_past(...)`** in `bills_derivations.py` — signature
  changes (single-step back-walk helper, see L4 Contracts). Pure-math, stays.
- **`_prior_month_savings_balance` / `_prior_month_savings_delta`** in
  `bills_builder.py` — used as-is for the future branch.
- **`build_bills_snapshot(...)`** entry point in `bills_builder.py` — stays
  the orchestrator. New internal helper for the chain (see below).

### New / changed modules

| Module | Change |
|---|---|
| `services/bills_derivations.py` | Add `compute_savings_balance_current(partner_id, account_mappings, account_catalog)`. Rewrite `compute_savings_balance_past(prior_balance, deltas_per_month)` — single-step back-walk helper. |
| `services/bills_builder.py` | Add `_back_walk_past_balances(anchor, deltas_per_month)` helper. Replace the inlined `is_past` branch in `build_bills_snapshot` with a chain build. Current-month branch reads live. Future stays lag. New `build_bills_chain` orchestrator + new required kwargs `live_combined` / `deltas_per_month` on `build_bills_snapshot`. |
| `tests/bills/test_builder.py` | Update 6 existing fixtures that assert past/current/future `savings_balance` to mock live combined. Add 4 new tests (anchor + back-walk + lag fallback + full chain). |

### Rationale for new abstractions

- `_back_walk_past_balances` encapsulates the month-by-month subtraction.
  Pure, takes `deltas_per_month: dict[month, float]`, returns
  `dict[month, float]`. Easy to unit-test.
- **Dropped**: `_live_combined_balance` was rejected by review (caveman-review L122)
  as a 4-line helper that opens the door to more tiny-named helpers. Inlined
  inside `build_bills_chain` instead. The new helper `compute_savings_balance_current`
  lives in `bills_derivations.py` (pure, testable, reusable) — that one stays.

## L3 — Interactions

### Data flow (one sync run)

```
account_catalog.json (live current_balance)
            │
            ▼
   compute_savings_balance_current(partner)    ← anchor per partner
            │
            ▼
   for each (partner, month) in [past ∪ current]:
       compute savings_delta
       collect into deltas_per_month[partner][month]
            │
            ▼
   build current-month snapshot
       savings_balance = live combined (anchor)
       savings_delta   = deltas_per_month[partner][current]
            │
            ▼
   _back_walk_past_balances(
       anchor            = live_combined   (current month's savings_balance),
       deltas_per_month  = {m: delta(m) for m in sorted past months}
   )
            │
            ▼
   write snapshots for all past months (newest first)
            │
            ▼
   build future months via lag chain (prior_balance + prior_delta)
            │
            ▼
   write future snapshots
```

### Sync ordering

1. Sync runner loads `account_catalog.json` via `storage.read_json(...)` per
   partner (matches existing `sync_runner.py` behavior — confirmed not
   "once at start"). One in-memory copy is reused across the sync run.
2. For each partner: read all PS raw data (events + txns) for the sync window
   (current + all past months) — same as today.
3. **First pass per partner**: compute `savings_delta` for every (partner, month)
   in past + current. Store in `deltas_per_month[partner][month]`. This pass
   also produces `real_bills`, `cc_usage`, etc. — same as today, just hoisted
   into a loop over months.
4. **Anchor read**: `live_combined = compute_savings_balance_current(partner)`.
   If `None` (live catalog missing for partner), fall back to lag model and
   skip step 5 for this partner.
5. **Back-walk** for each past month m (newest first):
   `balance[m] = balance[m+1] - delta[m]`. Write snapshot.
6. **Anchor apply**: assign `savings_balance = live_combined` on the current
   snapshot. `savings_delta` already assigned in step 3.
7. **Forward-chain** for each future month m: `balance[m] = balance[m-1] + delta[m-1]`.

### Failure modes

| Failure | Behavior |
|---|---|
| Live catalog missing | Fall back to lag model for current month. Append warning. |
| No bills account mapped for a partner | Raise `NoBillsAccountError` — already does. |
| Mid-chain write fails | Stop, leave disk as-is (atomic_write_json). User re-syncs. |
| Past month has no PS data (e.g. account was set up later) | Skip that month, keep disk snapshot as-is. Append warning. |
| Sync window has holes (e.g. PS API returns empty) | Same as above — skip + warn. |

### Observability

- `_calc_log` already logs per-partner math for past months. Extend with:
  - Current-month line: `live_combined = ...` before savings_balance assignment.
  - Back-walk line per past month: `balance[m] = balance[m+1] (X) − delta[m] (Y) = Z`.
- Existing `_bills_calc.log` file (`data/private/`) shows the full chain.

## L4 — Contracts

### New helpers

```python
# bills_derivations.py

def compute_savings_balance_current(
    partner_id: str,
    account_mappings: dict[str, Any],
    account_catalog: list[dict[str, Any]],
) -> float | None:
    """Sum of current_balance for partner's bills + savings accounts.

    Returns None when partner has no bills account mapped (caller decides
    fallback). Never returns 0.0 — if bills exists, return its balance even
    if savings accounts list is empty (no savings accounts is a legitimate
    partner state, not "missing data"). Caller treats None as "fall back
    to lag model".

    Reads live from account_catalog. Pure function — no I/O beyond reading
    the in-memory catalog dict passed in.
    """
```

```python
# bills_derivations.py (rewritten signature)

def compute_savings_balance_past(
    prior_balance: float,
    deltas_per_month: dict[str, float],
) -> float:
    """Back-walk one step: balance for target month given a later month.

    Caller passes the balance of the month immediately after the target
    month + the target month's savings_delta. Returns the target month's
    balance.

    Pure math. Returns prior_balance - deltas_per_month[target_month].
    Target month key MUST be in `deltas_per_month` — caller checks.
    """
```

```python
# bills_builder.py

def _back_walk_past_balances(
    anchor: float,
    deltas_per_month: dict[str, float],
) -> dict[str, float]:
    """Back-walk every past month from a current-month anchor.

    Walks `deltas_per_month` in reverse-chronological order (newest past
    month first). For each step m: balance[m] = balance[m+1] - delta[m].
    `deltas_per_month` maps past month -> savings_delta for the same partner.
    Current month is NOT in the map (its delta is part of the live anchor).

    Returns dict[month, balance] for every past month.

    Example: anchor=13917.02 (current=2026-08),
             deltas={"2026-07": 8920.61, "2026-06": -11872.68, ...}
      → {"2026-07": 13917.02 - 8920.61 = 4996.41,
         "2026-06": 4996.41 - (-11872.68) = 16869.09,
         ...}
    """
```

### `build_bills_snapshot` signature

No change to public signature. Internal change:
- `is_past` branch: instead of computing `sav_end` + `bills_end` via
  `_account_end_balance_from_raw`, defer to a new chain-driven helper that
  reads `deltas_per_month` collected earlier in the sync pass.
- `is_current` branch: assign `savings_balance = live_combined` directly.
- `is_future` branch: unchanged lag model.

### Sync orchestrator (new helper)

```python
def build_bills_chain(
    months: list[str],  # all months to sync, current + past + future
    events_per_month: dict[str, list[dict]],
    transactions_per_month: dict[str, list[dict]],
    account_mappings: dict[str, Any],
    category_roles: dict[str, Any],
    category_catalog: list[dict],
    account_catalog: list[dict],
    warnings: list[str] | None = None,
) -> dict[str, dict]:
    """Build the full chain in one pass.

    Returns {month: snapshot_dict}. Caller writes to disk.

    Order:
      1. Sort months. Identify current + past + future.
      2. Per partner: compute `savings_delta` for past + current, collect into
         `deltas_per_month[partner]`. This pass also produces real_bills,
         cc_usage, etc. — same as today, just hoisted into a loop over months.
      3. Anchor: `live_combined = compute_savings_balance_current(partner)`.
         If None, fall back to lag model for that partner.
      4. Back-walk past months per partner using `_back_walk_past_balances`.
      5. Forward-chain future months per partner (lag model).
      6. Return all snapshots.

    Backward compat: existing `build_bills_snapshot` stays (used by tests
    for single-month isolation with explicit kwargs). Sync runner calls
    `build_bills_chain`.
    """
```

### Data invariants

- For every snapshot in the same partner's chain:
  - **Forward**: `savings_balance[m+1] = savings_balance[m] + savings_delta[m]`
  - **Backward** (back-walk form): `savings_balance[m] = savings_balance[m+1] - savings_delta[m]`
  - Both directions are equivalent; verify with `pytest.approx` on adjacent months.
- `savings_balance[current]` = live combined from `account_catalog.json`.
- `savings_balance[m]` for past m = `savings_balance[current] - Σ delta(k) for k = m+1..current`.
- `savings_balance[m]` for future m = `savings_balance[m-1] + delta[m-1]` (lag).

### Test acceptance criteria

| Test | Asserts |
|---|---|
| `test_build_bills_snapshot_past_savings_balance_back_walk_from_anchor` | Past m balance = anchor − Σ delta(m+1..current). |
| `test_build_bills_snapshot_current_savings_balance_equals_live_combined` | Current `savings_balance` = sum of `current_balance` for partner's bills + savings accounts. |
| `test_build_bills_snapshot_falls_back_to_lag_when_live_unavailable` | When bills account not in catalog, current uses lag + warning. |
| `test_build_bills_chain_full_re_sync_consistent` | Building 5 months (2 past + current + 2 future) in one chain call produces internally consistent values per partner. |

Existing tests that assert old past-month `savings_balance` values to update:
- `test_build_bills_snapshot_past_savings_balance_uses_real_end_balances` → rewrite to back-walk from anchor fixture.
- `test_build_bills_snapshot_current_savings_balance_chains_from_prior` → rewrite to mock live combined.
- `test_build_bills_snapshot_current_savings_balance_lag_model` → rewrite to mock live combined.
- `test_build_bills_snapshot_current_savings_balance_uses_prior_delta_fixture_a_august` → rewrite to mock live combined.
- `test_build_bills_snapshot_future_savings_balance_lag_model` → fixtures updated to mock live combined.
- `test_build_bills_snapshot_future_savings_balance_uses_prior_delta_fixture_a_september` → fixtures updated.
- `test_build_bills_snapshot_past_savings_delta_includes_cc_paydown_fixture_a_july` → unchanged (delta semantics).

## L5 — Implementation Plan

### Ordered tasks

| # | Task | Dep | Estimate |
|---|---|---|---|
| 1 | Add `compute_savings_balance_current` + rewrite `compute_savings_balance_past` in `bills_derivations.py` | — | 30m |
| 2 | Add `_back_walk_past_balances` helper in `bills_builder.py` | 1 | 30m |
| 3 | Add `build_bills_chain` orchestrator in `bills_builder.py` | 1, 2 | 1h |
| 4 | Refactor `build_bills_snapshot` past + current branches to use the chain. `live_combined` + `deltas_per_month` are required kwargs (no silent None fallback). | 2, 3 | 1h |
| 5 | Update `sync_runner.py` to call `build_bills_chain` instead of per-month `build_bills_snapshot` | 3 | 30m |
| 6 | Update existing tests (fixtures for 4 tests) + add 4 new tests | 1-4 | 2h |
| 7 | Run full bills suite + wider test pass | 6 | 30m |
| 8 | Manual re-sync all past-month snapshots on disk via `re_sync_july_2026.py`-style helper | 5, 7 | 30m |
| 9 | Update design docs / F2 spec to reflect new chain | 7 | 30m |

Total: ~6.5h.

### Risk controls

- **Backward compat**: `build_bills_snapshot` keeps its existing kwargs
  (`prior_events`, `prior_transactions`, `warnings`). Two new required kwargs
  for the chain: `live_combined: float | None` (per-partner) and
  `deltas_per_month: dict[str, float] | None` (per-partner). When `None`,
  the legacy chain runs (lag model). Tests must explicitly pass the new
  kwargs — no silent fallback that masks the new logic.
- **Rollback**: revert the feat commits. Re-sync rolls back the on-disk
  snapshots. Likely 2-3 commits depending on slicing.
- **Observability**: `_bills_calc.log` shows every step. Easy to inspect
  chain drift.

### Incremental delivery

1. **Slice 1**: derivations only (task 1). Pure functions, no builder
   changes. New tests cover the new helpers. ~1h.
2. **Slice 2**: chain orchestrator (tasks 2-3). New module, doesn't touch
   `build_bills_snapshot`. New test covers the chain in isolation. ~1.5h.
3. **Slice 3**: builder refactor (task 4). Single-month snapshot uses
   chain inputs. Update fixtures. ~1h.
4. **Slice 4**: sync runner wiring (task 5) + manual re-sync (task 8). End
   to end. ~1h.
5. **Slice 5**: docs (task 9). ~30m.

Each slice ends with a green test run.

### Test plan

- **Unit**: 4 new tests + 4 fixture rewrites in `test_builder.py`.
- **Integration**: existing 177 bills suite must pass.
- **Wider**: existing 484-test wider run (2 pre-existing v4_pipeline failures
  unrelated — confirmed baseline).
- **Manual**: re-sync all past snapshots, inspect `_bills_calc.log` for
  chain consistency, verify FE dashboard reads expected values.

### Definition of done

- [x] All 9 tasks complete.
- [x] Full test suite green (193 bills + 485 wider, incl. 2 previously-failing
      v4_pipeline tests now passing at this baseline).
- [x] On-disk past snapshots re-synced to new chain
      (`scripts/re_sync_savings_chain.py`, 2025-08 → 2026-08).
- [x] FE dashboard unchanged (no UI changes needed).
- [x] Design doc reflects implemented behavior.
- [x] Manual verification: 2026-08 dashboard Fixture A = 13,917.02,
      Fixture B = 50,679.76.
- [x] No silent regressions in 2026-07 / 2026-06 / older past months
      (adjacent-pair invariant holds on all 12 month pairs, both partners).

### Implementation deviations (2026-08-04)

- `compute_savings_balance_past` gained a `target_month` param
  (`prior_balance, target_month, deltas_per_month`) — spec signature could
  not index the deltas dict. User-approved.
- `build_bills_snapshot` gained an OPTIONAL `prior_snapshot` kwarg: chain
  forwards the in-memory prior snapshot so future months lag off fresh
  chain output instead of stale disk. Lag formula unchanged — plumbing only.
- Extra fixture rewrite beyond the L4 list:
  `test_build_bills_snapshot_past_last_month_uses_real_cash_flow` asserted
  the old raw-walk balance; now asserts the same numbers via back-walk kwargs.
- Sync-runner skip warning format changed from per-month
  `"Bills snapshot for {month} skipped: …"` to single
  `"Bills snapshots skipped: …"` (chain is all-or-nothing on
  NoBillsAccountError).
- `_account_end_balance_from_raw` is now dead code (docstring-marked, kept
  awaiting user OK to delete).