"""Mega common-economy split coverage — mega_builder._split_category_nets +
build_mega_report split_summary wiring, category-level selection (Gate 2
evolution).

Rewritten (iteration 4, finding 1): _split_category_nets used to sum
detail_agg["cats"] partner nets — detail_agg aggregates ALL normalized
records with NO is_transfer gate (build_mega.py::_detail_agg feeds mega's
own home/common/trips totals, a different, unconditional aggregation),
while monthly net_category_totals() drops a transfer whose natural section
isn't home/savings/excluded (not real partner spend) to avoid
double-counting. Mega split settlement could diverge in dollar amounts
from monthly. Fixed: _split_category_nets now calls
accounting.net_category_totals() PER MONTH on that month's own
normalized_transactions (not detail_agg["cats"]) and sums the resulting
rows — same predicate, same transfer semantics, parity by construction.

Covers: _split_category_nets filtering + summing raw per-month records via
net_category_totals() (transfer-drop parity — the finding-1 regression),
split_summary populated end-to-end from monthly_results when config
enabled, null when disabled/missing/mapping-absent, aggregation math
across months, parent-category-selection expansion via a seeded catalog,
and real-label resolution in the settlement.

mega_split_seeded seeds detailed_section_mapping.json with a small
leaf->section map (c_rent->home, c_groceries->common,
c_salary->income_salary) and no category_catalog.json — category_parents
is None for these tests unless a test explicitly seeds one, so configs
here select known leaf category IDs directly via `categories` (no legacy
sections-only translation exercised here — see test_split_settings.py for
that).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from budget_api.services import mega_builder

# budget_api.services.mega_builder (imported above) already put v4_pipeline
# on sys.path — accounting must be imported after it (same order
# test_split_report.py uses).
from accounting import net_category_totals  # noqa: E402

from .test_mega_builder import _all_months, _mock_context

START = "2026-01"
END = "2026-02"  # 2-month window — keeps per-category sums short + explicit.

# Leaf-keyed section mapping (detailed_section_mapping.json shape) — twin of
# v4_pipeline/tests/test_split.py's MAPPING constant, category IDs renamed
# to match this file's synthetic records.
MAPPING = {
    "category_sections": {
        "c_rent": "home",
        "c_groceries": "common",
        "c_salary": "income_salary",
    },
    "account_roles": {},
}


@pytest.fixture
def mega_split_seeded(tmp_private_dir: Path) -> Path:
    """Seed ps_raw + config files for mega split tests (2-month window)."""
    for month in _all_months(START, END):
        (tmp_private_dir / f"{month}_ps_raw.json").write_text(
            json.dumps([{"id": 1}, {"id": 2}]), encoding="utf-8"
        )
    (tmp_private_dir / "account_mappings.json").write_text(
        json.dumps({"schema_version": 1, "partners": {}, "accounts": {}}),
        encoding="utf-8",
    )
    (tmp_private_dir / "detailed_section_mapping.json").write_text(
        json.dumps(MAPPING), encoding="utf-8"
    )
    return tmp_private_dir


def _record(
    record_id,
    amount,
    owner,
    category_id,
    date="2026-04-01",
    category_title="Cat",
    is_transfer=False,
):
    """Normalized-transaction-shaped record — same shape
    v4_pipeline/tests/test_split.py::_record uses (net_category_totals'
    actual input contract)."""
    return {
        "id": record_id,
        "date": date,
        "amount": amount,
        "payee": None,
        "note": None,
        "account_id": "acc",
        "account_name": None,
        "owner": owner,
        "category_path": [{"id": category_id, "title": category_title}],
        "is_transfer": is_transfer,
    }


def _monthly_results(records_by_month: dict[str, list[dict]]) -> list[tuple[str, dict]]:
    """context["monthly_results"]-shaped list for the START..END window —
    months not present in records_by_month get an empty transaction list."""
    return [
        (
            month,
            {
                "contract": {
                    "kpis": None,
                    "normalized_transactions": records_by_month.get(month, []),
                },
                "partner_labels": {"partner_a": "Fixture A", "partner_b": "Fixture B"},
            },
        )
        for month in _all_months(START, END)
    ]


def _records_by_month() -> dict[str, list[dict]]:
    """2 months of rent (home) + groceries (common) + salary (income_salary)
    — no transfers. Rent: net_partner_a 1000+1000=2000, net_partner_b 0.
    Groceries: net_partner_a 200+300=500, net_partner_b 100+50=150 (paid,
    real spend). Salary: received (amount > 0), so net = paid - received =
    0 - 5000 per month = -5000 per month, -10000 total — net_category_totals'
    paid-minus-received convention means income nets negative (partner_a is
    owed, not owing); it is NOT re-signed for a "this partner is owed"
    display anywhere in this module, same as monthly reports."""
    return {
        "2026-01": [
            _record(1, -1000.0, "partner_a", "c_rent", category_title="Rent"),
            _record(2, -200.0, "partner_a", "c_groceries", category_title="Groceries"),
            _record(3, -100.0, "partner_b", "c_groceries", category_title="Groceries"),
            _record(4, 5000.0, "partner_a", "c_salary", category_title="Salary"),
        ],
        "2026-02": [
            _record(5, -1000.0, "partner_a", "c_rent", category_title="Rent"),
            _record(6, -300.0, "partner_a", "c_groceries", category_title="Groceries"),
            _record(7, -50.0, "partner_b", "c_groceries", category_title="Groceries"),
            _record(8, 5000.0, "partner_a", "c_salary", category_title="Salary"),
        ],
    }


def _write_split_config(private: Path, config: dict) -> None:
    (private / "split_config.json").write_text(json.dumps(config), encoding="utf-8")


# --------------------------------------------------------------------------- #
# _split_category_nets — per-month net_category_totals() + sum across
# months, filtered by an allowed category-ID set.
# --------------------------------------------------------------------------- #


class TestSplitCategoryNets:
    def test_filters_by_allowed_category_ids(self):
        monthly_results = _monthly_results(
            {
                "2026-01": [
                    _record(1, -1000.0, "partner_a", "c_rent"),
                    _record(2, -200.0, "partner_a", "c_groceries"),
                    _record(3, 5000.0, "partner_a", "c_salary"),
                ]
            }
        )
        result = mega_builder._split_category_nets(
            monthly_results, {"c_rent", "c_groceries"}, MAPPING
        )
        ids = {row["category_id"] for row in result}
        assert ids == {"c_rent", "c_groceries"}  # c_salary excluded

    def test_sums_partner_nets_across_all_months(self):
        result = mega_builder._split_category_nets(
            _monthly_results(_records_by_month()), {"c_rent", "c_groceries"}, MAPPING
        )
        rows_by_id = {row["category_id"]: row for row in result}
        assert rows_by_id["c_rent"] == {
            "category_id": "c_rent",
            "category_title": "Rent",
            "section": "home",
            "net_partner_a": 2000.0,
            "net_partner_b": 0.0,
        }
        assert rows_by_id["c_groceries"] == {
            "category_id": "c_groceries",
            "category_title": "Groceries",
            "section": "common",
            "net_partner_a": 500.0,
            "net_partner_b": 150.0,
        }

    def test_empty_monthly_results_returns_empty_list(self):
        assert mega_builder._split_category_nets(_monthly_results({}), {"c_rent"}, MAPPING) == []

    def test_category_not_in_allowed_absent_from_result(self):
        result = mega_builder._split_category_nets(
            _monthly_results(_records_by_month()), {"c_rent"}, MAPPING
        )
        assert [row["category_id"] for row in result] == ["c_rent"]

    def test_category_without_mapping_entry_defaults_to_common_section(self):
        monthly_results = _monthly_results(
            {"2026-01": [_record(1, -1.0, "partner_a", "c_weird", category_title="Weird")]}
        )
        result = mega_builder._split_category_nets(monthly_results, {"c_weird"}, MAPPING)
        assert result[0]["section"] == "common"

    def test_transfer_dropped_when_natural_section_not_home_savings_excluded(self):
        """IMPORTANT regression (iteration 4, finding 1): a transfer whose
        natural section is "common" (c_groceries here) isn't real partner
        spend — dropped even though its category is selected. Previously
        (summing detail_agg["cats"], no is_transfer gate) this -500
        transfer would have inflated net_partner_a to 1000.0."""
        monthly_results = _monthly_results(
            {
                "2026-01": [
                    _record(1, -200.0, "partner_a", "c_groceries"),
                    _record(2, -100.0, "partner_b", "c_groceries"),
                    _record(3, -500.0, "partner_a", "c_groceries", is_transfer=True),
                ],
                "2026-02": [
                    _record(4, -300.0, "partner_a", "c_groceries"),
                    _record(5, -50.0, "partner_b", "c_groceries"),
                ],
            }
        )
        result = mega_builder._split_category_nets(monthly_results, {"c_groceries"}, MAPPING)
        row = result[0]
        assert row["net_partner_a"] == 500.0  # 200 + 300, NOT +500 transfer
        assert row["net_partner_b"] == 150.0

    def test_transfer_kept_when_natural_section_is_home(self):
        """Same drop rule as net_category_totals — a transfer whose natural
        section IS home/savings/excluded is real spend, kept."""
        monthly_results = _monthly_results(
            {"2026-01": [_record(1, -1000.0, "partner_a", "c_rent", is_transfer=True)]}
        )
        result = mega_builder._split_category_nets(monthly_results, {"c_rent"}, MAPPING)
        assert result[0]["net_partner_a"] == 1000.0


class TestMonthlyMegaAggregateParity:
    def test_parity_between_summed_monthly_split_and_mega_split(self):
        """Direct regression for iteration 4 finding 1: compute "monthly
        per-month sums" independently via net_category_totals() (what each
        month's own split report would compute) and assert
        mega_builder._split_category_nets() lands on the exact same
        summed totals for the same synthetic multi-month data — including
        a transfer that must be excluded from both sides identically."""
        records_by_month = {
            "2026-01": [
                _record(1, -1000.0, "partner_a", "c_rent", category_title="Rent"),
                _record(2, -200.0, "partner_a", "c_groceries", category_title="Groceries"),
                _record(3, -100.0, "partner_b", "c_groceries", category_title="Groceries"),
                _record(
                    4,
                    -500.0,
                    "partner_a",
                    "c_groceries",
                    category_title="Groceries",
                    is_transfer=True,
                ),
            ],
            "2026-02": [
                _record(5, -1000.0, "partner_a", "c_rent", category_title="Rent"),
                _record(6, -300.0, "partner_a", "c_groceries", category_title="Groceries"),
                _record(7, -50.0, "partner_b", "c_groceries", category_title="Groceries"),
            ],
        }
        allowed = {"c_rent", "c_groceries"}

        monthly_totals: dict[str, dict[str, float]] = {}
        for records in records_by_month.values():
            for row in net_category_totals(records, allowed, MAPPING):
                entry = monthly_totals.setdefault(
                    row["category_id"], {"net_partner_a": 0.0, "net_partner_b": 0.0}
                )
                entry["net_partner_a"] += row["net_partner_a"]
                entry["net_partner_b"] += row["net_partner_b"]

        mega_rows = mega_builder._split_category_nets(
            _monthly_results(records_by_month), allowed, MAPPING
        )
        mega_totals = {
            row["category_id"]: {
                "net_partner_a": row["net_partner_a"],
                "net_partner_b": row["net_partner_b"],
            }
            for row in mega_rows
        }

        assert mega_totals == monthly_totals
        # Sanity: the transfer really was excluded, not just coincidentally
        # netting to the same number — 500 would be 1000 if it leaked in.
        assert mega_totals["c_groceries"]["net_partner_a"] == 500.0


# --------------------------------------------------------------------------- #
# build_mega_report — split_summary wiring end-to-end.
# --------------------------------------------------------------------------- #


class TestBuildMegaReportSplitWiring:
    def _build(self, records_by_month: dict[str, list[dict]]) -> dict:
        context = _mock_context(START, END)
        context["monthly_results"] = _monthly_results(records_by_month)
        with patch(
            "budget_api.services.mega_builder.build_context", return_value=context
        ):
            return mega_builder.build_mega_report(START, END)

    def test_no_config_file_split_summary_is_none(self, mega_split_seeded: Path):
        report = self._build(_records_by_month())
        assert report["split_summary"] is None

    def test_disabled_config_split_summary_is_none(self, mega_split_seeded: Path):
        _write_split_config(
            mega_split_seeded,
            {
                "enabled": False,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["c_rent", "c_groceries"],
            },
        )
        report = self._build(_records_by_month())
        assert report["split_summary"] is None

    def test_split_summary_none_when_detailed_section_mapping_missing(
        self, tmp_private_dir: Path
    ):
        """Guard added alongside the finding-1 fix: net_category_totals()
        derives each record's natural section from detailed_section_mapping
        — same gate report_builder._detailed() uses (no mapping => no
        split, monthly or mega). Previously mega ignored this gate (it
        computed straight from detail_agg["cats"], which didn't need the
        mapping); a categories-only split_config can resolve without one
        (normalize_split_config doesn't require it for that schema), so
        this combination is reachable and must degrade to None, not crash."""
        for month in _all_months(START, END):
            (tmp_private_dir / f"{month}_ps_raw.json").write_text(
                json.dumps([{"id": 1}, {"id": 2}]), encoding="utf-8"
            )
        (tmp_private_dir / "account_mappings.json").write_text(
            json.dumps({"schema_version": 1, "partners": {}, "accounts": {}}),
            encoding="utf-8",
        )
        _write_split_config(
            tmp_private_dir,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["c_rent"],
            },
        )
        # No detailed_section_mapping.json written.
        report = self._build(_records_by_month())
        assert report["split_summary"] is None

    def test_enabled_config_populates_split_summary_from_monthly_records(
        self, mega_split_seeded: Path
    ):
        _write_split_config(
            mega_split_seeded,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["c_rent", "c_groceries"],
            },
        )
        report = self._build(_records_by_month())
        summary = report["split_summary"]
        assert summary is not None
        assert summary["shares"] == {"partner_a": 50.0, "partner_b": 50.0}
        assert summary["sections"] == ["home", "common"]
        rows_by_id = {row["category_id"]: row for row in summary["rows"]}
        assert set(rows_by_id) == {"c_rent", "c_groceries"}
        # Rent: total 2000.0 across 2 months, 50/50 fair share => 1000
        # actual vs 1000 fair => delta 1000 (A fronted the whole rent).
        assert rows_by_id["c_rent"]["actual"] == 2000.0
        assert rows_by_id["c_rent"]["fair"] == 1000.0
        assert rows_by_id["c_rent"]["delta"] == 1000.0
        # b-side additive — exact complement (50/50 shares here).
        assert rows_by_id["c_rent"]["actual_b"] == 0.0
        assert rows_by_id["c_rent"]["fair_b"] == 1000.0
        assert rows_by_id["c_rent"]["delta_b"] == -1000.0
        # Groceries: actual_a 500 (200+300), total 650, fair 325, delta 175.
        assert rows_by_id["c_groceries"]["actual"] == 500.0
        assert rows_by_id["c_groceries"]["fair"] == 325.0
        assert rows_by_id["c_groceries"]["delta"] == 175.0
        assert rows_by_id["c_groceries"]["actual_b"] == pytest.approx(150.0)
        assert rows_by_id["c_groceries"]["fair_b"] == pytest.approx(325.0)
        assert rows_by_id["c_groceries"]["delta_b"] == pytest.approx(-175.0)
        # General invariant across all rows: fair_a + fair_b == category
        # total (== actual_a + actual_b); delta_b == -delta.
        for row in summary["rows"]:
            assert row["delta_b"] == pytest.approx(-row["delta"])
            assert row["fair"] + row["fair_b"] == pytest.approx(
                row["actual"] + row["actual_b"]
            )

    def test_no_section_eligibility_restriction_income_salary_included(
        self, mega_split_seeded: Path
    ):
        """A category the caller allows is included regardless of its
        section — income_salary here. Sign convention: net_category_totals
        nets paid-minus-received, so a received (amount > 0) salary lands
        as a NEGATIVE net (partner_a is owed, not owing) — -5000/month,
        -10000 total, not a hand-picked positive mock value."""
        _write_split_config(
            mega_split_seeded,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["c_salary"],
            },
        )
        report = self._build(_records_by_month())
        rows = report["split_summary"]["rows"]
        assert len(rows) == 1
        assert rows[0]["category_id"] == "c_salary"
        assert rows[0]["actual"] == -10000.0

    def test_aggregation_nets_correctly_across_months_into_settlement(
        self, mega_split_seeded: Path
    ):
        """Single netted settlement across the whole mega window — not a
        per-month or per-category transfer. Total delta_a = 1000 + 175 =
        1175 (A overpaid) => B owes A 1175."""
        _write_split_config(
            mega_split_seeded,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["c_rent", "c_groceries"],
            },
        )
        report = self._build(_records_by_month())
        settlement = report["split_summary"]["settlement"]
        assert settlement is not None
        assert settlement["amount"] == pytest.approx(1175.0)
        # Default placeholder labels (no partner_labels.json/custom mappings
        # seeded by mega_split_seeded) — real-label resolution below.
        assert settlement["from_partner"] == "Partner B"
        assert settlement["to_partner"] == "Partner A"

    def test_only_selected_categories_contribute_to_mega_split(
        self, mega_split_seeded: Path
    ):
        """common has data but isn't in `categories` — excluded from rows
        and the settlement math."""
        _write_split_config(
            mega_split_seeded,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["c_rent"],
            },
        )
        report = self._build(_records_by_month())
        summary = report["split_summary"]
        assert [row["category_id"] for row in summary["rows"]] == ["c_rent"]
        assert summary["settlement"]["amount"] == pytest.approx(1000.0)

    def test_parent_category_selection_expands_via_seeded_catalog(
        self, mega_split_seeded: Path
    ):
        """Selecting a parent category catalog node pulls in both leaf
        categories beneath it — same catalog-driven expansion
        report_builder/accounting_html use, via
        accounting._resolve_allowed_category_ids."""
        (mega_split_seeded / "category_catalog.json").write_text(
            json.dumps(
                {
                    "categories": [
                        {
                            "id": "p_home_common",
                            "title": "Home & Common",
                            "parent_id": None,
                            "children": [
                                {
                                    "id": "c_rent",
                                    "title": "Rent",
                                    "parent_id": "p_home_common",
                                    "children": [],
                                },
                                {
                                    "id": "c_groceries",
                                    "title": "Groceries",
                                    "parent_id": "p_home_common",
                                    "children": [],
                                },
                            ],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        _write_split_config(
            mega_split_seeded,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["p_home_common"],
            },
        )
        report = self._build(_records_by_month())
        summary = report["split_summary"]
        assert {row["category_id"] for row in summary["rows"]} == {
            "c_rent",
            "c_groceries",
        }

    def test_real_partner_labels_resolved_in_settlement_custom_ids(
        self, mega_split_seeded: Path
    ):
        """Regression: mega settlement must resolve real display labels for
        custom partner IDs too (alex/sam), not just the default-slot path —
        same _load_partner_labels + _partner_slot_map resolution
        report_builder uses for monthly reports (LG-002 neutral fixture
        IDs: alex sorts before sam -> partner_a)."""
        (mega_split_seeded / "account_mappings.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "partners": {
                        "alex": {"label": "Alex"},
                        "sam": {"label": "Sam"},
                    },
                    "accounts": {},
                }
            ),
            encoding="utf-8",
        )
        _write_split_config(
            mega_split_seeded,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["c_rent", "c_groceries"],
            },
        )
        report = self._build(_records_by_month())
        settlement = report["split_summary"]["settlement"]
        assert settlement["from_partner"] == "Sam"
        assert settlement["to_partner"] == "Alex"
        assert report["partner_labels"] == {"partner_a": "Alex", "partner_b": "Sam"}

    def test_balanced_split_settlement_is_none(self, mega_split_seeded: Path):
        """Even split of an even category — no settlement fabricated."""
        _write_split_config(
            mega_split_seeded,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["c_rent"],
            },
        )
        records_by_month = {
            "2026-01": [
                _record(1, -500.0, "partner_a", "c_rent"),
                _record(2, -500.0, "partner_b", "c_rent"),
            ],
            "2026-02": [
                _record(3, -500.0, "partner_a", "c_rent"),
                _record(4, -500.0, "partner_b", "c_rent"),
            ],
        }
        report = self._build(records_by_month)
        assert report["split_summary"]["settlement"] is None

    def test_empty_categories_selected_still_populates_split_summary_empty(
        self, mega_split_seeded: Path
    ):
        """Design decision: enabled=true + zero categories selected is
        ALLOWED — split_summary stays a non-None dict (empty rows,
        settlement None, sections [])."""
        _write_split_config(
            mega_split_seeded,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": [],
            },
        )
        report = self._build(_records_by_month())
        assert report["split_summary"] == {
            "shares": {"partner_a": 50.0, "partner_b": 50.0},
            "sections": [],
            "rows": [],
            "settlement": None,
        }

    def test_malformed_config_raises_with_range_context(
        self, mega_split_seeded: Path
    ):
        from accounting import AccountingValidationError

        _write_split_config(
            mega_split_seeded,
            {
                "enabled": True,
                "shares": {"partner_a": 70.0, "partner_b": 40.0},
                "categories": ["c_rent"],
            },
        )
        with pytest.raises(AccountingValidationError, match=f"{START}..{END}"):
            self._build(_records_by_month())


# --------------------------------------------------------------------------- #
# compute_mega_split_summary — the mini-iteration extraction of
# build_mega_report's inline split logic into a standalone reusable
# function, so mega_pdf.py (HTML/PDF export) can call the EXACT SAME split
# math as build_mega_report (JSON/API) without recomputing/duplicating it.
# Pure refactor — TestBuildMegaReportSplitWiring above (unchanged, still
# calling build_mega_report end-to-end) already proves no regression;
# these tests cover the standalone function directly + confirm
# build_mega_report is a thin wrapper around it.
# --------------------------------------------------------------------------- #


class TestComputeMegaSplitSummary:
    def test_returns_none_when_no_config(self, mega_split_seeded: Path):
        assert (
            mega_builder.compute_mega_split_summary(
                START,
                END,
                _monthly_results(_records_by_month()),
                {"partner_a": "Fixture A", "partner_b": "Fixture B"},
            )
            is None
        )

    def test_returns_none_when_mapping_missing(self, tmp_private_dir: Path):
        _write_split_config(
            tmp_private_dir,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["c_rent"],
            },
        )
        assert (
            mega_builder.compute_mega_split_summary(
                START,
                END,
                _monthly_results(_records_by_month()),
                {"partner_a": "Fixture A", "partner_b": "Fixture B"},
            )
            is None
        )

    def test_populates_summary_with_resolved_settlement_labels(
        self, mega_split_seeded: Path
    ):
        _write_split_config(
            mega_split_seeded,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["c_rent", "c_groceries"],
            },
        )
        summary = mega_builder.compute_mega_split_summary(
            START,
            END,
            _monthly_results(_records_by_month()),
            {"partner_a": "Alex", "partner_b": "Sam"},
        )
        assert summary is not None
        assert summary["sections"] == ["home", "common"]
        # Settlement already label-resolved (not slot keys partner_a/partner_b)
        # — same resolution build_mega_report applies via
        # report_builder._resolve_split_settlement.
        assert summary["settlement"]["from_partner"] in {"Alex", "Sam"}
        assert summary["settlement"]["to_partner"] in {"Alex", "Sam"}

    def test_build_mega_report_delegates_to_compute_mega_split_summary(
        self, mega_split_seeded: Path
    ):
        """Parity check: build_mega_report's split_summary must equal a
        direct compute_mega_split_summary call on the same inputs —
        confirms the extraction didn't change behavior."""
        _write_split_config(
            mega_split_seeded,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["c_rent", "c_groceries"],
            },
        )
        context = _mock_context(START, END)
        monthly_results = _monthly_results(_records_by_month())
        context["monthly_results"] = monthly_results
        with patch(
            "budget_api.services.mega_builder.build_context", return_value=context
        ):
            report = mega_builder.build_mega_report(START, END)
        direct = mega_builder.compute_mega_split_summary(
            START, END, monthly_results, report["partner_labels"]
        )
        assert report["split_summary"] == direct


