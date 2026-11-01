# Feature 003 — independent reviews and bounded backend remediation

**Date:** 2026-10-31
**Independent review 1 verdict:** **FAILED — 3 Important findings.**
**Source:** Independent reviewer findings supplied in the backend rework request.
The reviewer reported no other high-confidence backend/frontend bugs and did not
rerun tests or inventory Git. Those statements are the supplied review record,
not a new frontend audit by this backend pass.

**Independent review2:** The supplied continuation identifies one residual
QA-001 fingerprint collision (**98% confidence**). Prior QA-002/003, RT-001,
HTTP evidence/cleanup and RT-002 baseline attribution are retained as accepted
in that supplied continuation, not independently re-approved by this implementer.

**Current disposition:** Final bounded independent review3 is **PASS WITH
CAVEATS**, with no remaining in-scope defect. Residual QA-001 is closed at
**99% confidence** after the type-preserving fix and **36 new regressions**.
**T034 is approved and complete for local handoff.**
Prior **real HTTP** built-browser acceptance and actual guarded Linux native
rendering evidence are retained, not rerun for this internal fix.
**RT-002 diagnosis is complete: the same
readiness timeout reproduces on unchanged HEAD without runway or its isolation
helper in the same synthetic Linux environment.** This is a baseline
collection/spawn-startup limitation, not feature test leakage. Linux canonical
is still not claimed green. **T033 technical objectives complete**.
This grants local technical QA approval only, not human acceptance or
publication permission. Historical pending statements below are superseded by
the final review record.

**Update 2026-11-01:** a post-review real-data defect, RD-001 (PocketSmith
`is_transfer: null` excluded every real month), is fixed by task T035. See the
RD-001 section below. It is outside the review3 verdict and has its own bounded
review (pass-with-caveats) in that section.

## RD-001 real-data finding — 2026-11-01

**Status:** fixed, reviewed and committed as a follow-up to `897a49e`. Outside the
review3 verdict. **Severity:** blocking for real users: runway stayed
"insufficient history" on real data.

### Observed

The committed feature was run against real PocketSmith data from the Docker
deployment. Only schema, type and count information was inspected; no amounts,
payees or other transaction contents were printed or recorded. All three
candidate months reported `status=excluded`, `coverage=invalid` and issue
`invalid_source`.

### Root cause

`_flag()` in `services/runway.py` accepts only literal booleans, so JSON `null`
raised `InvalidSource`. `_observe()` read the transaction `is_transfer` through
it and rejected the whole month. Real PocketSmith transactions carry
`"is_transfer": null` on a large share of rows. In each of the three months the
null share ranged from roughly one row in eight to about three in four; the other
rows were `true` or `false`. Every other field in those months passed validation.

### Fix

`_transfer_flag()` reads PocketSmith-sourced `is_transfer` flags: null or absent
means not a transfer, and a non-null value must be a literal boolean, otherwise
`InvalidSource` as before. It is used at exactly four read sites: category
catalog rows and the embedded-category check in `_classification`, and the
transaction and category flags in `_observe`. This matches
`v4_pipeline/accounting.py` (`normalize_transactions`: `None` is `False`; any
non-null value goes through `_literal_transfer_flag`). `_flag()` stays strict
everywhere else, notably the account-binding `excluded` flag: it is
user-authored, the app only writes booleans there and the pipeline also
requires a literal boolean.

### Regression tests, red first

49 new cases in `tests/runway/test_calculation.py` and `test_api.py`, with
`pocketsmith_transaction`/`pocketsmith_month` fixtures in
`tests/runway/synthetic.py`: full real field set, synthetic values, mixed
null/true/false flags, bare top-level list with no provenance block. Before the
fix **9 failed, 40 passed**; after the fix **49 passed**.

- Red before the fix: null flag at each of the four read sites (4 cases), mixed
  null/false/absent/true transaction totals, null category flag not masking other
  exclusion rules, whole-result equality of null versus false, and the
  PocketSmith-shaped three-month result (service and HTTP route).
- Guards that pass before and after: `true` still excludes at every site; `false`
  and absent still count; non-boolean `"true"`, `"false"`, `1`, `0`, `""` and
  `[]` still invalidate the month (transaction, embedded category) or fail the
  catalog closed; binding `excluded` stays strict for `null`, `"false"` and `0`;
  fixture shape pin.
- Totals are asserted against hand-computed numbers, not derived from the service.
- Local Windows runs after the fix: 264 runway, 918 API and 1256 canonical
  passes, with the two existing `pdf_renderer` exclusions.

### Before and after on real data

