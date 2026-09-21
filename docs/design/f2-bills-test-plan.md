# F2 — Bills & Scheduled Buys — Test Plan (DRAFT)

Status: ROUGH DRAFT — L5 in progress. Not human-approved.
Date: 2026-07-31
Repo: Pocket-Smith-Reports
Owner: coordinator

## What this doc is

Per-scenario test list. Each derivation function and each endpoint gets at
least one test. Each test names the scenario + the inputs + the expected
output.

Source-of-truth for fields: [f2-bills-source-of-truth.md](f2-bills-source-of-truth.md).
Math: [f2-bills-derivations.md](f2-bills-derivations.md).
API contracts: [f2-bills-api.md](f2-bills-api.md).
PS quirks: [f2-bills-ps-integration.md](f2-bills-ps-integration.md).

## Layers

- **Unit** — derivation functions in isolation, against synthetic PS event
  fixtures.
- **Integration** — `PSClient` mocked, full pipeline from `/api/sync/bills`
  through to snapshot file.
- **Endpoint** — `TestClient` against the FastAPI app, snapshot file present.
- **E2E** — Playwright; the dashboard renders correctly for a known snapshot.

## Test fixtures (frozen PS data)

- `tests/bills/fixtures/ps_events_2026-07.json` — small fixture (10-20
  events) covering: salary for both partners, bills on checking, buys on CC,
  savings transfers, CC payment on bills. **Confirming at implementation.**
- `tests/bills/fixtures/ps_transactions_2026-07.json` — same.

## Unit tests

### Salary (§1)

| Test | Input | Expected |
|---|---|---|
| `test_salary_single_event_per_partner` | 1 income event per partner | `42000`, `38000` |
| `test_salary_multiple_income_events_summed` | 2 income events for Fixture A | sum |
| `test_salary_missing_falls_back_to_prior_month` | no income event for July | prior month's value + warning flag |
| `test_salary_filters_by_checking_account` | income on savings account | ignored |

### Savings transfer (§2)

| Test | Input | Expected |
|---|---|---|
| `test_savings_transfer_normal` | scheduled + balance delta + expected | formula result |
| `test_savings_transfer_signed_positive` | bills shrank more than salary-bills | positive (into savings) |
| `test_savings_transfer_no_bills_account_errors` | bills account missing | 422 error |

### Savings delta (§13)

| Test | Input | Expected |
|---|---|---|
| `test_savings_delta_zero_when_aligned` | scheduled == transfer | 0 |
| `test_savings_delta_positive_when_oversaved` | transfer > scheduled | positive |
| `test_savings_delta_negative_when_undersaved` | transfer < scheduled | negative |
| `test_savings_delta_drives_savings_box` | positive | `savingsDeltaTone: "income"` in sub-deriv |

### Everyday budget (§8 — round-4 forward formula)

| Test | Input | Expected |
|---|---|---|
| `test_everyday_budget_forward_formula` | m+1 events (salary, bills, buys) | `salary(m+1) − bills(m+1) − ccBuys(m+1)` |
| `test_everyday_budget_null_last_window_month` | no m+1 data | `null` (FE hides budget zone) |
| `test_everyday_budget_excludes_cc_payment_events` | m+1 with CC-paydown event | excluded from bills/buys terms |

### Bills / buys count (FE-side, but documented here)

| Test | Input | Expected |
|---|---|---|
| `test_bills_count` | 12 bills | `bills_count: 12` |
| `test_buys_count` | 3 buys | `buys_count: 3` |

### Bill titles (§4)

| Test | Input | Expected |
|---|---|---|
| `test_bills_filter_by_checking_account` | events on checking + credits | only checking kept |
| `test_bills_payee_falls_back_to_note` | payee empty | note used as title |
| `test_bills_recurring_and_one_off_both_kept` | mix | all kept |

### Scheduled buys (§5)

| Test | Input | Expected |
|---|---|---|
| `test_buys_filter_by_credits_account` | events on checking + credits | only credits kept |
| `test_buys_matched_flag_set_when_real_posted` | real CC tx matches scheduled buy by date+amount | `is_matched: true` |
| `test_buys_one_off_counted` | one-off CC event | included |

### CC bill (§9)

