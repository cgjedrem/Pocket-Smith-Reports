"""SC-split / RD-002. Runway burn = Reports household net spending; owners follow common-economy split.

All numbers hand-computed in comments. Never derived from the service under test.
"""

from decimal import Decimal, localcontext

import pytest

from budget_api.tests.runway.synthetic import A, B, MONTHS, NOW, complete, pocketsmith_month, transaction

SECTIONS = {
    2100070: ("Synthetic rent", "home"),
    2100071: ("Synthetic groceries", "common"),
    2100072: ("Synthetic hobby A", "personal_partner_a"),
    2100073: ("Synthetic hobby B", "personal_partner_b"),
    2100074: ("Synthetic trip", "trips"),
    2100075: ("Synthetic card repayment", "cc_payments"),
    2100076: ("Synthetic saving", "savings"),
    2100077: ("Synthetic ignored", "excluded"),
    2100078: ("Synthetic salary", "income_salary"),
}
SPLIT_60_40 = {"enabled": True, "shares": {"partner_a": 60, "partner_b": 40}, "categories": ["2100070", "2100071"]}


def codes(value):
    return {issue["code"] for issue in value["issues"]}


def row(number, account, amount, category, **extra):
    # Offset ids. Avoid identity conflicts with default Aug/Sep rows.
    return transaction(500 + number, account, amount, category={"id": category, "title": SECTIONS[category][0]}, **extra)


def household_july(world, split=None):
    """July by payer. A: home 10000, common 3000, personal 500, trip 1200 = 14700.
    B: home 2000, common 1000 - 400 refund, personal 700 = 3300. Household 18000.
    Not burn: card repayment, savings, excluded, salary, transfer in common.
    """
    world.data["category_catalog.json"] = {"categories": [
        {"id": key, "title": title} for key, (title, _) in SECTIONS.items()
    ]}
    world.data["detailed_section_mapping.json"]["category_sections"].update(
        {str(key): section for key, (_, section) in SECTIONS.items()}
    )
    world.data["2026-07_ps_raw.json"] = complete("2026-07", [
        row(1, A, -10000, 2100070), row(2, B, -2000, 2100070),
        row(3, A, -3000, 2100071), row(4, B, -1000, 2100071), row(5, B, 400, 2100071),
        row(6, A, -500, 2100072), row(7, B, -700, 2100073), row(8, A, -1200, 2100074),
        row(9, A, -5000, 2100075), row(10, B, -4000, 2100076), row(11, A, -900, 2100077),
        row(12, A, 30000, 2100078), row(13, B, -600, 2100071, is_transfer=True),
    ])
    if split is not None:
        world.data["split_config.json"] = split


def test_contract_marks_household_net_basis_v2(world):
    result = world.result()
    assert result["calculation_version"] == 2
    assert result["basis"] == "household_net_spending"
    assert result["owner_attribution"] == "payer"
    assert result["split_shares"] is None


def test_rd002_transfer_flagged_parent_keeps_home_children_like_reports(world):
    from budget_api.services import report_builder
    world.data["category_catalog.json"] = {"categories": [
        {"id": 2100060, "title": "Synthetic home", "is_transfer": True, "children": [
            {"id": 2100061, "title": "Synthetic mortgage", "is_transfer": False},
            {"id": 2100062, "title": "Synthetic upkeep", "is_transfer": None},
        ]},
    ]}
    world.data["detailed_section_mapping.json"]["category_sections"]["2100060"] = "home"
    world.data["category_roles.json"] = {"2100060": "spend", "uncategorized": "spend"}
    world.data["2026-07_ps_raw.json"]["transactions"] += [
        transaction(5, A, -12000, category={"id": 2100061, "title": "Synthetic mortgage", "is_transfer": False}),
        transaction(6, B, -3000, category={"id": 2100062, "title": "Synthetic upkeep", "is_transfer": None}),
    ]
    result = world.result()
    july = result["observations"][0]
    # A 20000 + 12000. B 50000 + 3000. Parent flag never drops children.
    assert july["status"] == "included"
    assert [owner["spending"] for owner in july["owners"]] == [32000, 53000]
    assert july["household_spending"] == 85000
    report = report_builder.build_report("2026-07")
    assert report["detailed"]["household_totals"]["total"] == july["household_spending"]