Before: all three candidate months excluded with `invalid_source`. After: a
diagnostic that treated null as `false` made all three months `included` with
coverage `unverified` (top-level list, no provenance block), qualification
`coverage_unverified` only, and no further raise site on that data. Not verified
here: calculated amounts on real data; the later validity rerun on the rebuilt
stack (statuses only) is in the evidence ledger below.

### Independent RD-001 review — 2026-11-01

Bounded read-only review of the delta: **pass-with-caveats**. Code correct at all
four sites, no weakening of the transfer exclusions, parity with
`v4_pipeline/accounting.py` and Bills confirmed, tests pin hand-computed numbers.
The reviewer had no shell, so test counts above are developer-run, not
reviewer-run. Caveats and dispositions:

- Evidence ledger (I-1): see the ledger below.
- Real-data reconciliation (I-2): the validity gate was rerun on real data (see
  ledger); the exclusion of card repayments and transfers on real data was not
  reconciled against the production non-transfer total. Rows with null on both
  flags now count unless a category, title, role, section or account rule excludes
  them; production has the same blind spot (A-004). Left as an open risk.
- Minor, not changed: no test with null at transaction level and `true` on the
  category, no float non-boolean case; `status` outside posted/pending remains the
  one strict check without production precedent (recorded as a risk). A bad
  catalog `is_transfer` flag yields a global `invalid_source` (no month included),
  as `data-model.md` states.

### RD-001 evidence ledger

Base: feature commit `897a49e`; the fix is a follow-up commit on the same branch.

| Row | State |
|-----|-------|
| Windows runway / API / canonical suites (264 / 918 / 1256) | run on the fix tree |
| Frontend unit and build | carried forward: no client change, client never reads runway `is_transfer` |
| Real-HTTP browser scenarios (synthetic, boolean flags only) | carried forward: behaviour identical for boolean-only data; does not cover the null path |
| Linux/Debian run | stale for the 49 new tests: not run |
| Null input through real HTTP on synthetic data | not run |
| Real-data validity rerun in the user's Docker stack | done on the rebuilt stack: 3 of 3 candidate months included, selection `unconfigured` (no liquid accounts chosen yet), household `unavailable`; only statuses were read |
| Reconciliation of runway spend against production non-transfer total | not run |
| Human usability, screen reader, native renderer, remote review | unverified |

Rationale for carry-forward: the change only turns a previously invalid JSON null
into "not a transfer" at four backend read sites; the response shape and UI are
unchanged.

### Why the tests missed it

Fixtures and fakes always supplied booleans. CONTRIBUTING's integration
regression matrix lists absent-field and `null` states for boundaries that read
PocketSmith-shaped snapshots, and notes that fakes prove only our response to
supplied events, not what PocketSmith produces. The runway fixtures never
exercised `null`. Synthetic fixtures now include null `is_transfer`, not only
booleans.

## Final independent review3 — 2026-10-31

**Reviewer:** independent `qa-reviewer`, final bounded iteration 3 of 3.
**Status:** pass-with-caveats. **Findings:** none in the targeted change.

The reviewer inspected `services/runway.py:493-514`, its parser/consumers, all
32 new calculator/identity cases and four endpoint cases. Recursively tagged
tuples distinguish Decimal values from user arrays/objects at every depth,
including bool/int equality boundaries. Sorted string-key pairs preserve
object-order independence; representations are compared directly rather than
through potentially colliding digests. No residual collision or blocking
coverage gap was identified.

Recorded red/green evidence is consistent: 19 failed/17 passed before the fix,
36 passed afterward; 215 runway, 869 API and 1207 canonical Windows passes with
two existing renderer exclusions. Recorded 10,000-transaction service medians
are 154.280ms (integer) and 161.236ms (Decimal), maximum 295.820ms. These are not
new browser measurements.

Earlier accepted QA-002/003, RT-001, real HTTP acceptance/cleanup and RT-002's
verified baseline disposition remain closed. The review was static/read-only,
not a test rerun. Frontend 414/build and seven real-HTTP scenarios remain
historical accepted evidence; Linux canonical remains 1172 passed/one baseline
failure. Human, screen-reader, Ubuntu-specific and remote-review checks remain
unverified/nonblocking. The bounded OWASP assessment found no new applicable
issue; runtime-LLM categories remain not applicable.

The coordinator separately obtained fresh Git status/diff inventory, confirming
the backend/frontend/specification manifests and unchanged
local feature branch, with `git diff --check` passing. At that point no commit,
push, pull request, remote approval or additional review iteration had been
performed.

## Review2 residual QA-001 — local remediation, review3 pending

**2026-10-31. Source:** independent review2 finding supplied in the direct user
continuation; **98% confidence**, FR-008. This pass reproduces and fixes that
one finding. It is not another broad review or an independent QA verdict.

