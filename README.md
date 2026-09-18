# Pocket-Smith Reports

Financial-report pipeline for PocketSmith-compatible transaction data. It
builds single-month and multi-month PDF reports from local JSON inputs.

Tracked files contain only deterministic synthetic data. Local exports,
credentials, generated reports, and other financial records must remain
outside version control as defined in `docs/DATA_POLICY.md`.

---

## Quick start

```bash
python src/v4_pipeline/build.py --month 2026-04 --data-dir data --input-kind synthetic --detailed-section-map data/sample_apr_2026_detailed_section_mapping.json
```

The single-month build always publishes paired HTML and PDF artifacts to
`out/YYYYMM_partner_report.html` and `out/YYYYMM_partner_report.pdf`.
Use `--name NAME` to replace the default basename. `NAME` must be an
extensionless basename containing only letters, digits, `_`, or `-`;
`--output-dir` is not supported. The location is relative to the repository,
not the command working directory.

Publishing stages both files, validates that the PDF is nonempty and starts
with `%PDF-`, then replaces the fixed paths. Filesystems cannot atomically
replace two paths together. Consumers that need a coherent pair during a
concurrent publish must read `out/NAME.manifest.json` first, then use its
immutable HTML and PDF paths under `out/.published/NAME/`. After a command
returns successfully, the fixed HTML/PDF pair and manifest identify the new
report. Publishers for the same `NAME` serialize the full staging, publish,
and rollback operation; waiting longer than 30 seconds fails with an error.
If rollback itself fails, the error identifies the retained prior artifacts in
`out/.v4-recovery-*`.

The tracked fixture has neutral accounts (`Fixture A Checking`, `Fixture B
Checking`), synthetic payees, deterministic identifiers, and paired
reimbursement rows. It is not a production export.

## Local account ownership

Production input uses the ignored unified `data/private/account_mappings.json`.
The v4 and Mega live builds translate its account owners, partner labels, and
excluded account IDs internally.
Every report account must map to `partner_a` or `partner_b`, or the build fails
closed. `--account-owner-map PATH`, `--partner-label-map PATH`, and
`POCKETSMITH_ACCOUNT_OWNER_MAP` remain legacy report-only overrides; they use
the old separate-map formats and are never read by staged live sync.
Unified `excluded: true` is authoritative for both transaction sync and live
report rendering, including old local snapshots. `--exclude-account-id` adds
more IDs for one report run; it cannot include a unified-excluded account.

The ignored `data/private/detailed_section_mapping.json` is also the production
default for section routing. Its `savings_partner_a` and `savings_partner_b`
account roles define the net-savings movement accounts unless
`--savings-account-id` is supplied. Partner display names live in the unified
mapping; individual label flags remain available for one report run.

```bash
python src/v4_pipeline/build.py --month 2025-08 --data-dir data/private --input-kind live --category-role-map data/private/category_roles.json --account-owner-map C:/local/account_owners.json
```

## Breaking changes: report contract v2 and canonical labels

Stored monthly and mega reports are now stamped with `contract_version: 2`.
`GET /api/reports/monthly/{month}` and `GET /api/mega-reports/{start}/{end}`
reject pre-change payloads with **409 Conflict** (the detail names the month or
range and says to regenerate). Regenerate via the UI's Regenerate affordance or
`POST /api/reports/monthly/{month}/generate` /
`POST /api/mega-reports/{start}/{end}/generate`.
If a stored report cannot be regenerated because its source PocketSmith data
for those months is gone, re-run the staged sync from PocketSmith to re-fetch
it (LG-008 fallback), then regenerate.

Related behavioural changes in the same release:

- **Canonical partner-label validation everywhere.** Partner labels from
  `data/private/account_mappings.json` are validated on every load and at the
  settings write path: duplicates, empty labels, overlong labels, and the
  reserved placeholders `Partner A`/`Partner B` are rejected at write time
  with HTTP 400. At read time an invalid label degrades **the affected
  partner** to the placeholder with a visible warning in the payload's
  `warnings` field (equal values on both partners reset both); overlong
  labels are truncated to 64 chars with a warning. A config file that cannot
  be parsed at all degrades to placeholders instead of failing the build.
  There are no hardcoded names anywhere in the app.
- **Bills snapshot schema 5.** `BillsEvent` and `PartnerBills` now carry
  additive `partner_id` and `partner_slot`; `GET /api/bills/dashboard/events`
  accepts `?partner_id=` (supersedes the legacy label `?partner=`). Schema-4
  snapshots still load — both fields default to empty — but events lack stable
  partner routing until rebuilt.
- **Local config migration (pre-rename installs).** Values in
  `data/private/detailed_section_mapping.json` that referenced the old
  per-name personal sections must be renamed to `personal_partner_a` /
  `personal_partner_b`; until then every report build fails closed with
  "detailed section mapping invalid ... invalid category section".

## Staged live 12-month sync and Mega render

Live sync uses explicit stages and fixed repository-root paths. It reads only
the ignored repository-root `.env`, and writes only under `data/private/`.
Run all commands from the repository root. The legacy
`src/pull-month-ps-paginate.py` is disabled and cannot write snapshots. Use
the staged `src/live_sync.py` CLI.

First, build the private active-account catalog. This probes every account for
every requested month, then writes only metadata for accounts with at least
one transaction somewhere in the full period. It writes no monthly snapshots.

