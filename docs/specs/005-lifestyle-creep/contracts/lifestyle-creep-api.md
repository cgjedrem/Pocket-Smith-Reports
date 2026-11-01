# Contract: Lifestyle Creep GET

**Additive report-group mode**: The default contract below remains the
outgoing-card mode. Supplying `grouping=report` explicitly selects the broader
detailed-report population defined in this amendment.

## Report-group mode

`GET /api/bills/lifestyle-creep?month=YYYY-MM&grouping=report`
accepts the same optional paired `reference_start`/`reference_end` (2–24
consecutive completed reference months, both before target) and separate
`threshold_percent` (1–100, default 20). Omitting the pair defaults to the prior
three months. Invalid/repeated grouping or selection parameters return 400
before resolving storage paths; the only supported supplied grouping is
`report`. All responses, including 400/500, retain `Cache-Control: no-store`.

The report response retains the existing selection identity members exactly:
`month`, `reference_start`, `reference_end`, `window_months`,
`evaluation_months: [month]`, `baseline_months`, `threshold_percent`.
It adds `grouping: "report"` and uses `groups`, **not** `partners`:

```typescript
type GroupId = "shared" | "personal_partner_a" | "personal_partner_b";
type ReportGroup = {
  group_id: GroupId;
  label: string;
  partner_id: string | null;
  partner_slot: "" | "a" | "b";
  status: "ready" | "insufficient_history";
  categories: ReportCategory[];
  uncategorized_samples: { month: string; amount: string }[];
};
```

`groups` is always exactly three entries in that order, including for missing
or open-month evidence. Shared has null `partner_id`/empty slot; ready personal
groups have distinct stable saved person IDs and A/B slots. With no valid saved
metadata, insufficient groups use neutral labels, null person IDs and fixed
group IDs/slots, never current settings. Use `group_id` plus `category_id` for
view-only category identity; shared is not a fabricated person.

`ReportCategory` has exactly the existing category explanation members:
`category_id`, `category_title`, `samples`, `comparison`,
`latest_month_over_month_percent`, `is_above_threshold`,
`suppression_reason`. Samples/uncategorized samples and comparison
`baseline_amount`, `spending_amount`, `change_amount` are **signed canonical
decimal strings**. Comparison retains `month`, `baseline_months`, and nullable
`growth_percent`. No new total/ownership allocation is implied.

For reference total T, count r, target S and threshold p, the shared evaluator
requires T > 0, at least two strictly positive reference samples, and the exact
strict inequality `100*(r*S-T) > p*T`. Equality is false. Suppression is
`zero_baseline`, `negative_baseline`, `low_frequency`, or null, in that order of
precedence. Growth is null for nonpositive baseline; adjacent month-over-month
growth is null for nonpositive previous spending or a non-adjacent reference
end. Amount/change explanations remain present for suppressed categories,
including refunds/negative target spend. Only explanatory division is rounded
at 28 significant digits; verdicts use exact cross-products.

Overall `status` is `ready` or `insufficient_history`. Any missing/partial/
unavailable/legacy window member, changed scope or changed saved person-slot
assignment blocks **all three** groups and removes their category/sample money.
Corrupt evidence anywhere produces the existing generic 500 rather than a
partial response. Category IDs cannot appear in multiple response groups.

`issues` retain the existing `{month, partner_id, code, reason}` members and
add nullable `group_id`. Current issues are file-window-wide, with null
person/group IDs; they apply to all groups. Existing codes are reused, notably
`legacy_history`, `missing_snapshot`, `partial_month`, `unavailable_history`
and `scope_changed`. `history_guidance` is null when ready, otherwise a visible
operational explanation to use completed months, check report mappings and
explicitly re-sync every selected month consistently. Reading/Retry never
creates evidence. This is coverage guidance, not financial advice.