### Reproduction and root cause

Pre-fix `services/runway.py:493–495` serialized a `Decimal` as the ordinary JSON
array `["decimal", str(value)]`. A valid numeric amount **`-100.0`**, decoded by
`_decode` as `Decimal("-100.0")`, therefore shared its fingerprint with the
malformed array **`["decimal", "-100.0"]`**. The duplicate short circuit at
pre-fix lines **538–548** ran before monetary validation.

- Same-ID July copies, valid numeric first: July incorrectly remained included.
  Array first: July was excluded. Both orders now exclude July.
- Numeric July copy plus crafted array copy in August **retaining July's date**:
  July incorrectly remained included, even when candidate-source scan order was
  reversed. Both referencing months now have `coverage="invalid"`, null spending
  and `invalid_source`; only September remains, so burn/runway are unavailable.
- Swapping which source holds the numeric/array copy is also covered. Previously
  malformed July and out-of-month August happened to reject both independently;
  it did not prove the identity pre-scan was collision-free.
- Nested metadata Decimal/array lookalikes also reproduced missed conflicts in
  both record orders, despite metadata not contributing to spending.

**Red phase:** **19 failed / 17 passed / 134 deselected**, one existing warning,
**1.92s**, before the production edit. The failures are 4 calculator amount/order
cases, 10 nested metadata cases, 3 type matrices and 2 real-route cases.

### Narrow fix and exact regression inventory

Only production change: `services/runway.py::_fingerprint`. Identity now uses
recursively tagged immutable tuples for object/array/Decimal/null/bool/int/string/
float values, rather than JSON with an untagged Decimal replacement. Objects keep
sorted string-key/value pairs; arrays retain order; every child is encoded.
Source-shaped arrays/objects cannot imitate a scalar encoding. Equality compares
the full canonical representation, not a digest.

Preserved semantics: `_decode` still uses `parse_float=Decimal` and rejects
duplicate object keys. Decimal text retains decoded scale/sign without rounding
or context-sensitive normalization. Integer, Decimal, bool and string values
remain distinct; already equivalent decoded spellings (`-100.0`/`-1.000e2`,
escaped strings, object-key order) stay equivalent. The decoder's nonstandard
NaN/Infinity float constants have deterministic typed encodings; `_money` still
rejects them. No parser, monetary/date/category validation, identity pre-scan,
month invalidation, route, model, harness or frontend changes.

**36 added regressions** (`32` calculator/identity, `4` API):

| Test in `tests/runway/` | Cases | Assertion |
| --- | ---: | --- |
| `test_fingerprint_amount_array_conflict_is_order_independent` | 8 | Same/cross-month × source order × numeric/array placement; all affected months invalid, cross-month burn/runway null. |
| `test_fingerprint_decimal_repeats_count_once` | 2 | Genuine decimals plus nested key-reordered metadata, both record orders; A spends 100/month, household mean 60,100. |
| `test_fingerprint_nested_metadata_lookalikes_conflict` | 12 | Six scalar/array/object/sentinel-shaped metadata pairs × both record orders. |
| `test_fingerprint_parsed_types_and_tag_lookalikes_never_collide` | 3 | 28 parsed values at scalar/array/nested-object depth; distinct types, keys, ordering, scale/sign, extreme exponents/precision and serialized canonical lookalikes. |
| `test_fingerprint_preserves_equivalent_decoded_values` | 4 | Parsed integer zero, equivalent Decimal exponent, escaped string and nested key-reordered object equality. |
| `test_fingerprint_nonfinite_duplicate_amount_stays_invalid` | 3 | Repeated NaN/±Infinity amounts remain invalid, never silently accepted. |
| `test_fingerprint_amount_array_conflict_on_result_route` | 4 | Same/cross-month × numeric/array placement through real ASGI route; 200/no-store, invalid/null observations, no source writes. |

### Validation and final bounded handoff

All commands use the existing installed Windows Python **3.13.7**, pre-import
`BILLS_CALC_LOG=0`, synthetic temporary fixtures and the unchanged isolation
runner. No dependency installation/change, Docker, live service, private source,
real env, main checkout, frontend edit, agents/nesting, commits, push or PR.

| Check | Result | Time |
| --- | --- | ---: |
| Added fingerprint regressions | **36 passed / 134 deselected**, 1 warning | 0.88s |
| Entire runway subtree | **215 passed**, 1 warning | 10.68s |
| Entire API backend subtree | **869 passed**, 1 warning | 27.48s |
| Canonical Windows four trees | **1207 passed / 2 existing renderer deselections**, 1 warning | 40.88s |

Counts supersede **179 focused / 1171 Windows canonical** only; each grows by
36. Prior Linux **1172 passed / 1 baseline lock-startup failure** stays historical
and non-green; no broad Linux rerun or baseline repair.

