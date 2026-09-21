# Phase 0 Research — 001-depersonalize-identifiers

**Date**: 2026-09-16 | **Branch**: `001-depersonalize-identifiers`
**Inputs**: spec.md, `docs/open-source-launch-gates.md` (LG-001..LG-008), `code-evidence.md` (verified trace).

## Unknowns resolution

The Technical Context contains **zero NEEDS CLARIFICATION items**: the red-team pass already resolved the ambiguous areas into launch gates, and the code-evidence trace (all file:line anchors verified on this branch) resolved every codebase unknown. Each decision below records rationale and alternatives per the plan workflow.

---

## R1 — New personal-section key names

**Decision**: `personal_partner_a` and `personal_partner_b`.

**Rationale**:
- Converges with an existing transitional alias: `src/mom/sections/section_personal.py:21-22` already maps `personal_partner_a → personal_christian`. After the rename the alias becomes identity and is deleted — mom needs no third spelling.
- Matches the established naming style of adjacent contract fields: the same DTO already has `personal_share_partner_a` / `personal_share_partner_b` (golden fixture top level).
- Keeps the `personal_` prefix, so the section's role stays self-describing in the 10-member section-key enum (`income_salary`, `savings`, `home`, `common`, `trips`, `cc_payments`, `excluded`, …).
- Keys ride on the stable neutral ids `partner_a`/`partner_b` already used by `partner_labels` and the BE settings surface — LG-007 compliant by construction.

**Alternatives considered**:
- `personal_a` / `personal_b` — shorter and matches `partner_labels` keys directly, but ambiguous out of context and would leave mom's alias spelling disconnected (a third variant to maintain). Rejected.
- Keep keys, scrub only display strings — fails FR-004 (keys encode personal names) and LG-002 (substring grep). Rejected.

---

## R2 — Rename order and PR split

**Decision**: Five stacked PRs off `001-depersonalize-identifiers` (trunk-based stacking, repo pattern per `docs/memory/patterns.md`): **PR1 v4_pipeline → PR2 budget_api → PR3 mega+mom → PR4 client → PR5 fixtures-remainder + docs prose + verification + CI smoke**. Fixtures land in the PR of the layer whose tests consume them; the golden report fixture is regenerated in PR2 (mandatory — it embeds the renamed keys and is asserted byte-equal by `test_build_report_matches_golden_baseline`).

**Rationale**:
- Dependency direction: `v4_pipeline` is the canonical producer of section keys; `budget_api` wraps it (`report_builder._detailed`); `mega`/`mom` consume monthly payloads; the client consumes the DTO. Renaming bottom-up keeps every intermediate state self-consistent and testable — no PR ships a key its consumer doesn't know (FR-005).
- ~100 tracked files carry removal-list hits (full-tree grep, 2026-09-16); a single PR is unreviewable, but each stacked PR is a coherent, independently CI-green layer.
- Bills test fixtures use slug partner ids (`"christian"`/`"rasma"` in `conftest.py`, `src/budget_api/tests/bills/*`, client mocks) — these are code identifiers derived from names and belong to PR2/PR4/PR5 alongside their owning contracts.

