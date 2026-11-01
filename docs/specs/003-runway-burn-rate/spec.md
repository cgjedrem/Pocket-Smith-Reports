# Feature Specification: Runway & Burn Rate

**Feature Branch**: Existing app-managed dedicated branch (unchanged)

**Feature Directory**: `docs/specs/003-runway-burn-rate`

**Created**: 2026-10-31

**Status**: Draft — specification quality reviewed; not implementation approval

**Input**: User description: "we have 3 features we can implement, correct? runway, debt interest rate register - debd vs assets and lifestyle creep let's swap a child session for eahc with coordinator agent copilot fusion max to do a speckit and dev loop on those 3 features on autopilot mode. let them create a branch for each features no questions asked execte until completed. I am off to concert"

**Scope of this specification**: Runway & Burn Rate only. Debt/assets and lifestyle creep are separate features. This pass defines requirements and their quality checklist only.

## User Scenarios & Testing *(mandatory)*

All examples below are synthetic. Monetary examples use one household currency.

### User Story 1 - Understand selected reserves against recent spending (Priority: P1)

As a household user, I want to see how many months my selected liquid reserves represent at my recent recorded spending rate, for each account owner and the household, so I can understand the relationship between those two observations without treating it as a prediction.

**Why this priority**: This is the core value: a reproducible current reserve-to-spending comparison, with the meaning of "burn" made explicit.

**Independent Test**: Supply three valid completed months and an explicit reserve selection; open Bills and independently reproduce the owner and household figures from the displayed observations.

**Acceptance Scenarios**:

1. **Given** an as-of date in October 2026, Partner A's July/August/September spending of 20,000 / 30,000 / 40,000 and selected reserves of 90,000, **When** the user opens Runway in Bills, **Then** average monthly recorded spending is 30,000, runway is 3.0 months, and July, August, and September 2026 are named as the three included months.
2. **Given** the same months, Partner B's spending of 50,000 / 60,000 / 70,000 and selected reserves of 30,000, **When** household results are shown, **Then** household monthly spending is 70,000 / 90,000 / 110,000, average spending is 90,000, selected reserves are 120,000, and runway is 1.3 months after display rounding, not the mean of the owners' ratios.
3. **Given** a month's records contain a checking purchase of -100, a card purchase of -200, positive refunds of +40 and +60, both legs of a card repayment, and savings, investment, internal-transfer, and excluded-account movements, **When** burn is calculated, **Then** recorded spending is 300; refunds do not reduce it and the excluded movements do not increase it. An identical repeated purchase record is counted once.
4. **Given** a shared bill paid from Partner A's account and any configured shared-expense split, **When** owner results are shown, **Then** the bill belongs entirely to Partner A's recorded spending, household totals include it once, and results say they are account-owner-based rather than a fair-share allocation. Changing display names or owner ordering does not change attribution.
5. **Given** the result is visible, **When** the user reads its explanation, **Then** it says "average monthly recorded spending (gross burn)" and explains that the ratio compares selected balances with past recorded spending, does not subtract income or net refunds, and is not a forecast, financial advice, or a recommendation.

---

### User Story 2 - Choose which liquid accounts count (Priority: P1)

As a household user, I want to explicitly choose my liquid reserve accounts and see what was included, so that the calculation does not mistake credit limits, investments, or an unrelated balance for available reserves.

**Why this priority**: A ratio without a deliberate, auditable reserve selection could misrepresent available money. Configuration is part of the minimum useful feature.

**Independent Test**: Begin without runway settings, choose eligible synthetic accounts in Bills, save, reload, and confirm that exactly those accounts contribute without changing any existing account bindings.

**Acceptance Scenarios**:

1. **Given** no runway selection has been saved, **When** the user opens the panel, **Then** it shows "Select liquid accounts", reserves and runway are unavailable rather than zero, and no accounts are automatically selected. Merely viewing the panel creates no settings.
2. **Given** eligible owned checking and savings accounts, **When** the user selects and explicitly saves a unique set, **Then** the saved selection survives reload, the panel updates from that selection without a sync, and selected account names and owners are visible. Other account bindings and settings are unchanged.
3. **Given** a request containing duplicate, unknown, unowned, excluded, credit-card, investment, or otherwise ineligible account identifiers, **When** the selection is submitted, **Then** it is rejected with an actionable explanation and the previously saved selection remains intact.
4. **Given** a previously selected account is removed, excluded, or loses its ownership or balance, **When** results are refreshed, **Then** the affected owner and household reserve result is unavailable with the affected selection identified; the account is not silently dropped or treated as zero.
5. **Given** selected balances of 10,000 and -2,000, **When** reserves are calculated, **Then** their signed total is 8,000. **Given** the selected total is zero or negative, **When** runway is displayed, **Then** the observed total remains available but the ratio is undefined with a nonpositive-reserves reason.
6. **Given** only Partner A has selected reserve accounts but spending for both owners is valid, **When** results are shown, **Then** Partner B's reserve figure and ratio are unavailable with "No selected reserve accounts", while the household ratio compares the explicitly selected household reserves against both owners' combined spending. The panel identifies the selection scope; it does not invent a zero balance for Partner B or claim to include every household asset.
7. **Given** an existing selection, **When** the user saves an empty selection, **Then** runway returns to "Select liquid accounts" rather than displaying a zero-month ratio.

---

### User Story 3 - Judge the coverage and age of the evidence (Priority: P1)

As a household user, I want to see which months, accounts, and source dates underpin a result, and why a result is qualified or unavailable, so I do not confuse missing, partial, or old data with current certainty.

**Why this priority**: A precise-looking ratio from incomplete or invalid financial data is worse than an explicit limitation. These safeguards are part of the core calculation.

**Independent Test**: Use synthetic missing, incomplete, invalid, stale, and undated sources; verify the exact month set and the stated reason or qualification for every result.

**Acceptance Scenarios**:

1. **Given** October 2026 as the as-of month and valid July and September observations but no August source, **When** results are calculated, **Then** both owners and the household use July and September only, divide by two, and show August as missing. June is not substituted. With only one usable month, averages and ratios are unavailable with an insufficient-history reason.
2. **Given** July's source is known to cover only part of July or to have been collected before July ended, **When** the October result is calculated, **Then** July is excluded for everyone and its reason is visible. Current October and future months never become observations.
3. **Given** two or more structurally valid completed-month sources whose collection or coverage evidence is absent, **When** their recorded transactions are used, **Then** the result is qualified with "Month coverage unverified — recorded transactions only", the affected months are named, and no claim of full-month completeness is made. An undated empty source is not accepted as a proven zero-spending month.
4. **Given** a source has an invalid date or amount, an out-of-month transaction, a conflicting duplicate transaction identity, or spending that cannot be assigned to an owner, **When** observations are assessed, **Then** that month is excluded for all owners with an explicit invalid-source reason; individual problematic records are not silently omitted to manufacture a usable month.
5. **Given** known source or balance dates older than 24 hours, or unknown dates, **When** a valid ratio is shown, **Then** stale or unknown-date qualifications remain beside it, the available dates are shown separately from the calculation time, and recalculating does not make the underlying data appear fresh.
6. **Given** fewer than two usable months, a missing selected balance, nonpositive burn, nonpositive reserves, invalid settings, or known incompatible currencies, **When** the panel is shown, **Then** each affected ratio is undefined (`null`), a human-readable reason is visible, and no infinity, invalid number, or fabricated zero-month ratio appears. Valid zero or negative observations remain distinguishable from missing values.
7. **Given** all relevant amounts have an established common currency, **When** the result is shown, **Then** that currency is identified. Missing currency evidence produces a visible single-currency-assumption qualification; known currency conflicts prevent the affected aggregation rather than being converted or summed.
8. **Given** the local calendar rolls from October to November 2026 and a new result is requested, **When** the panel refreshes, **Then** the candidate window becomes August–October 2026. Changing the Bills past/future display window does not change it, and no historical runway is inferred from today's balances.

---

### User Story 4 - Use the panel without disrupting Bills (Priority: P2)

As a household user, I want a small, understandable Runway panel and settings in Bills that recover from failures independently, so I can use existing Bills information even when runway is unavailable.

**Why this priority**: Integration must preserve the existing workflow rather than turning an optional summary into a reason the rest of Bills fails.