```bash
PYTHONPATH=src python src/live_sync.py accounts --start 2025-08 --end 2026-07
```

Create `data/private/account_mappings.json` after inspecting the account
catalog. It must use this exact schema and cover exactly the catalog IDs;
every account `name` must match the catalog exactly. Duplicate account IDs
fail before map validation, credential reads, or API requests:

```json
{"schema_version":1,"partners":{"partner_a":{"label":"..."},"partner_b":{"label":"..."}},"accounts":{"ID":{"name":"exact account catalog name","owner":"partner_a","excluded":false}}}
```

Both partner labels must be nonempty and distinct. Each owner is `partner_a`
or `partner_b`; each exclusion is literal `true` or `false`. An excluded
account is never fetched by the transaction stage or rendered from live snapshots.

Next, fetch the category catalog. Human category-role and detailed-section
mapping happens after this stage, using the ignored `category_catalog.json`.

```bash
PYTHONPATH=src python src/live_sync.py categories --start 2025-08 --end 2026-07
```

Only after both catalogs and a valid unified account map exist, publish transaction
snapshots. The command fetches every non-excluded mapped account for every
month before it writes any output; a fetch error publishes no new monthly
snapshot. Each `YYYY-MM_ps_raw.json` uses the same `categories` array from
`category_catalog.json`; each transaction carries its API `category` object,
or `null` when uncategorized.

```bash
PYTHONPATH=src python src/live_sync.py transactions --start 2025-08 --end 2026-07
```

After one successful 12-month transaction-stage sync, render Mega from only
those local live files:

```bash
PYTHONPATH=src python -m mega.build_mega --start 2025-08 --end 2026-07 --data-dir data/private --input-kind live --category-role-map data/private/category_roles.json --account-owner-map C:/local/account_owners.json --detailed-section-map data/private/detailed_section_mapping.json
```

---

## Synthetic fixture contract

- Every CLI report build requires `--input-kind live` or `--input-kind synthetic`.
- Live source files use exactly `YYYY-MM_ps_raw.json` in `--data-dir`.
- Synthetic source files use exactly `sample_<mon>_<year>.json` in `--data-dir`.
- No filename fallback, glob lookup, or partial-period build is supported. Every requested
	month must be readable valid JSON before publishing starts.
- Fixture transaction identifiers stay in the reserved synthetic range.
- Fixture labels use neutral `Partner A` and `Partner B` terminology.
- Fixture input uses normalized category accounting and literal boolean transfer flags when supplied.
- The loader owns account-to-partner attribution for fixture labels.

---

## Supported MoM Synthetic Release Gate

Install Python dependencies with `uv sync` (reads `pyproject.toml` + `uv.lock`;
get uv from https://docs.astral.sh/uv/).
WeasyPrint also needs native libraries: on Windows install a 64-bit GTK 3
runtime (Pango, Cairo, and GDK-PixBuf); on Linux install those packages and
system fonts. The Python wheel alone does not provide the Windows GTK DLLs.
On Windows, install the MSYS2 Pango renderer with an official MSYS2 release
checksum supplied by you:

```powershell
.\scripts\install-weasyprint-msys2.ps1 -ExpectedSha256 '<official-msys2-sha256>'
```

Use `-WhatIf` to preview. Get the SHA-256 only from the official MSYS2 release
or signed checksum source; the script verifies it before installer execution.
GPG verification remains a manual human step.

Generate the tracked synthetic April report with:

```bash
python src/mom/render_mom.py --start 2026-04 --end 2026-04 --data-dir data --input-kind synthetic --output-dir out
```

Every inclusive month must have a readable, valid
`sample_<mon>_<year>.json` file in `--data-dir`. HTML and PDF publish only
after WeasyPrint successfully creates a non-empty staged PDF.

---

## Repository layout

```
src/
├── v4_pipeline/        # Single-month report pipeline
│   ├── build.py        # CLI orchestrator
│   ├── data_loader.py  # JSON to normalized transactions
│   ├── tally.py        # Transaction aggregation
│   ├── wallet.py       # Cash and reimbursement calculation
├── mega/               # Multi-month report pipeline
├── legacy/v7_mega/     # Retained legacy multi-month pipeline
└── pull-month-ps-paginate.py

data/
├── sample_apr_2026.json         # Deterministic synthetic test fixture
├── sample_apr_2026_detailed_section_mapping.json  # Fixture detailed-section routing
└── convert_to_nested.py         # Input-shape converter

docs/
├── DATA_POLICY.md
├── production-hardening-loops.md
└── decision-*.md
```

---

## QA

Run the current report test slices:

```bash
uv run pytest src/mega/tests src/v4_pipeline/tests src/mom/tests -q
```

Run the Mega release gate. It uses only the committed synthetic fixture, builds
the full report and every `--only` section, and validates HTML/PDF artifacts
with `pypdf`.

```bash
PYTHONPATH=src python -m pytest src/mega/tests/test_release_gate.py -q
```

Build a multi-month report with the supported package CLI. `--only` filters
the assembled output, but validates every month in the requested inclusive
range before publishing.

```bash
PYTHONPATH=src python -m mega.build_mega --start 2026-04 --end 2026-04 --data-dir data --input-kind synthetic --detailed-section-map data/sample_apr_2026_detailed_section_mapping.json
```

Current and planned report hardening work is tracked in
[docs/production-hardening-loops.md](docs/production-hardening-loops.md).
