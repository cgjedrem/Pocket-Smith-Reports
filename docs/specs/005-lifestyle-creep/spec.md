# Feature Specification: Lifestyle creep detector

**Feature Branch**: existing app-managed worktree branch (unchanged)

**Created**: 2026-10-31

**Status**: Draft

**Input**: User description (scope summary): Detect sustained monthly category spending growth on Bills using reliable completed-month history, with configurable sensitivity and existing amount privacy.

**Current correction (2026-11-02)**: The final one-target/reference-period clarification supersedes both the original fixed five-month calculation and the later multi-month evaluation-period amendment. Earlier acceptance examples are historical.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Understand sustained category spending growth (Priority: P1)

As a household member reviewing Bills, I want to see which of each partner's credit-card spending categories have remained elevated, so I can distinguish a sustained change from a single high month without interpreting it as financial advice.

**Why this priority**: This is the feature's primary value: an explainable description of observed category spending, not a forecast or a recommendation.

**Independent Test**: Supply five complete, comparable synthetic monthly records for Partner A and open Bills for the following month. Verify the category result and its explanation against the calculation examples below without needing another Bills display mode.

**Acceptance Scenarios**:

1. **Given** Partner A has category spending of `[100, 100, 100, 130, 140]` in May–September 2026, **When** October 2026 is viewed at the default threshold, **Then** the category is flagged, August is compared with May–July, and September is compared with June–August. The latest baseline is 110, latest spend is 140, latest monetary increase is 30, rolling growth is approximately 30% and 27.27%, and ordinary September-versus-August growth is approximately 7.69%.
2. **Given** spending is `[100, 100, 100, 130, 131]`, **When** evaluated at 20%, **Then** no sustained-growth alert appears because the second rolling comparison is approximately 19.09%, even though the last two months both exceed the initial baseline by more than 20%.
3. **Given** spending is `[100, 100, 100, 150, 150]`, **When** evaluated at 20%, **Then** sustained growth is flagged even though ordinary last-month growth is 0%; sustained elevation does not require acceleration.
4. **Given** a category has one isolated spike or insufficient recurring baseline evidence, **When** evaluated, **Then** it is not flagged and any suppression is explained without claiming to recognize an annual bill or a particular one-off transaction.
5. **Given** the same source category ID has a new title, or two different source IDs share a title, **When** history is compared, **Then** a rename remains one series, different IDs remain separate, and the latest available labels identify the results. Partner histories never combine.

---

### User Story 2 - Know when history cannot support a conclusion (Priority: P1)

As a household member, I want incomplete or incomparable history to be clearly distinguished from zero spending and from a genuine no-alert result, so I am not reassured by missing evidence.

**Why this priority**: A false negative or a false increase caused by missing history, changed identities, or changed spending scope would undermine the report.

**Independent Test**: Open the detector against synthetic records with each availability condition below. Verify that affected months, partners, reasons, and the existing re-sync route are visible without computing an incomplete partner's category verdicts.

**Acceptance Scenarios**:

1. **Given** only four of the five required months are complete, or an interior month is missing, **When** the detector is opened, **Then** it reports insufficient history and identifies the missing month; it neither shortens the baseline nor substitutes an older month.
2. **Given** a required record was created while its source month was still open, **When** the calendar later rolls over, **Then** that record remains partial until a successful full-month re-sync replaces it.
3. **Given** a month contains only legacy title-keyed category totals, lacks a stable partner identity, or lacks reliable completion information, **When** evaluated, **Then** the affected partner requires re-sync; titles, partner positions, existing total-spend values, and absent aggregates are not used to invent IDs or zeros.
4. **Given** all five months were completely observed for a partner with eligible credit-card accounts and one category has no qualifying spending in one month, **When** evaluated, **Then** that category's spend for that month is zero. **Given** the month's history is unavailable instead, **Then** its spending remains unknown.
5. **Given** included accounts, ownership, exclusions, or spending-relevant category roles changed between required records, **When** evaluated, **Then** the affected partner requires a consistent five-month re-sync (the range to run is described in A-012). A display-only partner, account, or category rename does not trigger this requirement.
6. **Given** Partner A is ready and Partner B has incomplete history, **When** the detector is opened, **Then** Partner A's result remains available, Partner B has no category verdicts, and the overall result explicitly says coverage is partial.
7. **Given** saved history is unreadable or structurally corrupt, **When** loading fails, **Then** the detector shows an error and Retry rather than a no-alert verdict. Retry evaluates the same requested window without starting a sync.
8. **Given** re-sync has successfully replaced all five required records with complete, comparable history, **When** the user retries the detector, **Then** availability and results reflect those records, not a previous insufficient-history result.
9. **Given** existing Bills views use title-keyed category totals, **When** sync adds complete stable-ID history, **Then** those totals and existing category displays are unchanged, while the detector can use the new evidence. Older records still open in existing Bills views but do not become eligible detector history.
10. **Given** the source transaction fetch fails during sync, **When** that sync ends, **Then** no new monthly record is published and previously partial or unavailable history is not promoted to complete.

---

### User Story 3 - Adjust detection sensitivity without changing the rule (Priority: P2)

As a household member, I want to adjust the percentage threshold for this Bills visit, so I can review the same history at a sensitivity I choose without creating a new saved preference.

**Why this priority**: A visible, bounded threshold makes the report interpretable while keeping the first version small.

