# Contract: Partner-Label Configuration

**File**: `data/private/partner_labels.json` — user-local, untracked-by-construction (covered by `.gitignore` `data/private/`; LG-003). No tracked code writes it; users create it by hand or via the partners settings API (`account_mappings.json partners[].label` is the secondary source).

## Schema

```json
{
  "partner_a": "string, 1–64 chars",
  "partner_b": "string, 1–64 chars"
}
```

## Validation (LG-006 + LG-007) — `validate_partner_labels(raw) -> (labels, warnings)`

Applied at every load (report build, mega build, PDF render, CLI) and at settings write (`PUT /api/partners/{id}` → 400 on hard-invalid). Canonical implementation in `src/v4_pipeline/accounting.py`; `budget_api` wraps it.

| Rule | Failure behavior |
|---|---|
| Root is an object | non-object → both placeholders + warning |
| Keys `partner_a` / `partner_b` present | missing key → that partner → placeholder + warning |
| Values are strings | non-string → placeholder + warning |
| Length ≤ 64 chars | longer → truncate to 64 + warning |
| Labels distinct (case-insensitive) | duplicate → BOTH → placeholders + warning (ambiguous attribution is worse than neutral) |
| Not reserved placeholders (`Partner A` / `Partner B`, empty, whitespace-only) | rejected → placeholder + warning |

Defaults / placeholders: `{"partner_a": "Partner A", "partner_b": "Partner B"}` (FR-003, SC-005). A household with one configured partner gets the other as placeholder, rendered as placeholder — not as a real second partner (spec edge case).

**Failure-mode invariant**: validation failure never crashes a build and never silently renders the bad value; it always degrades to placeholders + a visible warning.

## Warnings surfacing

- `logging.warning` on every violation (BE/CLI).
- Each built report payload carries `warnings: list[str]` (new additive field, default `[]`) so the client can display configuration warnings next to the report.
- CLI report builds print warnings to stderr.

## Escaping (LG-006 render half)

- HTML/PDF: every label interpolation uses `html.escape` (already true at all sites — verified `accounting_html.py`); regression test injects `<img src=x onerror=alert(1)>` as a label and asserts escaped output in HTML and PDF-source HTML.
- Client: labels render as React text only (never `dangerouslySetInnerHTML`).

## Resolution order (unchanged)

1. `partner_labels.json` flat map → 2. `account_mappings.json partners.partner_{a,b}.label` → 3. defaults.

## What labels may NEVER be used for (LG-007)

No FE/BE code path compares a resolved label to distinguish partners. All partner-scoped logic keys on `partner_a`/`partner_b` (or `personal_partner_a`/`personal_partner_b` section keys, or bills `partner_id`). Label strings are render-only.
