# Research: Lifestyle creep detector

- **Date**: 2026-10-31
- **Scope**: Phase 0 decisions for [spec.md](spec.md); no application execution or external research.

**Historical amendment (2026-11-02)**: The earlier multi-month evaluation-period decision and verification below have been superseded by the user's confirmed one-target/reference-period semantics. The latest contract is in the final section of [spec.md](spec.md), the final section of [plan.md](plan.md), and [API contract](contracts/lifestyle-creep-api.md). The target is one completed `month`; optional `reference_start`/`reference_end` select 2–24 contiguous prior months; threshold remains independent. Earlier client/runtime evidence does not verify the correction.

## Evidence and Method

The full supplied discovery report is the primary code evidence. Its original temporary handoff was `1793465917668-copilot-tool-output-df1a2067a3f74e488fa71cbc8cc06bfb.txt`; the source references below make these decisions usable without that machine-local file. The report's proposals are not treated as implemented features. Bounded direct source reads clarified only contract-critical details. No private data, credentials, main-checkout content, or running services were accessed.

| Evidence | Verified behavior relevant to this plan |
| --- | --- |
| `src/budget_api/services/bills_derivations.py:402–517` | Shared posted-outgoing CC filters; category-ID aggregation uses float accumulation; title aggregation merges equal titles; uncategorized uses internal `-1`. |
| `src/budget_api/services/bills_builder.py:556–655,1068–1105` | Partner IDs/account ownership are available; title totals are wrapped in a permissive exception handler and usage coerces absence to zero. |
| `src/budget_api/services/sync_runner.py:226–307` | Fetches explicit monthly transactions/events before building the chain, then atomically writes snapshots. Exceptions in the transaction loop prevent reaching that publication loop. |
| `src/budget_api/models/bills.py:37–160` | Stable partner fields default to empty for older files; current Bills schema is 5, with title-keyed optional usage. |
| `src/budget_api/routers/bills.py:38–85` | Direct exact-file reads; missing files differ from read/JSON errors; month-kind flags are recalculated on GET. |
| `src/budget_api/services/storage.py:59–89` | Exact snapshot path and atomic JSON writer; generic `read_json` returns `None` for missing files and also parses JSON `null` as `None`. |
| `src/budget_api/main.py:38–51,98–115` | Validation errors flatten to 400 with one detail string; no-store is an explicit endpoint allow-list. |
| Discovery: `client/src/pages/BillsPage.tsx:28,217`, `hooks/useBills.ts:53,116`, `lib/bills-source.ts:29` | Existing display window has only three past months by default; failed neighbors are discarded and display-source fallback may return mock data. |
| Discovery: `client/src/lib/privacy-store.ts:10,71,77`, `components/bills/finance-data.ts:205` | Existing reactive global amount masking and monetary formatters. |
| `client/src/api/bills.ts`, `client/src/router.tsx` | Thin API wrappers; `/sync` is the existing sync navigation target. |
| `src/budget_api/tests/conftest.py:20–57`; discovery on builder import/fallback | Temporary storage fixture is opt-in; builder logging can occur on import and standalone paths can read prior snapshots. |

## R1 — Stable identity and additive monthly evidence

**Decision**: Add nullable `cc_spend_history` per partner, default absent/`None` for compatibility, and emit schema 6 for new snapshots. Keep original source category IDs, with no parent rollup. Preserve old title totals exactly. Read-time joins use stable partner IDs and category IDs only.

**Rationale**: Titles can change, collide, disappear, or be reused. The old aggregate cannot recover lost identity. The source transaction already contains the category ID; schema 5 already supplies partner identity for recent snapshots.

**Alternatives considered**: Reverse-mapping titles through today's category catalog; joining by label or partner slot; inventing IDs for old totals. All can create incorrect continuity. A separate history store adds persistence and migration complexity without a need.

**Consequence**: Re-sync is the only supported upgrade of legacy evidence. Older snapshots still work in old views. An empty new complete category map means observed zero; a missing new field does not.

## R2 — Completion is a source assertion, not a calendar guess

**Decision**: Sync passes explicit per-month acquisition context only after a successful full-range transaction fetch and validation. Complete requires the source month to have closed before that acquisition began. Open-month acquisition is partial, even if a later builder/read runs after rollover. Missing acquisition context is unavailable. A failed transaction fetch publishes no new Bills snapshots.

**Rationale**: The dashboard recalculates `is_past` during GET; it cannot establish whether September was fully fetched. Current builder absence/error coercion cannot certify successful empty observation. Full collection validation must precede filtering, so malformed records cannot silently disappear.

