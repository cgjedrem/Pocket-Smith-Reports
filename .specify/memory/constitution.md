<!--
Sync Impact Report — 2026-09-03 (initial ratification)
- Version change: none (template placeholder) → 1.0.0 (initial ratification)
- Modified principles: N/A (initial adoption; template placeholders replaced)
- Added sections: Core Principles (9), Technical Constraints, Quality & Workflow,
  Governance, and composed charter fragment sections (platform/windows-powershell,
  toolchain/pnpm-strict, client/react-client) carrying typed section markers
- Removed sections: template example commentary
- Deferred: backend/node-backend fragment NOT composed — the backend is Python
  (pyproject.toml requires-python ">=3.13"); Python-specific principles were written
  from repo evidence instead (Principles IV–VI)
- Follow-up TODOs:
  - README references docs/DATA_POLICY.md as the data-policy authority, but that
    file does not exist yet; Principle I currently cites .gitignore + README.
  - client/package.json has no `packageManager` pin (pnpm-strict requires one) and
    no lint script (react-client quality gate lists `pnpm lint`).
  - Environment tooling is split: scripts/run_api.ps1 uses uv (uv.lock) while CI
    installs via pip; owner should confirm the canonical flow.
  - httpx is declared in pyproject.toml but ps_client.py is deliberately
    urllib-based ("No httpx"); confirm whether httpx stays.
-->

# Pocket-Smith Reports Constitution

Pocket-Smith Reports is a personal-finance reporting pipeline for PocketSmith-compatible
transaction data: a Python 3.13/FastAPI sync-and-reports service (`src/budget_api/`), a
staged live-sync CLI (`src/live_sync.py`), single- and multi-month report pipelines
(`src/v4_pipeline/`, `src/mega/`, `src/mom/`), and a React 19/Vite client (`client/`).
The reports are the product — the API, sync, and client exist to build, deliver, and
browse them. This constitution exists to keep those reports trustworthy and the real
financial data that feeds them private.

## Core Principles

### I. Real Financial Data Never Enters Version Control (NON-NEGOTIABLE)

Tracked files MUST contain only deterministic synthetic data. Real PocketSmith exports,
credentials, generated reports, and private reference material MUST stay out of git:
`.gitignore` blocks `data/raw/`, `data/private/`, `data/*.json` (except
`data/sample_*.json`), `.env`, `*.key`, `api_key`, `out/`, `/reports/`, and
`docs/old sections/`. Fixtures MUST keep neutral `Partner A`/`Partner B` labels,
reserved synthetic transaction-ID ranges, and deterministic payees
(`data/sample_apr_2026.json`). Rationale: this repo handles a real household's
finances; the README's opening paragraph states the synthetic-only contract and
`.gitignore` is the enforcement layer. (`docs/DATA_POLICY.md` is referenced by the
README but does not exist yet — see follow-up TODOs.)

### II. Pipelines Fail Closed

Report builds and sync stages MUST fail on incomplete or ambiguous input rather than
degrade silently: no filename fallback, glob lookup, or partial-period build (README
"Synthetic fixture contract"); every requested month MUST be readable, valid JSON
before publishing starts; every account MUST map to `partner_a` or `partner_b` or the
build fails; duplicate account IDs MUST fail before map validation, credential reads,
or API requests; a transaction-fetch error MUST publish no new monthly snapshot
(README "Staged live 12-month sync"). Rationale: a silently partial report is worse
than an error — decisions are made from these numbers, and the codebase already
implements this posture end to end.

### III. Publishing Is Atomic and Staged

Paired HTML/PDF artifacts MUST be staged, validated (nonempty and starting with
`%PDF-`), then moved into the fixed paths `out/YYYYMM_partner_report.{html,pdf}`.
Consumers needing a coherent pair during a concurrent publish MUST read
`out/NAME.manifest.json` first and use the immutable copies under
`out/.published/NAME/`. Publishers for the same `NAME` MUST serialize the full
staging, publish, and rollback operation (waiting past 30 seconds fails); a failed
rollback MUST identify retained prior artifacts in `out/.v4-recovery-*` (README
"Quick start"). Rationale: filesystems cannot atomically replace two paths — the
staging + manifest contract is already the documented consumer protocol.

### IV. Python 3.13 Backend with Pinned Dependencies