**Independent Test**: Use the same complete synthetic history at 20% and 30%, then exercise threshold boundaries and invalid values. Verify that only the threshold changes, not the five-month window, three-month baseline, or two-month sustained requirement.

**Acceptance Scenarios**:

1. **Given** no threshold has been supplied, **When** the detector is opened, **Then** it uses and displays 20%.
2. **Given** `[100, 100, 100, 130, 140]` is flagged at 20%, **When** the user applies 30%, **Then** it is not flagged; equality with the threshold is not sufficient.
3. **Given** a finite numeric threshold from 1% through 100%, inclusive, including a decimal such as 20.5%, **When** applied, **Then** the result identifies that threshold and both rolling comparisons use it without rounding before the decision.
4. **Given** an explicitly empty, nonnumeric, boolean, non-finite, or out-of-range threshold, **When** submitted, **Then** the value is rejected with a clear validation message, not silently clamped or replaced. An earlier result must not appear to use the rejected value.
5. **Given** a valid threshold has been applied, **When** the user changes the viewing month during this Bills visit, **Then** that threshold remains selected. **When** Bills is opened afresh or fully reloaded, **Then** the default is 20%; no durable preference is created.

---

### User Story 4 - Review results safely within Bills (Priority: P2)

As a household member, I want the detector to be available regardless of the Bills visualization or display window, and to honor my amount-visibility choice everywhere it presents money.

**Why this priority**: The report must remain usable alongside existing Bills views without exposing hidden amounts.

**Independent Test**: Exercise loading, error, insufficient, partial, ready/no-alert, and ready/alert examples on Bills; change visualization, display window, and amount visibility while keeping the selected viewing month fixed.

**Acceptance Scenarios**:

1. **Given** Bills is opened without a historical month selection, **When** the current month is October 2026, **Then** the detector analyzes May–September 2026 and excludes October spending.
2. **Given** the viewing month and threshold stay fixed, **When** Grid, Graph, or Table is selected or the Bills past/future display window changes, **Then** the detector remains available with the same five-month analysis and does not reload because of those controls.
3. **Given** amounts are hidden globally, **When** any detector state or comparison detail is displayed, **Then** spending, averages, monetary differences, and uncategorized totals—including zeros and signed amounts—are masked in visible text, tooltips, accessible labels, and hidden explanatory text. Percentages, months, counts, identities, and status remain visible.
4. **Given** the detector already has a result, **When** amount visibility is toggled, **Then** presentation updates without another history request.
5. **Given** complete comparable history has no qualifying alerts, **When** displayed, **Then** the detector says no sustained category growth was detected in the covered credit-card spending. It does not claim that all household spending was assessed.
6. **Given** an evaluation is loading, fails, or changes because of a new viewing month or threshold, **When** the user reviews the detector, **Then** loading and errors are explicit, Retry is available for errors, and an older response cannot be presented as the newly selected analysis.
7. **Given** a category is flagged, **When** its explanation is read, **Then** it describes recorded spending and the comparison rule, not what the user should spend, save, borrow, or change.
8. **Given** a valid viewing month and threshold, **When** the detector is opened or retried, **Then** it attempts only that window's five exact saved monthly snapshots, no more than once each, without scanning other history, reading raw transactions, contacting an external service, saving results, or starting sync. Invalid selections cause no history reads.
9. **Given** the user operates Bills by keyboard, **When** changing the threshold, opening comparison details, following re-sync guidance, or activating Retry, **Then** each available control is clearly labelled and keyboard-operable.

### Edge Cases

All amounts below are deterministic synthetic spending units. Bracketed amounts are ordered from the oldest to the newest of five consecutive completed months. The default threshold is 20% unless stated otherwise; decisions use unrounded values.

| Case | Expected result |
| --- | --- |
| `[100, 100, 100, 130, 140]` | Sustained growth: 30% and approximately 27.27%; latest month-over-month approximately 7.69%. |
| `[100, 100, 100, 130, 131]` | No sustained growth; second baseline is 110, not 100. |
| `[100, 100, 100, 120, 150]` | No sustained growth; first comparison equals 20%. |
| `[100, 100, 100, 130, 132]` | No sustained growth; second comparison equals 20%. |
| `[100, 100, 100, 130, 132.001]` | Sustained growth even if the second percentage displays as 20.00%; display rounding does not decide the flag. |
| `[100, 100, 100, 150, 150]` | Sustained growth despite 0% ordinary last-month growth. |
| `[100, 100, 100, 160, 100]` | Isolated spike; no sustained growth. |
| `[100, 100, 100, 90, 80]` | No sustained growth; negative percentages and monetary differences remain meaningful. |
| `[0, 100, 100, 130, 150]` | Eligible baseline with two positive months; sustained growth. |
| `[0, 0, 100, 200, 300]` | Suppressed for low-frequency baseline evidence, despite two above-threshold comparisons. |
| `[0, 0, 0, 100, 200]` | Suppressed for zero baseline; first rolling percentage absent, never infinity. |
| `[100, 100, 100, 0, 150]` | No sustained growth; ordinary latest month-over-month percentage absent because the previous month is zero. |
| Five observed zero-spend months with eligible accounts | Ready history, no alert; undefined percentages remain absent. |
| No eligible credit-card accounts for a partner | Unavailable history for that partner, not observed zero spending. |
| Four months, a gap, a legacy month, or an open-source partial month | Insufficient history for the affected partner; exact missing/affected month and re-sync need shown. |
| Category appears only in recent months or disappears after early months | Include its stable-ID series; absence means zero only within complete history. Apply the same sparse/zero rules. |
| Same ID renamed; same title on different IDs; deleted/recreated category | Rename continues the series; distinct source IDs never merge. Use the latest available label within the selected window. |
| Partner display name or position changes | Stable partner identity controls comparison; no joining by label or position. |
| Account, exclusion, or spending-relevant role population changes | Incomparable history for the affected partner until all five records share a comparable spending scope. Labels alone do not change scope. |
| Only uncategorized qualifying spending exists | Show separate uncategorized totals and the categorized-coverage limitation; do not create an uncategorized category alert. |
| A posted refund, pending charge, payment, transfer, excluded account, or exclude-role category | Does not enter the detector's spending population. Refunds are not netted against outgoing spending. |
| Viewing January 2027, when not in the future | Analyze August–December 2026; evaluate November and December. Calendar-year boundaries do not alter the rule. |
| Malformed/impossible/future viewing month, or a month without five representable predecessors | Reject the selection with validation feedback before history is read; do not substitute another month. |
| Corrupt record, invalid aggregate structure, duplicate identity, negative/non-finite spending amount, or read failure | Error with Retry; no misleading no-alert or partially computed verdict from invalid records. |
| Two identical evaluations of unchanged history | Same results and ordering; group partners by stable identity and categories by stable source ID, not changing labels. |

