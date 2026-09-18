# Bug Reproduction

## Bug Description
Bills dashboard shows `ps_events_fetched: 5` but `events_kept_after_filter: 0` and
`partners[].events: []` for August 2026. All 5 events (2 salary + 3 mortgage)
fetched from PocketSmith are silently dropped.

## Root Cause Analysis
Real PocketSmith `/users/{id}/events` returns events with a `scenario.account_id`
field (the underlying bank account id), not `transaction_account.id` (the
transaction_account id used as key in `account_mappings.json`).

The builder + classifier read `event.get("transaction_account", {}).get("id", "")`
which returns `""` for every real event. Two downstream effects:

1. `bills_builder.py:257` — `event_acct_id not in partner_account_ids` always
   true → event dropped before classification.
2. `bills_classifier.py:47` — `mapping = accounts.get("", {})` returns `{}` →
   `mapping.get("excluded", True)` defaults True → bucket=`"excluded"`.

Existing tests use fabricated `transaction_account` shape, which is why CI passes
but production silently drops everything.

## Reproduction Steps
1. Sync August 2026 (`.\scripts\sync.ps1`).
2. Inspect `data/private/bills_dashboard_2026-08.json`.
3. Expected: `events_kept_after_filter: 5`, salary + mortgage in
   `partners[].events[]`.
4. Actual: `events_kept_after_filter: 0`, both `partners[].events: []`.

Direct repro via builder:
```python
import json
from pathlib import Path
from budget_api.services.bills_builder import build_bills_snapshot

events = json.loads(Path("data/private/events_2026-08.json").read_text())
mappings = json.loads(Path("data/private/account_mappings.json").read_text())
acct_cat = json.loads(Path("data/private/account_catalog.json").read_text())
cat_roles = json.loads(Path("data/private/category_roles.json").read_text())
cat_cat = json.loads(Path("data/private/category_catalog.json").read_text())

snap = build_bills_snapshot(
    month="2026-08",
    events=events,
    transactions=[],
    account_mappings=mappings,
    category_roles=cat_roles,
    category_catalog=cat_cat.get("categories", []),
    account_catalog=acct_cat.get("accounts", []),
)
print(snap["source_counts"])  # {ps_events_fetched: 5, events_kept_after_filter: 0}
print(snap["partners"][0]["events"])  # []
```

## Environment
- PocketSmith events: real `/users/{id}/events` response (Aug 2026)
- account_mappings keys: transaction_account.id (e.g. `4110216`)
- account_catalog `account_id`: underlying bank account (e.g. `4004544`)
- account_catalog `id`: transaction_account.id (e.g. `4110216`)
- Event `scenario.account_id`: underlying bank account (e.g. `4004544`)
- Mapping chain: event.scenario.account_id → catalog[account_id==X].id → mappings