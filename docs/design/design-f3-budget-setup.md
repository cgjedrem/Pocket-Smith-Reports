# F3 — Budget Setup

Status: NOT STARTED (design-first L1-L5)
Date: 2026-07-27
Repo: Pocket-Smith-Reports

## Summary
PS Budget API per-category limits. Common categories split 60/40 locally (Fixture A/Fixture B).

## Decisions (from grill-me)
- Per-category LIMITS set in PS Budget API (per category)
- Personal categories → PS Budget API limit = per-partner limit directly (category already partner-specific)
- Common categories → PS Budget API sets one limit, local rule splits per partner
- Common split: Fixture A 60% / Fixture B 40% (of common category budget)
- Calculation done locally
- Limits apply to CC spend only (variable), not bills

## L1-L5: TBD