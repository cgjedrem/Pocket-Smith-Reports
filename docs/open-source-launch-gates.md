# Open-Source Launch Gates — Pocket-Smith-Reports

Forward-facing canonical record for the open-source launch. Supersedes the loose
assumptions in `docs/specs/001-depersonalize-identifiers/spec.md` where they
conflict; that spec file is a historical SpecKit record and is not edited after
ratification (per the red-team skill's immutability rule, changes land here).

**Status**: Active
**Feature**: 001-depersonalize-identifiers
**Spec ref**: `docs/specs/001-depersonalize-identifiers/spec.md`
**Findings basis**: `docs/specs/001-depersonalize-identifiers/red-team-findings-2026-09-16.md`

---

## LG-001 — Public launch is a history-reset fork (resolves F-RT-001-001)

The public repository is created as a **fresh repo containing a single clean
initial commit** of the de-personalized tree. No history is carried over.

- The current private repo remains the upstream archive; retiring it is a
  separate, optional decision and is not a precondition for launch.
- This replaces any plan to publish the current repo's history (including any
  `filter-repo` rewrite of it).
- Launch gate: the new repo's **only** commits are the initial clean commit
  and forward changes made after the reset. Verifiable by `git log --oneline`
  on the new repo — any pre-reset SHA present = gate FAIL.

**Why this is chosen over scrubbing**: scrubbing rewrites history but keeps a
long tail of old objects retrievable; a fresh initial commit removes the
question entirely. It also satisfies SC-001 ("zero identifiers in tracked
files") trivially, because the tree published is by construction the already
de-personalized tree.

---

## LG-002 — Identifier inventory and reproducible verification (resolves F-RT-001-002, F-RT-001-006)

A committed, versioned inventory enumerates every personal identifier targeted
for removal, plus the exact search command used to verify zero hits.

### Identifier inventory (removal list)

| # | Identifier | Variants covered |
|---|-----------|-----------------|
| I-001 | Christian | `christian`, `Christian`, `CHRISTIAN`; substrings e.g. `personal_christian`; whole-word diminutive `chris` (guard word vector) |
| I-002 | Rasma | `rasma`, `Rasma`, `RASMA`; substrings e.g. `personal_rasma`; whole-word diminutive `rsm` (guard word vector) |
| I-003 | Gjedrem | any occurrence in tracked source/config (currently only tooling examples — see notes) |

Notes: docs-prose vector is covered by the content search below. Filenames and
directory paths are a separate vector — the content search does not inspect
them, so a dedicated tracked-path check is required (below). Encoded payloads
(base64/URL encoding of the identifiers) do NOT retain the literal substring
and likewise need their own scan; both non-content vectors' outputs are
recorded as launch evidence alongside the content output.

### Verification commands (reproducible)

Run all three from the repo root on a clean checkout of the candidate tree;
SC-001 requires PASS on every command and all outputs recorded as launch
evidence in this file (or an adjacent dated evidence file).

```powershell
# 1) Content vector — file CONTENTS across the tracked tree:
git grep -n -i 'christian\|rasma\|gjedrem' -- .
# PASS = no matches outside the carve-outs below. (Zero matches => exit 1.)

# 2) Path vector — TRACKED PATH NAMES (git grep does not inspect these):
git ls-files | Select-String -Pattern 'christian','rasma','gjedrem'
# PASS = no output.

# 3) Encoded vector — common encodings of the identifiers (base64 literals at
#    byte-offset 0; any other suspicious token must be decoded and inspected):
git grep -n 'Q2hyaXN0aWFu\|Y2hyaXN0aWFu\|UmFzbWE\|cmFzbWE\|R2plZHJlbQ\|Z2plZHJlbQ' -- .
#   (Q2hyaXN0aWFu="Christian", Y2hyaXN0aWFu="christian", UmFzbWE="Rasma",
#    cmFzbWE="rasma", R2plZHJlbQ="Gjedrem", Z2plZHJlbQ="gjedrem")
# PASS = no matches.
```

Carve-outs (only permitted remainders): `.charter/` and `.specify/` tooling
templates, plus the governance files that must name the identifiers to be
meaningful — this file and `docs/specs/001-depersonalize-identifiers/` — which per
LG-001 are not carried into the public fresh-fork repo.

---

## LG-003 — Config files holding partner labels are untracked-by-construction

All configuration paths capable of holding partner display names
(`data/private/partner_labels.json` and any successors) are covered by tracked
`.gitignore` rules; the launch verification confirms no config-derived file is
present in the published tree.

---

## LG-004 — Legacy local artifacts are inventoried and purged pre-launch (resolves F-RT-001-003)

Before the public repo's initial push, the maintainer inventories local artifact
directories capable of holding PII from pre-change runs — `out/`,
`data/private/`, `docs/specs/**/out/` — and either regenerates every stored report
with the de-personalized build (which overwrites the old payload) or deletes
unregenerable ones. No pre-change stored report containing old partner names may
remain on the maintainer's machine at launch.

- Scope is the maintainer's own pre-launch artifacts, not past user machines.
- Regeneration replaces the artifact in place; purge is for leftovers.
- Evidence: a short purge log (files removed/regenerated count) recorded as
  launch evidence.

---

## LG-005 — Stored reports carry a contract-version marker; unknown versions rejected (resolves F-RT-001-005)

Every newly stored report includes an explicit contract-version marker (e.g.,
`contract_version: 2`). Readers MUST reject reports with an absent or
unrecognized version rather than parse them partially; rejection surfaces a
"regenerate this report" affordance. Silence-as-success is not allowed: reading
a pre-change report MUST fail loudly.

- Verification: a test feeds a pre-change payload (old keys) and asserts a
  rejection, plus an acceptance scenario covering a partially overlapping
  payload.

---

## LG-006 — Partner-label config is schema-validated and escaped at render (resolves F-RT-001-004)

`partner_labels.json` (and any successor config carrying display names) is
validated before use:

- Shape: object with exactly the partner keys the contract expects
  (`partner_a`, `partner_b`); extra keys warn, missing keys fall back.
- Types: string values only; non-strings fall back to the default placeholder.
- Length: max 64 characters per label; longer inputs are truncated with a
  warning.
- Render: display labels are escaped (no raw HTML injection into reports/UI).

Any validation failure surfaces a visible warning and falls back to the neutral
placeholders rather than crashing or silently rendering bad data.

---

## LG-007 — Logic keys on stable neutral identifiers only (resolves F-RT-001-008)

All partner-scoped logic, styling, aggregation, and comparisons reference only
the stable partner-neutral identifiers (e.g., `partner_a`, `personal_a`) — never
resolved display-label strings. In particular:

- No FE/BE code path compares against a display label to distinguish partners.
- Configuration with two identical labels is rejected at validation time
  (falls back to placeholders with a visible warning), rather than silently
  producing ambiguous attribution.
- Placeholder labels themselves are reserved and rejected as configured
  values for the same reason.

---

## LG-008 — Regeneration coverage is verified, not assumed (resolves F-RT-001-009)

A regeneration smoke test in CI proves every historical stored-report shape can
be regenerated from its source transactions under the new de-personalized
contract. For report shapes that cannot be regenerated (e.g., source data
pruned), re-sync from PocketSmith is the documented fallback — a note in
CONTRIBUTING.md/README explains the path. The de-personalized code is not
permitted to ship if any historical shape fails the regeneration smoke test.

---
