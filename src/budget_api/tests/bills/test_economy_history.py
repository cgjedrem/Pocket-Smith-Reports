"""Synthetic report parity, provenance and signed evidence contracts."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from budget_api.models.bills import EconomySpendHistory
from budget_api.services import report_builder
from budget_api.services.economy_history import EconomyContext, build_economy_history
from budget_api.tests.bills.test_cc_spend_history import acquisition, source, txn
from v4_pipeline.accounting import detailed_net_section, detailed_personal_sections, detailed_spending_groups
from v4_pipeline.data_loader import prepare_transactions


def economy_source():
    value = source()
    sections = {
        "910001": "common", "910010": "home", "910011": "personal_partner_a",
        "910012": "personal_partner_b", "910013": "trips", "910014": "savings",
        "910015": "income_salary", "910004": "cc_payments", "910005": "excluded",
        "uncategorized": "common",
    }
    inputs = report_builder.AccountingInputs(
        account_owners={aid: entry["partner_id"] for aid, entry in value["account_mappings"]["accounts"].items()},
        detailed_section_mapping={"category_sections": sections, "account_roles": {}},
        category_roles=None,
        category_parents={cid: None for cid in sections} | {"910002": "910001"},
        split_config=None,
        category_transfer_flags={cid: cid == "910003" for cid in sections} | {
            "910002": False,
        },
    )
    return value, EconomyContext(
        inputs, frozenset({"1100005"}),
        {"partner_a": "Partner A", "partner_b": "Partner B"},
    )


def build(value, context, acquired=None):
    return build_economy_history(
        value["month"], value["transactions"], value["account_mappings"],
        acquisition(value) if acquired is None else acquired, context,
    )


def test_exact_detailed_report_category_and_total_parity():
    value, context = economy_source()
    value["transactions"] = [
        txn(-0.1), txn(-0.2), txn(0.1), txn(-10, 910002),
        txn(-21, 910010), txn(3, 910010), txn(-4, 910010, is_transfer=True),
        # Personal category, not payer/card ownership, controls placement.
        txn(-7, 910011, account=1100004), txn(2, 910011, account=1100003),
        txn(-6, 910012, account=1100001), txn(9, 910012, account=1100004),
        # Common transfer excluded; home transfer above intentionally retained.
        txn(-999, is_transfer=True), txn(-999, 910013), txn(-999, 910014),
        txn(999, 910015), txn(-999, 910004), txn(999, 910004),
        txn(-999, 910005), txn(-999, account=1100005), txn(-4, None),
        # Reimbursements net to zero rather than sum account ownership.
        txn(-5, 910011, account=1100003), txn(5, 910011, account=1100004),
    ]
    history = build(value, context)
    assert history.status == "complete"
    shared, a, b = history.groups
    assert shared.categories["910001"].amount == "0.2"
    assert shared.categories["910002"].amount == "10"
    assert shared.categories["910010"].amount == "22"
    assert shared.uncategorized_amount == "4"
    assert a.categories["910011"].amount == "5"
    assert b.categories["910012"].amount == "-3"
    contract = report_builder.build_contract(
        prepare_transactions(value["month"], deepcopy(value["transactions"]), set(context.excluded_account_ids)),
        context.inputs,
    )
    records, mapping = contract["normalized_transactions"], contract["detailed_section_mapping"]
    expected = detailed_spending_groups(records, mapping)
    for group in history.groups:
        for category in expected[group.group_id]:
            net = sum(Decimal(str(-r["amount"])) for r in category["records"])
            actual = (group.uncategorized_amount if category["category_id"] == "uncategorized"
                      else group.categories[category["category_id"]].amount)
            assert Decimal(actual) == net
    shared_total = sum(Decimal(c.amount) for c in shared.categories.values()) + Decimal(shared.uncategorized_amount)
    report_shared = sum(detailed_net_section(records, section, mapping)["total"] for section in ("home", "common"))
    assert float(shared_total) == pytest.approx(report_shared)
    personal = detailed_personal_sections(records, mapping)
    for group in (a, b):
        assert float(sum(Decimal(c.amount) for c in group.categories.values())) == personal[group.group_id]["subtotal"]
    ids = [cid for g in history.groups for cid in g.categories]
    assert len(ids) == len(set(ids)) == 5


def test_scope_is_label_independent_and_covers_all_classification_policy():
    value, context = economy_source()
    original = build(value, context).scope_key
    value["account_mappings"]["partners"]["partner_a"]["label"] = "Renamed"
    assert build(value, context).scope_key == original
    labels_changed = replace(
        context, partner_labels={"partner_a": "Ada Example", "partner_b": "Ben Example"}
    )
    assert build(value, labels_changed).scope_key == original
    for field, change in (
        ("category_parents", {"910002": "910010"}),
        ("detailed_section_mapping", {"category_sections": {"910001": "home"}, "account_roles": {}}),
        ("detailed_section_mapping", {"category_sections": context.inputs.detailed_section_mapping["category_sections"],
                                      "account_roles": {"1100003": "savings_partner_a"}}),
        ("category_roles", {"910001": "spend"}),
    ):
        changed = replace(context, inputs=replace(context.inputs, **{field: change}))
        result = build(value, changed)
        assert result.status == "complete" and result.scope_key != original
    value["account_mappings"]["accounts"]["1100003"]["partner_id"] = "partner_b"
    changed = replace(context, inputs=replace(context.inputs, account_owners=(
        context.inputs.account_owners | {"1100003": "partner_b"})))
    assert build(value, changed).status == "complete"
    assert build(value, changed).scope_key != original
    value["account_mappings"]["accounts"]["1100003"]["partner_id"] = "partner_a"
    value["account_mappings"]["accounts"]["1100005"]["excluded"] = False
    assert build(value, replace(context, excluded_account_ids=frozenset())).scope_key != original
    value["account_mappings"]["accounts"]["1100005"]["excluded"] = True
    value["account_mappings"]["partners"] = {"other_a": {"label": "Partner A"}, "other_b": {"label": "Partner B"}}
    for entry in value["account_mappings"]["accounts"].values():
        entry["partner_id"] = "other_a" if entry["partner_id"] == "partner_a" else "other_b"
    assert build(value, context).scope_key != original


def test_parent_remap_changes_population_not_card_owner():
    value, context = economy_source()
    value["transactions"] = [txn(-10, 910002, account=1100004)]
    assert build(value, context).groups[0].categories["910002"].amount == "10"
    changed = deepcopy(context.inputs.detailed_section_mapping)
    changed["category_sections"]["910001"] = "personal_partner_a"
    moved = build(value, replace(context, inputs=replace(context.inputs, detailed_section_mapping=changed)))
    assert moved.groups[0].categories == {}
    assert moved.groups[1].categories["910002"].amount == "10"


def test_transfer_policy_changes_scope_and_embedded_mismatch_is_unavailable():
    value, context = economy_source()
    value["transactions"] = [txn(-10, 910001)]
    before = build(value, context)
    assert before.status == "complete"
    assert before.groups[0].categories["910001"].amount == "10"

    value["transactions"][0]["category"]["is_transfer"] = True
    flags = context.inputs.category_transfer_flags | {"910001": True}
    changed = replace(context, inputs=replace(context.inputs, category_transfer_flags=flags))
    after = build(value, changed)
    assert after.status == "complete"
    assert after.scope_key != before.scope_key
    assert after.groups[0].categories == {}

    value["transactions"][0]["category"]["is_transfer"] = False
    assert build(value, changed).reason == "invalid_source"


@pytest.mark.parametrize("category", [[], "uncategorized", 42, False])
def test_non_object_non_null_category_is_rejected_before_uncategorized_fallback(category):
    value, context = economy_source()
    malformed = txn(-4)
    malformed["category"] = category
    value["transactions"] = [malformed]
    result = build(value, context)
    assert result.status == "unavailable"
    assert result.reason == "invalid_source"
    assert result.groups is None


def test_category_without_catalog_transfer_policy_is_unavailable():
    value, context = economy_source()
    value["transactions"] = [txn(-10, 910001)]
    flags = dict(context.inputs.category_transfer_flags)
    del flags["910001"]
    context = replace(context, inputs=replace(context.inputs, category_transfer_flags=flags))
    result = build(value, context)
    assert result.status == "unavailable"
    assert result.reason == "invalid_source"


def test_savings_account_role_does_not_override_detailed_category_routing():
    value, context = economy_source()
    value["transactions"] = [txn(-10)]
    mapping = deepcopy(context.inputs.detailed_section_mapping)
    mapping["account_roles"]["1100003"] = "savings_partner_a"
    history = build(value, replace(context, inputs=replace(context.inputs, detailed_section_mapping=mapping)))
    assert history.status == "complete"
    assert history.groups[0].categories["910001"].amount == "10"


@pytest.mark.parametrize("invalid", ["exclusion_type", "owners", "parents", "sections", "exclusions"])
def test_invalid_or_missing_config_with_empty_fetch_never_certifies_zero(invalid):
    value, context = economy_source()
    if invalid == "exclusion_type":
        value["account_mappings"]["accounts"]["1100001"]["excluded"] = "false"
    elif invalid == "owners":
        context = replace(context, inputs=replace(context.inputs, account_owners={}))
    elif invalid == "parents":
        context = replace(context, inputs=replace(context.inputs, category_parents={}))
    elif invalid == "sections":
        context = replace(context, inputs=replace(context.inputs, detailed_section_mapping={
            "category_sections": {}, "account_roles": {},
        }))
    else:
        context = replace(context, excluded_account_ids=frozenset())
    result = build(value, context)
    assert result.status == "unavailable" and result.groups is None


@pytest.mark.parametrize("transactions", [
    [None], [txn(status="pending")], [txn(status="other")], [txn(status=None)],
    [txn(amount=True)], [txn(amount=float("nan"))], [txn(date="2026-07-99")],
    [txn(date="2026-08-01")], [txn(account=9999999)], [txn(category=9999999)],
    [txn(is_transfer="true")],
])
def test_unknown_invalid_source_never_becomes_complete_empty(transactions):
    value, context = economy_source()
    value["transactions"] = transactions
    result = build(value, context)
    assert result.status == "unavailable"
    assert result.reason == "invalid_source"
    assert result.groups is None


def test_acquisition_context_closure_and_empty_complete():
    value, context = economy_source()
    assert build(value, context).status == "complete"
    assert all(not g.categories for g in build(value, context).groups)
    assert build(value, None).reason == "missing_source_context"
    no_context = build_economy_history(value["month"], [], value["account_mappings"], None, context)
    assert no_context.reason == "missing_source_context"
    stale = acquisition(value)
    value["transactions"] = []
    assert build(value, context, stale).reason == "invalid_source"
    partial = build(value, context, acquisition(value, datetime(2026, 7, 31, 23, 59)))
    assert partial.status == "partial" and partial.groups is None
    assert build(value, context, acquisition(value, datetime(2026, 6, 30))).reason == "future_month"
    assert build(value, replace(context, inputs=replace(context.inputs, category_parents=None))).reason == "missing_source_context"
    invalid = replace(context, inputs=replace(context.inputs, detailed_section_mapping={
        "category_sections": {"910001": "unknown"}, "account_roles": {},
    }))
    assert build(value, invalid).reason == "invalid_source"
    value["account_mappings"]["partners"]["third"] = {"label": "Third"}
    assert build(value, context).reason == "invalid_source"


def test_signed_history_model_rejects_duplicate_categories_and_group_identities():
    value, context = economy_source()
    good = build(value, context).model_dump()
    for mutate in (
        lambda x: x["groups"].pop(),
        lambda x: x["groups"][1].update(partner_id="partner_b"),
        lambda x: x["groups"][0].update(partner_id="partner_a"),
        lambda x: x["groups"][1].update(partner_slot="b"),
        lambda x: x["groups"][0].update(categories={"910001": {"title": "", "amount": "-0"}}),
    ):
        bad = deepcopy(good)
        mutate(bad)
        with pytest.raises(ValidationError):
            EconomySpendHistory.model_validate(bad)
    good["groups"][0]["categories"]["910001"] = {"title": "Shared", "amount": "-1"}
    good["groups"][1]["categories"]["910001"] = {"title": "Personal", "amount": "1"}
    with pytest.raises(ValidationError):
        EconomySpendHistory.model_validate(good)