Five service calculations per 10,000-transaction/20-mapping fixture, before and
after, with identical frozen NOW: integer median **133.034→154.280ms**
(**+21.246ms**), decimal median **142.855→161.236ms** (**+18.381ms**).
Post-fix maximum **295.820ms**. Exact valid response SHA-256 is unchanged for
both datasets. Local service-only measurements, not new HTTP/SC-005 acceptance
or a production latency guarantee. Prior seven HTTP scenarios, screenshots,
**1047.450ms initial / 267.264–305.396ms refresh / 934.002ms save** and
**5203/8103 cleanup** remain accepted historical evidence; no browser rerun.

Exact commands, all raw timings and response hash:
[quickstart residual QA-001](quickstart.md#review2-residual-qa-001--2026-10-31).
Changed files: `services/runway.py`, `tests/runway/{test_calculation,test_api}.py`,
this report, `quickstart.md`, `tasks.md`, root `memory.md`. **No migrations.**

**Self-review:** 🔴 no new bug found in this bounded change; 🟡 service medians
rose by 18–21ms locally, well below the 2s fixture bound; ❓ none.
This is implementer self-review, not QA approval. **T034 stays unchecked
(33/34 original tasks)**. Final independent review3 should inspect only this
residual fix/regressions and evidence consistency, retaining accepted prior
fixes/runtime/baseline disposition. Human/screen-reader/Ubuntu-specific/remote
checks remain **unverified/nonblocking** for local handoff, not passed.

## Historical bounded backend continuation — before review2

**2026-10-31.** Only subprocess guard/tests and handoff docs changed in the
repository. No frontend/production code, architectural change, dependency/lock
change, migration, subagent, branch mutation, commit, push or PR.
Exact commands and HTTP recipe:
[quickstart.md](quickstart.md#bounded-backend-rework-and-real-http-acceptance--2026-10-31).

### RT-001 — remediated locally; independent verification next

`src/budget_api/tests/isolated_run.py:71–88,111–114` adds an exact Linux
read-only library-cache lookup policy. Only `/sbin/ldconfig -p` or
`/usr/sbin/ldconfig -p`; resolved path must remain in that set, root-owned regular
executable, no group/other write permission. Exact stdin/stderr `DEVNULL`,
stdout `PIPE`, locale-only env. No arbitrary args, relative/temp executable,
untrusted symlink, shell, executable/cwd override, pre-exec hook or positional
options. Protected-path/network guards and strict temporary-PDF `pdftotext`
policy unchanged.

Added **21 regressions** in `tests/runway/test_isolation.py`: two permitted
lookups reach intercepted launch; nineteen unsafe variants denied.
Red **2 failed / 19 passed**. Windows green: **45 isolation**, **179 focused**,
**1171 canonical passed / 2 existing renderer exclusions**.
Native Windows UTF-8 JSON→HTML→PDF/extraction target **1 passed**.

Debian 12 / Python 3.13.18, actual WeasyPrint 70 and Poppler, guard active:

- Target set **50 passed, 2 warnings in 109.76s**, including all four original
  native failures and publisher-lock contention.
- Canonical four trees, **no exclusions: 1172 passed, 1 failed, 2 warnings
  in 170.92s**. All four native tests pass.
- Each run records **26 real `/sbin/ldconfig -p` launches and one real
  `/usr/bin/pdftotext` launch** with an isolated temporary PDF.
- Physically isolated staged inputs only; same network-none/read-only/limited
  recipe. Existing owned image was absent; recreated entirely from cached
  install layers, then removed its tag. Both own containers auto-removed.

Artifacts: `runway-linux-rework-commands.json`, `runway-linux-rework-stage.json`,
`runway-linux-output/runway-linux-rework-{target,canonical}.json`.
Historical pre-fix evidence below remains separate.

### RT-002 — baseline attribution verified; narrow diagnosis complete

**2026-10-31, subsequent diagnosis only.** Read-only `git show` staged baseline
**`979a01c5daca080cd141bfdb2c82970488998018`** (150 files) versus the changed
worktree (159 files). Baseline has no runway files or `isolated_run.py`; shared
source content differs only in `budget_api/main.py` (line endings normalized).
Same two public synthetic fixtures, dependency lock, pinned Debian 12 /
Python 3.13.18 image, Windows-to-Linux read-only bind mounts, network none,
2 CPUs / 2 GiB, 300-second container bound. No worktree/private-data mount.

**Decisive baseline reproduction:** original evidence runner, guard **absent**,
canonical four-tree collection and its first 114 tests in unchanged order:
**113 passed / 1 failed / 880 diagnostically deselected in 104.92s**.
Failure is exactly `test_accounting.py:1197`, `ready.wait(5)`, not the
publisher-lock contention assertion. No diagnostic process wrappers or
faulthandler enabled in this run. The changed original runner also fails with
all four trees collected and just that lock selected:
**1 failed / 1172 deselected in 27.45s**. Prior changed canonical result remains
**1172 passed / 1 failed**; no new full-suite run was needed.

**Mechanism and leakage exclusion:**

- Canonical lock is item **114**, before every runway test. Collection alone
  reproduces failure on both changed+guard and baseline-without-helper, so no
  earlier feature test/fixture execution is required.
- Legacy `mom` modules/sections and v4 conftest/build repeatedly prepend
  `sys.path`. Captured parent paths have **30 entries baseline / 32 changed**.
  Spawn inherits that list, then reexecutes the evidence runner as
  `__mp_main__`; its top-level `import pytest` searches those mounted paths
  before the child can import `_hold_publisher_lock` and call `ready.set()`.
- A four-second child stack capture is in
  `multiprocessing.spawn.prepare → _fixup_main_from_path → runpy.run_path →
  import pytest → importlib._path_stat`. Baseline child main imports took
  **0.422s–4.417s** after interpreter startup. That timing probe narrowly
  **passed**; this is variable startup latency, not deterministic lock failure.
  The uninstrumented baseline collection-only probe also passed once; the
  uninstrumented baseline canonical-prefix failure above establishes that
  baseline can exceed the unchanged bound.
- Diagnostic-only removal of duplicate `sys.path` entries, retaining first
  occurrence and every unique directory, reduces the changed list **32→11**:
  unchanged lock **passes in 2.397s**; child main imports finish at **1.577s**.
  No such workaround was applied to repository code or canonical results.
- Captured spawn argv is the normal `-c ... spawn_main(...)`, **not** the
  isolation helper's guarded `Popen` child wrapper. POSIX multiprocessing uses
  `spawnv_passfds`/`fork_exec`. Failed diagnostic holders exit **0**, with no
  active children before or after. `private_defaults` cannot explain a failure
  reproduced without the helper; the child explicitly sets its synthetic
  output path. Pathlib test patches have no earlier executed runway test here.
- Additional adversarial order: **all 179 runway tests first, then unchanged
  lock**, guard active, no instrumentation/path deduplication:
  **180 passed in 28.11s**. This includes the guard's subprocess/path regressions.

**Disposition:** non-feature baseline startup/collection limitation in this
specific staged Docker Desktop Linux environment. Not a publisher algorithm
defect, not a claim about every Linux host, and not a green canonical result.
No production/harness/test changes, timeout relaxation, arbitrary subprocess
allowance, canonical skip or dependency change. Stop diagnosis here.
Only **RT-002 triage** is checked; **T034 / independent QA2 remain pending**.

Exact commands, intermediate outcomes and cleanup:
[quickstart RT-002 record](quickstart.md#rt-002-last-test-diagnosis--2026-10-31).
Session artifacts: `runway-rt002/{manifest.json,stage.py,run.py,harness/}`,
`runway-rt002/evidence/{baseline-original-prefix,changed-original,changed-feature-first}*.json`,
plus collection/stack/deduplicated-path diagnostics and per-run source snapshots.
This pass modifies only review-report, quickstart, tasks and durable memory.

### Real HTTP acceptance — seven scenarios passed

**2026-10-31T19:01:03.153Z–19:01:14.436Z**, built Chromium UI →
HTTP **127.0.0.1:5203** fixed proxy → actual uvicorn/FastAPI
**127.0.0.1:8103**. Temporary synthetic storage/ENV_FILE established before app
import; fake comment-only env, no credentials; NOW frozen. **No intercepted
API fulfillment, TestClient, sync or PocketSmith.** Server/browser response
hashes and request counts matched, with **13 real browser API responses**
plus one backend readiness response, four screenshots.

Dataset **10,000 transactions / 20 mappings / 1,442,752 bytes**. Unchanged
frontend identity/build verified. SC-005 bound **2000ms**:
initial **1047.450ms**, refreshes **305.396 / 267.264 / 298.670ms**,
A-only PUT/recompute **934.002ms**, empty PUT/unavailable **919.004ms**.
Action→HTTP→asserted DOM→two animation frames; no artificial delay.
Linux canonical ran concurrently. No production latency guarantee.

Correct household **120,000 / 33,333 gross burn / 3.6 months**; real Bills 404
does not block panel. A-only **90,000 / 2.7** and null B reserves persist across
reload. Empty save renders explicit unavailable/null. Hide/show
**59.382 / 49.141ms** under SC-007's 1000ms, all monetary surfaces masked,
ratios and unsaved draft retained, zero requests. Scope/month/source/basis/
non-advice content checked, not human comprehension.

Artifacts: `runway-http-results.json`,
`runway-http-{happy,masked,saved,unavailable}.png`,
`runway-browser/{http-backend.py,http-serve.mjs,http-acceptance.mjs}`.
Four screenshots viewed. Both owned helpers exited **0**; PIDs **51004/51360**
absent, synthetic root deleted, source hashes/fake env unchanged, ports
**5203/8103 closed**. No user stack/private data/main checkout touched.

### Historical independent review2 scope

At this earlier handoff, QA2 was to verify QA-001/002/003 remediations, narrow RT-001 allow/deny policy and
preserved native extraction, actual HTTP evidence/cleanup, and RT-002 disposition.
No broad review loop or unrelated refactor requested.
The supplied review2 residual and narrower final review3 scope now appear above.
T034 remains unchecked; original checklist **33/34**.
Human SC-004 usability/time, SC-008 comprehension, screen-reader use,
Ubuntu-specific run and remote plan/review remain **unverified/nonblocking for
local implementation handoff** per user direction; no invented user-signoff gate.
Debian native-renderer execution is verified, Linux canonical is not green,
and the original publication gate is still NOT passed.

## Subsequent runtime evidence — not independent review2

**Historical IPC pass and pre-fix Linux attempt.** IPC results do not count as
full HTTP end-to-end acceptance. Current HTTP/RT-001/RT-002 disposition is above.

Direct autonomous continuation, **2026-10-31**. No subagents or repository
production/test-code edits. See the current runtime section of
[quickstart.md](quickstart.md#integrated-runtime-acceptance-and-cross-platform-attempt--2026-10-31)
for exact isolation, commands, measurements and screenshots.

### Historical IPC built-browser acceptance, not HTTP E2E

- **Seven real-backend Chromium scenarios passed**, four new screenshots,
  **13 actual TestClient responses**. Prior seven mock scenarios/eight screenshots
  remain separate; they were not added to backend-only timing to assert SC-005.
- **10,000 synthetic transactions / 20 mappings / 1,442,752 source bytes**,
  frozen October 2026 clock; unchanged prior built assets and frontend source
  hashes checked. Python 3.13.7, Node 22.13.1, Chromium 156.0.8078.4, Windows 11.
- Navigation through real calculation, IPC, DOM consumption and two animation
  frames: **507.759 ms**. Three refreshes: **259.173 / 265.826 / 233.771 ms**.
  All below the exact **2000 ms SC-005** bound in this recorded local environment.
- Actual A-only PUT/recompute **248.577 ms**, showing **90,000 reserves / 2.7
  months**; persisted across browser reload. Actual empty PUT/recompute
  **275.682 ms**, explicit unavailable/null rather than fabricated zero.
- Hide/show **68.310 / 55.978 ms**; zero network requests, no lost B-off draft,
  raw monetary text/attributes masked, ratios retained. Visible source scope,
  months, gross basis, timestamps, qualifications, non-forecast/no-advice copy.
- **Zero unknown requests/page errors/static-helper API attempts**. Only own
  static 5203 helper; backend is in-process via stdio, not a server. Source
  hashes unchanged; backend exited 0, temp root removed, helpers stopped.
- Artifacts under the session's existing `files` directory:
  `runway-integrated-results.json`,
  `runway-integrated-{happy,masked,saved,unavailable}.png`,
  `runway-browser/{backend-bridge.py,integrated-acceptance.mjs}`.
- T033 technical completion does **not** assert SC-008 human comprehension or
  SC-004 human ease/time. Manual observation is deferred: user absent, no answers
  or participant fabricated.

### RT-001 — historical confirmed reproduction, now remediated above

**Location:** `src/budget_api/tests/isolated_run.py:49–52,91`.
Fresh Linux WeasyPrint import uses cffi/`ctypes.util.find_library`, which launches
exact `['/sbin/ldconfig', '-p']` with captured stdout, disabled stdin/stderr and
locale-only environment. The guard dispatches it to `_renderer_options` and raises
`UnsafeTestAccess`. It never reaches the optional pdftotext extraction.

Final **Debian 12 / Python 3.13.18** staged canonical four-tree run:
**1147 passed, 5 failed, 1 warning in 91.49s**, no marker exclusions, exit 1.
Four failures concern native rendering: mega synthetic full/section release gate,
two accounting PDF tests, and UTF-8 JSON→HTML→PDF test. The latter reproduces
alone via standard `python -m budget_api.tests.isolated_run`: **1 failed in 1.91s**.
All four unchanged native tests pass without the feature Python plugin in the
**same physically isolated code/synthetic-only container: 4 passed in 82.40s**.
This controlled comparison isolates guard compatibility; it is not a canonical
pass or permission to remove protection.

**Disposition at this historical handoff:** Coordinator/backend rework required before claiming Linux harness
completion. Preserve protected-path/network/subprocess boundaries, handle only
trusted native-library discovery, and add targeted allowed/blocked regressions.
Do not broadly permit subprocesses, prewarm only the parent while ignoring child
startup, or introduce skips to disguise failure. No backend changes made by the
frontend/runtime executor. Original QA-003 collection/alias fixes remain locally
verified; this is a newly reproduced native-startup gap, not review2 approval.

### RT-002 — Full-run lock timeout; attribution unresolved

`src/v4_pipeline/tests/test_accounting.py:1197`,
`test_publisher_lock_times_out_during_cross_process_contention`: child readiness
does not arrive within five seconds in two canonical runs. Same test alone through
the standard guarded entrypoint: **1 passed in 3.51s**. Adding the normal
multiprocessing main guard to the session evidence wrapper did not change the
full-run result. Cause is **unverified**; no feature attribution, baseline
repair or reduced assertion. Backend/QA triage retained.

### Native-tool and isolation evidence

- Windows standard guarded UTF-8 JSON→HTML→PDF test: **1 passed in 1.21s**;
  installed pdftotext **4.00** means optional extraction actually ran.
- Linux `/usr/bin/pdftotext` executed through unchanged strict temporary-file
  guard on a generated text PDF: expected synthetic text, exit 0, temp removed.
  Evidence: `runway-linux-output/runway-linux-extractor.json`. This verifies the
  extractor exception, **not** WeasyPrint discovery.
- Public pinned Python/Debian image; dependencies installed in a session-only
  image only after actual missing pytest/native-prerequisite probes. No host or
  repository dependencies changed. Only **159 allowlisted code/synthetic inputs**
  staged; no credentials/private data/original Git metadata/full checkout mounted.
  Standalone staging index means containment coverage is of staged inputs only.
- Test containers: no network, read-only root/code, dropped capabilities,
  no-new-privileges, explicit limits/time bounds, auto-removal, no published ports
  or Docker socket. No user container/env inspection or Compose action. Only
  session-created image tags removed after use. No own helpers remain.
- `runway-linux-command{,-initial}.json`, `runway-linux-diagnostics.json`,
  `runway-linux-stage.json`, and `runway-linux-output/runway-linux-results{,-initial}.json`
  retain exact argv, results, environment and source hashes.
- WSL had only Docker Desktop. **No Ubuntu-specific pass** is claimed. Linux
  was actually attempted and failed; this is not a missing-tool limitation.

## Findings and remediation

| ID | Important finding / confidence | Reproduction and fix | Status |
| --- | --- | --- | --- |
| QA-001 | Month-local identity tracking misses conflicting copies across candidate sources; FR-008. **97%**. Original `services/runway.py:498–508,737–740`. | Give August's first purchase July's first transaction ID, retaining valid distinct dates/amounts. Previously all three months counted. `_identity_conflicts` now scans all readable candidate transaction lists before observations enter the common window, including partial sources and records after malformed entries. Every month referencing a conflicting identity is invalidated; known source dates remain visible. Identical object-key-reordered copies still count once; equal amounts with distinct IDs still count separately. Forward/reverse source and record order tests plus API regression pass. | Review1 fix had review2 Decimal/array collision residual (98%); locally remediated above, final review3 pending. |
| QA-002 | Embedded category title coerced with `str(...)`, unlike validated catalog titles. **93%**. Original `services/runway.py:404–405,527–528`. | July title `["cc payment"]` or `{"text":"cc payment"}` previously became repayment evidence and yielded A's 3.9-month ratio. Embedded titles are now validated as strings before exclusion/classification, with no coercion. Bad shape invalidates July; August/September yield 2.6 months. Valid string repayment evidence still excludes repayment. Calculation and real-route regressions pass. | Accepted in supplied review2 continuation; unchanged here. |
| QA-003 | Importing feature conftest installs global audit/Popen guards, but only the custom runner redirects legacy aliases. Ordinary pytest's save-export copy-error test raises `UnsafeTestAccess` before its expected `OSError` handling. **99%**. Original `tests/runway/conftest.py:11–13`, `tests/isolated_run.py`. | Reproduced the exact protected mkdir failure under guarded ordinary pytest without opening the path. Conftest import now installs nothing; feature execution uses scoped guards that restore Popen/environment. Explicit `-p budget_api.tests.isolated_run` installs early temporary defaults and per-test legacy-alias redirection; the canonical runner uses that same plugin. Ordinary pytest feature collection + all three legacy save-export tests pass together (4 tests), as does ordinary focused pytest without the plugin (158 tests). No legacy production/test change, CI edit, or blanket skip. | Accepted in supplied review2 continuation; unchanged here. |

### Renderer-related QA-003 follow-up

The optional Linux `pdftotext` call is supported only as the exact resolved
installed executable with `[executable, isolated_absolute_pdf, "-"]`.
The PDF must resolve inside an active temporary isolation scope; temporary
executables, protected/non-PDF/out-of-scope inputs, output files, extra flags,
shell/executable overrides, environment overrides, and unrelated cwd are rejected.
Output is captured; stdin disabled; cwd forced to the PDF directory. Arbitrary
subprocesses remain blocked. Synthetic policy and intercepted-launch proofs pass;
no native renderer executable ran in this Windows pass. This is a narrow trusted
tool exception, not an OS sandbox for arbitrary native programs.

## Reproduction and validation evidence

- Calculator red phase: **7 failed, 3 passed, 79 deselected**. Five failures were
  identity consistency/order/partial-source cases; two were list/object titles.
- Harness red phase: **2 failed, 5 deselected**. Import side effect and the exact
  ordinary-pytest legacy mkdir failure both reproduced.
- Calculator + API after fixes: **132 passed**.
- Final ordinary focused pytest: **158 passed**, one existing TestClient warning,
  **7.01s**.
- Safe canonical Windows backend regression: **1150 passed, 2 deselected**,
  one existing TestClient warning, **34.89s**. Only the existing `pdf_renderer`
  marker was excluded.
- Final timing/recipe probe: **2 passed**; 10,000 synthetic transactions,
  20 mappings, service **0.312s**, fresh-process ASGI GET **0.146s**.
  These are separate local measurements, not end-to-end browser timing.
- Commands, isolated fixture setup, and frontend-specialist handoff:
  [quickstart.md](quickstart.md#review-1-backend-rework--2026-10-31).

In the earlier backend rework pass, no dependencies were installed or declarations
changed; no frontend files, live data, credentials, main checkout, Docker or
running servers were used. The later explicitly authorized isolated runtime
validation is recorded above. Work remains uncommitted on the existing branch.

## OWASP LLM checklist retained from review 1

This is the supplied reviewer checklist, with backend remediation/test status
updated. It is not a new independent security sign-off.

| Item | Applicability / evidence |
| --- | --- |
| LLM01 Prompt Injection | N/A — no runtime LLM. |
| LLM02 Insecure Output Handling | Applicable generated-output check: React text rendering, no raw HTML reported by reviewer; no frontend edits in rework. |
| LLM03 Training Data Poisoning | N/A — no runtime LLM/training pipeline. |
| LLM04 Model Denial of Service | N/A — no runtime LLM. |
| LLM05 Supply Chain Vulnerabilities | No added dependencies; existing dependency declaration drift unchanged. |
| LLM06 Sensitive Information Disclosure | Static errors, exact-route no-store, and existing masking; backend error/privacy tests pass. Masking is not authorization. |
| LLM07 Insecure Plugin Design | N/A — no runtime LLM plugins. |
| LLM08 Excessive Agency | N/A — no runtime LLM or model actions. |
| LLM09 Overreliance | Generated-code assurance: remediation tests and self-review complete; independent re-review and acceptance remain pending. |
| LLM10 Model Theft | N/A — no runtime LLM. |

General controls: QA-002 boundary validation is fixed. Runway production paths
introduce no SQL, shell commands, or raw-HTML rendering. Existing local-only
authentication/exposure convention is unchanged; no new remote-access claim.

## Caveman self-review and remaining gates

- 🔴 No new high-confidence bug found in the bounded QA-001 fingerprint change; final independent review3 pending.
- 🟡 `test_accounting.py:1197`: RT-002 baseline spawn/import startup limitation verified; historical Linux canonical remains non-green. No baseline repair.
- 🟡 `isolated_run.py:71–88`: Fixed trusted native-tool exception, not an OS sandbox. Exact allow/deny and native execution tested.
- 🟡 Human/screen-reader/Ubuntu/remote observation remains unverified. Real HTTP SC-005 passed locally, not a latency guarantee.
- ❓ No question for absent user. Independent QA owns review3 and final acceptance.

T033 technical objectives are checked with explicit deferred human observation;
T034 remains unchecked. The previously failed review/merged-plan publication
gate remains **NOT passed**; direct user authorization allowed local continuation,
not publication. Final reviewer owns bounded independent review3 and remaining
gate disposition; accepted RT-002 baseline attribution remains unchanged.
Deferred manual checks do not reopen completed
local implementation.
