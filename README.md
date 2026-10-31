# Pocket-Smith Reports

Self-hosted personal-finance reporting for [PocketSmith](https://www.pocketsmith.com/).
A FastAPI backend syncs your PocketSmith data into local JSON snapshots, and a
React dashboard renders single-month and 12-month PDF reports plus a bills
dashboard. Everything runs — and stays — on your machine.

**Using the app:** once it's running, open **Docs** in the top navigation
(`/docs`) for a guide to connecting, syncing, and building reports.
This README covers installation only.

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

## Run with Docker Compose

Docker Compose runs the API and static frontend in separate containers. The
frontend proxies `/api/` requests, including PDF responses, to the API. Only
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