**Independent Test**: Exercise loading, unavailable, result-load failure, settings-load failure, save failure, retry, and delayed responses with synthetic sources and older Bills snapshots.

**Acceptance Scenarios**:

1. **Given** a result is loading or a read fails, **When** the user views Bills, **Then** Runway shows an explicit loading or error/retry state without a misleading zero or example result; existing Bills content remains usable. Missing the current Bills snapshot does not by itself prevent showing runway derived from sufficient local historical sources and selected balances.
2. **Given** settings could not be loaded, **When** the user opens runway settings, **Then** saving is disabled until a successful settings load; an apparent empty default cannot overwrite an unknown saved selection.
3. **Given** a selection change whose save fails, **When** the error is shown, **Then** unsaved choices remain available for correction or retry, the saved configuration is not represented as changed, and any retained result remains labelled as using the saved selection. A successful save refreshes only the runway result.
4. **Given** overlapping result requests before and after a saved selection change, **When** the older response arrives last, **Then** it does not overwrite the newer selection's result or remove its warnings.
5. **Given** older Bills snapshots without runway fields or absent optional source dates, **When** the page is opened, **Then** existing Bills figures remain usable, absent runway inputs are handled explicitly, and no snapshot regeneration or automatic synchronization is required merely to open the panel.
6. **Given** keyboard-only or assistive-technology use, **When** the user opens settings, selects accounts, saves, or retries, **Then** controls are labelled and keyboard-operable, and loading, errors, and unavailable reasons are distinguishable without relying on color.
7. **Given** PocketSmith is unreachable and usable local sources already exist, **When** the user opens, refreshes, or configures Runway, **Then** the feature needs no PocketSmith connection, changes no source financial records, and creates no scheduled work. Sensitive result and settings responses are not retained in reusable browser or shared response caches.

---

### User Story 5 - Hide money without hiding the comparison (Priority: P2)

As a household user sharing the screen, I want existing hide-amounts behavior to cover every monetary value introduced by Runway while keeping its nonmonetary context readable.

**Why this priority**: The new panel must not undermine the application's existing presentation privacy control.

**Independent Test**: Toggle hide-amounts on a populated synthetic panel, inspect visible and assistive text and tooltips, then restore visibility without changing the selection.

**Acceptance Scenarios**:

1. **Given** amounts are hidden, **When** reserves, averages, monthly spending, and any individual account balances are displayed or described, **Then** each amount is masked as `****`, including zero and negative values, signs, titles, tooltips, and accessible descriptions. Warnings and errors do not reveal raw monetary values.
2. **Given** a 3.0-month runway and a three-month observation window, **When** amounts are hidden, **Then** 3.0 months, month names, dates, owner/account labels, and account counts remain visible.
3. **Given** saved or unsaved account choices, **When** masking is toggled either way, **Then** the change takes effect without a reload or refetch, does not reset those choices, and restores the same monetary values when unhidden.

### Edge Cases

