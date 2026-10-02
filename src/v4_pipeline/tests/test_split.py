"""Unit tests — common-economy split (accounting.py), category-level
selection (Gate 2 evolution).

Covers _resolve_allowed_category_ids (parent->descendant expansion, single
source of truth for "selecting a parent includes its descendants"),
net_category_totals (category-ID filtering + derived section, no more
section-eligibility restriction), compute_split (netting, sign, derived
section grouping/ordering, empty-categories allowed state),
migrate_legacy_split_sections / derive_split_sections (legacy-config
translation + best-effort display derivation), and
normalize_split_config/load_split_config (new categories-based schema,
legacy sections-only auto-translation, unknown-category-ID rejection).
"""

from __future__ import annotations

import json

import pytest

from accounting import (
    AccountingValidationError,
    _resolve_allowed_category_ids,
    compute_split,
    derive_split_sections,
    load_split_config,
    migrate_legacy_split_sections,
    net_category_totals,
    normalize_split_config,
)

# Leaf-keyed section mapping (detailed_section_mapping.json shape).
MAPPING = {
    "category_sections": {
        "c1": "home",
        "c2": "common",
        "c3": "common",
        "c4": "trips",
        "c5": "personal_partner_a",
    },
    "account_roles": {},
}

# child_id -> parent_id. p1/p2/p3 are intermediate catalog nodes; c5/top
# are top-level with no parent. "mid"/"leaf" exercise 2-level nesting.
CATEGORY_PARENTS = {
    "p1": None,
    "c1": "p1",
    "p2": None,
    "c2": "p2",
    "c3": "p2",
    "p3": None,
    "c4": "p3",
    "c5": None,
    "top": None,
    "mid": "top",
    "leaf": "mid",
}


def _record(
    record_id,
    amount,
    owner,
    category_id,
    date="2026-04-01",
    category_title="Cat",
    is_transfer=False,
):
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


# --------------------------------------------------------------------------- #
# _resolve_allowed_category_ids — parent selection -> descendant closure.
# --------------------------------------------------------------------------- #


class TestResolveAllowedCategoryIds:
    def test_no_catalog_returns_selection_unchanged(self):
        assert _resolve_allowed_category_ids(["c1", "c2"], None) == {"c1", "c2"}

    def test_leaf_with_no_children_returns_itself(self):
        assert _resolve_allowed_category_ids(["c1"], CATEGORY_PARENTS) == {"c1"}

    def test_parent_selection_expands_to_direct_children(self):
        assert _resolve_allowed_category_ids(["p2"], CATEGORY_PARENTS) == {
            "p2",
            "c2",
            "c3",
        }

    def test_grandparent_selection_expands_every_level(self):
        assert _resolve_allowed_category_ids(["top"], CATEGORY_PARENTS) == {
            "top",
            "mid",
            "leaf",
        }

    def test_multiple_selections_unioned_and_deduped(self):
        assert _resolve_allowed_category_ids(["p2", "c2"], CATEGORY_PARENTS) == {
            "p2",
            "c2",
            "c3",
        }

    def test_top_level_leaf_with_no_parent_entry_returns_itself(self):
        assert _resolve_allowed_category_ids(["c5"], CATEGORY_PARENTS) == {"c5"}

    def test_parent_selected_with_no_catalog_no_op_but_logs_warning(self, caplog):
        """IMPORTANT regression (iteration 4, finding 3): with no catalog
        loaded a "parent selection" ("p2" here, which WOULD have expanded
        to {p2, c2, c3} had the catalog been present) can't be
        distinguished from a genuine leaf ID — it passes through
        unexpanded, so it never matches any real leaf record and the
        split silently comes back empty on fresh installs (no
        category_catalog.json synced yet). Documented best-effort
        behavior: does NOT raise, matches literally (same as any other
        no-catalog call) — but it DOES log a WARNING naming the selected
        id(s) so this is visible in report build logs instead of being a
        silent empty split."""
        import logging

        with caplog.at_level(logging.WARNING, logger="accounting"):
            result = _resolve_allowed_category_ids(["p2"], None)
        assert result == {"p2"}  # best-effort: literal pass-through, no expansion
        assert any(
            record.levelno == logging.WARNING and "p2" in record.getMessage()
            for record in caplog.records
        )

    def test_empty_selection_with_no_catalog_does_not_log(self, caplog):
        """No selected IDs at all -> nothing to warn about."""
        import logging

        with caplog.at_level(logging.WARNING, logger="accounting"):
            result = _resolve_allowed_category_ids([], None)
        assert result == set()
        assert not caplog.records


