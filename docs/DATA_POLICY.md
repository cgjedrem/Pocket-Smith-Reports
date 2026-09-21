# Data Policy

Pocket-Smith Reports handles a real household's finances. This policy defines
what may enter version control and what must stay on the local machine. It is
the authority referenced by the README and enforced by `.gitignore`.

## Tracked content is synthetic-only

Every file tracked in this repository contains only deterministic synthetic
data:

- Neutral `Partner A` / `Partner B` labels (reserved placeholders — no real
  names anywhere in the app).
- Fixture transaction identifiers confined to a reserved synthetic range.
- Deterministic synthetic payees and fixture inputs
  (`data/sample_*.json`).
- No bank names, account numbers, category IDs from a real PocketSmith
  workspace, or personal identifiers of any kind.

## Local-only content (never commit)

`.gitignore` is the enforcement layer. The following are blocked from version
control and must remain local:

- `data/private/` — live sync output, unified `account_mappings.json`,
  `category_roles.json`, `detailed_section_mapping.json`, bills snapshots.
- `data/raw/` and `data/*.json` (except tracked `data/sample_*.json`
  fixtures).
- `.env` — holds `API_KEY` (the PocketSmith API key); also `*.key`,
  `api_key` patterns.
- `out/` and `/reports/` — generated HTML/PDF reports.
- `docs/old sections/` and any local historical artifacts.

## Rules of thumb

1. If it came from a PocketSmith export, a live sync, or your local report
   runs, it stays out of git.
2. New fixtures must pass the identity-neutral contract: neutral partner
   labels, synthetic ID ranges, deterministic payees. The identifier
   containment test (`src/mom/tests/test_lg002_identifier_containment.py`)
   guards this.
3. Before publishing anything from this repo, sweep working artifacts
   (`out/`, `data/private/`, `docs/specs/**/out/`) as described in
   [open-source-launch-gates.md](open-source-launch-gates.md).

## Why

The repo exists publicly as an open-source reporting pipeline. Its value is
the code and the synthetic fixture — never the financial records it
processed. Keeping that boundary mechanical (gitignore + tracked-text checks)
means no judgment call is needed per file.