- **EC-01 — Calendar boundaries**: In January, the prior three completed months belong to the preceding year. February length and leap days affect date validation, not the three-month count. The calculation uses the application's local calendar consistently.
- **EC-02 — Genuine zero versus absence**: A valid, demonstrably complete month with no eligible purchases contributes zero. A missing, unreadable, known partial, or undated empty source is not proof of zero spending. A positive observed month with unknown completeness can only support a qualified recorded-spending result.
- **EC-03 — Transfer exclusions**: Either a transaction transfer flag or a category transfer flag is sufficient to exclude the movement. Savings-category overrides apply even when no transfer flag is set. Savings, investment, and excluded category roles and known card repayments are excluded independently. A transfer flag of JSON `null` is treated as not a transfer (as in `v4_pipeline/accounting.py`; real PocketSmith transactions carry it often), while any other non-null non-boolean flag still invalidates the month.
- **EC-04 — Uncategorised purchases and refunds**: A valid negative posted purchase on an eligible owned checking/card account remains eligible when uncategorised unless another exclusion applies. Positive credits/refunds, pending transactions, and future-dated purchases never contribute. No refund pairing is added.
- **EC-05 — Identity and duplication**: Identical records with the same transaction identity count once; conflicting copies invalidate the month. Two genuinely different identities with equal amounts are not deduplicated by amount or payee. Missing required transaction/account identities or ambiguous ownership invalidate the affected observation.
- **EC-06 — Selection changes**: Exclusion, account-type changes, deletion, or invalid reassignment of a selected account must be visible, not silently repaired. A valid reassignment updates owner attribution on the next calculation and remains visible in the account list.
- **EC-07 — Invalid money**: Missing values, booleans, malformed numbers, and non-finite amounts are not money and must not become zero. Signed valid balances may offset one another, but a nonpositive selected total has no runway ratio.
- **EC-08 — Currency and collection differences**: Known incompatible currencies cannot be summed. Unknown currency, unknown dates, and sources collected at different times remain explicit qualifications; the result does not imply a single synchronized balance-and-history snapshot. Detectably conflicting or changing inputs make the affected calculation unavailable until a stable retry.
- **EC-09 — Owner versus household availability**: All spending averages use the same included months. One owner's unavailable reserves do not erase the other's valid result, but a missing/invalid balance on any selected account blocks the household numerator. Having no selected account for an owner is not the same as a selected account with a missing balance.
- **EC-10 — Very small positive values**: Determine availability before display rounding. A positive ratio that would round to 0.0 is shown as "<0.1 months", not zero; rounding never turns a positive burn into a nonpositive-burn status.
- **EC-11 — Legacy and concurrent data**: An old snapshot's zero, changed past/current flag, or projected balance is not evidence of complete recorded spending or historical selected reserves. Loading failures and delayed responses never substitute mock figures or old settings as if they were current.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a Runway & Burn Rate panel in Bills showing account-owner and household results, selected reserve accounts, the spending basis, and expandable account-selection settings.
- **FR-002**: The metric MUST be described as "average monthly recorded spending (gross burn)". Runway MUST mean selected liquid reserves divided by that average, not net cash loss, income-adjusted burn, everyday spending allowance, or a prediction of a depletion date.
- **FR-003**: Each calculation MUST use the previous three completed local calendar months relative to its calculation date, independently of the Bills display window. It MUST show the as-of month, all three candidate months, the exact included months, their count, and every excluded month with its reason. It MUST NOT substitute older, current, or future months.
- **FR-004**: A spending average MUST require at least two usable monthly observations. All owners and household results MUST use one common included month set: a month unusable for any in-scope owner's spending is excluded for all. The arithmetic mean MUST divide by the number of included months, without imputing missing months as zero.
- **FR-005**: A usable monthly observation MUST contain valid locally recorded transactions with identities, dates, amounts, posting state, and assignable account ownership sufficient to apply the expense rules. Missing, malformed, known partial, or known pre-month-end sources MUST be excluded with reasons. Unknown collection or coverage evidence MAY support a qualified recorded-spending observation, never a claim of complete coverage. A zero-spending observation MUST have evidence of completed-period coverage.
- **FR-006**: Monthly gross spending MUST sum the absolute values of eligible negative posted transactions on mapped, non-excluded checking and credit-card accounts. Positive credits and refunds MUST NOT offset that sum. Pending transactions, salary/income totals, planned bills or purchases, forecasts, and projected savings MUST NOT supply the spending denominator.
- **FR-007**: Spending MUST exclude movements flagged as transfers at either transaction or category level; accounts or categories excluded from reporting; savings and investment category roles; configured savings-category overrides; and all identified credit-card repayment movements, including both repayment legs. Transactions on savings or investment accounts MUST NOT become consumption spending. An uncategorised eligible purchase MUST still count.
- **FR-008**: Transactions MUST be counted once by stable transaction identity. Identical repeats MUST be deduplicated, while conflicting repeats, invalid or out-of-month dates, invalid monetary values, missing required identities, or unassignable non-excluded spending MUST invalidate the affected month rather than being silently omitted. Distinct transactions MUST NOT be merged solely because their amounts match.
- **FR-009**: Liquid reserves MUST come only from a user's explicit unique selection of currently mapped, owned, non-excluded checking or savings accounts with usable recorded balances. Credit cards, credit limits, investments, excluded, unbound, and missing accounts MUST NOT be selectable as reserves.
- **FR-010**: Runway selection MUST be independent of existing account bindings and other feature settings. Absent or intentionally empty selection MUST mean "Select liquid accounts"; it MUST NOT auto-select accounts, fabricate zero reserves, or create settings merely through viewing.
- **FR-011**: Every submitted selection MUST be validated as a whole, including identifiers, uniqueness, eligibility, and supported settings. Invalid or failed changes MUST leave the previous saved selection intact. Users MUST explicitly save changes; successful saves MUST persist and refresh the runway result without initiating synchronization.
- **FR-012**: Selected reserves MUST be the signed sum of recorded balances of exactly the selected accounts. Missing, malformed, boolean, or non-finite selected balances MUST make the affected owner and household reserve totals unavailable, not reduce the selected set or become zero. Selected accounts that become ineligible MUST remain visible as an invalid selection until corrected.
- **FR-013**: Spending and selected balances MUST be attributed by stable configured account-owner identity, using configured display labels without deriving logic from names or ordering. Shared-expense split percentages MUST NOT affect attribution. Owner results MUST be labelled account-owner-based.
- **FR-014**: Household spending MUST be the sum of all in-scope owners' eligible spending for each common month, and household reserves the sum of unique selected eligible balances. Household runway MUST divide those household reserves by the household average spending, never average owner ratios. The display MUST identify selected-reserve scope and MUST NOT describe an incomplete ownership-mapped spending subset as the full household.
- **FR-015**: An owner with no selected reserve accounts MUST have unavailable reserves and runway with a no-selection reason; that absence MUST NOT be represented as an observed zero balance. A household with a nonempty valid selection MAY still compare that explicitly selected reserve total with complete in-scope household spending, including owners without selected reserves.
- **FR-016**: Each result MUST distinguish available, qualified, and unavailable states. An otherwise valid ratio with any excluded candidate month, stale/unknown dates, unverified coverage, or unverified currency MUST be qualified; an available ratio has none of these limitations. Undefined ratios MUST be `null` with stable reason labels for missing selection, insufficient history, invalid settings/source/selection, missing balance, currency conflict, nonpositive reserves, or nonpositive burn. All applicable limitations MUST be available to the user; genuine zero or negative source observations MUST remain distinguishable from missing values. No undefined ratio may appear as zero, infinity, or an invalid number.
- **FR-017**: A result MUST expose its calculation time, available source-collection dates, available balance dates, included/excluded observations, and selection scope. A known collection or balance date older than 24 hours MUST be marked stale; missing dates or coverage evidence MUST be marked unknown/unverified. Different source dates MUST NOT be represented as one verified synchronized generation. Stale or unknown data MUST qualify otherwise valid results rather than silently becoming fresh on recalculation.
- **FR-018**: A result MUST use one currency basis. Known incompatible currencies MUST prevent the affected aggregation. Missing currency evidence MUST produce an explicit "Single-currency assumption; currency unverified" qualification. No exchange-rate conversion or implied cross-currency comparability is included.
- **FR-019**: The visible history MUST consist only of the monthly spending observations supporting the average. Current selected balances MUST NOT be shown as historical balances or used to manufacture historical runway, and projected savings balances MUST NOT supply reserves.
- **FR-020**: Opening, refreshing, retrying, or configuring Runway MUST use already available local financial sources without contacting PocketSmith, initiating sync, scheduling work, requesting additional account-access permissions, or changing financial records. Only explicit selection saves may change runway settings.
- **FR-021**: Existing Bills snapshots and other report contracts MUST remain usable without runway data or regeneration for this feature. Missing optional runway information MUST have explicit absence behavior; legacy fallback zeros, mock examples, forecast fields, or snapshot age flags MUST NOT be treated as proof of valid spending or reserve data.
- **FR-022**: The panel MUST distinguish loading, unavailable, qualified, and error/retry states without blocking otherwise available Bills content. A missing current Bills snapshot alone MUST NOT prevent a result when its own required local sources are usable. A failed settings load MUST disable Save until recovery; a failed save MUST retain unsaved choices and clearly distinguish them from the saved selection.
- **FR-023**: A delayed result for superseded settings MUST NOT replace the latest result. Detectably inconsistent or changing sources MUST cause explicit unavailability/retry rather than a silently mixed result. Controls, status messages, and recovery actions MUST be labelled, keyboard-operable, and understandable without color alone.
- **FR-024**: Existing hide-amounts behavior MUST mask every monetary presentation introduced by this feature as `****`, including signs, zeros, reserves, averages, observations, individual balances, tooltip/title attributes, and accessible descriptions. Warning and error text MUST NOT leak raw amounts. Runway months, dates, window length, account counts, and labels MUST remain visible.
- **FR-025**: Privacy toggling MUST apply without reload, refetch, or lost saved/unsaved selection and MUST restore the same values when unhidden. Runway results and sensitive settings responses MUST follow the application's no-store privacy policy; masking remains a presentation aid, not access control.
- **FR-026**: Monetary displays MUST follow the application's existing household-currency formatting. Because the shared Reports calculation sums monthly amounts in binary floats, each monthly household and owner spending value MUST be rounded to cents (half up) to remove float noise; with the common-economy split, owner A is rounded and owner B is the household remainder so owners sum exactly to household. Averages and ratios MUST be calculated from those monthly values without further intermediate rounding; ratios MUST be rounded to the nearest tenth of a month, with halfway values rounded up, except positive values below 0.05 months MUST display "<0.1 months". Availability MUST be determined before display rounding.
- **FR-027**: The panel MUST explain that balances and gross recorded spending are descriptive observations, may be stale or incomplete as disclosed, ignore future income and changes in spending, and do not establish a safe spending level or guaranteed duration. It MUST NOT give investment, debt-management, financial-independence, or lifestyle recommendations.

