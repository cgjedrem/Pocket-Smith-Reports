# Code Evidence — 001-depersonalize-identifiers

Explorer: code-explorer (read-only trace). Branch: `001-depersonalize-identifiers`. Date: 2026-09-16.
All file:line anchors verified by direct inspection on this branch. HTTP-behavior claim in Q1c verified by an in-memory FastAPI TestClient probe (no repo files touched).

---

## Q1 — Stored-report lifecycle + version marker

### Q1a — Where report JSON is written / read

**Writer.** `src/budget_api/services/report_builder.py:354-356` (`write_report`) → atomic JSON via storage:

```python
def write_report(month: str, report_dict: dict[str, Any]) -> None:
    """Write report JSON atomically to {month}_monthly_report.json."""
    storage.atomic_write_json(storage.monthly_report_path(month), report_dict)
```

Generation flow: `src/budget_api/routers/reports.py:82-111` — `POST /api/reports/monthly/{month}/generate` returns 202 and schedules `_run_generate` (reports.py:84) which calls `report_builder.build_report(month)` (routers/reports.py:90) then `report_builder.write_report(month, report)` (routers/reports.py:91). Status sidecar written to `{month}_monthly_report_status.json` (report_builder.py:364-366).

**Storage path pattern.** `src/budget_api/services/storage.py:12-13,31-33`:

```python
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PRIVATE_DATA_DIR = REPOSITORY_ROOT / "data" / "private"
...
def monthly_report_path(month: str) -> Path:
    return PRIVATE_DATA_DIR / f"{month}_monthly_report.json"
```

→ `data/private/{YYYY-MM}_monthly_report.json` (gitignored private dir; LG-003 in `docs/open-source-launch-gates.md:68-73`). Source transactions per month: `data/private/{month}_ps_raw.json` (storage.py:41-43).

**Reader.** `GET /api/reports/monthly/{month}` at `src/budget_api/routers/reports.py:62-73`:

```python
report = report_builder.read_report(month)          # reports.py:65
...
stale = report_builder.check_stale(month, report)   # reports.py:71
report["stale"] = stale
return ReportResponse.model_validate(report)        # reports.py:73
```

404 when no report on disk (reports.py:66-70: `"no report generated yet"`).

### Q1b — Version marker TODAY

**Yes.** Single constant `CALCULATION_VERSION` in `src/budget_api/services/report_builder.py:46`:

```python
CALCULATION_VERSION = 6
```

History comment at report_builder.py:44-45 (`PR1: 5 — detailed DTO contract`; `PR5: 6 — paired rows display-strings → signed numerics …`). Injected into every built payload at `report_builder.py:334` inside `build_report`'s return dict: `"calculation_version": CALCULATION_VERSION,`.

**Readers/checkers:**
- `src/budget_api/services/report_builder.py:374-376` — `check_stale`: `if report_dict.get("calculation_version") != CALCULATION_VERSION: return True` (also stale on txn-count mismatch, lines 377-383).
- Tests pin it: `src/budget_api/tests/reports/test_golden_fixture.py:67` (`assert golden["calculation_version"] == report_builder.CALCULATION_VERSION`); `src/budget_api/tests/test_report_builder.py:219, 248, 253-263` parametrize missing/old versions `[None, 1, 2, 3, 5]` → stale.
- Golden fixture carries `"calculation_version": 6` (`src/budget_api/tests/reports/golden/sample_apr_2026_report.json:3`).
- Note: `calculation_version` is **not** a pydantic field on `ReportResponse` (`src/budget_api/models/reports.py:228-273`) — it lives only in the stored JSON and in `check_stale`, so unknown stored keys pass validation silently (pydantic default `ignore` extra behavior).

Related but separate: mega reports have their own `MEGA_CALCULATION_VERSION = 1` (`src/budget_api/services/mega_builder.py:37`, injected `:229`, stale check `:263`); bills snapshots carry `schema_version: int = 4` (`src/budget_api/models/bills.py:129`, emitted `src/budget_api/services/bills_builder.py:1174`). These are independent markers from the monthly-report `CALCULATION_VERSION`.

### Q1c — Stored report failing pydantic validation → behavior

