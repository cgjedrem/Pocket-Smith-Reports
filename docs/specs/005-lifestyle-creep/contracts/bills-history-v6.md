# Contract: Additive Bills History, Schema 6

**Additive producer update**: New builds now emit schema 7 with separate
snapshot-level report-economy evidence; see
[bills-history-v7.md](bills-history-v7.md). This document still defines the
unchanged outgoing-card block. The default CC reader accepts schema 7;
report mode never reconstructs its groups from this CC-only block.

- **Producer**: Bills builder during explicit sync.
- **Consumer**: Lifestyle-creep service; existing dashboard consumers remain unchanged.
- **Status**: Backend implemented and synthetically verified on 2026-10-31. A later real-data validation is recorded in [quickstart section 16](../quickstart.md#16-post-rebase-real-data-validation).

## Envelope and Compatibility

The existing `BillsSnapshot` gains `schema_version: 6` when rebuilt. Existing `PartnerBills` gains:

```text
cc_spend_history: CCSpendHistory | null = null
```

The Python field is optional/default-null and the legacy client mirror is optional/nullable, so old snapshot models/callers remain accepted by old routes. The new producer must write an explicit history block for every partner; callers without trusted acquisition context write unavailable evidence. Do not rewrite `cc_usage_by_category`, `cc_usage`, events, amounts, title matching, or their old null/zero semantics.

The detector's reader validates only the needed envelope: schema marker, exact month, partner list, stable IDs/display labels/slots, and the additive blocks. It must not use full legacy model defaults to invent identity or evidence. Supported old envelopes (missing schema or integer version 1–5) with absent/null history are `legacy_history`; version 6 with absent/null history is also unavailable legacy/missing evidence, never complete. An old version with a non-null v6 block, an invalid schema value, or an unknown future version is invalid evidence and returns the generic GET error. Other optional legacy fields are ignored by this reader.

Missing partner ID or the legacy empty-string default means `missing_partner_identity`. A present null/non-string/whitespace-only ID, duplicate nonempty partner IDs, or duplicate category/object keys is structural corruption. A missing/empty display label is permitted: fallback to the stable ID. Display slot is optional, default `""`; present values must be `"a"`, `"b"`, or `""` and never determine ownership.

## History Shape

```typescript
type DecimalString = string;

interface CategorySpend {
  title: string;
  amount: DecimalString;
}

interface CCSpendHistory {
  status: "complete" | "partial" | "unavailable";
  reason:
    | "open_month"
    | "future_month"
    | "no_cc_accounts"
    | "missing_source_context"
    | "invalid_source"
    | null;
  scope_key: string | null;
  categories: Record<string, CategorySpend> | null;
  uncategorized_amount: DecimalString | null;
}
```

Category map keys are canonical positive original source IDs. Decimal-string validation and scope hash construction are defined in [data-model.md](../data-model.md). No sentinel key, label-keyed recovery, parent aggregation, float aggregate reuse, or undocumented type coercion.

| State | Required reason | `scope_key` | `categories` | `uncategorized_amount` |
| --- | --- | --- | --- | --- |
| `complete` | null | Valid fingerprint | Map, possibly `{}` | Nonnegative decimal string, possibly `"0"` |
| `partial` | `open_month` | Valid fingerprint | null | null |
| `unavailable` | `future_month`, `no_cc_accounts`, `missing_source_context`, or `invalid_source` | null | null | null |

Mixed states, missing required block members, invalid enums, negative/non-finite money, and wrongly typed amounts are invalid saved structures, not ordinary gaps. Unknown additive object properties may be ignored; known properties remain strict.

## Source-Trust Rules

1. Sync must successfully obtain all transaction pages for the explicit requested full-month date range. Missing transaction input cannot default to an empty list. An actual valid empty returned list can be complete zero with eligible accounts. Sync uses strict pagination for every paginated input, including events and prior-month fallback: a remaining next link at the cap is acquisition failure, not a successful partial list. Legacy non-strict client callers retain their existing truncation behavior.
2. Validate the supplied collection before legacy filtering: object shapes; valid dates belonging to the requested source month; finite numeric amounts excluding booleans; source account and category IDs; status/filter field types; stable ownership; account/exclusion/role context. Explicitly excluded mappings may have null owner/type, including retained mappings absent from the catalog; included ownership/type must remain resolved, and non-null values are validated. Never invent bindings. Known owned CC exclusions remain in the scope fingerprint. Uncategorized means category absent/null or an explicitly absent ID in a valid category object, not a malformed nonnumeric ID. Role context: every stored role value must be a known role, but only keys with the `exclude` role must be canonical category IDs and enter the population and fingerprint; other keys (for example the reports pipeline's synthetic `uncategorized` entry) are ignored.
3. Only acquisition begun after the month closed may establish complete history. Capture that boundary at fetch start, not from builder invocation or the current GET date. An open-month fetch followed by post-midnight building remains partial.
4. A failed transaction fetch or capped paginated sync acquisition must prevent new Bills monthly snapshot publication for the sync attempt. Do not promote prior blocks, publish earlier fetched months opportunistically, or rely on a later budget/status fetch to establish transaction completion. Existing catalog/raw/status writes may precede failure; this is not an all-files transaction.
5. Only successful validated context is passed to the additive builder. Missing context is `missing_source_context`; safely recordable validation failure is `invalid_source`. Do not put the new derivation inside the old broad exception-to-zero fallback. If invalid inputs prevent a safe surrounding build, fail instead of publishing.
6. Existing atomic JSON publication is retained. No read-time rewrites or new result cache.

## Aggregation and Scope

Use the shared posted/outgoing/partner-owned/non-excluded CC population, CC-payment exclusion, transfer exclusion, and exclude-role set. Validate first, then reuse filter membership for Decimal aggregation. Always pass an explicit partner-owned account set; the legacy `None` means all partners and is forbidden here.

Split internal uncategorized yields from identified categories immediately. Keep `-1` internal to old helper behavior, never as a stored or returned source ID. Build label lookup separately from numeric aggregation. Sum nonnegative magnitudes with Decimal; convert to canonical strings for the existing JSON writer.

Fingerprint resolved account ownership/inclusion/exclusions, spending-relevant category sets and calculation version, as specified in the data model. Equal fingerprints mean comparable computation inputs, not identical transactions or balances. Labels do not participate. Do not depend on today's catalog while reading historical evidence.

## Synthetic Fragments

These are history-field fragments, not complete Bills snapshots.

Complete categorized and uncategorized observation:

```json
{
  "status": "complete",
  "reason": null,
  "scope_key": "cc-spend-v1:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "categories": {
    "910001": {"title": "Category A", "amount": "132.001"}
  },
  "uncategorized_amount": "5"
}
```

The hash above is a synthetic opaque token for consumer fixtures, not a producer hash test vector. Producer tests must calculate real fingerprints from synthetic configuration.

Observed zero with eligible accounts:

```json
{
  "status": "complete",
  "reason": null,
  "scope_key": "cc-spend-v1:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "categories": {},
  "uncategorized_amount": "0"
}
```

Valid open-month acquisition:

```json
{
  "status": "partial",
  "reason": "open_month",
  "scope_key": "cc-spend-v1:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "categories": null,
  "uncategorized_amount": null
}
```

No trustworthy acquisition context:

```json
{
  "status": "unavailable",
  "reason": "missing_source_context",
  "scope_key": null,
  "categories": null,
  "uncategorized_amount": null
}
```

## Upgrade / Rollback

- No eager migration or schema-repair command. New evidence is produced only by an explicit successful sync that covers the selected five months, runs through the usual sync end month (at least the current month), and uses one consistent account/category configuration.
- GET never rewrites schema 5, invents source IDs, or promotes partial evidence after rollover.
- Old dashboard routes keep reading old snapshots. The new optional field does not require existing UI consumers to use it.
- Rolling back feature consumption leaves the old title totals usable; no destructive storage transform needs undoing.
- Planned compatibility tests compare legacy field values before/after enrichment, exercise schema-5 dashboard retrieval, and verify old/missing history is not detector-ready.
