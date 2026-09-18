# F6 — Dynamic Forecasting

Status: NOT STARTED (design-first L1-L5)
Date: 2026-07-27
Repo: Pocket-Smith-Reports

## Summary
Linear projection, deficit → savings warning, cut suggestions.

## Decisions (from grill-me)
- Dynamic budgeting = Meaning 2 (suggestive): deficit warning + show which discretionary categories drove overspend (top 3 by amount over 3-month avg). User decides cuts manually. No auto-adjust.
- Projection method: simplest linear — projected = current_spend × (days_in_month / days_elapsed)
- Baseline for overspend: 3-month rolling average per category
- Discretionary = personal_spend role only (never bills/savings/income)

## L1-L5: TBD