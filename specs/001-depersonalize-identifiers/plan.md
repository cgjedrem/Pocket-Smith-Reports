# Implementation Plan: De-personalize identifiers for open-source launch

**Branch**: `001-depersonalize-identifiers` | **Date**: 2026-09-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-depersonalize-identifiers/spec.md`

**Binding constraints**: Open-source launch gates LG-001..LG-008 (`docs/open-source-launch-gates.md`)
**Code evidence**: `code-evidence.md` (verified full call-graph trace, 2026-09-16)

## Summary

Remove every removal-list personal identifier (LG-002 inventory: I-001 `Christian`, I-002 `Rasma`, I-003 `Gjedrem`, all casings and derived code identifiers) from the tracked tree and make partner display identity configuration-driven end to end. Three mechanics:

1. **Neutral contract keys.** Rename the canonical report section keys `personal_christian`/`personal_rasma` → `personal_partner_a`/`personal_partner_b`, keyed on the existing stable ids `partner_a`/`partner_b`, applied consistently from the `v4_pipeline` math engine outward through `budget_api` (DTO, builder, settings enum), `mega`, `mom`, the React client, and tracked fixtures (FR-004/FR-005).
2. **Configuration-driven display names.** Replace every hardcoded display name (BE HTML fallbacks, FE mega-reports/settings strings, bills FE label comparisons) with `partner_labels` resolved from the gitignored user-local `data/private/partner_labels.json` (FR-002/FR-003, LG-003), schema-validated with visible warnings and placeholder fallback (LG-006); labels are display-only and never logic keys (LG-007). Bills payloads gain an additive neutral `partner_id` so the FE can stop comparing display strings.
3. **Deliberately breaking contract revision.** Stored monthly and mega reports gain an explicit top-level `contract_version: 2` marker (FR-006, LG-005). Readers reject absent/unknown versions loudly — HTTP 409 with a regenerate affordance — before any rendering, because the new DTO fields are optional-by-default and an old payload would otherwise validate with empty personal sections (the exact silent failure FR-006 forbids). Regeneration from source transactions is the remedy; a CI regeneration smoke test (LG-008) proves historical report shapes regenerate under the new contract; LG-002's committed inventory and reproducible `git grep` verification prove the tree is clean.

**Breaking-change honesty**: pre-change stored reports are REJECTED, never coerced or partially rendered (FR-006 + LG-005). Remedy: regenerate from `data/private/{month}_ps_raw.json`; where source data was pruned, PocketSmith re-sync is the documented fallback (LG-008). This is intentional and is surfaced in the API error, the UI, and the README.

**Delivery**: stacked PR chain (trunk-based stacking per `docs/memory/patterns.md`, 2026-07-30):
- PR1 — `v4_pipeline` rename (accounting.py, accounting_html.py, v4 tests, sample fixture payloads) **plus a transitional 2-line adapter in `budget_api/services/report_builder.py`** that reads `personal.get("personal_partner_a", personal.get("personal_christian"))` (and the `b` pair) so budget_api keeps passing CI against the renamed producer before PR2 lands
- PR2 — `budget_api` contract (DTO + report_builder full contract update — **removing the transitional adapter** — + category_mappings enum + `contract_version` rejection + label validation + golden regeneration + version bumps)
- PR3 — `mega` + `mom` (keys, alias-collapse in section_personal.py, appendix titles)
- PR4 — client (reports/mega/settings/bills components, TS mirrors, mocks, tests)
- PR5 — remaining test-fixture scrub (bills test slugs), docs prose scrub (designs/, docs/design/), LG-002 verification evidence + containment test, LG-008 CI smoke test, README/CONTRIBUTING notes

Fixtures consumed by a given layer land in that layer's PR (golden regeneration in PR2 is mandatory — the golden payload embeds the renamed keys).

## Technical Context

**Language/Version**: Python 3.13 (pipelines + FastAPI service); TypeScript 5 / React 19 (client) — both pinned by constitution, unchanged

**Primary Dependencies**: FastAPI 0.140.x, pydantic ≥2, pytest (backend); Vite 6, Tailwind CSS v4, Radix/shadcn primitives, vitest + Testing Library (client). **No new dependencies.**

**Storage**: JSON files under gitignored `data/private/`: monthly reports `{YYYY-MM}_monthly_report.json`, mega reports `{start}_{end}_mega_report.json`, bills snapshots `bills_dashboard_{month}.json`, partner-label config `partner_labels.json` (LG-003). Tracked golden fixture `src/budget_api/tests/reports/golden/sample_apr_2026_report.json`; tracked synthetic source fixture `data/sample_apr_2026.json` + `data/sample_apr_2026_detailed_section_mapping.json`.

**Testing**: pytest colocated in `src/{mega,v4_pipeline,mom,budget_api}/tests`, canonical command `PYTHONPATH=src python -m pytest src/mega/tests src/v4_pipeline/tests src/mom/tests src/budget_api/tests -q`; vitest via `pnpm test` in `client/`; CI dual-OS (`ubuntu-latest` full suite, `windows-latest` with `-m "not pdf_renderer"`), `.github/workflows/ci.yml`.

**Target Platform**: Windows 11 dev (PowerShell 5.1/7+ per Principle IX); local-first FastAPI bound to 127.0.0.1:8000; Vite SPA on localhost.

**Project Type**: Single repo — Python report pipelines + FastAPI service + React SPA.

**Performance Goals**: N/A — contract rename/refactor with no hot-path or algorithm changes; report build times must not regress materially (same code paths, renamed keys).

**Constraints**:
- Fail-closed only (Constitution II): incompatible stored data → loud rejection, never partial render.
- Synthetic-only tracked fixtures with neutral labels (Constitution I, FR-007).
- `git grep -i 'christian|rasma|gjedrem'` over tracked files → zero hits outside the exact governance allowlist (`.charter/`/`.specify/` tooling templates, `docs/open-source-launch-gates.md`, `specs/001-depersonalize-identifiers/**`) per LG-002/R7 — the same allowlist the CI containment test and the launch command both apply. This covers docs prose in `designs/` and `docs/design/`.
- Bills snapshots never 500 on old files (repo convention, memory index) — additive-with-defaults + `schema_version` bump.
- Monthly-reports reader keeps the render-with-`stale:true` convention for *additive* drift (`TestReportResponseCompat`); the *breaking* contract path is the new loud rejection.

**Scale/Scope**: ~100 tracked files carry removal-list hits (verified by full-tree grep 2026-09-16); ~26 carry the load-bearing `personal_*` contract keys (code-evidence.md Q3); 5 stacked PRs; 3 stored-artifact contracts (monthly, mega, bills) + 1 config schema.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Pre-research evaluation (2026-09-16) against `.specify/memory/constitution.md` v1.0.0:

| Principle | Verdict | Basis |
|---|---|---|
| I. Real financial data never in VC (NON-NEGOTIABLE) | **PASS** (feature directly serves it) | Identifiers scrubbed from tracked tree; `partner_labels.json` stays gitignored (LG-003); fixtures become fully synthetic with neutral labels (FR-007); data flow paths (`data/private/`) unchanged |
| II. Pipelines fail closed | **PASS** (strengthened) | LG-005 rejection replaces the current silent-ignore render path (verified: new optional DTO fields would validate old payloads as empty sections — rejection check is therefore load-bearing); label validation warns + falls back, never crashes (LG-006) |
| III. Publishing is atomic and staged | **PASS** | Publish/staging/manifest flow untouched; regeneration uses the existing build+write path |
| IV. Python 3.13 with pinned deps | **PASS** | No dependency or pin changes |
| V. PocketSmith API client hardened | **PASS** (out of scope) | No PS client changes; re-sync fallback (LG-008) uses existing hardened sync |
| VI. Backend layers separated | **PASS** | Validation helpers in `services/`/`v4_pipeline`; DTO changes in `models/`; routers stay thin — new work is mapping `IncompatibleContractError`→409 |
| VII. React 19 + Vite + TS via pnpm | **PASS** | Components stay thin; partner identity arrives as an API field; no new deps; `pnpm build` + `pnpm test` gates retained (lint gate still pending — pre-existing, unchanged) |
| VIII. Tests colocated, gate merges | **PASS** | Tests updated in place to the new keys with equivalent-or-stronger assertions (FR-008); new rejection/smoke tests land in existing suite dirs so the canonical command and dual-OS CI are unchanged |
| IX. Windows PowerShell platform | **PASS** | Quickstart and LG-002 verification commands are PowerShell-first, `;`-gated, UTF-8-safe |

**Result: no violations. Complexity Tracking not required.**

Post-design re-check (2026-09-16, after research.md + data-model.md + contracts/ + quickstart.md): **PASS — no drift**. Design introduced no new dependencies (IV holds), no directory/layer changes (VI holds — validator lives in `v4_pipeline`, rejection mapping stays thin in routers), tests remain colocated in existing suite dirs with the canonical command and dual-OS CI unchanged (VIII holds), all quickstart/verification commands are PowerShell-first (IX holds), and the fail-closed posture is strengthened by the LG-005 rejection design (II). Complexity Tracking remains empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-depersonalize-identifiers/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── code-evidence.md     # Verified code trace grounding this plan (read-only subagent)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── README.md
│   ├── monthly-report-contract-v2.md
│   ├── partner-labels-config.md
│   └── bills-partner-identity.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

Existing single-repo layout (no structural changes; all work is in-place renames/additions):

```text
src/
├── v4_pipeline/            # PR1: canonical math engine
│   ├── accounting.py       #   DETAILED_CATEGORY_SECTIONS, HOUSEHOLD_COMPOSITION,
│   │                       #   detailed_personal_sections(), load_partner_labels(),
│   │                       #   NEW canonical validate_partner_labels()
│   ├── accounting_html.py  #   section keys; hardcoded name fallbacks at :818-819;
│   │                       #   html.escape label rendering (already compliant)
│   └── tests/              #   mapping fixtures "christian"->"personal_christian" etc.
├── budget_api/             # PR2: API contract layer
│   ├── models/
│   │   ├── reports.py            # DetailedSections DTO fields (:240-241); ReportResponse
│   │   ├── category_mappings.py  # DETAILED_CATEGORY_SECTIONS validation enum (:17-18)
│   │   └── bills.py              # schema_version 4->5; additive partner_id fields
│   ├── services/
│   │   ├── report_builder.py     # keys (:207-208); NEW contract_version; NEW
│   │   │                         # IncompatibleContractError on read; label validation
│   │   ├── mega_builder.py       # contract_version on mega payloads
│   │   ├── bills_builder.py      # emit partner_id on events/partners
│   │   └── storage.py            # paths unchanged
│   ├── routers/
│   │   ├── reports.py            # 409 mapping for incompatible stored reports
│   │   ├── bills.py              # ?partner_id= filter replaces ?partner= label filter
│   │   └── partners.py           # label write-path uses shared validator
│   └── tests/                    # golden regen (sample_apr_2026_report.json) + LG-005/008 tests
├── mega/build_mega.py      # PR3: section_routes, section_series keys (:277-278, :511-519)
├── mom/sections/           # PR3: section_personal.py alias map collapses (identity),
│                           #   section_appendices.py appendix key list (:43-47)
└── live_sync.py            # untouched (no identifier coupling)

client/                     # PR4: React SPA
├── src/types/              # report.ts (:230-231), category_mappings.ts (:17-18,55-56),
│                           # api.ts F2Partner (:113), bills.ts
├── src/components/
│   ├── reports/DetailedSections.tsx      # key renames + comment scrub
│   ├── mega-reports/                     # buildNavItems.ts, PersonalSection.tsx,
│   │                                     # AppendicesSection.tsx hardcoded titles
│   ├── settings/CategoryMappingsEditor.tsx  # dropdown labels from partner_labels
│   └── bills/                # GraphView, BillsDashboard, BudgetTab, EconomyBar,
│                             # EventRow, TableView, SavingsSparkline: key on partner_id
├── src/styles/theme.css    # :45-46 comment scrub
└── tests/, src/**/__tests__/  # fixtures + mocks to new keys/ids

