# F2 — Bills & Scheduled Buys — PS Integration Notes (DRAFT)

Status: L1 in progress. Corrected after PS API research 2026-08-02.
Date: 2026-08-02
Repo: Pocket-Smith-Reports
Owner: coordinator

## What this doc is

PocketSmith-specific quirks. Account types, role filter, recurrence semantics,
sign convention. These are the things that bite if you don't write them down
once. Read together with [f2-bills-source-of-truth.md](f2-bills-source-of-truth.md) and [f2-bills-derivations.md](f2-bills-derivations.md).

## Account types (PS API)

PS exposes two account levels. We need both.

| Level | Field | PS enum values | Used for |
|---|---|---|---|
| Institution (top-level) | `Account.type` | `bank \| credits \| cash \| stocks \| mortgage \| loans \| vehicle \| property \| insurance \| other_asset \| other_liability` | Top-level grouping. |
| Transaction account (sub-level) | `TransactionAccount.type` | **same 11-value enum** | **This is the filter key.** See bucketing rule. |

> **Correction vs. earlier design.** The earlier design listed `transaction_account.type` as `"checking" \| "savings" \| "credits"`. That's **wrong**. PS has no `"checking"` or `"savings"` `type` values — both are `type=bank`, distinguished by the account's `name` string (e.g. "A-Check Nordic Bank" vs "A-Savings Nordic Bank"). The local `account_mappings.json` uses `type: "checking" \| "cc" \| "savings"` as a **local override**, not a PS enum value.

The `account_catalog.json` snapshot stores institution-level accounts. The
`account_mappings.json` is the per-account user binding (`partner_id`, local
`type`, `excluded`) — **this is the authoritative source-of-truth** for
bucketing. `account_owners.json` is a flat `{account_id: partner_id}` legacy
file that is not written by the sync flow and contains dangling references
(verified: `account_owners.json` lists account id `5245500` → `partner_b`,
which does not exist in either `account_catalog.json` or `account_mappings.json`).
The bucketing code should use `account_mappings.json` for `partner_id`,
local `type`, and `excluded` — never `account_owners.json` alone.

## Bucketing rule (recap)

| PS `TransactionAccount.type` | Local mapping override | Role filter | Bucket |
|---|---|---|---|
| `bank` (and `account_mappings.type == "checking"`) | `checking` | `spend` | bills |
| `credits` (and `account_mappings.type == "cc"`) | `cc` | `spend` | scheduled CC buys |
| `bank` (and `account_mappings.type == "savings"`) | `savings` | `savings` | savings transfers |
| `bank` (and `account_mappings.type == "checking"`) | `checking` | `income` | salary |

**Local `account_mappings.type` overrides PS's `type` value** when the user has
explicitly re-classified (e.g. local `cc` → PS `credits`). We respect the
local override.

## Recurrence semantics

PS event `repeat_type` is one of (verified from OpenAPI):
- `"once"` — one-off
- `"daily"`, `"weekly"`, `"fortnightly"`, `"monthly"`, `"yearly"`, `"each weekday"` — recurring
- `repeat_interval` is an int multiplier (e.g. `weekly + repeat_interval: 2` = every 2 weeks)

> **Correction vs. earlier design.** The earlier design listed `"never"` as a one-off. There is **no `"never"`** in PS — the one-off value is `"once"`.

**F2-BE does NOT filter on `repeat_type`.** Both recurring and one-off events
are bucketed the same way (by transaction account type + local mapping). See
[f2-bills-source-of-truth.md](f2-bills-source-of-truth.md) for the user
decision.

## Sign convention (VERIFIED)

Both APIs use the same signed-amount convention:

| API | Sign for income | Sign for expense |
|---|---|---|
| `/events` | positive | negative (verified — see existing report code) |
| `/transactions` | positive | negative (verified — live `2026-07_ps_raw.json` shows `-424.55` for a Hello Fresh debit on A-CC Nordic Bank) |

> **Correction vs. earlier design.** The earlier design marked `/transactions` sign as "CONFIRMING". It is now verified — both APIs use negative-for-expense.

## CC payment category

- Each partner has their own "CC payments" category in PS. Local catalog has
  `"CC Payment (paired)"` under the "Transfers" parent.
- The paydown flow: bills-account → CC-account. The cash leaving the bills
  account is tagged with the "CC payments" category; on the CC-account side
  the same event is the balance reducing.
- **Which side do we sum for the "real CC bill"?** Earlier design says bills-side. The
  design uses bills-side to avoid double-counting across both legs.

## Pre-knowledge window for CC bills

- Fixture A/Fixture B know the upcoming CC bill **14-20 days before it posts**.
- The estimate is therefore "reliable" for the first ~10-15 days of the month,
  then transitions to "real" as paydowns post.
- We display **both** numbers (estimate + real-so-far) for the current month
  rather than auto-flipping. The status bar uses the estimate; real-so-far is
  informational.

## PS pagination + rate limits

- `PSClient._get_paginated` follows `Link rel="next"` headers.
- Per-page size: 1000.
- Max pages: 1000 (capped).
- Rate limit: PS returns 429. We surface it as `PS API rate limited` in the
  sync job error list. Retry strategy: **TBD** (could be exponential backoff
  inside the sync job, or fail-fast and let the user retry).
- 30s timeout per request (`TIMEOUT_SECONDS` in `ps_client.py`).

## API client reference

[src/budget_api/services/ps_client.py](../src/budget_api/services/ps_client.py)
already has the GET-only methods we need:

| Method | Returns |
|---|---|
| `get_me()` | current user dict |
| `get_accounts(user_id)` | institution accounts (paginated) |
| `get_transaction_accounts(user_id)` | transaction accounts |
| `get_events(user_id, start_date, end_date)` | PS events (NOT paginated) |
| `get_transactions(user_id, start_date, end_date)` | transactions (paginated) |
| `get_transactions_for_account(account_id, start_date, end_date)` | per-account transactions |
| `get_categories(user_id)` | category tree |
| `get_budget(user_id)` | budget snapshot (roll_up=false) |

No new PS endpoints are required.

## Open items

- **TBD**: confirm `/transactions` sign convention (see above).
- **TBD**: confirm per-partner CC payment category title (likely
  `"CC Payment (paired)"`).
- **TBD**: rate-limit retry strategy inside the sync job.
