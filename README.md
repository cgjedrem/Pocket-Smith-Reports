# Pocket-Smith Reports

Self-hosted personal-finance reporting for [PocketSmith](https://www.pocketsmith.com/).
A FastAPI backend syncs your PocketSmith data into local JSON snapshots, and a
React dashboard renders single-month and 12-month PDF reports plus a bills
dashboard. Everything runs — and stays — on your machine.

**Using the app:** once it's running, open **Docs** in the top navigation
(`/docs`) for a guide to connecting, syncing, and building reports.
This README covers installation and local backend configuration.

## Requirements

- Python 3.13+ with [uv](https://docs.astral.sh/uv/)
- Node.js 20+ with [pnpm](https://pnpm.io/) 10
- WeasyPrint native libraries (Pango, Cairo, GDK-PixBuf) + system fonts for
  PDF rendering — the Python wheel alone does not include the Windows DLLs

## Install

```bash
git clone https://github.com/cgjedrem/Pocket-Smith-Reports.git
cd Pocket-Smith-Reports
uv sync                     # backend deps (pyproject.toml + uv.lock)
cd client && pnpm install   # client deps (pnpm-lock.yaml)
```

Windows only — install the WeasyPrint GTK runtime. Get the SHA-256 only from
the official MSYS2 release or a signed checksum source; the script verifies it
before running the installer (`-WhatIf` previews):

```powershell
.\scripts\install-weasyprint-msys2.ps1 -ExpectedSha256 '<official-msys2-sha256>'
```

On Linux, install Pango, Cairo, and GDK-PixBuf plus system fonts with your
package manager.

## Run

Start the backend (PowerShell, from the repo root; the client expects the API
on port 8001):

```powershell
.\scripts\run_api.ps1 -Port 8001
```

In a second terminal, start the frontend and open http://localhost:5174:

```bash
cd client
pnpm dev
```

Then open **Settings**, paste your PocketSmith API key (stored in the
git-ignored `.env`), run your first **Sync**, and build a report from
**Monthly Reports** — the in-app **Docs** page walks through each step.

## Runway & Burn Rate

Open **Bills → Runway & Burn Rate** to compare explicitly selected liquid
balances with **average monthly recorded spending (gross burn)**, per account
owner and for the household. Runway loads independently, even when the current
Bills snapshot is missing. Changing the Bills past/future window does not change
Runway's previous-three-completed-month window.

1. Expand **Liquid account settings**. No accounts are selected automatically.
2. Choose eligible owned checking/savings accounts and click **Save selection**.
   This saves locally and refreshes Runway only; no sync is started.
3. Read the selected accounts, exact included/excluded months, source dates, and
   qualifications alongside the ratios. **Refresh runway** rereads local sources;
   it does not fetch fresh bank data.

**Clear selection** prepares an empty draft; click **Save selection** to apply it.
**Reset changes** restores the last loaded selection. **Reload saved selection**
reads it again and discards the draft. Failed settings loads disable Save, and
failed saves keep the draft for correction or retry. Retained figures are labelled
as using the last loaded saved selection, not unsaved choices.

The global **Hide amounts** control masks reserves, averages, monthly spending,
and selected account balances, including zero and negative values. Ratios, dates,
labels, and counts remain visible; toggling does not refetch or reset the draft.

Local API:

- `GET /api/settings/runway` returns the saved selection and account eligibility
  without balance amounts. No accounts are selected automatically.
- `PUT /api/settings/runway` accepts only `{"liquid_account_ids":["1100001"]}`
  (synthetic ID shown; use eligible IDs from GET). IDs must be unique strings.
  An empty array explicitly clears the selection.
- `GET /api/bills/runway` returns owner and household observations, dates,
  qualifications, and nullable ratios. These endpoints accept no query parameters.

Only an explicit successful PUT writes `runway_config.json` under the existing
private-data directory, using atomic replacement. No schema migration, snapshot
regeneration, credential access, or synchronization is required by these routes.
All three operations return `Cache-Control: no-store`.

Spending uses at least two of the previous three completed local calendar months,
with no older backfill. It counts negative posted checking/card purchases without
netting refunds or income; transfers, repayments, savings/investment movements,
and exclusions do not count. Reserves use the signed recorded balances of selected
owned checking/savings accounts, not credit limits or projected savings.

Missing balances, invalid history, nonpositive inputs, and currency conflicts have
explicit unavailable reasons. Unknown coverage, currency, and source/balance dates
remain qualified; recalculation does not make old data fresh. The ratio is
account-owner-based, not fair-share allocation, a forecast, or financial advice.
See the [API contract](docs/specs/003-runway-burn-rate/contracts/runway-api.md) and
[synthetic validation guide](docs/specs/003-runway-burn-rate/quickstart.md).

## Run with Docker Compose

Docker Compose runs the API and static frontend in separate containers. The
frontend proxies `/api/` requests, including PDF responses, to the API. The
Docker frontend build sets `VITE_API_URL` to an empty string so browser
requests use this same-origin proxy instead of the development API port. Only
the frontend is published, bound to loopback by default; no login is provided,
so keep that binding local.

```bash
docker compose up --build -d
```

Open http://127.0.0.1:8080. To change the local port, set `APP_PORT=8081` in
your shell or the ignored root `.env`. The Compose services do not pass
`API_KEY` from that file. Add the PocketSmith API key in **Settings**; the API
writes it into the persistent private-data volume. Docker's volume is separate
from the working tree's `data/private`; existing local files are not imported.
Sync data and configuration remain across container rebuilds.

```bash
docker compose ps
docker compose logs -f
docker compose down
```

`docker compose down -v` also deletes the private-data volume and all locally
persisted financial data and API-key configuration. Do not use it unless
deletion is intended.

## Data safety

Tracked files contain only deterministic synthetic data — neutral
`Partner A`/`Partner B` labels, reserved synthetic ID ranges, deterministic
payees. `.gitignore` blocks all live financial data: `data/private/`,
`data/raw/`, local JSON exports, `.env`, keys, and generated `out/` reports.
The full policy is [docs/DATA_POLICY.md](docs/DATA_POLICY.md).

## Testing

```bash
uv run pytest src/mega/tests src/v4_pipeline/tests src/mom/tests -q
cd client && pnpm build && pnpm test
```

Tests marked `pdf_renderer` require working native WeasyPrint libraries.

## License

[MIT](LICENSE)
