# Common Economy Split

Configurable proportional split of shared household expenses between the two
partners, with a netted settlement transfer shown on monthly and mega reports.

## Configuration

Settings page section "Common economy split" → `GET/PUT /api/settings/split`.

Persisted privately in `split_config.json` (current category-based schema):

```json
{
  "enabled": true,
  "shares": { "partner_a": 60.0, "partner_b": 40.0 },
  "categories": ["<catalog category id>", "..."],
  "sections": ["home", "common"]
}
```

`categories` is the source of truth; `sections` is server-derived from it
(`derive_split_sections`) on every GET/PUT and persisted only as a
back-compat display field.

Rules:

- Shares are global (one pair for all selected categories), each 0–100, and
  **must sum to exactly 100** (tolerance 1e-6; `PUT` returns 422 otherwise).
- Non-finite values (NaN/±Infinity) are rejected with 400/raise at both the
  API boundary and the pipeline re-validation boundary (`math.isfinite`
  guards in `routers/settings.py::_validate_shares` and
  `accounting.normalize_split_config`) — **for enabled configs**. Share
  sum/finiteness validation only runs when `enabled: true`:
  `normalize_split_config` returns `None` for `enabled: false` before ever
  inspecting `shares`, so a non-finite share in a disabled config is not
  rejected at report-build time (it is simply unused). The API boundary
  (`PUT`) always validates shares/categories regardless of `enabled`, so a
  disabled config can only reach that state via manual file edits.
- Selection is by arbitrary catalog category ID (any tree level; selected
  parents are expanded to their leaves via `_resolve_allowed_category_ids`).
  Only legacy sections-only files are migrated:
  `migrate_legacy_split_sections` maps the three legacy section values
  (`home`, `common`, `trips` — `SPLIT_ELIGIBLE_SECTIONS`) to their member
  category IDs.
- No config file or `enabled: false` → reports behave exactly as before
  (`split` / `split_summary` are `null`).
- `GET` additionally returns a display-only `labels: {partner_a, partner_b}`
  object resolved server-side via the partner slot map. Labels are **never**
  persisted.

## Math

Per selected category (leaf level; subcategories resolved the same way as the
net sections):

- `actual` — what partner_a actually paid-reimbursed (existing net convention)
- `fair` = category total × `shares.partner_a` / 100
- `delta` = `actual − fair` (positive: partner_a overpaid)

Rows carry partner_a's perspective plus partner_b's exact additive complement
(`actual_b` = total − actual, `fair_b` = total − fair, `delta_b` = −delta) —
two partners, shares sum to 100%. Rows are grouped by derived section in
canonical display order.

Settlement: deltas are summed across all selected categories and **netted to
one transfer**. `abs(total_delta) < 0.005` (half-cent display snap — the same
threshold the renderers' totals-row dust snap uses) → `settlement: null`
(balanced; no fabricated zero or "owes 0.00" transfers). Otherwise
`{from_partner, to_partner, amount}` with real display labels.

All renderers show the same shape: a two-sided 7-column table (both partners'
actual/fair/delta), a totals row as the table's last row, and the settlement
sentence below the table; |value| < 0.005 snaps to zero on display so a
balanced split never prints "-0.00".

## Surfaces (all in parity, same pure functions)

| Surface | Where | Notes |
|---|---|---|
| Monthly JSON DTO | `report_builder.py` → `detailed.split` | `CALCULATION_VERSION` 10; v9 payloads lack the partner_b complement fields (totals cells render an em-dash); pre-v9 payloads omit the field and render unchanged |
| Monthly React | `DetailedSections.tsx` → `CommonEconomySplitSection` | Renders `detailed.split`; half-cent `snapDust` on totals |
| Monthly HTML/PDF | `accounting_html.py::_legacy_split_section` | Reuses `accounting.net_category_totals`/`compute_split` — byte-identical numbers |
| Mega JSON DTO | `mega_builder.compute_mega_split_summary` → `split_summary` | `_split_category_nets` runs `net_category_totals` per month on that month's `normalized_transactions` and sums by category (NOT `detail_agg["cats"]` — that aggregation has no transfer gate and would double-count). `MEGA_CALCULATION_VERSION` 3 |
| Mega React | `KpiCoverSection.tsx` → `SplitSummaryCard` | Renders `split_summary`; same 7-column table + totals row + settlement sentence |
| Mega HTML/PDF | `build_mega.py::_render_split_summary` | Renders the precomputed `split_summary`; never recomputes |

Config changes do NOT mark stored reports stale (same pre-existing behavior as
category mappings); regenerate the report to recompute.

## Validation status codes

- 422 — shares don't sum to exactly 100 (the one deliberate non-400 in this router)
- 400 — out-of-range / non-finite share, unknown category ID, malformed body
- 500 — corrupt `split_config.json` on disk