# --------------------------------------------------------------------------- #
# mega_pdf.generate_pdf — split_summary threaded into assemble_html without
# recomputation (calls the SAME compute_mega_split_summary helper as
# build_mega_report; mega_pdf itself never touches net_category_totals/
# compute_split directly).
# --------------------------------------------------------------------------- #


class TestMegaPdfSplitSummaryWiring:
    def test_generate_pdf_threads_split_summary_into_assemble_html(
        self, mega_split_seeded: Path, monkeypatch
    ):
        _write_split_config(
            mega_split_seeded,
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["c_rent", "c_groceries"],
            },
        )
        from budget_api.services import mega_pdf

        context = _mock_context(START, END)
        context["monthly_results"] = _monthly_results(_records_by_month())
        captured = {}

        def _fake_assemble_html(ctx, args, split_summary=None):
            captured["split_summary"] = split_summary
            return "<html>fake</html>"

        class _FakePdf:
            def write_pdf(self):
                return b"%PDF-1.4 fake"

        monkeypatch.setattr(mega_pdf, "build_context", lambda args: context)
        monkeypatch.setattr(mega_pdf, "assemble_html", _fake_assemble_html)
        monkeypatch.setattr(
            "weasyprint.HTML", lambda filename: _FakePdf()
        )

        result = mega_pdf.generate_pdf(START, END)
        assert result == b"%PDF-1.4 fake"
        assert captured["split_summary"] is not None
        assert captured["split_summary"]["sections"] == ["home", "common"]

    def test_generate_pdf_split_summary_none_when_no_config(
        self, mega_split_seeded: Path, monkeypatch
    ):
        from budget_api.services import mega_pdf

        context = _mock_context(START, END)
        context["monthly_results"] = _monthly_results(_records_by_month())
        captured = {}

        def _fake_assemble_html(ctx, args, split_summary=None):
            captured["split_summary"] = split_summary
            return "<html>fake</html>"

        class _FakePdf:
            def write_pdf(self):
                return b"%PDF-1.4 fake"

        monkeypatch.setattr(mega_pdf, "build_context", lambda args: context)
        monkeypatch.setattr(mega_pdf, "assemble_html", _fake_assemble_html)
        monkeypatch.setattr(
            "weasyprint.HTML", lambda filename: _FakePdf()
        )

        mega_pdf.generate_pdf(START, END)
        assert captured["split_summary"] is None
