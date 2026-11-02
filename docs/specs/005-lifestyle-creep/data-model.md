# Data Model: Lifestyle creep detector

## Schema 7 report-economy extension

New Bills builds now emit schema 7 and snapshot-level
`economy_spend_history: EconomySpendHistory | null`. The model default of null
permits older consumers; new builders always emit an explicit block, including
unavailable evidence when no trusted acquisition/context was supplied.
`PartnerBills.cc_spend_history`, its nonnegative `Amount` fields and every older
Bills field retain their semantics.

Complete report history contains exactly three ordered groups, `shared`,
`personal_partner_a`, `personal_partner_b`. Each group stores `group_id`, `label`,
nullable `partner_id`, fixed `partner_slot`, original-ID `categories` and signed
`uncategorized_amount`. Shared has no person ID; personal groups require distinct
stable person IDs. Category IDs are positive numeric source IDs and unique
across the groups; the report's explicit `uncategorized` sentinel is stored only
as the separate uncategorized amount. Net category amounts and report comparison
sample/baseline/spending/change fields are canonical **signed** decimal strings,
not the existing nonnegative `Amount` type.

The history has one coverage state and one scope for the entire snapshot.
Partial/unavailable states carry no group money. The report-mode reader requires
complete, scope-consistent evidence for the entire selected window before
exposing any group's comparison. A group/category cannot migrate between groups
without a scope change. Missing schema-7 evidence in supported older snapshots
is legacy/insufficient, not zero and not a CC fallback.

See `contracts/bills-history-v7.md` for the precise acquisition policy, scope
contents, report semantics, rollout and rollback rules. The schema-6 description
below remains the original outgoing-card contract, not the report-mode source.: Lifestyle creep detector

