# Quickstart: Safe Runway Validation

**Date**: 2026-10-31
**State**: T033 technical runtime acceptance and T034 independent QA are complete;
**34/34 original tasks checked**. Final bounded independent review3 is
**PASS WITH CAVEATS**, with no remaining in-scope finding. Reviews 1 and 2 found
issues that were fixed and regression-tested; review3 closed the residual
QA-001 Decimal/array identity collision after its 36 added regressions.
Human observation remains explicitly deferred, not passed.
RT-001 native discovery is fixed and verified with actual Linux
renderers. RT-002 is now conclusively separated as a baseline collection/spawn
startup limitation in the staged Linux environment; canonical is not claimed
green. Accepted HTTP/frontend/Linux evidence was not rerun after the final
internal fingerprint fix; its latest Windows suites and service timings follow.
Merged-plan gate was checked and **NOT passed**; direct user continuations
authorized local backend/frontend implementation nonetheless, not gate passage or
publication. See [plan.md](plan.md).

**Calculation v2 (2026-11-01, FR-028–FR-030).** Runway spending is now household
net spending as in Reports (`basis: "household_net_spending"`); refunds reduce it,
and monthly values/averages can be zero or negative (average ≤ 0 → `nonpositive_burn`).
Owner burn uses the common economy split shares on split categories plus own net
elsewhere (`owner_attribution: "common_economy_split"`), or net by paying account
(`"payer"`). Records below that mention gross burn are dated v1 evidence and were
not re-run against v2.

**Evidence locations.** The harness scripts and raw outputs named below
(`runway-browser/*`, `runway-http-results.json`, `runway-rt002/`, screenshots and
Linux logs) live in a local, unpublished evidence directory, written here as
`<local-evidence-dir>`. They are not part of this repository, were produced only
from synthetic fixtures, and the snippets that reference them are a record of
what was run rather than copy-paste reproductions.

## Review2 residual QA-001 — 2026-10-31

