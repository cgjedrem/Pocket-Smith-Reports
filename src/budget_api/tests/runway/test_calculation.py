from copy import deepcopy
from datetime import datetime, time as day_time, timedelta, timezone
import json
import time

import pytest

from budget_api.tests.runway.synthetic import A, B, CARD, MONTHS, NOW, SAVINGS, complete, transaction


def codes(value):
    return {issue["code"] for issue in value["issues"]}


def test_contract_arithmetic_and_no_source_writes(world):
    world.write()
    before = {p.name: p.read_bytes() for p in world.root.iterdir()}
    result = world.result()
    assert result["candidate_months"] == result["included_months"] == MONTHS
    assert result["included_month_count"] == 3
    a, b = result["owners"]
    assert (a["reserves"], a["average_monthly_spending"], a["runway_months"]) == (90000, 30000, 3)
    assert b["runway_display"] == "0.5"
    assert result["household"]["average_monthly_spending"] == 90000
    assert result["household"]["reserves"] == 120000
    assert result["household"]["runway_months"] == pytest.approx(4 / 3)
    assert result["household"]["runway_display"] == "1.3"
    assert result["household"]["status"] == "qualified"
    assert "source_stale" in codes(result["household"])
    assert before == {p.name: p.read_bytes() for p in world.root.iterdir()}


@pytest.mark.parametrize("missing,count", [([], 3), (["2026-08"], 2), (MONTHS[:2], 1), (MONTHS, 0)])
def test_common_window_never_backfills(world, missing, count):
    world.data["2026-06_ps_raw.json"] = complete("2026-07", [])
    for month in missing:
        world.remove(f"{month}_ps_raw.json")
    result = world.result()
    assert result["included_month_count"] == count
    assert "2026-06" not in result["included_months"]
    if count < 2:
        assert result["household"]["average_monthly_spending"] is None
        assert result["household"]["runway_months"] is None
        assert "insufficient_history" in codes(result["household"])
    if count == 2:
        assert result["household"]["average_monthly_spending"] == 90000
        assert "excluded_months" in codes(result["household"])


@pytest.mark.parametrize("now,expected", [
    (datetime(2027, 1, 1, tzinfo=timezone.utc), ["2026-10", "2026-11", "2026-12"]),
    (datetime(2024, 3, 1, tzinfo=timezone.utc), ["2023-12", "2024-01", "2024-02"]),
    (datetime(2026, 11, 1, tzinfo=timezone.utc), ["2026-08", "2026-09", "2026-10"]),
])
def test_calendar(now, expected, world):
    from budget_api.services.runway import calculate_runway
    world.write()
    assert calculate_runway(now=now).candidate_months == expected


def test_gross_exclusions_dedupe_and_descendants(world):
    mapping = world.data["account_mappings.json"]
    mapping["partners"]["partner_a"]["savings_category_id"] = 2100014
    mapping["accounts"]["1100004"] = {"excluded": True}
    mapping["accounts"]["1100005"] = {"partner_id": "partner_a", "type": "investment"}
    world.data["category_roles.json"] = {"2100001": "savings", "2100002": "investment", "2100003": "exclude"}
    world.data["detailed_section_mapping.json"] = {"category_sections": {"2100004": "cc_payments", "2100005": "excluded", "2100006": "savings"}}
    world.data["category_catalog.json"] = {"categories": [
        {"id": 2100010, "title": "CC PAYMENT one", "children": [{"id": 2100011}]},
        {"id": 2100012, "title": "CC Payment two"},
        {"id": 2100015, "is_transfer": True, "children": [{"id": 2100016}]},
    ]}
    rows = [transaction(1, A, -100), transaction(2, CARD, -200), transaction(3, B, -50)]
    rows += [deepcopy(rows[0]), transaction(4, A, 40), transaction(5, CARD, 60)]
    for index, cat in enumerate([2100001, 2100002, 2100003, 2100004, 2100005, 2100006, 2100011, 2100012, 2100014, 2100016]):
        rows.append(transaction(100 + index, category={"id": cat}))
    rows += [
        transaction(200, is_transfer=True), transaction(201, category={"id": 2100099, "is_transfer": True}),
        transaction(202, SAVINGS), transaction(203, "1100004"), transaction(204, "1100005"),
        transaction(205, status="pending"), transaction(206, amount=100, category={"id": 2100011}),
    ]
    world.data["2026-07_ps_raw.json"] = complete("2026-07", rows)
    result = world.result()
    assert result["observations"][0]["household_spending"] == 350
    assert result["observations"][0]["owners"][0]["spending"] == 300


