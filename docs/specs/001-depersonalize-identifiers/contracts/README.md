# Contracts — 001-depersonalize-identifiers

This repo's external interfaces are: stored JSON artifacts (monthly/mega reports, bills snapshots), the local FastAPI surface, and the user-local partner-label config. Pydantic models in `src/budget_api/models/` and the TS mirrors in `client/src/types/` remain the executable source of truth; these documents define the *delta* this feature introduces and the rules readers/writers must honor.

| Contract | File | Summary |
|---|---|---|
| Stored monthly + mega report, contract v2 | [monthly-report-contract-v2.md](monthly-report-contract-v2.md) | Explicit `contract_version: 2`; renamed personal-section keys; loud rejection of v1 payloads (LG-005) |
| Partner-label config | [partner-labels-config.md](partner-labels-config.md) | Schema, validation, fallback, warnings, escaping (LG-003/006/007) |
| Bills partner identity | [bills-partner-identity.md](bills-partner-identity.md) | Additive `partner_id`, `schema_version` 4→5, `?partner_id=` filter (LG-007) |

Versioning rules introduced by this feature — **two distinct semantics, do not conflate**:

- `contract_version` (monthly + mega stored reports) — breaking contract identity. Absent or unrecognized → **reject loudly** (HTTP 409 / CLI error) with a regenerate affordance. Never parse partially, never render (LG-005).
- `calculation_version` (monthly + mega) / `schema_version` (bills) — additive/content-drift markers.
  - Monthly/mega: the read endpoint computes a `stale` flag by comparing the stored `calculation_version` against the current one — mismatch → served with `stale: true` (existing convention, `bumped 6 → 7`).
  - Bills: **no stale flag exists or is introduced** — the bills read endpoint never computes staleness. A `schema_version` mismatch is handled purely by additive-with-defaults compat: old snapshots deserialize with default values for new fields and the client degrades gracefully (identity-neutral rendering, per bills-partner-identity.md). Regeneration refreshes either way.
