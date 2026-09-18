---
title: PDF export by sections (client + CLI parity)
status: backlog
created: 2026-07-31
owner: unassigned
priority: P2 (deferred per user — "later, dev queue")
depends_on: []
blocks: []
related:
  - docs/design/design-client-pdf-export-sections.md (DRAFT — not human-approved)
  - docs/design/done/ (prior completed design work)
---

# Task: PDF export by section + client/CLI parity

## Why (user context)

User reported on 2026-07-31: PDF export worked (backend WeasyPrint) but
"export by sections" is gone — earlier version had a dialog that let user
pick sections/subsections from a checklist. User wants that capability
restored.

User explicitly said: "later, dev queue" — not now.

## Scope (two distinct sub-tasks)

### Sub-task A: Client/CLI parity
The client (Vite + React 19) and a future CLI tool must produce the
**same** PDF output for the same `{start, end}` range. Today only the
client exists. When CLI lands, both paths must:
- Hit `POST /api/mega-reports/{start}/{end}/pdf`
- Get back the same WeasyPrint-rendered blob
- Render identically

**Action:** document the parity contract in `docs/design/design-client-pdf-export-sections.md`.
No code change yet (no CLI exists).

### Sub-task B: Export by section
Restore the section/subsection picker in `MegaReportExportDialog`.
Backend currently ignores selection (always returns full PDF).

**Backend changes:**
- Extend `POST /api/mega-reports/{start}/{end}/pdf` to accept `?sections=kpi,recommendations,...`
- Optionally accept `?subsections=kpi:salary-allocation,trips:trips-common-overview,...`
- In `src/mega/build_mega.py`: filter the rendered sections list before WeasyPrint
- Must reject unknown section ids with 400 (security: avoid passing arbitrary
  HTML through WeasyPrint)

**Client changes:**
- Bring back `buildNavItems` section/subsection checkboxes in dialog
- Wire `selected` Set → query params on `exportMegaPdf`
- Remove the "Backend returns full PDF" notice
- Re-add `print-block` / `data-block-id` attrs to section components (were
  stripped in 2026-07-31 cleanup) — OR not needed if backend filters via
  the existing `data-section-id` attribute contract

**Tests needed:**
- Backend: section filter test, invalid id 400, empty selection → empty PDF or 400
- Client: dialog state, query param construction, error surface

## Reference (current state)

- `client/src/components/mega-reports/MegaReportExportDialog.tsx` —
  113 lines, confirm-then-export only, no section selection
- `client/src/api/mega_reports.ts` — `exportMegaPdf(start, end, signal?)`
- `src/budget_api/routers/mega_reports.py` — `POST /mega-reports/{start}/{end}/pdf`
  at line 212
- `src/budget_api/services/mega_pdf.py` — WeasyPrint renderer
- `src/mega/build_mega.py` — section renderer list (to be filtered)

## Acceptance criteria (when picked up)

1. Dialog shows section + subsection checkboxes (same as `buildNavItems`).
2. Selecting 1 of 13 sections + 1 of N subsections returns a PDF containing
   only those sections, with correct TOC + page breaks.
3. Invalid section id → 400 with helpful message.
4. Empty selection → either empty PDF or 400 (decide during design).
5. Client + (future) CLI produce byte-identical PDF for same selection.
6. Test coverage: backend section filter + client dialog + parity contract.

## Notes

- Design doc `design-client-pdf-export-sections.md` was started 2026-07-31
  with a window.print() approach. That doc is **STALE** — we shipped
  backend PDF instead. The doc needs a major rewrite to reflect the new
  backend-filtered approach.
- Estimated effort: 1-2 hours (small — backend filter is a list
  comprehension, client is a UI restore).