**Alternatives considered**: Trusting `is_past`, `synced_at` alone, an empty list default, row count zero, or global sync success on read. Each conflates time or availability with trusted month coverage. Reading sync status would also break the five-path boundary.

**Consequence**: The stored evidence marker is authoritative and immutable on reads. A well-formed `unavailable/invalid_source` block is a diagnostic, whereas a corrupt saved block is an error. Builder validation failures that prevent safe publication still abort rather than inventing a block from a failed build.

**Cycle1 verified correction (2026-10-31)**: The initial integrated review found that `_get_paginated` returns a truncated list at the cap by design (`tests/test_ps_client.py::TestPagination::test_pagination_cap`). A successful list return therefore was not proof of full acquisition. Synthetic real-pagination sync tests reproduced unwanted Bills publication for both monthly transactions/events and prior-month fallback. The minimal policy is a keyword-only, default-false `require_complete_pagination` client option, enabled once by sync. It raises `PSClientError` on a remaining next page at the cap, before any Bills writes; default callers still truncate. A per-transactions-method flag would omit events/fallback, while a new acquisition result envelope would unnecessarily change legacy callers. Exact-cap terminal pages remain successful. See [cycle1 execution evidence](quickstart.md#13-integrated-qa-rework-cycle1--2026-10-31).

## R3 — Comparable scope without labels

**Decision**: Fingerprint stable partner ownership, eligible CC account IDs and effective exclusions, resolved spending-relevant category filters, and the calculator/filter version. Canonicalize and hash these inputs with standard-library SHA-256. Exclude display labels, balances, transaction counts, and spending values.

**Rationale**: Comparing different account or exclusion populations can manufacture apparent growth. Comparing raw mapping/catalog JSON would incorrectly invalidate history after labels or unrelated configuration changes.

**Alternatives considered**: No guard; title-based signatures; hashing only accounts observed in a month's transactions; effective-dated configuration history. The first three give wrong comparability; the last exceeds this feature.

**Targeted source caveat**: `_cc_payment_category_id` in `bills_builder.py:428–447` currently selects a resolved category ID using a title convention. Reuse the effective resolved exclusion ID, not that title, in the fingerprint. A rename that changes the resolver's actual exclusion set is a spending-scope change and must fail comparability; it is not a display-only rename. Do not redesign legacy payment mapping in this feature. Pure display renames with unchanged effective filters must leave fingerprints and readiness unchanged.

**Cycle1 verified correction (2026-10-31)**: `routers/accounts.py::update_binding` accepts excluded null owner/type, and sync retains removed mappings with `excluded=true`. Rejecting all unassigned mappings made that valid outside-scope state unrecoverable by repeated sync. The producer now permits null fields only for explicitly excluded mappings, still validates supplied non-null fields and all included ownership/type, and never invents bindings. Known owned CC exclusions still affect the fingerprint; excluded unassigned mappings do not. Producer/build and repeated-sync regressions cover catalog-present and removed entries.

## R4 — Exact Decimal math and serialization

**Decision**: Validate original source numeric amounts, then aggregate magnitudes using `Decimal(str(amount))` at the source adapter boundary, never by converting an already accumulated float total. Reuse shared filter membership, with a validated non-null partner account set and uncategorized splitting. Persist and return new decimal fields as canonical decimal strings; map Pydantic `Decimal` fields to that representation explicitly and retain all old numeric fields unchanged.

**Rationale**: `compute_real_cc_spend` currently accumulates floats. Reusing its result verbatim can turn equality into `>20`. A Decimal sum then cast to a JSON float would reintroduce precision loss. New-field strings work with the existing atomic JSON writer and avoid a global encoder change. They are an explicitly new feature-local representation, not an assertion that the repository already uses it.

**Exact decision rule**: For baseline sum `T`, spending `S`, threshold `p`, test `100 × (3S - T) > p × T`, with `T > 0`. Use enough local Decimal precision for exact sums/products based on input coefficients/exponents, not the default 28 digits or a rounded division. Both comparisons and the initial positive-month count decide the flag. Derived averages and percentages may need repeating-decimal output; compute those for explanation at 28 significant digits, round-half-even, only after exact decision work. They never feed the flag.

**Alternatives considered**: Float epsilon, cent-rounding before comparison, fixed-precision threshold math, server floats/client re-computation, or new decimal libraries. Epsilon changes strict equality, cent-rounding fails `132.001`, fixed precision can round a boundary, and the others duplicate logic or add dependencies.

**Client consequence**: Decimal strings remain strings in API types and hook state. Convert finite representable values only for existing masked money/percentage formatting. Never derive `is_sustained` from displayed percentages, and never treat null as zero. A presentation conversion that would overflow must not produce infinity or invalidate finite server evidence: use a privacy-aware decimal-text fallback with the existing unit/sign convention. Extremely small values may display rounded zero; exact strings and server outcomes remain authoritative.

## R5 — Fixed window, configurable threshold, conservative suppression

**Decision**: Five exact contiguous preceding months; three-month rolling averages; two sustained strict comparisons. Default threshold 20; inclusive 1–100 finite decimal query values. Only omission defaults. Require two positive months in the initial three, with zero-baseline suppression taking precedence. Per-visit threshold state is not persisted.

**Rationale**: These are completed spec decisions, including the four-versus-five-month correction. A second elevated month may be flat relative to the first and still qualify. Sparse suppression is a limited statistical screen, not semantic one-off detection.

**Alternatives considered**: A single baseline for both months, current-month extrapolation, older-month substitution, configurable sustained count, transaction recurrence classification, stored preferences. All contradict or expand the spec.

## R6 — Bounded read adapter and explicit error classes

**Decision**: A service reads five exact paths from `storage.bills_dashboard_path`; it directly reads text and strictly decodes JSON to distinguish missing, JSON `null`, duplicate keys, and malformed structures. The generic `read_json` helper is not sufficient for this boundary. Validate minimal snapshot identity/history envelopes, retaining compatibility with unrelated optional legacy fields.

**Rationale**: Missing is expected unavailability; corrupt is an error. A full `BillsSnapshot` parse would unnecessarily validate unrelated fields while defaults could obscure missing evidence. The detector needs strict targeted validation, not normalization into usable history.

**Alternatives considered**: Dashboard HTTP composition, scanning snapshots, raw-source fallback, reading catalogs to fill identity gaps, caching responses. These violate the read boundary or make corrected history invisible to Retry.

**Consequence**: GET 200 for ready/partial/insufficient coverage; 400 for invalid query; generic 500 for invalid saved inputs or I/O failures. No-store on all three via the existing allow-list and controlled error responses. Any corrupt record cancels the whole result, even if another partner was ready.

## R7 — Independent card and privacy-safe explanations

**Decision**: Dedicated wrapper/hook/card, mounted once outside Bills visualization/window rendering. Hook key is month plus applied threshold; explicit Retry forces a new bounded request. Use latest-request protection, visit-local draft/applied threshold separation, and reactive existing amount masking.

**Rationale**: Display-window loading discards failed neighbors and may use a mock fallback. It cannot be the detector's trusted history source. Money hiding must cover every output channel, not only the main amount.

**Alternatives considered**: Extending `useBillsSnapshot` to do detection, deriving from UI models, exposing only flagged categories, refetching on privacy toggle. These couple correctness to display loading, omit required explanations, or add needless reads.

**Consequence**: API-returned readiness and verdicts control presentation. Every category is inspectable, including suppressed/no-alert outcomes; uncategorized samples are separately visible. `/sync` is a navigation affordance, never a sync-on-render action. No runway/debt widgets, mocks, contracts, or route behavior are integrated.

## R8 — Safe verification and governance boundaries

**Decision**: Only deterministic synthetic tests. Disable builder logging before import; route all builder/storage/lifespan paths to temporary locations before execution, including inherited prior-snapshot fallbacks. Close relevant shared fixture isolation gaps before running the full suite. Browser smoke installs request mocks before navigation and never contacts a live backend.

**Rationale**: Existing opt-in fixtures do not make every builder test safe automatically. Vite currently proxies `/api` to 8100; merely changing the frontend port does not isolate API traffic. Mock every API request, abort unexpected traffic, and never interact with the user's stack.

**Alternatives considered**: Real data smoke, starting default dev services, running the builder suite without import guards, restoring dependencies speculatively. Each violates the requested boundary.

**Tooling clarification**: Current `client/package.json` pins pnpm 10.30.3 and has test/build but no lint script. Current Python manifest ranges differ from constitution prose. No dependency or charter amendments are part of this plan. Restore locked dependencies only after an actual missing-dependency command failure during later verification.

## Resolution

All design questions needed for Phase 1 are resolved. No research agents were needed: the supplied discovery plus bounded direct clarification provided the evidence. This document records decisions for future implementation, not runtime validation or a plan-review-gate pass.