@pytest.mark.parametrize("change", [
    {"date": "2026-06-30"}, {"date": "2026-07-99"}, {"date": "20260715"},
    {"amount": None}, {"amount": True}, {"amount": "NaN"}, {"amount": "Infinity"},
    {"amount": "bad"}, {"amount": "1e400"}, {"amount": "-1e-400"},
    {"id": None}, {"id": True}, {"transaction_account": {}},
    {"status": None}, {"status": "unknown"}, {"is_transfer": "true"},
    {"transaction_account": {"id": 1199999}},
])
def test_invalid_record_excludes_whole_month(world, change):
    world.data["2026-07_ps_raw.json"]["transactions"][0].update(change)
    result = world.result()
    assert result["included_months"] == MONTHS[1:]
    assert result["observations"][0]["household_spending"] is None
    assert result["observations"][0]["status"] == "excluded"


def test_conflicting_duplicate_invalidates_month(world):
    rows = world.data["2026-07_ps_raw.json"]["transactions"]
    rows.append({**rows[0], "payee": "Synthetic different metadata"})
    assert world.result()["included_months"] == MONTHS[1:]


@pytest.mark.parametrize("cross_month", [False, True])
@pytest.mark.parametrize("reverse_sources", [False, True])
@pytest.mark.parametrize("malformed_first", [False, True])
def test_fingerprint_amount_array_conflict_is_order_independent(
    world, monkeypatch, cross_month, reverse_sources, malformed_first,
):
    from budget_api.services import runway
    july = world.data["2026-07_ps_raw.json"]["transactions"]
    july[0]["amount"] = -100.0  # JSON number. Source decoder yields Decimal("-100.0").
    copy = deepcopy(july[0])
    copy["amount"] = ["decimal", "-100.0"]
    if cross_month:
        if malformed_first:
            july[0]["amount"], copy["amount"] = copy["amount"], july[0]["amount"]
        world.data["2026-08_ps_raw.json"]["transactions"].append(copy)
    elif malformed_first:
        july.insert(0, copy)
    else:
        july.append(copy)
    if reverse_sources:
        monkeypatch.setattr(runway, "_month_window", lambda now: list(reversed(MONTHS)))
    result = world.result()
    affected = MONTHS[:2] if cross_month else MONTHS[:1]
    assert sorted(result["included_months"]) == [month for month in MONTHS if month not in affected]
    for row in result["observations"]:
        if row["month"] in affected:
            assert (row["status"], row["coverage"]) == ("excluded", "invalid")
            assert "invalid_source" in codes(row)
            assert row["collected_at"] == "2026-10-01T00:15:00+00:00"
            assert row["household_spending"] is None
            assert all(owner["spending"] is None for owner in row["owners"])
    if cross_month:
        for scope in [*result["owners"], result["household"]]:
            assert scope["average_monthly_spending"] is None
            assert scope["runway_months"] is None
            assert "insufficient_history" in codes(scope)


@pytest.mark.parametrize("reverse_records", [False, True])
def test_fingerprint_decimal_repeats_count_once(world, reverse_records):
    for month in MONTHS:
        rows = world.data[f"{month}_ps_raw.json"]["transactions"]
        rows[0]["amount"] = -100.0
        rows[0]["metadata"] = {
            "nested": [{"decimal": -1.25, "array": ["decimal", "-100.0"]}],
            "scalars": [None, True, False, 0, "0"],
        }
        copy = dict(reversed(list(deepcopy(rows[0]).items())))
        copy["metadata"] = dict(reversed(list(copy["metadata"].items())))
        copy["metadata"]["nested"][0] = dict(reversed(list(copy["metadata"]["nested"][0].items())))
        rows.append(copy)
        if reverse_records:
            rows.reverse()
    result = world.result()
    assert result["included_months"] == MONTHS
    assert all(row["owners"][0]["spending"] == 100 for row in result["observations"])
    assert result["household"]["average_monthly_spending"] == 60100


