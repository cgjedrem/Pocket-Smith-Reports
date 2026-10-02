# Quickstart Validation: Hide Amounts Toggle

**Feature**: `002-hide-amounts-toggle` | **Branch**: `002-hide-amounts-toggle`

Runnable scenarios proving the feature end-to-end. Prerequisites: repo deps
installed (`uv sync`; `pnpm install --frozen-lockfile` in `client/`).

## Scenario 1 — Unit/store behavior (automated)

```powershell
cd client
pnpm test
```

Expected: new `privacy-store` tests pass —
- `maskAmount` returns input unchanged when visible, `"****"` when hidden,
  and preserves `""` as `""` (contract §1).
- `toggleAmountsHidden` flips state, notifies subscribers, persists to
  localStorage; a simulated fresh load restores the persisted value (I-2/I-3).
- `formatKr`, `formatSignedKr`, `formatNOK`, `compactNOK` return `"****"`
  when hidden and normal output when visible.
- No NEW failures vs. the pre-existing baseline (known pre-existing:
  IntersectionObserver stubs, SyncPage hardcoded date).

## Scenario 2 — Build gate (automated)

```powershell
cd client
pnpm build
```

Expected: `tsc -b && vite build` succeeds (or fails only on the documented
pre-existing vite.config/tsconfig issue, unchanged by this feature).

## Scenario 3 — Manual end-to-end (the LinkedIn-screenshot path)

1. Start the app: `scripts\run_api.ps1` (API on 127.0.0.1:8000), then
   `pnpm dev` in `client/` (Vite on 5173).
2. Open http://localhost:5173/reports with real data loaded. Note a few
   figures (salary, a category total, the savings balance).
3. Click the eye icon in the header (top-right of the nav).
   - **Verify**: every figure from step 2 now reads `****`; percentages,
     dates, counts, and all labels unchanged; no page reload, no network
     refetch (check devtools Network tab).
4. Navigate to Mega Reports and Bills.
   - **Verify**: amounts masked everywhere, including table rows, the bills
     graph axis, and chart hover tooltips; chart shapes still render.
5. Reload the browser tab.
   - **Verify**: amounts still masked.
6. Click the eye icon again.
   - **Verify**: exact original figures restored everywhere; reload shows
     figures visible.
7. Keyboard check: Tab to the eye icon, press Space.
   - **Verify**: toggles; screen reader announces the pressed state
     (`aria-pressed` flips).

## Scenario 4 — Screenshot safety spot-check

With masking active, screenshot each page and search the captures visually
for any digit group with `kr` or a currency magnitude. **Verify**: zero hits
other than percentages/counts/dates.

## Rollback

The feature is additive (one new module, one header button, one-line changes
inside existing format helpers). Rollback = revert the branch; no data,
schema, or API migration exists.