## Requirements *(mandatory)*

### Functional Requirements

#### Coverage and historical evidence

- **FR-001**: The detector MUST report monthly category spending growth separately for each partner's existing eligible credit-card spending. It MUST describe the coverage as credit-card-only, not a whole-household spending or financial-health assessment.
- **FR-002**: Each evaluation MUST use exactly the five contiguous completed calendar months immediately preceding its viewing month, oldest first. The viewing month defaults to the current calendar month under the application's existing calendar convention. Historical viewing months are supported. The current and future months MUST never contribute spending, and the Bills display window MUST NOT determine this history.
- **FR-003**: The viewing month MUST be validated before reading history: it must be a real `YYYY-MM` calendar month, no later than the current month, with five representable preceding months. Invalid input MUST receive clear validation feedback without a fallback month.
- **FR-004**: Spending MUST be the positive magnitude of posted outgoing transactions on the partner's non-excluded accounts mapped as credit cards. Pending transactions, refunds/credits, credit-card payments, transfers, and categories assigned an exclude role MUST be excluded using the existing Bills spend population. Refunds MUST NOT reduce this outgoing-spend measure.
- **FR-005**: Each historical series MUST use a stable partner ID and the original source category ID assigned to the transaction, without inferred IDs, joining by title or partner position, or parent-category rollups. Equal titles on different IDs and deleted/recreated categories MUST remain distinct. Results MUST use each identity's latest available display label in the selected five-month history; a label change alone MUST NOT break continuity.
- **FR-006**: Uncategorized qualifying spending MUST be retained and shown separately from identified categories for the five months. It MUST NOT be represented as a source category, assigned the sentinel ID `-1`, folded into another category, or used for category-growth alerts. Its presence MUST make the categorized-coverage limitation visible.
- **FR-007**: Sync MUST add reliable stable-ID category history to the monthly records while preserving the existing title-keyed category totals and their current Bills consumers unchanged. Existing records MUST remain readable by existing Bills views; legacy history is not automatically eligible for this detector.
- **FR-008**: Every new history record MUST explicitly distinguish complete, partial, and unavailable source coverage. Complete means the source month has closed, the full-month inputs were successfully obtained and validated, and eligible account scope is known. A record made from an open source month MUST remain partial after rollover until rebuilt from complete input. Time passing or a read-time calendar label MUST NOT promote it to complete. A failed transaction fetch MUST NOT publish a new monthly record.
- **FR-009**: Within complete, comparable history, an identified category absent from a month's qualifying spending MUST have observed spending of zero. A complete empty category set with eligible accounts is valid evidence of zero categorized spending. Missing or legacy history, unavailable input, a missing partner, and absence of eligible accounts MUST NOT be treated as zero.
- **FR-010**: Comparability MUST account for stable partner ownership, included account IDs, effective exclusions, spending-relevant category-role populations, and the definition of qualifying spending. All five monthly records for a partner MUST agree on this scope. Scope differences require a consistent re-sync, not a growth verdict. Display-only names or titles MUST NOT affect scope comparison.
- **FR-011**: A partner is ready only when all five required months contain valid, explicitly complete, comparable history with stable identities. Otherwise the detector MUST identify affected months and reasons and direct the user to the existing sync experience, without partial baselines, older-month substitution, invented identities, or zero-filling unknowns. Stable partners present in only some required months MUST remain visibly incomplete rather than being matched to someone else or silently dropped.

#### Calculation and explanation