# --------------------------------------------------------------------------- #
# net_category_totals — category-ID filtering (no section eligibility),
# derived `section` per row.
# --------------------------------------------------------------------------- #


class TestNetCategoryTotals:
    def test_includes_category_id_section_and_net_per_partner(self):
        records = [
            _record(1, -600.0, "partner_a", "c2", category_title="Groceries"),
            _record(2, -400.0, "partner_b", "c2", category_title="Groceries"),
        ]
        rows = net_category_totals(records, {"c2"}, MAPPING)
        assert rows == [
            {
                "category_id": "c2",
                "category_title": "Groceries",
                "section": "common",
                "net_partner_a": 600.0,
                "net_partner_b": 400.0,
            }
        ]

    def test_category_not_in_allowed_set_excluded(self):
        records = [_record(1, -100.0, "partner_a", "c1")]
        assert net_category_totals(records, {"c4"}, MAPPING) == []

    def test_received_amounts_reduce_net(self):
        records = [
            _record(1, -300.0, "partner_a", "c2"),
            _record(2, 100.0, "partner_a", "c2"),  # reimbursed back
        ]
        rows = net_category_totals(records, {"c2"}, MAPPING)
        assert rows[0]["net_partner_a"] == 200.0
        assert rows[0]["net_partner_b"] == 0.0

    def test_categories_outside_home_common_trips_included(self):
        """No more section-eligibility restriction — any category the
        caller allows, including personal_* sections, is included."""
        records = [_record(1, -100.0, "partner_a", "c5", category_title="Gear")]
        rows = net_category_totals(records, {"c5"}, MAPPING)
        assert rows == [
            {
                "category_id": "c5",
                "category_title": "Gear",
                "section": "personal_partner_a",
                "net_partner_a": 100.0,
                "net_partner_b": 0.0,
            }
        ]

    def test_transfer_dropped_when_natural_section_not_home_savings_excluded(self):
        """Same drop rule as _records_in_section/_routed_section — a
        transfer whose natural section is "common" isn't real partner
        spend, so it's excluded even if its category is allowed."""
        records = [_record(1, -500.0, "partner_a", "c2", is_transfer=True)]
        assert net_category_totals(records, {"c2"}, MAPPING) == []

    def test_transfer_kept_when_natural_section_is_home(self):
        records = [_record(1, -500.0, "partner_a", "c1", is_transfer=True)]
        rows = net_category_totals(records, {"c1"}, MAPPING)
        assert rows[0]["net_partner_a"] == 500.0


# --------------------------------------------------------------------------- #
# compute_split — netting, sign, derived-section grouping/ordering, empty
# state.
# --------------------------------------------------------------------------- #


def _row(category_id, title, section, net_a, net_b):
    return {
        "category_id": category_id,
        "category_title": title,
        "section": section,
        "net_partner_a": net_a,
        "net_partner_b": net_b,
    }