- **FR-028** *(SC-split / RD-002, user-directed, 2026-11-01; supersedes FR-002 wording, FR-006, FR-007 amount rules, FR-013 split clause, FR-014 sum rule)*: Monthly spending MUST be computed by the same production accounting as the Reports page. Household monthly spending equals the Reports `household_totals.total` for that month: net paid minus received over home, common, personal and trips sections. Refunds reduce burn. Transfers, card repayments, savings and excluded sections follow Reports routing. A transfer flag on a category catalog parent MUST NOT drop its children's spending (RD-002). Runway MUST NOT keep a separate amount classifier. Monthly values and averages are signed; an average ≤ 0 makes the ratio unavailable with `nonpositive_burn`. The metric is described as household net spending (`basis: "household_net_spending"`, `calculation_version: 2`).
- **FR-029** *(SC-split, 2026-11-01)*: When the common-economy split is enabled and both split slots map to configured owners, owner monthly spending MUST equal that owner's Reports net minus their split delta. That is the fair share of split categories plus their own net on non-split categories, and owners sum to household. Otherwise owner spending is net by paying account owner. The response MUST expose `owner_attribution` (`common_economy_split | payer`) and `split_shares`.
- **FR-030** *(2026-11-01)*: A Reports accounting error for one candidate month (for example an unmapped category or an unowned account) MUST exclude only that month with `invalid_source` and MUST NOT surface as a server error or leak source text. An invalid shared accounting configuration (section mapping, roles, catalog, split) makes classification unusable for every month (global `invalid_source`). Runway MUST evaluate the stable source snapshot, never re-read live files.

