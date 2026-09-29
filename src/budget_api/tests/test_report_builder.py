"""Unit tests — report_builder derived views, stale check, status transitions."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from budget_api.services import report_builder, storage

# --------------------------------------------------------------------------- #
# Test data — mock transactions matching ps_raw shape.
# --------------------------------------------------------------------------- #


def _mock_transactions() -> list[dict]:
    """Two txns — partner_a grocery, partner_b grocery."""
    return [
        {
            "id": 100001,
            "date": "2026-07-03",
            "amount": -450.50,
            "payee": "Rema 1000",
            "note": "Weekly shop",
            "is_transfer": False,
            "account": {"id": "1100001", "name": "FxA Check Nordic Bank"},
            "category": {"id": 2100005, "title": "Supermarket", "parent_id": 2100003},
            "category_hierarchy": [
                {"id": "2100003", "title": "Groceries"},
                {"id": "2100005", "title": "Supermarket"},
            ],
        },
        {
            "id": 100002,
            "date": "2026-07-10",
            "amount": -320.00,
            "payee": "Kiwi",
            "note": None,
            "is_transfer": False,
            "account": {"id": "1100007", "name": "FxB Check Nordic Bank"},
            "category": {"id": 2100005, "title": "Supermarket", "parent_id": 2100003},
            "category_hierarchy": [
                {"id": "2100003", "title": "Groceries"},
                {"id": "2100005", "title": "Supermarket"},
            ],
        },
    ]


def _mock_account_mappings() -> dict:
    """Unified account mapping — partner_id schema (budget_api format)."""
    return {
        "schema_version": 1,
        "partners": {
            "partner_a": {"label": "Fixture A"},
            "partner_b": {"label": "Fixture B"},
        },
        "accounts": {
            "1100001": {
                "name": "FxA Check Nordic Bank",
                "partner_id": "partner_a",
                "type": "checking",
                "excluded": False,
            },
            "1100007": {
                "name": "FxB Check Nordic Bank",
                "partner_id": "partner_b",
                "type": "checking",
                "excluded": False,
            },
        },
    }


def _mock_detailed_section_mapping() -> dict:
    return {
        "account_roles": {},
        "category_sections": {
            "2100003": "common",
            "2100005": "common",
        },
    }


def _mock_category_roles() -> dict:
    return {
        "2100003": "spend",
        "2100005": "spend",
    }


def _mock_category_catalog() -> dict:
    return {
        "start": "2026-07",
        "end": "2026-07",
        "categories": [
            {
                "id": 2100003,
                "title": "Groceries",
                "parent_id": None,
                "children": [
                    {
                        "id": 2100005,
                        "title": "Supermarket",
                        "parent_id": 2100003,
                        "children": [],
                    },
                ],
            },
        ],
    }


@pytest.fixture
def seeded_private_dir(tmp_private_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Seed tmp private dir with all config files + ps_raw."""
    # account_mappings.json
    (tmp_private_dir / "account_mappings.json").write_text(
        json.dumps(_mock_account_mappings()), encoding="utf-8"
    )
    # detailed_section_mapping.json
    (tmp_private_dir / "detailed_section_mapping.json").write_text(
        json.dumps(_mock_detailed_section_mapping()), encoding="utf-8"
    )
    # category_roles.json
    (tmp_private_dir / "category_roles.json").write_text(
        json.dumps(_mock_category_roles()), encoding="utf-8"
    )
    # category_catalog.json
    (tmp_private_dir / "category_catalog.json").write_text(
        json.dumps(_mock_category_catalog()), encoding="utf-8"
    )
    # partner_labels.json — fallback if account_mappings missing.
    (tmp_private_dir / "partner_labels.json").write_text(
        json.dumps({"partner_a": "Fixture A", "partner_b": "Fixture B"}),
        encoding="utf-8",
    )
    # ps_raw — dict format with "transactions" key (data_loader expects this).
    (tmp_private_dir / "2026-07_ps_raw.json").write_text(
        json.dumps({"transactions": _mock_transactions()}), encoding="utf-8"
    )
    return tmp_private_dir