- **FR-012**: For category spending `x0` through `x4` in months `m0` through `m4`, the first evaluated month MUST be `m3` with baseline `(x0 + x1 + x2) / 3`; the second MUST be `m4` with baseline `(x1 + x2 + x3) / 3`. Each baseline MUST contain exactly its own three preceding months, not its evaluated month.
- **FR-013**: For positive baseline `B` and evaluated spending `S`, monetary change MUST be `S - B` and growth percentage MUST be `100 × (S - B) / B`. A category MUST be flagged only when both evaluated months strictly exceed the selected percentage threshold and the recurring-evidence rule in FR-014 is satisfied. The sustained count MUST remain fixed at two; the second elevated month need not exceed the first. Decisions MUST precede display rounding.
- **FR-014**: A category MUST have positive spending in at least two of the initial three months (`m0`, `m1`, `m2`) to qualify for an alert. Otherwise it MUST be marked suppressed for low-frequency baseline evidence, unless zero-baseline suppression takes precedence. This is a statistical screen, not classification of annual or one-off transactions, and its conservative effect on newly established categories MUST be explained.
- **FR-015**: A zero rolling baseline MUST produce an absent percentage and no sustained-growth alert, never infinity. When both sparse and zero-baseline conditions apply, zero baseline MUST be the primary suppression reason. Ordinary latest month-over-month growth MUST separately be `100 × (x4 - x3) / x3` when `x3` is positive and absent when `x3` is zero. An absent percentage MUST be displayed as not calculable with its reason, not as 0%.
- **FR-016**: For every category observed anywhere within a ready partner's five-month history, users MUST be able to inspect its five monthly spending observations, latest spending, latest three-month baseline, latest monetary change, both rolling comparisons with their own month labels/baselines/spending/changes/percentages, and the separate latest ordinary month-over-month percentage. Each category MUST have an outcome of sustained growth, no sustained growth, or suppressed with a reason. Suppression MUST NOT make otherwise complete partner history insufficient. Partner/category ordering MUST be deterministic by stable IDs.
- **FR-017**: The threshold MUST default to 20% and be adjustable for the current Bills visit from 1% through 100%, inclusive. Finite decimal percentages are valid. The effective threshold MUST be visible with the results and remain selected across viewing-month changes during the visit. A fresh visit or full reload MUST restore 20%; no new durable preference subsystem is in scope.
- **FR-018**: All threshold entry points MUST reject explicitly empty, nonnumeric, boolean, non-finite, and out-of-range values with clear feedback, without clamping, changing the sustained count, or silently accepting a different value. Only an omitted threshold defaults to 20%. Results MUST always identify the valid threshold actually used.

#### Bills experience and safe retrieval

- **FR-019**: Bills MUST provide a distinct lifestyle-creep surface separate from Grid, Graph, Table, and the adjustable display window. It MUST support loading, error with Retry, insufficient history, ready with no alerts, and ready with alerts. Historical coverage and the selected viewing month MUST be visible in each available result.
- **FR-020**: Each partner MUST have an explicit ready or insufficient-history status. Overall status MUST be ready when every assessed partner is ready, partial when at least one is ready and at least one is not, and insufficient history when none is ready or no stable partner can be established. A missing whole-month record affects all partners requiring it. Ready partners MUST remain inspectable independently, but partial overall coverage MUST remain prominent; incomplete partners MUST have no calculated category verdicts.
- **FR-021**: Expected history gaps, legacy records, recorded unavailability, partial months, and scope mismatches MUST lead to availability diagnostics and a re-sync affordance. Unreadable records, structurally invalid aggregates or identities, invalid amounts, and unexpected retrieval failures MUST instead produce a generic error and Retry, without exposing storage details or presenting a no-alert conclusion. Invalid records MUST NOT produce a successful partial result. A retry after corrected history MUST reflect the latest saved records.
- **FR-022**: All detector monetary values MUST honor the global amount-hide state everywhere they are presented, including zero/signed values, baselines, differences, uncategorized totals, tooltips, accessible names/descriptions, and hidden text. Percentages, counts, months, identities, and status MUST remain visible. Masking is presentation-only and MUST NOT alter the calculations.
- **FR-023**: Changing amount visibility, visualization mode, or unrelated display-window controls MUST NOT trigger detector history retrieval. Loading and result states MUST be clearly announced; Retry, threshold, re-sync navigation, and detail controls MUST be keyboard-operable and clearly labelled. A late result for an earlier month or threshold MUST NOT replace or masquerade as the current selection.
- **FR-024**: A valid evaluation MUST attempt only the five exact stored monthly snapshot locations required by its window, at most once each. It MUST NOT scan other history, read raw transactions as a fallback, infer older substitutes, contact an external service, persist a result, or initiate sync. Invalid viewing-month or threshold input MUST trigger no history reads. Refresh and Retry MUST remain bounded, local, read-only actions.
- **FR-025**: All result wording MUST describe observed category spending and the rule used. No-alert wording MUST be limited to the covered spending and must not imply comprehensive financial health. This feature MUST NOT introduce runway, debts/assets analysis, forecasting or extrapolation, subscription detection, notifications, inflation adjustment, financial advice, or automatic budget changes.

### Key Entities *(include if feature involves data)*