### Key Entities *(include if feature involves data)*

- **Runway selection**: The explicitly saved set of unique liquid account identities; independent of account bindings. Missing/empty, valid, and invalid selections are distinguishable.
- **Account owner**: An existing configured household participant with a stable identity and display label. Owns recorded spending and selected reserve accounts; is not a shared-expense allocation.
- **Selected reserve account**: Account identity, name, owner, eligibility, signed recorded balance, currency evidence, and any balance/source dates. Selection does not establish current liquidity beyond the user's choice and the available data.
- **Monthly spending observation**: A completed calendar month, each owner's gross eligible spending, household total, usability, coverage/collection evidence, and exclusion or qualification reasons.
- **Runway result**: Calculation time/as-of month, fixed candidate window, common included months, selected-reserve scope, owner and household reserves/averages/nullable ratios, currency basis, status, and all source limitations.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every synthetic arithmetic example in US1–US3, displayed money matches independently computed totals to the displayed currency precision, and runway matches the specified one-decimal rounding. Household results never use a mean of owner ratios or split allocations.
- **SC-002**: In every three-, two-, one-, and zero-usable-month scenario, users can identify all three candidate months and the inclusion or exclusion of each from the panel; no current/future or silently substituted month contributes.
- **SC-003**: Every specified missing, invalid, incomplete, zero, negative, stale, unknown-date, and currency-conflict scenario yields its stated status and reason/qualification. There are zero fabricated zero balances, zero misleading zero-month ratios, and zero unqualified completeness claims for unknown coverage.
- **SC-004**: A user with a synthetic household of up to ten eligible accounts can open settings, select accounts, save, and identify the resulting reserve scope within two minutes, without leaving Bills or performing a sync.
- **SC-005**: With the previous three months containing up to 10,000 synthetic transactions total and up to 20 mapped accounts, opening or refreshing the panel presents a result or explicit unavailable state within two seconds under the recorded local acceptance environment. Loading is visible while waiting; no PocketSmith connection is needed.
- **SC-006**: In every save-failure, settings-load-failure, retry, and out-of-order-response scenario, saved selections are not lost or misrepresented and older responses never replace the latest result. Existing Bills content remains usable in every runway-only failure scenario.
- **SC-007**: With hide-amounts active, inspection of every new monetary presentation surface finds zero exposed amounts or signs, including tooltips and accessible descriptions. All runway ratios and nonmonetary context remain readable; toggling takes effect within one second with zero refetches or lost selections.
- **SC-008**: From the panel alone, a user can correctly identify all five of these facts in the synthetic user acceptance exercise: (1) selected accounts, (2) included months, (3) gross rather than net spending, (4) a reserve-to-spending ratio rather than a guaranteed duration, and (5) no financial-advice claim.

