# Design: Client-side PDF export (sections + subsections)

**Status:** DRAFT — not human-approved
**Date:** 2026-07-31
**Scope:** Bug fix for existing Print feature; full rewrite of print CSS approach

## Context

User requested an in-client way to export a chosen subset of mega report sections
to PDF. Initial implementation used the browser's `window.print()` with print CSS
that hides unselected sections. Multiple iterations have failed — print preview
shows the section header but hides most/all body content.

User has explicitly asked to:
1. Investigate the root cause (not guess).
2. Write a design doc before further code changes.

## Investigation findings (Level 1-4 done before this doc)

### Current DOM structure for a section

```html
<section data-section-id="kpi" data-print-selected="1">
  <div data-slot="card">
    <div data-slot="card-header">...title + intro...</div>
    <div data-slot="card-content">
      <div class="grid">...</div>            <!-- direct child -->
      <div>...</div>                          <!-- direct child -->
      ...
      <!-- TripsSection: NO print-block wrappers in CardContent intro -->
      <div class="print-block" data-block-id="trips-common-overview">
        <h3>...</h3>
        <Table/>
      </div>
      <div class="print-block" data-block-id="trips-by-partner">...</div>
      <div class="print-block" data-block-id="trips-by-subcategory">...</div>
    </div>
  </div>
</section>
```

### Current print CSS

```css
.section { display: none !important; }
.section[data-print-selected="1"] { display: block !important; }
.section[data-print-selected="1"] .print-block { display: none !important; }
.section[data-print-selected="1"] .print-block[data-print-include="1"] { display: block !important; }
.section[data-print-selected="1"] [data-slot="card-header"] { display: block !important; }
.section[data-print-selected="1"] [data-slot="card-content"] > *:not(.print-block) {
  display: none !important;  /* ← bug */
}
```

### Bug: `:not(.print-block)` is too aggressive

The last rule hides **every direct child of `card-content` that isn't a `print-block`**.
This kills:

1. **Sections without subsections** (KPI, Income, Savings, Home, Monthlies,
   Recommendations, Excluded). Their CardContent is plain divs/grids/charts —
   no `print-block` wrappers. Result: **empty CardContent** → section renders
   as title-only.

2. **CardContent intro content** in TripsSection/SavingsSection/etc. — the
   descriptive text/elements between the CardHeader and the first print-block
   are direct children and get hidden. Result: chart/intro missing.

3. **Appendices wrapper containers** — the trip blocks and subcat blocks are
   nested inside `<div class="flex flex-col gap-3">` parents. Those parents
   are direct children of CardContent (not `.print-block`), so they get
   hidden, taking their wrapped blocks with them.

### Other issues observed

- **React duplicate key warning** in console:
  `appendices-subcat-personal_partner_b-personal-partner-b-root`. Pre-existing in
  AppendicesSection when main cat title === subcat title. Unrelated to print
  bug but should be fixed alongside.

- **Cleanup race**: old code did cleanup synchronously after `window.print()`.
  `window.print()` is non-blocking — it returns immediately and opens the
  print dialog. Cleanup ran BEFORE browser rendered the print preview,
  stripping `data-print-selected` and `data-print-include`. New code uses
  `afterprint` event + 30s fallback — this part works.

- **Browser print engine gotcha**: `display: flex` parents ignore
  `page-break-before` reliably. Forced `display: block` in print CSS for
  `.megaReportView`, `.layout`, `.content`. This part works.

## Goals (v1)

- User can open "Export sections" dialog → pick sections + subsections → click
  Print → browser print dialog opens with ONLY selected sections + subsections
  rendered, one per page.
- Sections without subsections print fully (including all their internal cards,
  charts, tables, summaries).
- Sections with subsections print: CardHeader (intro) + ONLY the selected
  subsections, each on its own page.
- Print preview shows correct content (no empty sections, no missing intro).
- No regressions to the existing full-PDF export button.

## Non-goals

- No backend changes (stay pure-client).
- No new dependency for PDF rendering (use browser print engine).
- No change to the WeasyPrint PDF endpoint.
- No change to section component public API.
- The pre-existing React duplicate key warning is fixed in this work but is
  not the primary goal.

## Proposed approach

### Strategy: invert the filter — hide what is NOT marked, instead of hiding what IS marked

Instead of trying to hide every direct child of CardContent, **mark what should
print** and let the rest render naturally. The current approach fails because
not all sections have print-block wrappers — for those sections, NOTHING in
CardContent is marked.

### Concrete changes

1. **Wrap ALL CardContent children in `.print-block`** in sections that don't
   already have per-subsection wrappers. This means:
   - `KpiCoverSection`, `IncomeSection`, `SavingsSection` (non-investment),
     `HomeSection`, `MonthliesSection`, `RecommendationsSection`,
     `ExcludedSection` — wrap each top-level CardContent child in
     `<div className="print-block" data-block-id="X">`.

2. **Rename existing `.print-block` wrappers** to use a consistent
   `data-block-id` matching the existing nav item ids. Where a section has
   no subsections, give the wrapper a section-level id (e.g.
   `data-block-id="kpi-content"`).

3. **Remove the `[data-slot="card-content"] > *:not(.print-block)` rule.**
   It is no longer needed once every direct child is wrapped. The remaining
   rules become:
   - Hide all sections by default.
   - Show sections marked `data-print-selected="1"`.
   - Hide all `.print-block` by default.
   - Show `.print-block` marked `data-print-include="1"`.

4. **When section is wholly selected** (no subsections or all subsections
   marked), mark ALL its print-blocks so the entire section renders.