class TestComputeSplit:
    def test_empty_categories_returns_zero_state(self):
        """Design decision: enabled=true + zero categories selected is
        ALLOWED, not rejected — empty rows, settlement None, sections []."""
        result = compute_split([], {"partner_a": 50.0, "partner_b": 50.0})
        assert result == {
            "shares": {"partner_a": 50.0, "partner_b": 50.0},
            "sections": [],
            "rows": [],
            "settlement": None,
        }

    def test_even_split_zero_delta_no_settlement(self):
        """Partner A paid the whole 1000 category but shares are 50/50 —
        fair share is 500 each, so delta_a = 500 (A overpaid by 500)."""
        nets = [_row("c1", "Home", "home", 1000.0, 0.0)]
        result = compute_split(nets, {"partner_a": 50.0, "partner_b": 50.0})
        assert result["rows"] == [
            {
                "category_id": "c1",
                "label": "Home",
                "section": "home",
                "actual": 1000.0,
                "fair": 500.0,
                "delta": 500.0,
                "actual_b": 0.0,
                "fair_b": 500.0,
                "delta_b": -500.0,
            }
        ]
        assert result["settlement"] == {
            "from_partner": "partner_b",
            "to_partner": "partner_a",
            "amount": 500.0,
        }

    def test_actual_matches_fair_share_no_settlement(self):
        """Partner A paid exactly their 70% fair share — nothing owed."""
        nets = [_row("c1", "Home", "home", 700.0, 300.0)]
        result = compute_split(nets, {"partner_a": 70.0, "partner_b": 30.0})
        assert result["rows"][0]["delta"] == 0.0
        assert result["settlement"] is None

    def test_settlement_direction_flips_when_b_overpays(self):
        nets = [_row("c1", "Home", "home", 0.0, 1000.0)]
        result = compute_split(nets, {"partner_a": 50.0, "partner_b": 50.0})
        assert result["settlement"] == {
            "from_partner": "partner_a",
            "to_partner": "partner_b",
            "amount": 500.0,
        }

    def test_settlement_nets_across_multiple_categories_and_sections(self):
        """One category favors A, another favors B — settlement is the
        single netted total, not a per-category transfer."""
        nets = [
            _row("c1", "Home", "home", 1000.0, 0.0),  # A overpays 500 @ 50/50
            _row("c2", "Groceries", "common", 0.0, 1000.0),  # B overpays 500
        ]
        result = compute_split(nets, {"partner_a": 50.0, "partner_b": 50.0})
        assert len(result["rows"]) == 2
        assert result["settlement"] is None  # deltas cancel out exactly

    def test_categories_outside_home_common_trips_contribute(self):
        """No section-eligibility restriction any more — a personal_*
        category row participates in rows + settlement like any other."""
        nets = [_row("c5", "Gear", "personal_partner_a", 200.0, 0.0)]
        result = compute_split(nets, {"partner_a": 50.0, "partner_b": 50.0})
        assert [row["category_id"] for row in result["rows"]] == ["c5"]
        assert result["settlement"]["amount"] == 100.0

    def test_rows_grouped_by_derived_section_canonical_order(self):
        """Canonical order: home, common, trips, personal_partner_a,
        personal_partner_b, then anything else alphabetically — input
        order here is deliberately scrambled."""
        nets = [
            _row("c5", "Gear", "personal_partner_a", 10.0, 0.0),
            _row("c4", "Trip", "trips", 10.0, 0.0),
            _row("zz", "Misc", "misc_zeta", 10.0, 0.0),
            _row("c2", "Groceries", "common", 10.0, 0.0),
            _row("c1", "Home", "home", 10.0, 0.0),
            _row("aa", "Alpha", "aaa_alpha", 10.0, 0.0),
        ]
        result = compute_split(nets, {"partner_a": 50.0, "partner_b": 50.0})
        assert [row["category_id"] for row in result["rows"]] == [
            "c1",
            "c2",
            "c4",
            "c5",
            "aa",
            "zz",
        ]
        assert result["sections"] == [
            "home",
            "common",
            "trips",
            "personal_partner_a",
            "aaa_alpha",
            "misc_zeta",
        ]

    def test_shares_echoed_back_sections_derived_from_rows(self):
        nets = [_row("c1", "Home", "home", 100.0, 100.0)]
        result = compute_split(nets, {"partner_a": 60.0, "partner_b": 40.0})
        assert result["shares"] == {"partner_a": 60.0, "partner_b": 40.0}
        assert result["sections"] == ["home"]

    def test_balanced_multi_category_nonround_shares_no_fabricated_settlement(self):
        """Regression (iteration 4 CRITICAL fix): float-equality (`!= 0`)
        fabricated a spurious ~0.00 settlement once a genuinely balanced
        split with non-round shares (33.33/66.67-style) accumulates float
        noise across 10+ categories. Here the raw delta sum is ~5e-13 —
        nonzero bit-for-bit, but well inside the settlement gate's
        half-cent (0.005) threshold — must resolve to None, never a
        fabricated transfer."""
        totals = [
            300.0, 600.0, 150.0, 900.0, 450.0, 1200.0,
            75.0, 2100.0, 330.0, 990.0, 60.0, 1770.0,
        ]
        nets = [
            _row(f"c{i}", f"Cat{i}", "common", total / 3.0, total - total / 3.0)
            for i, total in enumerate(totals)
        ]
        shares = {"partner_a": 100 / 3, "partner_b": 200 / 3}
        result = compute_split(nets, shares)
        assert len(result["rows"]) == len(totals)
        total_delta = sum(row["delta"] for row in result["rows"])
        # Proves the fixture actually exercises float noise, not a trivially
        # exact-zero case — the pre-fix `!= 0` check would have fabricated
        # a settlement here.
        assert total_delta != 0.0
        assert abs(total_delta) < 1e-6
        assert result["settlement"] is None

    def test_b_side_is_exact_complement_of_a_side(self):
        """USER-REQUESTED: both partners' columns visible. b-side is
        additive — a-side fields untouched (backward compat) — and must
        be the exact complement per row: actual_b = total - actual,
        delta_b == -delta, fair_a + fair_b == category total."""
        nets = [
            _row("c1", "Home", "home", 700.0, 300.0),
            _row("c2", "Groceries", "common", 120.0, 480.0),
        ]
        shares = {"partner_a": 70.0, "partner_b": 30.0}
        result = compute_split(nets, shares)
        for row, net in zip(result["rows"], nets):
            total = net["net_partner_a"] + net["net_partner_b"]
            assert row["actual_b"] == pytest.approx(total - row["actual"])
            assert row["fair"] + row["fair_b"] == pytest.approx(total)
            assert row["delta_b"] == pytest.approx(-row["delta"])

    def test_b_side_exact_complement_nonround_shares(self):
        """Same complement invariants, non-round shares (33.33/66.67-style)
        — proves the tolerance-based equalities hold under float noise,
        not just clean 50/50 or 70/30 splits."""
        totals = [300.0, 600.0, 150.0, 900.0, 450.0]
        nets = [
            _row(f"c{i}", f"Cat{i}", "common", total / 3.0, total - total / 3.0)
            for i, total in enumerate(totals)
        ]
        shares = {"partner_a": 100 / 3, "partner_b": 200 / 3}
        result = compute_split(nets, shares)
        for row, total in zip(result["rows"], totals):
            assert row["fair"] + row["fair_b"] == pytest.approx(total, abs=1e-9)
            assert row["delta_b"] == pytest.approx(-row["delta"], abs=1e-9)
            assert row["actual_b"] == pytest.approx(total - row["actual"], abs=1e-9)

    def test_b_side_derived_complement_under_share_sum_tolerance(self):
        """Regression: normalize_split_config accepts shares summing to
        100 ± 1e-6 (here 100.0000004). fair_b must be DERIVED
        (total - fair_a), not independently multiplied — otherwise
        fair_a + fair_b drifts off the category total by the share-sum
        excess. Pins fair_a + fair_b == total and delta_b == -delta_a
        exactly (share_a >= 50% keeps total - fair_a inside Sterbenz
        range, so both identities are bit-exact here)."""
        shares = {"partner_a": 50.0000002, "partner_b": 50.0000002}
        # Guard: this fixture really is inside the validator's tolerance.
        normalize_split_config(
            {"enabled": True, "shares": shares, "categories": ["c1"]}
        )
        nets = [
            _row("c1", "Home", "home", 700.0, 300.0),
            _row("c2", "Groceries", "common", 120.0, 480.0),
        ]
        result = compute_split(nets, shares)
        for row, net in zip(result["rows"], nets):
            total = net["net_partner_a"] + net["net_partner_b"]
            assert row["fair"] + row["fair_b"] == total
            assert row["delta_b"] == -row["delta"]

    def test_sub_cent_imbalance_never_emits_zero_looking_settlement(self):
        """Regression: the settlement gate uses the same 0.005 half-cent
        snap as the totals-row dust snap — a delta of ~0.002 would render
        as 'X owes Y 0.00'. Below the snap -> settlement None."""
        # total 2.002 @ 50/50 -> fair 1.001, delta_a = 0.001 (< 0.005).
        nets = [_row("c1", "Home", "home", 1.002, 1.0)]
        result = compute_split(nets, {"partner_a": 50.0, "partner_b": 50.0})
        assert 0 < abs(result["rows"][0]["delta"]) < 0.005  # fixture guard
        assert result["settlement"] is None

    def test_imbalance_at_or_above_half_cent_still_settles(self):
        """Boundary: a delta the display snap would NOT round to 0.00
        (>= 0.005 -> renders 0,01) still produces a settlement."""
        # total 2.012 @ 50/50 -> fair 1.006, delta_a = 0.006 (>= 0.005).
        nets = [_row("c1", "Home", "home", 1.012, 1.0)]
        result = compute_split(nets, {"partner_a": 50.0, "partner_b": 50.0})
        assert result["rows"][0]["delta"] >= 0.005  # fixture guard
        assert result["settlement"] is not None
        assert result["settlement"]["from_partner"] == "partner_b"
        assert result["settlement"]["to_partner"] == "partner_a"
        assert result["settlement"]["amount"] == pytest.approx(0.006)