The API reads exactly the selected 3–25 Bills files once each (or zero when the
API clock guard blocks the target/window), never current configuration, raw
transactions or report files. It performs no writes/network/sync. Schemas 1–6
cannot establish report coverage; even valid CC blocks are never substituted.
See [bills-history-v7.md](bills-history-v7.md) for precise report accounting and
re-sync/rollback policy. Existing outgoing-card clients must omit `grouping`;
no old response field is silently reinterpreted.

- **Path**: `GET /api/bills/lifestyle-creep`
- **Purpose**: Compare one completed target month of saved CC category spending against a selected reference-period average. No sync, forecast, or financial recommendation.
- **Correction**: The 2026-11-02 one-target/reference-period semantics replace the earlier multi-month evaluation-period amendment. The earlier implementation's endpoint shape is not the current contract.

## Request

```http
GET /api/bills/lifestyle-creep?month=2026-10&reference_start=2026-07&reference_end=2026-09&threshold_percent=20
```

| Query | Required/default | Validation |
| --- | --- | --- |
| `month` | Required; one target month | Exact ASCII `YYYY-MM`; real month/year; no later than the current month on the API process clock (`date.today()`). Financial evaluation requires strictly earlier; current month returns insufficient history without reads. |
| `reference_start` | Optional, only together with `reference_end` | Inclusive first reference month; exact ASCII `YYYY-MM`, valid calendar month. |
| `reference_end` | Optional, only together with `reference_start` | Inclusive last reference month; valid month, not before start, strictly before `month`. The contiguous inclusive reference range must contain 2–24 months. |
| `threshold_percent` | Omission only defaults to 20 | Finite decimal value from 1 through 100 inclusive. Decimal fractions valid; no rounding or clamping. |

When both reference bounds are omitted, use the three calendar months immediately preceding `month`. Explicit reference periods may end before the month immediately before target; do not extend, shift, or clamp the range. Frontend requests should supply all three month values.

The earliest valid target is `0001-03`, with reference months `0001-01` and `0001-02`. For explicit bounds, `reference_start` may be `0001-01`. Future targets are rejected. No month is zero-filled or inferred.

### API/browser month-boundary handling (T052)

The browser still excludes its own current month. If its latest completed
local target is the API's current month, a fully valid selection returns HTTP
200 with `status="insufficient_history"`, `partners=[]`, and one issue:
`{month: <target>, partner_id: null, code: "partial_month", reason: "open_month"}`.
The target, reference bounds, threshold, `window_months`, and compatibility
fields echo the selection unchanged. `window_months` describes required
evidence, not a read log. No paths are resolved, no snapshots are read, and no
partner identity, category amount, comparison, or verdict is exposed.

All query validation still runs first; malformed current-month selections
return 400. Future targets return 400 with detail
`month must not be later than the current month`. Before reading history the
service rechecks **every selected evidence month** against its current clock.
An open month blocks all evaluation, regardless of a saved `complete` status.
If the clock moved backward after validation, future evidence also blocks all
reads and returns `unavailable_history` / `future_month` issues.
After closure, saved partial evidence remains partial until explicitly
re-synced; elapsed time alone never promotes it.

Threshold strings must match ASCII decimal syntax: optional sign, digits with optional decimal point (or leading decimal point followed by digits), optional `e`/`E` exponent with optional sign and digits. Examples accepted in range: `20`, `20.5`, `020.50`, `2e1`, `100`. Canonical response values are respectively `"20"`, `"20.5"`, `"20.5"`, `"20"`, `"100"`. URL-encode any plus sign. Whitespace, underscores, commas, blank strings, booleans, `null`, `NaN`, and infinities are rejected. Parse as Decimal, not through float. Out-of-range values are rejected exactly.

Repeated `month`, `reference_start`, `reference_end` or `threshold_percent` parameters return 400, even when repeated values agree. Unknown unrelated query parameters follow the framework convention and are ignored. Partial pairs and explicitly empty bounds are invalid. All query checks finish before resolving a storage path.

