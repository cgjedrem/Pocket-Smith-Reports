from copy import deepcopy
from datetime import datetime, time as day_time, timedelta, timezone
import json
import time

import pytest

from budget_api.tests.runway.synthetic import A, B, CARD, MONTHS, NOW, SAVINGS, complete, pocketsmith_month, transaction


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


def test_reports_exclusions_dedupe_and_refunds(world):
    mapping = world.data["account_mappings.json"]
    mapping["accounts"]["1100004"] = {"excluded": True}
    world.data["detailed_section_mapping.json"]["category_sections"].update(
        {"2100004": "cc_payments", "2100005": "excluded", "2100006": "savings", "2100099": "common"}
    )
    rows = [transaction(1, A, -100), transaction(2, CARD, -200), transaction(3, B, -50)]
    rows += [deepcopy(rows[0]), transaction(4, A, 40), transaction(5, CARD, 60)]
    for index, cat in enumerate([2100004, 2100005, 2100006]):
        rows.append(transaction(100 + index, category={"id": cat, "title": f"Synthetic section {index}"}))
    rows += [
        transaction(200, is_transfer=True),
        transaction(201, category={"id": 2100099, "title": "Synthetic moved", "is_transfer": True}),
        transaction(203, "1100004"), transaction(205, status="pending"),
    ]
    world.data["2026-07_ps_raw.json"] = complete("2026-07", rows)
    result = world.result()
    # By hand. A = 100 + 200 (card) + 100 pending - 40 - 60 refunds = 300. B = 50. Household 350.
    # Duplicate once. cc_payments/excluded/savings sections, transfers, excluded account: never.
    assert result["observations"][0]["household_spending"] == 350
    assert [owner["spending"] for owner in result["observations"][0]["owners"]] == [300, 50]


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


def test_embedded_repayment_title_alone_does_not_route_section_mapping_does(world):
    # Reports route by section mapping, not by title text.
    world.data["2026-07_ps_raw.json"]["transactions"][0]["category"] = {
        "id": 2100099, "title": "Synthetic CC Payment",
    }
    world.data["detailed_section_mapping.json"]["category_sections"]["2100099"] = "cc_payments"
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


# RD-001. PocketSmith sends is_transfer null. Null or absent = not a transfer.
# Non-null must be a literal bool. Binding "excluded" flag stays strict.
ABSENT = object()  # flag key omitted from the record
SITES = ["transaction", "embedded_category", "catalog_row", "catalog_ancestor"]
NON_BOOLEAN = ["true", "false", 1, 0, "", []]
NON_BOOLEAN_IDS = ["str-true", "str-false", "int-1", "int-0", "empty-str", "empty-list"]
REAL_TRANSACTION_KEYS = {
    "amount", "amount_in_base_currency", "category", "cheque_number", "closing_balance", "created_at",
    "date", "id", "is_transfer", "labels", "memo", "needs_review", "note", "original_payee", "payee",
    "status", "transaction_account", "type", "updated_at", "upload_source",
}
REAL_CATEGORY_KEYS = {
    "children", "colour", "created_at", "id", "is_bill", "is_transfer", "parent_id",
    "refund_behaviour", "roll_up", "rollover_type", "title", "updated_at",
}
REAL_ACCOUNT_KEYS = {
    "account_id", "created_at", "currency_code", "current_balance", "current_balance_date",
    "current_balance_exchange_rate", "current_balance_in_base_currency", "current_balance_source",
    "data_feeds_account_id", "data_feeds_balance_type", "data_feeds_connection_id",
    "has_safe_balance_adjustment", "id", "include_in_net_worth", "institution", "is_net_worth",
    "latest_feed_name", "name", "number", "offline", "safe_balance", "safe_balance_in_base_currency",
    "starting_balance", "starting_balance_date", "type", "updated_at",
}


def place_transfer_flag(world, site, flag):
    """July = one 100 purchase by A. Flag sits at one PocketSmith-sourced is_transfer read site."""
    row = transaction(1, A, -100)
    if site == "transaction":
        holder = row
    elif site == "embedded_category":
        holder = row["category"] = {"id": 2100050, "title": "Synthetic dining"}
    else:
        # Catalog site. Embedded leaf carries title; flag only in the catalog.
        row["category"] = {"id": 2100050, "title": "Synthetic dining"}
        holder = {"id": 2100050, "title": "Synthetic dining"}
        if site == "catalog_ancestor":  # flag on parent. purchase sits in child
            holder = {"id": 2100051, "title": "Synthetic parent", "children": [holder]}
        world.data["category_catalog.json"] = {"categories": [holder]}
    if flag is not ABSENT:
        holder["is_transfer"] = flag
    world.data["2026-07_ps_raw.json"] = complete("2026-07", [row])


