"""Synthetic history contracts and source trust."""

import pytest
from pydantic import ValidationError
from copy import deepcopy
from datetime import date, datetime

from budget_api.models import bills

SCOPE = "cc-spend-v1:" + "a" * 64


def complete(**changes):
    value = dict(status="complete", reason=None, scope_key=SCOPE,
                 categories={"910001": {"title": "Category A", "amount": "132.001"}},
                 uncategorized_amount="0")
    return value | changes


def history_model():
    assert hasattr(bills, "CCSpendHistory"), "schema-6 history contract missing"
    return bills.CCSpendHistory


def test_history_contract_roundtrip_and_legacy_default():
    model = history_model()
    assert model.model_validate(complete()).model_dump() == complete()
    assert bills.PartnerBills.model_fields["cc_spend_history"].default is None
    assert bills.BillsSnapshot.model_fields["schema_version"].default == 7
    for value in [
        complete(status="partial", reason="open_month", categories=None,
                 uncategorized_amount=None),
        complete(status="unavailable", reason="missing_source_context",
                 scope_key=None, categories=None, uncategorized_amount=None),
        complete(categories={}),
    ]:
        assert model.model_validate(value).model_dump() == value


@pytest.mark.parametrize("amount", [0, True, None, -1, "-1", "NaN", "Infinity",
                                     "1e2", "01", "1.0", "-0", "+1", " 1"])
def test_strict_stored_money(amount):
    with pytest.raises(ValidationError):
        history_model().model_validate(complete(uncategorized_amount=amount))


@pytest.mark.parametrize("changes", [
    {"categories": None}, {"scope_key": "bad"}, {"reason": "open_month"},
    {"status": "partial"}, {"status": "unavailable"}, {"uncategorized_amount": None},
    {"categories": {"-1": {"title": "", "amount": "0"}}},
    {"categories": {"01": {"title": "", "amount": "0"}}},
    {"categories": {"1": {"title": 123, "amount": "0"}}},
])
def test_history_state_invariants(changes):
    with pytest.raises(ValidationError):
        history_model().model_validate(complete(**changes))


def test_required_history_members():
    for key in complete():
        value = complete()
        del value[key]
        with pytest.raises(ValidationError):
            history_model().model_validate(value)


def source():
    mappings = {
        "partners": {"partner_a": {"label": "Partner A"}, "partner_b": {"label": "Partner B"}},
        "accounts": {
            "1100001": {"partner_id": "partner_a", "type": "checking", "excluded": False},
            "1100002": {"partner_id": "partner_b", "type": "checking", "excluded": False},
            "1100003": {"partner_id": "partner_a", "type": "cc", "excluded": False},
            "1100004": {"partner_id": "partner_b", "type": "cc", "excluded": False},
            "1100005": {"partner_id": "partner_a", "type": "cc", "excluded": True},
        }}
    categories = [
        {"id": 910001, "title": "Same", "children": [{"id": 910002, "title": "Same"}]},
        {"id": 910003, "title": "Transfer", "is_transfer": True},
        {"id": 910004, "title": "CC Payment"},
        {"id": 910005, "title": "Excluded"},
    ]
    return dict(month="2026-07", transactions=[], account_mappings=mappings,
                category_roles={"910005": "exclude"}, category_catalog=categories,
                account_catalog=[{"id": int(i)} for i in mappings["accounts"]],
                partner_id="partner_a", partner_account_ids={"1100001", "1100003", "1100005"},
                cc_payment_category_id=910004)


def txn(amount=-100, category=910001, account=1100003, **changes):
    return dict(status="posted", amount=amount, date="2026-07-12",
                transaction_account={"id": account},
                category=None if category is None else {"id": category, "title": "Embedded",
                                                        "is_transfer": category == 910003}) | changes


def aggregate(value):
    from budget_api.services import bills_derivations
    assert hasattr(bills_derivations, "compute_cc_spend_history"), "strict aggregation missing"
    return bills_derivations.compute_cc_spend_history(**value)


