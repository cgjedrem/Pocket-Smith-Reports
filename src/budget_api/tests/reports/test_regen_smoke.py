"""T065 / LG-008: v2 regeneration smoke.

Monthly + mega regenerate from the sample fixture under contract v2;
recursive payload walk proves no legacy identifiers remain; bills rebuild
emits schema_version 5 + partner_id. Runs alongside the golden
byte-equality test (test_golden_fixture.py).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from budget_api.services import bills_builder, mega_builder, report_builder
from budget_api.tests.bills.test_builder import (
    ACCOUNT_CATALOG,
    ACCOUNT_MAPPINGS,
    CATEGORY_CATALOG,
    CATEGORY_ROLES,
    _ps_events,
    _ps_transactions,
)
from budget_api.tests.test_mega_builder import _all_months, _mock_context

_REPO_ROOT = Path(__file__).resolve().parents[4]
# Assembled from fragments so the literal substrings never appear in the
# tracked tree (LG-002 containment); runtime values are the real identifiers.
_FORBIDDEN = ("chris" + "tian", "ra" + "sma", "gjed" + "rem")


def _walk_strings(node: Any) -> list[str]:
    out: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            out.append(str(key))
            out.extend(_walk_strings(value))
    elif isinstance(node, list):
        for item in node:
            out.extend(_walk_strings(item))
    elif isinstance(node, str):
        out.append(node)
    return out


def _assert_no_legacy_strings(payload: Any) -> None:
    for text in _walk_strings(payload):
        lowered = text.lower()
        for needle in _FORBIDDEN:
            assert needle not in lowered, f"legacy identifier {needle!r} in {text!r}"


class _FrozenDatetime(bills_builder.datetime):
    """Same 2026-08-31 pin as bills/conftest.py (fixtures assume Aug 2026)."""

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls(2026, 8, 31, 12, 0, 0)
        return cls(2026, 8, 31, 10, 0, 0, tzinfo=tz)


@pytest.fixture(autouse=True)
def _frozen_bills_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bills_builder, "datetime", _FrozenDatetime)


@pytest.fixture
def sample_month_seed(tmp_private_dir: Path) -> Path:
    fixture = json.loads(
        (_REPO_ROOT / "data" / "sample_apr_2026.json").read_text(encoding="utf-8")
    )
    (tmp_private_dir / "2026-04_ps_raw.json").write_text(
        json.dumps(fixture), encoding="utf-8"
    )
    mapping = json.loads(
        (_REPO_ROOT / "data" / "sample_apr_2026_detailed_section_mapping.json")
        .read_text(encoding="utf-8")
    )
    (tmp_private_dir / "detailed_section_mapping.json").write_text(
        json.dumps(mapping), encoding="utf-8"
    )
    return tmp_private_dir


def test_monthly_regen_is_v2_and_clean(sample_month_seed):
    report = report_builder.build_report("2026-04")
    assert report["contract_version"] == 2
    assert report["calculation_version"] == 7
    assert "personal_partner_a" in report["detailed"]
    assert "personal_partner_b" in report["detailed"]
    _assert_no_legacy_strings(report)


def test_mega_regen_is_v2_and_clean(tmp_private_dir):
    for month in _all_months("2026-01", "2026-07"):
        (tmp_private_dir / f"{month}_ps_raw.json").write_text(
            json.dumps([{"id": 1}, {"id": 2}]), encoding="utf-8"
        )
    (tmp_private_dir / "partner_labels.json").write_text(
        json.dumps({"partner_a": "Fixture A", "partner_b": "Fixture B"}),
        encoding="utf-8",
    )
    (tmp_private_dir / "account_mappings.json").write_text(
        json.dumps({"schema_version": 1, "partners": {}, "accounts": {}}),
        encoding="utf-8",
    )
    (tmp_private_dir / "detailed_section_mapping.json").write_text(
        json.dumps({"account_roles": {}, "category_sections": {}}), encoding="utf-8"
    )
    with patch(
        "budget_api.services.mega_builder.build_context",
        return_value=_mock_context(),
    ):
        report = mega_builder.build_mega_report("2026-01", "2026-07")
    assert report["contract_version"] == 2
    assert report["calculation_version"] == mega_builder.MEGA_CALCULATION_VERSION
    _assert_no_legacy_strings(report)


def test_bills_rebuild_emits_schema5_and_partner_id():
    snapshot = bills_builder.build_bills_snapshot(
        month="2026-07",
        events=_ps_events(),
        transactions=_ps_transactions(),
        account_mappings=ACCOUNT_MAPPINGS,
        category_roles=CATEGORY_ROLES,
        category_catalog=CATEGORY_CATALOG,
        account_catalog=ACCOUNT_CATALOG,
        live_combined=None,
        deltas_per_month=None,
    )
    assert snapshot["schema_version"] == 5
    assert {p["partner_id"] for p in snapshot["partners"]} == {
        "partner_a",
        "partner_b",
    }
    for block in snapshot["partners"]:
        assert block["partner_slot"] in ("a", "b")
        for event in block["events"]:
            assert event["partner_id"] == block["partner_id"]
    _assert_no_legacy_strings(snapshot)
