# F4 — CC Dashboard

Status: NOT STARTED (design-first L1-L5)
Date: 2026-07-27
Repo: Pocket-Smith-Reports

## Summary
CC bill (prev month), available, projection, deficit warning.

## Decisions (from grill-me)
- available = salary_events − bill_events (this month, forecasted)
- CC bill = single number (prev month CC spend, due 15th)
- deficit = projected_cc − available → warn if > 0
- Deficit coverage: WARNING when goes into savings account, BIG WARNING when savings cannot cover
- Savings = PS event (budget target) + savings account transactions (actual balance)
- Savings events = separate budget line (NOT in available formula)
- Projected deficit warning at month end
- Forecasting throughout (not just static numbers)

## L1-L5: TBD