@pytest.mark.parametrize("left,right", [
    (-100.0, ["decimal", "-100.0"]),
    ([-100.0], [["decimal", "-100.0"]]),
    ({"amount": -100.0}, {"amount": ["decimal", "-100.0"]}),
    ({"": [{"decimal": -100.0}]}, {"": [{"decimal": ["decimal", "-100.0"]}]}),
    ({"type": "decimal", "value": -100.0}, {"type": "decimal", "value": ["decimal", "-100.0"]}),
    ({"a": 1, "b": [None, True]}, [["a", 1], ["b", [None, True]]]),
])
@pytest.mark.parametrize("reverse_records", [False, True])
def test_fingerprint_nested_metadata_lookalikes_conflict(world, left, right, reverse_records):
    rows = world.data["2026-07_ps_raw.json"]["transactions"]
    rows[0]["metadata"] = left
    rows.append({**deepcopy(rows[0]), "metadata": right})
    if reverse_records:
        rows.reverse()
    result = world.result()
    assert result["included_months"] == MONTHS[1:]
    assert result["observations"][0]["coverage"] == "invalid"
    assert "invalid_source" in codes(result["observations"][0])


@pytest.mark.parametrize("container", ["scalar", "array", "object"])
def test_fingerprint_parsed_types_and_tag_lookalikes_never_collide(container):
    from budget_api.services.runway import _decode, _fingerprint
    values = _decode('''[
        null, false, true, 0, 1, -100, -100.0, -100.00, -0.0, 0.0,
        "", "0", "-100.0", [], {}, ["decimal", "-100.0"],
        {"decimal": "-100.0"}, {"type": "decimal", "value": "-100.0"},
        {"a": 1, "b": 2}, {"a": 2, "b": 1}, ["a", "b"], ["b", "a"],
        NaN, Infinity, -Infinity, 1e9999, 1e-9999, 1.0000000000000000000000000001
    ]''')
    if container == "array":
        values = [[value] for value in values]
    elif container == "object":
        values = [{"": {"value": value}} for value in values]
    fingerprints = [_fingerprint(value) for value in values]
    assert len(set(fingerprints)) == len(values)
    for value, fingerprint in zip(values, fingerprints):
        # User-shaped canonical data must not impersonate its source.
        lookalike = _decode(json.dumps(fingerprint))
        assert _fingerprint(lookalike) != fingerprint


@pytest.mark.parametrize("left,right", [
    ("-0", "0"),
    ("-100.0", "-1.000e2"),
    ('"a"', r'"\u0061"'),
    ('{"b":[-100.0,null],"a":{"x":true,"y":0}}',
     '{"a":{"y":0,"x":true},"b":[-1.000e2,null]}'),
])
def test_fingerprint_preserves_equivalent_decoded_values(left, right):
    from budget_api.services.runway import _decode, _fingerprint
    assert _fingerprint(_decode(f"[{left}]")) == _fingerprint(_decode(f"[{right}]"))


@pytest.mark.parametrize("amount", [float("nan"), float("inf"), float("-inf")])
def test_fingerprint_nonfinite_duplicate_amount_stays_invalid(world, amount):
    rows = world.data["2026-07_ps_raw.json"]["transactions"]
    rows[0]["amount"] = amount
    rows.append(deepcopy(rows[0]))
    result = world.result()
    assert result["included_months"] == MONTHS[1:]
    assert result["observations"][0]["coverage"] == "invalid"
    assert "invalid_source" in codes(result["observations"][0])