## Assumptions

- **A-001 — Audience and currency**: This feature serves the existing local household and its configured owners. A single household currency is the bounded first-version assumption, not a verified property of every source. Known conflicts fail; missing evidence is visibly qualified. Foreign-exchange support is out of scope.
- **A-002 — Coverage honesty**: Local raw history may lack reliable collection/completeness evidence. For this descriptive metric only, structurally valid positive recorded spending with unknown coverage can support a qualified result; known partial/invalid months and unproven zero-spending months cannot. A complete-period spending claim is not authorized by a filename, an old snapshot, or recalculation alone. No source-capture redesign or backfill is included.
- **A-003 — Meaning of reserves**: The user decides which eligible checking/savings balances count as liquid. Selected reserves are not net worth, all household wealth, a bank guarantee of immediate availability, or a debt-adjusted balance. An unselected owner's assets remain outside the reserve scope, not an inferred zero.
- **A-004 — Ownership and categories**: Existing account ownership, exclusions, transfer indicators, category roles, savings overrides, and identified repayment categories are the classification authorities. This feature does not guess unmarked transfers from payees, allocate shared expenses, or repair mappings. Undetected upstream misclassification can affect recorded spending; that limitation belongs in the explanation.
- **A-005 — Source freshness**: Recalculation is on demand, not scheduled monitoring. Available collection and balance dates may differ or be unknown; neither the current calendar nor calculation time is evidence that the bank balance is current. No historical runway, dated reserve reconstruction, new timestamp collection system, or alerting is included.
- **A-006 — Existing behavior**: The existing Bills workflow, household labels/currency formatting, privacy toggle, and local configuration behavior remain the surrounding product conventions. Runway is additive and independent of projected savings, everyday-budget calculations, debt/assets, lifestyle creep, report exports, and report-generation behavior.
- **A-007 — Delivery boundary**: No new external integration, permission scope, scheduler, dependency, or infrastructure is required by this specification. No production code, test implementation/execution, plan, branch mutation, commit, push, or pull request is authorized by this specification-writing pass.
- **A-008 — Verification boundary**: Scenarios are requirements, not evidence that the feature exists or passes. Later verification must use deterministic synthetic data and keep static review, build, automated checks, runtime integration, and user acceptance distinct. Mandatory downstream review gates remain in force.
- **A-009 — Net household basis (SC-split / RD-002, 2026-11-01)**: The user directed that runway follow the Reports page and the common-economy split. Mortgage payments, including principal, count as burn because Reports count them under home. Partial or in-progress months are shown as-is, with the existing coverage qualifications; no extrapolation. Pending transactions are treated exactly as Reports treat them. The single-currency assumption is unchanged; runway still checks per-transaction currency evidence.
