"""Exact synthetic detector examples. No storage or clock dependency."""

import importlib
from copy import deepcopy
from decimal import Decimal

import pytest
from pydantic import ValidationError

from budget_api.tests.bills.test_cc_spend_history import complete

MONTHS = ["2026-07", "2026-08", "2026-09", "2026-10"]


def response_model():
    name = "budget_api.models.lifestyle_creep"
    assert importlib.util.find_spec(name), "response contract missing"
    return importlib.import_module(name).LifestyleCreepResponse


def evaluate(series, threshold="20", months=None):
    name = "budget_api.services.lifestyle_creep"
    assert importlib.util.find_spec(name), "pure evaluation missing"
    from budget_api.models.bills import CCSpendHistory
    service = importlib.import_module(name)
    if months is None:
        months = [f"2026-{i:02d}" for i in range(1, len(series) + 1)]
    histories = [CCSpendHistory.model_validate(complete(
        categories={} if value is None else {
            "910001": {"title": "Category A", "amount": str(value)},
        },
        uncategorized_amount=str(i),
    )) for i, value in enumerate(series)]
    return service.evaluate_partner(
        "partner_a", "a", "Partner A", months, histories, Decimal(threshold),
    )


@pytest.mark.parametrize("series,above,reason", [
    ([100, 100, 100, 130], True, None),
    ([100, 100, 100, 120], False, None),
    ([100, 100, 100, 120.01], True, None),
    ([0, 100, 100, 130], True, None),
    ([0, 0, 100, 200], False, "low_frequency"),
    ([0, 0, 0, 200], False, "zero_baseline"),
    ([100, 0, 100, 200], True, None),
    ([100, 100, 100, 0], False, None),
    ([0, 0, 0, 0], False, "zero_baseline"),
])
def test_one_target_against_reference_average(series, above, reason):
    category = evaluate(series).categories[0]
    comparison = category.comparison
    assert category.is_above_threshold is above
    assert category.suppression_reason == reason
    assert comparison.month == "2026-04"
    assert comparison.baseline_months == ["2026-01", "2026-02", "2026-03"]
    assert len(category.samples) == 4


def test_average_comparison_and_compatibility_month_over_month():
    cat = evaluate([100, 200, 300, 240]).categories[0]
    assert cat.comparison.baseline_amount == "200"
    assert cat.comparison.spending_amount == "240"
    assert cat.comparison.change_amount == "40"
    assert cat.comparison.growth_percent == "20"
    assert not cat.is_above_threshold
    assert cat.latest_month_over_month_percent == "-20"

    cat = evaluate([100, 200, 300, "240.001"]).categories[0]
    assert cat.is_above_threshold
    assert cat.comparison.growth_percent == "20.0005"


def test_thresholds_use_strict_exact_decimal_arithmetic():
    for threshold, expected in [("1", True), ("20", False), ("20.0001", False), ("100", False)]:
        assert evaluate([100, 200, 300, 240], threshold).categories[0].is_above_threshold is expected
    cat = evaluate(
        ["10000000000000000000000000000000000000000"] * 3 +
        ["12000000000000000000000000000000000000001"],
    ).categories[0]
    assert cat.is_above_threshold


def test_mom_is_null_unless_reference_end_precedes_target():
    months = ["2026-01", "2026-02", "2026-03", "2026-05"]
    cat = evaluate([100, 100, 100, 150], months=months).categories[0]
    assert cat.latest_month_over_month_percent is None
    adjacent = evaluate(
        [100, 100, 100, 150],
        months=["2026-02", "2026-03", "2026-04", "2026-05"],
    ).categories[0]
    assert adjacent.latest_month_over_month_percent == "50"


def test_precision_and_repeating_average_explanations():
    cat = evaluate([1, 1, 2, 4]).categories[0]
    assert cat.comparison.baseline_amount == "1.333333333333333333333333333"
    assert cat.comparison.change_amount == "2.666666666666666666666666667"
    assert cat.comparison.growth_percent == "200"
    precise = evaluate([100, 100, 100, "120.00000000000000000000000000000000001"]).categories[0]
    assert precise.is_above_threshold