@pytest.mark.parametrize("reverse_sources", [False, True])
@pytest.mark.parametrize("reverse_records", [False, True])
def test_cross_month_identity_conflict_invalidates_every_affected_month(
    world, monkeypatch, reverse_sources, reverse_records,
):
    from budget_api.services import runway
    july = world.data["2026-07_ps_raw.json"]["transactions"]
    august = world.data["2026-08_ps_raw.json"]["transactions"]
    august[0]["id"] = july[0]["id"]
    if reverse_records:
        july.reverse()
        august.reverse()
    if reverse_sources:
        monkeypatch.setattr(runway, "_month_window", lambda now: list(reversed(MONTHS)))
    result = world.result()
    assert result["included_months"] == MONTHS[2:]
    observations = {row["month"]: row for row in result["observations"]}
    for month in MONTHS[:2]:
        row = observations[month]
        assert (row["status"], row["coverage"]) == ("excluded", "invalid")
        assert "invalid_source" in codes(row)
        assert row["collected_at"] == "2026-10-01T00:15:00+00:00"
        assert row["household_spending"] is None
        assert all(owner["spending"] is None for owner in row["owners"])
    for scope in [*result["owners"], result["household"]]:
        assert scope["average_monthly_spending"] is None
        assert scope["runway_months"] is None
        assert "insufficient_history" in codes(scope)


def test_conflict_scan_continues_past_invalid_record_and_partial_provenance(world):
    july = world.data["2026-07_ps_raw.json"]["transactions"]
    august = world.data["2026-08_ps_raw.json"]
    august["transactions"][0]["id"] = july[0]["id"]
    august["transactions"].insert(0, {"id": None})
    august["provenance"]["complete"] = False
    assert world.result()["included_months"] == MONTHS[2:]


@pytest.mark.parametrize("reverse_sources", [False, True])
def test_identical_repeats_ignore_object_key_order_not_distinct_identities(world, monkeypatch, reverse_sources):
    from budget_api.services import runway
    for month in MONTHS:
        rows = world.data[f"{month}_ps_raw.json"]["transactions"]
        rows.append(dict(reversed(list(deepcopy(rows[0]).items()))))
        rows.append({**deepcopy(rows[0]), "id": rows[0]["id"] + 50000})
    if reverse_sources:
        monkeypatch.setattr(runway, "_month_window", lambda now: list(reversed(MONTHS)))
    result = world.result()
    assert sorted(result["included_months"]) == MONTHS
    assert result["owners"][0]["average_monthly_spending"] == 60000
    assert result["household"]["average_monthly_spending"] == 120000


@pytest.mark.parametrize("reverse_sources", [False, True])
def test_identical_cross_month_copy_invalidates_only_out_of_month_source(world, monkeypatch, reverse_sources):
    from budget_api.services import runway
    original = world.data["2026-07_ps_raw.json"]["transactions"][0]
    world.data["2026-08_ps_raw.json"]["transactions"].append(
        dict(reversed(list(deepcopy(original).items()))),
    )
    if reverse_sources:
        monkeypatch.setattr(runway, "_month_window", lambda now: list(reversed(MONTHS)))
    result = world.result()
    assert sorted(result["included_months"]) == [MONTHS[0], MONTHS[2]]
    assert result["owners"][0]["average_monthly_spending"] == 30000
    assert result["household"]["average_monthly_spending"] == 90000
    august = next(row for row in result["observations"] if row["month"] == MONTHS[1])
    assert august["coverage"] == "invalid"
    assert "invalid_source" in codes(august)


@pytest.mark.parametrize("title", [["cc payment"], {"text": "cc payment"}])
def test_invalid_embedded_category_title_excludes_month(world, title):
    world.data["2026-07_ps_raw.json"]["transactions"][0]["category"] = {"id": 2100099, "title": title}
    result = world.result()
    assert result["included_months"] == MONTHS[1:]
    assert result["observations"][0]["coverage"] == "invalid"
    assert "invalid_source" in codes(result["observations"][0])
    assert result["owners"][0]["runway_display"] == "2.6"


def test_valid_embedded_repayment_title_still_excludes_purchase(world):
    world.data["2026-07_ps_raw.json"]["transactions"][0]["category"] = {
        "id": 2100099, "title": "Synthetic CC Payment",
    }
    result = world.result()
    assert result["included_months"] == MONTHS
    assert result["observations"][0]["owners"][0]["spending"] == 0
    assert result["owners"][0]["runway_display"] == "3.9"


