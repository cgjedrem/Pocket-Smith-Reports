# Contract: Lifestyle Creep Card

- **Status (2026-11-02 report-group amendment)**: T058 client adoption is complete. The page uses report grouping by default, replacing the former CC-owner view without a mode toggle. T059 independent review and T060 container/browser verification are pending. Historical two-person CC runtime evidence does not verify this amendment.
- **Backend authority**: [GET contract](lifestyle-creep-api.md).
- **Placement**: `LifestyleCreepPage`, its own route `/lifestyle-creep` reached from the **Lifestyle Creep** nav tab directly after **Bills**. The page shows a heading, a one-line description and this card, and nothing from Bills. Changed on 2026-11-02 at the user's request; until then the card sat on `BillsPage`, below the Runway & Burn Rate panel and above `BillsDashboard`, mounted outside the dashboard branch, Grid/Graph/Table and display-window rendering.

## Component Boundaries

| Boundary | Responsibility |
| --- | --- |
| `types/lifestyle-creep.ts` | Exact new wire types, including decimal strings and nullable percentages. No reuse of title-keyed Bills display models. |
| `api/lifestyle-creep.ts` | Separate typed `getEconomyLifestyleCreep` wrapper encodes target, threshold, both references and `grouping=report`; GET with `cache: "no-store"`. Preserve `getLifestyleCreep` as the original CC-compatible wrapper without grouping, plus response and `ApiError` behavior. |
| `hooks/useLifestyleCreep.ts` | Report-mode loading/data/error/retry, selection and fixed-three-group identity/coverage validation, and latest-request protection. No detection math, display-model fallback, or durable storage. |
| `LifestyleCreepPage` | Own route/tab (2026-11-02, user-directed; previously `BillsPage`). Owns one target-month control, draft/applied reference bounds and visit-local threshold; sends all three month values and mounts the card. `BillsPage` neither renders nor requests the detector. |
| `LifestyleCreepCard` | Report DTO props, labelled controls, coverage, group/category details and privacy-aware monetary formatting. Owns visit-local category visibility keyed by stable group and category IDs, outside conditionally mounted group results. No direct fetch or verdict computation. |

## Report Groups and Scope

- Always render valid response groups in API order: `shared`, `personal_partner_a`,
  `personal_partner_b`. Shared uses its saved label and contains Home + Common only;
  personal headings use configured saved labels, never hardcoded names.
- Mirror `ReportLifestyleCreepResponse`, `ReportLifestyleGroup`,
  `ReportLifestyleCategory` and report issues. Keep signed decimal strings and
  null percentages unchanged. Category IDs/titles and uncategorized samples come
  from the report classifier; do not merge, roll up or reclassify in the client.
- Included checking and card payers contribute paid minus received. Personal
  section assignment is not account-owner assignment. Refunds may yield negative
  samples, target spending, reference means and changes. Trips, savings, income,
  excluded and credit-card payment sections are omitted. No whole-household total
  or extra aggregate is supplied or invented.
- Missing/legacy/schema-6 history cannot be inferred from CC observations. All
  three valid insufficient group headings remain visible with no monetary rows
  and clear mapping/resync guidance, never fake `0 kr` or a no-alert conclusion.
  Pending/unknown transaction status conservatively prevents complete evidence.
  GET/Retry only reads persisted report evidence and never starts sync or storage
  repair. See [schema-7 migration and rollback](bills-history-v7.md).

The wrapper/hook must not call `bills-source.getMonths()`, reuse mock fallback as production evidence, or derive results from `useBillsSnapshot` neighbors. Bills loading failures must not affect this independent route.

## Target and Reference Period