def test_category_union_labels_and_uncategorized_samples():
    from budget_api.models.bills import CCSpendHistory
    from budget_api.services.lifestyle_creep import evaluate_partner

    months = ["2026-01", "2026-02", "2026-03", "2026-04"]
    histories = []
    for i in range(4):
        categories = {
            "910002": {"title": "Old" if i < 2 else "Renamed", "amount": "100"},
            "910001": {"title": "Same", "amount": "0"},
        }
        if i == 0:
            categories["910003"] = {"title": "Disappeared", "amount": "100"}
        if i == 3:
            categories["910004"] = {"title": "Appeared", "amount": "100"}
        histories.append(CCSpendHistory.model_validate(complete(
            categories=categories, uncategorized_amount=str(i),
        )))
    partner = evaluate_partner("partner_a", "a", "Partner A", months, histories, Decimal(20))
    assert [category.category_id for category in partner.categories] == [
        "910001", "910002", "910003", "910004",
    ]
    assert partner.categories[1].category_title == "Renamed"
    assert [sample.amount for sample in partner.categories[2].samples] == ["100", "0", "0", "0"]
    assert partner.categories[3].suppression_reason == "zero_baseline"
    assert [sample.amount for sample in partner.uncategorized_samples] == ["0", "1", "2", "3"]
    assert type(partner).model_validate_json(partner.model_dump_json()) == partner


def make_response(months, partner=None):
    return {
        "month": months[-1],
        "reference_start": months[0],
        "reference_end": months[-2],
        "window_months": months,
        "evaluation_months": [months[-1]],
        "baseline_months": len(months) - 1,
        "threshold_percent": "20",
        "status": "ready",
        "issues": [],
        "partners": [partner] if partner else [{
            "partner_id": "partner_a",
            "partner_slot": "a",
            "partner": "Partner A",
            "status": "ready",
            "categories": [],
            "uncategorized_samples": [{"month": month, "amount": "0"} for month in months],
        }],
    }


def test_response_contract_and_exact_target_reference_coverage():
    months = ["2026-01", "2026-02", "2026-03", "2026-04"]
    value = make_response(months)
    assert response_model().model_validate(value).model_dump(mode="json") == value
    invalids = [
        value | {"window_months": months[:-1]},
        value | {"evaluation_months": months[:-1]},
        value | {"baseline_months": 1},
        value | {"reference_end": "2026-04"},
        value | {"reference_start": "2026-02"},
        value | {"month": "2026-05"},
    ]
    for invalid in invalids:
        with pytest.raises(ValidationError):
            response_model().model_validate(invalid)


def test_response_category_shape_and_suppression_consistency():
    months = ["2026-01", "2026-02", "2026-03", "2026-04"]
    partner = evaluate([0, 0, 0, 200], months=months).model_dump(mode="json")
    value = make_response(months, partner)
    model = response_model()
    model.model_validate(value)
    for field in ("samples", "comparison"):
        invalid = deepcopy(value)
        if field == "samples":
            invalid["partners"][0]["categories"][0][field].pop()
        else:
            invalid["partners"][0]["categories"][0][field]["baseline_months"].pop()
        with pytest.raises(ValidationError):
            model.model_validate(invalid)
    invalid = deepcopy(value)
    invalid["partners"][0]["categories"][0]["comparison"]["month"] = "2026-03"
    with pytest.raises(ValidationError):
        model.model_validate(invalid)
    invalid = deepcopy(value)
    invalid["partners"][0]["categories"][0]["is_above_threshold"] = True
    with pytest.raises(ValidationError):
        model.model_validate(invalid)


@pytest.mark.parametrize("count", [2, 3, 24])
def test_variable_reference_counts_and_baseline_details(count):
    months = [f"{2024 + i // 12:04d}-{i % 12 + 1:02d}" for i in range(count + 1)]
    partner = evaluate([100] * (count + 1), months=months)
    category = partner.categories[0]
    assert [sample.month for sample in category.samples] == months
    assert category.comparison.baseline_months == months[:-1]
    assert category.comparison.baseline_amount == "100"
    assert category.comparison.change_amount == category.comparison.growth_percent == "0"
    assert partner.uncategorized_samples[-1].month == months[-1]
    assert not category.is_above_threshold
    with pytest.raises(ValueError):
        evaluate([100, 100])
    with pytest.raises(ValueError):
        evaluate([100] * 26)