The router validates at **read time** with a strict `ReportResponse.model_validate(report)` (routers/reports.py:73). `src/budget_api/main.py:28-29` registers **only** a `RequestValidationError` handler (request-body errors → 400). A `pydantic.ValidationError` raised inside the endpoint is unhandled.

**Verified empirically** (in-memory probe, FastAPI TestClient with `raise_server_exceptions=False`, repo venv 3.13): an endpoint raising `ValidationError` from `model_validate` returns **HTTP 500 "Internal Server Error"**. So today an unreadable/incompatible stored report makes `GET /api/reports/monthly/{month}` 500 — there is no graceful fallback in the endpoint.

Mitigating convention (memory: "compat = defaults + CALCULATION_VERSION bump"): new fields are added as optional/with defaults so older stored reports keep validating and are simply marked `stale: true`. Encoded in tests at `src/budget_api/tests/test_reports.py:295-303` (`TestReportResponseCompat`: "…so GET renders instead of 500ing before Regenerate is reachable") and model defaults, e.g. `normalized_transactions: list[dict] = []` (models/reports.py:244-247 comment: "strict required would 500 on GET before the Regenerate button renders") and `PairedReimbursementRow` defaults (models/reports.py:103-110, 118-123).

### Q1d — Stored-report top-level shape

From `src/budget_api/tests/reports/golden/sample_apr_2026_report.json` (exact key list, alphabetical): `balanced, calculation_version, categories, detailed, detailed_section_mapping, kpis, month, normalized_transactions, owner_totals, partner_labels, partner_panels, personal_share, personal_share_partner_a, personal_share_partner_b, reconciliation, root_totals, savings_summary, txn_count` — exactly the `build_report` return dict (`report_builder.py:332-351`); `stale` is added read-side only (routers/reports.py:72). `detailed` keys: `cc_payments, common, excluded, home, household_totals, income, personal_christian, personal_rasma, savings, trips`. Golden `partner_labels` = `{"partner_a": "Partner A", "partner_b": "Partner B"}` (golden fixture line 1351, defaults because the seeded fixture dir has no label config).

---

## Q2 — Partner labels config

### Q2a — partner_labels.json on disk + readers/writers + defaults

- **Path constant:** `src/budget_api/services/storage.py:25` — `PARTNER_LABELS_PATH = PRIVATE_DATA_DIR / "partner_labels.json"` → `data/private/partner_labels.json` (untracked).
- **Written by:** **nothing in tracked code.** `git grep "partner_labels.json"` shows readers only (report_builder, mega_builder) plus tests (`src/budget_api/tests/test_mega_builder.py:153`, `test_mega_reports.py:26`, `test_mega_acceptance.py:32`, `test_report_builder.py:136` write it into tmp dirs) and `src/budget_api/tests/conftest.py:44` monkeypatching the path. It is an optional legacy override file the user can create by hand (design docs mention a "Partner label UI editor" only as future work — `docs/design/done/design-f1.2-react-reports.md:84`).
- **Primary reader:** `src/budget_api/services/report_builder.py:94-117` `_load_partner_labels()`:

```python
def _load_partner_labels() -> dict[str, str]:
    """Load partner labels from account_mappings.json or partner_labels.json."""
    # Try partner_labels.json first.
    if storage.PARTNER_LABELS_PATH.exists():
        raw = storage.read_json(storage.PARTNER_LABELS_PATH)
        if isinstance(raw, dict) and "partner_a" in raw and "partner_b" in raw:
            return {"partner_a": str(raw["partner_a"]), "partner_b": str(raw["partner_b"])}
    # Fallback: account_mappings.json partners block.
    if storage.ACCOUNT_MAPPING_PATH.exists():
        ... partners[owner]["label"] ...
    return {"partner_a": "Partner A", "partner_b": "Partner B"}   # line 117
```