def test_parity_with_reports_household_totals_payer(world):
    from budget_api.services import report_builder
    household_july(world)
    result = world.result()
    july = result["observations"][0]
    assert [owner["spending"] for owner in july["owners"]] == [14700, 3300]
    assert july["household_spending"] == 18000
    totals = report_builder.build_report("2026-07")["detailed"]["household_totals"]
    assert (totals["partner_a"], totals["partner_b"], totals["total"]) == (14700, 3300, 18000)
    assert result["owner_attribution"] == "payer"
    # Means: A (14700 + 30000 + 40000) / 3. B (3300 + 60000 + 70000) / 3.
    assert result["owners"][0]["average_monthly_spending"] == pytest.approx(84700 / 3)
    assert result["owners"][1]["average_monthly_spending"] == pytest.approx(133300 / 3)
    assert result["household"]["average_monthly_spending"] == pytest.approx(218000 / 3)


def test_split_60_40_attributes_selected_categories_by_share(world):
    from budget_api.services import report_builder
    household_july(world, SPLIT_60_40)
    result = world.result()
    assert result["owner_attribution"] == "common_economy_split"
    assert result["split_shares"] == {"partner_a": 60, "partner_b": 40}
    july = result["observations"][0]
    # Home 12000 -> A fair 7200, B 4800. Common net 3000 + 600 = 3600 -> A 2160, B 1440.
    # A = 7200 + 2160 + own personal 500 + trip 1200 = 11060. B = 4800 + 1440 + 700 = 6940.
    a, b = (owner["spending"] for owner in july["owners"])
    assert (a, b) == (11060, 6940)
    assert a + b == july["household_spending"]
    assert july["household_spending"] == 18000
    report = report_builder.build_report("2026-07")["detailed"]
    totals = report["household_totals"]
    delta_a = sum(item["delta"] for item in report["split"]["rows"])
    delta_b = sum(item["delta_b"] for item in report["split"]["rows"])
    assert a == pytest.approx(totals["partner_a"] - delta_a)
    assert b == pytest.approx(totals["partner_b"] - delta_b)
    # Unselected uncategorized months stay by payer.
    assert [owner["spending"] for owner in result["observations"][1]["owners"]] == [30000, 60000]
    for scope in result["owners"]:
        assert "invalid_source" not in codes(scope)
    assert result["owners"][0]["average_monthly_spending"] == pytest.approx((11060 + 30000 + 40000) / 3)
    assert result["household"]["average_monthly_spending"] == pytest.approx(218000 / 3)


@pytest.mark.parametrize("split", [None, {**SPLIT_60_40, "enabled": False}])
def test_split_absent_or_disabled_is_payer_attribution(world, split):
    household_july(world, split)
    result = world.result()
    assert result["owner_attribution"] == "payer"
    assert result["split_shares"] is None
    assert [owner["spending"] for owner in result["observations"][0]["owners"]] == [14700, 3300]


def test_split_with_custom_partner_ids_maps_by_report_slots(world):
    mappings = world.data["account_mappings.json"]
    mappings["partners"] = {"zeta": {"label": "Partner Z"}, "alpha": {"label": "Partner Y"}}
    for binding in mappings["accounts"].values():
        binding["partner_id"] = "alpha" if binding["partner_id"] == "partner_a" else "zeta"
    household_july(world, SPLIT_60_40)
    result = world.result()
    # Sorted ids: alpha = slot a (A accounts), zeta = slot b.
    assert [owner["owner"]["partner_id"] for owner in result["owners"]] == ["alpha", "zeta"]
    assert [owner["spending"] for owner in result["observations"][0]["owners"]] == [11060, 6940]