@pytest.mark.parametrize("site", SITES)
@pytest.mark.parametrize("flag,counted", [(None, True), (False, True), (ABSENT, True), (True, False)],
                         ids=["null", "false", "absent", "true"])
def test_transfer_flag_semantics_at_each_pocketsmith_site(world, site, flag, counted):
    place_transfer_flag(world, site, flag)
    # RD-002: Reports read transaction/embedded flags only. Catalog flags never drop spend.
    counted = counted or site.startswith("catalog")
    result = world.result()
    july = result["observations"][0]
    assert (july["status"], july["coverage"]) == ("included", "complete")
    assert "invalid_source" not in codes(july) | codes(result)
    assert result["included_months"] == MONTHS
    assert [owner["spending"] for owner in july["owners"]] == [100 if counted else 0, 0]
    assert july["household_spending"] == (100 if counted else 0)


def test_null_transaction_transfer_flag_counts_as_gross_spend_like_false(world):
    world.data["2026-07_ps_raw.json"] = complete("2026-07", [
        transaction(1, A, -100, is_transfer=None),
        transaction(2, A, -250, is_transfer=False),
        transaction(3, A, -7),  # key absent
        transaction(4, A, -1000, is_transfer=True),  # transfer. never counted
        transaction(5, B, -40, is_transfer=None),
    ])
    result = world.result()
    july = result["observations"][0]
    assert (july["status"], july["coverage"]) == ("included", "complete")
    # By hand. A = 100 + 250 + 7. B = 40. Household = 397.
    assert [owner["spending"] for owner in july["owners"]] == [357, 40]
    assert july["household_spending"] == 397
    assert result["included_months"] == MONTHS


def test_null_category_transfer_flag_does_not_mask_section_exclusions(world):
    world.data["category_catalog.json"] = {"categories": [
        {"id": 2100050, "title": "Synthetic CC Payment", "is_transfer": None},
        {"id": 2100051, "title": "Synthetic parent", "is_transfer": None,
         "children": [{"id": 2100052, "title": "Synthetic child", "is_transfer": None}]},
        {"id": 2100098, "title": "Synthetic dining"},
        {"id": 2100099, "title": "Synthetic CC Payment"},
    ]}
    world.data["detailed_section_mapping.json"]["category_sections"].update(
        {"2100050": "cc_payments", "2100051": "excluded", "2100098": "common", "2100099": "cc_payments"}
    )
    world.data["2026-07_ps_raw.json"] = complete("2026-07", [
        transaction(1, A, -100, category={"id": 2100050, "title": "Synthetic CC Payment", "is_transfer": None}),
        transaction(2, A, -200, category={"id": 2100052, "title": "Synthetic child", "is_transfer": None}),  # parent section
        transaction(3, A, -300, category={"id": 2100099, "title": "Synthetic CC Payment", "is_transfer": None}),
        transaction(4, A, -400, category={"id": 2100098, "title": "Synthetic dining", "is_transfer": None}),
    ])
    result = world.result()
    july = result["observations"][0]
    assert july["status"] == "included"
    assert [owner["spending"] for owner in july["owners"]] == [400, 0]  # only the plain row counts
    assert july["household_spending"] == 400


@pytest.mark.parametrize("value", NON_BOOLEAN, ids=NON_BOOLEAN_IDS)
@pytest.mark.parametrize("site", ["transaction", "embedded_category"])
def test_non_boolean_transfer_flag_invalidates_transaction_and_embedded_category_month(world, site, value):
    place_transfer_flag(world, site, value)
    result = world.result()
    july = result["observations"][0]
    assert (july["status"], july["coverage"]) == ("excluded", "invalid")
    assert "invalid_source" in codes(july)
    assert july["household_spending"] is None
    assert result["included_months"] == MONTHS[1:]


@pytest.mark.parametrize("value", NON_BOOLEAN, ids=NON_BOOLEAN_IDS)
@pytest.mark.parametrize("site", ["catalog_row", "catalog_ancestor"])
def test_non_boolean_catalog_transfer_flag_is_not_an_authority(world, site, value):
    # Reports ignore catalog transfer flags. Runway follows. Spend counts.
    place_transfer_flag(world, site, value)
    result = world.result()
    assert result["included_months"] == MONTHS
    assert "invalid_source" not in codes(result)
    assert result["observations"][0]["owners"][0]["spending"] == 100


@pytest.mark.parametrize("value", [None, "false", 0])
def test_pocketsmith_transfer_reader_leaves_binding_excluded_flag_strict(world, value):
    world.data["account_mappings.json"]["accounts"][A]["excluded"] = value
    result = world.result()
    assert result["included_months"] == []
    assert {(row["status"], row["coverage"]) for row in result["observations"]} == {("excluded", "invalid")}
    assert result["household"]["reserves"] is None
    assert result["household"]["runway_months"] is None
    selected = next(account for account in result["selected_accounts"] if account["id"] == A)
    assert {"invalid_source", "account_excluded"} <= codes(selected)