Resolution order: (1) `partner_labels.json` flat `{"partner_a": …, "partner_b": …}` (both keys required, non-dict/partial → silently falls through); (2) `account_mappings.json` `partners.partner_a/partner_b.label` (both labels required); (3) hard default `Partner A`/`Partner B`. Called from `build_report` (report_builder.py:300), `mega_builder.py:224` (reuses `_load_partner_labels`; also passes the raw file path as `partner_label_map` to the mega CLI when it exists, mega_builder.py:70-73), and `report_pdf.py:54`.
- **v4_pipeline parallel loader:** `src/v4_pipeline/accounting.py:224-249` `load_partner_labels(mapping_path=None)` — with no path, reads `data/private/account_mappings.json` via `load_unified_account_mapping`; with a path, expects the legacy label-only map keyed `partner_a`/`partner_b`; empty label → `AccountingValidationError("Partner label mapping has an empty label")`. Defaults: `DEFAULT_PARTNER_LABELS = {"partner_a": "Partner A", "partner_b": "Partner B"}` (`accounting.py:44`).
- **Settings surface that actually edits labels:** `src/budget_api/routers/partners.py` CRUD on `account_mappings.json["partners"]` (labels), e.g. `update_partner` writes `partners[partner_id]["label"] = label` (partners.py:152-153). `routers/settings.py` is API-key only. Production canonical partner ids are `partner_a`/`partner_b` (README.md:85 example; `report_builder._load_account_owners` at lines 71-91 only bridges `partner_a|partner_b` ids), though `partners.py:_slugify` (lines 23-25) derives ids from labels for newly created partners — test fixtures use slug ids `"christian"`/`"rasma"` (`src/budget_api/tests/conftest.py:57-90`).

### Q2b — Display-name resolution in builder/HTML + escaping

- Monthly-report JSON: `report_builder.py:300` → `partner_labels` dict embedded verbatim in the payload (`"partner_labels": partner_labels`, report_builder.py:345) and into `partner_panels` via `_partner_panels` (report_builder.py:157-177: `panels[owner] = {"label": label, …}`).
- PDF path: `src/budget_api/services/report_pdf.py:54` loads labels, calls `render_html(contract, month, partner_labels, "minimal")` (line 77).
- HTML renderer default when labels are `None`: `src/v4_pipeline/accounting_html.py:966,977-980` — `partner_labels = partner_labels or {"partner_a": "Partner A", "partner_b": "Partner B"}`.
- **Escaping: yes, everywhere** — `accounting_html.py:3` `from html import escape`; labels are interpolated only via `escape(...)`, e.g. lines 147/164 (`<h3>{escape(label)}</h3>`), 390-391 (`<th>{escape(partner_labels["partner_a"])} paid</th>`), 447-449, 459-460, 526, 715-716, 722-724, 760-761, 851-852, 904-905.
- **Hardcoded-name exception:** `_legacy_personal_sections` (`accounting_html.py:784-830`) pairs each personal section with a hardcoded display fallback:

```python
for number, section, partner_key, personal_name in (
    (5, "personal_christian", "partner_a", "Christian"),   # accounting_html.py:818
    (6, "personal_rasma", "partner_b", "Rasma"),           # accounting_html.py:819
):
    partner_label = partner_labels[partner_key]            # :821
    title = f"{number}. {personal_name}"                   # :822
```

`personal_name` ("Christian"/"Rasma") is used for the `<h2>` section title (`:822`) and the chart title `f"{personal_name} personal by category"` (`:861`); the configured `partner_label` is used only in the per-partner `paid` column headers (`:851-852`). Column order also hardcodes personal sections first in the grouped dict (`:792`) and household composition (`:805-815`).

---

## Q3 — personal_christian / personal_rasma call graph (complete)

Full `git grep -n "personal_christian\|personal_rasma"` over **tracked** files, classified (untracked scratch hit `.swarm-tmp/qa-budget-api.md` excluded — not in git):

### (a) DEFINED as data / canonical registries

