# F2 — Bills & Scheduled Buys — API Contract (SUPERSEDED)

Status: SUPERSEDED. See updated endpoint contracts in:
- [f2-bills-dashboard.md](f2-bills-dashboard.md) — L4 contracts for `GET /api/bills/dashboard` (shipped in sub-feature 2).
- [f2-bills-sync.md](f2-bills-sync.md) — sub-feature 1 sync extension (shipped).

Date: 2026-08-02

## Why superseded

This doc described a separate `POST /api/sync/bills` async job model with
`bills_sync_jobs/*.json` state files and a `GET /api/sync/bills/status?job_id=...`
endpoint. **That model was not implemented.** Sub-feature 1 ships a simpler
design: the existing `GET /api/sync?start_month=&end_month=` endpoint runs
synchronously and writes `bills_dashboard_YYYY-MM.json` directly inside the
per-month loop. Sub-feature 2 reads those files via `GET /api/bills/dashboard`.

The FE behavior described here (12-month forward window, current-month pin,
banner for "Past"/"Future") is unchanged — those are FE-side decisions, not
affected by which BE endpoint produces the data.

## Endpoints that shipped

| Method | Path | Doc |
|---|---|---|
| GET | `/api/bills/dashboard?month=YYYY-MM` | [f2-bills-dashboard.md L4](f2-bills-dashboard.md#l4--contracts-approved--l2-q1-finalization) |
| GET | `/api/sync?start_month=&end_month=` | [f2-bills-sync.md](f2-bills-sync.md) (extended by sub-feature 1 to write snapshots) |

## Endpoints that did NOT ship (and were never built)

| Method | Path | Why |
|---|---|---|
| POST | `/api/sync/bills` | Sync runs via existing `GET /api/sync` — no separate async trigger needed. |
| GET | `/api/sync/bills/status?job_id=...` | No async job model — sync is synchronous inside the per-month loop. |
| GET | `/api/bills/events` (planned sub-feature 3) | Still on the roadmap. Same router as dashboard. See future sub-feature 3 design doc. |

## Endpoint contract details

All response shapes, error model, and 400/404/500 conventions are now in
[f2-bills-dashboard.md L4](f2-bills-dashboard.md#l4--contracts-approved--l2-q1-finalization).