Server-side code is Python: `requires-python = ">=3.13"` with `fastapi>=0.140,<0.141`,
`uvicorn>=0.51,<0.52`, `pydantic>=2`, and dev extras `pytest`/`pytest-asyncio`
(`pyproject.toml`); PDF tooling is exact-pinned `weasyprint==69.0` and `pypdf==6.14.2`
(`requirements.txt`). CI runs Python 3.13 on both `ubuntu-latest` and `windows-latest`
(`.github/workflows/ci.yml`). Dependency floors and pins MUST only move in deliberate,
reviewed changes — never incidentally to feature work. Rationale: the
`backend/node-backend` charter fragment was deliberately NOT composed (no Node server
code exists here); these Python pins and the 3.13 floor are the actual stability
anchors of this repository.

### V. The PocketSmith API Client Stays Hardened

All PocketSmith API access MUST follow the hardened patterns already in
`src/budget_api/services/ps_client.py` and `src/live_sync.py`: GET-only requests;
redirect rejection so the developer key is never resent (`_NoRedirectHandler`);
exact-endpoint URL validation (`https://api.pocketsmith.com/v2/...` only — https,
no credentials in URLs, no fragments, via `_validated_api_url`); Link-header
pagination at `per_page=1000` capped at 1000 pages; 30-second timeouts. The API key
lives only in the gitignored repository-root `.env` (`API_KEY`, documented in
`.env.example`) — never in code, tracked files, or client bundles. Live sync reads
only that `.env` and writes only under `data/private/` (README). Rationale: credential
exfiltration via redirects or URL manipulation is the primary API risk for a
personal-finance key; the codebase already defends against it and new integrations
MUST not regress it.

### VI. Backend Layers Stay Separated

`src/budget_api/` MUST keep its three-layer shape: `routers/` parse requests and
delegate (no business logic); `services/` own the sync, report, bills, and PDF logic
(`ps_client`, `sync_runner`, `report_builder`, `report_pdf`, `mega_builder`,
`mega_pdf`, `storage`, `env_writer`, `bills_*`); `models/` own the pydantic
request/response contracts. Framework-level error flattening (422→400 with one
human-readable detail) stays in `main.py`. CORS remains an explicit localhost
allow-list and uvicorn binds `127.0.0.1` by default (`scripts/run_api.ps1`) — the API
is local-first and MUST NOT be exposed to a network without an explicit decision.
Rationale: this adapts the charter's pure-logic/thin-adapter rule to FastAPI and is
what keeps the per-router tests and the golden-fixture check
(`src/budget_api/tests/reports/golden/`) meaningful.

### VII. React 19 + Vite + TypeScript Client, Managed Only by pnpm

The client is React 19 + Vite 6 + TypeScript 5 (`tsc -b` in `build`), styled with
Tailwind CSS v4 and Radix/shadcn-style primitives, tested with vitest + Testing
Library (`client/package.json`). pnpm is the only package manager;
`client/pnpm-lock.yaml` is the single client lockfile (see the composed pnpm-strict
fragment). Data fetching lives in `client/src/api/*.ts`; components stay thin —
props in, markup out. The react-client fragment's Next.js-specific guidance (exact
Next pin, Server Components by default, `pnpm lint` gate) does NOT apply to this Vite
SPA: where a composed fragment conflicts with documented repo reality, repo evidence
wins and the fragment or its application MUST be amended. Rationale: the fragment was
composed because the stack matches (React 19, TypeScript strict, Tailwind v4, shadcn
primitives, thin components); its Next.js lines are registry wording this repo never
opted into. Note: `client/package.json` currently has no `packageManager` pin and no
lint script — open question for the owner.

### VIII. Tests Are Colocated and Gate Merges

Python tests live next to the code they cover (`src/mega/tests`,
`src/v4_pipeline/tests`, `src/mom/tests`, `src/budget_api/tests`), including the Mega
release gate (`src/mega/tests/test_release_gate.py`) and the golden fixture
(`src/budget_api/tests/reports/golden/sample_apr_2026_report.json`). Client tests
live in `client/src/**/__tests__` and `client/tests`. CI MUST pass on BOTH Ubuntu and
Windows Python 3.13; Windows excludes the `pdf_renderer` marker (no native WeasyPrint
renderer there) — that marker split is the contract for renderer-dependent tests
(`pyproject.toml` markers, `.github/workflows/ci.yml`). The canonical Python command
is `PYTHONPATH=src python -m pytest src/mega/tests src/v4_pipeline/tests src/mom/tests
src/budget_api/tests -q`. Rationale: the dual-OS matrix and marker split already
exist; new tests follow the same slicing so that command stays canonical.