**Historical fix handoff; subsequently approved by independent review3.** One production
function changed: `services/runway.py::_fingerprint`, now a recursively
type-tagged tuple representation. No parser, validation, pre-scan/observation
flow, route/schema, frontend, harness, RT-001 guard or RT-002 baseline changes.
Full finding, exact regression inventory and file manifest:
[review-report.md](review-report.md#review2-residual-qa-001--local-remediation-review3-pending).

Before the fix, source numeric **`-100.0`** became `Decimal("-100.0")` and
fingerprinted identically to the malformed array **`["decimal","-100.0"]`**.
Valid-first same-ID July copies incorrectly included July; array-first excluded
it. Numeric July plus malformed August copy **retaining July's date** left July
included even with reversed candidate scan order. Both now invalidate every
referencing month. Decimal copies with reordered nested object keys still count
once. Typed scalar/array/object and canonical-encoding lookalikes cannot collide.
Decoded Decimal scale/sign and pre-existing numeric equality distinctions stay
unchanged; NaN/Infinity amounts still fail monetary validation.

### Exact synthetic Windows regression commands/results

Same worktree, existing Python **3.13.7**, no installs or dependency edits.
All runs use pre-import `BILLS_CALC_LOG=0`, plugin autoload disabled and the
unchanged pre-collection temporary storage/env + per-test isolation runner.
No protected source/env reads, live user services, main checkout, Docker,
browser/helper startup, agents/nesting, commit/push/PR or unrelated edits.

```powershell
$env:BILLS_CALC_LOG = '0'
$env:PYTHONPATH = 'src'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
# Run once before production fix (red), once after (green).
.\.venv\Scripts\python.exe -m budget_api.tests.isolated_run src/budget_api/tests/runway/test_calculation.py src/budget_api/tests/runway/test_api.py -k fingerprint -q --tb=short
# Post-fix suites, sequential.
.\.venv\Scripts\python.exe -m budget_api.tests.isolated_run src/budget_api/tests/runway -q
.\.venv\Scripts\python.exe -m budget_api.tests.isolated_run src/budget_api/tests -q
.\.venv\Scripts\python.exe -m budget_api.tests.isolated_run src/mega/tests src/v4_pipeline/tests src/mom/tests src/budget_api/tests -m 'not pdf_renderer' -q
```

| Check | Result | Pytest time |
| --- | --- | ---: |
| Added regressions, pre-fix | **19 failed / 17 passed / 134 deselected** | 1.92s |
| Same regressions, fixed | **36 passed / 134 deselected** | 0.88s |
| Focused runway subtree | **215 passed** | 10.68s |
| Full API backend subtree | **869 passed** | 27.48s |
| Canonical Windows four trees | **1207 passed / 2 deselected** | 40.88s |

All five runs have one existing Starlette TestClient/httpx deprecation warning;
no dependency change. Red failures: four calculator numeric/array order cases,
ten nested metadata conflicts, three parsed-type matrices, two real-route
numeric/array cases. Green inventory: **32 calculator/identity + 4 API** new
cases. The route tests assert HTTP 200/no-store, structured invalid/null
observations, cross-month unavailable runway and unchanged source bytes.
The two canonical exclusions are the same existing `pdf_renderer` marker;
no new skips. **179→215 focused / 1171→1207 canonical** reflects exactly 36
added tests, not changed historical results.

### Bounded 10,000-transaction comparison

Run this exact script once on the pre-fix function, then once after replacement.
Each process makes five sequential complete service calculations per dataset.
Fixture setup/writes/imports are outside the timing; first calculation is
retained, not discarded as warmup. Clock is frozen at synthetic NOW, timing
uses real `perf_counter`. Both datasets have **10,000 transactions / 20 mappings**,
with July/August/September **3334/3333/3333**. The second writes JSON decimal
amounts, actually exercising `parse_float=Decimal`, not strings.

```powershell
$env:BILLS_CALC_LOG = '0'
$env:PYTHONPATH = 'src'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
@'
import hashlib
import json
import statistics
import sys
import time
from budget_api.tests.isolated_run import isolated_environment
with isolated_environment() as private:
    from budget_api.tests.runway.synthetic import World, MONTHS, NOW
    from budget_api.services.runway import calculate_runway
    world = World(private)
    world.use_large_history()
    for amount in (-10, -10.0):
        for month in MONTHS:
            for row in world.data[f"{month}_ps_raw.json"]["transactions"]:
                row["amount"] = amount
        world.write()
        durations, digests = [], set()
        for _ in range(5):
            started = time.perf_counter()
            result = calculate_runway(now=NOW)
            durations.append((time.perf_counter() - started) * 1000)
            assert result.included_months == MONTHS
            assert abs(result.household.average_monthly_spending - 100000 / 3) < 1e-9
            digests.add(hashlib.sha256(result.model_dump_json().encode()).hexdigest())
        assert len(digests) == 1 and max(durations) < 2000
        print(json.dumps({"python": sys.version.split()[0], "amount": amount,
            "transactions": 10000, "mappings": 20,
            "source_bytes": sum((private / f"{month}_ps_raw.json").stat().st_size for month in MONTHS),
            "durations_ms": [round(value, 3) for value in durations],
            "median_ms": round(statistics.median(durations), 3),
            "response_sha256": next(iter(digests))}))
'@ | .\.venv\Scripts\python.exe -
```

| Source amount / phase | Five raw elapsed times (ms) | Median (ms) |
| --- | --- | ---: |
| Integer `-10`, before | 302.982, 133.548, 132.951, 133.034, 129.607 | 133.034 |
| Integer `-10`, after | 295.820, 154.280, 144.145, 159.706, 148.585 | 154.280 |
| Decimal `-10.0`, before | 242.195, 139.612, 152.086, 140.421, 142.855 | 142.855 |
| Decimal `-10.0`, after | 252.477, 158.575, 163.881, 153.466, 161.236 | 161.236 |

Observed median deltas **+21.246ms integer / +18.381ms decimal**;
post-fix maximum **295.820ms**, no fixture-scale explosion. These are local
service-only observations, not a new SC-005 browser pass or guaranteed latency.
Monthly raw JSON sizes only: **1,440,477 bytes integer / 1,460,477 decimal**;
unlike the older HTTP record's total source bytes, these exclude config/catalogs.
All twenty calculated response bodies have identical SHA-256:
`c92881a1b4e70db2bc4079586e28e0d1fe8bd53218c61b14b0e244fc889417eb`.
Valid response contract/arithmetic is unchanged. Temporary roots are removed by
the context manager; no server/port was started.

### Final review3 handoff boundary

Review only residual QA-001 canonical identity/regressions and evidence
consistency. Supplied review2 continuation retains QA-002/003/RT-001, the seven
HTTP scenarios/scripts/screenshots and **5203/8103 cleanup**, plus RT-002 baseline
attribution. No broad browser/Linux rerun: prior HTTP SC-005 initial
**1047.450ms**, refresh **267.264–305.396ms**, save **934.002ms** remains historical;
prior Linux **1172 passed / 1 baseline failure** remains non-green.
Human/screen-reader/Ubuntu-specific/remote review stays **unverified/nonblocking**
for local implementation. No QA approval or publication permission inferred.
**33/34 original tasks checked; T034 pending independent review3.**

Changed files: `services/runway.py`, `tests/runway/{test_calculation,test_api}.py`,
`docs/specs/003-runway-burn-rate/{review-report,quickstart,tasks}.md`, `memory.md`.
**Migrations:** none. **Caveman self-review:** 🔴 none found in this bounded fix;
🟡 retain measured 18–21ms median increase and historical validation limits;
❓ none. Accepted category/harness/native-guard changes are untouched.

## RT-002 last-test diagnosis — 2026-10-31

**Complete local diagnosis, not independent QA2 approval.** No production,
frontend, test or isolation-helper edits. Only this document, review-report,
tasks and memory changed. No branch mutation, commits, publication, agents,
servers, Compose or user-container inspection. **RT-002 triage only is checked;
T034 remains pending (33/34 original tasks).**

### Controlled comparison and attribution

Baseline **`979a01c5daca080cd141bfdb2c82970488998018`** was reconstructed
from read-only Git objects, not another checkout. `runway-rt002/manifest.json`
records SHA-256 for **150 baseline / 159 changed files**. Baseline lacks all
nine feature-added Python files, including `tests/isolated_run.py` and the
runway subtree. The only shared source content change is `budget_api/main.py`
(line endings normalized). Lock test, publisher, legacy collection code,
`pyproject.toml`, `uv.lock` and explicit public fixtures are unchanged.
No source/private files outside the allowlist were read or copied.

Every comparison uses the same pinned Debian 12 / Python **3.13.18** image,
pytest **9.1.1**, pytest-asyncio **1.4.0**, WeasyPrint **70.0**, FastAPI
**0.141.1**, and only `data/sample_apr_2026.json` plus
`data/sample_apr_2026_detailed_section_mapping.json`. Docker flags:
`--network none --read-only --cap-drop ALL --security-opt no-new-privileges
--pids-limit 256 --memory 2g --cpus 2 --tmpfs /tmp:rw,size=536870912`.
Only generated staged code, harness and output directories are mounted.
`BILLS_CALC_LOG=0`, plugin autoload disabled, bytecode writes disabled and
`HOME=/tmp` precede imports. Baseline comparisons physically contain no real
private data and run without the new helper. Each own container has `--rm`
and a 300-second outer bound. Runs were sequential, not competing test jobs.

| Probe / artifact stem under `runway-rt002/evidence/` | Guard | Result |
| --- | --- | --- |
| `changed-collection` — collect all four trees, execute only lock, diagnostic tracing | on | **1 failed / 1172 deselected**, 24.32s |
| `baseline-collection` — identical selection/tracing, feature/helper absent | absent | **1 failed / 993 deselected**, 20.65s |
| `baseline-timing` — exploratory probe also preimporting multiprocessing Event | absent | **1 passed / 993 deselected**, 18.64s; altered import order, not decisive |
| `baseline-stack` — original import order restored, four-second stack dump | absent | **1 passed / 993 deselected**, 17.45s; stack in child pytest import |
| `baseline-original` — original evidence runner, no process tracing, all-tree collection/lock only | absent | **1 passed / 993 deselected**, 16.52s |
| `changed-original` — same original runner/selection | on | **1 failed / 1172 deselected**, 27.45s |
| **`baseline-original-prefix` — original runner, no process tracing, unchanged canonical order through lock** | **absent** | **113 passed / 1 failed / 880 deselected**, **104.92s** |
| `changed-deduped` — diagnostic-only first-occurrence `sys.path` deduplication, all-tree collection/lock only | on | **1 passed / 1172 deselected**, 16.42s; lock call **2.397s** |
| `changed-feature-first` — all runway tests, then original lock; original runner, no tracing/deduplication | on | **180 passed**, **28.11s** |

All failure rows fail the **same unmodified** `ready.wait(5)` at
`src/v4_pipeline/tests/test_accounting.py:1197`. The baseline-prefix failure,
with no diagnostic process instrumentation and no isolation helper installed,
is the decisive same-environment baseline reproduction. Diagnostic selections
are not canonical exclusions or a green full-suite claim. Previous changed
canonical **1172 passed / 1 failed** remains the canonical record.

### Exact mechanism; why this is not feature leakage

Collection finishes before execution. The lock is original item **114**;
no runway test occurs before it. Existing `mom/build_mom.py:12–14`,
`mom/data.py:22–23`, `mom/tests/test_mom.py:7`, `mom/mom_template.py:22`,
multiple `mom/sections/*` imports, and `v4_pipeline/tests/conftest.py:14` /
`v4_pipeline/build.py:17` prepend paths. Captured `sys.path` lengths are
**30 baseline / 32 changed**, with repeated staged directories.

The child is ordinary POSIX multiprocessing spawn:
`python -B -c 'from multiprocessing.spawn import spawn_main; spawn_main(...)'
--multiprocessing-fork`. It is **not** launched through the helper's rewritten
`subprocess.Popen`; stdlib uses `spawnv_passfds`/`fork_exec`.
`spawn.prepare` restores the parent's expanded path list before
`_fixup_main_from_path` reexecutes the evidence script as `__mp_main__`.
The script's top-level pytest import therefore repeats filesystem lookups over
those Windows-backed Linux bind paths before the child target can signal ready.
The `if __name__ == "__main__"` guard prevents recursive pytest execution;
the cost is module imports, not a second test suite.

`baseline-stack` captures at four seconds:
`spawn.prepare → _fixup_main_from_path → runpy.run_path → import pytest →
_pytest/assertion/fixtures/main/runner/timing → importlib._path_stat`.
Child main import start/end: **0.422s / 4.417s** after interpreter startup.
Failed collection probes join the child with **exit 0** (baseline **1.194s**
after the five-second wait; changed **1.439s**), no active children at start
or completion. This is slow startup before readiness, not a stale held lock.
The timing and uninstrumented collection-only baseline passes are retained
above: latency varies around the bound, so not every baseline run must fail.

Deduplicating only the diagnostic parent's path list **32→11**, retaining all
unique directories and precedence, lets changed+guard child main imports end
at **1.577s**, with the unchanged lock passing in **2.397s**. Repository code
does **not** adopt this workaround. A full **179 runway tests → original lock**
order also passes (**180 total**), including pathlib, child subprocess, native
allow/deny and API regressions. Collection-only failures require no prior test
monkeypatches; baseline-prefix fails without `private_defaults` or any helper.

**Disposition:** baseline collection/spawn-import startup limitation in this
specific synthetic Docker Desktop Linux environment; **not feature-caused
isolation/test leakage**. No publisher repair, timeout weakening, broad
subprocess permission, skip or unrelated import-path refactor is warranted.
RT-002 diagnosis is complete; independent reviewer2 still owns T034.

### Reproduction commands and retained artifacts

All scripts/results are below:
`<local-evidence-dir>\runway-rt002`.
Each `*-command.json` records exact Docker argv, exit code, timestamps and full
stdout/stderr. Matching `.json` contains outcomes/order/stack where instrumented.
Original-runner and final control runs also preserve exact script snapshots
and SHA-256 in their command records. `original.py` retains the earlier
`run_validation.py` imports/native audit; only optional guard selection,
diagnostic prefix selection and evidence names differ. There is no pytest
fixture or process wrapper in its comparisons.

```powershell
$env:BILLS_CALC_LOG = '0'
$artifacts = '<local-evidence-dir>'
$b = Join-Path $artifacts 'runway-rt002'
# Initial own image lookup failed; rebuild used cached install layers only.
docker build --tag runway003-rt002:96e01e "$artifacts\runway-linux-provision"
# Requires absent baseline/changed generated directories; source hashes verified.
.\.venv\Scripts\python.exe "$b\stage.py"
$env:RT002_ENTRY = 'original.py'
.\.venv\Scripts\python.exe "$b\run.py" baseline 0 prefix baseline-original-prefix
.\.venv\Scripts\python.exe "$b\run.py" changed 1 all changed-original src/mega/tests src/v4_pipeline/tests src/mom/tests src/budget_api/tests -k test_publisher_lock_times_out_during_cross_process_contention
.\.venv\Scripts\python.exe "$b\run.py" changed 1 all changed-feature-first src/budget_api/tests/runway src/v4_pipeline/tests/test_accounting.py::test_publisher_lock_times_out_during_cross_process_contention
# Diagnostic import-path control only, not canonical execution or repo change.
$env:RT002_ENTRY = 'diagnose.py'
$env:RT002_DEDUPE = '1'
.\.venv\Scripts\python.exe "$b\run.py" changed 1 collection changed-deduped
Remove-Item Env:RT002_ENTRY, Env:RT002_DEDUPE
```

No repeated full suite. Investigation stops at verified baseline reproduction,
mechanism control and feature-first regression. Generated staged copies and
owned image/containers are cleaned; manifests, scripts and results are retained
for reviewer2. Verification/cleanup details: `runway-rt002/verification.json`.

Final `verify.py` **exit 0**: all nine comparison outcomes checked, original
114-item prefix identical, staged/source hashes verified, nine owned containers
absent, owned image removed, both generated staged copies removed. `git diff
--check` passes. Scripts, manifests and evidence remain available.
**Caveman self-review:** 🔴 none; 🟡 canonical still not green—retain verified
baseline limitation for QA2; ❓ none. **Migrations:** none.

## Bounded backend rework and real HTTP acceptance — 2026-10-31

**Current local handoff. No independent QA2 approval.** Latest direct instruction
permits owned loopback **5203/8103** with temporary synthetic storage. This
supersedes older no-backend-server directions below. Existing **8080/5200/8100**,
user Docker/Compose, real `.env`/financial storage and main checkout were not used.
No agents, unrelated refactor, production/frontend changes, dependency changes,
branch changes, commits, push or PR.

### RT-001 guard fix and regression

`tests/isolated_run.py` now allows only Linux
`["/sbin/ldconfig", "-p"]` or `["/usr/sbin/ldconfig", "-p"]`.
Resolved executable must stay in those system paths, be a root-owned regular
executable, and lack group/other write permissions. Options must exactly match
stdlib discovery: stdin/stderr `DEVNULL`, stdout `PIPE`, environment only
`{"LC_ALL":"C","LANG":"C"}`. No shell, executable/cwd override, pre-exec hook,
positional options, other flags or cache writes. Existing strict temporary-PDF
`pdftotext`, guarded Python children, protected paths and network guards remain
unchanged. No native skips added.

New regressions: exact trusted lookups reach intercepted launch; modifying/extra
arguments, relative/temp paths, untrusted symlink targets, ownership/permission/
file-type failures, non-Linux use and unsafe subprocess options are rejected.
Red: **2 failed, 19 passed, 24 deselected in 0.20s**. Green:

| Check | Result | Pytest time |
| --- | --- | ---: |
| Windows isolation guard file | **45 passed**, 1 warning | 3.26s |
| Windows ordinary focused runway subtree | **179 passed**, 1 warning | 9.12s |
| Windows safe canonical four trees | **1171 passed, 2 deselected**, 1 warning | 41.15s |
| Windows real UTF-8 JSON → HTML → PDF/extraction target | **1 passed** | 1.14s |
| Debian 12 / Python 3.13.18 guarded target set | **50 passed**, 2 warnings | 109.76s |
| Same Linux guarded canonical four trees, no exclusions | **1172 passed, 1 failed**, 2 warnings | 170.92s |

Exact Windows invocations, from this worktree:

```powershell
$env:BILLS_CALC_LOG = '0'
$env:PYTHONPATH = 'src'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
.\.venv\Scripts\python.exe -m pytest -p pytest_asyncio.plugin src/budget_api/tests/runway/test_isolation.py -q
.\.venv\Scripts\python.exe -m pytest -p pytest_asyncio.plugin src/budget_api/tests/runway -q
.\.venv\Scripts\python.exe -m budget_api.tests.isolated_run src/mega/tests src/v4_pipeline/tests src/mom/tests src/budget_api/tests -m 'not pdf_renderer' -q
.\.venv\Scripts\python.exe -m budget_api.tests.isolated_run src/v4_pipeline/tests/test_data_loader.py::test_utf8_json_loader_to_html_to_real_pdf_chain -q
```

Linux target set = guard file + all four original RT-001 native failures + RT-002
lock target. All four native tests now pass **with guards active**, in both target
and canonical runs. Each records **26 actual `/sbin/ldconfig -p` launches and one
actual `/usr/bin/pdftotext` extraction** from an isolated PDF. RT-001 is locally
remediated, not merely bypassed by prewarming or removing the plugin.

**At that earlier handoff RT-002 remained unresolved.** The lock
target passes in the 50-test set; canonical still fails at
`src/v4_pipeline/tests/test_accounting.py:1197`, `ready.wait(5)`.
Cause/feature attribution was then **unverified**; the subsequent
[narrow diagnosis above](#rt-002-last-test-diagnosis--2026-10-31) establishes
baseline attribution. No production change, timeout
relaxation, retry-until-green or additional broad review.

The prior owned image was absent (actual `docker image inspect` failure).
Recreated it from the existing pinned session recipe; **all install layers were
cached**, no new package installation. `run-runway-rework.py` verifies all 159
staged input hashes, replacing only the two changed harness/test files. Same
read-only staged mounts, network none, capability/resource limits and 300s bound
per container as the prior recipe. Target then canonical ran once each.
Exact reproduction:

```powershell
$artifacts = '<local-evidence-dir>'
docker build --tag runway003-validation:96e01e "$artifacts\runway-linux-provision"
if ($LASTEXITCODE -eq 0) { .\.venv\Scripts\python.exe "$artifacts\run-runway-rework.py" }
# After both owned containers exit; no user image/stack actions.
docker image rm runway003-validation:96e01e
```

Artifacts: `runway-linux-rework-commands.json` (exact argv/full stdout/stderr),
`runway-linux-rework-stage.json`, and
`runway-linux-output/runway-linux-rework-{target,canonical}.json`.
Both `--rm` containers exited; owned-name filter empty. Only recreated session
image tag removed. Debian evidence is **not Ubuntu-specific validation**.
Warnings: existing TestClient/httpx deprecation and future HarfBuzz-Subset prerequisite.

### Real TCP/HTTP backend → built browser

```powershell
$artifacts = '<local-evidence-dir>'
foreach ($port in @(5203,8103)) {
  if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
    throw "Test port $port occupied"
  }
}
node "$artifacts\runway-browser\http-acceptance.mjs"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

**Exit 0**, **2026-10-31T19:01:03.153Z–19:01:14.436Z**. Windows 11,
Python **3.13.7**, Node **22.13.1**, Chromium **156.0.8078.4**, Playwright
**1.64.1**, viewport **1440×1000**, Europe/Oslo. Linux canonical ran concurrently;
these are honest local observations, not idle-machine or production guarantees.
Frontend source identity and every built asset hash matched the earlier verified
build (`1bc2e34814131608ed33b93e8d5c2ec4d590da9af33cceacb494583bc26f1bc5`);
prior **414 tests/build** remain historical evidence, not rerun without edits.

`http-backend.py` sets guarded `isolated_environment()` storage and ENV_FILE
**before app import**, creates a temporary comment-only fake env with no
credentials, writes `World(private).use_large_history()`, then redirects newly
imported legacy aliases before serving the real app. No sync/PocketSmith route
is exposed by its outer fixed allowlist; unknown requests fail closed.
Uvicorn uses a pre-bound **127.0.0.1:8103** socket with existing outbound-network
guards active. Both backend `local_now` and browser Date are frozen at
**2026-10-15T12:00:00Z**; performance clocks/timers remain real.

`http-serve.mjs` serves the unchanged built frontend on **127.0.0.1:5203** and
streams allowlisted API requests/responses over **actual HTTP to 8103**.
Readiness was verified through HTTP `/health` and static/proxy status before
navigation. Playwright only aborts external origins; every same-origin request
continues to the server. **No `route.fulfill`, TestClient bridge, or substituted
API response.** Browser response hashes match server-side response hashes;
proxy/backend request counts match. Real missing-current-Bills 404 is retained.

Dataset: **10,000 transactions**, July/August/September **3334/3333/3333**,
**20 mappings**, **1,442,752 source bytes**. Two active purchasing accounts;
other mappings exercise scale, not twenty purchasing accounts.

| Action | Actual elapsed ms | Bound | Result |
| --- | ---: | ---: | --- |
| Initial navigation → result | 1047.4496000000008 | 2000 ms | Pass |
| Refresh 1 | 305.39630000000034 | 2000 ms | Pass |
| Refresh 2 | 267.2639999999992 | 2000 ms | Pass |
| Refresh 3 | 298.6697000000004 | 2000 ms | Pass |
| A-only HTTP PUT → recompute | 934.0017000000007 | 2000 ms | Pass |
| Empty HTTP PUT → unavailable | 919.0044999999991 | 2000 ms | Pass |
| Hide amounts | 59.382299999999304 | 1000 ms | Pass |
| Show amounts | 49.141099999998914 | 1000 ms | Pass |

SC-005's exact threshold is **within two seconds** at this dataset bound.
Start before navigation/action; end after actual HTTP, asserted DOM state and
two animation frames. Includes initial static loading; excludes fixture/helper/
browser startup. Loading observed. No artificial response delay. Privacy actions
make **zero requests**; their boundary is action to masked/restored paint.
Actual server-only runway requests were **194.686–492.176 ms**; not added to
independent frontend timings.

**H1–H7 passed, 13 browser API responses, four screenshots viewed in self-review:**

- H1/H2: household **120,000 reserves / 33,333 displayed gross burn / 3.6 months**;
  visible loading, real Bills 404 independence, three refreshes.
- H3: selected accounts, all three included months, gross basis, dates/staleness,
  non-forecast/no-advice text visible; not human comprehension.
- H4: every monetary `dd` and selected balance masked, raw monetary HTML
  text/attributes absent, ratios retained, B-off unsaved draft retained,
  original values restored, zero requests.
- H5/H6: keyboard A-only PUT gives **90,000 / 2.7 months**, B reserves null,
  no Bills refetch; browser reload reads persisted A-only settings/result.
- H7: real empty PUT gives `selection_status=empty`, null reserves/ratio,
  “Select liquid accounts” / “Unavailable”, never fabricated zero.

Evidence: `runway-http-results.json` (raw timings, actual synthetic HTTP bodies,
headers, server addresses, server/browser response hashes, counts, source/build
hashes and cleanup); `runway-http-{happy,masked,saved,unavailable}.png`;
`runway-browser/{http-backend.py,http-serve.mjs,http-acceptance.mjs}`.
Exactly seven runway GETs, two settings GETs, two PUTs, two Bills GETs.
One separate real backend health probe. Zero unknown requests, rejected proxy
routes, page errors or helper stderr.

Cleanup: backend **PID 51004** and proxy **PID 51360** exited **0** after explicit
owned stdin shutdown; Chromium closed. Both PIDs independently checked absent,
synthetic root deleted, source hashes and fake env unchanged, final on-disk
selection empty. **5203/8103 independently checked closed.** No user services
stopped or Docker stack inspected.

### Handoff boundary

T033 technical objectives complete, **33/34** original tasks checked.
**T034/independent QA2 remains unchecked**. Next review is bounded to QA-001/002/003
remediations, RT-001 allow/deny safety and preserved native extraction, real-HTTP
evidence/cleanup, and disposition of the unchanged RT-002 failure. No new broad
review loop requested.

Human SC-004 usability/time and SC-008 comprehension, screen-reader operation,
Ubuntu-specific execution and remote plan/review steps remain **unverified**.
They are nonblocking for this local implementation handoff per user direction,
not new user-signoff gates. Actual Debian native rendering is now verified;
do not label that performed check unverified or imply a green Linux canonical run.
Original remote/merged-plan publication gate remains NOT passed; no publication.

File manifest for this pass: `src/budget_api/tests/{isolated_run.py,runway/test_isolation.py}`,
`docs/specs/003-runway-burn-rate/{quickstart,review-report,tasks}.md`, `memory.md`.
Session harness/evidence files listed above are outside the repository.
No API/schema changes; **no migrations**.
`verify-runway-rework.py` checks current backend/frontend/screenshot hashes,
HTTP/Linux counts, native launches and the 33/34 task state; exit 0.
`runway-backend-rework-results.json` retains the six-file handoff manifest/hashes,
exact Windows commands/counts/times and evidence pointers. Historical IPC files
remain separate and unchanged.

Self-review: 🔴 no new high-confidence bug in bounded changes;
🟡 RT-002 canonical failure persists, cause unverified; native-tool policy remains
a narrow trusted-system-tool exception, not an OS sandbox; ❓ none for user.

## Integrated runtime acceptance and cross-platform attempt — 2026-10-31

**Historical IPC evidence, not full HTTP end-to-end verification.** Superseded
by the real HTTP run above for the requested SC-005 transport acceptance.

Latest direct user continuation authorized autonomous local validation, including
a separate bounded code/synthetic-only Docker container, but no Compose actions,
publication, production edits without a reproduced bug, or invented human results.
No subagents were used. **No production or repository test code changed in this
pass.** Linux harness rework is handed to the coordinator/backend owner below;
the browser result is not an independent QA approval.

### Historical real TestClient → built frontend, not HTTP E2E

Command, from the same worktree:

```powershell
$artifacts = '<local-evidence-dir>'
# Stop if port occupied. Never replace an existing listener.
if (Get-NetTCPConnection -LocalPort 5203 -State Listen -ErrorAction SilentlyContinue) { throw 'Port 5203 occupied' }
node "$artifacts\runway-browser\integrated-acceptance.mjs"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

- **Exit 0**, **2026-10-31T18:39:47.750Z–18:39:58.217Z**; Windows 11
  10.0.26200, Python **3.13.7**, Node **22.13.1**, Chromium **156.0.8078.4**,
  Playwright **1.64.1**; viewport **1440×1000**, Europe/Oslo.
- Reused the prior production build only after verifying both served asset hashes
  and every file in `runway-frontend-identity-final.json`. Frontend content ID
  remains `1bc2e34814131608ed33b93e8d5c2ec4d590da9af33cceacb494583bc26f1bc5`.
  No rebuild or broad frontend test rerun was needed for unchanged code.
- `runway-browser/backend-bridge.py` runs in a fresh guarded Python child with
  `isolated_environment()` before app import and `World(private).use_large_history()`.
  Both browser Date and `runway.local_now` use **2026-10-15T12:00:00Z**;
  performance clocks/timers are real. Storage and credential aliases are patched
  before import. No credential file is created.
- Dataset: **10,000 transactions**, July/August/September **3334/3333/3333**,
  **20 mappings**, **1,442,752 source bytes** excluding mutable runway settings.
  Two checking accounts supply purchases; the other mappings exercise mapped
  scale, not twenty active purchasing accounts.
- Every API request is intercepted and sent through JSON-line stdin/stdout IPC
  to **real `TestClient` routes**, retaining actual body/status/content type and
  no-store. Exactly seven runway GETs, two settings GETs, two settings PUTs and
  two missing-current-Bills GETs: **13 real API responses**, no fixture response
  substitution. All other methods/routes/origins fail closed.
- Only the fixed static-asset helper listens, on **127.0.0.1:5203**. No backend
  server, real API, user server, 8080/5200/8100 connection or proxy.
  **Zero unknown requests, page errors or API requests reaching the static helper.**

### Historical SC-005-shaped IPC timing, not HTTP E2E

The exact spec bound is **within two seconds** at up to 10,000 transactions and
20 mappings. Start: before navigation or browser action. End: actual backend
calculation/IPC response consumed by the built UI, asserted DOM state, and two
animation frames. Initial rendering includes static-page loading but excludes
test fixture generation and helper/browser startup. No artificial response delay.
Loading was observed in the live DOM; refresh was awaited until loading cleared.
Post-save measurements additionally include actual settings PUT and recomputation.

| Action | Raw elapsed ms | Bound | Result |
| --- | ---: | ---: | --- |
| Initial navigation → rendered result | 507.7592000000004 | 2000 ms | Pass |
| Refresh 1 | 259.1731 | 2000 ms | Pass |
| Refresh 2 | 265.8258999999998 | 2000 ms | Pass |
| Refresh 3 | 233.77099999999882 | 2000 ms | Pass |
| A-only PUT → recomputed result | 248.5767999999989 | 2000 ms | Pass |
| Empty PUT → explicit unavailable | 275.6821999999993 | 2000 ms | Pass |
| Hide amounts, zero requests | 68.3098000000009 | 1000 ms (SC-007) | Pass |
| Show amounts, zero requests | 55.97810000000027 | 1000 ms (SC-007) | Pass |

Actual backend-only runway requests were **139.674–204.674 ms** within this
same run. These are recorded local observations, not a production latency
guarantee, percentile benchmark, or a sum of unrelated backend/mock measurements.
For hide/show, no backend/IPC call occurs; the timing boundary is action to paint.

### Browser evidence and deferred human observation

**I1–I7: seven integrated scenarios passed; four new screenshots**, all viewed
during self-review. Prior **B1–B7/seven mock scenarios/eight screenshots** remain
separate historical evidence: **14 scenario checks and 12 screenshots total**,
not fourteen real-backend scenarios.

| ID | Verified observation | Screenshot in session artifacts |
| --- | --- | --- |
| I1 | Real large-history result: A **5.4**, B **1.8**, household **3.6 months**; household **120,000 kr** reserves, **33,333 kr** displayed gross burn. Real Bills 404 does not block panel. Loading observed. | `runway-integrated-happy.png` |
| I2 | Three real backend refreshes satisfy SC-005. | Happy screenshot; raw per-request/timing evidence in JSON |
| I3 | Selected names/owners, exact three included months, gross-not-net basis, non-forecast/no-advice copy, collection/balance dates and stale history qualifications are visible. | Happy screenshot |
| I4 | Unsaved B-off draft retained across hide/show; every monetary `dd`, selected balances and monetary HTML text/attributes masked; ratios retained, values restored, **zero requests**. | `runway-integrated-masked.png` |
| I5 | Keyboard Save sends actual A-only PUT; backend returns **90,000** reserves / **2.7 months**, B reserves null, no Bills refetch. | `runway-integrated-saved.png` |
| I6 | Browser reload obtains actual persisted A-only selection and recomputed **2.7** result. | Saved screenshot; subsequent reload assertions in script/JSON |
| I7 | Actual empty PUT yields `selection_status=empty`, null reserves/ratio, “Select liquid accounts” and “Unavailable”, never fabricated zero. | `runway-integrated-unavailable.png` |

`runway-integrated-results.json` contains full synthetic responses, route counts,
source/backend/build/screenshot hashes, raw timings, source-size evidence and
cleanup results. Scripts are `runway-browser/{backend-bridge.py,integrated-acceptance.mjs}`;
the existing fixed-allowlist `serve.mjs` is unchanged.

**T033 is reconciled to technical completion**, combining prior automated
SC-004 keyboard/configuration and SC-006 failure/race evidence with this integrated
SC-005/007 and source-copy check. SC-008 human five-fact comprehension and SC-004
human observed ease/time remain **deferred manual acceptance: user absent, no
participant or answers recorded**. Content visibility and scripted interaction
are not human comprehension. This explicit boundary does not leave the
functional browser implementation task unfinished or grant full QA approval.

### Linux and native renderer: attempted, not a canonical pass

Docker Server **29.9.2** was available; WSL listed only `docker-desktop`, not an
Ubuntu user distribution. Used an independent public **Debian 12** Python image,
not a user image/stack. This is Linux evidence, **not Ubuntu-specific validation**.

- Public base: `python:3.13-slim-bookworm`, digest
  `sha256:281d39ff02e3b389401586134ff9e6572954687822a58055ec07a60ded4e0b7f`.
  Python **3.13.18**, WSL2 kernel **6.6.87.2**, glibc **2.36**.
- A real `python -m pytest --version` first failed with **No module named pytest**.
  Separate prerequisite probes found no git/pdftotext/Pango/GObject. Only then
  provisioned a session-only image with the frozen `uv export` dependency set,
  git, Pango libraries, Poppler and DejaVu fonts. No host native install, repository
  dependency/lockfile change, CI change or user image rebuild.
- `stage-runway-linux.py` copied **159 explicit code/synthetic files**: current
  `src` code/tests, dependency metadata, and only the two documented public
  `sample_apr_2026` fixtures. No `.env`, private sources, original `.git`, main
  checkout or entire repository mount. A standalone staging Git index permits
  containment tests; those inspect **staged inputs**, not the full original tree.
- `run-runway-linux.py` records exact Docker argv in `runway-linux-command.json`.
  Mounts: staged code `/work` read-only, session harness `/harness` read-only,
  dedicated session output `/evidence`. Network **none**, root filesystem
  read-only, all capabilities dropped, no-new-privileges, 2 CPUs/2 GiB,
  512 MiB tempfs, 256 PID limit, **300-second bound**, `--rm`. No Docker socket,
  host networking, env-file mount, published port, or Compose action.
- Runs the **four canonical trees**, explicit isolation/asyncio plugins, no
  marker exclusions. Final result: **1147 passed, 5 failed, 1 warning in 91.49s**,
  exit **1**. Earlier run: same counts in **91.17s**. Final wrapper includes a
  multiprocessing main guard; the full-run timeout still occurs, so that wrapper
  change is **not** claimed to fix or explain it. No further broad retries.

**RT-001 — confirmed feature harness compatibility defect, backend rework needed:**
WeasyPrint → cffi → `ctypes.util.find_library` → `['/sbin/ldconfig', '-p']`
is rejected by `src/budget_api/tests/isolated_run.py:91`, then `:49–52`.
Four affected tests:

1. `mega/tests/test_release_gate.py::test_synthetic_release_gate_builds_full_report_and_every_registry_section`
2. `v4_pipeline/tests/test_accounting.py::test_monthly_report_html_renders_to_real_pdf`
3. `v4_pipeline/tests/test_accounting.py::test_monthly_report_keeps_norwegian_text_through_html_and_pdf_render`
4. `v4_pipeline/tests/test_data_loader.py::test_utf8_json_loader_to_html_to_real_pdf_chain`

The last test reproduces alone through the **standard guarded module entrypoint:
1 failed in 1.91s**. All four unchanged native tests pass without the feature
Python plugin in the **same physically isolated synthetic-only container:
4 passed in 82.40s**. That bounded comparison is not a full unguarded suite or
a substitute canonical pass. It also exercises the optional native extraction.
Backend follow-up must preserve protection while handling trusted native-library
discovery and add focused allow/deny regressions; do not blanket-allow subprocesses
or hide native failures with a renderer skip. No backend edit was made in this
frontend/runtime assignment.

**RT-002 — unresolved full-run timeout, cause not established:**
`v4_pipeline/tests/test_accounting.py:1197` waits five seconds for the child
publisher lock and times out in both canonical runs. The same unchanged test
passes alone through the standard guarded entrypoint: **1 passed in 3.51s**.
No feature attribution or baseline repair is claimed. Preserve for backend/QA
triage rather than weakening its assertion.

Additional native evidence:

- **Windows actual UTF-8 JSON → HTML → PDF → installed pdftotext 4.00: 1 passed
  in 1.21s**, standard guarded runner, no exclusions. The tool was present, so
  the test's optional extraction branch executed.
- **Linux actual `/usr/bin/pdftotext` through the unchanged strict temp-file
  guard: pass**, separate generated text PDF, expected text extracted, exit 0,
  temporary root removed. `runway-linux-output/runway-linux-extractor.json`.
  Initial session-generated PDF used an invalid direct content-stream object;
  corrected to indirect PDF objects in the session fixture only. No app/harness
  policy or baseline PDF changed. This proves the extractor exception, **not**
  WeasyPrint startup or canonical success.
- Exact commands/stdout: `runway-linux-command{,-initial}.json`,
  `runway-linux-diagnostics.json`; environment/results:
  `runway-linux-output/runway-linux-results{,-initial}.json`;
  staged hashes: `runway-linux-stage.json`. Reproduction scripts:
  `stage-runway-linux.py`, `run-runway-linux.py`, `diagnose-runway-linux.py`,
  `runway-linux-harness/{run_validation,extractor_probe}.py`,
  `runway-linux-provision/{Dockerfile,requirements.txt}`.
- One existing TestClient warning in canonical runs. Native comparison reported
  the unused `asyncio_mode` option (plugin intentionally absent) and a future
  HarfBuzz-Subset prerequisite warning. No dependency churn to silence them.

### Cleanup, handoff and self-review

Backend bridge exited **0**, verified unchanged source hashes, no credential
file, and deleted temporary fixture root. Chromium context/browser closed; static
helper terminated and its exit awaited. Exact helper PIDs absent and **no 5203
listener** on final check. All own containers auto-removed; filtered container
check empty. Removed only the two newly created public/session image tags;
user images/containers/Compose stack untouched.

Repository manifest for this pass:
`docs/specs/003-runway-burn-rate/{quickstart,tasks,review-report}.md`, `memory.md`.
All new scripts/JSON/screenshots/staged files are in session artifacts, not repo.
No user-visible component/style/config edits; component-test requirement is
unchanged and prior **414 tests/build** remain verified historical evidence.

- 🔴 RT-001: Linux native discovery blocked by guard; coordinator/backend rework required.
- 🟡 RT-002: Full-run lock timeout; isolated pass, cause unverified.
- 🟡 Human observation deferred; no independent review2 or Ubuntu pass claimed.
- ❓ No question for absent user. T034/review2 and original merged-plan gate
  remain open/**NOT passed**. No branch change, commit, push or PR.

The execution records below are **historical**, preceding this runtime pass;
their “pending” statements describe those handoffs, not replacement current status.

## Review 1 backend rework — 2026-10-31

The supplied independent report, exact findings, remediation status, retained
OWASP checklist, and open gates are in [review-report.md](review-report.md).
No final QA pass or human acceptance is claimed.

### Fixes and regression record

- **QA-001:** Candidate-wide identity conflict scan precedes common-window
  acceptance. Every affected month is invalid, including conflicts found in
  partial sources or after malformed rows. Source collection evidence is retained.
  Identical object-key-reordered copies count once; distinct IDs are not merged.
  Source/record order, malformed/partial source, and real-route regressions pass.
- **QA-002:** Embedded category titles must be strings. Lists/objects cannot be
  coerced into repayment evidence. Invalid July is excluded (A: **2.6** months);
  valid string repayment still excludes the purchase (A: **3.9** months).
- **QA-003:** Conftest import has no global guard/Popen effect. Feature tests
  activate/restore guards at execution scope. Explicit pytest plugin
  `-p budget_api.tests.isolated_run` supplies early global temporary defaults and
  per-test legacy aliases; the runner uses the same plugin.
- Renderer exception is limited to installed `pdftotext`, an absolute PDF resolving
  inside the active temporary scope, and stdout output (`"-"`). Captured
  stdout/stderr, disabled stdin, matching temp cwd, no shell/executable/env
  overrides or extra flags. Policy and intercepted-launch tests pass;
  no native renderer was run here.
- Red calculator regressions: **7 failed, 3 passed, 79 deselected**.
  Red harness regressions: **2 failed, 5 deselected**, including the exact
  protected mkdir failure before the mock copy error. Guards rejected that
  operation before protected filesystem access.
- Final ordinary focused pytest: **158 passed, 1 warning in 7.01s**.
- Final safe canonical Windows regression: **1150 passed, 2 deselected,
  1 warning in 34.89s**. Only the existing Windows `pdf_renderer` exclusion.
- Final two timing/recipe probes: **2 passed, 1 warning in 1.66s**.
  Service-only **0.312s**; fresh-process in-process ASGI GET **0.146s**.
  Both use 10,000 synthetic transactions and 20 mappings. Different execution
  contexts; not comparable benchmarks, backend-to-browser SC-005, or guarantees.
- One existing Starlette TestClient/httpx deprecation warning; no dependency
  install or dependency declaration/lock change. Frontend's prior **414** passes
  remain historical evidence, not rerun by this backend assignment.

Exact final focused invocation (feature subtree only; no collection-time app
imports and explicit feature fixtures provide temporary data + scoped guards):

```powershell
$env:BILLS_CALC_LOG = '0'
$env:PYTHONPATH = 'src'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
uv run --offline --frozen --no-sync python -m pytest -p pytest_asyncio.plugin src/budget_api/tests/runway -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

Ordinary pytest compatibility proof uses the opt-in early plugin, not just the
custom runner. It collects the feature alongside the actual legacy export tests.
`test_ordinary_pytest_plugin_handles_feature_collection_and_legacy_aliases`
executes this in a guarded child and asserts **4 passed**:

```powershell
$env:BILLS_CALC_LOG = '0'
$env:PYTHONPATH = 'src'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
uv run --offline --frozen --no-sync python -m pytest -p budget_api.tests.isolated_run -p pytest_asyncio.plugin src/v4_pipeline/tests/test_save_ps_data.py src/budget_api/tests/runway/test_calculation.py::test_contract_arithmetic_and_no_source_writes -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

Canonical Windows command is unchanged from section 4. Do **not** apply the
feature-only ordinary invocation to the full suite without the explicit plugin
or runner. CI configuration is unchanged; importing the feature no longer alters
unrelated tests. Global isolation remains an intentional local opt-in.

Timing/recipe probe:

```powershell
$env:BILLS_CALC_LOG = '0'
$env:PYTHONPATH = 'src'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
uv run --offline --frozen --no-sync python -m budget_api.tests.isolated_run src/budget_api/tests/runway/test_calculation.py::test_ten_thousand_transactions_twenty_accounts src/budget_api/tests/runway/test_isolation.py::test_fresh_process_synthetic_integration_recipe -q -s
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

### Exact synthetic service setup for frontend specialist

Historical recipe; latest authorized HTTP recipe above supersedes the
no-server restriction. Use a **fresh Python process**. Keep the browser/static harness isolated as in
section 5. This older recipe starts no backend server and uses no Docker/8080/5200/8100. Do not
read/copy `.env` or real financial data. Keep all temporary helpers outside the
checkout and use `apply_patch` to author any session-only script.

The reusable `World` now lives in
`src/budget_api/tests/runway/synthetic.py`; no importing pytest conftest or calling
a decorated fixture is needed. `World(private).use_large_history()` creates
**10,000** transactions in July/August/September 2026 (**3334/3333/3333**) and
**20 account mappings**. The transactions intentionally use synthetic checking
accounts A/B; the other mappings exercise mapped-account scale, not 20 active
purchase accounts. Default selection is A+B, 120,000 reserves; the v1 record was average gross
spending 100,000/3, displayed household runway **3.6** (calculation v2 net figures not re-recorded here).

Run a script containing this setup only after the PowerShell environment above
is set. It is exercised by `test_fresh_process_synthetic_integration_recipe`:

```python
import os
import sys
from unittest.mock import patch
from budget_api.tests.isolated_run import isolated_environment
from budget_api.tests.runway.synthetic import A, MONTHS, NOW, World

assert os.environ["BILLS_CALC_LOG"] == "0"
assert "budget_api.main" not in sys.modules
with isolated_environment() as private:
    from budget_api.services import env_writer, storage
    assert storage.PRIVATE_DATA_DIR == private
    assert env_writer.ENV_PATH == private.parent / ".env"
    assert os.environ["ENV_FILE"] == str(env_writer.ENV_PATH)
    assert not env_writer.ENV_PATH.exists()

    world = World(private)
    world.use_large_history()
    world.write()

    from budget_api.services import runway
    from budget_api.main import app
    from fastapi.testclient import TestClient

    with patch.object(runway, "local_now", lambda: NOW), TestClient(app) as client:
        settings = client.get("/api/settings/runway")
        result = client.get("/api/bills/runway")
        assert settings.status_code == result.status_code == 200
        assert result.headers["cache-control"] == "no-store"
        assert result.json()["included_months"] == MONTHS
        assert result.json()["household"]["runway_display"] == "3.6"
        saved = client.put("/api/settings/runway", json={"liquid_account_ids": [A]})
        assert saved.status_code == 200
        assert client.get("/api/bills/runway").json()["household"]["reserves"] == 90000
        assert client.get("/api/bills/dashboard?month=2026-10").status_code == 404
```

`isolated_environment()` sets guards and redirects **all storage-derived paths**,
the credential `ENV_PATH`, any loaded `ENV_FILE` aliases, and the `ENV_FILE`
environment variable before app import. No credential file is created. It
restores prior paths/environment and removes its temporary root on exit.
Freeze `runway.local_now` for **the entire client/request lifetime**, not only
fixture writing. Keep the context open across GET/PUT/GET so selection persists.
Use a new context/world for each scenario; the example above ends with A-only
selection and must not become another scenario's starting state.

For browser integration without a backend socket:

1. Keep this TestClient/context in a dedicated synthetic Python helper process.
   Use stdin/stdout JSON-line IPC from the existing isolated browser harness.
   Start it using the already provisioned Python and
   `-m budget_api.tests.isolated_run --child <absolute-temp-script.py>`.
   Set `BILLS_CALC_LOG=0`, absolute worktree `PYTHONPATH=.../src`, and disabled
   plugin autoload in the child environment before any imports.
2. Intercept **every** `/api/**` request in the browser. Forward only
   GET `/api/bills/runway`, GET/PUT `/api/settings/runway`, and optionally the
   exact missing-Bills request shown above, into `client.request(method, path,
   json=body)` inside that context. Validate IPC method/path/body shape and allow
   only those fixed route/method pairs; never accept arbitrary URLs or code.
3. Return the actual TestClient `status_code`, response content type, cache-control,
   and body through IPC to browser `route.fulfill`. Do not substitute stored
   response JSON for the measured runway requests. Other app routes require
   explicitly declared synthetic fixtures or a fail-closed error; never
   `route.continue()` or fall through to an existing API/proxy.
4. Measure browser user action through IPC, actual ASGI calculation, response,
   and painted panel. Record initial load and post-save separately, dataset
   count, environment, and unhandled-request count. Backend-only timestamps or
   the previous stubbed browser checks do not satisfy this measurement.
5. End the helper by closing stdin, wait for clean context exit, and stop only its
   exact process if needed. Leave all existing services untouched. No human
   comprehension or independent acceptance is implied by this setup.

This pass ran only the TestClient recipe and its tests, **not** the browser/IPC
bridge or a server. Coordinator/frontend follow-up owns that evidence.

### Backend rework file manifest and boundaries

- `src/budget_api/services/runway.py`
- `src/budget_api/tests/isolated_run.py`
- `src/budget_api/tests/runway/{conftest,synthetic,test_calculation,test_api,test_isolation}.py`
- `docs/specs/003-runway-burn-rate/{review-report,quickstart,tasks,data-model,research}.md`
- `memory.md`

`synthetic.py` and `review-report.md` are new in this rework; the other listed
files were amended from the existing feature. **No database/schema migration**,
route/response-contract change, frontend edit, dependency change, server, live
data/network, branch switch, commit, push, or PR. T033/T034 and the failed
publication gate remain open.

## Backend execution record — 2026-10-31 (prior pass, not rerun by frontend)

- Setup-tasks and `check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks`
  succeeded with explicit `SPECIFY_FEATURE_DIRECTORY=docs\specs\003-runway-burn-rate`.
  Requirement checklist: 16/16 requirements-quality checks, not implementation checks.
- Tests were written first. Initial guard-proof/red sample: **3 passed, 1 failed,
  1 error**; calculation/API failures were missing runway implementation.
- The existing Python command reported missing `pytest_asyncio`; only then ran
  `uv sync --locked`. No `pyproject.toml` or `uv.lock` edits. Installed lock versions
  include Python 3.13.7, FastAPI 0.141.1, Pydantic 2.13.5, pytest 9.1.1.
- Fixed test-harness startup deadlock by resolving the temp root before installing
  audit hooks; normalized Windows long/short temp paths. Windows asyncio's exact
  stdlib socketpair self-pipe is permitted; arbitrary loopback/network calls fail.
- Final focused backend: **124 passed, 1 warning in 3.45s**.
- Final canonical Windows suite, all four trees: **1116 passed, 2 deselected,
  1 warning in 34.29s**. The two `pdf_renderer` tests were excluded per Windows CI policy.
- Initial canonical guarded run was **1093 passed, 10 failed, 2 deselected**:
  nine subprocess checks were blocked and an existing save-export CLI test tried
  the default private-directory mkdir. Guards stopped it before filesystem access.
  Extended the opt-in runner with guarded Python children, an exact read-only
  `git ls-files -z` command, and per-test temporary defaults for imported legacy
  aliases. All ten now pass without changing legacy production code/tests.
- Focused harness/CLI proof after that change: **18 passed, 1 deselected**.
- Final backend performance: **0.241s**, 10,000 synthetic transactions across three
  months and 20 mappings on this Windows/Python 3.13.7 environment. Separate
  timing test: **1 passed in 0.31s**. This is service timing, not browser SC-005
  acceptance or a production latency guarantee.
- One pre-existing dependency warning: Starlette's TestClient deprecates httpx
  in favor of httpx2. No new dependency added to silence it. No remaining observed
  backend test failures. Dependency/constitution drift remains recorded in plan.
- No server, Docker, live API, credentials, real financial files, main-checkout
  access, branch changes, commits, push, or PR used. All financial fixtures were
  generated into temporary directories with neutral labels and synthetic IDs.
- Explicit content scan: **19 changed/feature text files, zero identity or
  private-path findings** (includes untracked artifacts; not only `git ls-files`).
  `git diff --check` passed. Dependency pins and feature/gate configuration unchanged.

### Direct self-review

- 🔴 Resolved: corrupt mappings could fabricate zero reserves; malformed consumed
  types could escape as 500s; JSON null could masquerade as absence; duplicate PUT
  keys were accepted; validation field names could echo money. Regression tests
  cover each. Decimal accumulation handles signed cancellation before conversion.
- 🔴 Resolved: equivalent timestamp offsets falsely qualified common collection
  time; historical month/bank-date midnight must use that date's local DST offset,
  not the calculation date's offset. Fresh/qualified and calendar regressions pass.
- 🟡 Bounded read check cannot detect change-and-restore between reads or changes
  after the final check; documented design limitation, not a filesystem transaction.
- 🟡 Existing atomic helper can leave its temp file if replace fails; prior settings
  bytes are preserved and error is safe. No shared storage refactor introduced.
- ❓ No open backend design question. At backend handoff, frontend/privacy/browser
  work remained unchecked; current frontend evidence follows below. Ubuntu/native
  renderer validation and merge/review gates remain open.

## Frontend execution record — 2026-10-31

### Identity and isolation

- Executor: frontend implementation session, no subagents. Windows 11
  `10.0.26200`, Node `22.13.1`, pnpm `10.30.3`, TypeScript `5.9.3`,
  Vitest `4.1.11`, Vite `6.4.3`, React `19.2.8`.
- Revision `979a01c5daca080cd141bfdb2c82970488998018` plus dirty frontend content ID
  `1bc2e34814131608ed33b93e8d5c2ec4d590da9af33cceacb494583bc26f1bc5`.
  This identity hashes all 14 frontend files, including new untracked files,
  rather than claiming the base SHA identifies this implementation.
- Session artifact directory: `<local-evidence-dir>`.
  `runway-frontend-identity-final.json` records absolute tested/served worktree identity,
  OS, generation time and per-file hashes. No main-checkout access.
- `runway-vite.config.mjs` imports this worktree's existing config, overrides
  `envDir` to an empty session directory, narrows the environment prefix, fixes
  the synthetic API base to same-origin, and removes server/preview proxies.
  No real `.env` was opened or implicitly loaded.
- `runway-network-guard.ts` blocks unmocked fetch/XHR and fails the test. Tests
  replace it only with synthetic API mocks. Unknown runway routes throw before
  any network; Chromium additionally aborts every unknown route or other origin.
- Initial normal command failed because Vitest was absent. Only then ran
  `pnpm install --frozen-lockfile`: 320 packages reused from cache, no lockfile or
  package declaration edits. Existing ignored `@parcel/watcher` build-script
  warning retained. No repository dependencies added.
- Python Playwright import and `pnpm exec playwright --version` both failed.
  Playwright `1.64.1` was then installed **only in session artifacts**, using the
  already cached Chromium `156.0.8078.4`; no repository tooling/dependency change.
- Static helper served only generated frontend assets on `127.0.0.1:5203`.
  Its fixed file allowlist rejects API requests with 503; it has no proxy, env
  loader, backend imports, or financial source access. Readiness was verified
  before navigation. The helper was attached and explicitly stopped afterward.
  No Docker, 8080 stack contact, 5200/8100 usage, backend server or live API.

### Evidence by check type

| Check | Observed result | Evidence / boundary |
|---|---|---|
| Static self-review | No open runway correctness finding; `git diff --check` passed | Direct source/diff review; no independent QA approval |
| Tests-first | Two suites failed on absent Runway imports; later 3 Bills integration tests failed before page integration | Actual red runs, followed by passing implementation |
| Focused automated tests | **62 passed**: 8 hook + 47 panel/presentation + 7 page, exit 0 | `runway-focused-tests.json`; 18:07:38.941–18:07:43.187 UTC, 4.246s recorded interval |
| Full automated tests | **414 passed, 44 files**, exit 0 | `runway-full-tests-final.json`; 18:08:01.812–18:08:27.092 UTC, 25.280s recorded interval |
| Typecheck/build | `pnpm exec tsc --noEmit` and `pnpm build` passed, exit 0 | `tsc -b` + Vite production build; final Vite run reported 16.29s |
| Browser runtime, intercepted API | **B1–B7 passed**, 8 screenshots | `runway-browser-results.json`; actual Chromium, not a unit-test substitute |
| Backend integration | Not run in frontend pass | Prior isolated backend evidence above; no live backend |
| User/independent acceptance | **Not run / pending** | T033 human comprehension and actual integrated latency; T034 review/Ubuntu/renderer/gates |

Initial full guarded run: **407 passed, 7 failed**. The guard blocked five
pre-existing SettingsPage tests missing categories/split mocks and two BillsPreview
alias tests missing new runway mocks. Added only test-local synthetic mocks;
no Settings production code changed. The first passing full run (33.764s) is
preserved in `runway-full-tests.json`. Subsequent test-only review fixes awaited
pending renders and wrapped privacy teardown in `act`; a PUT no-store assertion
was added. Final focused/full checks above pass with no runway-related warnings.
Existing React `act` warnings remain in MegaReportsPage and GraphView tests.
Build reports mixed dynamic/static `types/api.ts`
import and >500kB bundle advisories; no new splitting/dependency work attempted.

Production artifact: `runway-dist/assets/index-CX5td9Oz.js`
SHA-256 `e989b7bee50c9ffed7abcbf9cf56aea6293059fcacf373287d8663b2bd5399e6`;
CSS `index-LRYoX6KZ.css`
SHA-256 `723e45e3e8007264ea39a73e6e0c53ce936c9e848c6c3174742f2401283b8e1c`.
The browser report hashes the served assets and every screenshot. The final
rebuild produced identical asset hashes and the fixture is unchanged, verified
against the browser report. Browser evidence therefore carries forward through
the subsequent test-only edits; earlier frontend identity
`b599c172cb2de95dfd5124db4802ede75059731098435f630e0639817ba7527e`
is preserved in `runway-frontend-identity.json`. Typed fixture
hash: `2a1c8fdb8f2e47e399760a64664949ce0fb83a6623e5ba575df911abc33a4e52`.
Schema/calculation version 1, synthetic as-of October 2026, July–September history,
stale recorded balance dates and unknown catalog collection deliberately retained.

### Synthetic browser observations

Run: **2026-10-31T18:02:00.086Z–18:02:09.002Z** (UTC); desktop 1440×1000,
mobile viewport 390×844. Expected bounds were the spec's ≤2s displayed result,
≤1s masking, and ≤120s configuration. Times below are automated synthetic
observations, not human usability or real-backend timing.

| ID | Action and exact observation | Verdict / artifact |
|---|---|---|
| B1 | With missing current Bills snapshot and 250ms mock result delay: loading visible, then `"3.0 months"`, `"0.5 months"`, `"1.3 months"`; household `"120,000 kr"` / `"90,000 kr"`; **447.408ms** from navigation | Pass for stubbed UI latency only; `runway-happy-desktop.png` |
| B2 | Hide/show amounts with B unchecked in the unsaved draft: monetary text/attributes absent, `"1.3 months"` visible, same draft, **zero requests**; masking **43.860ms** | Pass; `runway-masked-draft.png` |
| B3 | Save returns 400: draft and saved `"1.3 months"` remain. Retry saves A only: `"1.0 months"`; reload confirms selection; **no Bills refetch** | Pass; `runway-saved-selection.png` |
| B4 | Clear draft then explicit Save: `"Select liquid accounts"` and `"Unavailable"`, never `"0.0 months"` | Pass; `runway-unavailable-empty.png` |
| B5 | Settings 500 disables Save; retry restores choices. Result 500 labels retained figures; retry shows July/September included and August missing, plus coverage/currency/date warnings | Pass; `runway-settings-error.png`, `runway-qualified-missing-month.png` |
| B6 | At 390px, panel x=24, width=342; client/scroll width both 340. Cards, evidence and open settings fit without panel overflow | Pass for Runway; `runway-mobile-panel.png`. Existing global nav causes document width 562; shell unchanged |
| B7 | Ten eligible accounts: Enter opens settings; Tab/Space selects A+B; Tab/Enter saves, scope visible and `"1.3 months"`; **203.705ms** scripted interaction | Pass for keyboard activation; `runway-keyboard-config.png`. Not human comprehension acceptance |

Browser report: **zero unknown requests, zero page errors, zero API requests
reaching the static helper**. All financial values are neutral synthetic fixtures.
Desktop/mobile screenshots were viewed during self-review. All eight PNGs and
the browser script/results stay in session artifacts, not the repository.
After stopping the helper, an explicit port check confirmed no listener on 5203.

### Frontend file manifest and self-review

Created:

- `client/src/types/runway.ts` — exact response/request DTOs.
- `client/src/api/runway.ts` — typed no-store GET/PUT wrappers.
- `client/src/hooks/useRunway.ts` — independent reads, drafts/save and request generations.
- `client/src/lib/runway.ts` — justified shared static issues, dates and masked currency display; no financial math.
- `client/src/components/bills/RunwayPanel.tsx` — owner/household results, evidence and independent states.
- `client/src/components/bills/RunwaySettings.tsx` — explicit eligible selection, reset/reload and safe Save.
- `client/src/hooks/__tests__/useRunway.test.tsx` — lifecycle, failure and race checks.
- `client/src/components/bills/__tests__/runway.test.tsx` — behavior, masking and all 29 contract issue mappings.
- `client/src/components/bills/__tests__/runway-fixtures.ts` — typed synthetic-only fixtures.

Modified:

- `client/src/api/client.ts` — optional cache policy, prior callers unchanged.
- `client/src/pages/BillsPage.tsx` — stable Runway mount outside Bills branches.
- `client/src/tests/BillsPage.test.tsx` — missing/legacy Bills and window/draft independence.
- `client/src/components/bills/__tests__/BillsDashboard.test.tsx` — alias route mocks.
- `client/tests/SettingsPage.test.tsx` — close pre-existing test network gap.
- `README.md`, this feature's `plan.md`, `tasks.md`, `data-model.md`,
  `contracts/runway-api.md`, `quickstart.md`, and root `memory.md` — usage,
  implementation/evidence/handoff alignment. No backend production edits this pass.

No component test exemption used. Local new patterns requiring team review:
native `<details>` for expandable runway settings and the narrow optional cache
argument on existing API helpers. No new library, store, generated API framework,
or persistent browser data. Session-only safety/browser tooling is not production.

- 🔴 Resolved: settings read error displayed a false zero-account saved count;
  successful Save claimed refresh success after a failed result read; unknown
  issue code could access inherited object keys. Failing regressions preceded fixes.
- 🔴 No open runway bug found in direct self-review.
- Static added-content identifier and UTF-8/BOM checks passed for all 21 frontend
  and documentation files. The existing README repository URL is unchanged and
  outside the added-content scan; this is not a claim to have rescanned private data.
- 🟡 Existing global nav overflows at mobile width; Runway itself does not.
- 🟡 No browser+real backend timing or human five-fact comprehension result.
  Do not promote the synthetic timings to SC-005 or user-acceptance sign-off.
- ❓ No implementation question. Independent QA, Ubuntu/native renderer checks,
  and the original review/merged-plan gates remain T033–T034.

## 1. Prerequisites and non-negotiable isolation

- Stay in the dedicated app-managed worktree. Never switch
  branches or use the main checkout.
- Use an already provisioned Python >=3.13 environment and existing locked
  dependencies. Commands below deliberately disable uv network/sync; they do not
  install packages. Client uses Corepack-managed `pnpm@10.30.3` and its existing
  frozen lockfile. No new dependency is needed.
- Never read/copy real financial files or credentials into fixtures. Do not start
  the normal app, run live sync, touch existing Docker/Compose stacks, or use
  default 5200/8100 endpoints. The latest continuation permits only the separate
  bounded code-staged container described in the runtime record above.
- Set `BILLS_CALC_LOG=0` **before Python starts**, not in a fixture after imports.
  Bills-builder import can otherwise create a private calculation log.
- `src/budget_api/tests/runway/conftest.py` has an autouse fixture
  explicitly requesting **both** `tmp_private_dir` and `tmp_env_file`. Existing
  parent fixtures are opt-in, not global safeguards.
- Patch all consumed storage paths and any already-imported aliases before app
  import/TestClient lifespan. New config path must derive from patched
  `PRIVATE_DATA_DIR`; no static unpatched fallback. Temp credential path may stay
  nonexistent: no API key needed.
- Feature tests must fail immediately on attempted real protected-path I/O or
  external network access. Patch/guard outbound socket/HTTP/urllib entry points
  before constructing the app client; the in-process TestClient is not an external
  server. Exercise guards against dummy protected-path sentinels, never by opening
  the actual private directory or credential file.
- Frontend tests must stub **all** API methods/global fetch used by the rendered
  tree before render. Unhandled fetch must throw. Existing test setup does not
  globally block the API fallback.

**Stop if any prerequisite cannot be demonstrated from code.** Environment
variables alone do not relocate the app's hardcoded private storage paths.
Do not use a successful targeted test as proof of suite-wide isolation.

## 2. Focused backend validation

Run from this worktree root; test collection is limited to the new runway subtree,
not the existing Bills suite and its collection-time imports:

```powershell
$env:SPECIFY_FEATURE_DIRECTORY = 'docs\specs\003-runway-burn-rate'
$env:BILLS_CALC_LOG = '0'
$env:PYTHONPATH = 'src'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
uv run --offline --frozen --no-sync python -m budget_api.tests.isolated_run src/budget_api/tests/runway -q
$code = $LASTEXITCODE
if ($code -ne 0) { exit $code }
```

The runner loads the existing pytest-asyncio plugin plus its explicit isolation
plugin, installs audit guards
before pytest collection, and uses a fresh temp root. Dependency restore is not
part of this command; an actual missing-tool/package failure must precede restore.

Required fixtures use neutral `Partner A`/`Partner B`, synthetic account IDs
`1100001` etc., reserved synthetic transaction IDs consistent with repository
fixture policy, deterministic payees, and a frozen October 2026 local clock.
Construct/write synthetic source files only inside pytest's temp directory.

Required results:

1. Reproduce [contract arithmetic](contracts/runway-api.md#synthetic-arithmetic-acceptance):
   A 90,000 / 30,000 = 3.0 months; B 30,000 / 60,000 = 0.5;
   household 120,000 / 90,000 = 1.3. Confirm sum-once, not mean-of-ratios.
2. Verify 3/2/1/0 common months, holes without backfill, January/leap boundaries,
   local rollover, known pre-month-end/partial sources, explicit complete zero,
   and unknown positive versus unknown zero. A zero owner without coverage excludes
   that month for everyone.
3. Spending equals Reports `household_totals.total` (net): purchases minus refunds/
   reimbursements, so a refund reduces burn and months can be zero or negative.
   Card repayments, transfers, savings and excluded categories follow Reports routing.
   Both repayment legs, savings overrides, investments, transfer
   flags, excluded accounts/categories, pending entries, and duplicate repeats
   never inflate it. Conflicting IDs across candidate sources invalidate every
   affected month; invalid dates/amounts invalidate their source month.
4. Missing selection has no GET write; explicit empty Save resets without false
   zero. Duplicate/unknown/ineligible/unowned/malformed selections and unsupported
   fields reject as a whole and preserve prior bytes. Selected account removal,
   reassignment, missing/invalid balance, and unresolvable ownership are visible.
5. Signed 10,000 + -2,000 = 8,000; zero/negative reserves and zero burn retain
   observations with null ratio. Verify half-up 1.25 => 1.3 and tiny positive
   ratio => `<0.1`; no non-finite or underflowed-zero output.
6. Verify per-owner and household currency conflict boundaries, unknown currency,
   stale/unknown dates, different collection times, every applicable issue, and
   unchanged source age after recalculation.
7. Simulate source byte changes, running sync, save failure, unsupported queries,
   invalid JSON, and settings-load failure. No source or legacy snapshot writes,
   no PS/sync call, no credentials, no fallback.
8. Test 200/400/409/500 cases and no-store for all three operations. Serve an older
   Bills snapshot through the existing dashboard using the same isolated client;
   assert its values/shape unaffected. A missing current snapshot still permits
   runway from local sources. Do not import/run unrelated legacy builder tests
   simply to establish this endpoint compatibility.

## 3. Reproduce safe client checks and build

The session wrapper and network guard described above must exist and point to
this worktree. Inspect their **code**, not any environment file, before reuse.
For another checkout, author equivalent session-only files with that checkout's
absolute config/setup imports. Never run the default Vite config against a real
environment directory. The wrapper keeps existing plugins/aliases/test setup.

```powershell
$env:SPECIFY_FEATURE_DIRECTORY = 'docs\specs\003-runway-burn-rate'
$artifacts = '<local-evidence-dir>'
$config = Join-Path $artifacts 'runway-vite.config.mjs'
Set-Location -LiteralPath 'client'
pnpm exec vitest run --config $config src/hooks/__tests__/useRunway.test.tsx src/components/bills/__tests__/runway.test.tsx src/tests/BillsPage.test.tsx
$code = $LASTEXITCODE
if ($code -ne 0) { exit $code }
pnpm test --config $config --reporter=default --reporter=json --outputFile.json="$artifacts\runway-full-tests-final.json"
$code = $LASTEXITCODE
if ($code -ne 0) { exit $code }
pnpm build --config $config --outDir "$artifacts\runway-dist" --emptyOutDir
$code = $LASTEXITCODE
if ($code -ne 0) { exit $code }
```

This builds without launching a server or loading real environment files.
`--emptyOutDir` applies only to the dedicated session build directory. `tsc -b`
also emits ignored `client/vite.config.{js,d.ts}` and `client/*.tsbuildinfo`;
the frontend session moved those generated files into `runway-tsc-metadata` in
session artifacts after verification. No authored config was removed.
Do not replace missing guards with a full unguarded test run.

Verify:

- Loading, domain unavailable, qualified/stale, and transport-error/retry states.
- Bills failure/current-snapshot absence does not hide or block runway; runway
  failure does not block available Bills.
- Failed settings load disables Save; failed save keeps unsaved choices and labels
  retained numbers as using the saved selection. Successful Save refreshes only
  runway, not Bills or sync.
- Delayed pre-save result cannot overwrite post-save result; delayed settings
  responses cannot wipe an edited draft/new saved selection.
- Owner labels and order never change calculation attribution.
- Hide amounts masks money including negatives/zeros, account amounts if rendered,
  observations, titles, tooltips, and ARIA. Inspect DOM attributes as well as
  visible text. Ratios/counts/months stay visible; toggling makes zero fetches,
  preserves draft, restores original display, and responds within one second.
- Labelled keyboard controls, semantic headings/tables, status/live-region copy,
  and errors understandable without color.

No client lint command is specified because `package.json` has no lint script.

## 4. Wider regression — guarded runner required

Do **not** run the complete Bills or canonical suite as-is. The opt-in
`src/budget_api/tests/isolated_run.py` runner establishes temporary storage and env
defaults before app imports, redirects imported backend/legacy path aliases per
test, and guards financial filesystem paths plus external network calls at the
Python audit boundary. Guarded child interpreters run through the same entrypoint.
Only the exact current-root tracked-file listing and validated temporary-PDF
`pdftotext` extraction bypass that Python wrapper; see review-1 policy above.
`src/budget_api/tests/runway/test_isolation.py` proves parent/child guards and
rejects arbitrary subprocesses; the record above includes the CLI proof.
Feature-local fixtures alone are still not a global safety guarantee.

The validated canonical Windows command is:

```powershell
$env:SPECIFY_FEATURE_DIRECTORY = 'docs\specs\003-runway-burn-rate'
$env:BILLS_CALC_LOG = '0'
$env:PYTHONPATH = 'src'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
uv run --offline --frozen --no-sync python -m budget_api.tests.isolated_run src/mega/tests src/v4_pipeline/tests src/mom/tests src/budget_api/tests -m "not pdf_renderer" -q
$code = $LASTEXITCODE
if ($code -ne 0) { exit $code }
```

Ubuntu Python 3.13 validation follows the same canonical suite without the Windows
renderer exclusion, in a separately verified isolated environment with native
renderer prerequisites. The Linux attempt above is Debian, not Ubuntu, and found
RT-001/RT-002. Do not install host native tooling or edit CI in feature 003;
session-container provisioning after demonstrated missing prerequisites is the
explicitly authorized exception.

Use the guarded/environment-isolated variants in section 3 for client merge checks.
CI/merge requirements are not waived if
safe local full-suite execution is blocked; report the pending evidence.

## 5. Synthetic browser acceptance — separate runtime evidence

The frontend record above used an isolated static build/helper, not a Vite dev
server or backend. Its session-only `runway-browser/serve.mjs` and `acceptance.mjs`
are the reproducible harness; start only an attached helper, verify its
`/__runway-test-status` readiness, run acceptance, and stop that exact helper.
For future checks, prefer a browser harness that
intercepts every API request and returns the deterministic contract fixtures;
fail all unmatched requests. No production API process is needed for this path.
Use port **5203** only if a Vite UI server is needed, loopback host and strict port.
Before starting it, use an already available browser harness that installs route
interception before navigation and a Vite invocation with an **empty environment
directory** so no `.env` files are loaded. Set `VITE_API_URL` to the same-origin
root for that isolated session. Do not let unmatched `/api` requests reach the
existing Vite proxy, which otherwise targets 8100. If these controls cannot be
verified, skip browser runtime and report it pending; do not launch the default
dev command or add infrastructure just to get screenshots.

If an actual API process is later necessary, only **8103**, bound to
`127.0.0.1`, with an in-memory/test-only bootstrap that patches temp storage/env,
blocks outbound network **before app import**, and serves deterministic synthetic
data. It must not use ordinary `budget_api.main:app` startup against real paths.
Current CORS does not include 5203; prefer intercepted same-origin browser
requests, not a production allowlist edit. Record/stop exact helper process IDs
when validation is finished. No Docker or existing application server contact.

Browser scenarios:

1. Populated three-month example: open selection, save/reload, identify accounts
   and owners within two minutes. Confirm 3.0 / 0.5 / 1.3-month ratios.
2. Remove August: show exactly July/September and missing August. Mark known
   source/balance age and unknown metadata beside the result.
3. Exercise no settings, invalid saved account, missing current Bills snapshot,
   settings read failure, save failure/retry, and delayed superseded response.
4. Toggle privacy on/off with an unsaved draft; inspect monetary text/attributes,
   nonmonetary ratio visibility, and zero request count caused by toggle.
5. Ask the synthetic acceptance reviewer to identify selected accounts, included
   months, net-as-in-Reports basis, owner attribution (common economy split shares or
   This comprehension result is not implied by unit tests.

For SC-005, generate 10,000 deterministic transactions across the three candidate
months and 20 mapped accounts inside the isolated fixture. Record machine/runtime,
dataset size, service timing and browser observed loading/result latency; target
<=2 seconds. A stub-only browser cannot prove backend performance: use separate
in-process service/API timing plus explicit end-to-end evidence if a safely
isolated process is available. Do not claim the target passed from architecture.

## 6. Evidence and stop conditions

Report separately: static review; build; focused automated tests; wider regression;
in-process API integration; actual browser runtime; performance; user acceptance.
Record command, environment/isolation evidence, exit status, and synthetic result.
Do not save money-bearing screenshots/logs from real data.

Stop on protected-path/network attempts, unisolated imports, unknown environment
loading, or missing test guards. The explicit user continuation is recorded in
plan/tasks; it does not turn the failed merged-plan gate into a pass. These
validation commands confer no review approval, branch mutation, commit, push,
or publication permission.