def test_shared_filters_ids_labels_uncategorized_and_decimals():
    value = source()
    value["transactions"] = [txn(-0.1), txn(-0.2), txn(-9, 910002), txn(-5, None),
                             txn(10), txn(-999, status="pending"), txn(-999, 910003),
                             txn(-999, 910004), txn(-999, 910005),
                             txn(-999, account=1100001), txn(-999, account=1100004),
                             txn(-999, account=1100005)]
    history = aggregate(value)
    assert history.categories["910001"].amount == "0.3"
    assert history.categories["910002"].amount == "9"
    assert [x.title for x in history.categories.values()] == ["Same", "Same"]
    assert history.uncategorized_amount == "5"
    assert set(history.categories) == {"910001", "910002"}
    other = aggregate(value | {"partner_id": "partner_b", "partner_account_ids": {"1100002", "1100004"}})
    assert other.categories["910001"].amount == "999"
    from budget_api.services.bills_derivations import compute_cc_usage_by_category
    legacy = compute_cc_usage_by_category("Partner A", value["transactions"],
        value["account_mappings"], value["partner_account_ids"], 910004, {910005})
    assert sum(legacy.values()) == pytest.approx(14.3)
    assert aggregate(source()).categories == {}
    assert compute_cc_usage_by_category("Partner A", [], value["account_mappings"]) is None


def test_scope_population_not_labels_or_monthly_presence():
    value = source()
    expected = aggregate(value).scope_key
    changed = deepcopy(value)
    changed["account_mappings"]["partners"]["partner_a"]["label"] = "Rename"
    changed["account_mappings"]["accounts"] = dict(reversed(list(changed["account_mappings"]["accounts"].items())))
    changed["category_catalog"][0]["title"] = "Renamed"
    changed["category_catalog"].append({"id": 910006, "title": "Unrelated"})
    changed["category_roles"]["910001"] = "spend"
    changed["transactions"] = [txn()]
    assert aggregate(changed).scope_key == expected
    for mutation in ["excluded", "payment", "transfer", "exclude_role", "owner"]:
        changed = deepcopy(value)
        if mutation == "excluded":
            changed["account_mappings"]["accounts"]["1100005"]["excluded"] = False
        elif mutation == "payment":
            changed["cc_payment_category_id"] = None
        elif mutation == "transfer":
            changed["category_catalog"][0]["is_transfer"] = True
        elif mutation == "exclude_role":
            changed["category_roles"]["910001"] = "exclude"
        else:
            changed["account_mappings"]["accounts"]["1100003"]["partner_id"] = "partner_b"
            changed["partner_account_ids"].remove("1100003")
        assert aggregate(changed).scope_key != expected


@pytest.mark.parametrize("changes", [
    {"amount": True}, {"amount": "1"}, {"amount": float("nan")}, {"amount": float("inf")},
    {"date": "2026-06-30"}, {"date": "2026-07-99"}, {"status": None},
    {"category": {"id": True}}, {"category": {"id": "bad"}},
    {"category": {"id": 1.5}}, {"category": []},
    {"category": {"id": 910003, "is_transfer": False}},
    {"category": {"id": 910001, "is_transfer": "false"}},
    {"transaction_account": {"id": 9999999}},
    {"transaction_account": None},
])
def test_invalid_original_transactions_never_disappear_in_filters(changes):
    value = source()
    value["transactions"] = [txn(status="pending") | changes]
    with pytest.raises(ValueError):
        aggregate(value)


@pytest.mark.parametrize("key,value", [
    ("transactions", None), ("transactions", {}), ("transactions", [None]),
    ("partner_account_ids", None), ("partner_account_ids", {"1100004"}),
    ("category_catalog", None), ("account_catalog", []),
    ("category_roles", {"910001": False}),
])
def test_invalid_context_is_not_empty_observation(key, value):
    with pytest.raises(ValueError):
        aggregate(source() | {key: value})


def role_source(**roles):
    value = source()
    value["transactions"] = [txn(-12.5), txn(-4, None)]
    baseline = aggregate(deepcopy(value))
    value["category_roles"].update(roles)
    return value, baseline


@pytest.mark.parametrize("role", ["spend", "personal_spend", "income", "savings", "investment"])
def test_synthetic_uncategorized_role_key_keeps_history_complete(role):
    # Found on real data: reports pipeline stores a role for synthetic "uncategorized".
    value, baseline = role_source(uncategorized=role)
    history = aggregate(value)
    assert history.status == "complete"
    assert history == baseline