- **Viewing month**: The user's as-of month; determines the preceding five completed calendar months, independently of displayed Bills months.
- **Partner**: A person represented by stable source identity and a display label; spending and readiness are assessed independently.
- **Monthly spending evidence**: One partner's monthly record of identified category spending and separate uncategorized spending, with explicit source completeness and comparable spending scope. Observed zero and unavailable evidence are different states.
- **Spending scope**: The ownership, accounts, effective exclusions, relevant category roles, and spending definition governing which transactions qualify; labels are not part of its identity.
- **Category series**: One original source category ID, its latest available label, and five chronological spending observations for a ready partner.
- **Rolling comparison**: One evaluated month, its own three preceding baseline months and average, spending, monetary difference, and optional percentage.
- **Detector result**: Selected month, effective threshold, exact history/evaluation months, overall and partner statuses, diagnostics, and category outcomes with explanations. It is a view of saved evidence, not a saved financial recommendation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every calculation example in User Story 1 and the edge-case table yields the specified outcome, including both exact-threshold boundaries, sparse categories, zero denominators, and sustained elevation without acceleration.
- **SC-002**: In every incomplete-history acceptance case, users can identify the affected month, partner where known, reason, and re-sync need; zero incomplete partners receive a category verdict or a misleading no-alert conclusion. A ready partner remains inspectable under an explicit partial-coverage status.
- **SC-003**: Users can identify each flagged category, partner, threshold, both evaluated months, baseline amounts, latest monetary change, and separate month-over-month change without leaving the detector. When amounts are hidden, the same explanation remains usable through visible months, percentages, and statuses without revealing money.
- **SC-004**: All detector monetary presentations remain masked while global hiding is active, including tooltips and assistive text. Changing visibility updates the presentation without reloading the analysis.
- **SC-005**: Users can change sensitivity by editing one threshold and applying it, with no setup or saved-preference step. Both inclusive bounds and decimal thresholds work; every defined invalid-input case is rejected without a falsely labelled result.
- **SC-006**: With month, threshold, and saved history unchanged, all three Bills visualization modes and any Bills display-window setting produce identical detector coverage and conclusions, including across year boundaries.
- **SC-007**: Every identity acceptance case preserves source-category and partner separation; label-only renames change neither computed growth nor readiness. A spending-scope change produces a re-sync requirement instead of an apparent increase.
- **SC-008**: After a successful re-sync supplies the five missing or incomparable months, Retry can change insufficient/partial coverage to ready using those months only. Existing Bills category displays remain unchanged when the new history capability is added.

## Assumptions

- **A-001 — Five months, not four**: The assignment's reference to research with a four-month acceptance example is corrected here. Three preceding baseline months plus two consecutive independent rolling evaluations require five distinct completed months. Four months are insufficient; neither baseline is shortened. External research is optional and no external research was performed for this specification.
- **A-002 — Sparse-category limits**: Positive spending in at least two of the initial three baseline months is the minimum recurring-evidence rule. It suppresses some newly established recurring habits as well as low-frequency activity. It cannot reliably recognize actual annual charges or one-off purchases within an otherwise frequent category. There is no minimum-currency floor or transaction-level recurrence classification in this version.
- **A-003 — Existing credit-card scope**: Coverage follows the existing Bills posted-outgoing credit-card population, not every account and not only a newly selected discretionary role. No currency conversion or household-wide financial conclusion is introduced.
- **A-004 — Threshold choice**: The default is 20%; finite numeric tuning from 1% through 100%, inclusive, is chosen to allow lower and higher sensitivity while excluding zero/negative and unbounded values. Decimals are accepted. Both comparisons use strict greater-than tests. Baseline length is three and sustained count is two, neither configurable in this version.
- **A-005 — Existing application conventions**: The current Bills calendar, monetary presentation, partner/account/category mappings, global amount-hide control, and explicit sync experience are reused. No new dependencies or preference-persistence subsystem are permitted. The project constitution governs later planning; this specification does not choose an implementation stack or new architecture.
- **A-006 — History prerequisite and compatibility**: The supplied discovery report confirms that legacy category totals are keyed by mutable titles, while source transactions retain category IDs. Existing title totals remain unchanged. A future sync must add stable-ID, explicitly completed, scope-aware evidence before those months are eligible; this specification does not read or rebuild personal history.
- **A-007 — Display labels**: The latest available label within the selected history is authoritative for presentation only. No current-catalog lookup is required while reading the detector. If an identity lacks a usable label, it remains distinguishable by its source ID rather than being joined to a similarly named category or partner.
- **A-008 — Unattended decisions**: The user explicitly authorized ordinary assumptions without questions and autopilot approval of those assumptions. The choices above are recorded on that basis, not as separately obtained interactive approvals. This authorization does not mean unexecuted technical or workflow gates have passed.
- **A-009 — Branch/workflow deviation**: The user directs work to remain on the existing app-managed branch. Per the coordination handoff, the git-feature hook was invoked but branch creation was skipped to honor that restriction; it is not a successful branch-creation claim. Feature identity is `005-lifestyle-creep`, independent of branch naming.
- **A-010 — Specification-only delivery**: This phase creates the specification and its requirements-quality checklist under `docs/specs/005-lifestyle-creep`, with a gitignored local feature pointer. It stops ready for planning, with no implementation, migrations, dependency changes, commits, pushes, pull requests, or merges. Optional after-specify commit and agent-context hooks are skipped by explicit coordination. The mandatory before-tasks plan-review gate has not been reached or run; no override or pass is claimed.
- **A-011 — Safe future verification**: Acceptance examples are synthetic. Later verification must use isolated synthetic evidence, never real financial records, credentials, the main checkout, or running services to establish correctness.
- **A-012 (Re-sync range)**: An explicit re-sync that repairs history runs from the first month of the evaluated five-month window through the usual sync end month (at least the current month), in one run under a consistent account/category configuration; it does not stop at the end of the evaluated window. The detector still reads only the five complete months required above. This assumption concerns how the existing sync is run, not what the detector requires. The reasons are recorded under Known limitations in the quickstart.
- **A-013 (Placement amendment, 2026-11-02, user-directed)**: The user asked for the detector in its own tab rather than on the Bills page. It now has a **Lifestyle Creep** navigation tab and page of its own; the Bills page no longer shows it. Where User Story 4 and FR-019 place the detector on Bills, read the Lifestyle Creep tab. The requirements themselves are unchanged: the detector stays separate from Bills visualization modes and the display window (SC-006), and the API path stays under `/api/bills/`.