def test_refund_reduces_burn(world):
    world.data["2026-07_ps_raw.json"]["transactions"].append(transaction(5, A, 2500))
    result = world.result()
    # A 20000 - 2500 refund. Gross basis would keep 20000.
    assert result["observations"][0]["owners"][0]["spending"] == 17500
    assert result["observations"][0]["household_spending"] == 67500
    assert result["owners"][0]["average_monthly_spending"] == pytest.approx(87500 / 3)


def test_negative_net_month_signed_and_negative_average_blocks(world):
    for index, month in enumerate(MONTHS):
        world.data[f"{month}_ps_raw.json"] = complete(month, [
            transaction(index * 10 + 1, A, 500, month), transaction(index * 10 + 2, B, -100, month),
        ])
    result = world.result()
    assert result["included_months"] == MONTHS
    for observation in result["observations"]:
        # A refunds 500, B spends 100. Household -400.
        assert [owner["spending"] for owner in observation["owners"]] == [-500, 100]
        assert observation["household_spending"] == -400
    a, b = result["owners"]
    assert a["average_monthly_spending"] == -500
    assert a["runway_months"] is None
    assert "nonpositive_burn" in codes(a)
    assert b["runway_months"] == 300  # 30000 / 100
    assert result["household"]["average_monthly_spending"] == -400
    assert result["household"]["runway_months"] is None
    assert "nonpositive_burn" in codes(result["household"])


def test_production_error_excludes_only_that_month(runway_client, world):
    # Unmapped category, absent from catalog: Reports raise for July only.
    world.data["2026-07_ps_raw.json"]["transactions"].append(
        transaction(5, A, -100, category={"id": 2100099, "title": "Leakcheck unmapped"}),
    )
    world.write()
    response = runway_client.get("/api/bills/runway")
    assert response.status_code == 200
    result = response.json()
    assert result["included_months"] == MONTHS[1:]
    july = result["observations"][0]
    assert (july["status"], july["coverage"]) == ("excluded", "invalid")
    assert "invalid_source" in codes(july)
    assert "Leakcheck" not in response.text and "2100099" not in response.text
    # Mean of Aug/Sep: A 35000, B 65000.
    assert result["owners"][0]["average_monthly_spending"] == 35000
    assert result["household"]["average_monthly_spending"] == 100000


def test_unexpected_production_failure_is_month_invalid_not_500(runway_client, world, monkeypatch):
    from budget_api.services import report_builder
    original = report_builder.build_contract

    def fail_for_july(transactions, inputs):
        if transactions and transactions[0]["date"].startswith("2026-07"):
            raise RuntimeError("Synthetic failure 123456.78")
        return original(transactions, inputs)

    monkeypatch.setattr(report_builder, "build_contract", fail_for_july)
    response = runway_client.get("/api/bills/runway")
    assert response.status_code == 200
    assert "123456.78" not in response.text
    assert response.json()["included_months"] == MONTHS[1:]


@pytest.mark.parametrize("split", [
    {"enabled": True, "shares": {"partner_a": 50, "partner_b": 40}, "categories": []},
    {"shares": {"partner_a": 60, "partner_b": 40}},
])
def test_invalid_split_config_fails_closed(world, split):
    world.data["split_config.json"] = split
    result = world.result()
    assert result["included_months"] == []
    assert "invalid_source" in codes(result)
    assert result["household"]["average_monthly_spending"] is None