# --------------------------------------------------------------------------- #
# Derived view tests — pure data logic.
# --------------------------------------------------------------------------- #


class TestDerivedViews:
    def test_root_totals(self):
        categories = [
            {
                "id": "1",
                "title": "Root",
                "parent_id": None,
                "paid": 100.0,
                "received": 50.0,
                "net": 50.0,
                "count": 3,
            },
            {
                "id": "2",
                "title": "Child",
                "parent_id": "1",
                "paid": 20.0,
                "received": 0.0,
                "net": -20.0,
                "count": 1,
            },
        ]
        totals = report_builder._root_totals(categories)
        assert totals["paid"] == 100.0
        assert totals["received"] == 50.0
        assert totals["net"] == 50.0
        assert totals["count"] == 3

    def test_owner_totals(self):
        categories = [
            {
                "id": "1",
                "title": "Root",
                "parent_id": None,
                "owners": {
                    "partner_a": {"paid": 100.0, "received": 0.0, "net": -100.0},
                    "partner_b": {"paid": 50.0, "received": 10.0, "net": -40.0},
                },
            },
        ]
        totals = report_builder._owner_totals(categories)
        assert totals["partner_a"]["paid"] == 100.0
        assert totals["partner_b"]["paid"] == 50.0
        assert totals["partner_b"]["received"] == 10.0

    def test_partner_panels(self):
        owner_totals = {
            "partner_a": {"paid": 100.0, "received": 50.0, "net": -50.0},
            "partner_b": {"paid": 30.0, "received": 40.0, "net": 10.0},
        }
        labels = {"partner_a": "Fixture A", "partner_b": "Fixture B"}
        panels = report_builder._partner_panels(owner_totals, labels)
        assert panels["partner_a"]["label"] == "Fixture A"
        assert panels["partner_a"]["net_class"] == "neg"
        assert panels["partner_b"]["net_class"] == "pos"


# --------------------------------------------------------------------------- #
# Build report — integration with mock data.
# --------------------------------------------------------------------------- #


class TestBuildReport:
    def test_build_report_success(self, seeded_private_dir):
        """build_report returns full contract + derived views."""
        report = report_builder.build_report("2026-07")
        assert report["month"] == "2026-07"
        assert report["calculation_version"] == report_builder.CALCULATION_VERSION
        assert report["txn_count"] == 2
        assert "root_totals" in report
        assert "owner_totals" in report
        assert "partner_panels" in report
        assert "detailed" in report
        assert "personal_share" in report
        assert "balanced" in report
        assert report["savings_summary"]["total"]["net_saved"] == 0.0
        assert report["partner_labels"]["partner_a"] == "Fixture A"

    def test_build_report_no_data(self, tmp_private_dir):
        """build_report raises FileNotFoundError if no ps_raw."""
        with pytest.raises(FileNotFoundError):
            report_builder.build_report("2026-07")


# --------------------------------------------------------------------------- #
# Stale check.
# --------------------------------------------------------------------------- #


class TestStaleCheck:
    def test_not_stale_with_current_calculation_version(self, tmp_private_dir):
        """Current calculation version + matching txn count is fresh."""
        (tmp_private_dir / "2026-07_ps_raw.json").write_text(
            json.dumps([{"id": 1}, {"id": 2}]), encoding="utf-8"
        )
        report = {
            "calculation_version": report_builder.CALCULATION_VERSION,
            "txn_count": 2,
        }
        assert report_builder.check_stale("2026-07", report) is False

    @pytest.mark.parametrize("calculation_version", [None, 1, 2, 3, 5])
    def test_stale_with_missing_or_old_calculation_version(
        self, tmp_private_dir, calculation_version
    ):
        """Same transaction count cannot reuse older savings KPI semantics."""
        (tmp_private_dir / "2026-07_ps_raw.json").write_text(
            json.dumps([{"id": 1}, {"id": 2}]), encoding="utf-8"
        )
        report = {"txn_count": 2}
        if calculation_version is not None:
            report["calculation_version"] = calculation_version
        assert report_builder.check_stale("2026-07", report) is True

    def test_stale_count_mismatch(self, tmp_private_dir):
        """txn_count != ps_raw count → stale."""
        (tmp_private_dir / "2026-07_ps_raw.json").write_text(
            json.dumps([{"id": 1}, {"id": 2}, {"id": 3}]), encoding="utf-8"
        )
        report = {
            "calculation_version": report_builder.CALCULATION_VERSION,
            "txn_count": 2,
        }
        assert report_builder.check_stale("2026-07", report) is True

    def test_stale_no_ps_raw(self, tmp_private_dir):
        """No ps_raw → stale."""
        report = {
            "calculation_version": report_builder.CALCULATION_VERSION,
            "txn_count": 2,
        }
        assert report_builder.check_stale("2026-07", report) is True