## Amendment: Choose the comparison period (2026-11-02)

**User request**: "I wamt to choose the periode to compare lifestyle creep pls".

This is an update to feature 005, not a new feature or governance change. The earlier scenarios, evidence and placement amendment remain historical records. The requirements below take precedence wherever the original text fixes every request to five evidence months or two evaluated months. Default calculations and their explanations remain unchanged.

### User Story 5 — Choose which completed months to compare (Priority: P1)

As a household member, I want explicit **From month** and **To month** choices for the period being evaluated, so I can inspect a short or longer run of spending without confusing an as-of month with the months compared.

**Independent Test**: Select one, two, six and 24 completed months of synthetic history. Verify every selected month against its own prior-three-month baseline, verify that one month never claims sustained growth, and verify that separated high months do not become a consecutive pair.

**Acceptance Scenarios**:

1. **Given** the current month is October 2026 and no range was chosen, **When** the detector opens, **Then** From is August and To is September, the evidence is May–September, and all existing default amounts and outcomes are unchanged.
2. **Given** From and To are both September 2026, **When** applied, **Then** June–September supply four observations, September has one comparison against June–August, and no category is sustained even if September exceeds the threshold. Ordinary month-over-month growth still compares September with August.
3. **Given** six or 24 consecutive completed months are selected, **When** applied, **Then** each selected month is evaluated and the evidence includes exactly the three additional months before From: nine or 27 months respectively. Year boundaries do not change the rule.
4. **Given** any two neighboring eligible selected months both strictly exceed the threshold, **When** results are calculated, **Then** the category is sustained even when the pair is not the last pair. Non-neighboring high months alone do not qualify; equality never qualifies.
5. **Given** a selected category has a zero or sparse rolling baseline, or observed zero spending between high months, **When** evaluated, **Then** that gap breaks any affected qualifying pair. A later genuinely eligible consecutive pair may still qualify. Unknown source history instead prevents the entire partner's evaluation.
6. **Given** one boundary is missing, either boundary is invalid, To precedes From, the range exceeds 24 months, From lacks three representable predecessors, or To is current/future, **When** submitted, **Then** clear validation rejects the selection before history is accessed. No automatic shift, shortening, substitution or zero-filling occurs.
7. **Given** a baseline month or an interior selected month is missing, legacy, partial, unavailable, lacks the partner or has changed spending scope, **When** evaluated, **Then** existing insufficient/partial coverage rules apply over the full required evidence window. A corrupt record still causes an error, not a successful partial result.
8. **Given** a valid selection is shown, **When** opening category or uncategorized details, **Then** all selected evidence months and all comparisons are visible, the latest values come from To, and global amount masking still covers every monetary value. Applying another valid range preserves the threshold; an older response cannot masquerade as the new range.

### Amended requirements and precedence

- **FR-026**: Users MUST be able to choose inclusive From and To completed calendar months defining one contiguous evaluation period of 1–24 months. These controls select evaluated months, not a redundant end/as-of control. This supersedes FR-002's fixed evaluation window and the viewing-month-only interaction in FR-019.
- **FR-027**: With no explicit range, the existing viewing-month behavior MUST remain: month `M` evaluates `M-2..M-1` using `M-5..M-1`. With a range, evidence MUST be exactly `From-3..To`, oldest first. The current and future months MUST never contribute spending. The earliest From is `0001-04`. Invalid, incomplete, repeated, reversed or oversized selections MUST fail before history access, supplementing FR-003 and FR-018.
- **FR-028**: Each selected month MUST compare with its own immediately preceding three-month average using the existing exact threshold and sparse/zero rules. A month is eligible only with a positive baseline and at least two positive observations among its three predecessors. A category MUST be sustained if and only if any two consecutive eligible selected months both strictly exceed the threshold. One selected month can be described but cannot be sustained. This supersedes the fixed indexing in FR-012, the all-selected-month conjunction in FR-013, and the single initial-baseline screen in FR-014–FR-015; it does not change baseline length, strictness or sustained count.
- **FR-029**: Readiness, stable-ID unions, display labels, scope checks, separate uncategorized amounts, unknown-versus-zero distinctions and fail-closed diagnostics MUST cover the entire required evidence window. This replaces “five” with the selected evidence count in FR-005–FR-006 and FR-010–FR-011. No evidence can be silently dropped because the selected range is longer.
- **FR-030**: Every category detail MUST contain all evidence observations and one complete rolling comparison per evaluated month; latest spending/baseline/change and ordinary month-over-month growth MUST refer to To and its immediately preceding month. Existing money privacy, deterministic ordering and absent-denominator behavior remain. This supersedes fixed cardinalities in FR-016 and SC-003.
- **FR-031**: The existing threshold MUST remain selected across valid From/To changes within the visit. The selected boundaries MUST be visible with results; invalid edits must not relabel earlier results, and stale responses MUST be rejected by complete selection identity. This extends FR-017 and FR-023; no durable range preference is introduced.
- **FR-032**: Valid reads MUST attempt exactly the required 4–27 saved snapshots at most once each; fatal corruption may stop early. No scans, raw transactions, catalogs, sync, writes or new persistence are permitted. Invalid selection causes zero history reads. This supersedes FR-024's fixed count; Retry and sync remediation retain their existing roles.

