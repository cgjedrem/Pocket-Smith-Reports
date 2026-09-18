# Security Policy

## Scope

Supported versions: **latest `main` only**. If you are on an older clone, pull the latest `main` before reporting.

## Reporting a vulnerability

Use GitHub's **private vulnerability reporting** for this repository (Repo → Security tab → "Report a vulnerability") — please do not open a public issue for a suspected vulnerability. Include:

- Steps to reproduce, or a proof of concept
- What you expected vs. what happened
- Which component is affected (report pipelines, budget_api, or the client)

Valid reports are fixed on `main`, credited to the reporter, and published as a GitHub security advisory.

## Security stance

Pocket-Smith-Reports is a **local, single-user tool**. The following behaviors are by design:

- **budget_api is unauthenticated.** It is meant to run on your own machine, bound to localhost (the bundled start scripts do this). Do not expose it to a network or the internet.
- **`GET /api/sync` mutates state** — it triggers PocketSmith API calls. This is intentional for local interactive use.
- **Your PocketSmith API key lives in `.env`**, which is gitignored and never committed. `.env.example` contains placeholders only.
- **Generated reports and logs** are written under gitignored data directories. Do not commit them.

Reports about the behaviors above will be answered as "working as intended" — but design improvements around them are welcome as regular issues.