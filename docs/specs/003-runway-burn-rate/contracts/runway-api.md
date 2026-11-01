# Runway HTTP API Contract

**Contract version**: 1
**Status**: Backend v1 and typed frontend consumer implemented and locally validated; independent QA pending.
**Base**: Existing local-first FastAPI `/api` application.

This Markdown HTTP/JSON contract is normative for the new Pydantic and TypeScript
DTOs. It is not a change to BillsSnapshot or monthly report contracts.
Calculation/source validation is specified in [../data-model.md](../data-model.md).
Unknown response fields may be ignored by the client for additive evolution;
requests and persisted runway settings reject unsupported fields.

## Common behavior

- No authentication or network-exposure change; retain the existing local-first
  boundary. No external API access, credential read, sync, or scheduler.
- Every response on `/api/bills/runway` and `/api/settings/runway`, including PUT,
  domain-unavailable 200s, request errors, and handled server errors:
  `Cache-Control: no-store`. Add both exact paths to `main.py`'s allowlist.
- JSON content type. No ETag/cache-based result reuse or browser persistence.
- No supported query parameters on any new route. Reject unsupported parameters
  with 400 rather than imply a custom period, historical date, currency, or owner
  filter was honored. GET has no request body.
- Request validation retains the existing 422-to-400 response shape:
  `{"detail":"human-readable safe explanation"}`. Runway uses static validation
  text rather than echoing caller-controlled field names or values. Duplicate JSON
  object keys are rejected, not silently overwritten. Do not return raw values from
  failed money parsing, source JSON, filesystem paths, payees, or exception text.
- Route handler delegates to service/models. Unexpected I/O/serialization errors
  yield generic 500 detail, not financial fallback values.
- Identifiers are canonical positive decimal strings; source integer IDs are
  normalized by the adapter, not coerced at the request boundary.
- Every field listed below is present unless explicitly optional. Nullable means
  JSON `null`, not omission or zero.

## GET /api/settings/runway

Read current selection and picker metadata without writing. Response **200**:

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | integer, 1 | Settings contract version. |
| `liquid_account_ids` | string[] | Saved IDs in saved order; `[]` when absent/empty. |
| `selection_status` | `unconfigured \| empty \| valid \| invalid` | File absence differs from explicit empty. |
| `owners` | Owner[] | Current configured identities; no positional attribution. |
| `accounts` | AccountOption[] | Catalog accounts plus saved missing IDs so selections never disappear silently. |
| `issues` | Issue[] | Selection/source limitations; no raw money in messages. |

`Owner`:

| Field | Type |
|---|---|
| `partner_id` | string |
| `partner_slot` | `"a" \| "b" \| ""` |
| `label` | string |

`AccountOption`:

| Field | Type | Meaning |
|---|---|---|
| `id`, `name` | string | ID remains visible when catalog entry is missing. |
| `partner_id` | string or null | Current configured identity, never guessed. |
| `type` | `checking \| savings \| cc \| investment` or null | Unknown/unsupported values represented as ineligible, not checking. |
| `excluded` | boolean | Effective exclusion status. |
| `selected` | boolean | Member of saved selection. |
| `eligible` | boolean | Valid currently selectable checking/savings account with balance. |
| `issues` | Issue[] | Specific ineligibility reason(s). |

Picker options contain **no balance amounts**; reserve money is returned by the
result endpoint for selected accounts only. Unsupported source account types
become null plus `account_type_ineligible`.

Absent config is successful `unconfigured`, never a read failure. A structurally
readable but now invalid selection returns 200 with retained IDs and issues.
Corrupt/unreadable config or unknown settings version returns **500**, not an
empty default; UI must not enable Save until settings load succeeds. Unreadable
required picker sources also return 500, preserving unknown saved selection.
A missing catalog can return 200 with ineligible saved rows and source issues;
only explicit empty reset can be saved until nonempty eligibility is verifiable.
Detected source change/running sync returns **409** with safe retry detail; this
is a settings-load failure and Save remains disabled until a stable successful read.

## PUT /api/settings/runway

Full replacement of the **runway selection only**:

```json
{"liquid_account_ids":["1100001","1100006"]}
```