### IX. Windows PowerShell Is the Development Platform

Development runs on Windows with PowerShell, and the repo ships PowerShell tooling
(`scripts/run_api.ps1`, `scripts/install-weasyprint-msys2.ps1`) plus a Windows CI leg.
All commands, scripts, and agent instructions MUST follow the composed
windows-powershell fragment: no `&&`/`||` chaining (`;` plus `if ($?)` gating), no
bash-only snippets without a documented fallback, UTF-8 without BOM, cross-platform
`package.json` scripts and CI steps. WeasyPrint's native Windows dependencies
(GTK/Pango via MSYS2) MUST be installed via the checksum-verified script — never by
unverified downloads. Rationale: mixed shell conventions and native-dependency drift
are the historical sources of CI/local divergence; one dialect, stated once.

## Technical Constraints

- Python `>=3.13` is the floor; FastAPI stays on `0.140.x`; `weasyprint==69.0` and
  `pypdf==6.14.2` stay exact-pinned (`pyproject.toml`, `requirements.txt`).
- The API is local-first: uvicorn binds `127.0.0.1:8000` (`scripts/run_api.ps1`);
  CORS is a fixed localhost allow-list (5173/5174/8000) in `src/budget_api/main.py`.
- Live sync runs in explicit stages (`accounts` → `categories` → `transactions`) with
  fixed repository-root paths, reading only the root `.env` and writing only under
  `data/private/`; the legacy `src/pull-month-ps-paginate.py` stays disabled.
- Input naming is fixed — live `YYYY-MM_ps_raw.json`, synthetic
  `sample_<mon>_<year>.json` — with no fallbacks or partial-period builds.
- The client is a Vite SPA: React 19, Vite 6, TypeScript 5, Tailwind v4, pnpm only,
  single lockfile at `client/pnpm-lock.yaml`.
- Report output locations are fixed relative to the repository root (`out/`); the v4
  single-month build does not support `--output-dir`.

## Quality & Workflow

- The canonical pytest command above MUST pass before merge; Windows additionally
  runs `-m "not pdf_renderer"` (mirroring `.github/workflows/ci.yml`).
- Client changes MUST pass `pnpm build` (`tsc -b && vite build`) and `pnpm test`
  (`vitest run`); a lint gate is pending until a lint script exists (open question).
