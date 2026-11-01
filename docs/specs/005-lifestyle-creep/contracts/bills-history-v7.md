# Bills schema 7: report-economy history

This additive extension does not alter the schema-6 outgoing-card history
contract. New producers write schema 7. Default CC readers accept it and continue
using only `partners[].cc_spend_history`.

## Snapshot-level evidence

`economy_spend_history` has these required members:

| Member | Contract |
|---|---|
| `status` | `complete`, `partial`, or `unavailable` |
| `reason` | null for complete; `open_month` for partial; otherwise `future_month`, `missing_source_context`, or `invalid_source` |
| `scope_key` | `economy-spend-v1:` followed by 64 lowercase SHA-256 hex digits; non-null for complete/partial only |
| `groups` | Exactly three ordered group objects for complete; null for partial/unavailable |

Group order and identity:

| `group_id` | Source detailed sections | `partner_slot` | `partner_id` |
|---|---|---|---|
| `shared` | `home`, `common` | `""` | null |
| `personal_partner_a` | `personal_partner_a` | `"a"` | Saved stable person ID assigned to A |
| `personal_partner_b` | `personal_partner_b` | `"b"` | Saved stable person ID assigned to B |

Each group also has `label: string`,
`categories: { [positiveNumericSourceCategoryId]: {title: string, amount: string} }`,
and `uncategorized_amount: string`. Amounts are finite canonical signed decimal
strings: `"0"`, `"0.2"`, `"-3"` are valid; `"-0"`, `"1.0"`, numbers, exponents and
non-finite values are invalid. Person IDs are nonempty, distinct for A/B, and
never derived from labels. Category IDs are unique across all three groups.
The report's `uncategorized` category requires an explicit valid section mapping
and is kept separate from numeric category IDs.

## Accounting authority

The producer uses `report_builder.load_accounting_inputs`, the report loader's
pure `prepare_transactions` step, `report_builder.build_contract`, and
`accounting.detailed_spending_groups`. That helper composes the same
`_records_in_section` / `_routed_section` and `_category_groups` used by the
detailed Home/Common/personal report sections. Parent inheritance is resolved
by the actual contract builder before aggregation.

- Shared is Home + Common only, not `HOUSEHOLD_COMPOSITION` (which also includes
  personal and Trips), and not the optional percentage settlement split.
- Each category is the exact decimal sum of paid minus received across both
  report owner slots. Positive amounts/refunds reduce spending. Paired
  reimbursements cancel; they are not added a second time.
- Personal placement follows the category section, regardless of which person's
  checking/card account paid. Included checking and card accounts both count.
- Trips, savings, income, excluded and CC-payment **sections** do not contribute.
  CC-payment positive/negative sides are not copied into shared spending.
- The report's transfer routing is authoritative: Home transfers remain Home;
  transfers in Common/personal/Trips route to excluded. Savings/excluded transfers
  stay in those non-comparison sections.
- Savings account roles affect report savings validation/summary, not the
  detailed spending router. An included account with a savings role but a
  Common-category record still appears in Common, exactly as in the report.
  Account type alone is not an extra spending filter.
- Categories retain leaf source IDs, not title keys or a new parent rollup.
  The report's root/leaf display title is retained as metadata.

The reports use floating-point presentation totals. Evidence sums
`Decimal(str(normalized_record.amount))` at sufficient local precision instead
of reusing rounded presentation totals; source population, category IDs, signs
and routing match reports. Display rounding remains separate from exact
threshold decisions.

## Trust and policy fingerprint

Sync already requires complete paginated fetches. The producer receives the
same `MonthAcquisition` used by CC evidence, bound to the exact full-month
collection/date bounds and acquisition-start timestamp. A fetch begun before
month close cannot become complete merely because building finishes later.
Absent context/configuration is unavailable, not zero. Invalid source/config
is unavailable and carries no group amounts; a valid empty closed acquisition
can establish three complete zero-spend groups.

Reports currently do not remove pending transactions. To guarantee both posted
coverage and report parity without silently changing existing reports, schema-7
evidence requires every acquired row to be posted. A pending/unknown/missing
status prevents complete report evidence rather than producing a different
partial spending population. Invalid dates, amounts, owner coverage, exclusion
flags, missing/empty report section policy or category-parent catalog likewise
fail closed. Existing CC evidence keeps its own original filters.

The label-independent fingerprint includes a versioned population/net policy,
the three section memberships, all report account owners and account roles,
all category-section and optional KPI-role mappings, the complete category-parent
map, the excluded-account set, and stable person-to-owner-slot assignments.
Changing an unused policy entry conservatively changes the scope. Titles,
person labels, amounts and percentage settlement configuration are not
classification identity. Invalid settlement configuration can still prevent
context loading because the shared report input loader validates it.

## Rollout, old data and rollback

No migration, repair, eager sync or real-data re-sync is part of this change.
Existing schemas 1–6, and schema 7 with absent/null new evidence, are insufficient
in report mode even when their CC history is ready. A non-null v7 block in a
pre-v7 envelope is incompatible/corrupt, not trusted evidence. Unknown schemas,
invalid blocks, duplicate JSON keys and inconsistent identities fail generically.

To establish usable report history, first fix report mapping/catalog problems,
then explicitly re-sync every selected completed reference and target month
using one consistent configuration and the normal sync window/flow. GET/Retry
never writes, repairs, loads reports/raw sources/current mappings or starts sync.
The API clock still rejects saved claims that an open month is complete.

Client rollout is opt-in via `grouping=report`. Omitting the parameter retains
the old CC response. Rolling back client adoption requires no data rewrite.
An older server that understands only up to schema 6 may reject newly written
schema-7 envelopes; preserve the updated reader when rolling back the UI.
