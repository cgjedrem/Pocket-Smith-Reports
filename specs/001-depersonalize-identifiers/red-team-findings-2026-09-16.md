# Red Team Findings: RT-001-depersonalize-identifiers-2026-09-16

**Session ID**: RT-001-depersonalize-identifiers-2026-09-16
**Target spec**: `specs/001-depersonalize-identifiers/spec.md`
**Date**: 2026-09-16
**Maintainer**: ChristianGjedrem
**Lenses run**: Regulatory Adversary, Trust-Boundary Adversary
**Selection method**: auto (2 lenses, both trigger-matched; ≤5 → no ranking needed)
**Triggers matched**: money_path, contracts, multi_party
**Supporting context**: n/a (no plan.md / tasks.md yet — spec is pre-plan)
**Wall clock**: ~80s from dispatch to both responses

---

## §1 Session Summary

Two trigger-matched lenses (Regulatory Adversary, Trust-Boundary Adversary)
attacked the spec pre-plan and returned 9 findings: **1 CRITICAL, 4 HIGH,
4 MEDIUM** (CRIT:1 / HIGH:4 / MED:4). All 9 were walked through with the
maintainer 2026-09-16 and resolved **spec-fix ×9**, with every fix landed in
the forward-facing canonical record `docs/open-source-launch-gates.md`
(LG-001..LG-008; F-006 absorbed into LG-002). Zero accepted-risk, zero open
questions, zero unresolved. The CRITICAL (history exposure) was resolved
architecturally: the public launch is a history-reset fork (LG-001), so no
history scrubbing is required.

---

## §2 Findings table

| # | Lens | Severity | Status | Location | Description | Suggested resolution |
|---|------|----------|--------|----------|-------------|----------------------|
| **F-RT-001-001** | Regulatory | CRITICAL | ✅ | Assumptions — "Git history will retain the old identifiers… out of scope" | The spec's stated goal is that publishing the repository must not expose the household's identities, yet it explicitly defers history-scrubbing as a "separate launch-time decision" with no blocking dependency recorded. A public repo whose history contains every old commit re-exposes all identifiers at release — the de-identification claim would be indefensible because the release artifact itself disproves it. | Make history disposition (scrub or history-reset) a mandatory, blocking precondition of public launch, recorded as a requirement or explicit launch gate tied to this feature — not an unscoped assumption. |
| **F-RT-001-002** | Regulatory | HIGH | ✅ | Assumptions / FR-001 / SC-001 (removal list) | The identifier removal list is defined only as "the two personal names (in all casings), plus any code identifiers derived from them," with an unverified "evidence pass" promised later. No requirement to produce a versioned, enumerable identifier inventory or a documented, reproducible search procedure — auditors expect a deterministic control list, not best-efforts enumeration validated by a single clean-checkout grep. | Add an FR requiring a committed artifact enumerating every identifier and variant (names, initials, derived code identifiers, nicknames) plus the exact search command/pattern set used, so SC-001 is independently repeatable. |
| **F-RT-001-003** | Regulatory | HIGH | ✅ | FR-006 / US-3 / Key Entities ("Stored report") | The remedy for pre-change stored reports is regeneration, but the spec never requires locating/deleting/migrating existing stored payloads that contain personal-section keys and personal names. Those files persist indefinitely in user-local directories as residual PII; "out of scope because untracked" does not eliminate the maintainer's own pre-launch artifacts. | Add a requirement for an explicit migration/disposal path (inventory + delete or regenerate-on-upgrade) for legacy stored reports; state that regeneration deletes or overwrites the old-key artifact rather than leaving it alongside the new one. |
| **F-RT-001-004** | Trust-Boundary | HIGH | ✅ | FR-002 / Edge Cases ("No configuration present") | User-local configuration is an implicitly trusted input whose contents flow unvalidated into reports, dashboards, and UI rendering. The spec defines behavior only for *absent* config (FR-003) — a present-but-malformed (invalid JSON, wrong types, empty strings) or malicious (over-length, HTML/script markup) file has no specified handling. | Add an FR requiring schema validation of partner-label config (shape, type, max length) with defined fallback to neutral placeholders plus a visible warning, and require display names to be escaped at render time. |
| **F-RT-001-005** | Trust-Boundary | HIGH | ✅ | FR-006 / US-3 / SC-004 | "Fails loudly" is specified only as an outcome, with no detection mechanism. If the new code ignores unknown keys rather than rejecting unknown payloads, a pre-change report — or a partially overlapping/corrupted one — can parse partially and silently misroute/mislabel transactions, the exact failure mode the spec calls worse than an explicit break. | Require an explicit contract-version marker in stored reports and mandate rejection of absent/unrecognized versions, making loud failure structural; add an acceptance scenario covering a partially overlapping pre-change payload. |
| **F-RT-001-006** | Regulatory | MEDIUM | ✅ | SC-001 / FR-001 (identifier vectors) | The success criterion covers literal text matches on tracked files but does not address other vectors: file and directory paths, embedded copies in generated/lock files, URL- or base64-encoded occurrences, or docs prose. A regulator treating "zero matches" against an unspecified search method would mark pass/fail as unverifiable. | Define the search surface explicitly in SC-001 (paths + contents, tracked generated artifacts, common encodings) and require the verification to cover all enumerated vectors, results recorded as launch evidence. |
| **F-RT-001-007** | Regulatory | MEDIUM | ✅ | Edge Cases ("Configuration that itself contains personal identifiers") / FR-002 | The spec waives responsibility for personal names in user-local config as "the user's own," but provides no control preventing a user (or the maintainer) from accidentally committing that config — with real names — into the now-public repository. No required .gitignore coverage, config-file location convention, or launch-time check asserting config paths are untracked. | Add an FR that all configuration paths capable of holding partner labels are covered by tracked .gitignore rules and that the launch verification (SC-001) confirms no config-derived file is present in the tracked tree. |
| **F-RT-001-008** | Trust-Boundary | MEDIUM | ✅ | FR-004 / FR-005 | Nothing in the spec forbids identity, styling, or aggregation logic keyed on the resolved display label instead of the stable partner-neutral key, and no requirement enforces that the two configured labels be distinct. A user configuring a label colliding with a placeholder (e.g., "Partner A") or with a residual comparison value, or configuring two identical labels, gets misattributed rows or styles — a low-privilege config input bypassing identity gating. | Add an FR stating all logic/styling decisions reference only the stable partner-neutral identifiers, never resolved display strings; require config validation that rejects duplicate labels or defines dedupe behavior. |
| **F-RT-001-009** | Trust-Boundary | MEDIUM | ✅ | Assumptions / US-3 (regeneration remedy) | The sole remedy for the breaking change — regenerate from source transactions — is recorded only as an assumption, not a verified requirement. If regeneration is unavailable for some reports (pruned source data, or a regeneration path broken by the same rename), affected users are stranded with unreadable data and no remedy. | Promote the assumption to an FR verified by an automated test covering regeneration of every historical report type, or define an explicit fallback path (export/migration utility) when regeneration is impossible. |