data/                       # fixtures (land with consuming layer's PR)
├── sample_apr_2026.json                        # payee/category-title scrub (FR-007)
└── sample_apr_2026_detailed_section_mapping.json   # "7"/"8" -> new section keys

docs/                       # PR5: designs/*.md, docs/design/*.md prose scrub (LG-002)
.github/workflows/ci.yml    # unchanged — smoke test lands inside existing suite dirs
```

**Structure Decision**: Existing layout retained verbatim (Principle VI three-layer `budget_api`, colocated tests per Principle VIII). No directory moves, no new projects: the feature is a contract rename plus validation/rejection additions inside the current modules. The canonical label validator lives in `v4_pipeline` (the lowest shared layer — `budget_api` already imports it; the reverse is forbidden), wrapped by `budget_api` services.

## Complexity Tracking

N/A — Constitution Check has no violations; nothing to justify.

## Follow-ups (spec record)

- `spec.md` is intentionally NOT edited (historical SpecKit record; red-team immutability rule). Its Assumption "Git history will retain the old identifiers … whether to scrub history is a separate launch-time decision" is **superseded by LG-001** (public launch = history-reset fork with a single clean initial commit). Any spec amendment lands in `docs/open-source-launch-gates.md` per its preamble.
- `.specify/` and `.charter/` tooling templates retain example identifier strings; LG-002 explicitly carves these out of the verification gate.
- Pre-existing (not this feature): stale comment at `src/v4_pipeline/accounting.py:899-900` references a hardcoded FE array that no longer exists (code-evidence.md notes); `client/package.json` still lacks `packageManager` pin and lint script (constitution follow-up TODO). Track separately.
