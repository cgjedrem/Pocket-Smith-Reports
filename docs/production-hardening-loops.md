# Report Hardening Roadmap

This roadmap tracks public code and synthetic-fixture work only. It contains
no local exports, credentials, account identifiers, or generated reports.

**Current delivery:** Loops 0-4 merged through
[PR #6](https://github.com/enso-dev-beep/Pocket-Smith-Reports/pull/6) on
2026-07-24 (merge commit `67f7b9005507b285dd0d357f6f9dfbe6d3b040b7`). Ubuntu
and Windows CI checks passed for Loops 0-3.

**Merged maintenance:** [PR #7](https://github.com/enso-dev-beep/Pocket-Smith-Reports/pull/7)
updates v4 to publish HTML, PDF, and manifest artifacts under repository-root
`out/`, independent of the current working directory, with safe
publishing/recovery.

| Loop | Status | Delivered / Goal | Validation |
| --- | --- | --- | --- |
| 0 | Merged | Contain private financial data; establish synthetic fixtures and the local-data boundary. | Current-tree containment guard; tracked-text checks; [data policy](DATA_POLICY.md). |
| 1 | Merged | Normalize accounting inputs into a deterministic monthly report contract. | Focused v4 accounting tests; [mixed-category decision](decision-mixed-category-accounting.md). |
| 2 | Merged | Make the MoM PDF release path fail closed: validate inclusive months, stage HTML/PDF, and publish only a non-empty PDF. | Release-gate tests; Ubuntu PDF-render CI; Windows renderer-free CLI coverage. |
| 3 | Merged | Restore detailed monthly Income, Savings, Home, Common, personal, Trips, and transfer sections; retain KPI cover; add four report themes; remove the unused legacy template; fix review findings and print pagination. | `python -m pytest src/v4_pipeline/tests src/mom/tests -q` (`92 passed`); Ubuntu/Windows CI passed; regenerated minimal local HTML/PDF; output escaping, safe sync errors, repeat table headers, intact rows, and large-drilldown pagination covered. |
| 4 | Merged | Route detailed monthly sections from configured stable category/account IDs and section roles, rather than historical titles or display names. Route the exact configured `CC Payment (paired)` category separately; do not also place its matched duplicate legs in Excluded. Route title-based `Internal Reimbursement` consistently to Excluded. Give `--savings-account-id` precedence over configured savings roles. | Focused routing/accounting tests; configured production-category-ID regression; synthetic renamed-category and renamed-account checks; v4 and Mega regression coverage for excluded legacy `transaction_account` records; UTF-8 Norwegian report verification; final HTML/PDF artifact and layout inspection in local `out/`. |
| 5 | Planned | Convert reconciliation and reimbursement matching to `Decimal` or integer minor units; normalize transaction IDs before sorting. | Fractional-currency, mixed-ID, exact-pair, and near-pair regression tests. |
| 6 | Planned | Improve the legacy `v7_mega` report. | Focused synthetic regression tests and generated-report inspection. |
| 7 | Planned | Develop dynamic budgeting as requirements are defined. | Validation defined with the approved scope. |
| 8 | Planned | Develop forecasting as requirements are defined. | Validation defined with the approved scope. |

## Boundaries

- Do not commit private PocketSmith data or generated reports.
- Do not change accounting policy without an approved decision and reconciliation tests.
- The report-structure rename is a separate future migration in
	[the rename map](report-structure-rename-map.md); it is not part of PR #4.

## Loop 4 Lessons

- Stable IDs and configured section roles are routing inputs; category and
	account titles are display labels and may change.
- The exact configured `CC Payment (paired)` category must route as paired
	movement. Its matched duplicate legs must stay out of Excluded.
- Detailed reports must resolve the configured stable category ID, while
	title-based reports must classify the same internal-routing semantics
	consistently. `Internal Reimbursement` belongs in Excluded, not Home.
- Routing regression coverage must exercise actual configured production
	category IDs as well as synthetic renamed-label fixtures. Label-only tests
	cannot prove production configuration remains connected to its section.
- Keep production section mappings in ignored private config. Keep the tracked
	sample mapping explicit in the quick-start command so fixture behavior is
	reproducible without private data.
- An explicit `--savings-account-id` is an operator override and must take
	precedence over configured savings-account roles.
- Verify Norwegian output by reading generated text as UTF-8. Tests alone do
	not confirm final PDF pagination, layout, or artifacts under local `out/`.

## Next Session

Start Loop 5 only after updating from `main`.

1. Convert reconciliation and reimbursement matching to `Decimal` or integer
	minor units without changing the completed routing contract.
2. Normalize transaction IDs before sorting and add fractional-currency,
	mixed-ID, exact-pair, and near-pair regression tests.
3. Keep report-structure rename work separate from Loop 5 accounting changes.