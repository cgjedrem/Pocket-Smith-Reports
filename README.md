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
balances with **average monthly spending (net, as in Reports)**, per account
owner and for the household. Runway loads independently, even when the current
Bills snapshot is missing. Changing the Bills past/future window does not change
Runway's previous-three-completed-month window. Bills shows the included-month
count and names, plus the note: “Based on recorded PocketSmith transactions for
the last three completed months.”

1. Expand **Liquid account settings**. No accounts are selected automatically.
2. Choose eligible owned checking/savings accounts and click **Save selection**.
   This saves locally and refreshes Runway only; no sync is started.
3. Read runway measures and reserve/account qualifications in Bills. Use
   **Data coverage** in the top navigation or the Bills link for month-by-month
   coverage, transaction source dates, and source diagnostics. **Refresh runway**
   rereads local sources; it does not fetch fresh bank data.

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
with no older backfill. It is the same household net spending as the Reports page
(home, common, personal and trips): refunds and reimbursements reduce it, so a
month or the average can be zero or negative (runway then unavailable). Transfers,
card repayments, savings and excluded categories do not count. Reserves use the
signed recorded balances of selected owned checking/savings accounts, not credit
limits or projected savings.

Owner burn follows the common economy split when it is enabled: each partner
carries their split share (for example 60 / 40) of split-category spending plus
their own net spending elsewhere, and owners sum to the household. Without the
split, owner burn is what that partner's accounts paid (net).

Missing balances, partial/invalid/missing history, nonpositive inputs, and currency
conflicts have explicit unavailable reasons. Unknown coverage, currency, and
source/balance dates remain qualified and are not treated as verified completeness;
coverage and transaction-source provenance are shown on **Data coverage**, while
balance dates and stale-balance warnings remain with the selected accounts in Bills.
Recalculation does not make old data fresh. The ratio is descriptive, not a forecast
or financial advice.
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

## Lifestyle-creep detector

`GET /api/bills/lifestyle-creep?month=2026-10&threshold_percent=20&reference_start=2026-07&reference_end=2026-09&grouping=report`
compares report-grouped category spending in one completed target month
with average monthly spending in a selected reference period of 2–24 consecutive
completed months. The reference period must end before the target, and the target
must be earlier than the API's current month for any financial comparison.
The current API month is accepted only as an unavailable selection: it returns
`insufficient_history` / `partial_month` / `open_month`, three insufficient groups without money,
and reads no snapshots. Future API months are rejected. The separate threshold defaults to 20%
and accepts values from 1–100%. A category is flagged only when its target-month
spending is strictly above the reference average by more than that threshold.
This is descriptive, not financial advice.

The page shows three tables in report order: **Shared economy** (Home + Common
only), then the two configured personal sections. Included checking and card
accounts contribute paid minus received across both payers. Personal placement
follows the report category section, not the owner of the paying account.
Refunds reduce spending; net negative observations, targets and reference means
remain visible. Trips, savings, income, excluded and credit-card payment sections
are omitted. The client does not reclassify categories, merge their IDs or invent
an overall total. A zero/negative reference mean or fewer than two positive
reference samples suppresses the warning without erasing the amounts.

The endpoint only reads saved Bills snapshots. Report mode requires explicit
schema-7 report-economy evidence for every selected completed month. Older CC-only
history cannot establish these groups. Missing, partial, unavailable or
differently configured evidence blocks all three groups, preserves their headings,
and shows resync guidance, not zero-filled spending. Check report mappings, then
explicitly re-sync all selected reference months and the target with one consistent
configuration through the normal Sync flow. Pending/unknown transaction status
conservatively prevents complete report evidence. GET/Retry never syncs, repairs
or fabricates history. New decimal fields are strings; existing Bills totals and
the default outgoing-CC API response (omit `grouping`) are unchanged.

The detector has its own **Lifestyle Creep** tab in the top navigation, directly
after **Bills** (route `/lifestyle-creep`). It is independent of the Bills page:
Bills no longer shows the card, and opening the tab sends no Bills dashboard or
Runway requests.

- Choose **Target month**, **Reference start**, and **Reference end**, then
  **Apply comparison** to apply all three drafts together. The default target is
  the latest completed local calendar month; the default reference period is the
  three months immediately before it. Targets must be completed and earlier than
  the current month. Reference periods must contain 2–24 consecutive completed
  months before target. The earliest target is `0001-03`; the earliest reference
  month is `0001-01`. Invalid or missing dates are rejected without fetching.
- The client always sends `month` as the target and both explicit reference
  bounds and `grouping=report`. Required evidence is exactly the reference months plus the target.
  For references July–September and target December, only July, August,
  September, and December are required; intervening months are not read.
  Missing snapshots never shift, shorten, or zero-fill the selected history.
  The card labels target, reference boundaries, and exact evidence coverage.
- Edit **Threshold (1–100%)** and **Apply threshold**. Decimals are accepted;
  invalid drafts never fetch or replace the applied value. The default is 20%,
  retained across target/reference changes for this visit only. Canonically
  equivalent decimals do not refetch; fresh visits reset the selection and threshold. Neither
  is stored in the URL or localStorage.
- Inspect each group's target spend, reference-period average, change, growth,
  and server-provided threshold outcome. Expand category details for all 3–25
  required observations and one target-versus-average comparison. Actual adjacent
  month-over-month growth is shown separately only when available. Uncategorized spending
  assigned by the report classifier is shown separately for each group, including
  signed refunds, and never treated as a category alert.