# Numeric-looking keys that are not canonical IDs: padding, sign, separators,
# a decimal point and non-ASCII digits (Arabic-Indic one and two).
NON_CANONICAL_ID_FORMS = [" 12", "12 ", "+12", "1_2", "1.0", "\u0661\u0662"]


@pytest.mark.parametrize("key", ["legacy title", "0", "01", "-1", "", *NON_CANONICAL_ID_FORMS])
def test_other_non_id_role_keys_without_exclude_never_shape_scope(key):
    value, baseline = role_source(**{key: "spend"})
    assert aggregate(value) == baseline


@pytest.mark.parametrize(
    "key", ["uncategorized", "legacy title", "0", "01", "-1", *NON_CANONICAL_ID_FORMS]
)
def test_non_id_exclude_role_key_is_still_invalid(key):
    value, _ = role_source(**{key: "exclude"})
    with pytest.raises(ValueError, match="invalid source identity"):
        aggregate(value)


@pytest.mark.parametrize("role", [None, False, 1, "bogus", "Spend"])
def test_non_id_role_key_still_needs_known_role(role):
    value, _ = role_source(uncategorized=role)
    with pytest.raises(ValueError, match="invalid category role"):
        aggregate(value)


def test_deterministic_embedded_label_fallback():
    value = source()
    value["transactions"] = [txn(category=910006, category_unused=True)]
    value["transactions"][0]["category"]["title"] = "Z"
    value["transactions"].append(deepcopy(value["transactions"][0]))
    value["transactions"][1]["category"]["title"] = "A"
    assert aggregate(value).categories["910006"].title == "A"
    value["transactions"].reverse()
    assert aggregate(value).categories["910006"].title == "A"


def build_source(value, acquisition=None):
    from budget_api.services.bills_builder import build_bills_snapshot
    return build_bills_snapshot(month=value["month"], events=[], transactions=value["transactions"],
        account_mappings=value["account_mappings"], category_roles=value["category_roles"],
        category_catalog=value["category_catalog"], account_catalog=value["account_catalog"],
        prior_events=[], prior_transactions=[], live_combined=None, deltas_per_month=None,
        today=date(2026, 8, 2), acquisition=acquisition)


def acquisition(value, started_at=datetime(2026, 8, 1)):
    from budget_api.services import bills_derivations
    assert hasattr(bills_derivations, "MonthAcquisition"), "acquisition context missing"
    return bills_derivations.MonthAcquisition(value["month"], "2026-07-01", "2026-07-31",
                                             started_at, value["transactions"])


def test_builder_additive_and_source_timestamp_survives_rollover():
    value = source()
    value["transactions"] = [txn()]
    before = build_source(value)
    after = build_source(value, acquisition(value))
    assert after["schema_version"] == 7
    assert after["partners"][0]["cc_spend_history"]["status"] == "complete"
    for old, new in zip(before["partners"], after["partners"]):
        assert old["cc_spend_history"]["reason"] == "missing_source_context"
        assert {k: v for k, v in old.items() if k != "cc_spend_history"} == {
            k: v for k, v in new.items() if k != "cc_spend_history"}
    partial = build_source(value, acquisition(value, datetime(2026, 7, 31, 23, 59)))
    assert partial["is_past"]
    assert partial["partners"][0]["cc_spend_history"]["status"] == "partial"
    future = build_source(value, acquisition(value, datetime(2026, 6, 30)))
    assert future["partners"][0]["cc_spend_history"]["reason"] == "future_month"


def test_builder_keeps_history_complete_with_synthetic_uncategorized_role():
    value, _ = role_source(uncategorized="spend")
    built = build_source(value, acquisition(value))
    assert [p["cc_spend_history"]["status"] for p in built["partners"]] == ["complete", "complete"]
    assert built["partners"][0]["cc_spend_history"]["categories"]["910001"]["amount"] == "12.5"
    assert built["partners"][0]["cc_spend_history"]["uncategorized_amount"] == "4"


def test_builder_rejects_mismatched_source_context():
    value = source()
    context = acquisition(value)
    value["transactions"] = []
    assert build_source(value, context)["partners"][0]["cc_spend_history"]["reason"] == "invalid_source"
    value["account_mappings"]["accounts"]["1100003"]["excluded"] = True
    assert build_source(value, acquisition(value))["partners"][0]["cc_spend_history"]["reason"] == "no_cc_accounts"


