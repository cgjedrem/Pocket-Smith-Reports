# Specification Quality Checklist: Runway & Burn Rate

**Purpose**: Validate specification completeness and quality before proceeding to planning.
**Created**: 2026-10-31
**Feature**: [spec.md](../spec.md)

**Review Ownership**: This is a reviewer-owned requirements-quality artifact maintained by the specify/clarify lifecycle.
**Marker Semantics**: `[x]` means the requirements-quality criterion was reviewed and satisfied. It does not mean implementation, testing, runtime acceptance, or a downstream gate has passed.

## Content Quality

- [x] CHK001 No implementation details (languages, frameworks, APIs). The spec prescribes observable calculations, eligibility, presentation, and constraints; no stack, route, storage layout, or code structure is prescribed.
- [x] CHK002 Focused on user value and business needs. US1–US5 cover understanding spending, deliberately selecting reserves, judging evidence, recovery, and presentation privacy.
- [x] CHK003 Written for non-technical stakeholders. US1 and FR-002 define gross burn and runway; owner attribution, undefined values, coverage, and non-advice limitations are explained in plain language.
- [x] CHK004 All mandatory sections completed. User Scenarios & Testing, Requirements, and Success Criteria are populated; Key Entities and Assumptions are also complete.

## Requirement Completeness

- [x] CHK005 No unresolved clarification markers remain. A-001–A-008 record bounded unattended assumptions; no unanswered product decision is delegated to the user.
- [x] CHK006 Requirements are testable and unambiguous. FR-003–FR-018 specify the exact window, minimum observations, filters, validation, selection scope, attribution, and availability; FR-026 fixes rounding.
- [x] CHK007 Success criteria are measurable. SC-001–SC-008 define numerical equality/tolerance, completeness checks, zero-leak/zero-fabrication conditions, two-minute configuration, two-second bounded loading, and one-second masking.
- [x] CHK008 Success criteria are technology-agnostic. Outcomes concern user-visible correctness, timing, preservation of choices, and comprehension, not implementation mechanisms.
- [x] CHK009 All acceptance scenarios are defined. Every story has Given/When/Then examples and an independent synthetic verification description; EC-01–EC-11 supply adjacent boundaries.
- [x] CHK010 Edge cases are identified. Calendar rollover, missing/partial/zero history, transfers, duplicates, invalid money, selection changes, currency conflicts, stale/unknown evidence, and legacy/racing responses are covered.
- [x] CHK011 Scope is clearly bounded. FR-019–FR-021 and FR-027 exclude historical runway reconstruction, live sync, scheduling, forecast/advice, and report-contract changes; A-005–A-007 exclude debt/assets, lifestyle creep, new integrations, and dependencies.
- [x] CHK012 Dependencies and assumptions are identified. A-001–A-006 identify existing ownership/category authorities, local sources, single-currency limits, absent coverage/date evidence, Bills conventions, and the privacy control.

## Feature Readiness

- [x] CHK013 All functional requirements have clear acceptance criteria. The coverage table below maps all 27 requirements to scenarios, edge cases, and measurable outcomes.
- [x] CHK014 User scenarios cover primary flows. P1 covers the comparison, reserve configuration, and evidence validity; P2 covers resilient Bills integration and existing privacy behavior. All remain required for delivery.
- [x] CHK015 The feature is specified against measurable outcomes in Success Criteria. SC-001–SC-008 cover every primary flow; this check confirms specification coverage, not that an unimplemented feature meets those outcomes.
- [x] CHK016 No implementation details leak into the specification. `null`, fixed mask text, currency rules, no-store privacy, and compatibility limits describe required behavior without choosing implementation.

### Acceptance coverage

`USn.m` means acceptance scenario m within User Story n. These are requirement references, not executed checks.

