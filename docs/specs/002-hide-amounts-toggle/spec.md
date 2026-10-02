# Feature Specification: Hide Amounts Toggle

**Feature Branch**: `002-hide-amounts-toggle`

**Created**: 2026-10-02

**Status**: Draft

**Input**: User description: "Implement a hide-real-numbers button on the report and bills pages — similar to what other finance apps use — show **** instead of the number, but keep the percentage. Motivation: safely capture screenshots of the app (with real data loaded) for public sharing (e.g., a LinkedIn post) without exposing actual financial figures."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Mask all monetary amounts on demand (Priority: P1)

The user is viewing any screen that displays monetary amounts (monthly reports, mega reports, bills dashboard) with their real financial data loaded. They want to share their screen or take a screenshot. They click a single, always-visible toggle and every monetary amount on the page is instantly replaced by a fixed mask (`****`), while the layout, percentages, charts, and all non-monetary context remain intact and readable.

**Why this priority**: This is the entire core value of the feature — without reliable one-click masking, no screenshot can be safely shared. It is independently shippable.

**Independent Test**: Load any report or the bills dashboard with data, activate the toggle, and verify that no monetary figure remains visible anywhere on the page while percentages and structure are unchanged.

**Acceptance Scenarios**:

1. **Given** a report page displaying monetary amounts, **When** the user activates the hide-amounts toggle, **Then** every monetary amount on the page renders as `****` and no real figure is visible.
2. **Given** the hide-amounts toggle is active, **When** the user navigates to another page (reports ↔ mega reports ↔ bills), **Then** amounts on the newly opened page are also masked without requiring another click.
3. **Given** the hide-amounts toggle is active, **When** the user deactivates it, **Then** all real amounts are immediately restored exactly as before.
4. **Given** amounts are hidden, **When** the user inspects percentages, bar proportions, transaction counts, dates, and category/partner labels, **Then** they are unchanged from the visible-amounts state.

---

### User Story 2 - Chart and tooltip figures are masked too (Priority: P2)

The user views charts (trend lines, bars, donuts, the bills graph view). Axis labels, data-point values, and hover tooltips must not leak the hidden figures, since a screenshot may include them.

**Why this priority**: Charts leaking axis scales or tooltip values would defeat the purpose of P1; but charts remain *visually* useful (shapes/trends) while masked, so this is a separable slice.

**Independent Test**: With masking active, hover chart elements and inspect axes on every chart-bearing page; verify no numeric monetary value appears, while chart shapes still render.

**Acceptance Scenarios**:

1. **Given** masking is active and a chart is displayed, **When** the user hovers a data point, **Then** the tooltip shows `****` in place of the monetary value.
2. **Given** masking is active, **When** a chart axis would normally show monetary scale labels, **Then** those labels are masked or omitted, while the chart geometry still renders.

---

### User Story 3 - Preference survives a page reload (Priority: P3)

The user reloads the browser tab (or returns later) and finds the mask preference remembered, so an already-"safe" window stays safe across reloads — and a user who wants real numbers isn't surprised by masking persisting silently.

**Why this priority**: Convenience and safety polish; the feature is fully usable without persistence.

**Independent Test**: Activate masking, reload the page, verify amounts are still masked; deactivate, reload, verify amounts are visible.

**Acceptance Scenarios**:

1. **Given** masking was activated, **When** the page is reloaded, **Then** amounts render masked immediately.
2. **Given** masking was never activated (fresh browser profile), **When** any page loads, **Then** real amounts are shown (default is visible).

---

### Edge Cases

- Masking must apply to **negative and signed** amounts (e.g. `+2,000 kr` / `-1,500 kr`) — the mask must not leak the sign, since sign alone reveals direction of money movement.
- Masking must apply to **zero** amounts (a visible `0 kr` leaks "no spending in this category").
- Empty/absent values (labels already rendered as empty string) stay empty — they must not become `****`.
- Bar widths, zone fills, and trend-line geometry are derived from real values; this is acceptable (proportions, not absolute figures) and matches the "keep the percentage" requirement — the feature masks numbers, not shapes.
- Non-monetary numerics — percentages, transaction counts, dates, month labels — must never be masked.
- Toggling must not trigger a data refetch or lose the user's current page/filters.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a single, always-accessible toggle control (available from every page) that switches all monetary amounts between visible and masked.
- **FR-002**: When masked, every monetary amount MUST render as the fixed string `****` — regardless of magnitude, sign, currency formatting, or value (including zero).
- **FR-003**: The mask state MUST apply application-wide across all pages (monthly reports, mega reports, bills dashboard, and any other amount-bearing surface) without per-page re-toggling.
- **FR-004**: Masking MUST cover all presentation surfaces of an amount: inline text, tables, KPI cards, chart axis labels, and chart tooltips.
- **FR-005**: Percentages, transaction counts, dates, and category/partner labels MUST NOT be affected by masking.
- **FR-006**: Chart geometry and proportional bar widths MAY continue to reflect real values (proportions are not absolute figures); only rendered numeric labels are masked.
- **FR-007**: The mask preference MUST persist across page reloads within the same browser, defaulting to visible for a fresh browser.
- **FR-008**: Toggling MUST NOT trigger a backend data refetch, reset page state, or lose the user's current selections (month, filters).
- **FR-009**: Toggling MUST take effect immediately (no page reload required) and restore exact original values when deactivated.
- **FR-010**: The toggle MUST be keyboard-accessible and expose its state to assistive technology (e.g., appropriate pressed-state semantics and label).

### Key Entities *(include if feature involves data)*

- **Mask preference**: A single boolean user preference ("amounts hidden" / "amounts visible"), stored client-side, defaulting to visible. No account, server state, or financial data is involved.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With masking active, an automated scan of every amount-bearing page finds zero rendered monetary figures (100% masked) on monthly reports, mega reports, and the bills dashboard.
- **SC-002**: Masking toggles fully within 1 second of the click, including charts and tooltips, with no reload and no network request.
- **SC-003**: A user can produce a screenshot of any page that is safe to share publicly in a single click from any page.
- **SC-004**: Percentages, counts, and dates are pixel-identical between masked and unmasked states (0 unintended changes).
- **SC-005**: The mask preference correctly survives 100% of page reloads.

## Assumptions

- The audience is the app's existing single user/household; masking is a presentation-layer privacy aid for screenshots and screen-sharing, **not** a security boundary (data remains in the browser and API responses are unchanged).
- Masking applies to the web client only; generated PDF/HTML report artifacts are out of scope (the user photographs the UI, not exported files).
- The fixed mask string `****` is language- and currency-neutral; no localization of the mask itself is needed.
- Client-side persistence (browser local storage) is sufficient; no server-side or per-account preference sync is required.
- Chart shapes continuing to reflect real proportions is acceptable and desirable (matches "keep the percentage").
