"""Golden-fixture baseline snapshot — monthly-reports-logic-migration.

Seeds a tmp private dir from the real public synthetic fixture
(data/sample_apr_2026.json + its section mapping) and calls
build_report("2026-04"). Asserts the result matches the committed baseline
JSON snapshot in golden/sample_apr_2026_report.json.

PR2 regenerated this snapshot once `detailed`/`personal_share`/`balanced`
started being computed (design doc L3 "Parity proof" — same synthetic
fixture, diffed against the committed baseline to prove nothing else moved).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from budget_api.services import report_builder

REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURE_PATH = REPO_ROOT / "data" / "sample_apr_2026.json"
MAPPING_PATH = REPO_ROOT / "data" / "sample_apr_2026_detailed_section_mapping.json"
GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "sample_apr_2026_report.json"

MONTH = "2026-04"


@pytest.fixture
def seeded_synthetic_private_dir(tmp_private_dir: Path) -> Path:
    """Seed tmp private dir with the public synthetic fixture as ps_raw.

    Deliberately does NOT seed account_mappings.json/category_roles.json —
    ownership resolves via the reserved-synthetic-ID + "Fixture A "/
    "Fixture B " name-prefix fallback (accounting._synthetic_owner), same as
    the documented CLI "quick start" path (no private files needed).
    """
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    (tmp_private_dir / "2026-04_ps_raw.json").write_text(
        json.dumps(fixture), encoding="utf-8"
    )
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    (tmp_private_dir / "detailed_section_mapping.json").write_text(
        json.dumps(mapping), encoding="utf-8"
    )
    return tmp_private_dir


def test_build_report_matches_golden_baseline(
    seeded_synthetic_private_dir: Path,
) -> None:
    """build_report(synthetic fixture) matches the committed baseline snapshot.

    Regenerate golden/sample_apr_2026_report.json only when a legitimate
    accounting change intentionally alters expected values.
    """
    report = report_builder.build_report(MONTH)
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert report == golden


def test_golden_baseline_detailed_populated() -> None:
    """PR2: `detailed` is now computed server-side (no category_roles.json
    seeded here, so `personal_share`/`kpis` stay None — nullable rule)."""
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert golden["contract_version"] == 2
    assert golden["calculation_version"] == 7
    assert golden["detailed"] is not None
    # Hand-checked against client/src/components/reports/DetailedSections.tsx
    # formulas on the fixture data (see PR2 report for full derivation).
    assert golden["detailed"]["income"]["total_income"] == 56500.0
    assert golden["detailed"]["home"]["total_partner_a"] == 1700.0
    assert golden["detailed"]["savings"]["household"]["rate"] == pytest.approx(
        13.097345132743362
    )
    assert golden["personal_share"] is None
    assert golden["balanced"] is True


def _populated_detailed() -> dict:
    """Fully populated `detailed` payload with explicit +/-/zero sign values
    and null percentages — the DTO graph exercised end-to-end regardless of
    what the golden baseline happens to contain (PR#53 review C1)."""
    income_row = {
        "partner_a": 1.0,
        "partner_a_class": "pos",
        "partner_b": -1.0,
        "partner_b_class": "neg",
        "total": 0.0,
        "total_class": "zero",
        "row_pct_partner_a": None,
        "row_pct_partner_b": None,
        "household_pct": None,
    }
    savings_row = {
        "to_savings": 1.0,
        "to_savings_class": "pos",
        "from_savings": -1.0,
        "from_savings_class": "neg",
        "net_saved": 0.0,
        "net_saved_class": "zero",
        "income": 1.0,
        "income_class": "pos",
        "rate": None,
    }
    net_row = {
        "category_title": "Fixture",
        "partner_a_net": 1.0,
        "partner_a_net_class": "pos",
        "partner_b_net": -1.0,
        "partner_b_net_class": "neg",
        "total": 0.0,
        "total_class": "zero",
        "g_share_partner_a": None,
        "g_share_partner_b": None,
    }
    paired_row = {
        "category_title": "Fixture (paired reimbursement)",
        "partner_a": -1.0,
        "partner_a_class": "neg",
        "partner_b": 1.0,
        "partner_b_class": "pos",
        "total": 0.0,
        "total_class": "zero",
    }
    net_section = {
        "rows": [net_row],
        "paired_reimbursements": [paired_row],
        "total_partner_a": 1.0,
        "total_partner_a_class": "pos",
        "total_partner_b": -1.0,
        "total_partner_b_class": "neg",
        "total": 0.0,
        "total_class": "zero",
        "share_partner_a": None,
        "share_partner_b": None,
    }
    personal_row = {
        "category_title": "Fixture",
        "paid_partner_a": -1.0,
        "paid_partner_a_class": "neg",
        "paid_partner_b": 0.0,
        "paid_partner_b_class": "zero",
        "total": -1.0,
        "total_class": "neg",
        "pct_personal": None,
        "pct_household": None,
    }
    personal_section = {
        "rows": [personal_row],
        "personal_total": -1.0,
        "personal_total_class": "neg",
        "household_total": -1.0,
        "household_total_class": "neg",
        "pct_personal": None,
        "pct_household": None,
    }
    excluded_row = {
        "category_title": "Fixture",
        "paid_partner_a": -1.0,
        "paid_partner_a_class": "neg",
        "paid_partner_b": 0.0,
        "paid_partner_b_class": "zero",
        "total": -1.0,
        "total_class": "neg",
    }
    return {
        "income": {
            "salary": income_row,
            "third_party": income_row,
            "total_partner_a": 1.0,
            "total_partner_a_class": "pos",
            "total_partner_b": -1.0,
            "total_partner_b_class": "neg",
            "total_income": 0.0,
            "total_income_class": "zero",
        },
        "savings": {
            "partner_a": savings_row,
            "partner_b": savings_row,
            "household": savings_row,
        },
        "home": net_section,
        "common": net_section,
        "personal_partner_a": personal_section,
        "personal_partner_b": personal_section,
        "trips": net_section,
        "cc_payments": {
            "partner_a_paid": -1.0,
            "partner_a_paid_class": "neg",
            "partner_b_paid": 0.0,
            "partner_b_paid_class": "zero",
            "household_paid": -1.0,
            "household_paid_class": "neg",
        },
        "excluded": {"rows": [excluded_row], "total": -1.0, "total_class": "neg"},
        "household_totals": {
            "partner_a": -1.0,
            "partner_a_class": "neg",
            "partner_b": 0.0,
            "partner_b_class": "zero",
            "total": -1.0,
            "total_class": "neg",
        },
    }


def test_detailed_dto_contract_populated_roundtrip() -> None:
    """Fully populated DetailedSections payload validates against the DTO
    graph, covers pos/neg/zero signs + null percentages, and round-trips
    through JSON losslessly (PR#53 review C1)."""
    from budget_api.models.reports import DetailedSections

    detailed = DetailedSections.model_validate(_populated_detailed())
    for field in type(detailed).model_fields:
        assert getattr(detailed, field) is not None, f"detailed.{field} is null"

    classes = {
        detailed.home.paired_reimbursements[0].partner_a_class,
        detailed.home.paired_reimbursements[0].partner_b_class,
        detailed.home.paired_reimbursements[0].total_class,
        detailed.home.rows[0].partner_a_net_class,
        detailed.home.rows[0].partner_b_net_class,
    }
    assert classes == {"pos", "neg", "zero"}

    dumped = json.loads(detailed.model_dump_json())
    assert DetailedSections.model_validate(dumped) == detailed
    assert dumped["home"]["rows"][0]["g_share_partner_a"] is None


def test_golden_baseline_personal_subtotals() -> None:
    """PR5: per-section subtotal = sum of the section's own row totals.

    Parity with the old UI/legacy HTML "Subtotal" row — personal_total is
    shared across BOTH personal sections, so rendering it as each section's
    subtotal was the PR2–PR4 parity break. Hand-checked against the fixture
    (subtotals differ between partners by construction).
    """
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    partner_a = golden["detailed"]["personal_partner_a"]
    partner_b = golden["detailed"]["personal_partner_b"]

    assert partner_a["subtotal"] == 1000.0
    assert partner_a["subtotal_class"] == "pos"
    assert partner_b["subtotal"] == 1200.0
    assert partner_b["subtotal_class"] == "pos"

    for section in (partner_a, partner_b):
        # Sum-of-rows parity — bit-identical accumulation order as the
        # accounting builder, so exact float compare holds.
        assert section["subtotal"] == sum(row["total"] for row in section["rows"])
        # Per-section subtotal must not collapse into the shared personal_total.
        assert section["subtotal"] != section["personal_total"]
        # subtotal_class matches the existing _sign_class convention
        # (exact-zero compare).
        assert section["subtotal_class"] == (
            "zero"
            if section["subtotal"] == 0
            else ("pos" if section["subtotal"] > 0 else "neg")
        )

    # Both partners' sections differ on the fixture (guards against
    # accidentally emitting personal_total as the subtotal).
    assert partner_a["subtotal"] != partner_b["subtotal"]
    # Composition: the two subtotals sum to the shared personal_total.
    assert partner_a["subtotal"] + partner_b["subtotal"] == partner_a["personal_total"]


def test_golden_baseline_normalized_transactions_restored() -> None:
    """PR5: normalized_transactions is back in the public contract (PR4 cut
    reverted — drilldown UX loss discovered in live smoke testing)."""
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert len(golden["normalized_transactions"]) == 43
    assert golden["txn_count"] == len(golden["normalized_transactions"])