# --------------------------------------------------------------------------- #
# Status transitions — write/read status.
# --------------------------------------------------------------------------- #


class TestStatusTransitions:
    def test_write_read_status(self, tmp_private_dir):
        """write_status → read_status roundtrip."""
        status = {
            "status": "generating",
            "errors": [],
            "started_at": "2026-07-28T00:00:00Z",
            "completed_at": None,
        }
        report_builder.write_status("2026-07", status)
        read = report_builder.read_status("2026-07")
        assert read == status

    def test_read_status_missing(self, tmp_private_dir):
        """read_status returns None if no file."""
        assert report_builder.read_status("2026-07") is None

    def test_status_success_transition(self, tmp_private_dir):
        """generating → success transition."""
        report_builder.write_status(
            "2026-07",
            {
                "status": "generating",
                "errors": [],
                "started_at": "t1",
                "completed_at": None,
            },
        )
        report_builder.write_status(
            "2026-07",
            {
                "status": "success",
                "errors": [],
                "started_at": "t1",
                "completed_at": "t2",
            },
        )
        assert report_builder.read_status("2026-07")["status"] == "success"

    def test_status_failed_transition(self, tmp_private_dir):
        """generating → failed transition with errors."""
        report_builder.write_status(
            "2026-07",
            {
                "status": "failed",
                "errors": ["pipeline error"],
                "started_at": "t1",
                "completed_at": "t2",
            },
        )
        status = report_builder.read_status("2026-07")
        assert status["status"] == "failed"
        assert "pipeline error" in status["errors"]


# --------------------------------------------------------------------------- #
# list_months — scan ps_raw files.
# --------------------------------------------------------------------------- #


class TestListMonths:
    def test_list_months_sorted_desc(self, tmp_private_dir):
        """Months sorted descending."""
        for month in ("2026-05", "2026-07", "2026-06"):
            (tmp_private_dir / f"{month}_ps_raw.json").write_text(
                "[]", encoding="utf-8"
            )
        months = report_builder.list_months()
        assert months == ["2026-07", "2026-06", "2026-05"]

    def test_list_months_empty(self, tmp_private_dir):
        """No ps_raw files → empty list."""
        assert report_builder.list_months() == []

    def test_list_months_ignores_non_ps_raw(self, tmp_private_dir):
        """Only *_ps_raw.json files counted."""
        (tmp_private_dir / "2026-07_ps_raw.json").write_text("[]", encoding="utf-8")
        (tmp_private_dir / "events_2026-07.json").write_text("[]", encoding="utf-8")
        (tmp_private_dir / "category_catalog.json").write_text("{}", encoding="utf-8")
        months = report_builder.list_months()
        assert months == ["2026-07"]


# --------------------------------------------------------------------------- #
# Write/read report.
# --------------------------------------------------------------------------- #