@pytest.mark.parametrize("provenance,reason", [
    ({"complete": False}, "partial_source"),
    ({"collected_at": "2026-07-31T23:59:00+00:00"}, "partial_source"),
    ({"complete": True}, "invalid_source"),
    ({"collected_at": "2027-01-01T00:00:00+00:00"}, "invalid_source"),
    ({"collected_at": "2026-10-01"}, "invalid_source"),
    ({"coverage_start": "2026-07-02", "coverage_end": "2026-07-31"}, "partial_source"),
])
def test_coverage_exclusions(world, provenance, reason):
    world.data["2026-07_ps_raw.json"]["provenance"] = provenance
    result = world.result()
    assert result["observations"][0]["status"] == "excluded"
    assert reason in codes(result["observations"][0])


def test_legacy_positive_history_qualified_but_unproven_owner_zero_excluded(world):
    for month in MONTHS:
        world.data[f"{month}_ps_raw.json"] = world.data[f"{month}_ps_raw.json"]["transactions"]
    result = world.result()
    assert result["included_month_count"] == 3
    assert "coverage_unverified" in codes(result["household"])
    assert "source_date_unknown" in codes(result["household"])
    world.data["2026-07_ps_raw.json"].pop()
    assert "unproven_zero" in codes(world.result()["observations"][0])


def test_complete_zero_is_observed_not_missing(world):
    for month in MONTHS:
        world.data[f"{month}_ps_raw.json"]["transactions"] = []
    result = world.result()["household"]
    assert result["average_monthly_spending"] == 0
    assert result["runway_months"] is None
    assert "nonpositive_burn" in codes(result)


@pytest.mark.parametrize("balance", [0, -20, None, True, "NaN", "bad", "1e400", "1e-400"])
def test_bad_or_nonpositive_balance(world, balance):
    world.data["account_catalog.json"]["accounts"][0]["current_balance"] = balance
    result = world.result()
    a, b = result["owners"]
    assert a["runway_months"] is None
    assert b["runway_months"] == 0.5
    if type(balance) is int:
        assert a["reserves"] == balance
        assert "nonpositive_reserves" in codes(a)
    else:
        assert a["reserves"] is None
        assert result["household"]["reserves"] is None


def test_signed_reserves_selection_scope_and_rounding(world):
    world.data["runway_config.json"]["liquid_account_ids"] = [A, SAVINGS]
    world.data["account_catalog.json"]["accounts"][0]["current_balance"] = 10000
    result = world.result()
    assert result["household"]["reserves"] == 8000
    assert result["owners"][1]["reserves"] is None
    assert "no_selection" in codes(result["owners"][1])
    world.data["runway_config.json"]["liquid_account_ids"] = [A]
    world.data["account_catalog.json"]["accounts"][0]["current_balance"] = 37500
    assert world.result()["owners"][0]["runway_display"] == "1.3"
    world.data["account_catalog.json"]["accounts"][0]["current_balance"] = 1
    assert world.result()["owners"][0]["runway_display"] == "<0.1"


def test_stable_owner_ids_reassignment_and_unresolved_selected_owner(world):
    mappings = world.data["account_mappings.json"]
    mappings["partners"] = {"zeta": {"label": "Partner B"}, "alpha": {"label": "Partner A"}}
    for binding in mappings["accounts"].values():
        binding["partner_id"] = "zeta" if binding["partner_id"] == "partner_a" else "alpha"
    result = world.result()
    assert result["owners"][1]["owner"]["partner_id"] == "zeta"
    assert result["owners"][1]["runway_months"] == 3
    mappings["accounts"].pop(A)
    result = world.result()
    assert all(row["reserves"] is None for row in result["owners"])


def test_currency_conflict_scopes(world):
    world.data["account_catalog.json"]["accounts"][1]["currency_code"] = "USD"
    result = world.result()
    assert [owner["runway_months"] for owner in result["owners"]] == [3, 0.5]
    assert result["household"]["reserves"] is None
    assert result["household"]["average_monthly_spending"] is None
    assert "currency_conflict" in codes(result["household"])
    assert result["included_month_count"] == 3


