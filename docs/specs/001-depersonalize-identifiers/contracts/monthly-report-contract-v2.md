# Contract: Stored Monthly Report v2 (and Mega Report)

**Applies to**: `data/private/{YYYY-MM}_monthly_report.json`, `data/private/{start}_{end}_mega_report.json`
**Readers**: `GET /api/reports/monthly/{month}` (`routers/reports.py:62-73`), mega read router, `report_pdf.py`, client reports/mega views.
**Writers**: `report_builder.build_report`/`write_report` (`report_builder.py:300-356`), `mega_builder`.

## Version markers

| Field | Value in v2 | Semantics |
|---|---|---|
| `contract_version` | `2` (integer, top-level, REQUIRED on write) | Breaking-contract identity. **Reader rule: absent or ≠ 2 → reject before any validation or render.** |
| `calculation_version` | `7` | Content/staleness marker (existing `check_stale` semantics unchanged: mismatch → `stale: true`, still renders) |

The pre-check is load-bearing, not decorative: v2 DTO fields follow the repo's optional-with-defaults convention, so a v1 payload (old keys `personal_christian`/`personal_rasma`, no marker) would otherwise pass `ReportResponse.model_validate` with null personal sections and render empty sections as if valid — the exact silent failure FR-006/LG-005 forbid.

## Reader behavior contract

| Stored payload condition | Response |
|---|---|
| No file | 404 `"no report generated yet"` (unchanged) |
| `contract_version: 2`, valid shape, current `calculation_version`+txn count | 200, `stale: false` |
| `contract_version: 2`, valid shape, drifted `calculation_version`/txn count | 200, `stale: true` (additive-drift convention preserved) |
| `contract_version` absent (any keys, incl. mixed old/new) | **409** — detail names the report month and instructs regeneration |
| `contract_version` present, unknown value | **409** — same |
| `contract_version: 2` but invalid shape | 500 (corrupt-data case; existing behavior class) |

Mechanics: `report_builder.read_report` (and the mega equivalent) raise `IncompatibleContractError(month, found_version)`; the router maps it to 409. The client renders the existing Regenerate affordance for 409s (same UX path as stale), so the remedy is one click: `POST /api/reports/monthly/{month}/generate` rebuilds from `data/private/{month}_ps_raw.json` and overwrites in place. Source data pruned → PocketSmith re-sync (LG-008 note in README/CONTRIBUTING).

## Renamed keys (the physical contract delta)

`detailed` object members:

```text
v1                              v2
personal_christian       →      personal_partner_a
personal_rasma           →      personal_partner_b
```

All other `detailed` keys unchanged: `income, home, common, personal_*, savings, trips, cc_payments, excluded, household_totals`.
The same rename applies to values inside `detailed_section_mapping.category_sections` (e.g. `"7": "personal_partner_a"`).
DTO fields: `DetailedSections.personal_partner_a: PersonalSection | None = None`, `.personal_partner_b` likewise (`models/reports.py`, replacing lines 240-241). TS mirror updated in `client/src/types/report.ts:230-231`.

## Skeleton (v2)

```json
{
  "month": "2026-04",
  "contract_version": 2,
  "calculation_version": 7,
  "txn_count": 43,
  "partner_labels": {"partner_a": "Partner A", "partner_b": "Partner B"},
  "warnings": [],
  "detailed": {
    "income": {}, "home": {}, "common": {},
    "personal_partner_a": null,
    "personal_partner_b": null,
    "savings": {}, "trips": {}, "cc_payments": {}, "excluded": {},
    "household_totals": {}
  },
  "detailed_section_mapping": {"category_sections": {"7": "personal_partner_a", "8": "personal_partner_b"}},
  "kpis": {}, "categories": [], "root_totals": {}, "owner_totals": {},
  "personal_share": 0, "personal_share_partner_a": 0, "personal_share_partner_b": 0,
  "savings_summary": null, "reconciliation": {}, "normalized_transactions": [],
  "balanced": true
}
```

(Field list mirrors the golden fixture exactly; see `data-model.md` Entity 3 for the full table. `stale` is added read-side only.)

## Mega reports

Same two-marker scheme: `contract_version: 2` added alongside the existing `MEGA_CALCULATION_VERSION` staleness marker; identical absent/unknown rejection rule; section data carries the renamed keys and label-resolved titles.

## Tests that pin this contract

- Golden regeneration: `src/budget_api/tests/reports/test_golden_fixture.py` (regenerated golden asserts `contract_version == 2`, new keys, byte-equality).
- Rejection: new tests feeding (a) v1 payload with old keys, (b) mixed/partial payload — both assert 409, no render.
- Compat preservation: `TestReportResponseCompat` updated — additive drift still renders with `stale: true`; only contract-v1 payloads reject.
- Version pins: golden `calculation_version == 7`, `contract_version == 2`.
