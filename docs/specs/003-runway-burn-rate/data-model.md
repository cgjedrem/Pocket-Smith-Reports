# Data Model: Runway & Burn Rate

**Date**: 2026-10-31
**Status**: Backend v1 and typed frontend consumer implemented; see [plan.md](plan.md) for the actual gate
disposition and [quickstart.md](quickstart.md) for executed validation.

No database or migration. One new local settings file, all other entities
read-time only. The normative JSON response fields are in
[contracts/runway-api.md](contracts/runway-api.md).

## 1. Runway selection

Persist at `storage.PRIVATE_DATA_DIR / "runway_config.json"`:

```json
{"schema_version":1,"liquid_account_ids":["1100001","1100006"]}
```

IDs above are synthetic. Fields: version integer exactly 1; IDs an ordered array
of unique canonical positive decimal ID strings (`^[1-9][0-9]*$`). Request IDs
are strict strings, not numbers, booleans, whitespace, or coerced values. Preserve
submitted order; order never changes arithmetic. No extra persisted fields.

Relationships: selected ID references one catalog account and its current binding;
binding references a configured owner. Store no balance, owner, name, currency,
timestamp, ratio, or legacy binding flag.

States:

| State | Meaning | Behavior |
|---|---|---|
| `unconfigured` | File absent | Empty IDs; no GET write; selection required. |
| `empty` | Version-1 file explicitly contains `[]` | Intentional reset; not zero reserves. |
| `valid` | Nonempty structurally valid selection; all accounts eligible | Calculate available observations. |
| `invalid` | IDs readable but a selected account became ineligible | Retain IDs and invalid rows; never silently repair. |
| Settings read error | Corrupt JSON, unsupported version/shape, unreadable file | Settings endpoint fails; Save disabled. Result can return `invalid_settings` without a fabricated selection. |

PUT accepts only `liquid_account_ids`. Nonempty selections require every account
to exist uniquely in the catalog and bindings, have a configured owner, be
non-excluded checking/savings, and have a usable finite recorded balance. A zero
or negative **valid** balance is selectable. Reject entire invalid request before
writing. Empty selection is a valid explicit reset, not automatic repair.

Known currency conflicts are not an account-eligibility rule: individual eligible
accounts may be selected; incompatible aggregation is then explicitly unavailable.
Validate again on every result, since mappings/catalog can change after Save.

## 2. Account owner and account

Owner identity comes from `account_mappings.partners` keys. Use its configured
`label`; a missing label falls back to the stable ID, not a positional person.
Optional display slots follow existing sorted-ID `a`, `b`, then neutral `""`.
Custom/reversed IDs and labels never affect attribution.

An account has:

- canonical ID; name (catalog name, binding name, then ID for a missing entry);
- current `partner_id` and identity display metadata;
- current type and exclusion flag;
- selected/eligible flags and specific eligibility reasons;
- recorded `current_balance` only when selected and readable;
- currency evidence and `current_balance_date`, each optional and distinct;
- catalog collection evidence, never an implied bank balance timestamp.

Catalog duplicate account IDs are ambiguous and invalidate affected lookups.
Unselected balances are checked only for picker eligibility; malformed ones
never block selected reserves. A picker marks that account ineligible without
exposing its money.
Malformed/unowned non-excluded spending bindings cannot be ignored to label a
mapped subset as the household.

A selected removed account stays in the response. If its binding still identifies
an owner, only that owner and household reserve sums are blocked. If no owner can
be resolved, every potentially affected owner reserve sum and household sum is
unavailable: do not guess the former owner or persist historical ownership.
Valid current reassignment changes attribution and is visible in account rows.

## 3. Local source bundle

Exact known inputs; no glob or filename fallback:

| Source | Consumed fields / purpose |
|---|---|
| `runway_config.json` | Version and explicit selection. |
| `account_mappings.json` | Configured owners/labels, bindings, exclusions, owner savings-category IDs. Required for attribution. |
| `account_catalog.json` | `accounts` identity, current selected balances, optional account currency/date. Required for reserves and picker; missing currency metadata may qualify spending rather than block it. |
| `category_catalog.json` | Category IDs, titles, transfer flags (null/absent is not a transfer; a non-null value must be boolean), tree/descendants for identified exclusions. |
| `category_roles.json` | Category ID to relevant role; missing file means no configured role override, not invented mappings. |
| `detailed_section_mapping.json` | Only relevant `category_sections`: `cc_payments`, `excluded`, `savings`; investment exclusion comes from category roles. Do not validate/read unrelated section/account-role logic. |
| Three exact `{YYYY-MM}_ps_raw.json` files | Raw recorded monthly transactions and optional explicit provenance. |
| `.sync_status.json` | Detect running sync/change only; no collection or completeness proof. |

Missing optional classification files mean no configured overrides from that
file. Present unreadable/invalid consumed structures are explicit invalid source,
not an empty dictionary. Missing category catalog can still use embedded category
evidence and configured IDs but must add `classification_unverified`; no claim
that every possible repayment was discovered. Missing both identity/binding
authority and assignable spending makes the affected observation unavailable.
Only referenced classification values and valid tree structure needed for
exclusions are validated; unrelated reports/config are not examined.

