---
name: fullstack-conventions
description: 'Coding conventions and patterns for any full-stack project. Covers frontend, backend, testing, and collaboration standards. Use when writing or reviewing code across a frontend + backend stack with TypeScript and React. Auto-references when starting implementation work on a full-stack feature. Do not use for infrastructure-as-code, pure database schema design, or single-layer projects (frontend-only or backend-only).'
---

# Full-Stack Conventions

## General
- Follow existing project conventions discovered during discovery phase
- Prefer readability over cleverness
- Keep functions focused and small
- Use TypeScript strictly — no `any` types without justification
- All generated code is treated as untrusted until reviewed

## Frontend
- Use functional React components with hooks
- Define TypeScript interfaces for all component props
- Handle loading, error, and empty states in every data-fetching component
- Use semantic HTML elements (nav, main, article, section, etc.)
- Follow the project's styling approach exactly — do not introduce new CSS-in-JS solutions unless the project already uses one
- Keep component files under 200 lines — extract when larger
- Use the project's existing state management pattern (Redux, Zustand, Context, etc.)

## Backend
- Validate all input at API boundaries
- Use proper HTTP status codes (200, 201, 204, 400, 401, 403, 404, 409, 422, 500)
- Return consistent response shapes: `{ data, error, meta }`
- Keep controllers thin — business logic in services
- Write database migrations for all schema changes
- Never expose internal errors to clients
- Use parameterized queries — never concatenate SQL strings

## Testing
- Test user-visible behavior, not implementation details
- Every API endpoint needs at least one happy path and one error test
- Frontend components need tests for rendering and key interactions
- Use the project's existing test utilities and patterns
- No test should depend on another test's state

## Collaboration
- Each contributor works within their defined scope — no cross-boundary modifications
- Frontend and backend agree on API contracts before implementation
- All changes must follow patterns found in the existing codebase
- When no existing pattern exists, document the new pattern in the commit message
- Change scope must list every file changed or created