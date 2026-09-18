# pnpm-Strict Package Management

**pnpm is the only package manager.** No npm, no yarn, no bun for dependency
operations in this repo.

## Rules

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

## Rationale

Exact, reproducible installs are a hard quality gate (evidence: the ticker
stack pins pnpm 10.30.3 and fails CI on lockfile drift). One package manager
removes an entire class of "works on my machine" dependency bugs.