Read bytes/existence for the fixed bundle, parse in memory, then re-read/compare
before publishing the result. Changing bytes/existence or running sync produces
`sources_changing`; no silently mixed calculation and no automatic sync.
Optional files that appear/disappear participate in this check. No generation
manifest or filesystem lock is introduced. Atomic settings replace handles the
single written file; it cannot freeze later mapping edits, hence read-time
revalidation.

### Optional provenance reader

Existing raw arrays remain accepted with unknown evidence. The already-supported
transaction envelope shape may additionally carry this **new read-only**
runway evidence contract:

```json
{
  "transactions": [],
  "provenance": {
    "collected_at": "2026-10-01T00:15:00+00:00",
    "coverage_start": "2026-09-01",
    "coverage_end": "2026-09-30",
    "complete": true
  }
}
```

This is a synthetic source illustration, not a planned source write or claim that
sync currently emits metadata. Existing `sync_runner` writes bare arrays.
The feature does not backfill or require this envelope for positive history.
An optional catalog `provenance.collected_at` is treated similarly; absent means
unknown. Only explicitly named evidence is read, not arbitrary timestamp aliases.

`collected_at` is an offset-aware ISO datetime. Coverage bounds are ISO dates,
inclusive. Explicit `complete` is boolean. A complete claim requires both exact
month bounds and collection at or after next-month local midnight. Partial bounds,
`complete:false`, or known early collection exclude the month. A `complete:true`
claim missing required evidence is invalid. No completeness claim plus absent
bounds/date is unknown; contradictory or malformed claimed evidence is invalid.
Future collection timestamps are invalid; future balance dates qualify as
`balance_date_unverified`, never as fresh bank data.

Bank date-only values remain date-only in responses; for the 24-hour warning use
the start of that local date conservatively and label the date precision. Datetime
dates must include an offset. Invalid optional balance-date syntax yields an
explicit unknown-date qualification, not a zero balance or a fabricated timestamp.
Local midnight resolves the system offset for that specific date (including DST),
not today's offset. Equivalent offset-aware collection instants count as one time.
Do not infer source collection from source mtime, Bills `synced_at`, catalog
`start/end`, or `.sync_status.last_sync`.

## 4. Transaction observation and exclusions

Required consumed fields: positive integer or canonical-string `id`;
`transaction_account.id` with the same ID rules; ISO date `date` within the
candidate month; `status` exactly `posted` or `pending`; finite decimal `amount`.
Bool/null/absent IDs or money are invalid. Unknown posting states are invalid,
not silently posted. Category may be null/absent for an uncategorized purchase.
Validate optional transfer flags as booleans when present. JSON `null` counts as
absent: not a transfer, matching `v4_pipeline/accounting.py`. Real PocketSmith
transactions carry `"is_transfer": null` on many rows (RD-001). Any other
non-null, non-boolean value (for example `"true"`, `1` or `0`) still invalidates
the month. This applies to the transaction, embedded category and category
catalog `is_transfer`; in the catalog it makes classification unusable, so no
candidate month is included. The account-binding `excluded` flag is user
authored, not PocketSmith-sourced, and stays strict.

Normalize valid numeric source IDs to canonical strings. Deduplicate identical
records by stable transaction ID after ignoring JSON object-key order. Conflicting
copies of that identity across any candidate source invalidate every affected
month, including conflicting metadata. Scan identity consistency before accepting
the common window, even when another source is partial or contains invalid rows;
do not try to select the newer one. Distinct IDs with equal values stay distinct.
Out-of-month or malformed dates invalidate the source even on a record that would
otherwise be excluded. Apply identity/date/amount/posting validation to raw records,
not arbitrary unrelated upstream profile fields.
An embedded category title, when present, must be a string before using
classification metadata. Malformed title shapes invalidate the observation;
never stringify a list/object into repayment evidence.

Classify valid records in this order:

1. Exclude known excluded account, pending state, nonnegative amount, and either
   transaction/category transfer flag that is `true` (null or absent is `false`).
2. Exclude savings/investment account types, configured savings overrides, excluded/
   savings/investment category roles, and configured excluded/repayment sections.
   Expand relevant catalog category parents to descendants; any applicable
   exclusion wins. Consider catalog and embedded transfer evidence.
3. Exclude every catalog category identified by the existing `"cc payment"` title
   convention and descendants, not just the first match. Both repayment legs are
   excluded; the positive leg never contributed to gross spending anyway.
4. Remaining negative posted checking/card records require a mapped configured
   owner. Unmapped/ambiguous non-excluded potential spending invalidates the month.
   Do not infer account type/owner from account name or position.
5. Add absolute amount to the identified owner's gross recorded spending.

No salary/event totals, planned CC purchases, current/future records, repayment
netting, or shared-split allocation. Negative posted uncategorized purchases count.

## 5. Monthly spending observation

Exactly three candidate rows in ascending order. Each contains month,
`included | excluded`, reasons, coverage state (`complete | unverified | partial |
invalid | missing`), source collection evidence, owner observations, and household
observation where currency permits aggregation.

