# F2 — Bills & Scheduled Buys — Per-Field Derivations (DRAFT)

Status: L2 in progress. Math bodies refined for §1-§13. §8 RESOLVED 2026-08-28 (grill-me round 4: forward formula). §12 RESOLVED 2026-08-04 (savings-balance-anchor doc, implemented). §13 REVISED 2026-08-28 (user decision: savings_delta = savings-account-only posted flow).
Date: 2026-08-02
Repo: Pocket-Smith-Reports
Owner: coordinator

## What this doc is

The math. For every field on the dashboard, this doc spells out the PS query,
the filter, the formula, and the edge cases. Read together with
[f2-bills-source-of-truth.md](f2-bills-source-of-truth.md).

Related:
- Source-of-truth decisions: [f2-bills-source-of-truth.md](f2-bills-source-of-truth.md)
- PS-side notes: [f2-bills-ps-integration.md](f2-bills-ps-integration.md)
- Existing FE math: [client/src/components/bills/finance-data.ts](../client/src/components/bills/finance-data.ts)
- PS client: [src/budget_api/services/ps_client.py](../src/budget_api/services/ps_client.py)

---

### 1. Salary
- Source: `PSClient.get_events(user_id, month_start, month_end)`.
- Filter: `category_id` is in our `income` role (from `category_roles.json`).
- Group by partner (transaction_account → partner via `account_mappings.json`
  `accounts[id].partner_id`). **Do not use `account_owners.json`** — that file
  has dangling references and is not written by the sync flow.
- One income event per partner per month → take its absolute amount.
- Edge case: multiple income events per partner per month → **CONFIRMED**: sum them
  (only bills-account "CC payments" category events).
- Edge case: missing for a month → **CONFIRMED**: fall back to prior month + warning flag.

### 2. Savings transfer
- **Inputs**:
  1. `scheduledSavings`: sum of PS savings events in the month, per partner.
  2. `billsAccountBalanceDelta` = `currentBalance(billsAcct) - openingBalance(billsAcct)`.
  3. `expectedBalanceChange` = `salary - bills` (same partner, same month).
- **Formula**: `savingsTransfer = scheduledSavings + (billsAccountBalanceDelta - expectedBalanceChange)`.
- **Why**: if the bills account grew/shrank more than salary-minus-bills, the
  difference is savings.
- Per partner. Signed (positive = into savings).
- **Superseded note (2026-08-28):** the correction-vs-scheduled comparison
  now lives in the planned/actual pair — see §13 (`savings_planned` vs
  `savings_delta`). This section's formula is retained as the definition
  of the transfer amount itself.
- Edge case: no bills account mapped → **CONFIRMED**: return error (422).

### 3. Categories
- Reuse the existing sync output: `data/private/category_catalog.json`.
- The category tree is fetched via `PSClient.get_categories` during the standard
  PS sync (existing flow). F2-BE reads from the JSON, does not re-call PS.
- **TBD**: how FE gets a category title for an event (current `category_mappings`
  endpoint is for mappings, not titles). See L3 API contract.

### 4. Bill titles (bills-account spend events, recurring + one-off)
- Source: `PSClient.get_events(user_id, month_start, month_end)`.
- Filter: category role `spend` AND `transaction_account.type == "bank"` AND
  `account_mappings.type == "checking"`. **Both recurring and one-off** (no
  `repeat_type` filter).
