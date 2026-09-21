# Phase 1 Data Model — 001-depersonalize-identifiers

**Date**: 2026-09-16 | **Sources**: spec.md Key Entities, `docs/open-source-launch-gates.md`, `code-evidence.md`.

## Entity 1 — PartnerLabelConfig (user-local, untracked)

**Storage**: `data/private/partner_labels.json` (gitignored — LG-003; also falls back to `account_mappings.json partners[].label`). Never committed.

| Field | Type | Constraints |
|---|---|---|
| `partner_a` | string | 1–64 chars (longer truncated + warning, LG-006); non-string → fallback + warning |
| `partner_b` | string | same |

**Validation rules** (canonical `validate_partner_labels` in `src/v4_pipeline/accounting.py`; applied at every load and at settings write):
- Unknown extra keys → warning, ignored. Missing key → that partner gets the placeholder + warning.
- `partner_a` label ≠ `partner_b` label (case-insensitive) — duplicates rejected (LG-007).
- Reserved placeholders `Partner A` / `Partner B` rejected as configured values (LG-007).
- Any failure → neutral placeholder for the affected partner(s) + visible warning; never a crash, never silent bad render (LG-006).

**Defaults / placeholders**: `{"partner_a": "Partner A", "partner_b": "Partner B"}` (FR-003).

**Surfacing**: resolved labels embedded in `StoredMonthlyReport.partner_labels` and `partner_panels`; rendered via `html.escape` (HTML/PDF) or React text nodes (client); warnings collected into `StoredMonthlyReport.warnings` and CLI stderr.

## Entity 2 — DetailedSectionKey (contract enum)

Canonical registry: `DETAILED_CATEGORY_SECTIONS` in `src/v4_pipeline/accounting.py:16-26`; duplicate validation enum in `src/budget_api/models/category_mappings.py:11-21`; TS mirrors in `client/src/types/{report.ts,category_mappings.ts}`.

**Rename map** (the only members changing):

| Old (v1) | New (v2) |
|---|---|
| `personal_christian` | `personal_partner_a` |
| `personal_rasma` | `personal_partner_b` |

Unchanged members: `income_salary`, `income_third_party`, `savings`, `home`, `common`, `trips`, `cc_payments`, `excluded`.

**Producers/consumers of the renamed members** (verified inventory — code-evidence.md Q3): `accounting.py` (registry, `HOUSEHOLD_COMPOSITION`, `detailed_personal_sections()`), `accounting_html.py` (grouped dict, household composition, legacy personal renderer), `models/reports.py` `DetailedSections` DTO, `report_builder._detailed`, `models/category_mappings.py` enum, `mega/build_mega.py` (section_routes, section_series, composition), `mom/sections/section_personal.py` (alias map collapses to identity → deleted), `mom/sections/section_appendices.py`, fixtures (`sample_apr_2026_detailed_section_mapping.json`, golden payload), client components listed in plan.md, and both BE/FE test suites.

**Validation rule**: settings API rejects values outside the enum (existing 400 behavior, `routers/category_mappings.py:121-127`) — unchanged semantics, new members.

## Entity 3 — StoredMonthlyReport (`data/private/{YYYY-MM}_monthly_report.json`)

Top-level shape (from golden fixture + `build_report` return, code-evidence.md Q1d):

| Field | Change |
|---|---|
| `contract_version` | **NEW — required, integer `2`** |
| `calculation_version` | bumped 6 → 7 (staleness marker — semantics unchanged) |
| `detailed` | object keyed by the 10 `DetailedSections` **DTO keys** (distinct from the `DETAILED_CATEGORY_SECTIONS` enum): `income, savings, home, common, personal_partner_a, personal_partner_b, trips, cc_payments, excluded, household_totals` |
| `detailed.personal_partner_a` / `.personal_partner_b` | renamed from `personal_christian` / `personal_rasma`; each a `PersonalSection` object (subtotals, pct, rows) or null |
| `partner_labels` | unchanged shape `{"partner_a": str, "partner_b": str}`; values now always validator-sanctioned |
| `partner_panels` | unchanged shape; labels sanitized; keyed by neutral `partner_a`/`partner_b` |
| `warnings` | **NEW — additive `list[str]`, default `[]`** (label-validation warnings) |
| `month, txn_count, balanced, kpis, categories, root_totals, owner_totals, household_totals, personal_share, personal_share_partner_a, personal_share_partner_b, savings_summary, reconciliation, normalized_transactions, detailed_section_mapping` | unchanged semantics (key spellings inside `detailed_section_mapping.category_sections` values follow the rename) |
| `stale` | read-side only (never stored); unchanged |

