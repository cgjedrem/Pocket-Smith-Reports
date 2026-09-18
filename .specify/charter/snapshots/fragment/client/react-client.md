# React Client Conventions

Applies whenever the project (or a package) contains a React/Next.js UI.

## Stack (pinned, no substitutions)

- Next.js exact-pinned (precedent: `15.5.19`) with React 19 and TypeScript
  `strict: true`.
- Styling via **Tailwind CSS v4** and **shadcn/ui** components only. No CSS
  modules, styled-components, or ad-hoc stylesheet systems.
- State/business rules live outside components (see backend fragment's
  pure-logic rule): `src/lib/` for logic, hooks for wiring, components for
  rendering.

## Component Discipline

- Components are thin: props in, markup out. Data fetching and orchestration
  happen in hooks or server functions, never inline in JSX.
- Prefer Server Components by default; add `"use client"` only for interactivity
  and keep client islands as small as possible.
- Accessibility is a gate: semantic HTML, keyboard operability, and labelled
  controls are required for every interactive element.

## Quality Gates (all must pass before merge)

```text
pnpm lint
pnpm build
pnpm test
```

- Timer/animation/render-sensitive logic MUST be covered by tests (precedent:
  ticker timer-accuracy principle).

## Assets

- Attribution-first: every third-party asset is licensed and attributed in
  `NOTICE` or the project attribution file.