- Expanding a category's **Target comparison** disclosure mounts a usage graph
  for that category only (collapsed disclosures render no chart). It plots the
  reference months and target chronologically with a solid usage line, a dashed
  **Trailing average (up to 3 prior months)** line, triangles for months strictly
  above their own trailing average and a square outline for the target. The
  average uses up to three immediately preceding consecutive evidence months,
  excludes the month itself and starts only after two; earlier months have no
  average or marker. Unselected months between reference end and target break
  both lines (never zero-filled) and the month after the break has no average.
  Markers are descriptive only, not the applied threshold or server verdict.
  A legend, summary and graph data table give a text alternative. With **Hide
  amounts** on, the chart is replaced by a masked placeholder (no plotted
  coordinates or tooltip) and table money shows `****`; toggling never fetches
  or collapses the disclosure. Details: [quickstart section 22](docs/specs/005-lifestyle-creep/quickstart.md#22-category-usage-graph---2026-11-02).
  Final verification (2026-11-02): independent review passed; frontend-only
  deployment passed 333 synthetic graph/browser assertions and six separate
  live metadata-only assertions. Live document/report GETs returned 200 with
  three ready report groups; no live graph was opened. API and named data volume
  were unchanged and both services remain healthy. Feature tasks: **63/63**.
- Use a category row's **Hide** button to hide that row and its detail disclosure
  for that group. Each group has a hidden count, **Show hidden categories**
  toggle, and **Restore all**; shown hidden rows are marked **Hidden** and offer
  **Restore**. If every category is hidden, the view says so and keeps recovery
  controls available. This is presentation only: the assessment still covers all
  categories. Visibility uses stable `group_id`/`category_id` pairs, not labels
  or nullable person IDs, survives target,
  reference and threshold changes during this visit, and resets on a fresh visit.
  Hide/show/restore never fetches or writes settings, snapshots or API data, and
  **Hide amounts** still masks every monetary value when hidden rows are shown.
- Missing, legacy or partial history shows affected months and a link to **Sync**.
  Check report mappings and explicitly re-sync every selected completed reference
  and target month with one consistent configuration, then use **Retry history**. Retry only
  rereads the same applied target, reference bounds, and threshold; it does not start sync.
- The global **Hide amounts** control masks all monetary details, including
  collapsed disclosures. Percentages and dates remain visible, with no refetch.

If API callers omit both reference bounds, the API defaults to the three months
immediately preceding the explicitly selected target. This page always sends
both bounds. Corrected client verification, the passing independent review, and
the completed container/browser smoke are recorded in
[quickstart section 19](docs/specs/005-lifestyle-creep/quickstart.md#19-corrected-target-month-and-reference-period---2026-11-02).

Historical visit-local category visibility implementation and test results are recorded in
[quickstart section 20](docs/specs/005-lifestyle-creep/quickstart.md#20-visit-local-category-visibility---2026-11-02);
the three-group frontend amendment is documented in
[quickstart section 21](docs/specs/005-lifestyle-creep/quickstart.md#21-shared-economy-backend-and-persisted-report-group-evidence).
T057–T060 are complete: independent review passed and both rebuilt services are
healthy on port 8080 with the existing private volume retained. Final browser
verification passed 68 assertions (57 synthetic, 11 unmocked structural-only).
Old history honestly shows three insufficient groups and resync guidance; it is
not automatically upgraded to schema 7. Check report mappings and explicitly
resync the selected completed months to acquire report-group evidence. Verification
did not run sync or modify saved data. Earlier two-person CC browser evidence
remains historical.

Known limitations and clock-boundary handling (details in
[quickstart section 16](docs/specs/005-lifestyle-creep/quickstart.md#16-post-rebase-real-data-validation)):

- **Time zone:** the API checks the target against its process clock, while the
  card defaults from the browser's local calendar. Near a month boundary, the
  browser's latest completed target can still be the API's current month.
  The API then returns `insufficient_history`, not a selection error, without
  reading saved history or exposing money, even if a snapshot claims `complete`.
  The card shows the open-month reason and no reliable conclusion. Wait until
  the API month closes or choose an earlier target; re-sync after closure if
  saved history was acquired while open. The client still excludes its own
  current month. The clocks themselves are not synchronized by this handling.
- **Sync-window shape:** the last month of a sync window has no everyday-budget
  zone, and past savings balances use only deltas inside the window, so a window
  that stops before the current month can leave a partial picture [Inference].
  Re-sync through the usual sync end month, as above.
- **Hand-edited roles (original CC API mode):** an `exclude` entry in `category_roles.json` whose key is
  not a canonical category ID makes CC history report `invalid_source` with no
  detail about the key, because the evidence builder fails closed.
- **Re-sync depth:** a default target month M needs the three reference months
  M-3 through M-1 plus M re-synced with this build. Custom reference bounds
  require those selected months plus target M. Older stored months stay
  `legacy_history` until they are re-synced.
- **Nav width:** the extra tab widens the top navigation. On Mega Reports the
  fixed contents toggle overlaps the nav's **Hide amounts** button in viewports
  narrower than about 864px (about 150px wider than before). The nav already
  overflowed at 390px. Left unchanged; see
  [quickstart section 17](docs/specs/005-lifestyle-creep/quickstart.md#known-limitation-nav-overlap-on-mega-reports).

See the [complete API contract and example](docs/specs/005-lifestyle-creep/contracts/lifestyle-creep-api.md)
and [safe test commands, results and browser evidence](docs/specs/005-lifestyle-creep/quickstart.md).

## License

[MIT](LICENSE)
