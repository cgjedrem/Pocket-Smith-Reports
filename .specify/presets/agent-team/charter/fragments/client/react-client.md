# React Client Conventions

Applies whenever the project (or a package) contains a React UI — any
meta-framework (Next.js, Vite, …) or none.

## Stack (pinned, consistent, no mid-project substitutions)

- React and the meta-framework are pinned exactly (precedent:
  `next@15.5.19`-style exact pins), whichever stack the repo uses — Next.js,
  or the Vite 6 + MUI org stacks.
- TypeScript where present: `strict: true`. Plain-JavaScript repos keep the
  JS baseline — no forced TS migration; a repo that adopts TS adopts strict
  from day one.
- Styling follows the project's chosen system — **Tailwind CSS v4 +
  shadcn/ui**, or **MUI** — used consistently. Do not mix additional ad-hoc
  stylesheet systems alongside the chosen one.
- State/business rules live outside components (see backend fragment's
  pure-logic rule): `src/lib/` for logic, hooks for wiring, components for
  rendering.

## Component Discipline

- Components are thin: props in, markup out. Data fetching and orchestration
  happen in hooks or server functions, never inline in JSX.
- Accessibility is a gate: semantic HTML, keyboard operability, and labelled
  controls are required for every interactive element.

## Next.js-only guidance (skip on Vite/SPA stacks)

- Prefer Server Components by default; add `"use client"` only for
  interactivity and keep client islands as small as possible.

## Quality Gates (all must pass before merge)

```text
npm run lint / pnpm lint    # per the selected toolchain fragment
npm run build / pnpm build
npm run test / pnpm test
```

- Timer/animation/render-sensitive logic MUST be covered by tests (precedent:
  ticker timer-accuracy principle).

## Assets

- Attribution-first: every third-party asset is licensed and attributed in
  `NOTICE` or the project attribution file.