def test_builder_invalid_source_precedes_calendar_and_empty():
    from dataclasses import replace
    value = source()
    context = acquisition(value)
    assert build_source(value, replace(context, start_date="2026-07-02"))["partners"][0]["cc_spend_history"]["reason"] == "invalid_source"
    value["transactions"] = [txn(status="pending", date="2026-06-01")]
    result = build_source(value, acquisition(value, datetime(2026, 7, 1)))
    assert result["partners"][0]["cc_spend_history"]["reason"] == "invalid_source"


def test_acquisition_missing_chain_input_is_not_complete():
    from budget_api.services.bills_builder import build_bills_chain
    value = source()
    kwargs = {k: value[k] for k in ["account_mappings", "category_roles", "category_catalog", "account_catalog"]}
    warnings = []
    result = build_bills_chain(["2026-07"], {"2026-07": []}, {}, **kwargs, warnings=warnings,
                               acquisitions={"2026-07": acquisition(value)}, today=date(2026, 8, 2))
    assert result == {}
    assert any("month skipped" in w for w in warnings)


def test_unknown_catalog_ownership_cannot_certify_empty():
    value = source()
    value["account_catalog"].append({"id": 1100099, "type": "credit_card"})
    with pytest.raises(ValueError):
        aggregate(value)


@pytest.mark.parametrize("in_catalog", [True, False], ids=["present", "removed"])
@pytest.mark.parametrize("owner,kind", [
    (None, None), (None, "cc"), ("partner_a", None), ("partner_a", "cc"),
])
def test_excluded_optional_binding_does_not_invalidate_history(in_catalog, owner, kind):
    value = source()
    value["transactions"] = [txn()]
    before = aggregate(value)
    before_build = build_source(value, acquisition(value))
    value["account_mappings"]["accounts"]["1100099"] = {
        "partner_id": owner, "type": kind, "excluded": True,
    }
    if owner == "partner_a":
        value["partner_account_ids"].add("1100099")
    if in_catalog:
        value["account_catalog"].append({"id": 1100099})
        value["transactions"].append(txn(-999, account=1100099))
    after = aggregate(value)
    assert after.status == "complete"
    assert after.categories == before.categories
    assert after.uncategorized_amount == before.uncategorized_amount
    known_owned_cc = owner == "partner_a" and kind == "cc"
    assert (after.scope_key != before.scope_key) == known_owned_cc
    after_build = build_source(value, acquisition(value))
    for old, new in zip(before_build["partners"], after_build["partners"]):
        history = new["cc_spend_history"]
        assert history["status"] == "complete"
        assert history["categories"] == old["cc_spend_history"]["categories"]
        assert (history["scope_key"] != old["cc_spend_history"]["scope_key"]) == (
            known_owned_cc and new["partner_id"] == "partner_a"
        )


@pytest.mark.parametrize("binding", [
    {}, {"partner_id": None, "type": None},
    {"partner_id": None, "type": "cc"}, {"partner_id": "partner_a", "type": None},
])
def test_included_unassigned_mapping_still_fails_closed(binding):
    value = source()
    value["account_catalog"].append({"id": 1100099})
    value["account_mappings"]["accounts"]["1100099"] = binding | {"excluded": False}
    if binding.get("partner_id") == "partner_a":
        value["partner_account_ids"].add("1100099")
    with pytest.raises(ValueError, match="ownership"):
        aggregate(value)
    snapshot = build_source(value, acquisition(value))
    assert all(p["cc_spend_history"]["reason"] == "invalid_source" for p in snapshot["partners"])


@pytest.mark.parametrize("changes", [
    {"excluded": "true"}, {"partner_id": "unknown"}, {"type": "unknown"},
])
def test_excluded_mapping_still_validates_explicit_values(changes):
    value = source()
    value["account_mappings"]["accounts"]["1100099"] = {
        "partner_id": None, "type": None, "excluded": True,
    } | changes
    with pytest.raises(ValueError):
        aggregate(value)


def test_large_exact_aggregate_and_transaction_order_invariance():
    from decimal import Decimal
    value = source()
    value["transactions"] = [txn(Decimal("-10000000000000000000000000000.1")), txn(-0.2)]
    expected = aggregate(value)
    assert expected.categories["910001"].amount == "10000000000000000000000000000.3"
    value["transactions"].reverse()
    assert aggregate(value) == expected