| Requirements | Acceptance coverage | Outcomes |
| --- | --- | --- |
| FR-001–FR-002 | US1.1–US1.5; US2.1–US2.2 | SC-001, SC-004, SC-008 |
| FR-003–FR-005 | US3.1–US3.4, US3.8; EC-01–EC-02 | SC-002–SC-003 |
| FR-006–FR-008 | US1.3; US3.4; EC-03–EC-05, EC-07 | SC-001, SC-003 |
| FR-009–FR-012 | US2.1–US2.5, US2.7; EC-06–EC-07 | SC-003–SC-004, SC-006 |
| FR-013–FR-015 | US1.2, US1.4; US2.6; EC-09 | SC-001, SC-003, SC-008 |
| FR-016–FR-018 | US3.1–US3.7; EC-02, EC-07–EC-09 | SC-002–SC-003 |
| FR-019 | US3.8; EC-11 | SC-001–SC-003, SC-008 |
| FR-020–FR-021 | US2.1–US2.2; US4.1, US4.5, US4.7; EC-11 | SC-004–SC-006 |
| FR-022–FR-023 | US4.1–US4.6; EC-08, EC-11 | SC-004–SC-006 |
| FR-024–FR-025 | US5.1–US5.3; US4.7 | SC-007 |
| FR-026 | US1.1–US1.2; EC-10 | SC-001, SC-003 |
| FR-027 | US1.5; A-003–A-005 | SC-008 |

## Notes

- **Review result (2026-10-31)**: 16/16 requirements-quality checks satisfied after direct review. First-pass findings were resolved: explicit state rules for partial-window qualifications, deterministic halfway rounding, a local-only/no-store acceptance scenario, and an unambiguous five-fact comprehension outcome. No unresolved specification-quality findings remain.
- **Templates**: Resolved `spec-template` and `checklist-template` using the repository's `Resolve-Template` preset stack (overrides → enabled presets → extensions → core). Both resolved to `.specify/templates/`. Mandatory headings/order and checklist ownership semantics were retained; sample content was replaced.
- **Grounding**: Read the supplied discovery artifact `1793465902647-copilot-tool-output-6e1b5392320945d5b3fa7b9c885405d1.txt` in full. Cross-checked repository instructions, `.specify/memory/constitution.md` v1.0.2, `CONTRIBUTING.md`, `docs/DATA_POLICY.md`, and feature 002's privacy specification. No real financial data was inspected.
- **Coverage decision**: Unknown completeness is not a verified full month. FR-005/A-002 allow only a visibly qualified recorded-spending comparison from valid positive observations, reject known partial/invalid sources and unproven zeros, and prohibit completeness claims or fallback values. This is not permission to relax existing report-build fail-closed rules.
- **Selection/currency decisions**: Household reserves cover explicitly selected accounts, not all assets. Missing selected balances block the household total; an owner with no selection is not given a fabricated zero. Known currency conflicts block aggregation; unknown currency is disclosed, not verified or converted.
- **Branch-hook exception**: The caller reports that the coordinator invoked the mandatory `speckit.git.feature` skill. Its branch-creation step cannot execute under the runtime's app-managed-branch restriction. The existing dedicated branch was retained; this pass neither reinvoked specify/the branch hook nor claims successful branch creation. No hook configuration was changed.
- **Optional after-specify hooks**: `speckit.git.commit` and `speckit.agent-context.update` were not executed: leave changes uncommitted and do not overwrite unrelated agent context.
- **Downstream gates**: The mandatory plan-review gate before tasks remains enabled and pending with the coordinator. Its default-remote-branch/unchanged-artifact prerequisites are not satisfied merely by this local draft. No plan, tasks, red-team review, waiver, or gate bypass was produced or executed here.
- **Evidence boundary**: Static requirements review only. Build, automated tests, runtime integration, and user acceptance were not run; no production code or migration was created. The private-source completeness and currency assumptions are not claims about the user's actual data.
- **Handoff**: Feature context is persisted in `.specify/feature.json` as `docs/specs/003-runway-burn-rate`. Specification-quality review is complete; the coordinator owns the next authorized phase and its gates. Incomplete downstream evidence must not be reported as acceptance.