Required array; strict string IDs; no duplicates or unknown fields (including
client-supplied `schema_version`, balances, owners, currency, or `liquid` flags).
Validate the selection as a whole against current local catalog and bindings.
Do not deduplicate, drop, auto-add, trim, or repair submitted IDs.

- **200**: Same response shape as GET settings, derived from the validated saved
  selection. `[]` persists intentional `empty`. Save is explicit and atomic.
- **400**: Invalid body/ID/duplicate/eligibility/balance or unsupported query.
  Prior file bytes remain unchanged.
- **409**: `{"detail":"Runway sources changed; retry the selection save."}`
  for detected source change/running sync before persistence. Prior config stays.
- **500**: Required source cannot be safely read, or atomic save fails.
  Prior file remains intact when replace does not complete. An ambiguous lost
  response after a successful replace is resolved by settings GET; do not promise
  transactional delivery of the HTTP response.

Generate response metadata before replacing the file; do not perform another
fallible source read after commit and call it a failed save. No new owner or
account bindings are written. No source financial record, sync status, or other
feature settings are changed. This local-first API does not introduce multi-user
optimistic concurrency; sequential explicit settings writes are last-write-wins.
Revalidate eligibility on result GET to handle changes after Save.

## GET /api/bills/runway

Calculates the current comparison independently of Bills dashboard snapshots.
No `month`, historical as-of, or display-window parameter.

Response **200** is returned for both useful results and expected domain
unavailability, including absent settings/raw history, invalid source/selection,
insufficient history, currency conflict, or sources changing. **500** is reserved
for unexpected service failure; the UI distinguishes that transport error from
a domain result with null measures.

### Top-level RunwayResponse

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | integer, 1 | Independent API version. |
| `calculation_version` | integer, 2 | Runway calculation version only. v2 = SC-split / RD-002 (2026-11-01). |
| `calculated_at` | ISO offset-aware datetime | Time evaluated, not time data was collected. |
| `as_of_month` | `YYYY-MM` | Server-local current month. |
| `basis` | `"household_net_spending"` | Reports household net spending (`detailed.household_totals`); no forecasting. |
| `owner_attribution` | `"common_economy_split" \| "payer"` | Split: owner = fair share of split categories + own net elsewhere. Payer: own net by paying account owner. |
| `split_shares` | `{partner_a, partner_b}` numbers or null | Split percentages in use; null for payer attribution. |
| `candidate_months` | string[3] | Exact prior three completed months, ascending. |
| `included_months` | string[] | Common included subset, ascending. |
| `included_month_count` | integer, 0..3 | Must equal array length. |
| `selection_status` | settings selection enum or `"invalid_settings"` | Safe explicit absence/invalidity. |
| `selected_account_ids` | string[] or null | Saved IDs, or null when settings cannot be parsed. |
| `selected_accounts` | SelectedAccount[] | Every readable selected ID, including invalid/missing ones. |
| `catalog_collected_at` | ISO datetime or null | Explicit catalog collection evidence only. |
| `catalog_freshness` | `fresh \| stale \| unknown` | Older than 24h is stale; absence unknown. |
| `observations` | MonthObservation[3] | All candidate months, not only useful ones. |
| `owners` | OwnerResult[] | Current configured owners, stable identities. |
| `household` | Measures | Unique-account selected reserves / combined-owner mean. |
| `issues` | Issue[] | Global evidence/consistency/ownership limitations. |

If owner configuration is unreadable, `owners:[]` with `invalid_source` is an
unavailable result, not a synthetic pair of people. Candidate months and global
issues are still returned. Settings/read consistency failure produces null affected
measures; never an older cached ratio presented as current.

### SelectedAccount

`id`, `name`, `partner_id`, `type`, `excluded`, `selected`, `eligible`, and `issues` as in
AccountOption, plus:

| Field | Type |
|---|---|
| `balance` | finite JSON number or null |
| `currency_code` | uppercase 3-letter code or null |
| `currency_status` | `verified \| unverified \| conflict` |
| `balance_date` | ISO date or ISO offset datetime or null |
| `balance_date_precision` | `date \| datetime \| unknown` |
| `balance_freshness` | `fresh \| stale \| unknown` |

Missing/invalid balance is null and identified; valid zero/negative is preserved.
Only currently eligible known balances enter sums; no partial reserve sum is
returned as the full selected total when one selected account is invalid.