def test_reserve_spending_conflict_preserves_separate_measures(world):
    for month in MONTHS:
        world.data[f"{month}_ps_raw.json"]["transactions"][0]["transaction_account"]["id"] = int(CARD)
    world.data["account_catalog.json"]["accounts"][3]["currency_code"] = "USD"
    result = world.result()["owners"][0]
    assert result["reserves"] == 90000
    assert result["average_monthly_spending"] == 30000
    assert result["runway_months"] is None
    assert result["reserves_currency_code"] == "NOK"
    assert result["spending_currency_code"] == "USD"


def test_conflicting_transaction_currency_excludes_common_month(world):
    world.data["2026-07_ps_raw.json"]["transactions"][0]["currency_code"] = "USD"
    assert world.result()["included_months"] == MONTHS[1:]


def test_unknown_currency_and_balance_dates_qualified(world):
    account = world.data["account_catalog.json"]["accounts"][0]
    account.pop("currency_code")
    account["current_balance_date"] = "invalid"
    result = world.result()["owners"][0]
    assert result["runway_months"] == 3
    assert {"currency_unverified", "balance_date_unverified"} <= codes(result)


@pytest.mark.parametrize("source,value", [
    ("account_mappings.json", {}),
    ("account_mappings.json", {"partners": [], "accounts": {}}),
    ("account_catalog.json", None),
    ("category_roles.json", None),
    ("detailed_section_mapping.json", None),
    ("category_catalog.json", {"categories": [{"id": 2100001, "parent_id": 2100002}]}),
])
def test_invalid_source_does_not_fabricate_reserves(world, source, value):
    world.data[source] = value
    result = world.result()
    assert result["household"]["reserves"] is None
    assert result["household"]["average_monthly_spending"] is None
    assert "invalid_source" in codes(result)


@pytest.mark.parametrize("field,value", [("type", []), ("excluded", 1), ("partner_id", [])])
def test_malformed_binding_explicit_unavailability(world, field, value):
    world.data["account_mappings.json"]["accounts"][A][field] = value
    result = world.result()
    assert result["household"]["runway_months"] is None
    assert result["household"]["reserves"] is None


@pytest.mark.parametrize("field,value", [("status", []), ("amount", {}), ("category", []), ("date", 1)])
def test_malformed_consumed_transaction_types_exclude_month(world, field, value):
    world.data["2026-07_ps_raw.json"]["transactions"][0][field] = value
    assert world.result()["included_months"] == MONTHS[1:]


def test_signed_sum_does_not_lose_small_balance_on_cancellation(world):
    world.data["runway_config.json"]["liquid_account_ids"] = [A, SAVINGS, B]
    for account, balance in zip(world.data["account_catalog.json"]["accounts"], ["1e100", "-1e100", "1.5"]):
        account["current_balance"] = balance
    result = world.result()
    assert result["household"]["reserves"] == 1.5


def test_cross_month_currency_conflict_keeps_other_owner(world):
    for account in world.data["account_catalog.json"]["accounts"]:
        account.pop("currency_code")
    for index, month in enumerate(MONTHS):
        rows = world.data[f"{month}_ps_raw.json"]["transactions"]
        rows[0]["currency_code"] = "NOK" if index == 0 else "USD"
        rows[1]["currency_code"] = "NOK"
    result = world.result()
    assert result["included_month_count"] == 3
    assert result["owners"][0]["average_monthly_spending"] is None
    assert result["owners"][1]["runway_months"] == 0.5
    assert result["household"]["average_monthly_spending"] is None


def test_missing_catalog_retains_selected_ids_no_reserve_zero(world):
    world.remove("account_catalog.json")
    result = world.result()
    assert result["selected_account_ids"] == [A, B]
    assert result["household"]["reserves"] is None
    assert result["household"]["average_monthly_spending"] == 90000


def test_duplicate_catalog_identity_blocks_affected_reserves(world):
    accounts = world.data["account_catalog.json"]["accounts"]
    accounts.append(deepcopy(accounts[0]))
    result = world.result()
    assert result["household"]["reserves"] is None
    assert result["owners"][1]["reserves"] == 30000
    assert result["included_month_count"] == 0


