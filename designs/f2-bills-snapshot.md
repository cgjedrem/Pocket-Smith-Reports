# F2 — Bills & Scheduled Buys — Snapshot + Async Job (SUPERSEDED)

Status: SUPERSEDED. See updated snapshot details in:
- [f2-bills-dashboard.md](f2-bills-dashboard.md) — L4 response shape for `GET /api/bills/dashboard`.
- [f2-bills-sync.md](f2-bills-sync.md) — sub-feature 1 sync extension that produces the snapshot.

Date: 2026-08-02

## Why superseded

This doc described an async job lifecycle (`pending` → `running` → `completed` / `failed`)
with per-job state files at `data/private/bills_sync_jobs/<job_id>.json`.
**That model was not implemented.** Sub-feature 1 ships a simpler design:
the existing `GET /api/sync?start_month=&end_month=` endpoint runs
synchronously and writes `bills_dashboard_YYYY-MM.json` directly inside the
per-month loop. There is no `bills_sync_jobs/` directory.

## Snapshot file (still accurate)

- **Path**: `data/private/bills_dashboard_YYYY-MM.json` (one file per month).
- **Owner**: only the BE process (PS service account or local user with write access to `data/private/`).
- **Gitignored**: yes. The `.gitignore` already excludes `data/private/*`.
- **Atomic write**: temp file + rename via `storage.atomic_write_json`. See [services/storage.py](../src/budget_api/services/storage.py).

## Snapshot shape (the actual one shipped)

Sub-feature 1 ships this shape (defined by [models/bills.py](../src/budget_api/models/bills.py),
written by [services/bills_builder.py](../src/budget_api/services/bills_builder.py)):

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

**Differences from the original draft above:**

- `ps_window_start` / `ps_window_end` were **removed** during sub-feature 1 build. Not in the shipped shape.
- `bills_count` / `buys_count` are month-level aggregates (sum across partners). Per-partner events carry their own `type` field.

## What did NOT ship

| Concept | Why dropped |
|---|---|
| Async job lifecycle (pending/running/completed/failed) | Sync is synchronous. No `BackgroundTasks` for bills. |
| `data/private/bills_sync_jobs/<job_id>.json` state files | No async jobs. |
| Server-side dedup of duplicate POSTs | No POST endpoint to dedupe against. |
| TTL/pruning (24 months) | Not implemented yet. Future task. |
| `ps_window_start` / `ps_window_end` fields | Dropped during sub-feature 1 — not needed by FE. |

## Tests (the ones that shipped)

- `test_snapshot_writes_atomic_for_each_month` — covered in `tests/bills/test_sync_extension.py`.
- 17 dashboard-read acceptance tests in `tests/bills/test_dashboard.py`.

The original test list (`test_sync_dedup`, `test_failure_preserves_old_snapshot`)
was for the async job model and is obsolete.