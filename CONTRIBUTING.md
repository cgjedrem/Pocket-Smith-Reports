# Contributing

Issues and pull requests are welcome. This is an open-source project: good-quality contributions are merged even for features the maintainer does not personally use.

## How to contribute

- **Bug fixes:** open a pull request directly. Include a test that fails without the fix.
- **Features:** open an issue first describing what you want to build and why, and wait for a response before investing serious time. This protects you from building something that cannot be merged.

## Quality bar

- All tests pass: `pytest` for the Python side, `pnpm test` in `client/` for the frontend.
- Match the existing code style of the module you are touching.
- One change per pull request — no drive-by refactors mixed into a feature.
- New code comes with tests.
- **No personal identifiers in the tracked tree.** The containment guard
  `src/mom/tests/test_lg002_identifier_containment.py` fails CI if any of the
  launch-gate identifier strings (content, tracked path, or base64 literal)
  appear outside the LG-002 governance carve-outs. If a test legitimately needs
  the old v1 values (e.g. legacy-section fixtures), assemble them from string
  fragments at runtime instead of writing the literal; see
  `src/budget_api/tests/reports/test_contract_v2.py` for the pattern.

## Verification and handoff policy

Policy revision: 1.0.0 (2026-09-15). Applies to contributors and agents working
in this repository; it does not authorize live sync, private-data publication,
Git mutations, or work in another checkout.

### Evidence contract

Keep separate rows for **static review/checks**, **build**, **automated tests**,
**runtime integration**, and **user acceptance**. A passing build or unit test
does not prove browser behavior, live PocketSmith behavior, PDF rendering, or
user acceptance. A test named "acceptance" remains automated-test evidence
unless it actually exercises and records the required acceptance scenario.

For each required scenario, record:

| Field | Required content |
| --- | --- |
| Identity | Row ID; commit SHA plus dirty-diff/content identity, including relevant untracked files; tested artifact path and hash/build ID. A SHA alone cannot identify a dirty checkout. |
| Environment | Timestamp with timezone, absolute checkout and served-process checkout, OS, Python/Node/browser versions as relevant, API endpoint, renderer availability, sanitized config and fixture/snapshot identity. Record schema/calculation version and data freshness when relevant. |
| Scenario | Requirement, initial state, action/transition, expected outcome, numeric units/tolerance and duration bound agreed before testing. |
| Observation | Exact observed values in quotes, compared with expected values; command, exit code, test scope, timestamped start/end and measured elapsed time for duration claims. Do not replace observations with "looks right" or estimated timings. |
| Provenance | Executor or reporting user, evidence type, local log/screenshot/report locator and artifact identity. Separate direct observation, quoted user report, inference, and unknown. |
| Verdict | `pass`, `fail`, `blocked`, `inconclusive`, or `not-run`; reason, owner, and next check. Use `not-applicable` only with a recorded scope justification and reviewer approval. |

`blocked` means a prerequisite, permission, tool, environment, or execution owner
is unavailable. `inconclusive` means evidence is incomplete, conflicting, or
cannot establish the claim. Neither means pass. Missing duration or revision
identity makes the corresponding acceptance claim inconclusive. Quote user
reports faithfully; unverified environment or build identity remains unknown.
Keep private financial data and credentials out of tracked evidence and public
PRs. Use synthetic fixtures and sanitized excerpts; retain full logs locally in
an approved private location, with a safe locator rather than publishing them.

After code, configuration, fixture, artifact, or behavior-affecting review
changes, mark affected rows stale and reopen them as `not-run`. Preserve the old
observations as history, not current acceptance. Record the changed identity and
affected rows; if the impact is uncertain, reopen the broader integration scope.
Review-only findings that challenge an assumption also reopen affected rows.
Carry forward unaffected results only with a recorded impact rationale. Rebuild
affected artifacts, rerun checks, and request fresh user acceptance where affected.

### Integration regression matrix

For a changed boundary, test the decision logic directly with deterministic
fixtures, then test the connected system in its actual runtime. Record expected
and observed outcomes separately for each applicable row below; expand the matrix
for the change, and justify exclusions rather than silently skipping them.