**Alternatives considered**:
- One mega-PR — rejected (unreviewable, and repo convention is stacked PRs for F-series work).
- Fixtures-first — rejected (consumers would break mid-chain; fixture semantics are validated by the consuming layer's tests).
- Independent sibling PRs off main — rejected (gated by stacked PR policy; related work stacks).

---

## R3 — Bills FE de-coupling (LG-007)

**Decision**: Add an additive `partner_id: str` to the bills contract — on `BillsEvent`, `PartnerBills`, and the dashboard month blocks emitted by `bills_builder._partner_label()`'s call sites — plus a companion `partner_slot: "a" | "b"`, and bump the snapshot `schema_version` 4 → 5 (additive-with-defaults convention).

`partner_id` is defined as **an arbitrary, opaque, stable string** — a pure passthrough of the partner key already used in `account_mappings.json` (`_all_partner_ids()`, `bills_builder.py:169-172`). It is **not** constrained to `partner_a`/`partner_b` because the settings API (`settings.create_partner`) can mint arbitrary label-derived slugs, and stability of existing configs matters more than a closed enum. No settings-API migration is required.

`partner_slot` is the **neutral slot/style field**: the BE assigns it deterministically — sorted `partner_id` order → first id gets `"a"`, second gets `"b"` — and emits it in the payload alongside `partner_id`. The FE keys all ordering/styling decisions (color class, series position) on `partner_slot` and all identity/grouping/filter decisions on `partner_id`; it never derives either from a display label and never from array position in the FE. The events filter endpoint parameter changes from `?partner=` (label) to `?partner_id=`. `client/src/types/api.ts:113` `F2Partner = "Christian" | "Rasma"` is deleted; mock `PARTNERS` in `finance-data.ts` becomes `{ partner_id, partner_slot, label }` triples.

**Rationale**:
- LG-007: no code path may compare a display label to distinguish partners. Today the label is the ONLY partner identifier in the bills payload (verified Q4b) — load-bearing for color, filtering, and sort across 6+ components (`GraphView.tsx:44,378,382-390,416-427`, `BillsDashboard.tsx:55`, `BudgetTab.tsx:146`, `EconomyBar.tsx:183`, `EventRow.tsx:38`, `TableView.tsx:240`, `SavingsSparkline.tsx`).
- `partner_id` already exists internally throughout the builder (`_all_partner_ids`, `bills_builder.py:169-172`) and in `account_mappings.json`; emitting it is a pure passthrough — zero derivation risk. Because ids are arbitrary (see Decision), slot assignment is the ONLY identity inference the system performs, it happens once in the BE, and it is deterministic (sorted id order).
- Legacy schema-4 snapshots (no `partner_id`/`partner_slot`): the FE renders them in identity-neutral mode (neutral styling, partner filter hidden) with a "regenerate" hint, per the bills "never 500s on old files" convention — the FE never infers partner identity from the `partners[]` array order, because that order is insertion order, not sorted (see contracts/bills-partner-identity.md, Regeneration & legacy handling).

**Alternatives considered**:
- Constrain the settings API to the two fixed ids `partner_a`/`partner_b` and migrate existing configs — rejected: forces a breaking settings migration for zero modeling gain; arbitrary stable ids + an explicit slot field express the same invariant without touching stored config.
- Derive slot from label order on the FE — keeps the label load-bearing somewhere; rejected by LG-007's spirit and letter.
- Positional-only contract (partners[0]/[1] with no id) — fragile for the spec's one-partner edge case; rejected.

---

## R4 — Contract-version marker and loud rejection (LG-005, FR-006)

**Decision**: Add an explicit top-level `contract_version: 2` to monthly (`{month}_monthly_report.json`) and mega (`{start}_{end}_mega_report.json`) stored payloads. Read rule: **absent or ≠ current → reject before pydantic validation**. `report_builder.read_report` (and `mega_builder` equivalent) raises `IncompatibleContractError`; routers map it to HTTP 409 with detail "stored report predates contract v2 — regenerate"; the client surfaces the existing Regenerate affordance. `calculation_version` (bumped 6 → 7 because payload content changes) keeps its current staleness-marking role unchanged; `MEGA_CALCULATION_VERSION` and bills `schema_version` likewise remain staleness/compat markers.

**Rationale**:
- LG-005 names exactly this shape ("e.g., `contract_version: 2`") and demands rejection of absent/unrecognized versions — silence-as-success is forbidden.
- **The check must run before validation**: the repo convention adds new DTO fields as optional-with-defaults so old files don't 500 (`TestReportResponseCompat`). Under that convention a pre-change payload (old keys, `personal_partner_a` absent) would validate with `None` sections and render empty — precisely the silent failure FR-006 prohibits. Verified in code-evidence.md Q1c/Q1d and the explorer's notes.
- Two markers, two semantics: `contract_version` = breaking contract identity (reject); `calculation_version` = additive/content drift (render with `stale: true`). Collapsing them would either regress the render-with-stale-flag convention for future additive bumps or violate LG-005 now.
- Verification per LG-005: tests feed (a) a v1 payload (old keys, no marker) → 409, and (b) a partially overlapping payload (mixed old/new keys, marker absent) → 409; plus regeneration producing a v2 payload that validates and renders.

**Alternatives considered**:
- Reuse `calculation_version` alone as the break signal — rejected (conflates staleness with breakage; see above).
- Pydantic alias/pre-validator coercing old keys to new — silent coercion explicitly forbidden by FR-006 and the red-team finding F-RT-001-005; rejected.

---

## R5 — Partner-label config validation (LG-006 + LG-007 validation half)

**Decision**: One canonical validator in the lowest shared layer — `validate_partner_labels(raw) -> (labels, warnings)` in `src/v4_pipeline/accounting.py` — wrapped by `budget_api` `report_builder._load_partner_labels()` (used by `build_report`, `mega_builder.py:224`, `report_pdf.py:54`) and by the v4 CLI path (`accounting.load_partner_labels`). Rules, all with visible-warning + placeholder fallback (never crash, never silently render bad data):
- Shape: object; keys `partner_a`, `partner_b`. Extra keys → warning, ignored. Missing key → that partner falls back to placeholder + warning.
- Types: string values only; non-string → placeholder + warning.
- Length: max 64 chars; longer → truncate + warning (LG-006 text).
- Duplicate configured labels (case-insensitive) → rejected, both fall back + warning (LG-007).
- Reserved placeholders: configuring literally `Partner A` / `Partner B` (or empties/whitespace) → rejected + fallback + warning (LG-007).
- Warnings surface via: `logging` warning, and a new additive `warnings: list[str]` top-level field on the report payload (default `[]`); CLI prints to stderr.
- Escaping: HTML/PDF paths already escape all label interpolations via `html.escape` (verified: `accounting_html.py` uses `escape(...)` at every label site); React renders labels as text (escaped by default). A regression test injects an HTML label (e.g. `<img onerror>`) and asserts escaped output.

Write path: **both** partner mutating endpoints run the same validator and return 400 on hard-invalid input, so bad labels can't be persisted through the settings API either — `routers/partners.py update_partner` (PUT) **and** `create_partner` (POST), which otherwise mints arbitrary label-derived slugs with no validation.

Current resolution order is preserved: `partner_labels.json` (flat map) → `account_mappings.json partners[].label` → defaults.

**Alternatives considered**:
- Validate only at write time — the file is hand-editable and has no tracked writer today (Q2a); load-time validation is the only guarantee. Rejected as sole mechanism (kept as an additional 400 guard).
- Validator in `budget_api` — v4's CLI HTML rendering needs it too, and v4 must not import budget_api; rejected.

---

## R6 — CI regeneration smoke test (LG-008)

**Decision**: Anchor on the existing golden regeneration test (`src/budget_api/tests/reports/test_golden_fixture.py:50-60`, which rebuilds the monthly report from `data/sample_apr_2026.json` and asserts equality with the golden payload) and add a dedicated smoke module `src/budget_api/tests/reports/test_regen_smoke.py` asserting, for each historical stored-report shape:
1. Monthly report regenerates from the synthetic fixture under the new contract: payload carries `contract_version: 2`, `detailed` keys are exactly the 10 new keys, and no legacy key string appears anywhere (recursive walk).
2. Mega report regenerates via `mega_builder` from the same fixture (anchor: `test_mega_acceptance.py`) with `contract_version: 2` and neutral section keys.
3. Bills snapshot rebuild emits `schema_version: 5` and `partner_id` fields.
4. Legacy-shape rejection probes (R4 verification) live beside it.
CI picks this up with zero workflow changes: both OS legs already run the full `src/budget_api/tests` tree. README/CONTRIBUTING gain the LG-008 fallback note (unregenerable shape → PocketSmith re-sync).

**Rationale**: LG-008 demands "verified, not assumed" regeneration coverage; reusing the golden-fixture machinery gives byte-level proof instead of a shallow smoke. Keeping the test inside existing suite dirs honors Constitution VIII (canonical command stays canonical).

**Alternatives considered**: separate CI job — rejected (duplicates the dual-OS matrix for no signal gain). Golden-fixture-only coverage — rejected (covers monthly but not mega/bills shapes).

---

## R7 — Identifier inventory + reproducible verification (LG-002)

**Decision**: The committed inventory already exists as `docs/open-source-launch-gates.md` (I-001..I-003 + the exact `git grep -n -i 'christian\|rasma\|gjedrem' -- .` command). Implementation adds:
1. An automated containment test (same style as the existing `test_tracked_relevant_text_has_no_private_paths_or_credentials`) running that grep over tracked files and failing on any hit **outside the exact governance allowlist**: `.charter/`, `.specify/` tooling templates, `docs/open-source-launch-gates.md`, and everything under `docs/specs/001-depersonalize-identifiers/` (the inventory/red-team/plan docs deliberately name their targets — see R8). The same allowlist applies to the LG-002 launch-time command, so CI and launch verification can never disagree.
2. The verification output recorded as launch evidence (appended to the launch-gates file or an adjacent dated evidence file) when SC-001 first goes green.

**Rationale**: LG-002 requires committed inventory + reproducible command; making the command a CI test converts a launch-time manual step into a continuous guarantee.

**Alternatives considered**: manual verification only — rejected (non-reproducible, decays immediately). Allow-listing doc hits instead of scrubbing — rejected (LG-002 marks docs prose as FAIL).

---

## R8 — Docs-prose and comment scrub scope

**Decision**: Historical design docs (`docs/design/*.md`, `docs/bugs/*/` provenance notes) are edited in place to neutralize identifiers; FE/BE comments mentioning names (`theme.css:45-46`, `DetailedSections.tsx:423`, `accounting.py:899-900` — also fixing its staleness) are rewritten. `red-team-findings-2026-09-16.md` and `open-source-launch-gates.md` themselves contain the identifiers **by design** (they are the removal inventory); LG-002's gate applies to "tracked source, fixtures, contracts, UI strings, or docs prose" — the inventory docs are the one sanctioned place the names must remain for the verification to be meaningful, and they are excluded from the published tree because the public launch is a fresh history-reset repo (LG-001) where these governance docs stay in the private upstream. [This exclusion must be recorded in launch evidence at LG-002 verification time.] The governance allowlist is exactly: `docs/open-source-launch-gates.md` and `docs/specs/001-depersonalize-identifiers/**`; both the CI containment test (R7) and the LG-002 launch command apply this same allowlist — everything else in the tracked tree must be grep-clean on this repo's own CI, today and at launch.

**Rationale**: grep-clean tree is the acceptance test (SC-001); an inventory file that cannot name its targets is useless, and publishing is by fresh-fork anyway.

**Alternatives considered**: rewriting the inventory to initials — rejected (weakens the exact-match verification command into guesswork).