### Amendment assumptions and outcomes

- **A-014 — Variable period**: A-001's five-month minimum applies only to the default two-month comparison. One evaluated month requires four evidence months; 24 requires 27. The 24-month bound limits local work without adding a new history subsystem.
- **A-015 — Local sparse screen**: A-002's initial baseline screen now applies at each rolling position. An established qualifying pair later in a range is not globally vetoed by earlier sparse activity. Default two-month suppression explanations remain compatible; a longer range is not described as wholly suppressed when another candidate pair is usable.
- **A-016 — Unchanged baseline and sustained count**: A-004 still fixes baseline length at three, sustained count at two, and threshold default/bounds at 20%/1–100%. Only the evaluated period changes.
- **A-017 — Full-window remediation**: A-012 now starts re-sync at `From-3` and still runs through the usual sync end month (at least current month) in one consistent configuration. The read-only detector requires and reads only its selected evidence.
- **A-018 — Scope and authorization**: This dated amendment updates existing feature artifacts under the user's autopilot delegation. No new feature pointer, directory, branch, hook, commit, dependency or governance change is authorized. Backend/spec verification does not certify frontend, integrated review or a container rebuild.
- **SC-009**: Users can select a one-, two-, six- or 24-month period with two month choices and Apply. Each result identifies the same boundaries, exposes exactly one comparison per selected month, and preserves the previous default result when the default range is chosen.
- **SC-010**: Every invalid-range acceptance case causes zero history reads. Every valid range uses no more than 27 exact snapshots; no incomplete partner receives a verdict and no one-month range receives a sustained flag.

**Acceptance mapping**: FR-026–FR-027 → Story 5.1–5.3/5.6; FR-028 → 5.2/5.4/5.5; FR-029 → 5.5/5.7; FR-030–FR-031 → 5.8; FR-032 → 5.3/5.6/5.7. SC-001–SC-008 retain their original default expectations, with window references generalized as above.

## Corrected target/reference semantics — 2026-11-02

The user clarified that month ranges are reference thresholds for one selected historical month, not a multi-month evaluation range. This section supersedes the preceding selectable-period amendment wherever their meanings conflict.

- **FR-033**: `month` MUST identify exactly one target month, using the existing API parameter name and ASCII `YYYY-MM`. It MUST be no later than the API process clock's current month. Financial evaluation MUST require every evidence month to be strictly earlier. For a valid current-month selection, return `insufficient_history` with a null-partner `partial_month` / `open_month` issue, no partners or money, and zero snapshot reads, even if saved status claims complete. This handles a browser whose latest completed local month is still current on the API clock; client exclusions remain unchanged.
- **FR-034**: Users MUST be able to provide optional paired inclusive `reference_start` and `reference_end` bounds. The contiguous reference range MUST contain 2–24 completed months, each strictly earlier than the target. An omitted pair defaults to the three calendar months immediately preceding the selected target. The sensitivity threshold remains a separate input, default 20%, bounded 1–100%.
- **FR-035**: A valid evidence window MUST be exactly the selected reference months followed by the one target month. The response MUST expose one comparison per category: target actual spend versus arithmetic mean reference spend. No other comparison or sustained-month verdict is implied.
- **FR-036**: For reference total `T`, count `r`, target amount `S`, and threshold `p`, an above-threshold result MUST require `T>0`, at least two distinct positive-spend reference months, and the exact strict inequality `100*(r*S-T) > p*T`. Equality MUST remain false. Zero mean and low-frequency suppression MUST be reported as `zero_baseline` and `low_frequency`, respectively, without erasing amounts.
- **FR-037**: The compatibility field `evaluation_months` MUST contain only `[month]`; `baseline_months` MUST report the selected 2–24 reference months. Category details MUST include all reference and target samples, one comparison, and uncategorized samples for every month. `latest_month_over_month_percent` MUST be null unless reference_end is immediately before target; when adjacent it uses those two exact sample values.
- **FR-038**: Missing, partial, legacy, unavailable, or scope-inconsistent evidence anywhere in the reference months or target MUST block that partner's conclusion. Read exactly the reference snapshots and target once each (3–25 files), without reading any intervening month if the reference end is older than target−1. Invalid requests MUST resolve no storage paths.
- **SC-011**: At a 20% threshold, reference amounts `[100,200,300]` and target `240` produce mean `200`, change `40`, growth `20%`, and `is_above_threshold=false` by strict equality. Target `240.001` exceeds. With a two-month reference, both months must have positive spend to satisfy the frequency minimum.

## Visit-local category visibility — 2026-11-02 amendment

This additive UI amendment does not alter the corrected target/reference calculation contract.

- **FR-039**: On `/lifestyle-creep`, users MUST be able to hide a comparison category's row and detail disclosure together, independently for each stable `partner_id` + `category_id` pair, regardless of duplicate or changing display titles.
- **FR-040**: Each ready partner with categories MUST expose a clearly view-only hidden count, a keyboard-operable **Show hidden categories** toggle with `aria-pressed`, a **Restore** action for each shown hidden row, and partner-only **Restore all** when any identities are hidden. Shown hidden rows MUST be marked **Hidden**. The all-hidden state MUST retain recovery controls and distinguish itself from genuinely absent categories.
- **FR-041**: Visibility MUST be visit-local, survive target/reference/threshold loading and errors/Retry, and reset on a fresh visit. Hide/show/restore MUST make no requests or persistent writes and MUST NOT change calculations, snapshots, configuration, sync, other tabs or global amount privacy. Explain that server assessments still cover all covered categories, including hidden rows. Existing masking MUST cover shown hidden rows and collapsed details.
- **SC-012**: Synthetic client tests MUST prove stable-ID/partner independence, reversible row/detail filtering, all-hidden recovery, refetch-state retention, fresh-visit reset, unchanged request counts, monetary masking and the existing absence of detector requests on Bills. Independent review and container/browser acceptance of this amendment remain separate tasks.