def test_pocketsmith_fixture_carries_the_full_real_field_set():
    rows = pocketsmith_month("2026-07", 0)
    for row in rows:
        assert set(row) == REAL_TRANSACTION_KEYS
        assert set(row["category"]) == REAL_CATEGORY_KEYS
        assert set(row["transaction_account"]) == REAL_ACCOUNT_KEYS
        assert row["status"] == "posted"
    assert {row["is_transfer"] for row in rows} == {None, True, False}
    assert len({row["id"] for row in rows}) == len(rows)


def test_null_transfer_flag_result_equals_false_flag_result(world):
    for index, month in enumerate(MONTHS):
        world.data[f"{month}_ps_raw.json"] = pocketsmith_month(month, index)
    with_null = world.result()
    assert with_null["included_months"] == MONTHS
    for month in MONTHS:
        for row in world.data[f"{month}_ps_raw.json"]:
            if row["is_transfer"] is None:
                row["is_transfer"] = False
    assert world.result() == with_null


def test_pocketsmith_shaped_months_with_mixed_transfer_flags_are_included_unverified(world):
    for index, month in enumerate(MONTHS):
        world.data[f"{month}_ps_raw.json"] = pocketsmith_month(month, index)  # bare list. no provenance
    result = world.result()
    assert result["included_months"] == MONTHS
    # By hand per scale unit (months scale x1, x2, x3). Reports net basis.
    # A = 120.50 + 80.25 + 60.00 (card) + 77.00 (savings acct) - 20.00 refund = 317.75.
    # B = 45.10 + 15.90 + 30.00 = 91. Transfers (txn or embedded category flag) never count.
    for scale, observation in enumerate(result["observations"], 1):
        assert (observation["status"], observation["coverage"]) == ("included", "unverified")
        assert ("coverage_unverified", "qualification") in {(i["code"], i["severity"]) for i in observation["issues"]}
        assert all(i["severity"] == "qualification" for i in observation["issues"])
        a_month, b_month = (owner["spending"] for owner in observation["owners"])
        # Cent-rounded monthly values. Exact, no float noise.
        assert (a_month, b_month) == (317.75 * scale, 91 * scale)
        assert observation["household_spending"] == 408.75 * scale
        assert a_month + b_month == observation["household_spending"]
    a, b = result["owners"]
    household = result["household"]
    # Mean scale (1 + 2 + 3) / 3 = 2.
    assert (a["average_monthly_spending"], b["average_monthly_spending"]) == (635.5, 182)
    assert household["average_monthly_spending"] == 817.5
    # 90000 / 635.5 = 141.62. 30000 / 182 = 164.84. 120000 / 817.5 = 146.79.
    assert (a["runway_display"], b["runway_display"], household["runway_display"]) == ("141.6", "164.8", "146.8")
    assert household["status"] == "qualified"
    assert "coverage_unverified" in codes(household)
    assert "insufficient_history" not in codes(household)
    assert "invalid_source" not in codes(result)


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


@pytest.mark.parametrize("reserve,spending,code", [
    ("1e-300", -1e300, "invalid_source"),
    ("1e307", -0.01, "invalid_source"),  # 1e309 overflows float
    ("1e300", -1e-300, "nonpositive_burn"),  # Monthly cents: 1e-300 -> 0.00
])
def test_unrepresentable_ratio_never_zero_or_infinity(world, reserve, spending, code):
    world.data["account_catalog.json"]["accounts"][0]["current_balance"] = reserve
    for month in MONTHS:
        world.data[f"{month}_ps_raw.json"]["transactions"][0]["amount"] = spending
    result = world.result()["owners"][0]
    assert result["runway_months"] is None
    assert result["runway_display"] is None
    assert code in codes(result)


def test_removed_selected_account_blocks_only_its_reserve_owner(world):
    world.data["account_catalog.json"]["accounts"].pop(0)
    result = world.result()
    selected = result["selected_accounts"]
    assert {account["id"] for account in selected} == {A, B}
    assert result["owners"][0]["reserves"] is None
    assert result["owners"][1]["runway_months"] == 0.5


def test_missing_category_authority_and_unrelated_split_do_not_invent_data(world):
    world.remove("category_catalog.json")
    # Valid but disabled split: payer attribution, no invented share.
    world.data["split_config.json"] = {"enabled": False, "shares": {"partner_a": 0, "partner_b": 100}, "categories": []}
    result = world.result()
    assert result["owner_attribution"] == "payer"
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