# --------------------------------------------------------------------------- #
# migrate_legacy_split_sections — legacy sections-only config -> category
# IDs, via detailed_section_mapping LEAF keys (not catalog expansion).
# --------------------------------------------------------------------------- #


class TestMigrateLegacySplitSections:
    def test_translates_via_leaf_mapping(self):
        assert migrate_legacy_split_sections(["home", "trips"], MAPPING) == [
            "c1",
            "c4",
        ]

    def test_empty_sections_returns_empty(self):
        assert migrate_legacy_split_sections([], MAPPING) == []

    def test_section_with_no_mapped_categories_yields_nothing(self):
        assert migrate_legacy_split_sections(["savings"], MAPPING) == []

    def test_only_categories_currently_mapped_to_listed_sections_included(self):
        """"common" has 2 leaf categories mapped to it — both included,
        nothing from "home"/"trips" leaks in."""
        assert migrate_legacy_split_sections(["common"], MAPPING) == ["c2", "c3"]


# --------------------------------------------------------------------------- #
# derive_split_sections — best-effort display derivation (never raises).
# --------------------------------------------------------------------------- #


class TestDeriveSplitSections:
    def test_derives_sections_for_selected_categories(self):
        assert derive_split_sections(["c1", "c2"], MAPPING, CATEGORY_PARENTS) == [
            "home",
            "common",
        ]

    def test_parent_selection_expands_before_deriving(self):
        """Selecting p2 (parent of c2/c3) derives "common" via the
        expanded descendants, not by looking up p2 itself."""
        assert derive_split_sections(["p2"], MAPPING, CATEGORY_PARENTS) == ["common"]

    def test_no_detailed_section_mapping_returns_empty(self):
        assert derive_split_sections(["c1"], None, CATEGORY_PARENTS) == []

    def test_unmapped_category_with_no_ancestor_mapping_skipped(self):
        mapping = {"category_sections": {}, "account_roles": {}}
        assert derive_split_sections(["c1"], mapping, CATEGORY_PARENTS) == []

    def test_ancestor_fallback_when_leaf_itself_unmapped(self):
        """"child" has no direct category_sections entry, but its parent
        does — best-effort walks the ancestor chain rather than skipping."""
        parents = {"child": "parent", "parent": None}
        mapping = {"category_sections": {"parent": "common"}, "account_roles": {}}
        assert derive_split_sections(["child"], mapping, parents) == ["common"]


