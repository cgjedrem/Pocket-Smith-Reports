# Integrated Review: Feature005 Lifestyle Creep

- **Date**: 2026-10-31
- **Initial verdict**: **FAIL, two Important source-integrity findings**
- **Final local verdict**: **PASS** - independent re-review closed both findings; coordinator Git-scope verification resolved its metadata caveat.
- **Cycle1 status**: Both reproduced, remediated, and independently re-reviewed.
- **Task state**: T033 and T034 complete. Original findings and intermediate evidence below remain historical, including the counts measured at the time. T035 to T039 (rebase, real-data validation and the post-rebase review round) are also complete. T041 (move to a separate tab) and T040 (final container rebuild, done by the coordinator on 2026-11-02 against the working tree) are recorded in [quickstart section 17](quickstart.md#17-separate-lifestyle-creep-tab---2026-11-02).
- **Post-rebase review verdict**: pass-with-caveats, no critical or high findings. See [Post-rebase review (real-data round)](#post-rebase-review-real-data-round) for the final counts and the ten findings.
- **Historical selectable-period amendment (2026-11-02)**: T042–T048 complete; **48/48 total** for the superseded multi-month interpretation. Its coordinator-supplied independent review and 164-assertion real-container/browser verification are historical, not evidence for the corrected one-target/reference-period contract.
- **Corrected-contract checkpoint before visibility (2026-11-02)**: T049–T053 complete; **53/53 total** at that historical checkpoint. Independent review T052 **PASS, no significant issues**; corrected actual-container/browser smoke T053 passed. See [quickstart section 19](quickstart.md#19-corrected-target-month-and-reference-period---2026-11-02).
- **Historical visibility checkpoint (2026-11-02)**: T054–T056 complete; **56/56 total, zero pending** at that boundary. Supplied independent code-review T055 **PASS**; T056 frontend-only deployment and **67/67 Chromium assertions** passed. Evidence and review provenance are in the visibility section and quickstart section 20.
- **Historical report-group checkpoint (2026-11-02)**: T057–T060 complete; **60/60 total, zero pending** at that boundary. T059 independent read-only review **PASS, no significant issues**, supplied in the final-verification handoff. T060 rebuilt/deployed both images and passed **68/68 Chromium assertions** (57 synthetic, 11 live metadata/structural-only), the identical-category-ID component test and nine containment tests. Both services remained healthy with the original named private volume; live schema-7 report evidence was insufficient with four legacy-history issues and visible resync guidance. No sync was performed. Exact commands, evidence and final slice manifest are in quickstart section 21.
- **Current usage-graph checkpoint (2026-11-02)**: **63/63 total, zero pending**. Supplied T062 independent review **PASS, no significant issues**; T063 frontend-only deployment and **339/339 Chromium assertions** (333 synthetic, 6 separate live metadata/structure-only), nine containment tests and clean diff check. API container/image and named volume unchanged; both services remain healthy. The current live report GET returned ready/200 with three groups; no live graph was opened or financial values/identities captured. Graph acceptance uses synthetic data only. See quickstart section 22.

## Review provenance and scope

This report persists the initial integrated QA supplied in the cycle1 handoff.
That review was static; the two reproductions had **not** been executed.
The cycle1 execution evidence below is separate developer evidence, not an
independent QA approval or a rewrite of the original FAIL verdict.

The supplied review covered feature backend/frontend integration against
`spec.md`, `plan.md` and all three contracts: source acquisition, stable IDs,
Decimal decisions, complete-zero versus partial/missing evidence, bounded saved
history/route validation, error precedence, React request races, privacy,
compatibility and scope exclusions. Prior recorded baseline evidence was
192 feature / 1184 full Windows nonrenderer backend tests, 468 frontend tests,
a successful client build and all eight synthetic browser scenarios.

Cycle1 directly read the affected client/sync/producer/account source and
existing tests, reviewed the focused changes, and ran synthetic backend tests.
No client code was modified or rerun; earlier frontend conclusions and the
security checklist below are attributed to the supplied review.

## Initial blocking findings

### QA-001 — Important: capped retrieval certified complete

**Original references (pre-rework)**:
`src/budget_api/services/sync_runner.py:231–236`,
`services/ps_client.py:138–143,172`,
`services/bills_builder.py:1251–1269`;
`tests/test_ps_client.py:207–214` explicitly retained legacy truncation.

Sync treated any returned transaction list as successful acquisition.
`_get_paginated` could stop at the cap while a next page remained and return
the accumulated valid partial list. Builder validation could then certify
that closed-month subset as complete. This undermined history integrity and
originally blocked acceptance. Other paginated acquisition inputs, including
events and fallback fetches, needed the same sync policy.

**Required remedy**: explicit acquisition completeness or strict sync failure
before Bills publication, without changing deliberate legacy pagination callers.
Exercise actual pagination, a lowered cap, valid closed-month context, no new
Bills snapshots and byte-preserved prior Bills artifacts. Keep successful
single/multiple-page acquisition working.

**Cycle1 implementation**:
`services/ps_client.py:101–105,141–145` adds a keyword-only, default-false strict
pagination option; `services/sync_runner.py:191–192` enables it for the entire
sync client. A remaining next link at the cap raises `PSClientError`. This
covers monthly transactions/events and prior-month fallback before Bills
publication. A terminal page at the cap succeeds; default client truncation,
URL/redirect/repeat protections and response shapes remain unchanged.

**Actual reproduction**: four failing integration cases used real pagination
with mocked HTTP and cap one. Each incorrectly published a new May snapshot and
changed the seeded June partial / July unavailable artifacts during May–July
sync. Both complete-page control cases passed before the fix. All four failure
cases now require a failed sync, zero Bills writes, no May file and unchanged
prior bytes, and pass. Separate strict client tests cover transactions,
per-account transactions and events at one/two-page boundaries.

**Disposition**: Remediated in cycle1. The independent re-review was pending at that point and later closed it (see the final re-review section below).

### QA-002 — Important: excluded unassigned mappings invalidate all history

**Original references (pre-rework)**:
`src/budget_api/services/bills_derivations.py:110–116`,
`services/bills_builder.py:1258–1259`,
`routers/accounts.py:101–138`,
`tests/test_accounts.py:120–129`.

The validator required every mapping to have recognized partner/type before
considering exclusion. The existing account API accepts
`{partner_id: null, type: null, excluded: true}`. Removed catalog accounts also
retain excluded mappings. Either valid outside-scope state therefore made every
partner unavailable/invalid_source despite valid included CC accounts; repeated
sync could not resolve it. This originally blocked acceptance.

**Required remedy**: distinguish explicit exclusion from ambiguous included
ownership/type. Do not invent bindings. Preserve fingerprint participation of
known owned CC exclusions. Test producer and sync with catalog-present and
retained-removed null bindings, repeated sync and still-failing included ambiguity.

**Cycle1 implementation**:
`services/bills_derivations.py:114–130` accepts null ownership/type only when
`excluded` is Boolean true, validates all non-null values and keeps known owned
CC exclusions in scope. Catalog membership remains required for included
accounts, and unknown/missing included bindings remain unavailable/fail-closed.

**Actual reproduction**: six producer cases with null/partially unassigned
excluded bindings raised `unresolved source ownership`; two fully known excluded
CC controls passed. Both catalog-present and removed null/null sync cases failed
the complete-history assertion. They now pass, including two successive syncs,
unchanged null bindings, correct amounts and stable history. Additional
regressions reject included ambiguity and malformed explicit excluded values.

**Disposition**: Remediated in cycle1. The independent re-review was pending at that point and later closed it (see the final re-review section below).

## Security checklist summary from initial integrated review

No independent penetration test or resource-stress result is claimed.

| Area | Review summary / applicability |
| --- | --- |
| Prompt injection | N/A: no runtime LLM, prompt execution or agent in this feature. |
| Sensitive information disclosure | Reviewed privacy masking, generic error bodies, no-store responses and no new secrets identified. Rework inputs/keys are synthetic only. |
| Supply chain | No new dependencies or manifest/lockfile edits identified. No dependency audit execution claimed. |
| Data/model poisoning and source integrity | Model/training poisoning N/A. Financial source integrity **failed initially** on QA-001/QA-002; the cycle1 remedies were closed by the final re-review below. |
| Improper output handling | Supplied review verified ordinary React text escaping; no new raw HTML sink identified. |
| Excessive agency | Fixed read-only GET; no sync, write, source fallback or autonomous action on read. |
| System prompt leakage | N/A: no runtime system prompt. |
| Vector/embedding weaknesses | N/A: no vector store, embeddings or retrieval-augmented model. |
| Misinformation / verdict integrity | Deterministic Decimal/ID/zero/partial flows reviewed; descriptive CC-only wording. The original source-integrity blockers still governed acceptance. |
| Unbounded consumption | GET has a fixed five-file read window. Arbitrary-length numeric resource stress was **unverified**, not a demonstrated vulnerability or a tested bound. |

## Nonblocking observations retained, not expanded into fixes

- Supplied review found no other high-confidence frontend correctness bugs.
- Superseded transport requests may finish; hook cleanup rejects their results.
- Pre-existing global navigation overflow is outside the card.
- Existing client build warnings: mixed static/dynamic import and large bundle.
- Arbitrary-length numeric resource stress remains unverified.
- No Ubuntu/native renderer, live-data, or new manual assistive-technology
  validation is claimed.

## Cycle1 verification and next gate

See [quickstart section 13](quickstart.md#13-integrated-qa-rework-cycle1--2026-10-31)
for exact commands, isolation bootstrap, full manifest and failure history.

- Before production fixes: **12 defect failures / 4 controls passed**.
- New strict client contract tests: **9 red failures** for the absent keyword;
  these are distinct from the runtime defect reproductions.
- Final defect selection: **16 passed**.
- Final affected backend selection: **448 passed**.
- Full Windows nonrenderer: **1220 passed, 2 deselected** (1184 baseline + 36 new).
- Initial full run: **1219 passed / 1 launcher failure** because Windows spawn
  could not reload `<stdin>`; `python -c` fixed the invocation, with no publisher
  or test changes. Existing Starlette/httpx deprecation warning remains.
- Migration: none in cycle1; additive schema 6 unchanged. Existing artifacts
  require explicit successful re-sync, never GET-time repair. No real re-sync ran in cycle1; a later real-data validation is recorded in [quickstart section 16](quickstart.md#16-post-rebase-real-data-validation).

Developer caveman self-review found no unresolved defect in the two-fix delta.
This is **not** independent approval. Reviewer must recheck both fixes and their
legacy/scope boundaries before closing T033; T034 final summary follows. The re-review below did this.
The earlier failed merged-plan gate remains failed under the recorded explicit
user continuation. No branch/rename, commit, push, PR, merge, extension edit or
publication occurred.

## Final independent re-review and coordinator acceptance

The final read-only reviewer passed the scoped code review with approximately
95% confidence, closing QA-001 and QA-002. It found no remaining Critical or
Important implementation defect:

- QA-001: strict opt-in pagination rejects an unconsumed next link at the cap;
  a terminal page at the cap succeeds, and legacy callers still truncate.
  Monthly and prior-month transaction/event fetches use the strict sync client.
  Actual-pagination regressions verify no new Bills files and byte-preserved
  existing Bills snapshots on failure.
- QA-002: Boolean exclusion permits null bindings without inventing them;
  included ambiguity and malformed explicit values still fail closed. Producer
  and repeated-sync tests cover catalog-present and retained-removed accounts;
  known owned CC exclusions still participate in the scope fingerprint.
- The reviewer verified the 36 added regression cases and accepted the recorded
  448 affected / 1220 full Windows test results. The unchanged consumer contract
  leaves the earlier 468 client tests, production build and eight synthetic
  browser scenarios applicable; these were not rerun during static review.

The reviewer's only caveat was inability to execute Git metadata commands.
The coordinator subsequently ran `git status --porcelain --untracked-files=all`,
`git diff --stat`, `git diff --cached --name-only`, `git diff --check`, and
`git branch --show-current`. The 45-path union is exactly the documented
18 backend, 15 frontend and 12 documentation files. The index is empty; all
changes remain unstaged/untracked. No sibling, dependency, lockfile or workflow
hook changes were found; the branch is the existing app-managed branch.
Thus the metadata caveat is resolved without altering the independent
reviewer's source conclusions.

Final acceptance is local implementation/verification only. It does not certify
Ubuntu, native rendering, real-data behavior or a merged-plan review. A later
real-data validation is recorded in [quickstart section 16](quickstart.md#16-post-rebase-real-data-validation).
The merged-plan review
remains failed under the recorded user continuation. Optional publication,
commit and unrelated bugfix-consistency hooks were not run. No source changes
were made after the final re-review, only completion documentation.

### Post-acceptance unmocked smoke

The parent session asked for one more check before local completion: a browser to
real-FastAPI to synthetic temporary storage smoke with no API response mocks. It
passed 182/182 assertions (ready, threshold change, legacy-history and
missing-snapshot states, privacy masking) with 22 real `/api` responses, all 2xx, and
zero failed requests, page errors, console errors or tripwire hits. The harness
changed no repository file and no source changed, so no re-review was needed. The
coordinator re-verified the 45-path Git status, the empty index, a clean
`git diff --check` and the absence of listeners on 5205 and 8105. The only caveat
is a disclosed in-memory removal of the bundle's default API origin so the page used a
same-origin `/api` path, as the Docker frontend does. Two defects outside this
feature (the `theme.css` accent hover contrast and the 390px navigation overflow)
were recorded in [quickstart section 15](quickstart.md#15-unmocked-real-api-browser-smoke---2026-10-31)
and left unfixed.

## Post-rebase review (real-data round)

An independent read-only review of the post-rebase delta (the rebase onto the main branch that gained the Runway feature, the real-data fix and the client review fixes) returned **pass-with-caveats, with no critical or high findings**. It reported ten findings: one Medium, three Low and six Info. The review-driven fixes are task T039.

| # | Severity | Finding | Disposition |
| --- | --- | --- | --- |
| 1 | Medium | Re-sync guidance was lossy: it told users to re-sync only the indicated five-month range | Fixed in the UI and in the documents. The guidance now starts at the first window month and runs through the usual sync end month (at least the current month), in one run under a consistent account/category configuration |
| 2 | Low | Timezone: in the first hours of a month the API clock and the browser clock can disagree about the current month | Documented as a known limitation, contract unchanged |
| 3 | Low | The two role-key strictness parametrizations missed several non-canonical key forms | Tests added (six forms in both parametrizations) |
| 4 | Low | A hand-edited non-ID `exclude` role key gives a generic `invalid_source` with no key detail | Documented, deferred |
| 5 | Info | Stale statements that no real re-sync ran | Replaced with a sanitized pointer to the real-data validation record |
| 6 | Info | The Runway header comment was lost in the rebase | Restored in the Bills page |
| 7 | Info | Stale comments on the no-store allow-list | Refreshed |
| 8 | Info | The detector GET lacked the no-store fetch option | Applied |
| 9 | Info | A route test is deterministic only because of the frozen test clock | Note added next to the test case |
| 10 | Info | Placement of the detector section in the README | Left as is, no functional value |

Final counts after these fixes: backend **1580 passed, 2 deselected** (non-renderer suite, isolated storage); client **49 files and 540 tests passing**; production client build passing. They replace the dated counts recorded earlier in this report, which stay as the measurements of their round. Both containment tests pass on the final tree.

The real-data validation, the rebase record and the known limitations are in [quickstart section 16](quickstart.md#16-post-rebase-real-data-validation). The final container rebuild and structural verification (T040) is performed by the coordinator after the documentation commit.

## Selectable-period review and deployment acceptance — 2026-11-02

**Historical/superseded scope**: This T047–T048 review and runtime evidence
applies to the prior multi-month evaluation interpretation. It is not
independent review or container acceptance of the corrected target/reference
contract.

**T047 provenance**: The coordinator's verification handoff reports an independent code-review **PASS with no significant issues** for the completed backend/frontend comparison-period amendment. This records the supplied independent result, not a new review performed by the deployment specialist. Synthetic acceptance is inherited from T045/T046: 374 backend tests, 181 targeted client tests, 594 full client tests and production client build passing. No unchanged full suite was rerun here.

**T048 executed evidence**: After confirming Compose ownership of the assigned worktree, the delegated verifier rebuilt API/frontend and recreated those services only. Both remained healthy at `127.0.0.1:8080` with the original `pocket-smith-reports_private-data` mount. The actual unmocked browser smoke passed **164 assertions**, observing six detector HTTP 200 responses across 24 API responses. Default September–October and single October selections were ready. May–September and May–October correctly displayed insufficient history, with exact requested/evidence dates and no stale verdicts. A partial response was not present in this real dataset; synthetic coverage remains the evidence for that state.

Controls, explicit query/response identity, one-request Apply behavior, accessible invalid drafts without requests, all rendered month shapes, single-month no-sustained semantics, threshold/range preservation, privacy without network requests, direct/nav entry after `aria-busy=false`, and Bills isolation passed. Page/console/connection/HTTP errors, cross-origin requests, non-GET requests and sync requests were all zero. No raw body, finance value, identity or screenshot was persisted; browser helpers were closed and the actual stack remains running. No application fixes were necessary.

Exact commands, sanitized dates/statuses/counts, documentation manifest and session artifact names are recorded in [quickstart section 18](quickstart.md#18-selectable-comparison-period---2026-11-02). **Historical checkpoint: 48/48 tasks complete** for that superseded interpretation. The original failed merged-plan gate remains failed, and no commit, branch change, publication or governance override is claimed.

## Corrected-contract review and container/browser smoke — 2026-11-02

### T052 independent read-only review

The independent reviewer examined the corrected API/service/model, client
controls/hook, tests and documentation and returned **PASS, no significant
issues**. The one earlier finding was a local-browser/API-clock month rollover:
the default target could be current on the API clock and return 400. The
corrected implementation fails closed: a current API-month target returns
200 `insufficient_history`, no partner money, and detects current/open
evidence before storage path resolution or snapshot reads. Future and malformed
selections remain 400. Targeted API tests cover the current target and no-path
resolution behavior. The final five-file backend run passed 283 tests with one
pre-existing Starlette TestClient/httpx deprecation warning.

### T053 corrected-contract runtime verification

The coordinator built API/frontend with `docker compose -p pocket-smith-reports
build api frontend` and started them with
`docker compose -p pocket-smith-reports up -d api frontend`. Both services were
healthy at frontend `127.0.0.1:8080`; the existing
`pocket-smith-reports_private-data` volume remained mounted. No sync or writes
to real data occurred, and no service shutdown or volume deletion was done.

Unmocked Chromium used same-origin requests only with DNS blocked except
`127.0.0.1`. Direct deep link and navigation entry passed; the tab reported
`aria-current=page`, and Bills had zero detector cards/requests. Default
target 2026-10/reference 2026-07..09/threshold 20 returned ready/200 and echoed
the selection, with four evidence months, one evaluation, two partners and 35
categories. Custom target 2026-09/reference 2026-04..08 returned
`insufficient_history`/200, echoed its selection, and included the six
required evidence months without category data. Reversed range was
`aria-invalid=true` and added no request. Combined browser errors, failed
requests and external-origin requests were zero. No amounts, partner labels,
raw response bodies or screenshots were captured.

Final client evidence was **7 targeted files / 139 passed**, **50 full-suite
files / 552 passed**, and passing `pnpm build` (2611 modules; existing mixed
static/dynamic import and >500kB chunk warnings). Containment passed 9 tests on
the pre-documentation-update tree and is rerun after this documentation edit.
The quickstart section 19 contains the exact test/build/container commands and
sanitized results. **T049–T053 complete; 53/53 tasks checked, zero pending.**

## Visit-local category visibility final acceptance — 2026-11-02

**T055 review provenance:** the final-verification assignment explicitly supplied an independent code-review **PASS** for the completed T054 implementation. No blocking findings were reported. The final verifier did not run another code-review agent or represent runtime checks as independent code review.

**T056 runtime verdict: PASS.** Ownership/mount metadata was verified before updating only the assigned project's frontend. `docker compose -p pocket-smith-reports build frontend` and `up -d --no-deps frontend` passed with `APP_PORT=8080`; API was not rebuilt/recreated and its existing `pocket-smith-reports_private-data` volume was retained. Both services were running/healthy after deployment.

Chromium passed **67/67 actual assertions**, not proxy tests: **58 synthetic** verified keyboard Hide/Show hidden/Restore/Restore all, coupled row/disclosure visibility, duplicate-title/stable-ID partner isolation, all-hidden recovery, masking of hidden-shown and collapsed monetary markup, zero visibility-action fetches, retained choices through threshold/selection/loading/error/Retry, fresh-route reset and mobile table scrolling. Six synthetic detector requests were expected across fetch/route scenarios. **9 unmocked structural-only** assertions confirmed live deep-link/API HTTP 200, ready state, controls and structural counts (2 partner regions, 2 tables, 35 rows, 37 disclosures). Both contexts had zero runtime/console errors, failed requests, unexpected routes and external-origin requests.

Synthetic routes were installed before navigation, dynamically echoed selected months/threshold and blocked unexpected APIs/external domains; only the separate live context allowed the read-only detector GET through. The live check did not inspect/log monetary text, identities or response bodies and captured no screenshots. Harness corrections (browser executable path and Retry history selector) did not require application changes.

The T054 baseline remains **7 targeted files / 145 tests**, **50 full-suite files / 558 tests** and passing client build. The final frontend image build passed again with the same existing Vite warnings; unchanged client suites were not rerun. Bills isolation is covered by that existing suite, not a new browser scenario. Exact commands, sanitized results, scope and session-only evidence names are in [quickstart section 20](quickstart.md#20-visit-local-category-visibility--2026-11-02).

**Final state: 56/56 tasks checked; zero pending.** This final-verification slice changed only the four planning/status documents and appended a sourced fact to ignored `memory.md`. No implementation defects, dependency changes, API changes/rebuild, sync, private-volume modification, commits or remote publication occurred. The verifier's browser was closed; actual API/frontend containers remain running.

Post-documentation containment passed **9 tests** using the required locked/no-sync command with `PYTHONPATH=src`, `BILLS_CALC_LOG=0`; `git diff --check` passed. These checks were repeated after recording their results.