## Shared economy and report grouping amendment

This amendment adds an explicit report-population comparison mode. The original
outgoing-credit-card mode remains available and does not change meaning.

- **FR-042**: Report mode MUST always identify three separate groups: shared economy (Home plus Common), Personal Partner A, and Personal Partner B. Personal placement follows the report category section, not the owner of the paying card/account. Shared MUST NOT mean the sum of the two personal owners' spending.
- **FR-043**: Each group MUST use the detailed reports' resolved category inheritance, account exclusions, transfer routing and leaf-category grouping. Category amounts MUST be paid minus received across both payers. Refunds and reimbursements reduce spending; net negative spending MUST remain representable. Trips, savings, income, excluded and credit-card-payment sections MUST NOT be included in shared or personal comparisons.
- **FR-044**: Complete report evidence MUST come from a verified full-month acquisition begun after month close, with valid report classification inputs and posted transactions. Missing/invalid configuration, incomplete acquisition or unknown source MUST NOT produce successful zero-spend observations. The producer MUST NOT silently discard pending rows to claim parity with a report that includes them.
- **FR-045**: Report evidence MUST retain stable category/group/person identities and a label-independent scope covering the report classification policy, category parents, owner slots and included/excluded accounts. All three groups require the complete selected file window and one consistent scope/identity assignment. Original outgoing-card evidence MUST NOT be substituted for missing report evidence.
- **FR-046**: Report mode MUST retain the corrected target/reference/threshold selection contract and the exact strict comparison inequality. A negative reference total MUST suppress the verdict explicitly as `negative_baseline`; zero reference total remains `zero_baseline`. At least two positive reference samples remain required. Negative target spending and negative changes are valid. Undefined percentages MUST be null, not invented.
- **FR-047**: History GETs MUST remain bounded to exactly the selected 3–25 snapshots, with validation and the API clock guard before data access. GET/Retry MUST NOT read current configuration/raw reports, call upstream services, sync, repair or write data. Unsupported old evidence MUST show all three groups as insufficient and explain the need to check report mappings and explicitly re-sync.
- **FR-048**: The default outgoing-credit-card response and legacy Bills fields MUST retain their existing semantics. Report mode MUST be explicitly selected and expose generic groups rather than reinterpreting the old partner array.
- **FR-049**: The standalone client MUST request `grouping=report` by default, replacing the former CC-owner presentation without adding a mode toggle. It MUST show Shared economy first (Home + Common only), then the two configured personal labels in report order. Visit-local visibility MUST distinguish stable `group_id`/`category_id` identities, including the shared group without a person ID. The existing controls, amount privacy, response-identity checks and request-free hide/restore behavior MUST be preserved.
- **SC-013**: Synthetic verification MUST prove report total/category parity, Home/Common sum without duplication, opposite-owner personal placement, inheritance/remapping, refunds/negative/zero baselines, actual transfer/exclusion rules, closed acquisition provenance, configuration/scope failure, fixed three identities, bounded read-only API behavior and unchanged default outgoing-card results. Client adoption, independent review and container/browser validation remain separate tasks.

### T058 client acceptance boundary (2026-11-02)

The client mirrors report DTOs rather than adapting the old partner array. It
validates mode, selection, ordered group identities, slots, saved personal
identities and monetary coverage before adopting a response. It preserves server
category IDs/titles, signed amounts, suppression and verdicts without client-side
accounting or an extra total. All three group headings remain visible for valid
insufficient responses with empty money arrays and mapping/resync guidance.
Missing or malformed response identities are errors, never fabricated groups.
Uncategorized samples follow the backend report group and remain separate from
category-threshold outcomes, including negative samples. T059 review and T060
container/browser verification are still required; client tests do not replace them.

## Category usage graph — 2026-11-02 amendment

Dated scope note: the user asked for a graph in each Target comparison dropdown
showing usage over the selected period, with an average line and marked months
above that running average. This is a client-only, descriptive addition. It does
not change the target/reference calculation, threshold, API, snapshots or
server verdict.

- **FR-050**: Each expanded category disclosure MUST show that category's samples chronologically with a distinct **Trailing average (up to 3 prior months)** line. For each month the average uses up to three immediately preceding consecutive evidence months, excluding the month itself, and is shown only with at least two. Unselected calendar gaps MUST break the lines and MUST NOT be zero-filled, interpolated or bridged by nonconsecutive months.
- **FR-051**: A non-colour marker MUST identify months whose net usage is strictly greater than their own trailing average, decided exactly from decimal strings; the target MUST be distinguishable. The UI MUST state that these markers are not the applied threshold, the reference verdict or a forecast. Hide amounts MUST mask every monetary surface of the graph, including ticks, tooltips and accessibility text, without requests or disclosure changes.
- **SC-014**: Synthetic helper/component/page tests MUST prove the averaging, strictness, gap, rollover, signed, precision, lazy mounting, accessibility text, privacy and hide/restore behaviour across all three report groups. Independent review and container/browser verification are separate tasks.