| Anchor | What |
|---|---|
| `src/v4_pipeline/accounting.py:21-22` | `DETAILED_CATEGORY_SECTIONS` set — canonical math-engine registry of the 10 section keys |
| `src/v4_pipeline/accounting.py:905-906` | `HOUSEHOLD_COMPOSITION` tuple (`:901-908`) — `[home, common, personal_christian, personal_rasma, trips]` |
| `src/v4_pipeline/accounting.py:1194-1214` | `detailed_personal_sections()` — builds the result dict keyed by these names (`:1196-1202` grouped dict keyed `"personal_christian"/"personal_rasma"`; `:1210` `for section in ("personal_christian", "personal_rasma"): result[section] = …`) |
| `src/budget_api/models/reports.py:240-241` | API contract — `DetailedSections.personal_christian: PersonalSection \| None = None` / `personal_rasma` (docstrings also at `:165`, `:218`) |
| `src/budget_api/models/category_mappings.py:17-18` | budget_api's duplicate `DETAILED_CATEGORY_SECTIONS` set (validation enum for the settings API) |
| `src/budget_api/services/report_builder.py:207-208` | `_detailed()` composes DTO: `"personal_christian": personal["personal_christian"],` / `"personal_rasma": …` |
| `src/v4_pipeline/accounting_html.py:792, 810-811, 818-819` | legacy HTML: grouped dict keys (:792), household composition (:805-815), hardcoded partner pairing (:818-819) |
| `data/sample_apr_2026_detailed_section_mapping.json:9-10` | fixture mapping data: `"7": "personal_christian", "8": "personal_rasma"` |
| `src/budget_api/tests/reports/golden/sample_apr_2026_report.json:434, 457, 556-557` | golden stored-report payload — `detailed.personal_christian` (:434), `detailed.personal_rasma` (:457), plus embedded `detailed_section_mapping.category_sections` values |
| `client/src/types/report.ts:230-231` | TS mirror of the DTO: `personal_christian: PersonalSection \| null;` |
| `client/src/types/category_mappings.ts:17-18, 55-56` | TS union type of section keys + runtime array (validator) |

### (b) Consumed by explicit name

| Anchor | What |
|---|---|
| `src/v4_pipeline/tests/test_accounting.py:40-41, 527` | test mappings `"christian": "personal_christian"` etc. |
| `src/mega/build_mega.py:277-278` | `_appendix_transactions` `section_routes` dict maps key→key (`"personal_christian": "personal_christian"`) |
| `src/mega/build_mega.py:511-512` | `personal_a = section_series("personal_christian")` / `personal_b = section_series("personal_rasma")` |
| `src/mega/build_mega.py:519` | household composition loop naming both sections |
| `src/mom/sections/section_personal.py:21-22` | alias map `PERSONAL_SECTION_KEYS = {"personal_partner_a": "personal_christian", "personal_partner_b": "personal_rasma"}` |
| `src/mom/sections/section_appendices.py:43-47` | appendix section list: `("personal_christian", f"Personal — {partner_a}"), ("personal_rasma", f"Personal — {partner_b}")` (labels already parameterized, lines 33-34) |
| `src/budget_api/tests/reports/test_golden_fixture.py:185-186, 241-242` | populated-DTO roundtrip fixture keys; subtotal assertions (`christian = golden["detailed"]["personal_christian"]`) |
| `client/src/components/reports/DetailedSections.tsx:130-131, 139-140` | `section={detailed.personal_christian}` / `sectionTxns["personal_christian"] ?? []` and same for rasma (display titles come from `partner_labels`; section header comment at `:423` still says "Personal sections — Christian / Rasma.") |
| `client/src/components/mega-reports/buildNavItems.ts:76-77` | `SECTION_ORDER` array lists both keys |
| `client/src/components/mega-reports/buildNavItems.ts:185` | `const targetSection = partner === "partner_a" ? "personal_christian" : "personal_rasma";` |
| `client/src/components/mega-reports/sections/PersonalSection.tsx:23-24` | `SECTION_KEY = { partner_a: "personal_christian", partner_b: "personal_rasma" }` (hardcoded titles at `:33-34`: `"Personal Christian"`, `"Personal Rasma"`) |
| `client/src/components/mega-reports/sections/AppendicesSection.tsx:35-36` | nav entries `{ id: "personal_christian", label: "Personal — Christian" }, …` |
| `client/src/components/settings/CategoryMappingsEditor.tsx:20-21` | settings dropdown options `{ key: "personal_christian", label: "Personal — Christian" }, …` |
| `client/tests/DetailedSections.test.tsx:66-67, 161, 184, 333-334` | fixtures + subtotal-null regressions |
| `client/tests/MegaReportView.test.tsx:48, 55` | mock cats `section: "personal_christian"` / `"personal_rasma"` |
| `client/tests/ReportView.test.tsx:162, 185` | mock `detailed` keys |

