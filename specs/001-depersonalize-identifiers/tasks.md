# Tasks: De-personalize identifiers for open-source launch

**Input**: Design documents from `/specs/001-depersonalize-identifiers/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present and review-resolved on PR #77)

**Tests**: INCLUDED — mandated by FR-008, SC-002, LG-005/006/007/008 and every contract's "Tests that pin this contract" section.

**Organization**: Tasks are grouped by user story. The 5 stacked delivery PRs from plan.md are annotated per task range — see "Stacked PR mapping".

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- All paths are repo-relative. Windows PowerShell commands; use `;` + `if ($?)` gating (no `&&`).

## Path Conventions

Single repo: BE pipelines `src/v4_pipeline`, `src/mega`, `src/mom`; API layer `src/budget_api`; FE `client/src`; fixtures `data/`; docs `docs/`, `designs/`. Tests colocated per Constitution VIII. Canonical BE command (PowerShell):

```powershell
$env:PYTHONPATH = 'src'; python -m pytest src/mega/tests src/v4_pipeline/tests src/mom/tests src/budget_api/tests -q
```

---

## Phase 1: Setup

**Purpose**: Baseline evidence and working artifacts; no source changes.

- [X] T001 Capture green baseline: run the canonical BE command + (in `client/`) `pnpm build; if ($?) { pnpm test }`; record pass counts as the pre-change baseline evidence in the session artifacts dir (not the repo)
- [X] T002 [P] Produce the working identifier inventory: `git grep -n -i 'christian\|rasma\|gjedrem' -- . | Out-File <artifacts>/identifier-inventory.txt` plus `git ls-files | Select-String -Pattern 'christian','rasma','gjedrem'` appended; this file scopes every US1 task and is deleted/never committed

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The canonical partner-label validator (R5) — every load path in US1/US2 and both settings write endpoints depend on it.

- [X] T003 Implement `validate_partner_labels(raw) -> tuple[dict, list[str]]` in `src/v4_pipeline/accounting.py` per contracts/partner-labels-config.md: shape/type/≤64-char-truncate/duplicate-case-insensitive/reserved-placeholder/empty rules; every failure → placeholder for the affected partner(s) + warning string; never raise
- [X] T004 [P] Unit tests for `validate_partner_labels` in `src/v4_pipeline/tests/` covering each contract rule row (non-object root, missing key, non-string value, >64 chars, duplicates, reserved `Partner A`/`Partner B`, empty/whitespace) asserting fallback labels + warning text

**Checkpoint**: Validator exists and is green. US1, US2, US3 can now all proceed.

---

## Phase 3: User Story 1 — Repository contains no personal identifiers (Priority: P1) 🎯 MVP

**Goal**: Every tracked file free of removal-list identifiers; personal-section contract keys renamed consistently through v4_pipeline → budget_api → mega/mom → client → fixtures (`personal_christian`→`personal_partner_a`, `personal_rasma`→`personal_partner_b`; FR-001/004/005/007).

**Independent Test**: `git grep -n -i 'christian\|rasma\|gjedrem' -- .` exits 1 (zero matches outside the governance allowlist in LG-002/R7); canonical BE command + `pnpm build`/`pnpm test` remain green; a regenerated report renders `personal_partner_a`/`personal_partner_b` sections.

### PR1 — v4_pipeline rename

- [X] T010 [US1] Rename the registry members in `src/v4_pipeline/accounting.py`: `DETAILED_CATEGORY_SECTIONS` (:16-26), `HOUSEHOLD_COMPOSITION`, `detailed_personal_sections()`; delete/replace the stale comment at :899-900 (references a nonexistent hardcoded FE array)
- [X] T011 [P] [US1] Rename section keys in `src/v4_pipeline/accounting_html.py` and replace the hardcoded name fallbacks at :818-819 with label resolution (validator output → placeholder fallback); confirm every label interpolation still goes through `html.escape`
- [X] T012 [US1] Update v4 tests + mapping fixtures in `src/v4_pipeline/tests/` (`"christian"->"personal_christian"` etc. → new keys); assert equivalent-or-stronger behavior (FR-008)
- [X] T013 [US1] Add the transitional adapter in `src/budget_api/services/report_builder.py` `personal.get("personal_partner_a", personal.get("personal_christian"))` (and `_b`) so budget_api stays CI-green against the renamed producer until PR2
- [X] T014 [P] [US1] Scrub tracked source fixtures `data/sample_apr_2026.json` (payee/category titles → clearly synthetic values per FR-007) and `data/sample_apr_2026_detailed_section_mapping.json` (`"7"`, `"8"` values → new section keys)

### PR2 — budget_api contract surface

- [X] T015 [US1] Rename `DetailedSections` DTO fields in `src/budget_api/models/reports.py` (:240-241) to `personal_partner_a`/`personal_partner_b`; update `ReportResponse` assembly
- [X] T016 [P] [US1] Rename validation enum members in `src/budget_api/models/category_mappings.py` (:11-21); existing 400 behavior on unknown values is unchanged
- [X] T017 [US1] Remove the transitional adapter and switch `report_builder._detailed` (:207-208) to the new keys only; update `report_builder` unit/integration tests
- [X] T018 [US1] Regenerate the golden fixture `src/budget_api/tests/reports/golden/sample_apr_2026_report.json` from the scrubbed source fixture and verify `test_build_report_matches_golden_baseline` passes byte-equal with the renamed keys
- [X] T019 [P] [US1] Scrub bills test slugs (`"christian"`/`"rasma"` ids) in `src/budget_api/tests/conftest.py` and `src/budget_api/tests/bills/*` → neutral ids (e.g. `partner_a`/`partner_b`)

### PR3 — mega + mom rename

- [X] T020 [P] [US1] Rename section keys in `src/mega/build_mega.py` (`section_routes` :277-278, `section_series` :511-519, composition)
- [X] T021 [P] [US1] Collapse the alias map in `src/mom/sections/section_personal.py` (:21-22) to identity and delete it; update appendix key list in `src/mom/sections/section_appendices.py` (:43-47)
- [X] T022 [US1] Update `src/mega/tests` and `src/mom/tests` to new keys; canonical command green

### PR4 — client rename surface (non-bills)

- [X] T023 [P] [US1] Update TS mirrors: `client/src/types/report.ts` (:230-231) and `client/src/types/category_mappings.ts` (:17-18, :55-56) to the new section keys/enum members
- [X] T024 [P] [US1] Rename section-key usage in `client/src/components/reports/DetailedSections.tsx` incl. comment scrub (:423)
- [X] T025 [P] [US1] Rename keys + scrub hardcoded titles in `client/src/components/mega-reports/` (`buildNavItems.ts`, `PersonalSection.tsx`, `AppendicesSection.tsx`)
- [X] T026 [P] [US1] Scrub name reference in `client/src/styles/theme.css` (:45-46 comment)
- [X] T027 [US1] Update client non-bills mocks/fixtures and tests (`client/tests/`, `src/**/__tests__/`) to the new keys; `pnpm build` + `pnpm test` green

### PR5 — remainder fixtures + docs prose scrub

- [X] T028 [P] [US1] Scrub remaining test-fixture identifiers across BE/FE suites not covered above (search-driven from the T002 inventory)
- [X] T029 [P] [US1] Scrub docs prose in `designs/*.md`, `docs/design/*.md`, `docs/bugs/*/` provenance notes (R8 — in-place neutralization of identifiers)
- [X] T030 [US1] Run quickstart Scenario 1 (content + path + encoded vectors) and record PASS output as launch-evidence material; only the LG-002 governance allowlist may remain — 2026-09-16: all three vectors PASS, recorded in `launch-evidence-2026-09-16.md`

**Checkpoint**: SC-001 holds on the whole tree; suites green; US1 independently verifiable via quickstart Scenarios 1-2.

---

## Phase 4: User Story 2 — Partner identity is configuration-driven (Priority: P2)

**Goal**: Labels resolve from user-local `partner_labels.json` (validated via the T003 validator) on every partner-scoped surface; bills contract ships additive `partner_id` + `partner_slot` so no code paths key on display strings (FR-002/003, LG-003/006/007).

**Independent Test**: quickstart Scenarios 5-7 — configure `{"partner_a": "Ada Example", "partner_b": "Ben Example"}`, regenerate, confirm labels on every surface; rename a label and confirm data attribution is unchanged (LG-007); no-config run shows `Partner A`/`Partner B` everywhere.

### BE: label resolution wiring

- [X] T040 [US2] Wire `report_builder._load_partner_labels()` to wrap the T003 validator (used by `build_report`, `src/budget_api/services/mega_builder.py:224`, `report_pdf.py:54`); add `warnings: list[str] = []` additive field to the report payload and surface validation warnings into it
- [X] T041 [P] [US2] Wire the v4 CLI label load (`src/v4_pipeline/accounting.py load_partner_labels`) through the same validator; print warnings to stderr
- [X] T042 [US2] Settings write-path: `src/budget_api/routers/partners.py` `update_partner` (PUT) **and** `create_partner` (POST) run the validator and return 400 on hard-invalid input

### BE: bills partner identity (schema_version 4→5)

- [X] T043 [US2] Emit additive `partner_id` (pure passthrough of `account_mappings.json` partner key) and `partner_slot` (BE-assigned, deterministic, sorted-`partner_id` order → `"a"`/`"b"`) on `BillsEvent` and per-month `PartnerBills` in `src/budget_api/services/bills_builder.py`; bump snapshot `schema_version` → 5
- [X] T044 [US2] `src/budget_api/routers/bills.py`: add `?partner_id=` filter replacing label `?partner=` for new clients (legacy param accepted exactly as before for one deprecation cycle); sort ties key on `partner_id`; old files still never 500
- [X] T045 [US2] Bills contract tests: builder emits id+slot; router `?partner_id=` filtering; schema-4 snapshot deserializes with `partner_id == ""` defaults (no crash); **legacy-order regression**: schema-4 snapshots with reversed `partners[]` insertion order render identically (no positional identity inference)

### FE: config-driven surfaces

- [X] T046 [P] [US2] `client/src/components/settings/CategoryMappingsEditor.tsx`: partner dropdown labels come from `partner_labels` (no hardcoded names)
- [X] T047 [US2] Bills FE de-coupling per contracts/bills-partner-identity.md: key identity/filter/grouping on `partner_id` and styling/order on `partner_slot` in `GraphView.tsx` (:44,:378-427), `BillsDashboard.tsx` (:55), `BudgetTab.tsx` (:146), `EconomyBar.tsx` (:183), `EventRow.tsx` (:38), `TableView.tsx` (:240), `SavingsSparkline.tsx`; render schema-4 snapshots (empty ids) in identity-neutral mode (neutral styling, partner filter hidden, regenerate hint)
- [X] T048 [US2] Delete `F2Partner = "Christian" | "Rasma"` (`client/src/types/api.ts:113`); type becomes `{ partner_id: string; partner_slot: "a" | "b"; label: string }`; update bills mocks in `finance-data.ts` to id/slot/label triples
- [X] T049 [US2] FE tests: renamed label does not change data attribution (LG-007 regression); no-config render shows placeholders; settings editor options are config-driven

### Validation/escaping regression (LG-006)

- [X] T050 [P] [US2] HTML/PDF escaping regression test: inject `<img src=x onerror=alert(1)>` as a label; assert escaped output in HTML and PDF-source HTML; assert `warnings` payload field + server log warning emission

**Checkpoint**: quickstart Scenarios 5-7 pass; US2 independently verifiable.

---

## Phase 5: User Story 3 — Breaking change is discoverable and deliberate (Priority: P3)

**Goal**: Stored monthly/mega reports carry `contract_version: 2`; readers reject absent/unknown versions **before** pydantic validation with HTTP 409 "regenerate"; `calculation_version` 6→7 keeps its separate stale-flag role (FR-006, LG-005/008; contracts/README.md two-semantics rule).

**Independent Test**: quickstart Scenario 3 — pre-change payload → GET returns 409 naming the month and the regenerate remedy (never 200, never empty personal sections, never bare 500); POST generate from source data → GET returns 200 with `contract_version: 2` and new keys.

- [X] T060 [US3] Writers stamp `contract_version: 2` + bump `calculation_version` 6→7 in `src/budget_api/services/report_builder.py`; stamp the same marker alongside `MEGA_CALCULATION_VERSION` in `src/budget_api/services/mega_builder.py`
- [X] T061 [US3] Readers reject-before-validate: `report_builder.read_report` and the mega equivalent raise `IncompatibleContractError` when `contract_version` is absent or != 2 **before** pydantic model validation (the optional-with-defaults convention would otherwise validate v1 payloads with empty personal sections)
- [X] T062 [US3] Routers map `IncompatibleContractError` → HTTP 409 with detail naming the report month and the regenerate remedy (`src/budget_api/routers/reports.py`, mega router); no partial render path
- [X] T063 [P] [US3] Client surfaces the 409 with the existing Regenerate affordance for monthly + mega report views
- [X] T064 [US3] Contract tests (per monthly-report-contract-v2.md "Tests that pin this contract"): (a) v1 payload (old keys, no marker) → 409; (b) mixed old/new keys with no marker → 409; (c) regenerated v2 payload validates and renders fully; (d) additive `calculation_version` drift still renders with `stale: true` (existing convention preserved)
- [X] T065 [US3] LG-008 regen smoke module `src/budget_api/tests/reports/test_regen_smoke.py`: monthly + mega regenerate from `data/sample_apr_2026.json` under v2 (recursive walk finds no legacy key strings), bills rebuild emits `schema_version: 5` + `partner_id`; alongside the golden byte-equality test

**Checkpoint**: SC-004 verified; US3 independently verifiable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Continuous verification, launch plumbing for this feature, and docs.

- [X] T070 [P] LG-002 CI containment test (same style as `test_tracked_relevant_text_has_no_private_paths_or_credentials`): the three-vector check (content grep, `git ls-files` path scan, base64-pattern scan) failing on any hit outside the exact governance allowlist `.charter/`, `.specify/`, `docs/open-source-launch-gates.md`, `specs/001-depersonalize-identifiers/**`
- [X] T071 [P] README + CONTRIBUTING breaking-change note: contract v2 rejection semantics and the regenerate remedy; LG-008 fallback (unregenerable shape → PocketSmith re-sync)
- [X] T072 Fix pre-existing adjacent defect: stale comment at `src/v4_pipeline/accounting.py:899-900` if not already covered by T010 (verify, do not duplicate) — verified covered by PR1/T010: grep for the stale text finds nothing; the surviving comment at :978 correctly describes server-side computation
- [X] T073 Run full quickstart.md validation (Scenarios 1-8) on the final tree; record outputs — 2026-09-16 all PASS, matrix in `launch-evidence-2026-09-16.md`
- [X] T074 Record LG-002 launch evidence (all three verification outputs) appended to `docs/open-source-launch-gates.md` or an adjacent dated evidence file — recorded in `launch-evidence-2026-09-16.md` (inside the governance carve-out so the guard stays green)d evidence file — **launch-gate bookkeeping only; the actual LG-001 fork/LG-004 purge remain launch-time actions outside this feature**

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2 : T003-T004)**: blocks US2 wiring and US1 task T011 (label fallback) — complete first.
- **US1 (Phase 3)**: internally sequential by stacked-PR order (PR1 → PR2 → PR3 → PR4 → PR5); each PR must be independently CI-green (T013 transitional adapter exists precisely for this).
- **US2 (Phase 4)**: depends on Foundational; bills contract (T043-T045) can start in parallel with late-US1 PRs but FE bills work (T047-T048) must follow PR4's TS type updates to avoid file conflicts in `client/src/types/api.ts` consumers.
- **US3 (Phase 5)**: depends on US1 PR2 (T017 — new keys are what the contract marker protects); T063 needs PR4 client conventions.
- **Polish (Phase 6)**: after all stories.

### Within Each Story

- Tests that pin a contract land with (or before) the behavior they pin; FR-008 forbids weakened assertions.
- Producers (v4) before consumers (budget_api → mega/mom → client) — rename direction.

### Parallel Opportunities

- Phase 1: T001 ∥ T002.
- US1 PR1: T010 ∥ T011 ∥ T014; PR2: T016 ∥ T019; PR3: T020 ∥ T021; PR4: T023 ∥ T024 ∥ T025 ∥ T026; PR5: T028 ∥ T029.
- US2: T041 ∥ T043 ∥ T046; T050 independent.
- US3: T063 ∥ backend chain (T060-T062, T064-T065).
- Phase 6: T070 ∥ T071.

---

## Stacked PR mapping

| PR (plan.md) | Tasks |
|---|---|
| PR1 v4_pipeline | T010-T014 (+ T003/T004 validator foundation) |
| PR2 budget_api | T015-T019, T040, T042-T045, T060-T062, T064 |
| PR3 mega + mom | T020-T022 |
| PR4 client | T023-T027, T046-T049, T063 |
| PR5 fixtures/docs/CI | T028-T030, T050, T065, T070-T074 |

## Parallel Example: US1 PR4 wave

```text
Task: "Update TS mirrors report.ts + category_mappings.ts"      (T023)
Task: "Rename keys in DetailedSections.tsx"                     (T024)
Task: "Rename keys in mega-reports components"                  (T025)
Task: "Scrub theme.css comment"                                 (T026)
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Phase 1 + Phase 2 → validator green
2. Phase 3 US1 in stacked-PR order → tree grep-clean, suites green
3. **STOP and VALIDATE** quickstart Scenarios 1-2 before US2/US3

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 → **the repo is publishable-blocker-free** (SC-001/002) — the core launch gate
3. US2 → third-party usability proven (SC-003/005)
4. US3 → breaking-change honesty proven (SC-004)
5. Phase 6 → continuous verification + launch evidence

---

## Notes

- The canonical validator lives in `v4_pipeline` (lowest shared layer); `budget_api` wraps it — never the reverse (Principle VI).
- Never key logic on resolved label strings anywhere (LG-007); labels are render-only.
- Old bills snapshots never 500; identity-neutral rendering replaces the forbidden positional inference.
- Old monthly/mega payloads are REJECTED loud (409), never coerced — reject **before** validation.
- Governance allowlist is the only sanctioned remainder in the tracked tree; identical in the CI containment test and the LG-002 launch command.