## Responses

Every response from this route, including errors, has `Cache-Control: no-store` and JSON content type.

| HTTP | Meaning | Body |
| --- | --- | --- |
| 200 | Evaluated availability: ready, partial, or insufficient | `LifestyleCreepResponse` |
| 400 | Invalid, missing, or repeated query | `{ "detail": "<validation message>" }` |
| 500 | Unreadable, corrupt, structurally invalid history, or unexpected evaluation error | `{ "detail": "internal error reading lifestyle creep history" }` |

Missing monthly history is represented in the 200 availability body, not a 404. Error details must not expose file paths, financial data, exception text, or raw query content.

## Response Types

Decimal fields are strings, not JSON numbers, except integer counts. This feature-local convention preserves precision.

```typescript
type DecimalString = string;
type Month = string;

interface LifestyleCreepResponse {
  month: Month; // selected target; current API month cannot be evaluated
  reference_start: Month;
  reference_end: Month;
  window_months: Month[]; // reference months, then target; 3–25
  evaluation_months: [Month]; // compatibility field: exactly [month]
  baseline_months: number; // reference count, 2–24
  threshold_percent: DecimalString;
  status: "ready" | "partial" | "insufficient_history";
  issues: HistoryIssue[];
  partners: LifestylePartner[];
}

interface HistoryIssue {
  month: Month;
  partner_id: string | null;
  code:
    | "missing_snapshot"
    | "legacy_history"
    | "partial_month"
    | "missing_partner_identity"
    | "missing_partner"
    | "unavailable_history"
    | "scope_changed"
    | "no_stable_partners";
  reason:
    | "open_month"
    | "future_month"
    | "no_cc_accounts"
    | "missing_source_context"
    | "invalid_source"
    | null;
}

interface MonthlyAmount {
  month: Month;
  amount: DecimalString;
}

interface LifestylePartner {
  partner_id: string;
  partner_slot: "a" | "b" | "";
  partner: string;
  status: "ready" | "insufficient_history";
  categories: LifestyleCategory[];
  uncategorized_samples: MonthlyAmount[];
}

interface LifestyleCategory {
  category_id: string;
  category_title: string;
  samples: MonthlyAmount[]; // every reference month and target
  comparison: Comparison;
  latest_month_over_month_percent: DecimalString | null;
  is_above_threshold: boolean;
  suppression_reason: "zero_baseline" | "low_frequency" | null;
}

interface Comparison {
  month: Month; // target
  baseline_months: Month[]; // exactly reference_start..reference_end
  baseline_amount: DecimalString; // arithmetic mean
  spending_amount: DecimalString; // target actual
  change_amount: DecimalString; // target minus mean
  growth_percent: DecimalString | null; // relative to positive mean
}
```

## Cardinality and calculation

- `window_months` is exactly the selected contiguous reference months followed by `month`; the target need not immediately follow `reference_end`.
- `evaluation_months` remains as a compatibility field and contains only `[month]`.
- `baseline_months` is the selected reference count. Each category has one `comparison` with the same reference-month list and the target month.
- Ready partners include all target and reference samples, including observed zero amounts. Incomplete partners have empty categories and uncategorized samples; unknown values are never filled with zero.
- For a category, let `r` be reference count, `T` the exact sum of reference amounts, `S` target spend, and `p` the threshold. Baseline mean is `T/r`; exact threshold exceedance requires `T>0`, at least two positive reference-month amounts, and `100*(r*S-T) > p*T`. Equality does not exceed.
- `suppression_reason` is `zero_baseline` when `T=0`; else `low_frequency` when fewer than two distinct reference months have positive spend; else null. Suppression does not erase samples or monetary comparison details.
- `growth_percent` is `100*(r*S-T)/T`, null only for zero mean. `latest_month_over_month_percent` is computed only if `reference_end` is the month immediately before target; otherwise null. For an adjacent end, it uses target spend versus that reference-end sample and is null when that prior sample is zero.
- Derived repeating values use 28 significant digits, round-half-even, after exact verdict calculation. No float or rounded response value determines `is_above_threshold`.
- Stable IDs determine ordering. Labels and partner slots are display-only.