### (c) Generic iteration (rename-safe, key-agnostic)

- `accounting.py` `_records_in_section(records, section, mapping)` — reverse-looks-up category ids whose mapped section equals the requested key; agnostic to key spelling.
- `routers/category_mappings.py:121-127` — PUT validates `update.detailed_section in DETAILED_CATEGORY_SECTIONS` (membership only); `_load_category_titles`/merge never special-case names.
- `DetailedSections.tsx:131/140` `sectionTxns[...]` generic dict lookups derived from `detailed_section_mapping`.
- `mega/build_mega.py:286-289` — `section = section_routes.get(section_map.get(str(leaf["id"])))` (generic double lookup).
- `buildNavItems.ts:82-84` iterates `SECTION_ORDER` generically (the array contents in (b) change, the loop doesn't).

### Docs prose hits (removal list / design history)

- `docs/open-source-launch-gates.md:45-46` — identifier inventory I-001/I-002 (`personal_christian`/`personal_rasma` as substrings to remove).
- `docs/design/monthly-reports-logic-migration.md:83, 94-95`; `docs/design/design-client-pdf-export-sections.md:77`; `docs/design/done/design-f1.2-react-reports.md:258, 794, 891`.

---

## Q4 — Bills FE partner handling

### Q4a — the `partner === "Christian"` comparisons (all 6 files, exact quotes)

Type under test: `client/src/types/api.ts:113` — `export type F2Partner = "Christian" | "Rasma";` (used as `FinanceEvent.partner: F2Partner`, api.ts:126).

1. `client/src/components/bills/GraphView.tsx:44` — `type PartnerFilter = "Christian" | "Rasma";` Default selection `:378` `useState<PartnerFilter>("Christian")`; series pivots `:382` `m.partners.find((p) => p.partner === "Christian") ?? m.partners[0]` and `:386` same for "Rasma" (`?? m.partners[1] ?? m.partners[0]`); `:390` `const singleData = partner === "Rasma" ? rasma : christian;`; toggle UI `:416-427` hardcodes both labels. **Role: "Christian" = first/salary partner (partner_a analog) — default view and partners[0] fallback.**
2. `client/src/components/bills/BillsDashboard.tsx:55` — sparkline color: `name === "Christian" ? "var(--color-partner-a)" : "var(--color-partner-b)"` inside `savingsSeries` (lines 50-65). **Role: name→CSS-class mapping; Christian ⇒ partner-a (teal).** Theme pins this: `client/src/styles/theme.css:45-46` — `--partner-a: 189 78% 26%; /* teal — Christian */`, `--partner-b: 262 52% 50%; /* violet — Rasma */`.
3. `client/src/components/bills/BudgetTab.tsx:146` — `name === "Christian" ? "bg-partner-a" : "bg-partner-b"` (PartnerTag dot; also column layout comment at `:2`). Same role mapping.
4. `client/src/components/bills/EconomyBar.tsx:183` — `partner === "Christian" ? "bg-partner-a" : "bg-partner-b";` (status dot). Same role mapping.
5. `client/src/components/bills/EventRow.tsx:38` — `event.partner === "Christian" ? "bg-partner-a" : "bg-partner-b"` (row dot; label re-rendered at `:40` `title={event.partner}`). Same role mapping.
6. `client/src/components/bills/TableView.tsx:240` — `row.partner === "Christian" ? "bg-partner-a" : "bg-partner-b"` (cell dot; `{row.partner}` printed at `:245`). Same role mapping.

Additional name hardcodes adjacent to these flows: `client/src/components/bills/finance-data.ts:15` (`export const PARTNERS: F2Partner[] = ["Christian", "Rasma"];` — mock source) and `:197-203, 425-426` mock per-partner data; tests under `client/src/components/bills/__tests__/`, `client/src/hooks/__tests__/useBills.test.ts:140`, `client/src/lib/__tests__/bills-mapper.test.ts`, `client/src/api/__tests__/bills.test.ts:58` (`expect(url).toContain("partner=Christian")`).

### Q4b — Bills API partner identity + possible stable key

Backend resolves display labels from config only: `src/budget_api/services/bills_builder.py:163-166`:

```python
def _partner_label(account_mappings: dict[str, Any], partner_id: str) -> str:
    """Get the human label for a partner."""
    partners = account_mappings.get("partners", {})
    return partners.get(partner_id, {}).get("label", partner_id)
```

That **label string is the only partner identifier in the shipped payload**: events are stamped `"partner": partner_label` (bills_builder.py:478 and the dashboard-event shape at :1139), and each month block carries `"partner": partner_label` (bills_builder.py:1153). Models confirm: `BillsEvent.partner: str` (`src/budget_api/models/bills.py:28`) and `PartnerBills.partner: str` (`:37`) — **no partner_id / neutral key field exists in the bills API today.**

The read API also filters on the label: `GET /api/bills/dashboard/events?partner=…` (`src/budget_api/routers/bills.py:96, 131, 225` — `if partner is not None and event["partner"] != partner: return False`), and sorts ties by it (:169).

**Stable identifier the FE could use instead:** `partner_id` exists internally throughout the builder (e.g. `_all_partner_ids` bills_builder.py:169-172) and in `account_mappings.json` (`accounts[*].partner_id`), but is never emitted. Canonical ids in production data are `partner_a`/`partner_b` (README.md:85); note `partners.py:_slugify` + test fixtures (`conftest.py:67-68`) show slug ids like `"christian"` are possible for user-created partners, so a neutral `partner_slot` (`a`/`b`) or explicit `partner_id` passthrough would be the robust contract addition. [Inference] Either requires a `schema_version` 4→5 bump on the bills snapshot with additive-with-default handling per the repo's compat convention.

---

## Q5 — CI + test layout (LG-008 inputs)

- **Workflows:** only `.github/workflows/ci.yml`.
  - Job `ubuntu` (ci.yml:15-32): `python -m pytest src/mega/tests src/v4_pipeline/tests src/mom/tests src/budget_api/tests -q` (Python 3.13, `PYTHONPATH=src`, `pip install .`).
  - Job `windows` (ci.yml:34-66): same suite with `-m "not pdf_renderer"` — `python -m pytest src/mega/tests src/v4_pipeline/tests src/mom/tests src/budget_api/tests -m "not pdf_renderer" -q`.
  - Triggers: PRs + pushes to `main`, `feature/**`, `copilot/**` (ci.yml:3-9). No client/ JS tests in CI.
- **Golden-fixture test location:** `src/budget_api/tests/reports/` — golden `golden/sample_apr_2026_report.json`; runner `tmp_private_dir` monkeypatch fixture in `src/budget_api/tests/conftest.py:22-45`.
- **Existing regenerate-and-compare test (exactly what LG-008 asks about):** `src/budget_api/tests/reports/test_golden_fixture.py:50-60` — `test_build_report_matches_golden_baseline` seeds `data/sample_apr_2026.json` as `2026-04_ps_raw.json` + `data/sample_apr_2026_detailed_section_mapping.json` into a tmp private dir (fixture `seeded_synthetic_private_dir`, :33-47) and asserts `report_builder.build_report("2026-04") == golden`. Version pin: :67. This test is the natural template/anchor for the LG-008 regeneration smoke test (gate text: `docs/open-source-launch-gates.md:139-144`).

---

## Q6 — Fixture shape (data/sample_apr_2026*.json)

`data/sample_apr_2026.json`: JSON object with `transactions` array of 43 items. Transaction keys: `account, amount, category, date, id, payee, transaction_account` — **no `owner` field**; ownership is derived from account id/name by `_synthetic_owner` (`src/v4_pipeline/accounting.py:533-545`: txn id in `[100000, 200000)` + account name prefix `"Fixture A "`→`partner_a` / `"Fixture B "`→`partner_b`). Identifiers appear in **payees and category titles**, not owners/accounts:

```json
// line ~583-594
{"payee": "Personal Payee Christian 1", "category": {"id": "7", "title": "Test Personal Christian"}, "account": {"id": "1", "name": "Fixture A Checking"}}
// line ~619-630
{"payee": "Personal Payee Rasma 1", "category": {"id": "8", "title": "Test Personal Rasma"}, "account": {"id": "2", "name": "Fixture B Checking"}}
```

`git grep` hits in `data/`: `sample_apr_2026.json:583, 594, 601, 612, 619, 630, 637, 648` (payees + category titles above) and `sample_apr_2026_detailed_section_mapping.json:9-10` (`"7": "personal_christian"`, `"8": "personal_rasma"` — full file shown in Q3(a); its `account_roles` are already neutral: `savings_partner_a/b`). No other `data/sample_apr_2026_*.json` variants exist.

---

## Q7 — models/category_mappings.py:17-18

Structure: module-level set `DETAILED_CATEGORY_SECTIONS` (`src/budget_api/models/category_mappings.py:11-21`) enumerating the 10 valid detailed-section values for the settings API (duplicate of `accounting.py:16-26`); `personal_christian`/`personal_rasma` are members at lines 17-18:

```python
DETAILED_CATEGORY_SECTIONS = {
    "income_salary", "income_third_party", "savings", "home", "common",
    "personal_christian",   # :17
    "personal_rasma",       # :18
    "trips", "cc_payments", "excluded",
}
```

Sibling constant `KPI_ROLES` (category_mappings.py:8). **Consumers:**
- `src/budget_api/routers/category_mappings.py:11, 121-127` — `PUT /api/category-mappings/{id}` rejects `detailed_section` values outside the set (400 `"invalid detailed_section"`); the same router writes chosen values into `data/private/detailed_section_mapping.json` (:149-151).
- FE mirror: `client/src/types/category_mappings.ts:17-18` (TS union member) and `:55-56` (runtime array used for dropdown validation), rendered by `client/src/components/settings/CategoryMappingsEditor.tsx:20-21` with hardcoded labels `"Personal — Christian"`/`"Personal — Rasma"`.

---

## Notes for the coordinator

- **Rename blast radius for `personal_*`:** every tracked hit is enumerated in Q3 — 26 files. The golden fixture (`sample_apr_2026_report.json`) contains the keys three times (two `detailed.*` objects + embedded `detailed_section_mapping`), so a key rename implies golden regeneration + `CALCULATION_VERSION` 6→7 bump per the compat convention (old stored reports with old keys fail `ReportResponse.model_validate` → **500 on GET**, see Q1c — the version bump alone does not prevent the 500; a key rename is a breaking DTO change, unlike the additive-with-defaults pattern used so far). [Inference] Mitigation options (pydantic aliases/pre-validator or regenerate-on-version-mismatch before validate) belong to planning, not recorded here as fact.
- `accounting.py:899-900` comment claims the household composition is "currently a hardcoded frontend array (DetailedSections.tsx:592-619)" — **stale**: grep shows no such array in `DetailedSections.tsx` anymore (server computes `household_totals` since PR2; FE only reads it). Flag for cleanup during this feature.
- Bills payload carries no neutral partner id (Q4b) — FE rename work in the 6 bills components requires a new additive field (e.g. `partner_id`/`partner_slot`) or order-based mapping; today the label is load-bearing for color, filtering, and sort.
- Display-name fallbacks hardcoding names exist in three layers beyond the DTO keys: `accounting_html.py:818-819` (BE PDF/HTML), `PersonalSection.tsx:33-34` + `AppendicesSection.tsx:35-36` + `buildNavItems.ts:38-39` (FE mega-reports), `CategoryMappingsEditor.tsx:20-21` (FE settings), plus `theme.css:45-46` comments and `types/api.ts:113` / `finance-data.ts` (bills FE types + mocks).
- Durable fact surfaced for memory: unhandled `pydantic.ValidationError` inside a FastAPI endpoint under this app's `main.py` returns 500 (verified via TestClient probe 2026-09-16); the repo's only guard is the optional-with-defaults convention encoded in `TestReportResponseCompat`.