def test_production_reads_snapshot_copies_not_live_sources(world, monkeypatch):
    from budget_api.services import report_builder, runway
    household_july(world, SPLIT_60_40)
    world.write()
    seen = []
    for name in ("load_detailed_section_mapping", "load_category_roles", "load_category_parents",
                 "load_split_config"):
        original = getattr(report_builder, name)

        def spy(path, *args, _original=original, **kwargs):
            seen.append(path)
            return _original(path, *args, **kwargs)

        monkeypatch.setattr(report_builder, name, spy)
    # load(month, path, excluded): month first.
    original_load = report_builder.load
    monkeypatch.setattr(report_builder, "load", lambda month, path, excluded=None: (
        seen.append(path), original_load(month, path, excluded))[1])
    result = runway.calculate_runway(now=NOW).model_dump(mode="json")
    assert result["included_months"] == MONTHS
    assert seen
    live = str(world.root)
    assert all(not str(path).startswith(live) for path in seen)


# --- Review fixes (T038) ---------------------------------------------------


def test_monthly_values_rounded_to_cents_payer(world):
    # Reports float sum: 0.1 + 0.2 = 0.30000000000000004. Runway emits cents.
    world.data["2026-07_ps_raw.json"] = complete("2026-07", [
        transaction(1, A, -0.1), transaction(2, A, -0.2), transaction(3, B, -100),
    ])
    result = world.result()
    july = result["observations"][0]
    a, b = (owner["spending"] for owner in july["owners"])
    assert (a, b) == (0.3, 100)
    assert july["household_spending"] == 100.3
    assert a + b == july["household_spending"]
    # Averages unrounded, from rounded months. A (0.30 + 30000 + 40000) / 3.
    with localcontext() as context:
        context.prec = 700
        expected = float(Decimal("70000.30") / 3)
    assert result["owners"][0]["average_monthly_spending"] == expected


def test_split_rounds_owner_a_then_b_is_household_remainder(world):
    # 50/50 of 100.01 home: each fair share 50.005. Independent rounding gives 100.02.
    household_july(world, {"enabled": True, "shares": {"partner_a": 50, "partner_b": 50}, "categories": ["2100070"]})
    world.data["2026-07_ps_raw.json"] = complete("2026-07", [row(1, A, -100.01, 2100070)])
    result = world.result()
    assert result["owner_attribution"] == "common_economy_split"
    july = result["observations"][0]
    a, b = (owner["spending"] for owner in july["owners"])
    assert july["household_spending"] == 100.01
    assert a in (50.0, 50.01)
    assert b == float(Decimal("100.01") - Decimal(repr(a)))
    # Exact in decimal (float a + b itself adds noise).
    assert Decimal(repr(a)) + Decimal(repr(b)) == Decimal(repr(july["household_spending"]))
    assert all(round(value, 2) == value for value in (a, b))


def _extra_record(original):
    def patched(transactions, inputs):
        contract = original(transactions, inputs)
        if transactions and transactions[0]["date"].startswith("2026-07"):
            records = contract["normalized_transactions"]
            # Reports kept a row runway never indexed.
            records.append({**records[0], "id": "999999"})
        return contract
    return patched


def _missing_slot(original):
    def patched(records, mapping, split, parents):
        spending = original(records, mapping, split, parents)
        if records and records[0]["date"].startswith("2026-07"):
            totals = {key: value for key, value in spending.totals.items() if key != "partner_b"}
            return type(spending)(totals, spending.split, spending.allowed_category_ids)
        return spending
    return patched


def _missing_delta(original):
    def patched(records, mapping, split, parents):
        spending = original(records, mapping, split, parents)
        if records and records[0]["date"].startswith("2026-07") and spending.split is not None:
            rows = [{key: value for key, value in item.items() if key != "delta"} for item in spending.split["rows"]]
            return type(spending)(spending.totals, {**spending.split, "rows": rows}, spending.allowed_category_ids)
        return spending
    return patched