**State transitions**:
```
[absent] --POST /generate (202 async)--> [stored v2, current]
[stored v2, current] --GET--> 200, stale=false
[stored v2, calculation_version drift or txn-count drift] --GET--> 200, stale=true   (additive-drift convention preserved)
[stored v1 | contract_version absent | unknown] --GET--> 409 IncompatibleContractError  (LG-005 — never validated, never rendered)
[any stored] --POST /generate--> regenerated in place from {month}_ps_raw.json  (FR-006 remedy)
```

**Validation rules**: reader checks `contract_version == 2` BEFORE `ReportResponse.model_validate` (load-bearing — new DTO fields are optional-by-default, so a v1 payload would otherwise validate silently with null personal sections); DTO strict-validates the rest; invalid JSON/corrupt → existing 404/500 behavior unchanged.

## Entity 4 — StoredMegaReport (`{start}_{end}_mega_report.json`)

| Field | Change |
|---|---|
| `contract_version` | **NEW — `2`**, same absent/unknown rejection rule |
| `MEGA_CALCULATION_VERSION` | unchanged staleness marker |
| section payloads | personal sections keyed/titled from neutral keys + configured labels (mom `section_appendices.py` titles already parameterized by label) |

State machine mirrors StoredMonthlyReport.

## Entity 5 — BillsSnapshot (`data/private/bills_dashboard_{month}.json`)

| Field | Change |
|---|---|
| `schema_version` | 4 → 5 |
| `events[].partner_id` | **NEW additive** `"partner_a" \| "partner_b"` (display label `partner` retained for rendering) |
| partner blocks `partner_id` | **NEW additive**; per-month `partners[]` order stays deterministic (sorted by partner id) for legacy-slot fallback |
| `partner` (label string) | kept — display-only from now on; FE logic NEVER reads it (LG-007) |

Legacy schema-4 snapshots remain readable (no 500 convention); FE `??`-guards + order-based slot fallback until re-synced.

## Entity 6 — FixtureData (tracked, synthetic-only — FR-007)

`data/sample_apr_2026.json`: 43 transactions; ownership derived synthetically (`_synthetic_owner`: id ranges `[100000,200000)` → `partner_a`, account-name prefixes `Fixture A`/`Fixture B`) — **unchanged mechanism**. Renamed content:
- Payees: `Personal Payee Christian 1` → `Personal Payee A 1`, `Personal Payee Rasma 1` → `Personal Payee B 1` (…n).
- Category titles: `Test Personal Christian` → `Test Personal A`, `Test Personal Rasma` → `Test Personal B`.
- No value may collide with any real person's name (spec edge case).

`data/sample_apr_2026_detailed_section_mapping.json`: `"7": "personal_partner_a"`, `"8": "personal_partner_b"`; `account_roles` already neutral (`savings_partner_a/b`).

BE/FE test fixtures: partner slug ids `christian`/`rasma` in `budget_api/tests` and client mocks → `partner_a`/`partner_b` (they are derived identifiers; removal list covers them).

## Entity 7 — IdentifierInventory (documentation entity, LG-002)

Committed at `docs/open-source-launch-gates.md`: removal list I-001 (`Christian`), I-002 (`Rasma`), I-003 (`Gjedrem`) with all casings/derived substrings; verification command `git grep -n -i 'christian\|rasma\|gjedrem' -- .`; carve-out scope (`.charter/`, `.specify/` tooling templates; the inventory docs themselves — see research.md R8); dated verification evidence recording.

## Relationships

```
PartnerLabelConfig ── resolves ──> StoredMonthlyReport.partner_labels / partner_panels
                                      │                                   │
DetailedSectionKey ── keys ──> StoredMonthlyReport.detailed ── renders ──> accounting_html (escape) ──> PDF
        │                                    │                                     │
        └──── validated by category_mappings enum                          client DetailedSections.tsx
        │
        └──── consumed by mega build_context / mom sections (contract_version 2 gate)
BillsSnapshot.partner_id  <── account_mappings.partner_id ── emitted by bills_builder
IdentifierInventory ── verified by ── containment test + launch evidence
```