- Provide three calendar month selectors labeled **Target month**, **Reference start**, and **Reference end**, plus one **Apply comparison** action. Apply all three draft months atomically. `threshold_percent` has its own **Apply threshold** action.
- The target defaults to the latest completed browser-local month. The default reference is target−3 through target−1. The client target must be strictly before the browser's current month; the contiguous reference range contains 2–24 completed months, all before target. Earliest target is `0001-03`; earliest reference is `0001-01`.
- The client continues excluding its own current month. If a browser-local completed target is still current on the API clock, report mode returns `insufficient_history`, three insufficient groups without money, and a null-group/null-partner `partial_month` / `open_month` issue without reading snapshots. Show no reliable conclusion, with the reason "Month is still open or history was acquired while open; wait until it closes, then re-sync if needed". Label `window_months` as "Required evidence months", never as proof of reads. No new status or issue enum is introduced.
- Use this description: “Compares spending in the selected target month with average monthly spending in the selected reference period. A category is flagged when it is above the applied threshold; this is descriptive, not advice.”
- Every request supplies `month`, `reference_start` and `reference_end`, plus canonical threshold. Do not derive target as `To+1`.
- Required evidence is exactly reference start through reference end followed by target (3–25 snapshots). The target need not follow reference_end immediately; never read intervening months. Missing snapshots never shift, drop, or zero-fill required evidence.
- Validate before requests; associate errors with affected controls and `aria-invalid`. An invalid or unapplied draft never relabels existing results. Applying an unchanged selection does not fetch.
- Label **Target month**, **Reference period**, and **Required evidence** honestly in loading, error, insufficient, partial and ready states. Do not describe the selected range as a multi-month evaluation period.

## Threshold and Request State

- Initial visit uses draft `"20"` and applied `"20"`. Changing period preserves the applied threshold. A fresh mount/visit or full reload resets range and threshold; no localStorage, settings API, query persistence, or new preference system.
- Use a controlled text value with decimal input affordance, a clear 1–100% label, and an Apply action. Native numeric coercion must not turn empty text into zero, Boolean into one, or an invalid value into the prior default.
- Validate numeric grammar and exact inclusive decimal bounds, consistent with the API. Keep raw text until validated; any normalization is value-preserving and visible through the response's canonical effective threshold. Do not rely only on JS float bounds for `100.00000000000000001`.
- Invalid draft shows an inline error and is not applied; no new detector request. If earlier results remain visible, they retain an explicit **Applied threshold** label for the previously accepted value and an indication that the edited value was not applied.
- A valid Apply clears/hides the prior selection's result while the new selection loads. Never show old data beneath the new period/threshold label.
- Request identity includes `report` mode, target month, both reference boundaries and canonical applied threshold; explicit Retry starts a fresh request for that identity, ignoring unapplied drafts. Deduplicate applying an equivalent canonical threshold without a selection change.
- Protect with request generation/cleanup or existing abort support. A late success or failure from a superseded request cannot replace current state. Guard identity on completion.
- Validate that returned `month`, `reference_start`, `reference_end` and `threshold_percent` match the requested effective selection before adopting the result.
- Validate the exact reference-plus-target window, `grouping=report`, three ordered
  stable group IDs/slots, null shared person ID, nonempty distinct personal IDs
  when ready, and sample/comparison coverage. Incomplete groups carry no money.
  Mixed group readiness, missing/duplicate/reordered groups or malformed coverage
  are errors, never accepted partial or inferred data. Do not recalculate verdicts.
- Privacy and unrelated display settings are not hook dependencies and must not refetch. Changing any target/reference value is a genuine request change.

## Required States

| State | Required presentation/actions |
| --- | --- |
| Loading | Distinct busy/status announcement for applied period and threshold; do not label prior results as current. |
| Error | Generic readable error; keyboard-operable Retry; no no-alert or partial verdict. Query validation errors explain the invalid selection. |
| Insufficient history | Affected months/groups/reasons, all three headings with no monetary rows or verdicts, the re-sync guidance below, and a link to `/sync`. |
| Partial | Not a valid report-mode response. The original CC API retains its partial-partner contract; the report client fails closed on mixed coverage. |
| Ready, no alerts | State that no category exceeded the configured threshold; keep all details and suppression explanations accessible. |
| Ready, above threshold | Three report-group tables in API order; stable-ID category results and their explainable target-versus-reference comparison. |
| Complete empty categories | No categorized spending observed, not insufficient. Show uncategorized samples and a coverage limitation if any are nonzero, including negative values. |

Expected issue codes map to short local messages; show source `reason` where applicable. Do not render raw backend structures, technical paths, or exception dumps. Null-group issues affect all report groups, not the first display slot. Group-scoped issues use the saved group label.

The `/sync` link only opens the existing sync experience; no invented route parameters or automatic submit/fetch. Show `history_guidance` when supplied. The fallback says to check report mappings and explicitly re-sync every selected completed reference and target month with one consistent configuration. Retry is read-only and never creates report-economy history.

## Category and Coverage Detail

For **every** observed category of a ready group, provide inspectable:

- Stable-ID-backed display title and report grouping; disambiguate duplicate titles using IDs.
- All 3–25 monthly spending observations with exact month labels.
- Target spend, selected-reference arithmetic mean, and target-minus-mean change.
- One comparison with target month, every selected reference month, average, spend, change and percentage.
- Optional adjacent month-over-month percentage, labelled separately from target-versus-reference growth.
- Above-threshold or not-above-threshold outcome, or suppressed outcome, using the server's `is_above_threshold` and `suppression_reason`.

Disclosures may keep the card compact but must not omit non-alert or suppressed categories except by the user's reversible visit-local visibility choice below. Never recompute averages/verdicts. Ordinary month-over-month percentage is available only when reference_end immediately precedes target and the previous amount is positive; it compares those actual samples. When null, omit this optional comparison rather than inventing `0%`. Genuine zero change may display `0%`.

### Visit-local category visibility — 2026-11-02 amendment

- Every normal comparison row has a semantic **Hide** button; its accessible name includes the category title (or ID fallback) and stable ID. After T058 a hidden identity is the pair `group_id` + `category_id`, never a title or nullable person ID. Groups and duplicate IDs/titles remain independent at the presentation boundary. Valid report API categories are unique across groups; the UI namespace does not depend on that invariant.
- Hide removes both the category row and its detail disclosure from the rendered view. Do not retain category money in concealed detail markup. Uncategorized spending and server coverage/threshold outcomes are unchanged.
- Each ready group with observed categories shows a view-only hidden count and **Show hidden categories** toggle with `aria-pressed`. Showing hidden entries renders their rows and disclosures, marks each hidden row **Hidden**, and provides **Restore** instead of Hide. Non-hidden rows retain Hide.
- Provide **Restore all** for that group whenever it has hidden identities. All-hidden views say **All categories are hidden in this view**, not "No categorized spending observed", and keep show/restore controls available. Preserve the true zero-category empty state.
- Keep visibility above group-result mounts, so loading/error/Retry and applied target/reference/threshold changes preserve it during the visit, including when display labels/person identities change. A fresh route visit/full reload resets visibility; no localStorage, URL, API or configuration persistence.
- Hide/show/restore cause no requests and change no API calculations, saved snapshots, account/category configuration, monetary privacy, sync or other tabs. Explain that hiding affects only rows/details, not the assessment across all covered categories; no-alert summaries remain based on every server-provided category.
- Existing monetary masking applies to shown hidden rows and every collapsed disclosure. No unmasked amounts in accessibility text, tooltips or attributes. Keep visibility actions in table cells and recovery controls outside the table.


### Category usage graph — 2026-11-02 amendment

- Each category's Target comparison disclosure renders a graph only while that disclosure is open (`<details>` toggle state). Collapsed, hidden and filtered categories mount no chart. Hiding a category removes its disclosure and graph; showing it again starts collapsed.
- Data source is only `category.samples` and `comparison.month` from the already-loaded response. No API change, request, persistence or localStorage.
- Series: monthly net usage (solid line, dot markers) and **Trailing average (up to 3 prior months)** (dashed line, short-bar markers). The trailing average for month M is the exact arithmetic mean of up to three immediately preceding consecutive calendar months present in the displayed evidence, excluding M. It is drawn only with at least two such months; no 0 or prior value is invented.
- Markers: a triangle marks usage strictly greater than its own trailing average (exact decimal comparison `amount × n > sum(prior)`, so equality is not above, including zero/negative values). The target has a square outline. Both are shape cues, not colour-only. Months without an average have no marker.
- Gaps: when months between reference end and target are not evidence, insert one break row (`?` tick), do not connect lines across it, and give the month after it no trailing average. Never treat nonconsecutive observed months as consecutive.
- The graph is descriptive. Text must say its markers are not the applied threshold, the reference-period verdict or a forecast. The server comparison above stays authoritative and unchanged.
- Text alternative: figure caption with month span and above-average months, an HTML legend, rule/gap/refund explanations and a graph data table (month, net usage, trailing average with its months, comparison status). The SVG itself is `aria-hidden` with Recharts' accessibility layer off.
- Precision: invalid decimals, duplicate months or non-calendar months show a visible "Graph unavailable" status. Values whose JS number would overflow, underflow to zero or exceed `Number.MAX_SAFE_INTEGER` are not plotted; a visible status explains this while the table keeps exact text and markers.
- Privacy: while **Hide amounts** is on, render a masked placeholder instead of the SVG (no axis ticks, coordinates, tooltips or marker metadata) and mask every table/average amount. Month labels, counts and above/not-above status remain. Toggling privacy keeps the disclosure open and causes no request.
The threshold decision uses the exact strict comparison of target spend to the arithmetic reference mean. It requires positive mean and at least two distinct positive-spend reference months. Explain suppression as `zero_baseline`, `negative_baseline` or `low_frequency` and do not infer verdicts from rounded percentages. Null growth says "nonpositive reference baseline", not zero when the baseline is negative. This is a one-month comparison, not sustained growth.