def test_fresh_verified_evidence_available_with_equivalent_timestamp_offsets(world):
    for month in MONTHS:
        world.data[f"{month}_ps_raw.json"]["provenance"]["collected_at"] = "2026-10-15T13:00:00+02:00"
    result = world.result()
    assert "source_times_differ" not in codes(result)
    assert result["household"]["status"] == "available"


def test_system_calendar_uses_period_offset_not_calculation_offset(world, monkeypatch):
    from budget_api.services import runway
    winter_now = datetime(2026, 10, 31, 12, tzinfo=timezone(timedelta(hours=1)))
    monkeypatch.setattr(runway, "local_now", lambda: winter_now)
    monkeypatch.setattr(
        runway, "_system_midnight",
        lambda day: datetime.combine(day, day_time.min, timezone(timedelta(hours=2))),
    )
    world.data["2026-07_ps_raw.json"]["provenance"]["collected_at"] = "2026-08-01T00:15:00+02:00"
    world.write()
    assert runway.calculate_runway().included_months == MONTHS


@pytest.mark.parametrize("value,precision,code", [
    ("2026-10-15", "date", None),
    ("2026-10-14T12:00:00+00:00", "datetime", None),
    ("2026-10-14T11:59:59+00:00", "datetime", "balance_stale"),
    ("2027-01-01", "unknown", "balance_date_unverified"),
    (None, "unknown", "balance_date_unknown"),
])
def test_bank_date_precision_and_24_hour_boundary(world, value, precision, code):
    world.data["account_catalog.json"]["accounts"][0]["current_balance_date"] = value
    account = world.result()["selected_accounts"][0]
    assert account["balance_date_precision"] == precision
    assert account["balance"] == 90000
    if code:
        assert code in codes(account)
    else:
        assert account["balance_freshness"] == "fresh"


@pytest.mark.parametrize("reserve,spending", [("1e-300", "-1e300"), ("1e300", "-1e-300")])
def test_unrepresentable_ratio_never_zero_or_infinity(world, reserve, spending):
    world.data["account_catalog.json"]["accounts"][0]["current_balance"] = reserve
    for month in MONTHS:
        world.data[f"{month}_ps_raw.json"]["transactions"][0]["amount"] = spending
    result = world.result()["owners"][0]
    assert result["runway_months"] is None
    assert result["runway_display"] is None
    assert "invalid_source" in codes(result)


def test_removed_selected_account_blocks_only_its_reserve_owner(world):
    world.data["account_catalog.json"]["accounts"].pop(0)
    result = world.result()
    selected = result["selected_accounts"]
    assert {account["id"] for account in selected} == {A, B}
    assert result["owners"][0]["reserves"] is None
    assert result["owners"][1]["runway_months"] == 0.5


def test_missing_category_authority_and_unrelated_split_do_not_invent_data(world):
    world.remove("category_catalog.json")
    world.data["split_config.json"] = {"shares": {"partner_a": 0, "partner_b": 100}}
    result = world.result()
    assert result["owners"][0]["runway_months"] == 3
    assert "classification_unverified" in codes(result["household"])


def test_sources_changing_blocks_all_measures(world, monkeypatch):
    from budget_api.services import runway
    world.write()
    original = runway._read_bytes
    seen = 0

    def changed(path):
        nonlocal seen
        value = original(path)
        if path.name == "account_catalog.json":
            seen += 1
            if seen > 1:
                return value + b" "
        return value

    monkeypatch.setattr(runway, "_read_bytes", changed)
    result = runway.calculate_runway(now=NOW).model_dump(mode="json")
    assert "sources_changing" in codes(result)
    assert result["household"]["reserves"] is None
    assert result["household"]["average_monthly_spending"] is None


def test_ten_thousand_transactions_twenty_accounts(world):
    world.use_large_history()
    world.write()
    from budget_api.services.runway import calculate_runway
    started = time.perf_counter()
    result = calculate_runway(now=NOW)
    elapsed = time.perf_counter() - started
    assert result.household.average_monthly_spending == pytest.approx(100000 / 3)
    assert elapsed < 2
    print(f"Synthetic backend: 10000 transactions, 20 mappings, {elapsed:.3f}s")