### Measures and OwnerResult

`OwnerResult` has `owner: Owner` plus all `Measures` fields:

| Field | Type | Meaning |
|---|---|---|
| `selected_account_ids` | string[] | Current attribution of selected IDs. |
| `reserves` | finite number or null | Signed total of exactly those selected accounts. |
| `average_monthly_spending` | finite signed number or null | Mean over common included months; null if <2. Can be <=0 (refunds) -> `nonpositive_burn`, ratio null. |
| `runway_months` | finite number >0 or null | Unrounded descriptive ratio, never infinity or zero. |
| `runway_display` | string or null | One decimal (`"3.0"`, `"1.3"`) or `"<0.1"`; UI appends "months". |
| `currency_code` | uppercase code or null | Common comparison basis if established, else null. |
| `reserves_currency_code` | uppercase code or null | Valid reserve observation's basis, even if ratio incompatible. |
| `spending_currency_code` | uppercase code or null | Valid average observation's basis, even if ratio incompatible. |
| `currency_status` | `verified \| unverified \| conflict` | Unknown contributing currency prevents verified. |
| `status` | `available \| qualified \| unavailable` | Status of the ratio, not a guarantee. |
| `issues` | Issue[] | All blockers and qualifications affecting this result. |

Ratio null iff unavailable; display null iff ratio null. Preserve independently
valid money on unavailable results, e.g. nonpositive reserves or no spending
history. With no owner selection, reserves is null and `no_selection` is present.
Household with some owners unselected may still have valid selected reserves;
its scope text explicitly describes selected accounts, not all household assets.

### MonthObservation

| Field | Type | Meaning |
|---|---|---|
| `month` | `YYYY-MM` | Candidate month. |
| `status` | `included \| excluded` | Common window membership. |
| `coverage` | `complete \| unverified \| partial \| invalid \| missing` | Source evidence classification. |
| `collected_at` | ISO datetime or null | Explicit raw-source collection date. |
| `freshness` | `fresh \| stale \| unknown` | Collection age, not spending date age. |
| `coverage_start`, `coverage_end` | ISO date or null | Explicit inclusive bounds. |
| `owners` | array of `{partner_id, spending, currency_code, currency_status}` | Spending finite signed net or null; codes/status as above. |
| `household_spending` | finite signed number or null | Reports `household_totals.total` for the month; null on conflict/excluded source. |
| `household_currency_code` | uppercase code or null | Compatible household observation basis. |
| `issues` | Issue[] | Every exclusion or qualification. |

Owner and household observations for a source-excluded month are null. An included
month can retain valid owner observations but have null household spending on
cross-owner currency conflict; that blocks household average/ratio, not valid
independent owner comparisons. The same included set is exposed for all owners.

### Issue

```json
{
  "code": "coverage_unverified",
  "severity": "qualification",
  "month": "2026-07",
  "account_id": null,
  "partner_id": null
}
```

All five fields required. `severity` is `blocking | qualification`.
`month`, `account_id`, and `partner_id` are nullable safe identifiers.
Codes are stable machine labels. The client maps them to static human-readable
copy with account/owner/month labels, never raw source/error strings.

| Codes | Meaning / expected display |
|---|---|
| `no_selection` | "Select liquid accounts" / owner "No selected reserve accounts". |
| `invalid_settings` | Saved settings unreadable/unsupported; recover settings load. |
| `invalid_selection`, `account_missing`, `account_unowned`, `account_excluded`, `account_type_ineligible` | Retain and identify selected account; correct selection/binding. |
| `missing_balance`, `invalid_balance` | Recorded selected balance unusable, never zero fallback. |
| `insufficient_history` | Fewer than two common usable completed months. |
| `missing_source`, `invalid_source`, `partial_source`, `unproven_zero` | Candidate observation excluded; include source month label. |
| `ownership_incomplete` | Non-excluded spending cannot be assigned; no partial household claim. |
| `sources_changing` | Inconsistent read/running sync; explicit Retry, no auto-sync. |
| `currency_conflict` | Affected sums/ratios unavailable; no FX. |
| `nonpositive_reserves`, `nonpositive_burn` | Preserve valid observed values; ratio undefined. |
| `coverage_unverified` | "Month coverage unverified — recorded transactions only". |
| `currency_unverified` | "Single-currency assumption; currency unverified". |
| `source_stale`, `source_date_unknown` | Show actual source date or unknown, separate from calculated time. |
| `balance_stale`, `balance_date_unknown`, `balance_date_unverified` | Show bank-date evidence/limitation without making money disappear. |
| `classification_unverified` | Missing category authority; recorded classification limitations visible. |
| `excluded_months` | Otherwise valid result uses fewer than all three candidates. |
| `source_times_differ` | Sources were not collected at one verified time. |

