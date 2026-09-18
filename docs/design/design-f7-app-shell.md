# F7 — React App Shell

Status: NOT STARTED (design-first L1-L5)
Date: 2026-07-27
Repo: Pocket-Smith-Reports

## Summary
Vite + React + routing + layout, sync button, settings page.

## Decisions (from grill-me)
- React frontend (manual sync, show usage + projection)
- Vite stack (matches Frivillig/Ungfritid)
- Monorepo in Pocket-Smith-Reports — `client/` folder
- FastAPI backend in `src/budget_api/`
- Data storage: existing /private folder (shared with existing reports)
- Manual sync button (pull transactions from PS)
- Show: CC usage, projection, deficit warning, cut suggestions

## L1-L5: TBD