- **Status**: Backend and client implemented and synthetically verified (2026-10-31). A later real-data validation after a rebase onto main is recorded in [quickstart section 16](quickstart.md#16-post-rebase-real-data-validation).
- **Contracts**: [snapshot v6](contracts/bills-history-v6.md), [GET response](contracts/lifestyle-creep-api.md), [Bills card](contracts/bills-card.md).

**2026-11-02 amendment**: Section 9 supersedes the fixed response/evidence counts and range-wide initial suppression rules in sections 1 and 4–8. Persisted evidence and the original default result are unchanged.

## 1. Types and Numeric Representation

| Type | Meaning and validation |
| --- | --- |
| `Month` | ASCII `YYYY-MM`, year 0001–9999, month 01–12. Target selection may equal the API process current month (`date.today()`), but financial evaluation requires every evidence month strictly before it. Current-month selections return insufficient history without reads or money. |
| `PartnerId` | Existing nonempty stable string from partner mappings; reject non-string/whitespace-only values. Never derive from display label or slot. |
| `CategoryId` | Original source positive integer ID normalized to a canonical decimal string, matching `[1-9][0-9]*`. No Boolean, fractional ID, invented ID, or `-1`. |
| `DecimalString` | Finite base-10 value serialized without exponent, leading plus, unnecessary leading/trailing zeros, or negative zero. Examples: `"0"`, `"132.001"`, `"-30"`, `"20.5"`. Never JSON number, Boolean, null, NaN, or infinity unless a field explicitly permits null. |
| `Amount` | Nonnegative `DecimalString`. Stored observations and uncategorized totals cannot be negative. Differences can be signed. |
| `ScopeKey` | `cc-spend-v1:` plus 64 lowercase SHA-256 hex digits over the canonical spending scope below. Nonempty for complete evidence. |

**New convention, bounded to this feature**: Decimal-string fields preserve exact new aggregates and query values through JSON and Pydantic. Existing snapshot numeric fields and API contracts remain numbers and are not converted. Client formatting may convert strings to finite JS numbers only at the presentation boundary; verdicts never depend on that conversion.

Source transaction numeric values are validated before `Decimal(str(value))`; never use `Decimal(float)` or accumulate a float first. This uses the source value supplied by the existing client, without claiming to recover decimal digits already lost upstream. No new dependency or PocketSmith transport rewrite is introduced.

## 2. Monthly Source Coverage (Internal, Not Persisted Separately)

**Owner**: sync runner, passed explicitly to Bills chain/builder.

| Field/concept | Invariant |
| --- | --- |
| Requested month and start/end dates | Exact first/last day for that month. |
| Acquisition-start date/time | Captured before fetching the month, from the sync process clock (naive `datetime.now()`). |
| Fetch result | All pages returned successfully; transaction collection actually supplied, not a missing-key/default empty list. |
| Input validation | Transaction shapes, numeric values, dates, account identity/ownership and filter inputs valid; ambiguity is not a successful empty observation. |
| Eligible account knowledge | Partner and spending scope resolved from validated mappings/catalog input. |

No new stored sync-status dependency or history manifest is needed. The persisted `CCSpendHistory` block is the resulting source-coverage assertion.

### State transitions

| Acquisition condition | New history state |
| --- | --- |
| Transaction fetch raises | No new Bills snapshot publication for that sync attempt; prior evidence remains unchanged. |
| No trusted acquisition context | `unavailable`, reason `missing_source_context`. |
| Invalid supplied source/filter context | `unavailable`, reason `invalid_source`, if the surrounding legacy snapshot can be built safely; otherwise abort build. |
| Valid context, no eligible CC accounts | `unavailable`, reason `no_cc_accounts`. |
| Valid eligible scope, source month is future | `unavailable`, reason `future_month`. |
| Valid eligible scope, fetch began during source month | `partial`, reason `open_month`. Never promotes by elapsed time. |
| Valid full-range fetch begun after source month closed | `complete`, reason null. Empty transactions may be true zero. |

Error/unknown-source precedence comes before calendar classification. Completing an open-month fetch after midnight does not prove full-month observation. Only a later successful closed-month rebuild can replace partial/unavailable evidence with complete evidence.

## 3. `CCSpendHistory` (Persisted in `PartnerBills`)

| Field | Type | Semantics |
| --- | --- | --- |
| `status` | `complete \| partial \| unavailable` | Built-time source state. |
| `reason` | Enumerated string or null | See [snapshot contract](contracts/bills-history-v6.md). |
| `scope_key` | `ScopeKey \| null` | Comparable effective filter scope; never a display-label hash. |
| `categories` | Map of `CategoryId` to `{title: string, amount: Amount}` or null | Original category IDs only. Empty map allowed only for complete zero categorized observation. |
| `uncategorized_amount` | `Amount \| null` | Qualifying outgoing spend without category ID; outside category map and growth decisions. |

For a smaller unambiguous contract, partial/unavailable blocks carry **no** calculated category or uncategorized amounts: both fields are null. Partial may retain its known scope key; unavailable uses null. Existing Bills fields still supply current-period displays. Complete requires scope, a map (including `{}`), and a nonnegative uncategorized amount (including `"0"`).

New snapshots write `schema_version: 6` and an explicit block for every partner. The optional model field defaults to `None` solely to keep legacy readers/callers compatible; omission is never complete evidence.

**Relationships**: The containing snapshot's `month` is the observation month. The containing partner's stable ID is the owner. Each ID occurs at most once within a month's partner list; each category ID occurs at most once in that partner's map. Duplicate JSON object keys must be caught before parsing can discard them.

## 4. Spending Scope

Use sorted, deduplicated, normalized IDs and stable JSON serialization (`sort_keys`, compact separators, UTF-8) to hash:

- Calculation/filter revision `cc-spend-v1`.
- Stable partner ID.
- Sorted owned credit-card account records: source account ID, stable owner ID, type, and effective excluded flag. Include excluded CC account records so changed eligibility is visible; non-CC balances/names are irrelevant.
- Sorted effective eligible CC account IDs used by the filter.
- Resolved CC-payment category ID or null.
- Sorted effective exclude-role category IDs.
- Sorted effective transfer-category IDs from the validated catalog/filter context; do not derive this set from only categories observed in that month's transactions.
- Fixed policy: posted outgoing only, positive magnitude, refunds not netted, no parent rollup, uncategorized separate.

Transfer flags in eligible transaction categories must agree with the known filter context; contradictory/malformed filter inputs cannot certify complete coverage. An explicit embedded false flag is not a missing flag to be invented from a title.

Exclude labels, account balances, month, timestamps, transaction/category amounts, category presence in that month, unrelated section roles, and display slots. Category catalog additions with no spending-relevant role change do not change the hash. Hashing all raw catalog/mapping data is not this contract.

All five complete blocks for a partner must have the same key. Otherwise mark that partner insufficient and emit `scope_changed` for all five months: the reader cannot identify an authoritative configuration without an extra read. The remediation is to re-sync from the first window month through the usual sync end month (at least the current month) in one run under a consistent account/category configuration.

## 5. History Window and Validation

For viewing month `v`, derive `m0..m4 = v-5 .. v-1`. The latest evaluated month is always `m4`, never `v`. For October 2026, history is May–September and evaluations August/September; for January 2027, history is August–December 2026.

1. Validate query grammar, calendar representability/current-month bounds, and threshold before touching storage.
2. Read only these five exact files, once each. Missing file is a missing observation, not zero.
3. Strictly parse JSON: reject bad encoding/JSON, duplicate keys, non-finite constants, non-object root, malformed partner list, mismatched snapshot month, invalid nonempty IDs, duplicate partner IDs, malformed history, invalid decimal amounts, or unrecognized future schema.
4. Classify supported old/missing history and recorded source states as availability diagnostics. Missing/empty legacy partner IDs are unavailable, not manufactured identities. Null/wrong-type IDs are malformed, not legacy defaults.
5. Discover partners from the union of valid stable IDs across the window; never read current partner/catalog files. Preserve partners that occur in only some months.
6. A partner is ready only with five valid complete matching-scope blocks. No partial baseline exists.

Structural errors invalidate the entire GET. A well-formed recorded `unavailable/invalid_source` is not structurally corrupt: it is a visible explanation that a sync did not establish valid evidence.

## 6. Pure Evaluation

**Input**: One ready partner's five complete history blocks plus exact threshold `p`.

**Category union**: Union all observed category IDs. For each category, fill absent observations with Decimal zero only because all five blocks are already complete. Do not invent an all-zero category when the union is empty.

**Labels**: For each category/partner, choose the newest nonempty label present for that ID anywhere in the selected window; fallback to the source ID string. Within one source month, prefer the validated catalog title for the ID; if absent, choose the lexically first nonempty embedded title, independent of transaction order. If no category label exists, persist an empty title so the reader can still select an older available label before falling back to the ID. Labels never join series or decide ordering.

For amounts `x0..x4`:

| Output | Definition |
| --- | --- |
| Comparison 1 | Evaluation `m3`; baseline months `m0,m1,m2`; baseline sum `T0=x0+x1+x2`. |
| Comparison 2 | Evaluation `m4`; baseline months `m1,m2,m3`; baseline sum `T1=x1+x2+x3`. |
| Baseline amount | `T/3`. |
| Monetary change | `S-T/3`. |
| Rolling growth | `100*(3*S-T)/T` if `T>0`; null otherwise. |
| Strict comparison | `100*(3*S-T) > p*T`, with positive `T`. Exact arithmetic, no division needed. |
| Latest ordinary month-over-month | `100*(x4-x3)/x3` if `x3>0`; null otherwise. |
| Recurring evidence | Count of positive `x0,x1,x2` is at least two. |

Use local Decimal precision sized for exact addition/multiplication from the supplied coefficients and exponents. Default context precision must not accidentally round either side of the inequality. Serialize exact samples/threshold unchanged in value. Serialize repeating derived values at 28 significant digits with round-half-even, canonical decimal notation. Compute output decimals only after the exact verdict; do not feed rounded baseline output into change/growth calculation.

### Category outcome invariants

1. If either baseline sum is zero: `suppression_reason="zero_baseline"`, `is_sustained=false`.
2. Else if fewer than two initial positive months: `suppression_reason="low_frequency"`, `is_sustained=false`.
3. Else: `suppression_reason=null`; `is_sustained` is the conjunction of the two strict comparisons.

`is_sustained=false` with null suppression means **no sustained growth**, not suppressed. Suppression does not change partner readiness. No need for another redundant outcome enum.

Every observed category includes all five samples and both full comparisons, even when unflagged or suppressed. Null percentages require reason-aware presentation; they are not zero. Return the five separate uncategorized observations for ready partners without any growth verdict for them.

## 7. Result and Availability

**Partner result**: `partner_id`, display `partner`, display-only `partner_slot`, ready/insufficient status, category results, and uncategorized samples. Incomplete partners return empty category and uncategorized arrays, plus root issues identifying their missing/affected months.

**Overall status**:

- `ready`: At least one stable partner is present and all discovered partners are ready, with no unresolved identity/coverage issues.
- `partial`: At least one partner ready and another known partner or unassigned legacy partner row incomplete. Preserve ready results and display the incomplete coverage prominently.
- `insufficient_history`: No partner ready, or no stable identity can be established.

An identity-less legacy row contributes an issue with `partner_id=null`, not a fake partner record. If no stable IDs exist, `partners=[]` and diagnostics explain missing/legacy/empty evidence. A missing whole month produces one root `missing_snapshot` issue with null partner ID; its effect applies to every known partner.

Deterministic output: months oldest first; partners lexically by stable ID; categories lexically by canonical ID string; issues by month, null partner before named partners, then partner ID and code. Do not use locale-sensitive title ordering.

## 8. Evolution and Storage Boundaries

This is an additive JSON schema migration, not a relational migration. New producer version is 6; old fields remain intact. The detector accepts supported legacy envelopes as unavailable, never upgrades them by title lookup. An explicit successful sync that covers the five window months and runs through the usual sync end month generates new evidence through the existing writer. GET and Retry never persist, migrate, or initiate acquisition.

No history for runway, debts/assets, subscriptions, forecasts, or persistent thresholds is added. No cross-request result cache or effective-dated mapping store is introduced.

## 9. One Target Month and Reference Period — 2026-11-02 correction

This correction supersedes the earlier selectable evaluation-period amendment in this section and its corresponding fixed-window language in sections 5–7. The user selects one completed target month and a separate contiguous reference period. A percentage threshold is an independent sensitivity input.

### Selection and exact evidence

`Selection` retains `month: str`, `window_months: tuple[str, ...]` and `threshold: Decimal`; the tuple contains every reference month followed by the single target. Derived properties `reference_start` and `reference_end` are the first and penultimate tuple items.

- `month` is the target, exact ASCII `YYYY-MM`, and must be no later than the API process clock's current month. A current-month selection returns `insufficient_history`, no partners, and a null-partner `partial_month` / `open_month` issue before any snapshot read. All evidence must independently pass the closed-month clock check before evaluation; saved `complete` cannot override it.
- `reference_start` and `reference_end` are an optional pair. If supplied, they name an inclusive contiguous range of 2–24 months, each strictly earlier than the target.
- Without explicit reference bounds, use the three months immediately before the target.
- No month is shifted, clamped, skipped, or zero-filled.
- The earliest representable explicit selection is target `0001-03`, references `0001-01..0001-02`.
- The window is exactly `reference_start..reference_end` followed by `month`; an older reference end is valid and requires no extra month read.

| Response field | Invariant |
| --- | --- |
| `month` | One selected target month. Current API month is selection-only and cannot carry a financial evaluation. |
| `reference_start`, `reference_end` | Required, valid, echoed inclusive bounds; 2–24 contiguous reference months. |
| `window_months` | Required evidence: exactly the reference months followed by target; 3–25 entries, not a read log. |
| `evaluation_months` | Compatibility field containing exactly `[month]`. |
| `baseline_months` | Integer reference count, 2–24. |
| `LifestyleCategory.samples` | One amount for every `window_months` value. |
| `LifestyleCategory.comparison` | One comparison for target against all reference months. |
| `Comparison.baseline_months` | Exactly the selected reference months; 2–24 entries. |
| Ready `uncategorized_samples` | One amount for every evidence month, including observed zeros. |
| Incomplete partner arrays | Empty; never a partial-length money series. |

Every reference and target snapshot participates in identity/category union, labels, completion and scope checks. Scope mismatch identifies every required evidence month. A missing or invalid snapshot blocks the partner; an absent category in a ready complete snapshot means zero. Uncached reads are bounded to the selected references and target.

### Exact category comparison

For category amounts `x[0..r-1]` across the `r` reference months and target amount `S=x[r]`, define `T=sum(x[0..r-1])`, reference count `r`, and `N=r*S-T`. The exact mean is `T/r`.

- `baseline_amount = T/r`.
- `spending_amount = S`.
- `change_amount = S - T/r`.
- `growth_percent = 100*(r*S-T)/T` when `T>0`, otherwise null.
- A strict threshold exceedance requires `T>0`, positive spend in at least two distinct reference months, and `100*(r*S-T) > p*T`.
- `is_above_threshold` is false when either baseline suppression applies. Equality does not exceed.
- `suppression_reason="zero_baseline"` when `T=0`; otherwise `"low_frequency"` when fewer than two distinct reference months have positive spend; otherwise null.

Use local Decimal precision sized for exact addition and multiplication. The verdict uses the cross-product inequality, not rounded outputs. Serialize repeating explanatory averages, changes and percentages at 28 significant digits with round-half-even. Never use binary floats or response display values to decide outcomes.

`latest_month_over_month_percent` is retained for compatibility. Derive it only when `reference_end` is the calendar month immediately before the target, using the target and that end-month sample; otherwise return null. Return null as well when the prior-month amount is zero. It does not replace comparison growth.

All target and reference samples remain available even when a category is suppressed. Preserve stable category IDs and newest nonempty labels. Preserve uncategorized samples for every month, but do not evaluate an uncategorized growth verdict.