## Availability diagnostics

| Code | Partner identity | Meaning/action |
| --- | --- | --- |
| `missing_snapshot` | null | Required reference or target snapshot absent; affects every known partner. Re-sync required. |
| `legacy_history` | Stable ID when known | No reliable additive block. Re-sync; no title recovery. |
| `partial_month` | Stable ID, or null for API-clock gate | Stored partial evidence, or an evidence month still open on the API clock. Wait for closure; re-sync saved partial history after closure. |
| `missing_partner_identity` | null | Legacy row has absent/empty identity. No synthetic partner row. |
| `missing_partner` | Stable ID | Partner known elsewhere in selected evidence absent from an existing month's list. |
| `unavailable_history` | Stable ID, or null for API-clock gate | Well-formed unavailable block with its exact reason; or `future_month` after clock recheck, with no reads. |
| `scope_changed` | Stable ID | Evidence blocks do not share scope; report every selected month. |
| `no_stable_partners` | null | Present empty partner lists with no stable partner identity. |

If no partner is ready, status is insufficient. If one is ready and another known or unassigned legacy partner is incomplete, status is partial. Only complete coverage of the discovered stable partner population with no unresolved identity gaps is ready.

## Synthetic success example

Three reference months at 100 and target spend 130, with threshold 20:

```json
{
  "month": "2026-10",
  "reference_start": "2026-07",
  "reference_end": "2026-09",
  "window_months": ["2026-07", "2026-08", "2026-09", "2026-10"],
  "evaluation_months": ["2026-10"],
  "baseline_months": 3,
  "threshold_percent": "20",
  "status": "ready",
  "issues": [],
  "partners": [{
    "partner_id": "partner_a",
    "partner_slot": "a",
    "partner": "Partner A",
    "status": "ready",
    "categories": [{
      "category_id": "910001",
      "category_title": "Category A",
      "samples": [
        {"month": "2026-07", "amount": "100"},
        {"month": "2026-08", "amount": "100"},
        {"month": "2026-09", "amount": "100"},
        {"month": "2026-10", "amount": "130"}
      ],
      "comparison": {
        "month": "2026-10",
        "baseline_months": ["2026-07", "2026-08", "2026-09"],
        "baseline_amount": "100",
        "spending_amount": "130",
        "change_amount": "30",
        "growth_percent": "30"
      },
      "latest_month_over_month_percent": "30",
      "is_above_threshold": true,
      "suppression_reason": null
    }],
    "uncategorized_samples": [
      {"month": "2026-07", "amount": "0"},
      {"month": "2026-08", "amount": "0"},
      {"month": "2026-09", "amount": "0"},
      {"month": "2026-10", "amount": "0"}
    ]
  }]
}
```

## Storage and execution contract

- Validate all query fields before storage path resolution. Invalid selections cause zero reads.
- Before any path resolution/read, independently check every required month against the API clock. Open/future evidence returns insufficient history with no partners and zero snapshot reads; saved completion cannot override the clock.
- An otherwise valid, closed-month evaluation reads exactly each selected reference month and the target, oldest first, once each: 3–25 snapshot reads. It does not read months between `reference_end` and target when there is a gap.
- Resolve paths only with validated month values and `storage.bills_dashboard_path`. No directory scans, fallback paths, current-month snapshot, source transaction reads, config/catalog reads, sync, writes, or result cache.
- Parse and validate every loaded snapshot before exposing any calculation. Corruption cancels the GET; a missing file is a readiness issue.
- Retry rechecks the clock for the same selection, then reopens snapshots only if all required months are closed. Existing per-file atomic replacement is unchanged; no multi-file transaction guarantee is added.