Exclusion due to missing/invalid/partial source applies to the whole month, not
selected records or a different window for each owner. A zero owner observation
requires complete-period evidence; unknown household-positive history does not
prove that owner's zero. Positive owner observations with unknown coverage can
contribute, qualified as recorded transactions only.

All included months contribute to all reported means. At least two are required.
Valid included zeros count in the divisor. Excluded-month spend fields are null,
not zero; do not display an independently computed partial subtotal as usable.
Expose every exclusion even if the remaining two months suffice.

## 6. Currency and numeric measures

Currency codes, when present, are nonempty three-letter alphabetic ISO-code
evidence normalized uppercase. Do not infer currency from `kr` or a locale.
Resolve transaction `currency_code`, embedded account `currency_code`, and catalog
account `currency_code`; known disagreement within a consumed transaction or
owner-month invalidates that observation for the common window.

Different owners can have individually homogeneous but mutually incompatible
currencies: retain their observations and common included months, but return
household money/mean/ratio null with `currency_conflict`, never sum them. Likewise,
an owner's currency changing across months blocks its mean and the household
mean without inventing a conversion. A conflict between an owner's selected
reserves and spending blocks its ratio, not its separately valid observations.
One affected owner does not erase another valid owner's result.

Missing currency evidence on any contributing amount qualifies the affected
measure/result as `currency_unverified`. A sole observed code may be reported but
is not evidence for unknown records. No known code yields `currency_code:null`
and the visibly assumed existing household display unit. Currency evidence for
excluded movements does not contaminate eligible spending.

Use Decimal internally; emit only finite JSON numbers, preserving sign and
valid zero. Availability checks precede display rounding. A numeric serialization
overflow or positive underflow must be an explicit invalid-source result, never
NaN/infinity/false zero.

Implementation uses a calculation-local Decimal precision of 700 to cover the
finite JSON-float exponent range and signed cancellation without intermediate
rounding to binary floats. Present JSON `null` sources and duplicate object keys
are invalid, not equivalent to a missing optional file. Malformed consumed
structures fail closed; unrelated classification entries remain outside validation.

For each owner and household:

```text
average_monthly_spending = sum(spending for common included months) / count
selected_reserves = sum(signed balances of exactly selected eligible accounts)
runway_months = selected_reserves / average_monthly_spending
```

Household sums unique account IDs once and all owner spend once; it does not average
ratios. Owner no-selection reserves are null; household nonempty selection can
remain valid without selecting accounts for every owner.

The ratio requires valid comparable measures, >=2 months, reserves >0, and mean
>0. Otherwise it is null. Keep known zero/negative reserves or a zero mean visible.
Round the positive ratio to one decimal with Decimal half-up for
`runway_display`; values below 0.05 produce `<0.1`. The unrounded `runway_months`
remains the numeric metric; there is no historical ratio field.

## 7. Result state and evidence

- `unavailable`: ratio null; all blocking reasons and applicable qualifications
  present, even if some component measures are usable.
- `qualified`: ratio valid but any excluded month, stale/unknown date, unverified
  coverage/classification/currency, or differing source-time limitation applies.
- `available`: ratio valid and no such limitations. This is not a guarantee or
  forecast; historical collection timestamps normally make actual results qualified.

Use arrays of structured issues, not one reason that hides others. A primary
display reason may be chosen deterministically: settings/source consistency,
invalid selection/balance/currency, no selection, insufficient history,
nonpositive reserves, nonpositive burn. Always make the complete list accessible.
Issue parameters contain only safe identifiers, dates, and counts, never money,
raw transactions, payees, credentials, file contents, or exception reprs.

Response dates distinguish `calculated_at`, server `as_of_month`, collection dates,
and per-account bank balance dates/precision. Unknown remains null with a reason;
older-than-24-hours means stale. Differently captured sources are not called one
verified synchronized snapshot. No automatic freshness timer/server poll required;
the next explicit refresh recalculates window and qualifications.

## 8. UI lifecycle state (not persisted)

Keep separate result request generation, saved IDs, draft IDs, settings load state,
save state, and optional retained result. Settings load failure disables Save;
Save failure retains draft; Save success updates saved IDs then starts a newer
result generation. A late old response cannot overwrite it. Retained older figures
must be labelled, not presented as confirming new settings. No localStorage,
shared response cache, or Bills store hydration for runway data.

Privacy changes only presentation: render-time money formatting/masking applies to
text and attributes; no network request or draft reset. Read errors use static
safe copy and action labels; the unavailable result is not a transport error.

Implemented frontend: `useRunway` holds independent request generations, saved
settings, draft IDs, loading/error/save state and the optional retained result.
Successful Save clears old figures before starting the new result request; failed
Save keeps the draft and last loaded result. A result-load failure after successful
Save is reported separately from persistence success. Settings reload is explicit
and discards the draft; privacy and Bills display-window changes do not reload it.
Amounts use existing `formatKr`/`maskAmount`; a known non-NOK currency retains the
same numeric formatting with its own code, never an implied conversion or kr label.