- Commits follow Conventional Commits — `<type>(<scope>): <subject>`, imperative —
  with types `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, matching the existing
  history (`fix(reports):`, `feat(bills):`, `chore:`).
- Feature work flows through the spec-kit workflow (specify → plan → tasks →
  implement) with artifacts under `specs/`; this constitution governs every
  plan-review gate (spec-kit + cgjedrem-spec-stack initialized in PR #69, commit
  `42c166e`).
- This is a single-maintainer repository: self-merge is allowed; the spec-kit
  discipline plus this constitution ARE the review process.

## Governance

This constitution supersedes conflicting practices in ad-hoc docs. Where a composed
charter fragment section conflicts with documented repo reality, repo evidence wins
and the discrepancy MUST be resolved by amending the local registry fragment
(`.charter/fragments/`) and recomposing via `/speckit.charter.compose` — the typed
section markers (`<!-- [F] ... SECTION -->`) are load-bearing for that flow and MUST
be preserved exactly. Amendments require: (1) a commit updating this file with a Sync
Impact Report comment, (2) a semantic version bump (MAJOR = principle
removal/redefinition; MINOR = new principle or section; PATCH = clarification), and
(3) review via pull request. All plans and PRs are reviewed against these principles;
complexity beyond them demands explicit justification.

## Charter Conventions (Composed Fragments)

The sections below are composed verbatim from the local charter registry
(`.charter/fragments/`) and are managed by `/speckit.charter.compose`. Their typed
section markers MUST be preserved. The `backend/node-backend` fragment was
deliberately not composed — this repo's backend is Python (Principle IV); its
pure-logic rule is adapted for FastAPI in Principle VI. Where a fragment conflicts
with repo evidence (e.g. the react-client fragment's Next.js specifics versus this
Vite SPA), the precedence rule in Governance applies.

<!-- [F] platform/windows-powershell SECTION -->
## Windows PowerShell Environment

All development on this machine runs on **Windows with PowerShell** (5.1 and 7+).
Commands, scripts, and agent instructions MUST honor these rules.

### Shell Syntax

- PowerShell does NOT support POSIX chaining operators (`&&`, `||`). Chain commands
  with `;` and gate on success with `if ($?) { ... }`.
- Do not assume a bash shell exists. If a tool truly needs POSIX features, document
  the Git Bash/WSL fallback explicitly instead of writing bash-only snippets inline.
- PowerShell (Windows PowerShell 5.1) has no heredoc. Feed inline scripts via
  piped here-strings or `-c` arguments.
- Every `powershell` tool invocation starts a fresh process: `Set-Location`,
  environment variables, and alias state do not persist between calls. Re-establish
  context per call.

### Paths and Files

- Use Windows-style paths with backslashes when addressing this machine directly;
  inside committed files (package.json scripts, CI config, docs) prefer
  forward-slash paths only where the tooling normalizes them (Node, git).
- Write text files as UTF-8 without BOM. `Out-File`/`>` in Windows PowerShell 5.1
  default to UTF-16LE — always pass `-Encoding utf8` or use another tool when a
  file will be consumed by cross-platform tooling.

### npm Scripts and CI

- `package.json` scripts and CI steps MUST be cross-platform. Prefer Node-based
  script files (`node scripts/x.mjs`) over inline shell when logic is non-trivial.
- Never require a developer to hand-edit their shell profile to work on the repo.

### Rationale

Mixed shell conventions caused repeated CI/local divergence (pinned Next.js +
pnpm stack on this machine is Windows-hosted). One shell dialect, stated once,
applied everywhere.

<!-- [F] toolchain/pnpm-strict SECTION -->
## pnpm-Strict Package Management

**pnpm is the only package manager.** No npm, no yarn, no bun for dependency
operations in this repo.

### Rules

- The pnpm version is pinned exactly via `packageManager` in `package.json`
  (e.g. `pnpm@10.30.3`). Corepack MUST be the activation mechanism
  (`corepack enable`); do not rely on a globally installed pnpm drifting.
- CI and scripted installs MUST use `pnpm install --frozen-lockfile`. Never
  regenerate `pnpm-lock.yaml` implicitly in a pipeline.
- All dependency changes go through `pnpm add` / `pnpm add -D`. Lockfile changes
  are reviewed in diffs like source changes.
- Run scripts and one-off tools via `pnpm <script>` / `pnpm dlx` (not `npx`).
- A single lockfile lives at the workspace root; per-package lockfiles are
  forbidden.

### Rationale

Exact, reproducible installs are a hard quality gate (evidence: the ticker
stack pins pnpm 10.30.3 and fails CI on lockfile drift). One package manager
removes an entire class of "works on my machine" dependency bugs.

<!-- [F] client/react-client SECTION -->
## React Client Conventions

Applies whenever the project (or a package) contains a React/Next.js UI.

### Stack (pinned, no substitutions)

- Next.js exact-pinned (precedent: `15.5.19`) with React 19 and TypeScript
  `strict: true`.
- Styling via **Tailwind CSS v4** and **shadcn/ui** components only. No CSS
  modules, styled-components, or ad-hoc stylesheet systems.
- State/business rules live outside components (see backend fragment's
  pure-logic rule): `src/lib/` for logic, hooks for wiring, components for
  rendering.

### Component Discipline

- Components are thin: props in, markup out. Data fetching and orchestration
  happen in hooks or server functions, never inline in JSX.
- Prefer Server Components by default; add `"use client"` only for interactivity
  and keep client islands as small as possible.
- Accessibility is a gate: semantic HTML, keyboard operability, and labelled
  controls are required for every interactive element.

### Quality Gates (all must pass before merge)

```text
pnpm lint
pnpm build
pnpm test
```

- Timer/animation/render-sensitive logic MUST be covered by tests (precedent:
  ticker timer-accuracy principle).

### Assets

- Attribution-first: every third-party asset is licensed and attributed in
  `NOTICE` or the project attribution file.

**Version**: 1.0.0 | **Ratified**: 2026-09-03 | **Last Amended**: 2026-09-03