- `payee` first, fall back to `note` if payee is empty (mirrors existing report
  logic in [src/mom/data.py:298](../src/mom/data.py#L298)).
- Per partner via `account_mappings.json` on the transaction account.

### 5. Scheduled buys (CC-account spend events, recurring + one-off)
- Same `get_events` payload, filtered to: category role `spend` AND
  `transaction_account.type == "credits"` (PS enum value). **Both
  recurring and one-off**.
- Any spend on a CC account — monthly subscriptions, recurring insurance,
  one-off purchases — all count as "buys" for the dashboard.
- Per partner via `account_mappings.json`.
- Payee → title. Category title → category.

### 6. Buy item names + categories
- Same as §5: `payee` → name; `category.title` for category.

### 7. Savings transfers
- Same `get_events` payload, filtered to: category role `savings`. **Both
  recurring and one-off**.
- Per partner via `account_mappings.json` on the transaction account.
- This is the "scheduled" half of the savings-transfer calculation in §2.

### 8. Everyday budget (per partner, per month)
- **RESOLVED 2026-08-28 (grill-me round 4).** Supersedes the round-3 lag draft below.
- **Formula (all month kinds — past, current, future):**
  `everydayBudget(m) = salary(m+1) − totalBills(m+1) − scheduledCcBuys(m+1)`
  where the m+1 terms come from PS scheduled events (future) or actuals (past).
- **Semantics:** the value on month m is the **CC spending allowance for m** —
  how much the partner can put on the credit card during m, because the CC bill
  is paid from m+1's income. The capsule intentionally compares next month's
  money (budget) against this month's actual usage (`budgetUsage`, `ccUsage`).
- **Direction note:** this reverses the round-3 draft
  (`salary(prev) − totalBills(prev)`). User decision 2026-08-28: forward-looking
  is correct — "this is budget for cc, and I pay cc next month."
- **Edge case — last month in sync window:** m+1 data does not exist →
  return `null`; FE hides the budget zone. No flat-repeat or same-month
  fallback (both silently wrong).
- Per-partner. Per-month. `null` is a legitimate value (last-window month only).
- **Distinct from the display `budget`** (FE presentation sub-derivation): the
  display value shown in the UI is `budget = everydayBudget + ccBuys` (so the
  budget zone covers both planned card spend and the share of everyday that
  lands on the card). The display budget is computed by the FE — see §17 below.
  The BE returns only `everydayBudget`.
  **Open L3 question:** the new formula already subtracts `scheduledCcBuys(m+1)`;
  whether the FE should still add `ccBuys` on top needs re-checking when the
  API contract is written.

### 9. CC bill — past / current / future (per partner)

**Per round-3 decision, two separate response fields:**
- `estimated_cc_bill` — populated for **current + future** months. Per
  [source-of-truth field table](f2-bills-source-of-truth.md).
- `real_cc_bill` — populated for **past** months.
- `net` uses `estimated_cc_bill` for current + future, `real_cc_bill` for past.
- The FE does **NOT** need a separate `real_cc_bill_so_far` field for the
  current month — the real CC-payment events appear in `events[]` with
  `is_cc_payment=true`, and the FE sums them locally if it wants a real-so-far
  indicator.

**`estimated_cc_bill(partner, m)` formula** (REVISED 2026-08-28, grill-me
round 6 — envelope model; supersedes the 2026-07-31 match-based formula):

Scheduled CC buys are treated as **budget envelopes**, never matched to
transactions. Rationale: real charges fragment (Hello Fresh posts as 9
lines of 39-1,189 against a 1,300/wk event) and drift in date — exact or
fuzzy matching is unmaintainable, and the match-based estimate
double-counted every posted buy (September 2026 estimate was 44,095 vs
real ~30,620).

- **Future month m:** `estimated = posted CC spend of month m−1` (signed
  debits, abs-summed, CC-paydown category excluded). No events leg.
  Slides forward: for m+1 the "prior" month is m, etc.
- **Current month:** `estimated = posted-so-far(this month) + remaining
  envelope` where remaining envelope = for each scheduled CC-buy event
  dated later this month (date > last synced day), its abs amount.
  Events dated on/before today whose amounts did or didn't post are
  irrelevant — posted-so-far already carries reality. No matching, no
  `is_matched` involvement.
- **Past months:** not used (`real_cc_bill` instead).
- Edge case: no CC account for partner → 0 on all paths.

**`is_matched` deprecation:** the estimate path no longer consumes
`is_matched`. The events-table badge (FE) may keep using
`match_scheduled_buys` output as a cosmetic "posted" marker — that is a
display concern only, decoupled from the estimate.

**`real_cc_bill(partner, month)` formula** (past months only):
- `real_cc_bill(partner, month) = sum of all transactions from the partner's
  **bills/checking account** posted to the "CC payments" category, dated in that
  month`.
- The paydown flows: bills account → CC account. A "CC payment" category
  transaction on the **bills** side is the cash leaving; on the **CC** side is
  the balance reducing. We pick the **bills-account** side to avoid
  double-counting.
- Per-partner filter via `account_mappings.json` (the bills account's owner).

**`is_cc_payment` flag on events:**
- Set to `true` on bills-account transactions where the category is the
  per-partner "CC payments" category.
- Same source as `real_cc_bill` — they're different views of the same data.
- The FE uses this to suppress CC-paydown rows in the table view.
- UI shows both numbers until the bill is fully paid for the month.

**Pre-knowledge handling** (per user 2026-07-31, **14-20 days before the bill
is due**):
- CC bills land predictably — Fixture A/Fixture B know ~14-20 days in advance what
  the upcoming bill will be (previous month's CC spend + scheduled CC buys).
- The "estimated" value is **already known** to the user ahead of time. Don't
  auto-flip to real when a transaction posts — show **estimate + real-so-far**
  together.
- **The status bar uses the estimate as the "expected" value, and the real-so-far
  is informational only until the bill is fully paid.**

**For future months** (per user 2026-07-31):
- Always the estimate. `futureCcBill(partner, m) = estimatedCcBill(partner)`
  (slides forward — for future month m, the "previous" month is m-1).

**Scheduled CC buys in the estimate** (REVISED 2026-08-28, grill-me round 6):
- Buys are budget envelopes. Future-month estimates use prior-month posted
  spend only; the current-month estimate adds the remaining (not-yet-dated)
  envelope for the rest of the month. The old exact (date, amount) matching
  removed <1% of the double-count on real data and is abandoned on this path.

Edge case: no CC account for partner → 0 for all three paths. **TBD**: how to
render this.

### 9a. CC payment category — per partner
- Each partner has their own "CC payments" category in PS. We look it up via the
  **category tree on the bills account**: walk the partner's bills-account
  transactions, find the category that appears as outgoing "CC payment" → that's
  the category id. Cache it.
- **TBD**: confirm exact title per partner (e.g. `"CC payments"` vs
  `"CC Payment (paired)"` — see
  [data/private/category_catalog.json](../data/private/category_catalog.json)
  which has a child `"CC Payment (paired)"`).

### 10. CC usage (current month, per partner)
- `ccUsage = sum of CC-account transactions dated in current month` across
  partner's CC accounts.
- Per partner. Used for the `ccUsageWidth` bar slice (only meaningful for the
  current month — past months are fully settled, future months are unknown).

### 11. Budget usage (per partner, current month)
- **Renamed from `real_budget_usage`** (per round-3 decision).
- `budgetUsage(partner) = sum of spend transactions for that partner in the
  current month, on non-CC / non-savings / non-transfer accounts`.
- I.e. the per-partner spend that lands on the bills/checking account, excluding
  CC-paydowns (which are on the bills account too but flagged `is_cc_payment=true`).
- The "spend" classification: positive in PS = debit on the account → counts.
  (Need to confirm PS sign convention for transactions vs events — events use
  negative-amount = expense; transactions may differ.)
- Past months: FE derives from `events[]` (sum spend events on bills account
  minus `is_cc_payment=true` events).
- Future months: not surfaced (no real data yet).

### 12. Savings balance — past / current / future

**RESOLVED 2026-08-04** — superseded by
[design-f2-savings-balance-anchor.md](f2-bills-savings-balance-anchor.md)
(implemented; definition-of-done complete, deviations logged). Summary:

- **Current month**: live `current_balance` sum of the partner's mapped bills +
  savings accounts, read from `account_catalog.json`. The anchor.
- **Past months**: back-walk from the anchor —
  `savings_balance[m] = savings_balance[m+1] − savings_delta[m]`.
- **Future months**: lag model, unchanged —
  `savings_balance[m] = savings_balance[m−1] + savings_delta[m−1]`.
- Missing live data → fall back to lag model + warning. Never silent zero.
- No schema bump. Past snapshots re-synced on disk
  (`scripts/re_sync_savings_chain.py`, 2025-08 → 2026-08).

### 13. Savings planned + delta (per partner, per month) — F2-C savings box driver

**REVISED 2026-08-28 (user decision, supersedes grill-me round 5).** The
savings box is a **budget-vs-actual** pair, same mental model as the
budget zone: planned envelope + actual fill.

**`savings_planned` (NEW field, all month kinds):**
- `savingsPlanned(partner, month) = salary(month) − bills(month) − estimatedCcBill(month)`
  (past months use `real_cc_bill` in place of `estimated_cc_bill`, per §14).
- Static — computed from the month's PS events. The *expected* leftover.

**`savings_delta` (actual-so-far) — savings accounts ONLY:**
- Signed net of POSTED transactions on the partner's **savings accounts**,
  dated in-month. Checking/bills-account activity NEVER counts — salary
  timing, CC paydowns, overdraft recovery, paired reimbursements are all
  checking noise and must not pollute savings.
- **Past months**: savings-account-only posted flow (was: combined
  bills+savings cash flow).
- **Current month**: same savings-account-only posted flow (was: live
  anchor − back-walked end-of-prior-month balance).
  - Edge case — savings accounts unresolvable / chain kwargs absent:
    `savings_delta = null` + warning (honest; planned still computed).
    Never a silent 0, never a planned fallback posing as actual.
  - Savings accounts resolve fine but no txns posted → `0.0` is CORRECT
    (nothing saved).
- **Future months**: `null` — no reality exists yet. Only `savings_planned`
  is populated. (The lag chain in §12 consumes `savings_planned` for
  future months; for the first future month it consumes the current
  month's REAL savings-only delta — the anchor is current reality, and
  savings-only flow is just the part that landed in savings.)

**Chain/delta split (subtle):** the chain's internal `deltas_per_month`
(balance back-walk plumbing, §12) stays **combined bills+savings** flow —
the chain invariant `balance[m+1] = balance[m] + delta[m]` holds for
combined balances. The *displayed* `savings_delta` field is savings-only
for both current and past months. Two different numbers, two purposes.

**FE rendering:** savings box shows planned as the envelope and delta as
the fill (budget-zone pattern). `null` delta (future months, missing
anchor) → fill hidden, envelope still shown.

**Signed.** Positive delta = savings grew this month. Negative = net
outflow (pull from savings). Zero on the 1st of the current month before
anything posts is *correct* — nothing has landed yet.

### 14. Net
- `net = salary - bills - estCcBill` per partner. (Past months: `- realCcBill`.)

### 15. Status rule
- Unchanged. Verbatim from
  [client/src/components/bills/finance-data.ts:115-123](../client/src/components/bills/finance-data.ts#L115-L123).

### 16. Capsule width
- Unchanged. Verbatim from
  [client/src/components/bills/finance-data.ts:88-99](../client/src/components/bills/finance-data.ts#L88-L99).

### 17. Date logic
- Each event owns its own `date` (ISO yyyy-mm-dd) and `day` (1-31).
- Recurring PS events get their per-month date from PS (the day field on the
  event + month rollover).
- Local buys store `date` directly.
- No random day assignment. No `day ≤ 28` clamp — actual month length respected.

---

## Presentation sub-derivations (FE-side)

These are computed **in the FE**, not the BE. The BE response returns only the
high-level fields; the FE derives these display values locally.

Reason: keeps the BE response clean (~20 fields per partner) instead of ~36
(every presentation sub-width). Trade-off: FE owns a piece of the math. The
formulas are pinned here so the BE and FE stay aligned.

### Display `budget`
- `displayBudget = everydayBudget + ccBuys`.
- Used by the budget zone (right panel of the capsule).

### Capsule sub-widths (FE, presentation)

| Sub-field | Formula | Source field(s) |
|---|---|---|
| `bar.upperBarWidth` | `(bills + estCcBill) / salary * 0.659 * 100`, min 6% | salary, bills, estCcBill |
| `bar.billsWidth` | share of capsule assigned to bills zone | salary, bills, estCcBill, budget |
| `bar.budgetWidth` | constant 11.862% of salary zone (= 7% / 0.659 × 100) | constant |
| `bar.billsFillWidth` | `bills / (bills + estCcBill)` × 100, clamped [0, 100] | bills, estCcBill |
| `bar.billsFillSmall` | `totalBills / salary < 0.05` (capsule too narrow to show inline labels) | salary, bills, estCcBill |
| `bar.estCcBillWidth` | `estCcBill / displayBudget` × 100, clamped | estCcBill, displayBudget |
| `bar.ccUsageWidth` | `ccUsage / estCcBill` × 100, clamped [0, 100] | ccUsage, estCcBill |
| `bar.budgetUsageWidth` | `ccUsage / displayBudget` × 100, clamped [0, 100] | ccUsage, displayBudget |
| `bar.budgetOverspent` | `ccUsage > displayBudget` | ccUsage, displayBudget |
| `bar.budgetFillTone` | `"shortfall"` if `ccUsage / displayBudget ≥ 0.8`, `"warning"` if `≥ 0.5`, else `"income"`. At-budget (`ratio === 1`) tints `shortfall`. | ccUsage, displayBudget |
| `bar.savingsDeltaWidth` | `|savingsDelta| / savingsBalance` × 100, clamped [0, 100] | savingsDelta, savingsBalance |
| `bar.savingsDeltaTone` | `"income"` if `savingsDelta > 0`, `"shortfall"` if `< 0`, `"neutral"` if `0` | savingsDelta |
| `bar.salaryWidth` | `salary / (bills + estCcBill)` × 100, min 6% | salary, bills, estCcBill |
| `bar.remainingLabel` | `"X kr left"` if `salary − bills − estCcBill ≥ 0`, else `"X kr short"` | salary, bills, estCcBill |
| `bar.remainingTone` | `"income"` if remaining ≥ 0, else `"shortfall"` | derived from `remainingLabel` |
| `bar.netLabel` | `formatKr(net)` | net |

### Bills count / buys count (FE)
- `billsCount = events.filter(e => e.transaction_account.type == "bank" && e.account_mappings.type == "checking" && e.amount < 0).length`
- `buysCount = events.filter(e => e.transaction_account.type == "credits" && e.amount < 0).length`
- Computed from the event list the BE returns. No extra API surface needed.

### Pre-formatted display strings (FE)
- `billsLabel`, `budgetLabel`, `ccUsageLabel`, `estimatedCcBillLabel`,
  `savingsBalanceLabel`, `savingsTransferLabel`, `savingsDeltaLabel`,
  `estimatedSalaryLabel` — all `formatKr(x)` / `formatSignedKr(x)`. Pure
  presentation; raw numbers carry truth.

### Recurring vs one-off detection (FE heuristic)
- Per
  [client/src/components/bills/BillsDashboard.tsx:46-49](../client/src/components/bills/BillsDashboard.tsx#L46-L49):
  a PS event is "recurring" if `Number(event.date.slice(8, 10)) === event.day`,
  else "one-off". This is a UI heuristic for the edit dialog — not a
  authoritative classification. PS's authoritative `repeat_type` field is on
  the event payload but the dashboard does not display it.