| Boundary | Happy path and adjacent states | Negative path and recovery |
| --- | --- | --- |
| PocketSmith sync to local snapshots | Empty, one-page and multi-page results; first sync and repeat sync; prior snapshot retained during work | Timeout, denial/rate limit, malformed response, missing ownership mapping, interrupted sync; retry and verify no partial publication or duplicate results |
| Snapshot/API to React client | Fresh and older schema; absent field, `null`, legitimate zero, positive and negative values; past/current/future month and month-window edges; initial load and refresh | Missing/stale snapshot, API error, delayed/out-of-order response, unmount or month switch during a request; retry, warning cleanup, and no fabricated fallback data |
| Financial derivations across months | Current/prior/next-month inputs; real versus estimated values; refunds, transfers, excluded accounts and partner isolation | Missing prior month, stale balance date, unmapped category, changed calculation version; verify affected historical snapshots and independently computed totals |
| HTML/PDF publication | Valid paired outputs, repeated generation and concurrent reads using artifact identity | Missing native renderer, empty/invalid PDF, lock timeout or interrupted publication; prior output preservation, rollback and recovery |

Fakes prove our response to supplied events, not that PocketSmith, a browser, or
a native renderer produces those events. Route live, browser, or renderer checks
to an authorized executor; absent credentials or a renderer means blocked, not
permission to sync or substitute static evidence.

### Review gate and ownership

1. Before implementation, agree on scope, expected outcomes, affected matrix rows,
   execution owner, and any manual/user checks. Use read-only QA for review.
2. After implementation, have QA review the current diff and evidence. QA reports
   findings without editing files or running commands with side effects. For mixed
   static/runtime requests, return the static findings and mark execution checks
   blocked/routed to an execution-capable owner.
3. After every review fix, reopen affected rows and repeat the affected checks and
   review. Final handoff requires current evidence, resolved findings, and explicit
   disposition of exclusions. Required blocked, inconclusive, stale, or not-run
   rows prevent an acceptance/readiness claim; the user decides any scope deferral.
4. Report build, static review, automated tests, runtime, and user acceptance
   separately, including checks not run. Stop at the agreed permission/approval
   boundary; evidence does not itself authorize commit, push, merge, or release.

**Enforcement limit:** this is a procedural post-review gate, not an installed
agent hook or automated acceptance gate. `.github/workflows/ci.yml` runs Python
tests on pull requests and configured pushes; it does not validate this evidence
contract or respond to review completion. Windows excludes `pdf_renderer` tests,
and CI does not run the frontend tests/build. Contributors must run applicable
checks separately and record the gaps. No Spec Kit, generated command surfaces,
or repo agent definitions are present for automatic gate wiring.

Use this status format at handoff:

```text
Current task / revision + artifact:
Current owner / next execution owner:
Check type / mode (automatic, manual, or user acceptance):
Latest observed result / evidence locator:
Open or stale rows / blocker / unknowns:
Next action / stop condition / required approval:
```

Route risky or uncertain financial, cross-layer, data-migration, or publication
work to higher-capability reasoning and an executor with the required tools and
permissions. Do not pin a model name or claim one model caused a better outcome
from an uncontrolled comparison. Do not poll idle workers or invent ETAs.
Before a model/owner switch, provide the exact failure and reproduction, revision
and environment, attempted fixes with results, relevant logs, current hypothesis
(labelled as such), unknowns, and the smallest test that could falsify it. Name
the receiving owner and stop condition; switching does not reset evidence or
authorize another attempt with side effects.

### PowerShell and native commands

Use the patch/editor tool for authored files. In Windows PowerShell 5.1,
`Set-Content -Encoding UTF8` **adds a BOM**; omitting the encoding is not a
BOM-free UTF-8 workaround. For script serialization, use
`[System.IO.File]::WriteAllText($path, $text, [System.Text.UTF8Encoding]::new($false))`
and verify the resulting bytes contain no leading BOM or unintended U+FEFF.
Do not rely on PowerShell 7-only syntax in 5.1 instructions.

Capture `$LASTEXITCODE` immediately after **each** native command and gate every
dependent step on that code, including dependency installation. For example:

```powershell
python -m pytest src/budget_api/tests -q
$code = $LASTEXITCODE
if ($code -ne 0) { exit $code }
# Only now proceed to an authorized dependent step.
```

Use the same rule for `pnpm`, `git`, and `gh`. `$?`, the last pipeline command,
or a displayed log tail is not the native process exit code. Preserve full logs
privately and show concise excerpts. When an authorized GraphQL request reads a
query file, use `gh api graphql -F query=@<file>`, not `-f`; review-comment
identity is `author`. These examples grant no permission to post or mutate Git.

## What to expect

- PRs are merged or declined **with reasoning**. A decline is about quality, scope, or maintainability — never about whether the maintainer personally uses the feature.
- CI must pass on both Ubuntu and Windows before merge.
- This project is maintained at a personal pace; there are no response-time guarantees.

## Conduct

Be civil and be patient — this is a personal project maintained in spare time. Hostile, entitled, or abusive behavior gets one warning; repeat behavior closes the thread.