# --------------------------------------------------------------------------- #
# normalize_split_config / load_split_config — new categories-based schema,
# legacy sections-only auto-translation, unknown-category-ID rejection.
# --------------------------------------------------------------------------- #


class TestNormalizeSplitConfig:
    def test_disabled_returns_none(self):
        assert normalize_split_config(
            {
                "enabled": False,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": [],
            }
        ) is None

    def test_valid_enabled_config_with_categories_normalizes(self):
        result = normalize_split_config(
            {
                "enabled": True,
                "shares": {"partner_a": 60.0, "partner_b": 40.0},
                "categories": ["c1", "c2"],
            }
        )
        assert result == {
            "shares": {"partner_a": 60.0, "partner_b": 40.0},
            "categories": ["c1", "c2"],
        }

    def test_sections_field_ignored_when_categories_present(self):
        result = normalize_split_config(
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["c1"],
                "sections": ["this-is-stale-and-ignored"],
            }
        )
        assert result["categories"] == ["c1"]

    def test_duplicate_categories_deduped_preserving_order(self):
        result = normalize_split_config(
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["c2", "c1", "c2"],
            }
        )
        assert result["categories"] == ["c2", "c1"]

    def test_unknown_category_id_rejected_when_valid_ids_given(self):
        with pytest.raises(AccountingValidationError, match="unknown category ID"):
            normalize_split_config(
                {
                    "enabled": True,
                    "shares": {"partner_a": 50.0, "partner_b": 50.0},
                    "categories": ["c1", "does-not-exist"],
                },
                valid_category_ids={"c1", "c2"},
            )

    def test_unknown_category_id_skipped_when_valid_ids_none(self):
        result = normalize_split_config(
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["does-not-exist"],
            },
            valid_category_ids=None,
        )
        assert result["categories"] == ["does-not-exist"]

    def test_legacy_sections_only_translates_via_detailed_section_mapping(self):
        result = normalize_split_config(
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "sections": ["home"],
            },
            detailed_section_mapping=MAPPING,
        )
        assert result == {
            "shares": {"partner_a": 50.0, "partner_b": 50.0},
            "categories": ["c1"],
        }

    def test_legacy_sections_without_mapping_raises(self):
        with pytest.raises(AccountingValidationError, match="detailed section mapping"):
            normalize_split_config(
                {
                    "enabled": True,
                    "shares": {"partner_a": 50.0, "partner_b": 50.0},
                    "sections": ["home"],
                }
            )

    def test_legacy_unknown_section_rejected(self):
        with pytest.raises(AccountingValidationError, match="unknown section"):
            normalize_split_config(
                {
                    "enabled": True,
                    "shares": {"partner_a": 50.0, "partner_b": 50.0},
                    "sections": ["not-a-real-section"],
                },
                detailed_section_mapping=MAPPING,
            )

    def test_neither_categories_nor_sections_raises(self):
        with pytest.raises(AccountingValidationError, match="categories or sections"):
            normalize_split_config(
                {
                    "enabled": True,
                    "shares": {"partner_a": 50.0, "partner_b": 50.0},
                }
            )

    def test_shares_not_summing_to_100_raises(self):
        with pytest.raises(AccountingValidationError, match="sum to 100"):
            normalize_split_config(
                {
                    "enabled": True,
                    "shares": {"partner_a": 60.0, "partner_b": 30.0},
                    "categories": [],
                }
            )

    def test_shares_sum_within_tolerance_passes(self):
        result = normalize_split_config(
            {
                "enabled": True,
                "shares": {"partner_a": 50.0000001, "partner_b": 49.9999999},
                "categories": [],
            }
        )
        assert result["categories"] == []

    def test_share_out_of_range_rejected(self):
        with pytest.raises(AccountingValidationError, match="between 0 and 100"):
            normalize_split_config(
                {
                    "enabled": True,
                    "shares": {"partner_a": 150.0, "partner_b": -50.0},
                    "categories": [],
                }
            )

    def test_nan_share_rejected(self):
        """Regression (iteration 4 CRITICAL fix): NaN compares false in
        every range/sum check (`NaN < 0` is False, `NaN > 100` is False,
        `abs(NaN + x - 100) > 1e-6` is False) — a bare range check lets
        `float("nan")` sail through and get persisted. Must raise before
        those comparisons run."""
        with pytest.raises(AccountingValidationError, match="finite"):
            normalize_split_config(
                {
                    "enabled": True,
                    "shares": {"partner_a": float("nan"), "partner_b": 50.0},
                    "categories": [],
                }
            )

    def test_infinity_share_rejected(self):
        with pytest.raises(AccountingValidationError, match="finite"):
            normalize_split_config(
                {
                    "enabled": True,
                    "shares": {"partner_a": float("inf"), "partner_b": 50.0},
                    "categories": [],
                }
            )

    def test_negative_infinity_share_rejected(self):
        with pytest.raises(AccountingValidationError, match="finite"):
            normalize_split_config(
                {
                    "enabled": True,
                    "shares": {"partner_a": float("-inf"), "partner_b": 50.0},
                    "categories": [],
                }
            )

    def test_missing_share_key_rejected(self):
        with pytest.raises(AccountingValidationError, match="partner_a and partner_b"):
            normalize_split_config(
                {"enabled": True, "shares": {"partner_a": 100.0}, "categories": []}
            )

    def test_not_an_object_rejected(self):
        with pytest.raises(AccountingValidationError):
            normalize_split_config([1, 2, 3])