| Test | Input | Expected |
|---|---|---|
| `test_real_cc_bill_past_month` | past month, "CC payments" txns on bills acct | sum of those |
| `test_estimated_cc_bill_current_month` | current month, no paydowns yet | prev-month CC spend + prev-month CC buys |
| `test_estimated_cc_bill_current_with_real_so_far` | current month, 2 of 4 paydowns posted | both numbers returned |
| `test_estimated_cc_bill_future_month` | future month | prev-month-relative estimate |
| `test_no_cc_account_returns_zero` | partner with no CC account | 0 |

### CC usage (§10)

| Test | Input | Expected |
|---|---|---|
| `test_cc_usage_current_month` | CC transactions this month | sum |
| `test_cc_usage_not_computed_past_or_future` | past/future month | null |

### Real budget usage (§11)

| Test | Input | Expected |
|---|---|---|
| `test_budget_usage_current_month` | current month, all spend txns for partner | sum |
| `test_budget_usage_excludes_cc_and_savings` | mix | only non-CC, non-savings counted |
| `test_budget_usage_past_month_via_events` | past month | FE derives from `events[]` |

### Savings balance (§12)

| Test | Input | Expected |
|---|---|---|
| `test_savings_balance_current` | current month | live `current_balance` |
| `test_savings_balance_past_derived` | past month, transactions after EOM known | formula |
| `test_savings_balance_projected_12_months` | current + 12 future | 12 values, formula-correct |
| `test_savings_balance_projection_per_partner` | both partners | independent values |

### Net (§13)

| Test | Input | Expected |
|---|---|---|
| `test_net_current_month` | normal | `salary - bills - estCcBill` |
| `test_net_past_month_uses_real_cc_bill` | past | `salary - bills - realCcBill` |

### Status (§14)

Reuse the existing FE fixtures in
[client/src/components/bills/__tests__/fixtures.ts](../client/src/components/bills/__tests__/fixtures.ts)
— the six scenarios (comfortable, exact, partial, shortfall, zero_savings,
extreme_shortfall). Port them to Python.

## Endpoint tests

### GET /api/bills/dashboard

| Test | Setup | Expected |
|---|---|---|
| `test_dashboard_current_month_ok` | snapshot for current month exists | 200, full payload |
| `test_dashboard_past_month_ok` | snapshot for past month exists | 200, real data |
| `test_dashboard_future_month_ok` | snapshot for future month exists | 200, estimate only |
| `test_dashboard_no_snapshot_errors` | missing snapshot file | 422 with reason |
| `test_dashboard_invalid_month_errors` | `month=foo` | 400 |
| `test_dashboard_pagination_window` | request month 13 months out | 200 or 422? **TBD** |

### GET /api/bills/events

| Test | Expected |
|---|---|
| `test_events_paginated_default` | page=1, pageSize=12 |
| `test_events_page_size_max_100` | pageSize=200 clamped to 100 |
| `test_events_out_of_range_empty` | page=999 → empty list, accurate total |

### POST /api/sync/bills

| Test | Expected |
|---|---|
| `test_sync_kickoff_returns_job_id` | 202, `{job_id, status: "pending"}` |
| `test_sync_dedup_same_job_id` | second POST returns same `job_id` |
| `test_sync_failure_status` | PS error → `status: "failed"`, error list populated |
| `test_sync_atomic_write` | kill mid-write → no partial file |

### GET /api/sync/bills/status

| Test | Expected |
|---|---|
| `test_status_pending` | 200, `status: "pending"` |
| `test_status_running` | 200, `status: "running"` |
| `test_status_completed_includes_snapshot` | 200, `snapshot` payload |
| `test_status_failed_includes_errors` | 200, `errors` array |
| `test_status_unknown_job_id` | 404 |

## E2E (Playwright)

| Test | Expected |
|---|---|
| `e2e_dashboard_renders_current_month` | page loads, partner bars visible, status badges correct |
| `e2e_dashboard_renders_past_month_with_real_data` | past month shows real CC bill, not estimate |
| `e2e_dashboard_no_snapshot_shows_error_page` | error page with reason |
| `e2e_sync_button_kickoff_then_completes` | click Sync → poll status → dashboard re-renders |
| `e2e_pagination_next_future` | next button walks to future month, banner shows "Future" |
| `e2e_pagination_prev_past` | prev button walks to past month, banner shows "Past" |
| `e2e_matched_badge_appears_when_buy_matched` | real CC tx posts → buy badge flips to "matched" |

## Coverage targets

- Unit: 100% of derivation functions.
- Endpoint: every documented status code (200, 400, 404, 422).
- E2E: at least one happy path per scenario, one error path per error class.
