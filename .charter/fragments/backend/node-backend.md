# Node Backend Conventions

Applies whenever the project (or a package) contains Node.js server-side code.

## Runtime and Language

- Node.js **22.x LTS, floating within the major**: `>=22.0.0 <23.0.0` in
  `engines`, same LTS line in CI. The major is the commitment — do not
  exact-pin the Node patch version; ride the LTS.
- TypeScript where present: `strict: true`, no new `any` without a written
  justification. Plain-JavaScript repos keep the JS baseline — no forced TS
  migration; a repo that adopts TS adopts strict from day one.
- Framework and toolchain versions are pinned exactly (no `^`/`~` for direct
  dependencies — precedent: `next@15.5.19`-style exact pins).

## Structure

- **Pure logic in `src/lib/`**: framework-free, dependency-injected, fully
  unit-testable. No I/O, env, or framework imports inside `src/lib/`.
- **Thin adapters**: route handlers / controllers / entrypoints do parsing,
  auth, and delegation only — no business logic.
- Environment access goes through one validated config module (parse env once,
  fail fast at boot); no scattered `process.env` reads.

## Quality Gates (all must pass before merge)

```text
npm run lint / pnpm lint    # per the selected toolchain fragment
npm run build / pnpm build
npm run test / pnpm test
```

- Tests live next to the logic they cover; `src/lib/` modules MUST have unit
  tests. HTTP-level tests are for contract-critical routes.

## Secrets and Config

- Secrets never enter source control, `.env` files are gitignored, and an
  `.env.example` documents every required variable.
