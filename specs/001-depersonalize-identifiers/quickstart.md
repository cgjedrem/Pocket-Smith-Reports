# Quickstart Validation — 001-depersonalize-identifiers

Runnable scenarios proving the feature end to end. Each maps to a success criterion / launch gate. Run from the repo root on Windows PowerShell unless noted. Contract details live in `contracts/`; entity rules in `data-model.md`.

## Prerequisites

```powershell
# BE env (one of the repo's existing flows)
pip install -e .            # or: uv sync
# FE deps
Set-Location client; pnpm install --frozen-lockfile; Set-Location ..
```

## Scenario 1 — Zero identifiers in tracked tree (SC-001, LG-002)

```powershell
git grep -n -i 'christian\|rasma\|gjedrem' -- .
$code = $LASTEXITCODE
# git grep exit codes: 0 = matches found, 1 = zero matches, >1 = command error.
if ($code -eq 1) { Write-Output 'PASS' }
elseif ($code -eq 0) { Write-Output 'FAIL — identifiers present (matches printed above)'; exit 1 }
else { Write-Output "FAIL — grep error (exit $code)"; exit $code }
# Expected PASS. Only permitted remainders: .charter/ and .specify/ tooling
# templates plus the governance inventory docs (docs/open-source-launch-gates.md,
# specs/001-depersonalize-identifiers/) — see LG-002 carve-outs.
```

The path-name and encoded-payload vectors of LG-002 are checked the same way:

```powershell
git ls-files | Select-String -Pattern 'christian','rasma','gjedrem'
if ((git ls-files | Select-String -Pattern 'christian','rasma','gjedrem').Count -eq 0) { Write-Output 'PASS' } else { Write-Output 'FAIL'; exit 1 }
git grep -n 'Q2hyaXN0aWFu\|Y2hyaXN0aWFu\|UmFzbWE\|cmFzbWE\|R2plZHJlbQ\|Z2plZHJlbQ' -- .
$code = $LASTEXITCODE; if ($code -eq 1) { Write-Output 'PASS' } elseif ($code -eq 0) { Write-Output 'FAIL'; exit 1 } else { exit $code }
```

The automated containment test (R7) runs the same check in CI:

```powershell
$env:PYTHONPATH = 'src'; python -m pytest src/mom/tests/test_lg002_identifier_containment.py -q
if ($?) { Write-Output "PASS" }
```

## Scenario 2 — Full backend + frontend suites (SC-002, FR-008)

```powershell
$env:PYTHONPATH = 'src'; python -m pytest src/mega/tests src/v4_pipeline/tests src/mom/tests src/budget_api/tests -q
if ($?) { Write-Output "BE PASS" }
# Windows parity leg (mirrors CI):
$env:PYTHONPATH = 'src'; python -m pytest src/mega/tests src/v4_pipeline/tests src/mom/tests src/budget_api/tests -m "not pdf_renderer" -q
if ($?) { Write-Output "BE PASS (no pdf_renderer)" }
Set-Location client; pnpm build; if ($?) { pnpm test }; Set-Location ..
# Expected: all green; no test deleted, no assertion weakened.
```

## Scenario 3 — Old stored report rejected loudly (SC-004, FR-006, LG-005)

```powershell
# Automated contract tests:
$env:PYTHONPATH = 'src'; python -m pytest src/budget_api/tests/reports -k "contract or regen" -q
if ($?) { Write-Output "PASS" }
# Manual end-to-end proof:
# 1. Copy a pre-change payload (or the pre-change golden) to
#    data/private/2026-03_monthly_report.json  (old keys, no contract_version)
# 2. Start API: scripts/run_api.ps1
# 3. GET http://127.0.0.1:8000/api/reports/monthly/2026-03
# Expected: HTTP 409, detail names the month and says to regenerate. NOT 200,
# NOT silently-empty personal sections, NOT a bare 500 stack trace.
# 4. POST /api/reports/monthly/2026-03/generate  (source data present)
# 5. GET again
# Expected: 200; payload has contract_version 2, detailed.personal_partner_a/b.
```

## Scenario 4 — Regeneration smoke test (LG-008)

```powershell
$env:PYTHONPATH = 'src'; python -m pytest src/budget_api/tests/reports/test_regen_smoke.py -q
if ($?) { Write-Output "PASS" }
# Expected: monthly + mega shapes regenerate from data/sample_apr_2026.json
# under contract v2; bills snapshot rebuilds at schema_version 5 with
# partner_id fields; recursive walk finds no legacy key strings.
# Golden byte-equality: src/budget_api/tests/reports/test_golden_fixture.py
```

## Scenario 5 — Config-driven labels end to end (SC-003, FR-002/FR-005)

```powershell
# 1. Create data/private/partner_labels.json with two arbitrary synthetic
#    labels, e.g. {"partner_a": "Ada Example", "partner_b": "Ben Example"}
# 2. Regenerate a month (Scenario 3 step 4), then GET it:
# Expected: partner_labels echo "Ada Example"/"Ben Example"; HTML/PDF section
# titles use them; no placeholder text; dashboard sections keyed consistently.
# 3. Open the client bills dashboard: partner colors/filters follow partner_id;
#    renaming a label does NOT move data between partners (LG-007).
```

## Scenario 6 — First run with no config (SC-005, FR-003)

```powershell
# Remove/rename data/private/partner_labels.json and any partners block labels.
# Regenerate a report and open it.
# Expected: "Partner A"/"Partner B" everywhere partner identity shows; never a
# real name; never empty strings.
```

## Scenario 7 — Bad config degrades visibly, never crashes (LG-006)

```powershell
# Try each in data/private/partner_labels.json, regenerating between:
#   a) {"partner_a": "Same", "partner_b": "Same"}        (duplicate)
#   b) {"partner_a": "<img src=x onerror=alert(1)>", "partner_b": "Ben Example"}
#   c) {"partner_a": 123, "partner_b": "Ben Example"}    (non-string)
#   d) a 100-char label                                  (length)
# Expected per contracts/partner-labels-config.md: placeholders + warnings
# (payload `warnings`, server log, CLI stderr); the HTML output contains the
# label escaped if accepted or the placeholder if rejected; no crash, no bare
# exception, no unescaped markup.
```

## Scenario 8 — LG-003/LG-004 launch hygiene

```powershell
git ls-files data/private out
# Expected: no output — nothing under data/private/ or out/ is tracked.
git check-ignore -v data/private/partner_labels.json
# Expected: a .gitignore rule matches.
# LG-004 purge evidence (launch-time, maintainer-local): recorded separately in
# the launch evidence — not reproducible here.
```

## Expected overall outcome

All scenarios green ⇒ SC-001..SC-005 and LG-002/003/005/006/007/008 satisfied on the candidate tree. LG-001 (history-reset fork) and LG-004 (local purge) are launch actions, not code; this tree is their input.
