# Playwright E2E for User-Facing Features

Applies whenever the project (or a package) ships a **web UI**. Repos without
a web UI simply do not compose this fragment.

## Rules

- Every user-facing feature MUST have Playwright end-to-end coverage before
  it is considered done. "User-facing" means any flow a human operates in the
  UI: screens, forms, navigation, and permission-gated actions.
- The E2E suite is a merge gate for user-facing flows: Playwright MUST pass
  in CI before merge. A red user-facing E2E run blocks the merge; skips are
  not the default state.
- E2E specs live in a dedicated `e2e/` directory and drive the app the way
  users reach it (built app or dev server) — not a mocked-out UI shell.
- Assert on user-visible behaviour (roles, text, visible states), not
  implementation details (class names, DOM structure), so refactors do not
  orphan the suite's intent.
- Keep the suite deterministic: explicit waits on user-visible conditions,
  no real-time or date-dependent flakiness. A flaky spec is quarantined with
  a tracked issue — never silently skipped.

## Rationale

Unit and integration tests do not exercise flows the way users do, and
agent-run smoke checks are not a durable gate. Playwright is the cheapest
reliable enforcement of "the feature works as experienced" (owner resolution
2026-09-03 — codified here so the rule survives future
`/speckit.charter.compose` cycles instead of living in a skipped pilot).