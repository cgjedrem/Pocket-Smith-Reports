# Data Model: Hide Amounts Toggle

**Feature**: `002-hide-amounts-toggle` | **Date**: 2026-10-02

The feature has exactly one piece of state. No server entities, no financial
data, no schema changes.

## MaskPreference (client-only)

| Field | Type | Values | Default |
|-------|------|--------|---------|
| `hidden` | boolean | `true` = amounts masked, `false` = visible | `false` |

- **Storage**: `localStorage["psr:hide-amounts"]` — `"1"` (hidden) / `"0"`
  (visible). Absent or unparsable ⇒ default `false` (visible). Fail-open to
  visible matches FR-007's "fresh browser shows real amounts"; persistence is
  a convenience, not a safety boundary (spec Assumptions).
- **Scope**: one preference per browser profile, shared across all pages.
- **Lifetime**: no expiry; changed only via the toggle.

## State transitions

```text
visible --[toggle click / setAmountsHidden(true)]--> hidden
hidden  --[toggle click / setAmountsHidden(false)]--> visible
(any)   --[page load]--> read localStorage, fall back to visible
```

## Derived behavior (not stored)

- `maskAmount(formatted)` → `"****"` when `hidden`, else input unchanged.
- Empty/blank labels stay empty — the mask MUST NOT turn an absent value
  (e.g. `realCcBillLabel: ""` for a future month) into `"****"`, since that
  would falsely imply a value exists.
- The mask string is a constant (`AMOUNT_MASK = "****"`); it is not
  localized and never embeds the sign, magnitude, or currency of the
  underlying value.
