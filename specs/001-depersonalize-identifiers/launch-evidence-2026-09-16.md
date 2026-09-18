# Launch evidence — 2026-09-16 (working record for LG gates)

All outputs recorded from the repo root of the candidate tree on branch
`001-depersonalize-identifiers`. This file lives under the LG-002 governance
carve-out and is not carried into the public history-reset repo (LG-001).

## LG-002 / SC-001 — quickstart Scenario 1 (three vectors)

### Vector 1 — content (case-insensitive)

```powershell
git grep -n -i 'christian\|rasma\|gjedrem' -- .
```

Result: **PASS** — zero matches outside the LG-002 carve-outs.
All printed matches are confined to `.charter/`, `.specify/`,
`docs/open-source-launch-gates.md`, and `specs/001-depersonalize-identifiers/`
(governance inventory / tooling templates only).

### Vector 2 — tracked path names

```powershell
git ls-files | Select-String -Pattern 'christian','rasma','gjedrem'
```

Result: **PASS** — no output (0 hits).

### Vector 3 — encoded (base64 byte-offset-0 literals)

```powershell
git grep -n 'Q2hyaXN0aWFu\|Y2hyaXN0aWFu\|UmFzbWE\|cmFzbWE\|R2plZHJlbQ\|Z2plZHJlbQ' -- .
```

Result: **PASS** — matches only in `docs/open-source-launch-gates.md` (the
command documentation itself) and `specs/001-depersonalize-identifiers/quickstart.md`,
both inside the carve-outs.

### Containment guard (R7 / T070)

```powershell
$env:PYTHONPATH='src'; python -m pytest src/mom/tests/test_lg002_identifier_containment.py -q
```

Result: **PASS** — `3 passed`. The guard encodes the identical three vectors and
carve-out list, so CI and the launch command cannot disagree. (Note: the
quickstart's older reference path `src/budget_api/tests -k containment` was
updated to this module; the `-k containment` selector works in either suite.)

## Full quickstart validation (Scenarios 1–8) — final tree, commit 830308a

| Scenario | Gate | Automated leg executed | Result |
|----------|------|------------------------|--------|
| S1 zero identifiers | SC-001, LG-002 | three git vectors above + `pytest src/mom/tests/test_lg002_identifier_containment.py` | **PASS** (3 passed) |
| S2 full suites | SC-002, FR-008 | BE: 791 passed; Windows parity `-m "not pdf_renderer"`: 789 passed, 2 deselected; client: vitest 246/247 — sole failure = pre-existing SyncPage date-drift, identical on baseline (accepted deviation; see note below) | **PASS** (SC-002 met on all changed files; the one failing case is a documented pre-existing deviation, not a regression) |
| S3 old report rejected | SC-004, FR-006, LG-005 | `pytest src/budget_api/tests/reports -k "contract or regen"`: 11 passed (409 names month + regenerate remedy; v2 roundtrip 200; TestClient exercises the HTTP layer in lieu of live-server manual steps) | **PASS** |
| S4 regen smoke | LG-008 | `pytest test_regen_smoke.py test_golden_fixture.py`: 8 passed (v2 monthly + mega from sample fixture, bills schema 5 + partner_id, recursive legacy-string walk clean, golden byte-pinned) | **PASS** |
| S5 config-driven labels | SC-003, FR-002/005 | `pytest src/budget_api/tests/test_partners.py`: 30 passed; client LG-007 rename-invariance vitest cases in the 246-pass set | **PASS** |
| S6 no-config first run | SC-005, FR-003 | placeholder-default tests (`-k "placeholder or default_label"`): 2 passed; client identity-neutral render tests (filter hidden, neutral dots, placeholders) in the 246-pass set | **PASS** |
| S7 bad config degrades | LG-006 | `pytest test_label_escaping.py test_label_xss.py`: 4 passed; write-path 400s covered by test_partners.py (30) | **PASS** |
| S8 launch hygiene | LG-003 | `git ls-files data/private out`: 0 entries; `git check-ignore -v data/private/partner_labels.json`: matched `.gitignore:16 **/data/private/` | **PASS** |

Known pre-existing items recorded, unchanged by this feature: `pnpm build`
halts on TS5103 (config deprecation) — `pnpm test` (vitest) is the client gate;
SyncPage date-drift vitest failure identical on baseline.

**Launch actions NOT reproducible here:** LG-001 (history-reset public fork) and
LG-004 (local artifact purge in `data/private/`, `out/`) are maintainer
launch-time actions; this tree is their verified input.

Conclusion: SC-001..SC-005 and LG-002/003/005/006/007/008 verified on the
candidate tree. Remaining to launch: LG-001 fork + LG-004 purge (LG-008's
unregenerable-shape fallback is documented in README "Breaking changes").
