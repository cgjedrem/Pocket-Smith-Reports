# F2 — Bills & Scheduled Buys — Backend Design (INDEX)

Status: ROUGH DRAFT — not human-approved. Refined in conversation.
Date: 2026-07-31
Repo: Pocket-Smith-Reports
Owner: coordinator

## What this is

Entry point for the F2-BE design. The full design is split across five small
docs by concern. Read this index first, then follow links.

## The seven docs

| Doc | Purpose | Audience |
|---|---|---|
| [f2-bills-source-of-truth.md](f2-bills-source-of-truth.md) | The contract: which field, which source, bucketing rule, open Qs. | Both FE + BE |
| [f2-bills-derivations.md](f2-bills-derivations.md) | The math: per-field formulas, edge cases, sign-convention caveats. | BE primarily; FE for cross-check |
| [f2-bills-api.md](f2-bills-api.md) | The HTTP surface: endpoints, request/response shapes, error model, window. | Both |
| [f2-bills-snapshot.md](f2-bills-snapshot.md) | On-disk JSON file shape, async job lifecycle, atomic write. | BE |
| [f2-bills-ps-integration.md](f2-bills-ps-integration.md) | PS account types, role filters, recurrence semantics, sign-convention note. | BE |
| [f2-bills-test-plan.md](f2-bills-test-plan.md) | Per-scenario test list (L5). Unit / integration / endpoint / E2E. | Both |
| [f2-bills-crud.md](f2-bills-crud.md) | Sibling: in-app create/edit/delete of salary + savings + bills + CC buys (F2-CRUD, future task). L1 only. | Both |

## Series

- **F2-BE** = read path, this index + the first 6 docs above.
- **F2-CRUD** = write path, [f2-bills-crud.md](f2-bills-crud.md). Own index
  to be created when L2 starts.

## TL;DR

- The dashboard reads a per-month JSON snapshot from
  `data/private/bills_dashboard_YYYY-MM.json`.
- A new async endpoint `POST /api/sync/bills` (status-check pattern) produces
  that snapshot.
- All events come from PS (no local CRUD). Bucketing is by **transaction
  account type**, not by `repeat_type`.
- Per-partner derived fields: salary, bills, everyday budget, CC buys,
  savings transfer, scheduled savings, savings delta, savings balance,
  est/real CC bill, CC usage, real budget usage, net, status.
- Past months use real data; current uses estimate + real-so-far; future uses
  estimate only. 12-month forward projection window for savings.
- The events list shown in the FE table view includes ALL event types
  (income / savings / bills / buys). The FE no longer filters.
- FE presentation sub-derivations (capsule sub-widths, savings-box tone, etc.)
  are computed locally from the high-level BE response — see
  [f2-bills-derivations.md §17](f2-bills-derivations.md).

## L1-L5 status

- **L1 (Goals)**: done — see source-of-truth + derivations.
- **L2 (Scenarios)**: in test-plan doc.
- **L3 (API contract)**: sketched — see API doc; field names to confirm with FE.
- **L4 (Data model)**: snapshot file shape sketched — see snapshot doc.
- **L5 (Test plan)**: drafted — see test-plan doc.

## References

- PS client: [src/budget_api/services/ps_client.py](../src/budget_api/services/ps_client.py)
- Account mappings: [data/private/account_mappings.json](../data/private/account_mappings.json)
- Category roles: [data/private/category_roles.json](../data/private/category_roles.json)
- Category catalog: [data/private/category_catalog.json](../data/private/category_catalog.json)
- Sync runner (existing pattern): [src/budget_api/services/sync_runner.py](../src/budget_api/services/sync_runner.py)
- FE mock: [client/src/components/bills/finance-data.ts](../client/src/components/bills/finance-data.ts)
- FE types: [client/src/types/api.ts:111-150](../client/src/types/api.ts#L111-L150)
- Existing bills design: [docs/design/design-f2-bills.md](../docs/design/design-f2-bills.md)