class TestLoadSplitConfig:
    def test_missing_file_returns_none(self, tmp_path):
        assert load_split_config(tmp_path / "nope.json") is None

    def test_reads_and_normalizes_categories_file(self, tmp_path):
        path = tmp_path / "split_config.json"
        path.write_text(
            json.dumps(
                {
                    "enabled": True,
                    "shares": {"partner_a": 55.0, "partner_b": 45.0},
                    "categories": ["c1"],
                }
            ),
            encoding="utf-8",
        )
        assert load_split_config(path) == {
            "shares": {"partner_a": 55.0, "partner_b": 45.0},
            "categories": ["c1"],
        }

    def test_reads_and_translates_legacy_sections_file(self, tmp_path):
        path = tmp_path / "split_config.json"
        path.write_text(
            json.dumps(
                {
                    "enabled": True,
                    "shares": {"partner_a": 50.0, "partner_b": 50.0},
                    "sections": ["trips"],
                }
            ),
            encoding="utf-8",
        )
        result = load_split_config(
            path, category_parents=None, detailed_section_mapping=MAPPING
        )
        assert result["categories"] == ["c4"]

    def test_unknown_category_id_raises_when_category_parents_given(self, tmp_path):
        path = tmp_path / "split_config.json"
        path.write_text(
            json.dumps(
                {
                    "enabled": True,
                    "shares": {"partner_a": 50.0, "partner_b": 50.0},
                    "categories": ["does-not-exist"],
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(AccountingValidationError, match="unknown category ID"):
            load_split_config(path, category_parents=CATEGORY_PARENTS)

    def test_disabled_file_returns_none(self, tmp_path):
        path = tmp_path / "split_config.json"
        path.write_text(json.dumps({"enabled": False}), encoding="utf-8")
        assert load_split_config(path) is None

    def test_corrupt_json_raises(self, tmp_path):
        path = tmp_path / "split_config.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(AccountingValidationError, match="unreadable"):
            load_split_config(path)
