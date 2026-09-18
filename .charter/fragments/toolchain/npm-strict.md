# npm-Strict Package Management

**npm is the only package manager.** No pnpm, no yarn, no bun for dependency
operations in this repo.

<!-- Toolchain fragments are mutually exclusive: select exactly ONE of
     `toolchain/npm-strict` or `toolchain/pnpm-strict` when configuring the
     charter — pick the manager the repo already uses end-to-end. -->

## Rules

- The npm major is pinned via `packageManager` in `package.json` (e.g.
  `npm@11`) and activated through corepack; do not rely on a globally
  installed npm drifting.
- CI and scripted installs MUST use `npm ci` (never `npm install` in a
  pipeline). Never regenerate `package-lock.json` implicitly in CI.
- All dependency changes go through `npm install <pkg>` / `npm install -D
  <pkg>` so the lockfile moves with them; lockfile changes are reviewed in
  diffs like source changes.
- Run scripts via `npm run <script>`; one-off tools via
  `npx --yes <tool>@<exact-version>`.
- A single `package-lock.json` lives at the workspace root; per-package
  lockfiles are forbidden.

## Rationale

Exact, reproducible installs are a hard quality gate. Four of the seven
cgjedrem repos are npm end-to-end (Frivillig, Ungfritid, path-of-practice,
and partially others); forcing pnpm wording onto them produced registry
drift on every `/speckit.charter.compose`. One package manager — the one the
repo already uses — removes an entire class of "works on my machine"
dependency bugs.