An excluded month carries blocking issues at observation scope; an otherwise
valid two-month owner/household ratio carries the `excluded_months` qualification,
not an incorrectly global blocking status. It still exposes full month issues.
Deduplicate repeated identical issues; do not stop after the first limitation.

## Synthetic arithmetic acceptance

At October 2026, include July/August/September:

| Scope | Monthly net spend | Reserves | Mean | Numeric ratio | Display |
|---|---|---|---|---|---|
| Partner A | 20,000 / 30,000 / 40,000 | 90,000 | 30,000 | 3 | 3.0 months |
| Partner B | 50,000 / 60,000 / 70,000 | 30,000 | 60,000 | 0.5 | 0.5 months |
| Household | 70,000 / 90,000 / 110,000 | 120,000 | 90,000 | 1.333... | 1.3 months |

These numbers do not imply available/fresh status: dated stale or unknown evidence
still qualifies them. Removing August uses July/September for all means, marks
August excluded, and never substitutes June. With one usable month all means and
ratios are null. With only A selected, household still divides A's selected
reserves by both owners' combined valid mean; B reserves/ratio are null.

### v2 basis (SC-split / RD-002, user-directed, 2026-11-01)

Monthly spending is the Reports page's own accounting, not a runway copy:
`report_builder.load_accounting_inputs` -> `_load_transactions` ->
`build_contract` (`build_month_contract`) -> `household_spending`
(`detailed_household_totals` + optional `compute_split`). Household =
`household_totals.total` (home + common + personal_partner_a +
personal_partner_b + trips, net paid - received). Transfers, cc_payments,
savings and excluded sections follow Reports routing; a transfer flag on a
catalog parent no longer drops children (RD-002).

Owner per month, slot by Reports partner-slot map:

- split enabled (both slots owned): `household_totals[slot] - sum(split delta for slot)`
  over split rows in household sections (`delta` for partner_a, `delta_b` for
  partner_b) = fair share on split categories + own net elsewhere; A + B = household.
- split absent/disabled: `household_totals[slot]` (net by payer).

Synthetic 60/40 example (July): home A 10,000 + B 2,000; common A 3,000 + B 1,000
minus a 400 refund (a 600 transfer in common routes to excluded); personal A 500, B 700; trip
A 1,200. Household 18,000. Payer: A 14,700 / B 3,300. Split on home+common:
A 7,200 + 2,160 + 500 + 1,200 = 11,060; B 4,800 + 1,440 + 700 = 6,940.

A Reports pipeline error in one month (unmapped category, non-numeric amount,
missing owner) excludes only that month with `invalid_source`; message text is
dropped (may carry payees). Invalid split/mapping/roles config is global
`invalid_source`, as invalid classification sources were in v1.

## Compatibility and privacy acceptance

- Existing Bills endpoints/shapes, schema-5 snapshots, reports, settings/split,
  and account-binding behavior unchanged. Missing current Bills snapshot cannot
  alone block this result.
- No new route returns transactions, payees, credentials, source-file contents,
  unselected account balances, or financial diagnostic messages.
- All money in the UI, including ARIA/title/tooltip surfaces, passes through
  masking. Ratio display strings are intentionally nonmonetary and stay visible.
- Settings/result load failure must not substitute defaults/mock figures; no
  stale response may overwrite the latest saved-selection generation.

Frontend consumer: `client/src/types/runway.ts` mirrors these DTOs;
`api/runway.ts` uses the existing request helpers with `cache: "no-store"` for
both GETs and PUT. No query, Bills schema field, browser persistence, automatic
sync, or client-side runway calculation is introduced. Static issue copy has a
safe fallback for unknown codes; raw HTTP error details are not rendered.
