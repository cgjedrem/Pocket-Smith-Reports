# Common Economy Split

Configurable proportional split of shared household expenses between the two
partners, with a netted settlement transfer shown on monthly and mega reports.

## Configuration

Settings page section "Common economy split" → `GET/PUT /api/settings/split`.

Persisted privately in `split_config.json`:

```json
{
  "enabled": true,
  "shares": { "partner_a": 60.0, "partner_b": 40.0 },
  "sections": ["home", "common", "trips"]
}
```

Rules:

- Shares are global (one pair for all included sections), each 0–100, and
  **must sum to exactly 100** (tolerance 1e-6; `PUT` returns 422 otherwise).
- Non-finite values (NaN/±Infinity) are rejected with 400/raise at both the
  API boundary and the pipeline re-validation boundary (`math.isfinite`
  guards in `routers/settings.py::_validate_shares` and
  `accounting.normalize_split_config`).
- `sections` ⊆ `SPLIT_ELIGIBLE_SECTIONS` (`home`, `common`, `trips`).
- No config file or `enabled: false` → reports behave exactly as before
  (`split` / `split_summary` are `null`).
- `GET` additionally returns a display-only `labels: {partner_a, partner_b}`
  object resolved server-side via the partner slot map. Labels are **never**
  persisted.

## Math

Per included category (leaf level; subcategories resolved the same way as the
net sections):

- `actual` — what partner_a actually paid-reimbursed (existing net convention)
- `fair` = category total × `shares.partner_a` / 100
- `delta` = `actual − fair` (positive: partner_a overpaid)

Rows are partner_a's perspective; partner_b's numbers are the complement
(sums to 100%, exactly two partners).

Settlement: deltas are summed across all included categories and **netted to
one transfer**. `abs(total_delta) <= 1e-6` → `settlement: null` (balanced;
no fabricated zero transfers). Otherwise
`{from_partner, to_partner, amount}` with real display labels.

## Surfaces (all three in parity, same pure functions)

| Surface | Where | Notes |
|---|---|---|
| Monthly JSON DTO | `report_builder.py` → `detailed.split` | `CALCULATION_VERSION` 9; v7/v8 payloads omit the field and render unchanged |
| Monthly HTML/PDF | `accounting_html.py::_legacy_split_section` | Reuses `accounting.net_category_totals`/`compute_split` — byte-identical numbers |
| Mega report | `mega_builder._split_section_nets` → `split_summary` | Aggregated from `detail_agg["cats"]` (same source as mega's own section totals; avoids drift). `MEGA_CALCULATION_VERSION` 2 |

Config changes do NOT mark stored reports stale (same pre-existing behavior as
category mappings); regenerate the report to recompute.

## Validation status codes

- 422 — shares don't sum to exactly 100 (the one deliberate non-400 in this router)
- 400 — out-of-range / non-finite share, unknown section, malformed body
- 500 — corrupt `split_config.json` on disk