class TestReportStorage:
    def test_write_read_report(self, tmp_private_dir):
        """write_report → read_report roundtrip."""
        report = {
            "month": "2026-07",
            "contract_version": report_builder.CONTRACT_VERSION,
            "calculation_version": report_builder.CALCULATION_VERSION,
            "txn_count": 5,
            "categories": [],
        }
        report_builder.write_report("2026-07", report)
        read = report_builder.read_report("2026-07")
        assert read == report

    def test_read_report_missing(self, tmp_private_dir):
        """read_report returns None if no file."""
        assert report_builder.read_report("2026-07") is None


class TestPartnerLabelRobustness:
    """Label configuration degrades visibly, never crashes the build."""

    def test_malformed_partner_labels_json_degrades_to_placeholders(
        self, seeded_private_dir
    ):
        """Unparseable partner_labels.json -> defaults + read-path warning."""
        (seeded_private_dir / "partner_labels.json").write_text(
            "{ not valid json", encoding="utf-8"
        )
        report = report_builder.build_report("2026-07")
        assert report["partner_labels"] == {
            "partner_a": "Partner A",
            "partner_b": "Partner B",
        }
        assert any("could not be parsed" in w for w in report["warnings"])

    def test_label_warnings_are_logged(self, seeded_private_dir, caplog):
        """Monthly builder logs validation warnings like mega/PDF builders."""
        import logging

        (seeded_private_dir / "partner_labels.json").write_text(
            json.dumps({"partner_a": "Shared", "partner_b": "Shared"}),
            encoding="utf-8",
        )
        with caplog.at_level(
            logging.WARNING, logger="budget_api.services.report_builder"
        ):
            report = report_builder.build_report("2026-07")
        assert any(
            "partner-label validation:" in record.getMessage()
            for record in caplog.records
        )
        assert report["warnings"]


# --------------------------------------------------------------------------- #
# _load_account_owners bridge — depersonalized partner_id → owner slots.
# --------------------------------------------------------------------------- #


