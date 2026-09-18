# F2 — Bill Management

Status: NOT STARTED (design-first L1-L5)
Date: 2026-07-27
Repo: Pocket-Smith-Reports

## Summary
CRUD PS Events (bills, salary, savings) via React → FastAPI → PS Events API.
PS = source of truth. React = UI. FastAPI = thin proxy.

## Decisions (from grill-me)
- Bills = PS Events (no separate bills API — Events IS the bills system)
- Full CRUD via PS Events API: GET/POST/PUT/DELETE /events, /scenarios/{id}/events
- Event fields: category_id, date, amount (neg=debit), repeat_type (once/monthly/etc), repeat_interval, note
- React app = full CRUD UI for PS Events (write-through to PS)
- One scenario: "Budget 2026" — we create and manage it
- Salary + fixed bills = PS events (recurring, stable)
- CC bill = computed locally each run (NOT PS event — amount varies monthly)
- Savings events = separate budget line (planned savings target)

## L1-L5: TBD

## Sub-designs (EconomyBar UI iteration)

- [design-f2-bills-zone-a.md](design-f2-bills-zone-a.md) — Bills zone (APPROVED, in implementation)
- [design-f2-budget-zone-b.md](design-f2-budget-zone-b.md) — Budget zone fill bar (NOT STARTED)
- [design-f2-savings-box-c.md](design-f2-savings-box-c.md) — Savings box (NOT STARTED)