---

## §3 Resolutions Log

| ID | Resolution category | downstream_ref | Notes |
|----|---------------------|----------------|-------|
| F-RT-001-001 | spec-fix | `docs/open-source-launch-gates.md#lg-001` | Launch reframed as a history-reset fork (single clean initial commit), not a scrub. Closes the critical exposure; no `filter-repo` needed. |
| F-RT-001-002 | spec-fix | `docs/open-source-launch-gates.md#lg-002` | Committed identifier inventory + reproducible `git grep` command; also absorbs F-RT-001-006 (underspecified search surface). |
| F-RT-001-003 | spec-fix | `docs/open-source-launch-gates.md#lg-004` | Maintainer pre-launch artifact purge (inventory + regenerate-or-delete) added as launch gate. |
| F-RT-001-004 | spec-fix | `docs/open-source-launch-gates.md#lg-006` | Config validation: shape/type/length + fallback + visible warning; render escaping. |
| F-RT-001-005 | spec-fix | `docs/open-source-launch-gates.md#lg-005` | Contract-version marker on stored reports; missing/unknown version → loud rejection, never partial parse. |
| F-RT-001-006 | spec-fix | `docs/open-source-launch-gates.md#lg-002` | Search-surface enumeration + reproducible command in LG-002 covers this concern. |
| F-RT-001-007 | spec-fix | `docs/open-source-launch-gates.md#lg-003` | .gitignore coverage of config paths + launch verification of clean tracked tree already mandated by LG-003. |
| F-RT-001-008 | spec-fix | `docs/open-source-launch-gates.md#lg-007` | Logic keys on stable neutral identifiers only; placeholder/duplicate labels rejected at config validation. |
| F-RT-001-009 | spec-fix | `docs/open-source-launch-gates.md#lg-008` | Regeneration smoke test in CI for all historical report shapes; re-sync as documented fallback. |

---

## §5 Session metadata

```yaml
session_id: RT-001-depersonalize-identifiers-2026-09-16
target_spec: specs/001-depersonalize-identifiers/spec.md
date: 2026-09-16
maintainer: ChristianGjedrem
lenses: [Regulatory Adversary, Trust-Boundary Adversary]
selection_method: auto
selection_note: "2 lenses trigger-matched (≤5) — no ranking prompt needed"
supporting_context: []
triggers_matched: [money_path, contracts, multi_party]
wall_clock_seconds: 80
findings:
  total: 9
  by_severity:
    CRITICAL: 1
    HIGH: 4
    MEDIUM: 4
    LOW: 0
  by_lens:
    Regulatory Adversary: 5
    Trust-Boundary Adversary: 4
dropped_findings: 0
lens_failures: []
resolution_counts:
  spec_fix: 9
  new_oq: 0
  accepted_risk: 0
  out_of_scope: 0
  unresolved: 0
dogfood_session: false
notes:
  - "Pre-plan session (no plan.md/tasks.md yet); spec is the sole target"
  - "Both adversaries returned structured findings without failure"
  - "All 9 findings resolved to spec-fixes in docs/open-source-launch-gates.md (#lg-001..008; -006 absorbed into -002)"
  - "F-RT-001-001 (history) resolved as history-reset fork — scrubbing ruled out as unnecessary"
source_of_truth: docs/open-source-launch-gates.md
```