@pytest.mark.parametrize(("name", "patch"), [
    ("build_contract", _extra_record), ("household_spending", _missing_slot), ("household_spending", _missing_delta),
])
def test_reports_shape_disagreement_excludes_only_that_month(runway_client, world, monkeypatch, name, patch):
    from budget_api.services import report_builder
    household_july(world, SPLIT_60_40)
    world.write()
    monkeypatch.setattr(report_builder, name, patch(getattr(report_builder, name)))
    response = runway_client.get("/api/bills/runway")
    assert response.status_code == 200
    result = response.json()
    assert result["included_months"] == MONTHS[1:]
    july = result["observations"][0]
    assert (july["status"], july["coverage"]) == ("excluded", "invalid")
    assert "invalid_source" in codes(july)


def test_scratch_removed_and_list_months_not_copied_twice(world, monkeypatch):
    import tempfile
    from budget_api.services import runway
    scratch_root = world.root.parent / "scratch-root"
    scratch_root.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch_root))
    for index, month in enumerate(MONTHS):
        world.data[f"{month}_ps_raw.json"] = pocketsmith_month(month, index)  # bare list
    world.write()
    copies = []
    original = tempfile.NamedTemporaryFile
    monkeypatch.setattr(tempfile, "NamedTemporaryFile", lambda *a, **k: (copies.append(k), original(*a, **k))[1])
    result = runway.calculate_runway(now=NOW).model_dump(mode="json")
    assert result["included_months"] == MONTHS
    assert copies == []  # Wrapped once in runway scratch. No second temp copy.
    assert list(scratch_root.iterdir()) == []


def test_scratch_dir_ignores_cleanup_errors(world, monkeypatch):
    import tempfile
    from budget_api.services import runway
    seen = []
    original = tempfile.TemporaryDirectory
    monkeypatch.setattr(tempfile, "TemporaryDirectory", lambda *a, **k: (seen.append(k), original(*a, **k))[1])
    world.write()
    runway.calculate_runway(now=NOW)
    assert seen and all(k.get("ignore_cleanup_errors") is True for k in seen)


def test_scratch_oserror_is_global_invalid_source(runway_client, monkeypatch):
    import tempfile

    def broken(*args, **kwargs):
        raise OSError("Synthetic disk full /secret/path")

    monkeypatch.setattr(tempfile, "TemporaryDirectory", broken)
    response = runway_client.get("/api/bills/runway")
    assert response.status_code == 200
    assert "secret" not in response.text
    result = response.json()
    assert "invalid_source" in codes(result)
    assert result["included_months"] == []
    assert result["household"]["runway_months"] is None


def _custom_partners(world, partners, owner_of):
    mappings = world.data["account_mappings.json"]
    mappings["partners"] = {key: {"label": f"Synthetic {key}"} for key in partners}
    for account, binding in mappings["accounts"].items():
        binding["partner_id"] = owner_of(account, binding["partner_id"])


def test_owner_slot_comes_from_reports_slot_map(world):
    from budget_api.services import report_builder
    # Excluded account names a third id. Reports pool = alpha, beta, gamma -> alpha a, beta b.
    _custom_partners(world, ["beta", "gamma"], lambda _, owner: "beta" if owner == "partner_a" else "gamma")
    world.data["account_mappings.json"]["accounts"]["1100050"] = {
        "partner_id": "alpha", "type": "checking", "excluded": True,
    }
    slots = report_builder.partner_slot_map(world.data["account_mappings.json"])
    assert slots == {"alpha": "partner_a", "beta": "partner_b"}
    result = world.result()
    assert {o["owner"]["partner_id"]: o["owner"]["partner_slot"] for o in result["owners"]} == {"beta": "b", "gamma": ""}


def test_split_enabled_but_one_owner_mapped_is_payer(world):
    household_july(world, SPLIT_60_40)
    _custom_partners(world, ["solo"], lambda *_: "solo")
    result = world.result()
    assert [o["owner"]["partner_slot"] for o in result["owners"]] == ["a"]
    assert result["owner_attribution"] == "payer"
    assert result["split_shares"] is None
    july = result["observations"][0]
    assert july["status"] == "included"
    assert [owner["spending"] for owner in july["owners"]] == [18000]
    assert july["household_spending"] == 18000