5. **For sections with NO subsections at all** — treat the section as one
   big print-block. Either wrap the entire CardContent in a print-block, OR
   add a section-level rule: "if no print-block children exist, do not hide
   anything inside".

### Simplest variant (preferred)

Instead of touching every section component, do it from `MegaReportView`:

**For sections with NO print-block children**: change CSS so when section is
marked, ALL of CardContent renders. Rule:
```css
/* Hide print-blocks by default; show only marked ones. */
.section[data-print-selected="1"] .print-block { display: none; }
.section[data-print-selected="1"] .print-block[data-print-include="1"] { display: block; }
/* If section has NO .print-block children at all, don't apply the per-block
   hiding rule. Instead show all direct children of card-content. */
/* This can't be expressed in CSS directly. Use JS instead: when marking
   sections for print, if a section has no .print-block, mark ALL its
   direct children of card-content as if they were print-blocks. */
```

**JS-side solution** (preferred — least invasive):
In `handlePrint`, after marking the section:
- If section has NO `.print-block` children: mark ALL direct children of
  its `card-content` as `data-print-include="1"`. Treat them as blocks.
- Else: mark only the specific subsections.

Then CSS becomes:
```css
.section { display: none; }
.section[data-print-selected="1"] { display: block; }
.print-block { display: none; }
.print-block[data-print-include="1"] { display: block; page-break-before: always; }
```

No `:not(.print-block)` rule. CardContent renders naturally for sections
without subsections (their blocks get marked). For sections with
subsections, only marked blocks render.

### Print-block contract

Every `.print-block` MUST have a `data-block-id`. The id is used by the JS
print handler to find which blocks to mark. Section components without
subsections get ONE print-block wrapper around CardContent content (or use
the JS auto-mark approach for unwrapped sections).

For the JS auto-mark approach, the section DOES NOT need print-block wrappers.
The handler just marks all CardContent children directly. This is the path of
least invasion — no section component changes needed for sections without
subsections.

## File-level impact

### Modified
- `client/src/components/mega-reports/MegaReportExportDialog.tsx` — print
  handler marks all `card-content` direct children when section has no
  `.print-block` descendants. Cleanup uses `afterprint` (already in place).
- `client/src/components/mega-reports/MegaReportView.module.css` —
  remove the `:not(.print-block)` rule. Keep the rest of the print CSS.

### Not modified
- All section components stay as-is.
- `AppendicesSection` stays with its existing print-block wrappers.
- `TripsSection`, `CommonSection`, `PersonalSection`, `SavingsSection`
  (investment), `CcPaydownsSection` stay with their wrappers.

## Alternative approaches considered

### A. Force-print-block wrappers on every section
Every section wraps CardContent in `<div class="print-block">`. Print handler
marks that block for whole-section selections.

**Pros:** Most explicit, future-proof.
**Cons:** Touches every section component. Risk of regressions in screen
rendering (extra div wraps).

### B. Use `visibility: hidden` instead of `display: none`
Hidden content takes space, layout preserved.

**Cons:** Wastes paper in print preview. Browser may still print invisible
content in some engines. Doesn't solve the root problem.

### C. Switch to backend-assisted PDF (Option B from earlier discussion)
Extend `/pdf` endpoint with `?sections=X,Y` query param.

**Pros:** WeasyPrint-quality output, direct download.
**Cons:** Backend change required. User explicitly chose pure-client earlier.
Not pursuing.

### D. Use a CSS class on `<body>` instead of per-element data attributes
Add `body.printing-kpi` etc. Toggle class via JS. CSS keys off body class.

**Cons:** Same fragility — body class can't express subsection selection
without combinatorial explosion of classes. Same data-attribute model is
cleaner.

**Decision:** Go with the **simplest variant** above (auto-mark JS approach).

## Acceptance criteria

1. Open mega report for `2025-08 → 2026-07`.
2. Click "Export sections". Dialog shows 13 sections + their dynamic
   subsections (same as the navigation menu).
3. Select **only** section 8 (Trips), subsection "Common-only overview".
   Print preview shows exactly: page with "8. Trips" title + intro, then one
   page with the trips overview table. No other sections appear.
4. Select **all** sections. Print preview shows all 13 sections, each on
   its own page, with full content (no empty CardContent).
5. Select only sections 1 (KPI), 6 (Personal Fixture A), 13 (Appendices).
   Appendices renders with all its tables.
6. After print dialog closes (or user cancels), the page returns to normal
   view with no leftover `data-print-*` attributes.
7. Existing "Export PDF" button (full WeasyPrint PDF) still works.
8. No React duplicate-key warnings in console (pre-existing fix).

## Test plan

- **Manual (browser)**: open `localhost:5174/mega-reports?start=2025-08&end=2026-07`,
  run scenarios 1-6 above, verify print preview.
- **Manual (PDF)**: scenario 7 — click Export PDF, confirm PDF downloads.
- **Console**: scenario 8 — open dev tools, check for duplicate-key warnings.
- **No automated tests** in this iteration — print CSS is hard to unit-test
  without a full DOM render. Manual is sufficient.

## Risks

- **Browser engine differences**: Chromium and WebKit handle print CSS
  slightly differently (e.g. `break-before` vs `page-break-before`).
  Both are included as fallbacks — already in place.
- **`afterprint` event reliability**: Some browsers may not fire
  `afterprint` if the user cancels the print dialog. 30s timeout fallback
  already in place — covers this.
- **CSS pseudo-class `:not()` precedence**: CSS keeps the last matching
  rule. The new rules don't conflict because they target different
  selectors.

## Rollback

Revert the print CSS change in `MegaReportView.module.css` and the print
handler in `MegaReportExportDialog.tsx`. No data migrations, no API changes.
Risk-free to roll back.