class TestLoadAccountOwners:
    def _write_mappings(self, dir_path: Path, mappings: dict) -> None:
        (dir_path / "account_mappings.json").write_text(
            json.dumps(mappings), encoding="utf-8"
        )

    def test_custom_partner_ids_map_to_sorted_slots(
        self, tmp_private_dir: Path
    ):
        """Custom partner IDs (e.g. alex/sam) map deterministically:
        sorted IDs → partner_a / partner_b. Regression for
        'transactions[0] has no account-ID owner mapping'."""
        self._write_mappings(
            tmp_private_dir,
            {
                "schema_version": 1,
                "partners": {
                    "alex": {"label": "Alex"},
                    "sam": {"label": "Sam"},
                },
                "accounts": {
                    "100": {"partner_id": "sam"},
                    "200": {"partner_id": "alex"},
                },
            },
        )
        owners = report_builder._load_account_owners()
        # "alex" sorts before "sam" → partner_a.
        assert owners == {"200": "partner_a", "100": "partner_b"}

    def test_custom_ids_without_partners_block(self, tmp_private_dir: Path):
        """Partner IDs are collected from account partner_id values too,
        so a partners block is not required for slot derivation."""
        self._write_mappings(
            tmp_private_dir,
            {
                "schema_version": 1,
                "partners": {},
                "accounts": {
                    "100": {"partner_id": "zeta"},
                    "200": {"partner_id": "alpha"},
                },
            },
        )
        owners = report_builder._load_account_owners()
        assert owners == {"200": "partner_a", "100": "partner_b"}

    def test_legacy_partner_ids_unchanged(self, tmp_private_dir: Path):
        """Legacy literal partner_a/b files map identically (regression)."""
        self._write_mappings(tmp_private_dir, _mock_account_mappings())
        owners = report_builder._load_account_owners()
        assert owners == {"1100001": "partner_a", "1100007": "partner_b"}

    def test_deterministic_regardless_of_key_order(self, tmp_private_dir: Path):
        """JSON key order must not affect slot assignment."""
        reversed_mappings = {
            "accounts": {
                "200": {"partner_id": "alex"},
                "100": {"partner_id": "sam"},
            },
            "partners": {
                "sam": {"label": "Sam"},
                "alex": {"label": "Alex"},
            },
            "schema_version": 1,
        }
        self._write_mappings(tmp_private_dir, reversed_mappings)
        assert report_builder._load_account_owners() == {
            "200": "partner_a",
            "100": "partner_b",
        }

    def test_third_partner_excluded(self, tmp_private_dir: Path):
        """Beyond the two-owner cap, partners get no slot (loud failure
        downstream is intentional — the pipeline is two-owner only)."""
        self._write_mappings(
            tmp_private_dir,
            {
                "schema_version": 1,
                "partners": {},
                "accounts": {
                    "100": {"partner_id": "a_first"},
                    "200": {"partner_id": "b_second"},
                    "300": {"partner_id": "c_third"},
                },
            },
        )
        owners = report_builder._load_account_owners()
        assert owners == {"100": "partner_a", "200": "partner_b"}

    def test_mixed_schema_literal_slot_token_passthrough(
        self, tmp_private_dir: Path
    ):
        """Custom partners block + one account already keyed by a literal
        slot: the token is NOT a pool member (else a third sorted ID could
        displace a real partner), passes through unchanged, and labels still
        resolve the real partners. Mirrors v4's
        load_unified_account_mapping rule on the same file shape."""
        self._write_mappings(
            tmp_private_dir,
            {
                "schema_version": 1,
                "partners": {
                    "alex": {"label": "Alex"},
                    "sam": {"label": "Sam"},
                },
                "accounts": {
                    "100": {"partner_id": "sam"},
                    "200": {"partner_id": "alex"},
                    "300": {"partner_id": "partner_a"},
                },
            },
        )
        owners = report_builder._load_account_owners()
        # alex→partner_a, sam→partner_b, literal slot stays partner_a.
        assert owners == {
            "200": "partner_a",
            "300": "partner_a",
            "100": "partner_b",
        }
        labels, warnings = report_builder._load_partner_labels()
        assert labels == {"partner_a": "Alex", "partner_b": "Sam"}
        assert warnings == []

    def test_missing_file_returns_empty(self, tmp_private_dir: Path):
        assert not (tmp_private_dir / "account_mappings.json").exists()
        assert report_builder._load_account_owners() == {}

    def test_malformed_file_returns_empty(self, tmp_private_dir: Path):
        (tmp_private_dir / "account_mappings.json").write_text(
            '["not", "a", "dict"]', encoding="utf-8"
        )
        assert report_builder._load_account_owners() == {}

    def test_build_report_with_custom_partner_ids(
        self, tmp_private_dir: Path
    ):
        """End-to-end: full report generation succeeds with custom IDs."""
        (tmp_private_dir / "account_mappings.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "partners": {
                        "alex": {"label": "Alex"},
                        "sam": {"label": "Sam"},
                    },
                    "accounts": {
                        "1100001": {
                            "name": "FxA Check Nordic Bank",
                            "partner_id": "alex",
                            "type": "checking",
                            "excluded": False,
                        },
                        "1100007": {
                            "name": "FxB Check Nordic Bank",
                            "partner_id": "sam",
                            "type": "checking",
                            "excluded": False,
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        (tmp_private_dir / "detailed_section_mapping.json").write_text(
            json.dumps(_mock_detailed_section_mapping()), encoding="utf-8"
        )
        (tmp_private_dir / "category_roles.json").write_text(
            json.dumps(_mock_category_roles()), encoding="utf-8"
        )
        (tmp_private_dir / "category_catalog.json").write_text(
            json.dumps(_mock_category_catalog()), encoding="utf-8"
        )
        (tmp_private_dir / "2026-07_ps_raw.json").write_text(
            json.dumps({"transactions": _mock_transactions()}),
            encoding="utf-8",
        )
        report = report_builder.build_report("2026-07")
        assert report["contract_version"] == report_builder.CONTRACT_VERSION


# --------------------------------------------------------------------------- #
# _load_partner_labels — custom-ID fallback, precedence, degradation.
# --------------------------------------------------------------------------- #


class TestLoadPartnerLabels:
    def _write_mappings(self, dir_path: Path, mappings: dict) -> None:
        (dir_path / "account_mappings.json").write_text(
            json.dumps(mappings), encoding="utf-8"
        )

    def test_custom_partner_ids_resolve_real_labels(self, tmp_private_dir: Path):
        """Regression: partners block keyed by custom IDs ("alex"/"sam")
        must resolve through the same sorted-slot map _load_account_owners
        uses — a literal partner_a/partner_b lookup finds nothing and the
        report silently shows placeholders."""
        self._write_mappings(
            tmp_private_dir,
            {
                "schema_version": 1,
                "partners": {
                    "sam": {"label": "Sam"},
                    "alex": {"label": "Alex"},
                },
                "accounts": {
                    "100": {"partner_id": "sam"},
                    "200": {"partner_id": "alex"},
                },
            },
        )
        labels, warnings = report_builder._load_partner_labels()
        # "alex" sorts before "sam" → partner_a.
        assert labels == {"partner_a": "Alex", "partner_b": "Sam"}
        assert warnings == []

    def test_partner_labels_json_wins_when_present(self, tmp_private_dir: Path):
        """partner_labels.json takes precedence over the mappings fallback."""
        self._write_mappings(
            tmp_private_dir,
            {
                "schema_version": 1,
                "partners": {
                    "alex": {"label": "Alex"},
                    "sam": {"label": "Sam"},
                },
                "accounts": {},
            },
        )
        (tmp_private_dir / "partner_labels.json").write_text(
            json.dumps({"partner_a": "Fixture A", "partner_b": "Fixture B"}),
            encoding="utf-8",
        )
        labels, warnings = report_builder._load_partner_labels()
        assert labels == {"partner_a": "Fixture A", "partner_b": "Fixture B"}
        assert warnings == []

    def test_malformed_partners_block_degrades_to_placeholders(
        self, tmp_private_dir: Path
    ):
        """Non-dict partners block → placeholders + warning, never raises."""
        self._write_mappings(
            tmp_private_dir,
            {"schema_version": 1, "partners": "bogus", "accounts": {}},
        )
        labels, warnings = report_builder._load_partner_labels()
        assert labels == {"partner_a": "Partner A", "partner_b": "Partner B"}
        assert warnings

    def test_missing_files_give_defaults_without_warnings(
        self, tmp_private_dir: Path
    ):
        labels, warnings = report_builder._load_partner_labels()
        assert labels == {"partner_a": "Partner A", "partner_b": "Partner B"}
        assert warnings == []


# --------------------------------------------------------------------------- #
# detailed DTO — nested paired_reimbursements contract.
# --------------------------------------------------------------------------- #


class TestDetailedNetSectionDto:
    def _build_pair_report(self, dir_path: Path) -> dict:
        """Full build with one fully-paired common pair (-500 pa / +500 pb)."""
        (dir_path / "account_mappings.json").write_text(
            json.dumps(_mock_account_mappings()), encoding="utf-8"
        )
        (dir_path / "detailed_section_mapping.json").write_text(
            json.dumps(_mock_detailed_section_mapping()), encoding="utf-8"
        )
        (dir_path / "category_roles.json").write_text(
            json.dumps(_mock_category_roles()), encoding="utf-8"
        )
        (dir_path / "category_catalog.json").write_text(
            json.dumps(_mock_category_catalog()), encoding="utf-8"
        )
        (dir_path / "partner_labels.json").write_text(
            json.dumps({"partner_a": "Fixture A", "partner_b": "Fixture B"}),
            encoding="utf-8",
        )
        transactions = [
            {
                "id": 100001,
                "date": "2026-07-03",
                "amount": -500.00,
                "payee": "Shop",
                "note": None,
                "is_transfer": False,
                "account": {"id": "1100001", "name": "FxA Check Nordic Bank"},
                "category": {
                    "id": 2100005,
                    "title": "Supermarket",
                    "parent_id": 2100003,
                },
                "category_hierarchy": [
                    {"id": "2100003", "title": "Groceries"},
                    {"id": "2100005", "title": "Supermarket"},
                ],
            },
            {
                "id": 100002,
                "date": "2026-07-04",
                "amount": 500.00,
                "payee": "Repayment",
                "note": None,
                "is_transfer": False,
                "account": {"id": "1100007", "name": "FxB Check Nordic Bank"},
                "category": {
                    "id": 2100005,
                    "title": "Supermarket",
                    "parent_id": 2100003,
                },
                "category_hierarchy": [
                    {"id": "2100003", "title": "Groceries"},
                    {"id": "2100005", "title": "Supermarket"},
                ],
            },
        ]
        (dir_path / "2026-07_ps_raw.json").write_text(
            json.dumps({"transactions": transactions}), encoding="utf-8"
        )
        return report_builder.build_report("2026-07")

    def test_category_rows_carry_nested_paired_reimbursements(
        self, tmp_private_dir: Path
    ):
        """Fully-paired common category keeps its zero-net row; the pair is
        nested under it AND still present in the flattened section list."""
        report = self._build_pair_report(tmp_private_dir)
        common = report["detailed"]["common"]
        assert len(common["rows"]) == 1
        row = common["rows"][0]
        assert row["total"] == 0.0
        assert row["total_class"] == "zero"
        assert row["g_share_partner_a"] is None
        assert len(row["paired_reimbursements"]) == 1
        nested = row["paired_reimbursements"][0]
        assert nested["category_title"] == "Groceries / Supermarket"
        assert nested["partner_a"] == -500.0
        assert nested["partner_a_class"] == "neg"
        assert nested["partner_b"] == 500.0
        assert nested["partner_b_class"] == "pos"
        assert nested["total"] == 0.0
        assert nested["total_class"] == "zero"
        # Section-level flattened list unchanged (backward compat).
        assert common["paired_reimbursements"] == row["paired_reimbursements"]


# --------------------------------------------------------------------------- #
# Mega namespace bridging — partner_label_map temp file.
# --------------------------------------------------------------------------- #


class TestMegaNamespacePartnerLabels:
    def test_real_labels_write_temp_map_file(self, tmp_private_dir: Path):
        """Resolved real labels (not placeholder defaults) → temp JSON map
        file with the partner_a/partner_b slot shape, cleaned up after."""
        from budget_api.services import mega_builder

        (tmp_private_dir / "partner_labels.json").write_text(
            json.dumps({"partner_a": "Fixture A", "partner_b": "Fixture B"}),
            encoding="utf-8",
        )
        args = mega_builder._build_namespace("2026-01", "2026-02")
        tmp_path = args.partner_label_map
        try:
            assert tmp_path is not None
            assert Path(tmp_path).exists()
            loaded = json.loads(Path(tmp_path).read_text(encoding="utf-8"))
            assert loaded == {"partner_a": "Fixture A", "partner_b": "Fixture B"}
        finally:
            mega_builder._cleanup_namespace(args)
        assert not Path(tmp_path).exists()

    def test_custom_id_labels_resolved_via_mappings(self, tmp_private_dir: Path):
        """Mega reports get real labels even with custom partner IDs — the
        account_mappings partners fallback now bridges through."""
        from budget_api.services import mega_builder

        (tmp_private_dir / "account_mappings.json").write_text(
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
        args = mega_builder._build_namespace("2026-01", "2026-02")
        try:
            assert args.partner_label_map is not None
            loaded = json.loads(
                Path(args.partner_label_map).read_text(encoding="utf-8")
            )
            assert loaded == {"partner_a": "Alex", "partner_b": "Sam"}
        finally:
            mega_builder._cleanup_namespace(args)

    def test_placeholder_defaults_pass_none(self, tmp_private_dir: Path):
        """Placeholder defaults (no config) → None, as before."""
        from budget_api.services import mega_builder

        args = mega_builder._build_namespace("2026-01", "2026-02")
        try:
            assert args.partner_label_map is None
        finally:
            mega_builder._cleanup_namespace(args)
