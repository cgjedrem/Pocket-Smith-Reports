# Pocket-Smith Reports

Self-hosted personal-finance reporting for [PocketSmith](https://www.pocketsmith.com/).
A FastAPI backend syncs your PocketSmith data into local JSON snapshots, and a
React dashboard renders single-month and 12-month PDF reports plus a bills
dashboard. Everything runs — and stays — on your machine.

**In-app documentation:** run the app and open **Docs** in the top navigation
(or visit `/docs`) for the full setup walkthrough, staged-sync reference,
report CLI, and release notes. This README covers installation only.

## Features

- Staged sync from the PocketSmith API: account catalog → category catalog →
  transaction snapshots; stages fail closed and never write partial data
- Single-month reports published as paired HTML + PDF (WeasyPrint)
- 12-month "Mega" reports with per-section navigation and export
- Bills dashboard: budget coverage, economy bar, savings view
- Settings for partner labels, account ownership, and category mappings
- Local-first: API key and synced data live in git-ignored local files

## Requirements

- Python 3.13+ with [uv](https://docs.astral.sh/uv/)
- Node.js 20+ with [pnpm](https://pnpm.io/) 10
- WeasyPrint native libraries (Pango, Cairo, GDK-PixBuf) + system fonts for
  PDF rendering — the Python wheel alone does not include the Windows DLLs

## Quick start

Install backend and frontend dependencies:

```bash
git clone https://github.com/cgjedrem/Pocket-Smith-Reports.git
cd Pocket-Smith-Reports
uv sync                # backend deps (pyproject.toml + uv.lock)
cd client && pnpm install   # client deps (pnpm-lock.yaml)
```

Windows only — install the WeasyPrint GTK runtime. Get the SHA-256 only from
the official MSYS2 release or a signed checksum source; the script verifies it
before running the installer (`-WhatIf` previews):

```powershell
.\scripts\install-weasyprint-msys2.ps1 -ExpectedSha256 '<official-msys2-sha256>'
```

Start the backend (client expects the API on port 8001):

```powershell
.\scripts\run_api.ps1 -Port 8001
```

In a second terminal, start the frontend and open http://localhost:5174:

```bash
cd client
pnpm dev
```

First run: open **Settings**, paste your PocketSmith API key (stored as
`API_KEY` in the git-ignored `.env`), run your first **Sync**, then generate a
report from **Monthly Reports**. The in-app **Docs** page walks through each
step.

## Data safety

Tracked files contain only deterministic synthetic data — neutral
`Partner A`/`Partner B` labels, reserved synthetic ID ranges, deterministic
payees. `.gitignore` blocks all live financial data: `data/private/`,
`data/raw/`, local JSON exports, `.env`, keys, and generated `out/` reports.
The full policy is [docs/DATA_POLICY.md](docs/DATA_POLICY.md).

## Testing

```bash
uv run pytest src/mega/tests src/v4_pipeline/tests src/mom/tests -q
PYTHONPATH=src python -m pytest src/mega/tests/test_release_gate.py -q   # Mega release gate
cd client && pnpm build && pnpm test
```

Tests marked `pdf_renderer` require working native WeasyPrint libraries.

## Repository layout

```
src/
├── budget_api/         # FastAPI app — sync, reports, bills, settings
├── v4_pipeline/        # Single-month report pipeline
├── mega/               # Multi-month (Mega) report pipeline
├── mom/                # MoM report renderer + release gate
└── live_sync.py        # Staged live-sync CLI (accounts/categories/transactions)

client/                 # React + Vite + Tailwind dashboard
data/
├── sample_apr_2026.json                           # Deterministic synthetic fixture
└── sample_apr_2026_detailed_section_mapping.json  # Fixture section routing
scripts/               # Dev helper scripts (API server, WeasyPrint installer)
docs/                  # Data policy, launch gates, design notes
```

## License

[MIT](LICENSE)