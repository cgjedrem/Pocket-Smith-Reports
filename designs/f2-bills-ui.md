# F2-FE — Bills Dashboard UI (APPROVED L1-L3, working L4-L5)

Status: L1-L3 approved. L4-L5 in progress.
Date: 2026-08-03
Repo: Pocket-Smith-Reports
Owner: coordinator

## What this sub-feature is

Wires the existing `/bills-preview` page (and new `/bills` route) to the 4 live BE endpoints
delivered in [f2-bills-dashboard.md](f2-bills-dashboard.md) (sub-features 1-4, PRs #37-#40).
**No component rewrites.** Existing `BillsDashboard`/`MonthCard`/`TableView`/`GraphView`/
`EconomyBar`/`EventRow`/`AddEventDialog` stay byte-identical. New layer translates BE responses
into the existing component shape via a mapper + a swap point (`bills-source.ts`).

## Endpoints consumed

| Endpoint | Role |
|---|---|
| `GET /api/bills/dashboard?month=YYYY-MM` | Full snapshot → hydrate `bills-source.ts` |
| `GET /api/bills/dashboard/events?month=YYYY-MM&...` | Per-month events list (current snapshot source) |
| `GET /api/bills/dashboard/event?id=X&month=YYYY-MM` | One event for the dialog |
| `GET /api/sync?start_month=&end_month=` | Trigger sync on 404 (via `/sync` page navigation) |

CORS allows `localhost:5173` + `:5174`. Vite proxy `/api` → `localhost:8000`.

## Related docs
- [f2-bills-dashboard.md](f2-bills-dashboard.md) — BE sub-features 1-4 (snapshot shape, error envelopes).
- [f2-bills-sync.md](f2-bills-sync.md) — sub-feature 1 (sync writes the snapshot file).

---

# L1 — Capabilities (APPROVED)

## In-scope

1. **Replace `getMonths()`/`getAllEvents()` data source with live BE API**, via `lib/bills-source.ts` swap pattern. Zero component changes.
2. **New `/bills` route** alongside existing `/bills-preview`. Both render the same `BillsPage` (alias).
3. **URL-driven month**: `/bills?month=YYYY-MM`. Default = `currentMonth()`.
4. **Month dropdown** (Radix Select, like `MonthSidebar` in reports) drives URL + refetch.
5. **Snapshot 404 → page takeover** with `BillsNotFoundAlert` + "Run sync" button → navigates to `/sync?start_month=X&end_month=X`.
6. **Snapshot 500/network → ErrorAlert + retry button**.
7. **Event click in TableView → EventDetailDialog** opens with full event dict (BE `event` endpoint).
8. **Event 404 in dialog** → "Event not found in {month}" copy, auto-close 3s.
9. **Warnings banner** above dashboard when `snapshot.warnings[]` non-empty.
10. **Stale badge** when `synced_at > 24h` old + re-run sync link.
11. **Local `useState` + custom hooks** (`useBillsSnapshot`, `useBillsEvents`, `useBillsEvent`). No SWR/TQ.
12. **TS types** mirror Pydantic `BillsEvent`/`PartnerBills`/`BillsSnapshot` exactly. New file `client/src/types/bills.ts`.
13. **API client** `client/src/api/bills.ts` — `getSnapshot(month)`, `getEvents(month, filters)`, `getEvent(id, month)`.
14. **Mapper** `client/src/lib/bills-mapper.ts` — pure: BE → existing component shapes.
15. **Unit + component tests**: mapper, hooks, page, API client. No Playwright (not installed in repo).

## Out-of-scope

1. No CRUD (no add/edit/delete events) — `AddEventDialog` stays stub.
2. No Redux / Zustand.
3. No SWR / TanStack Query.
4. No new shadcn primitives (Dialog/Card/Table/Select/Popover/Button/Badge already installed).
5. No auto-sync on 404.
6. No new BE endpoints.
7. No Pydantic-validate on FE.
8. No locale change (en-NO via existing `formatKr`).
9. No GraphView changes — existing 12-month iteration accepts mapped single-month snapshot.
10. No Playwright e2e.
11. **No component rewrites** (`BillsDashboard`/`MonthCard`/`TableView`/`GraphView`/`EconomyBar`/`EventRow`/`AddEventDialog` untouched).

## Success criteria

| Outcome | Measure |
|---|---|
| User opens `/bills?month=2026-07` | 200 + snapshot hydrates source + `BillsDashboard` re-renders with live data. |
| Snapshot missing (404) | Page takeover alert + "Run sync" button. |
| Snapshot 500/network | `ErrorAlert` + retry button. |
| User changes month in dropdown | URL updates, source re-hydrates, components re-render. |
| Snapshot `warnings[]` non-empty | Yellow `BillsWarningBanner` above dashboard. |
| Stale `synced_at` (>24h) | `BillsStaleBadge` + re-sync link. |
| User clicks event row in TableView | `EventDetailDialog` opens, fetches event, renders 10 fields. |
| Event 404 in dialog | Dialog shows "Event not found", auto-closes 3s. |
| `pnpm tsc -b` | Passes (TS strict). |
| `pnpm test` | All existing tests + new tests green. |
| Live dev smoke | `pnpm dev` + BE on `:8000` → `/bills?month=2026-07` renders content. |

## Risks

| Risk | Mitigation |
|---|---|
| All 12 dev snapshots empty (observed) | Empty state copy in `TableView` + dialog "No events this month". |
| Source module race on rapid month switch | `AbortController` cancels in-flight fetch before hydrate. |
| `useBillsSnapshot` StrictMode double-mount | `useEffect` cleanup aborts first request. |
| Existing tests import `getMonths` from `finance-data.ts` directly | Keep `finance-data.ts` exports intact. Source module re-exports + falls back. |
| Dialog fetches event while page refetches snapshot | Each hook has own AbortController. |
| Mapper field mapping errors | Pure unit tests cover each branch. |

---

# L2 — Components (APPROVED)

## Existing components (REUSE-ONLY, no rewrites)

| Component | File | Role |
|---|---|---|
| `BillsDashboard` | [components/bills/BillsDashboard.tsx](../client/src/components/bills/BillsDashboard.tsx) | Unchanged. Calls `getMonths()` from `bills-source.ts`. |
| `MonthCard` | [components/bills/MonthCard.tsx](../client/src/components/bills/MonthCard.tsx) | Unchanged. |
| `EventRow` | [components/bills/EventRow.tsx](../client/src/components/bills/EventRow.tsx) | Unchanged. |
| `TableView` | [components/bills/TableView.tsx](../client/src/components/bills/TableView.tsx) | Unchanged. Calls `getAllEvents()` from `bills-source.ts`. |
| `GraphView` | [components/bills/GraphView.tsx](../client/src/components/bills/GraphView.tsx) | Unchanged. |
| `EconomyBar` | [components/bills/EconomyBar.tsx](../client/src/components/bills/EconomyBar.tsx) | Unchanged. |
| `AddEventDialog` | [components/bills/AddEventDialog.tsx](../client/src/components/bills/AddEventDialog.tsx) | Unchanged (no CRUD in scope). |
| `formatKr`/`formatDate`/`ordinalDay`/`formatSignedKr` | [components/bills/finance-data.ts](../client/src/components/bills/finance-data.ts) | Unchanged. |
| `PARTNERS`/`getMonths()`/`getAllEvents()` | [components/bills/finance-data.ts](../client/src/components/bills/finance-data.ts) | Unchanged exports. |
| `ErrorAlert`, `cn()`, `ErrorBoundary`, shadcn UI | existing | Unchanged. |

## New components

| Component | File | Role |
|---|---|---|
| **BE types** | `client/src/types/bills.ts` | `BillsEvent`, `PartnerBills`, `BillsSnapshot`, `BillsEventList`, `BillsSourceCounts`, `BillsEventType`, `BillsPartnerStatus`. Mirror Pydantic 1:1. |
| **API client** | `client/src/api/bills.ts` | `getSnapshot(month)`, `getEvents(month, filters)`, `getEvent(id, month)`. Thin `apiGet` wrappers. |
| **Mapper** | `client/src/lib/bills-mapper.ts` | Pure: `BillsSnapshot → MonthData[]` (single entry), `BillsSnapshot → FinanceEvent[]`, `PartnerBills → PartnerEconomy` (derive bar view). |
| **Source module** | `client/src/lib/bills-source.ts` | Module state: `monthlyData` + `events`. Exports `getMonths()` + `getAllEvents()` + `hydrate(snapshot)`. Falls back to mock when no hydration. |
| **Hooks** | `client/src/hooks/useBills.ts` | `useBillsSnapshot(month)`, `useBillsEvents(month, filters)`, `useBillsEvent(id, month, open)`. |
| **Month select** | `client/src/components/bills/BillsMonthSelect.tsx` | Radix Select dropdown, 12 months back + current + next 3. |
| **Warning banner** | `client/src/components/bills/BillsWarningBanner.tsx` | Yellow card for `snapshot.warnings[]`. |
| **Stale badge** | `client/src/components/bills/BillsStaleBadge.tsx` | Badge when `synced_at > 24h`. |
| **Not-found alert** | `client/src/components/bills/BillsNotFoundAlert.tsx` | Full-width alert + "Run sync" button. |
| **Event detail dialog** | `client/src/components/bills/EventDetailDialog.tsx` | shadcn Dialog + event fetch. |
| **Page** | `client/src/pages/BillsPage.tsx` | Wraps `BillsDashboard`. Owns URL, hydration, dialog, 404. |

## Updated files (minimal)

| File | Change |
|---|---|
| `client/src/router.tsx` | Add `/bills` route → `BillsPage`. Keep `/bills-preview` → `BillsPreviewPage`. |
| `client/src/layouts/AppLayout.tsx` | Update "Bills Preview" link → `/bills`. |
| `client/src/pages/BillsPreviewPage.tsx` | 1-line alias: `export { BillsPage as BillsPreviewPage } from "./BillsPage"`. |

## New tests

| File | Coverage |
|---|---|
| `client/src/api/__tests__/bills.test.ts` | API client thin wrappers. Mock `api/client`. |
| `client/src/lib/__tests__/bills-mapper.test.ts` | Pure mapper: BE → component shapes. |
| `client/src/hooks/__tests__/useBills.test.ts` | Hook 200/404/500 paths. Mock `api/bills`. |
| `client/src/tests/BillsPage.test.tsx` | Page renders 200/404/500/dialog/month change. |

## Component boundaries

```
URL: /bills?month=YYYY-MM
  │
  ▼
BillsPage mount
  │
  ├── useSearchParams() → month
  ├── useBillsSnapshot(month)  ── fetch /api/bills/dashboard
  │     [200] → bills-source.hydrate(mapSnapshot(snapshot))
  │             → BillsDashboard re-renders (subscribed via source)
  ├── useBillsEvents(month)    ── fetch /api/bills/dashboard/events
  ├── view state (grid|graph|table) local useState
  └── dialog state {open, eventId} local useState
  │
  ▼
render branches (see L3)
```

## L2 locked decisions

1. **Add-only**. No component rewrites.
2. **Source module pattern** = single swap point.
3. **404 = full-page alert**.
4. **Event detail = dialog**.
5. **Month dropdown = new `BillsMonthSelect`** (Radix Select).
6. **Run sync = `useNavigate` to `/sync?start_month=X&end_month=X`**.
7. **Stale badge >24h**.
8. **Old mock types stay in `types/api.ts`**.
9. **Mapper is pure**, single source of truth for BE → component translation.
10. **`/bills-preview` route stays** (alias). Zero test changes.

---

# L3 — Interactions (APPROVED)

## Mount: `/bills?month=YYYY-MM`

```
Browser navigates to /bills?month=2026-07
  │
  ▼
BillsPage mount
  │
  ├── useSearchParams() → month = "2026-07" (or currentMonth() fallback)
  │
  ├── useBillsSnapshot("2026-07")  ── async fetch
  │     │
  │     ├── [200 OK] → bills-source.hydrate(mapSnapshot(snapshot))
  │     │              setState({snapshot, notFound: false, error: null})
  │     │              → BillsDashboard re-renders from bills-source.ts (live)
  │     │
  │     ├── [404] → setState({snapshot: null, notFound: true, error: null})
  │     │           render <BillsNotFoundAlert month={month} />
  │     │
  │     ├── [400/500] → setState({snapshot: null, notFound: false, error: ApiError})
  │     │               render <ErrorAlert> + retry
  │     │
  │     └── [network] → setState({snapshot: null, notFound: false, error: ApiError("Cannot reach server")})
  │                     render <ErrorAlert> + retry
  │
  ├── useBillsEvents(month)  ── async fetch (parallel)
  │     │
  │     ├── [200] → store events for dialog use (TableView uses mapped from source)
  │     ├── [400] → events error in ErrorAlert (page still shows snapshot)
  │     └── [500/network] → events error
  │
  ├── view state (grid|graph|table) default "grid"
  └── dialog state {open: false, eventId: null}
```

## Source module hydration (key flow)

```
bills-source.ts (module state)
  │
  ├── module state:
  │     monthlyData: MonthData | null  (null = use mock fallback)
  │     events: FinanceEvent[]
  │     subscribers: Set<() => void>  (for re-render signal)
  │
  ├── export getMonths(): MonthData[]
  │     return monthlyData ? [monthlyData] : mockGetMonths()
  │
  ├── export getAllEvents(): FinanceEvent[]
  │     return events.length > 0 ? events : mockGetAllEvents()
  │
  ├── export hydrate(snapshot: BillsSnapshot): void
  │     monthlyData = mapSnapshotToMonthData(snapshot)
  │     events = mapSnapshotToEvents(snapshot)
  │     subscribers.forEach(fn => fn())
  │
  └── export subscribe(listener: () => void): () => void
        subscribers.add(listener)
        return () => subscribers.delete(listener)
```

```
useBillsSnapshot(month) success
  │
  ▼
bills-source.hydrate(mapSnapshotToMonthData(snapshot))
  │
  ├── monthlyData updated
  ├── events updated
  └── subscribers notified
        │
        ▼
BillsDashboard re-renders from bills-source.ts (now live)
```

**Why source module pattern**: existing `BillsDashboard` calls `getMonths()` + `getAllEvents()`
synchronously at render time. Replacing those call sites = rewrite 5 components. Keeping them
but **making them read from a swappable module** = zero component changes. The hook fetches →
mapper → source hydrate → existing tree re-renders with live data.

**Subscription pattern**: components that read source data subscribe in `useEffect`. On hydrate,
subscribers called → React state bumps → re-render. This avoids making source reads observable
via React's reconciler directly.

## Render branches (BillsPage)

```
state                                          render
─────────────────────────────────────────────────────────────────
notFound === true                              <BillsNotFoundAlert month={month} />
                                                (full takeover, no body)

loading && !snapshot && !error                 <Skeleton />

error && !notFound                             <ErrorAlert message={error.detail} /> + Retry

snapshot loaded                                <BillsWarningBanner warnings={snapshot.warnings} />
                                                <header>
                                                  <BillsMonthSelect value={month} onChange={setMonth} />
                                                  <BillsStaleBadge syncedAt={snapshot.synced_at} />
                                                </header>
                                                <BillsDashboard onEventClick={openDialog} />
                                                <EventDetailDialog
                                                  open={dialog.open}
                                                  id={dialog.eventId}
                                                  month={month}
                                                  onClose={closeDialog}
                                                />
```

## View toggle (existing — unchanged)

```
BillsDashboard (unchanged) toggle: grid | graph | table
  grid  → 2x MonthCard + event list (collapsed)
  graph → GraphView (iterates months; single-month snapshot = current month only)
  table → TableView with all events
```

## Month change

```
User selects month in BillsMonthSelect
  │
  ▼
BillsPage.setMonth(newMonth)
  ├── setSearchParams({month: newMonth}) → URL updates
  ├── useBillsSnapshot(newMonth) refetches (AbortController cancels previous)
  │     ├── [200] → bills-source.hydrate(newSnapshot)
  │     └── [404] → BillsNotFoundAlert
  └── useBillsEvents(newMonth) refetches
```

## Event click → dialog

```
User clicks event row in TableView
  │
  ▼
TableView calls onEventClick(event.id) → BillsPage.openDialog(eventId)
  │
  ▼
EventDetailDialog open=true, mounts
  │
  ├── useBillsEvent(id, month, open=true) fetches /api/bills/dashboard/event?id=X&month=Y
  │     ├── [200] → render 10 fields
  │     ├── [404 "Event not found"] → show copy, auto-close 3s via setTimeout
  │     └── [400/500] → show error, stay open
  │
  ▼
User clicks Close / X / Escape → BillsPage.closeDialog() → dialog.open=false
```

## Stale data interaction

```
isStale(syncedAt) = (Date.now() - new Date(syncedAt).getTime() > 24 * 3600 * 1000)
  │
  ├── true  → <BillsStaleBadge /> + "Re-run sync" link → /sync?start_month=X&end_month=X
  └── false → badge hidden
```

---

# L2 amendment (2026-08-03) — planned-vs-actual row pair on past months

`EconomyBar` now renders extra row pair on past months only.
Sits below existing `Bills` + `Estimated cc bill` row inside the bills zone.

**Capsule branch (big bar):**
- New `<div>` inside `<Zone>`, BELOW existing `justify-between` row.
- Past-only gate: `realBills != null` (current/future → null → row hidden).
- Left pair: label "Bills (planned)" + value `billsLabel` (event-derived, keep).
- Right pair: label "Real bills" + value `realBillsLabel` (posted-txn sum, new).
- Muted tone (`text-foreground/60` label, `text-foreground/70` value).
- No new color, no red fill, no TOTAL BILLS pill change.

**Labels-list branch (small bar):**
- Two new `LabelsListRow`s AFTER "Estimated cc bill", BEFORE "Budget".
- Same past-only gate.
- `icon={Receipt}` for both, labels: "Bills (planned)" / "Real bills".

**Gating:** `realBills: number | null` — null for current/future.
UI key: `economy.realBills != null` → render row, else hide.

**Unchanged:** red fill width, TOTAL BILLS pill value (`bills + estCcBill`),
`upperBarTotalLabel` math, all 3 capsules branches' width formulas.

**Files touched (FE only):**
- `client/src/types/bills.ts` — `PartnerBills.real_bills: number | null`
- `client/src/types/api.ts` — `PartnerEconomy.realBills` + `realBillsLabel`
- `client/src/lib/bills-mapper.ts` — map `partner.real_bills` → fields
- `client/src/components/bills/EconomyBar.tsx` — destructure + 2 render sites
- `client/src/components/bills/__tests__/economy-bar-bills-zone.test.tsx` — `makeEconomy()` default null + new past-only test
- `client/src/components/bills/__tests__/economy-bar-budget-zone.test.tsx` — `makeEconomy()` default null
- `designs/f2-bills-ui.md` — this section


## Run sync navigation

```
User clicks "Run sync" in BillsNotFoundAlert
  │
  ▼
navigate(`/sync?start_month=${month}&end_month=${month}`)
  │
  ▼
SyncPage picks up query params, runs sync
  │
  └── User navigates back to /bills manually after sync completes (no auto-redirect)
```

## Failure modes

| Failure | State | UI |
|---|---|---|
| `month` missing/invalid URL | `currentMonth()` fallback | No error. |
| Snapshot 200 | `snapshot: BillsSnapshot` → hydrate source → `BillsDashboard` re-renders | Normal. |
| Snapshot 404 | `notFound: true` | `<BillsNotFoundAlert />` page takeover. |
| Snapshot 400/500 | `error: ApiError` | `<ErrorAlert>` + retry. |
| Network throw | `error: ApiError("Cannot reach server")` | Same. |
| Events 200 | `events: BillsEvent[]` (mapped for dialog) | Normal. |
| Events 200 empty (`total: 0`) | `events: []` | TableView "No events this month" (existing empty copy). |
| Event 200 | `event: BillsEvent` | Dialog renders 10 fields. |
| Event 404 ("Event not found") | `eventNotFound: true` | Dialog copy, auto-close 3s. |
| Stale `synced_at` (>24h) | `isStale: true` (computed inline) | Badge + re-sync link. |
| Non-empty `warnings[]` | banner | `<BillsWarningBanner />` above dashboard. |
| Hydrate before snapshot loaded | `monthlyData === null` | Source returns mock. UI shows mock data. |

## Concurrency

- **AbortController** in `useEffect` cleanup for in-flight cancellation on month change or unmount.
- **Source hydration is sync** (set module state + notify subscribers). No race since one hook drives it at a time per page.
- **StrictMode double-mount**: hooks tolerate via cleanup.
- **Subscription cleanup**: `useEffect` return value unsubscribes from source on unmount.

## Observability

| Touchpoint | Where | What | Why |
|---|---|---|---|
| Browser console | `client.ts` already logs `Cannot reach server` | Network error fallback | Match existing. |
| `console.error` in hooks | `useBills` fetch error path | Log unexpected non-API errors | Dev debugging. |
| No new logging infra | — | — | Match existing codebase. |

## Security

- All inputs are query params validated by BE (regex on month, allow-list on type, etc.).
- No user-provided HTML rendering.
- No tokens / cookies (single-user app).
- No CORS concerns (same-origin via Vite proxy).

## L3 locked decisions

1. **URL-driven month** via `useSearchParams`. Default = `currentMonth()`.
2. **Source module** = `lib/bills-source.ts`. Single swap point with subscribe/notify.
3. **404 = page takeover** alert.
4. **Event detail dialog** with auto-close on event-not-found 3s.
5. **Run sync = `useNavigate` to `/sync?start_month=X&end_month=X`**.
6. **Stale badge >24h**.
7. **Warnings banner** for non-empty `warnings[]`.
8. **Graph view unchanged** — accepts single mapped `MonthData[]` from source.
9. **Subscription pattern** for source → component re-render signal.
10. **AbortController** in all hooks.
