# Research: Runway & Burn Rate

**Date**: 2026-10-31
**Scope**: Feature 003 planning research. Subsequent local implementation
authorization and validation are recorded in plan/tasks/quickstart.

## Evidence and method

Read the supplied read-only discovery report at
`1793465902647-copilot-tool-output-6e1b5392320945d5b3fa7b9c885405d1.txt`
(caller-supplied temporary discovery artifact; machine-specific path omitted).
Targeted source reads resolved the decisions below. No agents, application imports,
tests, servers, network requests, private files, or main-checkout inspection were
used. The report is an input, not a generated repository artifact.

Authorities: [spec.md](spec.md), `.github/skills/speckit-plan/SKILL.md`,
`.specify/memory/constitution.md` (1.0.2), the resolved plan template, and
`.specify/extensions.yml`. Findings describe inspected source; decisions describe
proposed implementation. No product-design clarification remains open. Governance
blockers remain in [plan.md](plan.md#constitution-check).

## R1 — Independent read-time calculation

**Decision**: Add `GET /api/bills/runway`, `GET /api/settings/runway`, and
`PUT /api/settings/runway`. Use one thin router, one models module, and one
runway service with pure calculation helpers and a small local-file adapter.

**Rationale**: `bills_builder.py:1068–1137` coerces missing/error CC spending
to zero; current-month snapshots do not supply completed-month checking spending.
`bills_derivations.py:74–109` and the builder's balance chain use an implicit
checking/savings anchor, not explicitly selected reserves. Reading snapshots cannot
establish this feature's provenance. Read-time calculation also applies selection
changes and calendar rollover without a sync.

**Alternatives considered**: Extending schema-5 Bills snapshots; recalculating old
snapshots; consuming `bills-source` (which has a mock fallback). Rejected: false-zero,
projection, compatibility, and coupling risks. Do not change Bills/report schema or
calculation versions, or write a runway snapshot/cache.

## R2 — Separate, explicit selection

**Decision**: Store only `{schema_version: 1, liquid_account_ids: [...]}` in
`runway_config.json`. Compute its path from `storage.PRIVATE_DATA_DIR` at call time.
Use `atomic_write_json`; absent GET synthesizes an unsaved empty selection and
does not write. PUT forbids extra fields and validates the entire unique selection
against current catalog, bindings, owner identities, eligibility, and balances.

**Rationale**: `routers/accounts.py:93–139` replaces known binding fields, and
the pipeline rejects unknown mapping fields. `routers/settings.py:155–273` provides
the local config/atomic-save precedent; its duplicate-tolerant split behavior is
not copied because runway requires duplicate rejection. Dynamic paths also work
with the existing opt-in storage fixture.

**Alternatives considered**: A `liquid` flag in account bindings; selecting all
savings; persisting balances or owner names. Rejected: discarded fields, implicit
selection, duplicated mutable financial data. Return eligible picker metadata
through runway settings itself, avoiding another fetch and eligibility guesswork.

## R3 — Spending classification, not the legacy derivation call

**Decision**: Validate the candidate month's transaction identity, account identity,
date, posting state, and finite amount before counting. Count absolute negative
posted checking/card purchases once by transaction ID. Identical JSON records,
ignoring object-key order, deduplicate; conflicting records with the same ID
invalidate every affected candidate month, not just the source encountered last.
Validate identity consistency across candidate sources before accepting the
common window. Do not merge distinct IDs by amount/payee.

Exclude excluded accounts/categories; savings/investment accounts and category
roles; either transfer flag; every configured owner savings-category override;
and all known repayment categories. Identify repayments from
`detailed_section_mapping.category_sections == "cc_payments"` plus **all**
catalog nodes matching the existing case-insensitive `"cc payment"` title
convention, including their descendants. Do not use the first-match helper or
guess payees/transfer pairs. Positive refunds and income do not offset purchases.
An `income` role alone does not erase a negative posted purchase; the explicit
movement exclusions remain authoritative.
Transfer flags follow `v4_pipeline/accounting.py`: `null` or absent is not a
transfer, and a non-null non-boolean value invalidates the observation. Real
PocketSmith transactions carry `"is_transfer": null` on many rows (RD-001).

**Rationale**: The existing expense loops omit date validation and deduplication;
embedded category transfer flags are not the only transfer evidence. The
classifier's savings override and `category_mappings.py` roles/sections provide
existing classification authorities.

**Alternatives considered**: Calling `compute_real_bills + derive_cc_usage`;
netting refunds/income; adding transfer inference or refund pairing. Rejected:
missing guarantees or changed metric. Keep this stricter logic runway-local,
without refactoring legacy Bills math.

**Superseded by R3b (2026-11-01)** for amounts.

## R3b — Reports-equivalent net basis and split attribution (SC-split / RD-002)

**Decision** (user-directed, 2026-11-01): Runway monthly spending is computed by
the production Reports accounting:

1. `report_builder.load_accounting_inputs` loads the shared config.
2. `report_builder._load_transactions` loads the month.
3. `build_contract` (wrapping `build_month_contract`) builds the contract.
4. `household_spending` returns `detailed_household_totals` plus, when the split
   is enabled, `_resolve_allowed_category_ids` → `net_category_totals` →
   `compute_split`.

All of these are shared with `build_report`, so the logic is not duplicated.

- Household = `totals.total`.
- With split on, owner = `totals[slot] − Σ delta(slot)` over household-section
  split rows.
- With split off, owner = `totals[slot]` (payer).

**Snapshot feeding**: the Reports loaders take file paths. Runway writes the
already-read snapshot bytes for the accounting sources and each month into a
per-request `tempfile.TemporaryDirectory` and points the loaders at it:

- `private_dir`, `account_mapping_path` and `split_config_path` are parameters
  of `load_accounting_inputs`.
- Month bytes are written verbatim. When there are identical repeats, a
  deduplicated `{"transactions": [...]}` is written instead.

This keeps the stable-bundle guarantee (one read set, change detection
unchanged) without forking the loaders into parsed-object variants. The cost is
one small temp write per month; 10,000 synthetic transactions take about
0.65 s.

**Rationale**: RD-002. A real catalog marked a parent category with
`is_transfer: true`, and runway's own ancestor walk dropped every child, which
put burn well below Reports. A single source of truth fixes this class of drift
by construction. Gross versus net was the other gap. The user also asked for
owner burn to follow the common-economy split.

**Alternatives considered**:

- Patching `_classification` to ignore catalog transfer flags. Rejected: it
  keeps two classifiers that can drift again.
- Calling `build_report` per month. Rejected: it builds the full DTO and labels
  at extra cost and reads live paths.
- Adding parsed-object entry points to `data_loader` / `load_*` config readers.
  Rejected: wider change to the Reports surface.

## R4 — Bounded validation and common months

**Decision**: Server-local date determines exactly the prior three completed
months, ascending. Validate only consumed source structures, transaction fields,
referenced categories/accounts, configured owners, and selected balances.
Ignore unrelated optional fields; do not validate every report setting.

One common month set serves every owner and household. Missing/invalid/known
partial months, or a zero owner observation without complete-period evidence,
are excluded for everyone. At least two usable months are required. Never
backfill older history. Unknown-coverage **positive** observations may be used
only with qualifications.

**Rationale**: FR-003–FR-008 require both a common denominator and honest zero
observations. A household's positive total cannot prove an unobserved owner's
zero. Unassigned non-excluded spending prevents claiming complete household
attribution; explicitly excluded movements need no owner allocation.

**Alternatives considered**: Independent owner windows, skipping bad records,
validating all financial configuration, filling missing months with zero.
Rejected: inconsistent aggregation, silent undercounting, or unnecessary scope.

## R5 — Provenance without a new capture system

**Decision**: Accept existing bare transaction lists and the existing
`{transactions: [...]}` envelope shape (also read by
`report_builder.py:558–564`). Bare lists have unknown collection and coverage.
Define an optional **read-only** `provenance` object on envelopes for explicit
collection/coverage evidence; its exact contract is in [data-model.md](data-model.md).
This is a new, runway-local metadata-reading convention, not evidence that the
current sync writes it. No source rewrite, metadata sidecar, backfill, sync change,
or capture infrastructure is planned.

Catalog `provenance.collected_at` and account `current_balance_date`, when present
and valid, are separate evidence. Normal sync writes `{start, end, accounts}` and
raw arrays (`sync_runner.py:194–244`); neither `start/end` nor file presence proves
coverage. `.sync_status.last_sync` is run-level information, not a transaction or
balance timestamp. File modification times are only local-write observations,
never substituted for collection or bank dates.

Complete coverage requires explicit complete-period bounds and collection no
earlier than the first instant of the following local month. Known partial or
pre-period-end sources are excluded. Invalid claimed metadata is an invalid
source, not silently changed to unknown. Absent metadata supports only the
specified qualified positive observations. Known dates older than 24 hours are
stale, including historical collection dates; calculation time never resets age.

**Alternatives considered**: Treating sync success/mtime/snapshot flags as
completeness; changing sync publication; refusing all legacy raw history.
Rejected: invented provenance, scope growth, or violation of the spec's explicit
qualified-history allowance.

## R6 — Stable reads, not a transaction framework

**Decision**: Read a fixed set of exact paths into memory, then re-read their
bytes/existence before returning or saving. Compare both passes, including
settings, mappings, catalogs, relevant category config, three raw files, and
sync status. A detected change or recorded running sync yields
`sources_changing` and retry, not a mixed ratio. No automatic retry loop.
Ignore sync-status money/warning payloads; consume only the state needed for
this check. A stable failed sync is not evidence of complete coverage.

**Rationale**: Sync replaces files individually. A bounded double-read catches
ordinary concurrent replacements, including same-size content changes, without
new dependencies or persistent versions. It cannot prove a common capture
generation; source dates and unknown evidence still qualify the result.

**Alternatives considered**: Filesystem locks, a generation manifest, a watcher,
using mtime alone, caching. Rejected: infrastructure or weaker detection. This is
not a claim to detect changes occurring after the final check or a change-and-
restore between reads.

## R7 — Ownership, signed reserves, and currency

**Decision**: Use the stable keys and labels in
`account_mappings.partners`; deterministic sorted IDs supply optional display
slots, never attribution. Do not import `bills_builder` or report-builder label
helpers just for identity. Sum each selected checking/savings account once, with
its signed finite recorded `current_balance`. Missing/ineligible selected accounts
remain visible and block affected owner/household reserves. A valid reassignment
uses its current owner. An unresolvable removed account blocks all potentially
affected owner reserve results rather than guessing its former owner.

Owners without a selection have null reserves, not zero. A nonempty valid
household selection may cover only some owners, while household spending still
covers all configured owners. Shared-expense split settings are never read.

Use explicit `currency_code` evidence where available on consumed transactions,
embedded accounts, and catalog accounts; normalize case, not currency values.
Conflicting evidence blocks affected sums/ratios. Unknown evidence is the visible
single-currency assumption, not an inferred ISO code or an FX conversion.
Currency conflicts do not erase another owner's independently valid result.

**Alternatives considered**: Slot/name-based ownership, fair-share allocation,
absolute balances, one bad account silently dropped, assuming all `kr` means
NOK, or adding FX. Rejected: misleading money or scope growth.

## R8 — Numeric and response semantics

**Decision**: Use standard-library `Decimal` for parsing, sums, means, ratio, and
half-up display rounding. Reject bool, null, malformed, and non-finite money.
Accept JSON numbers and finite decimal strings from upstream, but never coerce
missing values to zero. Serialize finite JSON numbers to match existing client
DTO conventions; reject an unrepresentable result instead of returning NaN,
infinity, or an underflowed zero. Monetary values are not rounded before math.

Expose `available | qualified | unavailable`, all applicable machine reason
codes, the included/excluded months, source and balance dates, and nullable
measures. Provide an authoritative nonmonetary `runway_display` for tenth-month
half-up rounding and `<0.1`. Model local absence as a 200 domain result; invalid
PUT is 400 and failure to safely read/save settings is 500, matching
`{detail: string}` and existing 422-to-400 handling.

**Alternatives considered**: Decimal strings throughout the API, JS-only ratio
rounding, false-zero defaults, or a generic result framework. Rejected: contract
expansion, binary rounding traps, or unnecessary abstraction.

## R9 — Independent UI and privacy

**Decision**: Mount a runway panel at a stable position outside Bills' early
loading/error/not-found returns; keep legacy content branches intact. Use a
typed API module, one hook with separate result/settings/save state, and thin
panel/settings components. Request sequence IDs suppress stale responses.
No request depends on Bills' adjustable window or privacy state. Keep saved
selection separate from the editable draft; disable Save on settings-load error.

Use `useAmountsHidden` and mask at render time, including attrs and assistive
text. Ratios/months/counts/dates remain visible. Reuse `formatKr` for the existing
unverified household display unit; show exact currency evidence alongside it.
For an established non-`kr` currency, a runway-local formatter follows the same
grouping/whole-money convention and `maskAmount`, with the actual ISO label,
never a false `kr` suffix. No cross-currency comparison is displayed.

**Rationale**: `BillsPage.tsx:120–155` currently short-circuits on Bills failure.
`finance-data.ts:205–208` hardcodes `kr`; it is not currency evidence.
`SplitConfigSection` and privacy tests provide lifecycle/masking precedents.
`main.py:94–111` requires adding **both** new exact sensitive paths to no-store,
including error and PUT responses.

**Alternatives considered**: Hydrating the legacy Bills store, refetching all
Bills after Save, inline fetch logic, retaining old figures without a label,
or monetary warning strings. Rejected: coupling, races, privacy leaks.

## R10 — Verification and governance boundaries

**Decision**: Plan new tests in a dedicated `tests/runway/` subtree so existing
Bills conftest is not its ancestor. Use autouse runway fixtures that explicitly
depend on the opt-in `tmp_private_dir` and `tmp_env_file`, block external network
and protected-path fallback before app import/client lifespan, and run Python
only with `BILLS_CALC_LOG=0` set before process startup.

Focused validation is the first runnable path. Full suites require verified
global isolation, not merely these feature-local fixtures. Browser acceptance
uses deterministic route interception, ports 5203/8103 only if needed, and no
default 5200/8100 proxy traffic. No new test dependency is selected.

**Rationale**: Discovery verified import-time logging, opt-in fixtures, disk
fallbacks, and unblocked frontend fetch defaults. Current declarations also
contradict constitution dependency pins. The active mandatory before-tasks
plan-review gate remains pending, not waived by unattended execution.

**Alternatives considered**: Running the full suite immediately, importing the
production app before patching storage, adding infrastructure to solve unrelated
baseline issues, or publishing to satisfy the gate. Rejected: unsafe or outside
this planning authorization.