Show all 3–25 uncategorized amounts separately for each ready group, including signed negatives and zeros, and label the actual evidence count. When any is nonzero, make clear that it is net spending assigned to that report group but excluded from category-threshold outcomes. Never invent an “Uncategorized” category ID or alert.

Use descriptive, non-prescriptive wording. No recommendation to spend/save/borrow; no whole-household health claim, forecast, or automatic budget change.

## Amount Privacy and Accessibility

- Subscribe to `useAmountsHidden()` so all presented money reacts immediately without a request.
- Reuse existing masked `formatKr`/signed-money presentation helpers after converting validated decimal strings at the formatting boundary. If a finite decimal would overflow JS number conversion, use a masked decimal-text fallback with the same unit/sign convention rather than infinity or a fabricated zero. Do not call a raw unmasked formatter for secondary text.
- Mask spending, averages, positive/negative changes, zeros, and all uncategorized amounts. Do not mask percentages, threshold, dates, counts, identity, or status.
- No raw monetary strings/numbers in `title`, tooltip content, aria-label/description, screen-reader-only text, data attributes, hidden detail markup, or logs. A collapsed element is still a presentation surface.
- Percentage formatting is separate from money formatting; do not derive verdicts from rounded percentages. `20.00%` may be displayed beside a true strict-above result when exact growth was slightly greater.
- Semantic headings/status regions; labelled threshold and error association; keyboard-operable Apply/Retry/disclosures/link. Announce loading and selection changes without repeatedly announcing the whole table.
- Maintain the fixed returned group order and returned stable-ID category order, not locale titles.

## Integration Exclusions

Do not extend runway, debts/assets, forecasting, subscriptions, shared Bills calculation modes, or their sibling APIs/hooks. Do not change global privacy semantics, the legacy mapper, or default live Vite proxy settings for this feature.

## Required Client Verification

Wrapper query encoding/default behavior; hook loading/success/error/retry and stale responses; response identity; draft versus applied invalid inputs; every card state; all-category/uncategorized detail; complete empty history; duplicate-title identity; full masking including tooltip/aria/hidden content; visible percentages; keyboard access.

Page level: completed-target and three-month-reference defaults/month/year rollovers; atomic drafts; reference bounds of 2/24 and rejected 1/25, earliest target March 0001; threshold canonicalization, persistence across selection changes and fresh-visit reset; custom evidence labels; no privacy refetch; Retry repeats target, both references and threshold despite edited drafts. Hook tests race stale successes/failures before and after newer results, clear old values, and reject every echoed identity mismatch. Detail tests cover the single comparison, adjacent-only MoM and suppression semantics.

Bills (`BillsPage`): renders no detector region or month control and never calls the detector API, in the dashboard, not-found, error and loading states.

Visibility: synthetic component tests verify same-ID/title/label independence across all three group namespaces; page tests verify targeted row/disclosure removal, duplicate-title ID identity, show-hidden marking and `aria-pressed`, individual restore/group-only restore-all, all-hidden recovery versus true empty history, survival across loading/threshold/target/reference/error/Retry and renamed labels/person IDs, fresh-visit reset, unchanged API call counts, and masking in shown hidden rows/collapsed details.

Usage graph: pure helper tests cover the 3-month window, 2-prior minimum, strict equality, 2/3/24 references, gaps, month/year rollover, zero/negative and huge/precise values; component/page tests cover lazy mounting in all three groups, legend/summary/table text, markers, masked placeholder and restoration without requests, and removal on category hide.

Routing: a deep link to `/lifestyle-creep` renders the app shell with the **Lifestyle Creep** tab active, placed directly after **Bills**, and the detector region.

Browser verification must use synthetic request mocks installed before navigation, including adjacent app-shell requests. No request may reach a live backend. See [quickstart.md](../quickstart.md).
