"""Synthetic tests for generic normalized report accounting."""

import argparse
import json
import multiprocessing
import os
import sys
import types
from pathlib import Path

import pytest

from accounting import (
    AccountingValidationError,
    build_month_contract,
    load_detailed_section_mapping,
    load_account_owners,
    load_partner_labels,
    normalize_transactions,
    savings_account_ids_from_mapping,
)
from accounting_html import _REPORT_STYLES, _transaction_drilldowns, render
import build
from build import main as build_main
from charts import render_horizontal_bar, render_vertical_bar

OWNERS = {
    "account-a": "partner_a",
    "account-b": "partner_b",
    "source-account": "partner_a",
}


DETAILED_SECTION_MAPPING = {
    "category_sections": {
        "income": "income_salary",
        "savings": "savings",
        "home": "home",
        "common": "common",
        "personal_a": "personal_partner_a",
        "personal_b": "personal_partner_b",
        "trip": "trips",
        "excluded": "excluded",
    },
    "account_roles": {
        "account-a": "savings_partner_a",
        "account-b": "savings_partner_b",
    },
}


def _transaction(transaction_id, amount, category, account_id="account-a", **extra):
    return {
        "id": transaction_id,
        "date": "2030-04-01",
        "amount": amount,
        "account": {"id": account_id},
        "category": category,
        **extra,
    }


def _hold_publisher_lock(output_dir, output_name, ready, release):
    import build as child_build

    child_build.PUBLISHED_OUTPUT_DIR = Path(output_dir)
    with child_build._publisher_lock(output_name):
        ready.set()
        release.wait(10)


def _mock_pdf_renderer(monkeypatch):
    class PdfHTML:
        def __init__(self, filename):
            self.filename = filename

        def write_pdf(self, target):
            Path(target).write_bytes(b"%PDF-test")

    monkeypatch.setitem(sys.modules, "weasyprint", types.SimpleNamespace(HTML=PdfHTML))


def test_mixed_debit_and_credit_use_generic_paid_received_net():
    category = {"id": "groceries", "title": "Groceries"}
    contract = build_month_contract(
        [_transaction(1, -100, category), _transaction(2, 40, category, "account-b")],
        OWNERS,
    )

    groceries = contract["categories"][0]
    assert (groceries["paid"], groceries["received"], groceries["net"]) == (100, 40, 60)
    assert groceries["owners"]["partner_a"]["net"] == 100
    assert groceries["owners"]["partner_b"]["net"] == -40


def test_explicit_category_roles_build_original_kpi_semantics():
    income = {"id": "income", "title": "Income"}
    savings = {"id": "savings", "title": "Savings"}
    spend = {"id": "spend", "title": "Spend"}
    excluded = {"id": "excluded", "title": "Excluded"}
    contract = build_month_contract(
        [
            _transaction(1, 100, income, "source-account"),
            _transaction(2, -25, spend),
            _transaction(3, -10, savings, "account-b"),
            _transaction(4, -20, excluded, "account-b"),
        ],
        OWNERS,
        {
            "income": "income",
            "savings": "savings",
            "spend": "personal_spend",
            "excluded": "exclude",
        },
    )

    # savings_summary uses account_roles from detailed_section_mapping; none
    # provided here so no savings movement is recognized (net_savings 0).
    assert contract["kpis"]["total"] == {
        "income": 100.0,
        "real_spend": 25.0,
        "personal_spend": 25.0,
        "net_cash": 75.0,
        "net_cash_class": "pos",
        "net_savings": 0.0,
        "investment": 0.0,
    }
    assert contract["kpis"]["partner_b"]["net_savings"] == 0.0


def test_savings_kpi_uses_explicit_savings_account_transactions():
    income = {"id": "income", "title": "Income"}
    savings = {"id": "savings", "title": "Savings"}
    # savings_summary now derives savings flows from account_roles in the
    # detailed section mapping; savings_account_ids is no longer consulted.
    mapping = {
        "category_sections": {
            "income": "income_salary",
            "savings": "savings",
        },
        "account_roles": {
            "account-a": "savings_partner_a",
            "account-b": "savings_partner_b",
        },
    }
    contract = build_month_contract(
        [
            _transaction(1, 100, income, "source-account"),
            _transaction(2, 15, savings, "account-a"),
            _transaction(3, 26, savings, "account-b"),
            _transaction(4, -10, savings, "account-a"),
        ],
        OWNERS,
        {"income": "income", "savings": "savings"},
        detailed_section_mapping=mapping,
    )

    # Savings-category records on savings accounts add to kron_net, which is
    # then folded into to_savings: partner_a in 15 + |-10|=5 -> 20, out 10;
    # partner_b in 26 + |26|=52. Net saved = 20-10=10 / 52-0=52 / 62 total.
    assert contract["kpis"]["partner_a"]["net_savings"] == 10.0
    assert contract["kpis"]["partner_b"]["net_savings"] == 52.0
    assert contract["kpis"]["total"]["net_savings"] == 62.0


def test_cover_savings_matches_section_two_and_ignores_savings_account_noise():
    categories = {
        "income": {"id": "income", "title": "Salary"},
        "savings": {"id": "savings", "title": "Savings movement"},
        "common": {"id": "common", "title": "Common"},
        "personal_a": {"id": "personal_a", "title": "Personal"},
        "trip": {"id": "trip", "title": "Trip"},
        "excluded": {"id": "excluded", "title": "CC Payment (paired)"},
    }
    transactions = [
        _transaction(1, 80000, categories["income"], "account-a", payee="Salary noise"),
        _transaction(
            2, -26723.46, categories["common"], "account-a", payee="Mortgage noise"
        ),
        _transaction(
            3, -4000, categories["common"], "account-b", payee="Purchase noise"
        ),
        _transaction(4, -16000, categories["savings"], "account-a", payee="Savings A"),
        _transaction(5, -26000, categories["savings"], "account-b", payee="Savings B"),
        _transaction(
            6,
            -1200,
            categories["excluded"],
            "account-a",
            is_transfer=True,
            payee="Card payment noise",
        ),
        _transaction(
            7, -10, categories["personal_a"], "account-a", payee="Personal noise"
        ),
        _transaction(8, -20, categories["trip"], "account-b", payee="Trip noise"),
    ]
    contract = build_month_contract(
        transactions,
        OWNERS,
        {
            category_id: "income" if category_id == "income" else "spend"
            for category_id in categories
        },
        detailed_section_mapping=DETAILED_SECTION_MAPPING,
    )

    html = render(
        contract,
        "2030-04",
        {"partner_a": "Fixture A", "partner_b": "Fixture B"},
    )
    cover = html[: html.index("1. Income")]
    savings_section = html[html.index("2. Savings") : html.index("3. Home")]

    # account_roles on account-a/b make every txn on those accounts count as
    # savings flow, so the income/common/personal "noise" now contributes;
    # net_savings reflects all account-a/b movement, not just savings category.
    assert contract["kpis"]["total"]["net_savings"] == 48046.54
    assert 'Net savings</span><span class="metric-value">48,046.54' in cover
    assert "Net movement" in cover
    assert (
        "<td>Household</td><td>122,000.00</td><td>73,953.46</td><td>48,046.54</td>"
        in savings_section
    )
    assert "Fixture A net" in html
    assert "Fixture B net" in html
    assert "Fixture A paid" in html
    assert "Fixture B paid" in html
    assert "FxA net" not in html
    assert "FxB net" not in html


def test_income_and_excluded_headers_use_configured_partner_labels():
    contract = build_month_contract(
        [
            _transaction(1, 100, {"id": "income", "title": "Income"}),
            _transaction(
                2,
                -25,
                {"id": "excluded", "title": "Internal transfer"},
                "account-b",
                is_transfer=True,
            ),
        ],
        OWNERS,
        detailed_section_mapping=DETAILED_SECTION_MAPPING,
    )

    html = render(
        contract,
        "2030-04",
        {"partner_a": "Alex", "partner_b": "Blair"},
    )

    assert "<th>% Alex</th><th>% Blair</th>" in html
    assert "<th>Alex paid</th><th>Blair paid</th>" in html
    assert "<b>% Alex</b> = Alex&apos;s amount" in html
    assert "<b>% Blair</b> = Blair&apos;s amount" in html
    assert "% FxA" not in html
    assert "% FxB" not in html
    assert "FxA paid" not in html
    assert "FxB paid" not in html


def test_unified_mapping_supplies_default_report_owners_and_labels(
    tmp_path, monkeypatch
):
    mapping_path = tmp_path / "account_mappings.json"
    mapping_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "partners": {
                    "partner_a": {"label": "Alex"},
                    "partner_b": {"label": "Blair"},
                },
                "accounts": {
                    "account-a": {
                        "name": "Account A",
                        "owner": "partner_a",
                        "excluded": False,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("accounting.PRIVATE_ACCOUNT_MAPPING", mapping_path)

    assert load_account_owners() == {"account-a": "partner_a"}
    assert load_partner_labels() == {"partner_a": "Alex", "partner_b": "Blair"}


def test_transaction_drilldown_escapes_configured_owner_label():
    html = _transaction_drilldowns(
        [
            {
                "id": "transaction-1",
                "date": "2030-04-01",
                "amount": -10.0,
                "category_path": [{"id": "common", "title": "Common"}],
                "is_transfer": False,
                "owner": "partner_a",
                "payee": "Shop",
                "note": None,
            }
        ],
        {"partner_a": '<img src=x onerror="alert(1)">', "partner_b": "Partner B"},
    )

    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in html
    assert '<img src=x onerror="alert(1)">' not in html


def test_savings_section_uses_historical_table_and_account_cards():
    income = {"id": "income", "title": "Salary (Fixture A)"}
    savings = {"id": "savings", "title": "Sparekonto (Fixture A)"}
    transactions = [
        _transaction(1, 100, income, "account-a"),
        _transaction(2, -25, savings, "account-a", payee="Transfer in"),
        _transaction(3, 5, savings, "account-a", payee="Transfer out"),
    ]
    transactions[1]["account"]["name"] = "FxA Check Handelsbanken"
    transactions[2]["account"]["name"] = "FxA Check Handelsbanken"
    contract = build_month_contract(
        transactions,
        OWNERS,
        {"income": "income", "savings": "savings"},
        detailed_section_mapping=DETAILED_SECTION_MAPPING,
    )

    html = render(contract, "2030-04")

    assert "To savings (in)" in html
    assert "From savings (out)" in html
    assert "Savings rate" in html
    assert "Household" in html
    assert "Sparekonto (Fixture A) - 30.00 NOK - 2 txns" in html
    assert "FxA Check Handelsbanken" in html


def test_home_section_nets_paired_reimbursement_marked_as_transfer():
    home = {"id": "home", "title": "Home"}
    transactions = [
        _transaction(1, 100, home, "account-a", is_transfer=True),
        _transaction(2, -100, home, "account-b", is_transfer=True),
    ]
    contract = build_month_contract(
        transactions, OWNERS, detailed_section_mapping=DETAILED_SECTION_MAPPING
    )

    html = render(contract, "2030-04")

    assert "Home (paired reimbursement)" in html
    assert "+100.00" in html
    assert "-100.00" in html
    assert "net 0 (paired)" not in html
    assert "Paired reimbursements (net 0, shown for transparency)" in html
    # Sign classes mirror the React DTO: recipient pos, payer neg, total zero.
    assert '<td class="pos">+100.00</td>' in html
    assert '<td class="neg">-100.00</td>' in html
    assert '<td class="zero"><b>0.00</b></td>' in html
    # Paired rows live in a separate transparency table BELOW the category
    # table + note (React parity), not inline in the category table.
    home_section = html.split("<h2>3. Home")[1].split("</section>")[0]
    assert home_section.index("</table>") < home_section.index(
        "Paired reimbursements"
    )
    assert home_section.index("The Home reimbursement rows") < home_section.index(
        "Home (paired reimbursement)"
    )
    assert html.index("Home (paired reimbursement)") < html.index(
        "9. Excluded (Internal transfers)"
    )
    assert html.count("Home (paired reimbursement)") == 1


def test_fallback_styles_color_paired_sign_classes():
    # The _REPORT_STYLES fallback (used when report-shared.scss is missing)
    # must carry the same .legacy-table sign-color rules, or the paired
    # reimbursement table loses its green/red/muted cell coloring.
    for rule in (
        ".legacy-table .pos { color: #2ca02c; }",
        ".legacy-table .neg { color: #d62728; }",
        ".legacy-table .zero { color: #888; }",
    ):
        assert rule in _REPORT_STYLES


@pytest.mark.parametrize(
    ("category", "payee"),
    [
        ({"id": "income", "title": "Mapped income"}, "Income transfer marker"),
        ({"id": "common", "title": "Mapped common"}, "Common transfer marker"),
        (
            {"id": "personal_a", "title": "Mapped personal"},
            "Personal transfer marker",
        ),
        (
            {"id": "personal_b", "title": "Mapped personal"},
            "Other personal transfer marker",
        ),
        ({"id": "trip", "title": "Mapped trip"}, "Trip transfer marker"),
    ],
)
def test_mapped_transfers_render_only_in_excluded(category, payee):
    contract = build_month_contract(
        [_transaction(1, -50, category, is_transfer=True, payee=payee)],
        OWNERS,
        detailed_section_mapping=DETAILED_SECTION_MAPPING,
    )

    html = render(contract, "2030-04")

    assert html.count(payee) == 1
    assert html.index(payee) > html.index("9. Excluded (Internal transfers)")
    # No pairings anywhere -> no transparency table must be emitted at all.
    assert "Paired reimbursements (net 0, shown for transparency)" not in html


def test_common_section_renders_multiple_paired_reimbursements_in_one_table():
    dining = {"id": "common", "title": "Dining"}
    groceries = {"id": "common_extra", "title": "Groceries X"}
    mapping = {
        **DETAILED_SECTION_MAPPING,
        "category_sections": {
            **DETAILED_SECTION_MAPPING["category_sections"],
            "common_extra": "common",
        },
    }
    transactions = [
        # Dining pair: partner_a paid 200, partner_b received 200 back.
        _transaction(1, -200, dining, "account-a"),
        _transaction(2, 200, dining, "account-b"),
        # Groceries X pair: partner_b paid 300, partner_a received 300 back.
        _transaction(3, -300, groceries, "account-b"),
        _transaction(4, 300, groceries, "account-a"),
    ]
    contract = build_month_contract(
        transactions, OWNERS, detailed_section_mapping=mapping
    )

    html = render(contract, "2030-04")

    common_section = html.split("<h2>4. Common")[1].split("</section>")[0]
    # Both pairs sit in the single transparency table below the category table.
    assert common_section.count('class="reimb-row"') == 2
    block = common_section.split(
        "Paired reimbursements (net 0, shown for transparency)"
    )[1].split("</table>")[0]
    assert "Dining (paired reimbursement)" in block
    assert "Groceries X (paired reimbursement)" in block
    assert '<td class="neg">-200.00</td>' in block  # partner_a paid
    assert '<td class="pos">+200.00</td>' in block  # partner_b received
    assert '<td class="pos">+300.00</td>' in block  # partner_a received
    assert '<td class="neg">-300.00</td>' in block  # partner_b paid
    assert block.count('<td class="zero"><b>0.00</b></td>') == 2
    # Fully-paired categories still skip their zero-net category row.
    assert "Dining</td>" not in common_section
    assert "Groceries X</td>" not in common_section


def test_cc_payments_use_private_stable_leaf_category_id():
    cc_payment = {"id": "34025345", "title": "CC Payment (paired)"}
    transactions = [
        _transaction(1, -600, cc_payment, "account-a", payee="Fixture A CC payment"),
        _transaction(2, -900, cc_payment, "account-b", payee="Fixture B CC payment"),
        _transaction(3, 1_500, cc_payment, "account-a", payee="Paired receiving leg"),
        _transaction(
            4,
            75,
            {"id": "common", "title": "Common"},
            "account-a",
            payee="Arbitrary CC credit",
        ),
        _transaction(
            5,
            -75,
            {"id": "excluded", "title": "Other transfer"},
            "account-a",
            is_transfer=True,
            payee="Other internal transfer",
        ),
    ]
    contract = build_month_contract(
        transactions,
        OWNERS,
        detailed_section_mapping={
            "category_sections": {
                "34025345": "cc_payments",
                "common": "common",
                "excluded": "excluded",
            },
            "account_roles": {},
        },
    )

    html = render(contract, "2030-04", {"partner_a": "Fixture A", "partner_b": "Fixture B"})
    cc_start = html.index("8. CC Payments")
    excluded_start = html.index("9. Excluded (Internal transfers)")
    cc_section = html[cc_start:excluded_start]
    excluded_section = html[excluded_start:]

    assert "<td>Fixture A</td><td>600.00</td>" in cc_section
    assert "<td>Fixture B</td><td>900.00</td>" in cc_section
    assert "<td>Household</td><td>1,500.00</td>" in cc_section
    assert "Fixture A CC payment" in cc_section
    assert "Fixture B CC payment" in cc_section
    assert "Paired receiving leg" not in cc_section
    assert "Arbitrary CC credit" not in cc_section
    assert "inflow" not in cc_section.lower()
    assert "CC Payment (paired)" not in excluded_section
    assert "Fixture A CC payment" not in excluded_section
    assert "Fixture B CC payment" not in excluded_section
    assert "Paired receiving leg" not in excluded_section
    assert "Other internal transfer" in excluded_section


def test_credit_card_purchases_stay_in_their_mapped_sections(tmp_path):
    mapping_path = tmp_path / "detailed-section-map.json"
    mapping_path.write_text(
        json.dumps(
            {
                "category_sections": {
                    "common": "common",
                    "personal_a": "personal_partner_a",
                    "excluded": "excluded",
                    "34025345": "cc_payments",
                },
                "account_roles": {"credit-card": "credit_card"},
            }
        ),
        encoding="utf-8",
    )
    mapping = load_detailed_section_mapping(mapping_path)
    contract = build_month_contract(
        [
            _transaction(
                1,
                -20,
                {"id": "common", "title": "Common"},
                "credit-card",
                payee="Common card purchase",
            ),
            _transaction(
                2,
                -30,
                {"id": "personal_a", "title": "Personal"},
                "credit-card",
                payee="Personal card purchase",
            ),
            _transaction(
                3,
                50,
                {"id": "common", "title": "Common"},
                "credit-card",
                payee="CC refund",
            ),
            _transaction(
                4,
                75,
                {"id": "common", "title": "Common"},
                "account-a",
                payee="Non-CC credit",
            ),
            _transaction(
                5,
                -50,
                {"id": "34025345", "title": "CC Payment (paired)"},
                "account-a",
                payee="CC payment",
            ),
            _transaction(
                6,
                50,
                {"id": "34025345", "title": "CC Payment (paired)"},
                "credit-card",
                payee="Paired CC receiving leg",
            ),
            _transaction(
                7,
                -50,
                {"id": "excluded", "title": "Other transfer"},
                "account-a",
                is_transfer=True,
                payee="Non-CC transfer",
            ),
        ],
        OWNERS | {"credit-card": "partner_a"},
        detailed_section_mapping=mapping,
    )

    html = render(contract, "2030-04", {"partner_a": "Fixture A", "partner_b": "Fixture B"})
    common_start = html.index("4. Common")
    personal_start = html.index("5. Fixture A")
    cc_start = html.index("8. CC Payments")
    excluded_start = html.index("9. Excluded")

    assert common_start < html.index("Common card purchase") < personal_start
    assert personal_start < html.index("Personal card purchase") < cc_start
    assert common_start < html.index("CC refund") < personal_start
    assert cc_start < html.index("CC payment") < excluded_start
    assert "Paired CC receiving leg" not in html[cc_start:excluded_start]
    assert "Non-CC credit" not in html[cc_start:excluded_start]
    assert html.index("Non-CC transfer") > excluded_start


def test_summary_cards_wrap_with_a4_safe_minimum_width():
    html = render(build_month_contract([], OWNERS, category_roles={}), "2030-04")

    assert ".summary { display: flex; flex-wrap: wrap;" in html
    assert "flex: 1 1 30%; min-width: 0;" in html
    assert 'Net savings</span><span class="metric-value">0.00' in html


def test_savings_account_roles_define_default_kpi_accounts():
    mapping = {
        "category_sections": {},
        "account_roles": {
            "saving-a": "savings_partner_a",
            "saving-b": "savings_partner_b",
            "credit-card": "credit_card",
        },
    }

    assert savings_account_ids_from_mapping(mapping) == {"saving-a", "saving-b"}


def test_normalized_credit_card_credit_does_not_route_to_cc_payments(tmp_path):
    mapping_path = tmp_path / "detailed-section-map.json"
    mapping_path.write_text(
        json.dumps(
            {
                "category_sections": {"common": "common", "34025345": "excluded"},
                "account_roles": {
                    "5245500": "credit_card",
                    "5376195": "credit_card",
                },
            }
        ),
        encoding="utf-8",
    )
    from accounting import load_detailed_section_mapping

    transactions = [
        {
            "id": 1,
            "date": "2030-04-01",
            "amount": 100,
            "transaction_account": {
                "id": "5376195",
                "account_id": "5245500",
                "name": "Renamed Fixture B account",
            },
            "category": {"id": "common", "title": "Common"},
            "payee": "Fixture B arbitrary CC credit",
        }
    ]
    account_owners = {"5376195": "partner_b"}
    contract = build_month_contract(
        transactions,
        account_owners,
        detailed_section_mapping=load_detailed_section_mapping(mapping_path),
    )

    html = render(contract, "2030-04")

    assert (
        normalize_transactions(transactions, account_owners)[0]["account_id"]
        == "5376195"
    )
    cc_start = html.index("8. CC Payments")
    excluded_start = html.index("9. Excluded (Internal transfers)")
    assert "Fixture B arbitrary CC credit" not in html[cc_start:excluded_start]


def test_cli_account_owner_map_overrides_default_local_mapping(tmp_path, monkeypatch):
    data_path = tmp_path / "sample_apr_2030.json"
    owner_map_path = tmp_path / "owners.json"
    section_map_path = tmp_path / "sections.json"
    data_path.write_text(
        json.dumps(
            {
                "transactions": [
                    _transaction(
                        1, -100, {"id": "common", "title": "Common"}, "local-account"
                    )
                ]
            }
        ),
        encoding="utf-8",
    )
    owner_map_path.write_text(
        json.dumps({"local-account": "partner_b"}), encoding="utf-8"
    )
    section_map_path.write_text(
        json.dumps(
            {"category_sections": {"common": "common"}, "account_roles": {}},
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"
    monkeypatch.setattr(build, "PUBLISHED_OUTPUT_DIR", output_dir)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build.py",
            "--month",
            "2030-04",
            "--data-dir",
            str(data_path.parent),
            "--input-kind",
            "synthetic",
            "--account-owner-map",
            str(owner_map_path),
            "--detailed-section-map",
            str(section_map_path),
            "--name",
            "custom-report",
        ],
    )

    _mock_pdf_renderer(monkeypatch)
    assert build_main() == 0
    assert (output_dir / "custom-report.html").exists()
    assert (output_dir / "custom-report.pdf").read_bytes().startswith(b"%PDF-")


def test_cli_defaults_to_fixed_output_directory(tmp_path, monkeypatch):
    assert build.REPOSITORY_ROOT == Path(build.__file__).resolve().parents[2]
    assert build.PUBLISHED_OUTPUT_DIR == build.REPOSITORY_ROOT / "out"
    data_path = tmp_path / "sample_apr_2030.json"
    owner_map_path = tmp_path / "owners.json"
    section_map_path = tmp_path / "sections.json"
    data_path.write_text(
        json.dumps(
            {
                "transactions": [
                    _transaction(
                        1,
                        -100,
                        {"id": "common", "title": "Common"},
                        "local-account",
                    )
                ]
            }
        ),
        encoding="utf-8",
    )
    owner_map_path.write_text(
        json.dumps({"local-account": "partner_a"}), encoding="utf-8"
    )
    section_map_path.write_text(
        json.dumps(
            {"category_sections": {"common": "common"}, "account_roles": {}},
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "repository-out" / "out"
    monkeypatch.setattr(build, "PUBLISHED_OUTPUT_DIR", output_dir)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build.py",
            "--month",
            "2030-04",
            "--data-dir",
            str(data_path.parent),
            "--input-kind",
            "synthetic",
            "--account-owner-map",
            str(owner_map_path),
            "--detailed-section-map",
            str(section_map_path),
        ],
    )

    _mock_pdf_renderer(monkeypatch)
    assert build_main() == 0
    assert (output_dir / "203004_partner_report.html").exists()
    assert (output_dir / "203004_partner_report.pdf").exists()


def test_cli_rejects_output_directory_override(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build.py",
            "--month",
            "2030-04",
            "--data-dir",
            "input-dir",
            "--input-kind",
            "synthetic",
            "--output-dir",
            "elsewhere",
        ],
    )

    with pytest.raises(SystemExit, match="2"):
        build_main()


def test_documented_synthetic_quick_start_emits_report_without_private_files(
    tmp_path, monkeypatch
):
    repository = Path(__file__).resolve().parents[3]
    missing_private_map = tmp_path / "missing-private-map.json"
    monkeypatch.setattr("accounting.PRIVATE_ACCOUNT_MAPPING", missing_private_map)
    output_dir = tmp_path / "out"
    monkeypatch.setattr(build, "PUBLISHED_OUTPUT_DIR", output_dir)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build.py",
            "--month",
            "2026-04",
            "--data-dir",
            str(repository / "data"),
            "--input-kind",
            "synthetic",
            "--detailed-section-map",
            str(repository / "data" / "sample_apr_2026_detailed_section_mapping.json"),
        ],
    )

    _mock_pdf_renderer(monkeypatch)
    assert build_main() == 0
    output_path = output_dir / "202604_partner_report.html"
    assert output_path.stat().st_size > 0

    html = output_path.read_text(encoding="utf-8")
    cc_start = html.index("8. CC Payments")
    excluded_start = html.index("9. Excluded")
    cc_section = html[cc_start:excluded_start]
    excluded_section = html[excluded_start:]

    # The public synthetic fixture's original Test A/B txns route to Common
    # only (no internal transfers), so they never render in CC Payments or
    # Excluded. Extended coverage rows use distinct category titles (Test CC
    # Payment / Test Excluded) so this stays true after the PR1 fixture
    # extension, which also gives Excluded real content instead of the
    # former "no items" placeholder.
    assert "Test A" not in cc_section
    assert "Test B" not in cc_section
    assert "Test A" not in excluded_section
    assert "Test B" not in excluded_section
    assert "Test Excluded" in excluded_section
    assert "Test A" in html
    assert "Test B" in html


def test_cli_uses_configured_partner_labels_and_savings_account_roles(
    tmp_path, monkeypatch
):
    data_path = tmp_path / "sample_apr_2030.json"
    owner_map_path = tmp_path / "owners.json"
    role_map_path = tmp_path / "roles.json"
    section_map_path = tmp_path / "sections.json"
    label_map_path = tmp_path / "labels.json"
    data_path.write_text(
        json.dumps(
            {
                "transactions": [
                    _transaction(
                        1, 100, {"id": "income", "title": "Income"}, "income-account"
                    ),
                    _transaction(
                        2,
                        -25,
                        {"id": "savings", "title": "Savings"},
                        "savings-account",
                        is_transfer=True,
                    ),
                ]
            }
        ),
        encoding="utf-8",
    )
    owner_map_path.write_text(
        json.dumps({"income-account": "partner_a", "savings-account": "partner_a"}),
        encoding="utf-8",
    )
    role_map_path.write_text(
        json.dumps({"income": "income", "savings": "savings"}), encoding="utf-8"
    )
    section_map_path.write_text(
        json.dumps(
            {
                "category_sections": {"income": "income_salary", "savings": "savings"},
                "account_roles": {"savings-account": "savings_partner_a"},
            }
        ),
        encoding="utf-8",
    )
    label_map_path.write_text(
        json.dumps({"partner_a": "Alex", "partner_b": "Blair"}), encoding="utf-8"
    )
    output_dir = tmp_path / "out"
    monkeypatch.setattr(build, "PUBLISHED_OUTPUT_DIR", output_dir)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build.py",
            "--month",
            "2030-04",
            "--data-dir",
            str(data_path.parent),
            "--input-kind",
            "synthetic",
            "--account-owner-map",
            str(owner_map_path),
            "--category-role-map",
            str(role_map_path),
            "--detailed-section-map",
            str(section_map_path),
            "--partner-label-map",
            str(label_map_path),
        ],
    )

    _mock_pdf_renderer(monkeypatch)
    assert build_main() == 0
    html = (output_dir / "203004_partner_report.html").read_text(encoding="utf-8")
    assert "Alex" in html
    assert "Blair" in html
    # savings -25 is the only savings-account leg; it is both a savings-category
    # record (kron_net) and a savings-account outflow, so to_savings and
    # from_savings cancel and net_saved is 0.
    assert 'Net savings</span><span class="metric-value">0.00' in html


def test_publish_rejects_invalid_pdf_before_final_pair(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    monkeypatch.setattr(build, "PUBLISHED_OUTPUT_DIR", output_dir)
    monkeypatch.chdir(tmp_path)

    class InvalidPdfHTML:
        def __init__(self, filename):
            self.filename = filename

        def write_pdf(self, target):
            Path(target).write_bytes(b"not a PDF")

    monkeypatch.setitem(
        sys.modules, "weasyprint", types.SimpleNamespace(HTML=InvalidPdfHTML)
    )
    with pytest.raises(RuntimeError, match="valid PDF"):
        build._publish_report("<p>report</p>", "report")

    assert not (output_dir / "report.html").exists()
    assert not (output_dir / "report.pdf").exists()


def test_pdf_publish_failure_restores_prior_v4_pair(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    monkeypatch.setattr(build, "PUBLISHED_OUTPUT_DIR", output_dir)
    monkeypatch.chdir(tmp_path)
    output_dir.mkdir(parents=True)
    final_html = output_dir / "report.html"
    final_pdf = output_dir / "report.pdf"
    final_html.write_text("old html", encoding="utf-8")
    final_pdf.write_bytes(b"old pdf")
    real_replace = os.replace

    class PdfHTML:
        def __init__(self, filename):
            self.filename = filename

        def write_pdf(self, target):
            Path(target).write_bytes(b"%PDF-new")

    def fail_staged_pdf_publish(source, destination):
        if (
            Path(source).name == final_pdf.name
            and Path(source).parent.name.startswith(".v4-stage-")
            and Path(destination).resolve() == final_pdf
        ):
            raise OSError("forced second publish failure")
        real_replace(source, destination)

    monkeypatch.setitem(sys.modules, "weasyprint", types.SimpleNamespace(HTML=PdfHTML))
    monkeypatch.setattr(build.os, "replace", fail_staged_pdf_publish)
    with pytest.raises(OSError, match="forced second publish failure"):
        build._publish_report("<p>report</p>", "report")

    assert final_html.read_text(encoding="utf-8") == "old html"
    assert final_pdf.read_bytes() == b"old pdf"


@pytest.mark.parametrize(
    "output_name",
    [
        "../report",
        "..\\report",
        "/report",
        "C:\\report",
        ".",
        "..",
        "report.html",
        "report name",
        "report\tname",
        "",
    ],
)
def test_cli_rejects_unsafe_output_basename(monkeypatch, output_name):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build.py",
            "--month",
            "2030-04",
            "--data-dir",
            "input-dir",
            "--input-kind",
            "synthetic",
            "--name",
            output_name,
        ],
    )

    with pytest.raises(SystemExit, match="2"):
        build_main()


@pytest.mark.parametrize(
    ("input_kind", "source_name", "source_content", "error_text"),
    [
        ("synthetic", None, None, "Required month 2030-04 is missing"),
        (
            "live",
            "2030-04_ps_raw.json",
            "not json",
            "Required month 2030-04 is invalid",
        ),
    ],
)
def test_cli_rejects_invalid_month_input_before_output_publish(
    tmp_path, monkeypatch, input_kind, source_name, source_content, error_text
):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    if source_name:
        (data_dir / source_name).write_text(source_content, encoding="utf-8")
    output_dir = tmp_path / "out"
    monkeypatch.setattr(build, "PUBLISHED_OUTPUT_DIR", output_dir)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build.py",
            "--month",
            "2030-04",
            "--data-dir",
            str(data_dir),
            "--input-kind",
            input_kind,
        ],
    )

    with pytest.raises(SystemExit, match="2"):
        build_main()

    assert not output_dir.exists()


def test_publish_rejects_unsafe_output_basename(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "PUBLISHED_OUTPUT_DIR", tmp_path / "out")

    with pytest.raises(argparse.ArgumentTypeError, match="extensionless basename"):
        build._publish_report("<p>report</p>", "../report")


@pytest.mark.parametrize("output_name", ["_report", "-report", "_-report"])
def test_output_basename_accepts_leading_safe_punctuation(output_name):
    assert build._output_basename(output_name) == output_name


def test_publisher_lock_times_out_during_cross_process_contention(
    tmp_path, monkeypatch
):
    output_dir = tmp_path / "out"
    monkeypatch.setattr(build, "PUBLISHED_OUTPUT_DIR", output_dir)
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    release = context.Event()
    holder = context.Process(
        target=_hold_publisher_lock,
        args=(str(output_dir), "report", ready, release),
    )
    holder.start()
    try:
        assert ready.wait(5)
        with pytest.raises(
            RuntimeError, match="Timed out waiting 0.1s for publisher lock for 'report'"
        ):
            with build._publisher_lock("report", timeout_seconds=0.1):
                pass
    finally:
        release.set()
        holder.join(10)
    assert holder.exitcode == 0


def test_publisher_lock_releases_after_context_exit(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "PUBLISHED_OUTPUT_DIR", tmp_path / "out")

    with build._publisher_lock("report", timeout_seconds=0.1):
        pass
    with build._publisher_lock("report", timeout_seconds=0.1):
        pass


def test_publish_manifest_references_immutable_html_pdf_pair(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    monkeypatch.setattr(build, "PUBLISHED_OUTPUT_DIR", output_dir)

    class PdfHTML:
        def __init__(self, filename):
            self.filename = filename

        def write_pdf(self, target):
            Path(target).write_bytes(b"%PDF-new")

    monkeypatch.setitem(sys.modules, "weasyprint", types.SimpleNamespace(HTML=PdfHTML))
    final_html, final_pdf = build._publish_report("<p>report</p>", "report")
    manifest = json.loads(
        (output_dir / "report.manifest.json").read_text(encoding="utf-8")
    )
    immutable_html = output_dir / manifest["html"]
    immutable_pdf = output_dir / manifest["pdf"]

    assert final_html.read_text(encoding="utf-8") == immutable_html.read_text(
        encoding="utf-8"
    )
    assert final_pdf.read_bytes() == immutable_pdf.read_bytes()
    assert immutable_pdf.read_bytes().startswith(b"%PDF-")


def test_publish_ignores_recovery_cleanup_failure_after_success(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    monkeypatch.setattr(build, "PUBLISHED_OUTPUT_DIR", output_dir)
    _mock_pdf_renderer(monkeypatch)
    real_rmtree = build.shutil.rmtree

    def fail_recovery_cleanup(path, *args, **kwargs):
        if Path(path).name.startswith(".v4-recovery-"):
            raise OSError("forced recovery cleanup failure")
        real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(build.shutil, "rmtree", fail_recovery_cleanup)

    final_html, final_pdf = build._publish_report("<p>report</p>", "report")

    assert final_html.exists()
    assert final_pdf.read_bytes().startswith(b"%PDF-")
    assert (output_dir / "report.manifest.json").exists()


def test_publish_preserves_original_error_when_recovery_cleanup_fails(
    tmp_path, monkeypatch
):
    output_dir = tmp_path / "out"
    monkeypatch.setattr(build, "PUBLISHED_OUTPUT_DIR", output_dir)
    output_dir.mkdir(parents=True)
    final_html = output_dir / "report.html"
    final_pdf = output_dir / "report.pdf"
    final_html.write_text("old html", encoding="utf-8")
    final_pdf.write_bytes(b"old pdf")
    real_replace = os.replace
    real_rmtree = build.shutil.rmtree

    def fail_staged_pdf_publish(source, destination):
        if (
            Path(source).name == final_pdf.name
            and Path(source).parent.name.startswith(".v4-stage-")
            and Path(destination) == final_pdf
        ):
            raise OSError("forced PDF publish failure")
        real_replace(source, destination)

    def fail_recovery_cleanup(path, *args, **kwargs):
        if Path(path).name.startswith(".v4-recovery-"):
            raise OSError("forced recovery cleanup failure")
        real_rmtree(path, *args, **kwargs)

    _mock_pdf_renderer(monkeypatch)
    monkeypatch.setattr(build.os, "replace", fail_staged_pdf_publish)
    monkeypatch.setattr(build.shutil, "rmtree", fail_recovery_cleanup)

    with pytest.raises(OSError, match="forced PDF publish failure"):
        build._publish_report("<p>report</p>", "report")

    assert final_html.read_text(encoding="utf-8") == "old html"
    assert final_pdf.read_bytes() == b"old pdf"


def test_publish_rollback_failure_retains_prior_pair_in_recovery_directory(
    tmp_path, monkeypatch
):
    output_dir = tmp_path / "out"
    monkeypatch.setattr(build, "PUBLISHED_OUTPUT_DIR", output_dir)
    output_dir.mkdir(parents=True)
    final_html = output_dir / "report.html"
    final_pdf = output_dir / "report.pdf"
    final_html.write_text("old html", encoding="utf-8")
    final_pdf.write_bytes(b"old pdf")
    real_replace = os.replace

    class PdfHTML:
        def __init__(self, filename):
            self.filename = filename

        def write_pdf(self, target):
            Path(target).write_bytes(b"%PDF-new")

    def fail_publish_and_html_rollback(source, destination):
        source = Path(source)
        destination = Path(destination)
        if source.parent.name.startswith(".v4-stage-") and destination == final_pdf:
            raise OSError("forced PDF publish failure")
        if source.name == final_html.name and source.parent.name.startswith(
            ".v4-recovery-"
        ):
            raise OSError("forced HTML rollback failure")
        real_replace(source, destination)

    monkeypatch.setitem(sys.modules, "weasyprint", types.SimpleNamespace(HTML=PdfHTML))
    monkeypatch.setattr(build.os, "replace", fail_publish_and_html_rollback)
    with pytest.raises(
        RuntimeError, match="prior report artifacts retained at"
    ) as error:
        build._publish_report("<p>report</p>", "report")

    recovery_dir = next(output_dir.glob(".v4-recovery-*"))
    assert str(recovery_dir) in str(error.value)
    assert (recovery_dir / "report.html").read_text(encoding="utf-8") == "old html"
    assert final_pdf.read_bytes() == b"old pdf"


def test_savings_and_home_transfers_are_never_in_excluded():
    contract = build_month_contract(
        [
            _transaction(
                1,
                -50,
                {"id": "savings", "title": "Savings"},
                is_transfer=True,
                payee="Savings transfer marker",
            ),
            _transaction(
                2,
                -75,
                {"id": "home", "title": "Home"},
                is_transfer=True,
                payee="Home transfer marker",
            ),
        ],
        OWNERS,
        detailed_section_mapping=DETAILED_SECTION_MAPPING,
    )

    html = render(contract, "2030-04")
    excluded_start = html.index("9. Excluded (Internal transfers)")

    for payee in ("Savings transfer marker", "Home transfer marker"):
        assert html.count(payee) == 1
        assert html.index(payee) < excluded_start


def test_detailed_section_mapping_rejects_unmapped_leaf_category_id():
    with pytest.raises(
        AccountingValidationError,
        match="Detailed section mapping has no section for category ID 'unmapped'",
    ):
        build_month_contract(
            [_transaction(1, -25, {"id": "unmapped", "title": "Unmapped"})],
            OWNERS,
            detailed_section_mapping=DETAILED_SECTION_MAPPING,
        )


def test_explicit_savings_account_ids_override_mapping_roles_after_map_validation():
    income = {"id": "income", "title": "Income"}
    savings = {"id": "savings", "title": "Savings"}
    mapping = {
        "category_sections": {"income": "income_salary", "savings": "savings"},
        "account_roles": {"account-a": "savings_partner_a"},
    }
    contract = build_month_contract(
        [
            _transaction(1, 100, income, "source-account"),
            _transaction(2, -25, savings, "account-a"),
            _transaction(3, -40, savings, "account-b"),
        ],
        OWNERS,
        {"income": "income", "savings": "savings"},
        savings_account_ids={"account-b"},
        detailed_section_mapping=mapping,
    )

    # savings_account_ids is no longer consulted; savings flows come from
    # account_roles. account-a is savings_partner_a; account-b has no role, so
    # its savings-category txn only feeds kron_net (folded into to_savings).
    assert contract["kpis"]["partner_a"]["net_savings"] == 0.0
    assert contract["kpis"]["partner_b"]["net_savings"] == 40.0


def test_explicit_savings_account_ids_still_validate_detailed_section_map_categories():
    with pytest.raises(
        AccountingValidationError,
        match="Detailed section mapping has no section for category ID 'unmapped'",
    ):
        build_month_contract(
            [_transaction(1, -25, {"id": "unmapped", "title": "Unmapped"})],
            OWNERS,
            {"unmapped": "savings"},
            savings_account_ids={"account-a"},
            detailed_section_mapping={"category_sections": {}, "account_roles": {}},
        )


def test_restored_sections_include_historical_category_charts():
    categories = [
        {"id": "common", "title": "Groceries"},
        {"id": "personal_a", "title": "Gaming (Fixture A)"},
        {"id": "personal_b", "title": "Cafes (Fixture B)"},
        {"id": "trip", "title": "Common Trip"},
    ]
    contract = build_month_contract(
        [
            _transaction(index, -10, category)
            for index, category in enumerate(categories, 1)
        ],
        OWNERS,
        detailed_section_mapping=DETAILED_SECTION_MAPPING,
    )

    html = render(contract, "2030-04", {"partner_a": "Fixture A", "partner_b": "Fixture B"})

    assert "Common spending by category" in html
    assert "Fixture A personal by category" in html
    assert "Fixture B personal by category" in html
    assert "Trips spending by category" in html


def test_role_kpis_render_original_card_labels_and_report_title():
    income = {"id": "income", "title": "Income"}
    contract = build_month_contract(
        [_transaction(1, 100, income)], OWNERS, {"income": "income"}
    )

    html = render(contract, "2030-04")

    assert "Household Financial Report - 2030-04" in html
    assert "<header><h1>Household Financial Report - 2030-04</h1>" in html
    assert 'class="report-header"' not in html
    assert "Monthly household ledger" not in html
    assert "Total income" in html
    assert "Real spend" in html
    assert "Net cash" in html
    assert "Net savings" in html
    assert "Net saved" in html
    assert "Personal spend" in html
    assert "Partner A" in html
    assert "1. Income" in html
    assert "2. Real spend" in html
    assert "3. Net savings" in html
    assert "overview-page" in html
    assert "<h2>Overview</h2>" not in html
    assert 'width="720"' in html
    assert html.index("Partner A") < html.index("Partner B")
    assert html.count('class="overview-chart overview-matrix"') == 1
    assert "Top report categories" not in html


def test_report_themes_preserve_kpi_content_and_reject_unknown_theme():
    income = {"id": "income", "title": "Income"}
    contract = build_month_contract(
        [_transaction(1, 100, income)], OWNERS, {"income": "income"}
    )

    for theme in ("minimal", "cyberpunk", "medieval", "oriental"):
        html = render(contract, "2030-04", theme_name=theme)
        assert f'<body class="theme-{theme}">' in html
        assert "Total income" in html
        assert "1. Income" in html
        assert f"body.theme-{theme} .legacy-section" in html
        assert f"body.theme-{theme} .legacy-chart" in html

    with pytest.raises(ValueError, match="Unknown report theme"):
        render(contract, "2030-04", theme_name="unknown")


def test_report_print_styles_keep_detailed_content_together():
    income = {"id": "income", "title": "Income"}
    contract = build_month_contract(
        [_transaction(1, 100, income)], OWNERS, {"income": "income"}
    )

    html = render(contract, "2030-04")

    assert "thead { display: table-header-group; }" in html
    assert "tr { break-inside: avoid-page; page-break-inside: avoid; }" in html
    assert (
        ".report-section > h2 { break-after: avoid-page; page-break-after: avoid; }"
        in html
    )
    assert (
        ".drilldown-card, .legacy-chart { break-inside: avoid-page; page-break-inside: avoid; }"
        in html
    )
    assert (
        ".drilldown summary { break-after: avoid-page; page-break-after: avoid; }"
        in html
    )
    assert (
        ".drilldown .tx-table { break-inside: auto; page-break-inside: auto; }" in html
    )


def test_report_and_svg_labels_are_html_escaped():
    income = {"id": "income", "title": "Salary (Fixture A)"}
    contract = build_month_contract(
        [_transaction(1, 100, income)], OWNERS, {"income": "income"}
    )

    html = render(
        contract,
        "2030-04",
        {"partner_a": "<script>alert(1)</script>", "partner_b": "Partner B"},
    )
    chart = render_horizontal_bar(
        [("<script>alert(1)</script>", 100)], title="<b>Chart</b>"
    )
    vertical_chart = render_vertical_bar(
        [("<script>alert(1)</script>", 0)], title="<b>Chart</b>"
    )

    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in chart
    assert "&lt;b&gt;Chart&lt;/b&gt;" in chart
    assert "&lt;b&gt;Chart&lt;/b&gt;" in vertical_chart
    assert "<b>Chart</b>" not in vertical_chart


def test_normalized_contract_keeps_optional_transaction_drilldown_text():
    contract = build_month_contract(
        [
            _transaction(
                1,
                -12.5,
                {"id": "category", "title": "Dynamic category"},
                payee="Synthetic market",
                note="Synthetic note",
            )
        ],
        OWNERS,
    )

    transaction = contract["normalized_transactions"][0]
    assert transaction["payee"] == "Synthetic market"
    assert transaction["note"] == "Synthetic note"


def test_parent_and_child_categories_aggregate_without_title_routing():
    parent = {"id": "home-root", "title": "Any Parent"}
    child = {"id": "home-child", "title": "Any Child", "parent": parent}
    contract = build_month_contract([_transaction(1, -25, child)], OWNERS)

    categories = {category["id"]: category for category in contract["categories"]}
    assert categories["home-root"]["net"] == 25
    assert categories["home-child"]["net"] == 25
    assert categories["home-child"]["parent_id"] == "home-root"


@pytest.mark.parametrize(
    "transaction",
    [
        {"id": 1, "date": "2030-04-01", "amount": -1, "account": {"id": "account-a"}},
        _transaction(1, -1, {"id": "x", "title": "X"}, "missing-account"),
        _transaction(1, float("inf"), {"id": "x", "title": "X"}),
        _transaction(1, -1, {"id": "x", "title": "X"}, category_hierarchy=[]),
    ],
)
def test_missing_or_invalid_normalized_fields_fail_closed(transaction):
    with pytest.raises(AccountingValidationError):
        build_month_contract([transaction], OWNERS)


def test_transfer_is_separate_and_reconciliation_is_zero():
    category = {"id": "misc", "title": "Miscellaneous"}
    transfer = {"id": "move", "title": "Fixture transfer", "is_transfer": True}
    contract = build_month_contract(
        [
            _transaction(1, -60, category),
            _transaction(2, 60, transfer, is_transfer=True),
        ],
        OWNERS,
    )

    assert [category["id"] for category in contract["categories"]] == ["misc"]
    assert [category["id"] for category in contract["transfers"]] == ["move"]
    assert contract["reconciliation"] == {
        "source": 0,
        "report": -60,
        "excluded_transfers": 60,
        "difference": 0,
    }


@pytest.mark.parametrize("value", [1, 0, "true"])
def test_transaction_transfer_metadata_requires_literal_booleans(value):
    transaction = _transaction(1, -1, {"id": "x", "title": "X"}, is_transfer=value)
    with pytest.raises(AccountingValidationError):
        build_month_contract([transaction], OWNERS)


@pytest.mark.parametrize("value", [1, 0, "true"])
def test_category_transfer_metadata_requires_literal_booleans(value):
    transaction = _transaction(1, -1, {"id": "x", "title": "X", "is_transfer": value})
    with pytest.raises(AccountingValidationError):
        build_month_contract([transaction], OWNERS)


def test_null_transfer_metadata_means_not_supplied():
    category = {"id": "x", "title": "X", "is_transfer": None}
    transaction = _transaction(1, -1, category, is_transfer=None)

    contract = build_month_contract([transaction], OWNERS)

    assert contract["normalized_transactions"][0]["is_transfer"] is False


@pytest.mark.parametrize(
    "date_value", ["2030-04-01T12:00:00", "2030-04-01Z", "20300401"]
)
def test_date_requires_full_iso_calendar_date(date_value):
    transaction = _transaction(1, -1, {"id": "x", "title": "X"})
    transaction["date"] = date_value
    with pytest.raises(AccountingValidationError):
        build_month_contract([transaction], OWNERS)


def test_category_path_must_match_category_identity():
    transaction = _transaction(1, -1, {"id": "x", "title": "X"})
    transaction["category_hierarchy"] = [{"id": "x", "title": "Other"}]
    with pytest.raises(AccountingValidationError):
        build_month_contract([transaction], OWNERS)


def test_category_id_cannot_have_conflicting_titles():
    category = {"id": "x", "title": "X"}
    conflicting = {"id": "x", "title": "Other X"}
    with pytest.raises(AccountingValidationError):
        build_month_contract(
            [_transaction(1, -1, category), _transaction(2, -1, conflicting)], OWNERS
        )


def test_category_id_cannot_have_conflicting_parents():
    child = {"id": "child", "title": "Child"}
    first = _transaction(1, -1, child)
    first["category_hierarchy"] = [
        {"id": "parent-a", "title": "Parent A"},
        child,
    ]
    second = _transaction(2, -1, child)
    second["category_hierarchy"] = [
        {"id": "parent-b", "title": "Parent B"},
        child,
    ]
    with pytest.raises(AccountingValidationError):
        build_month_contract([first, second], OWNERS)


def test_first_report_html_generation_uses_generic_contract():
    contract = build_month_contract(
        [_transaction(1, -12, {"id": "category", "title": "Dynamic category"})],
        OWNERS,
    )

    html = render(contract, "2030-04")
    assert "Dynamic category" in html
    assert "4. Common (Groceries, Hello Fresh, Restaurants, etc.)" in html


def test_generic_summary_has_valid_net_movement_metric_markup():
    contract = build_month_contract(
        [_transaction(1, -12, {"id": "category", "title": "Dynamic category"})],
        OWNERS,
    )

    html = render(contract, "2030-04")

    assert '<div class="metric"><span class="metric-label">Net movement</span>' in html
    assert 'Net movement</span><span class="metric-value">12.00</span>' in html


def test_new_kpi_page_keeps_old_v4_section_order_and_routing():
    categories = [
        {"id": "income", "title": "Salary (Fixture A)"},
        {"id": "savings", "title": "Sparekonto (Fixture A)"},
        {"id": "home", "title": "Mortgage"},
        {"id": "common", "title": "Groceries"},
        {"id": "personal_a", "title": "Gaming (Fixture A)"},
        {"id": "personal_b", "title": "Cafes (Fixture B)"},
        {"id": "trip", "title": "Common Trip"},
        {"id": "excluded", "title": "CC Payment (paired)"},
    ]
    contract = build_month_contract(
        [
            _transaction(index, -index, category)
            for index, category in enumerate(categories, 1)
        ],
        OWNERS,
        {category["id"]: "spend" for category in categories},
        detailed_section_mapping=DETAILED_SECTION_MAPPING,
    )

    html = render(contract, "2030-04", {"partner_a": "Fixture A", "partner_b": "Fixture B"})

    headings = [
        "1. Income",
        "2. Savings",
        "3. Home",
        "4. Common",
        "5. Fixture A",
        "6. Fixture B",
        "7. Trips",
        "8. CC Payments",
        "9. Excluded",
    ]
    assert [html.index(heading) for heading in headings] == sorted(
        html.index(heading) for heading in headings
    )
    assert "Category accounting" not in html
    assert "Source" in html
    assert "% of income" in html
    assert "Total Income" in html


def test_detailed_category_section_ids_ignore_renamed_display_titles():
    mapping = {"category_sections": {"home": "home"}, "account_roles": {}}
    original = build_month_contract(
        [_transaction(1, -125, {"id": "home", "title": "Mortgage"})],
        OWNERS,
        detailed_section_mapping=mapping,
    )
    renamed = build_month_contract(
        [_transaction(1, -125, {"id": "home", "title": "Renamed display title"})],
        OWNERS,
        detailed_section_mapping=mapping,
    )

    original_html = render(original, "2030-04")
    renamed_html = render(renamed, "2030-04")

    for html in (original_html, renamed_html):
        assert "3. Home (Mortgage, Per Olav Loan, USBL, Insurance)" in html
        assert "<td>Total</td><td>125.00</td>" in html
        assert "4. Common (Groceries, Hello Fresh, Restaurants, etc.)" in html
    assert "Renamed display title" in renamed_html


def test_detailed_savings_account_ids_ignore_renamed_account_names():
    mapping = {
        "category_sections": {
            "income": "income_salary",
            "savings": "savings",
        },
        "account_roles": {"account-a": "savings_partner_a"},
    }
    transactions = [
        _transaction(1, 100, {"id": "income", "title": "Salary"}),
        _transaction(2, -25, {"id": "savings", "title": "Savings"}),
        _transaction(3, 5, {"id": "savings", "title": "Savings"}),
    ]
    original = build_month_contract(
        transactions, OWNERS, detailed_section_mapping=mapping
    )
    for transaction in transactions:
        transaction["account"]["name"] = "Renamed savings account"
    renamed = build_month_contract(
        transactions, OWNERS, detailed_section_mapping=mapping
    )

    original_html = render(original, "2030-04")
    renamed_html = render(renamed, "2030-04")

    for html in (original_html, renamed_html):
        assert "2. Savings" in html
        # income on the savings account counts as to_savings; savings-category
        # legs add to kron_net which folds back into to_savings -> 100+25-10=125.
        assert "<td>Partner A</td><td>125.00</td><td>25.00</td><td><b>100.00</b>" in html
        assert "<td>Household</td><td>125.00</td><td>25.00</td><td>100.00</td>" in html
    assert "Renamed savings account" in renamed_html


def test_report_html_has_generic_summary_empty_transfers_and_escaped_titles():
    contract = build_month_contract(
        [_transaction(1, -12.5, {"id": "category", "title": "Dynamic <title>"})],
        OWNERS,
    )

    html = render(contract, "2030-04")

    assert "Monthly accounting report" in html
    assert 'aria-label="Report movements"' in html
    assert 'aria-label="Partner movements"' in html
    assert "Partner A" in html
    assert "Partner B" in html
    assert 'class="overview-charts"' in html
    assert "Top report categories" not in html
    assert "12.50" in html
    assert "No excluded items this month." in html
    assert "Dynamic &lt;title&gt;" in html
    assert "9. Excluded (Internal transfers)" in html


def test_report_html_renders_dynamic_hierarchy_and_explicit_transfers():
    parent = {"id": "parent", "title": "Any parent"}
    child = {"id": "child", "title": "Any child", "parent": parent}
    transfer = {"id": "transfer", "title": "Fixture transfer", "is_transfer": True}
    contract = build_month_contract(
        [
            _transaction(1, -25, child, payee="Synthetic market"),
            _transaction(2, 25, transfer, is_transfer=True),
        ],
        OWNERS,
    )

    html = render(contract, "2030-04")

    assert "Any parent" in html
    assert "Any child" in html
    assert "Fixture transfer" in html
    assert "9. Excluded (Internal transfers)" in html
    assert "Any parent / Any child" in html


def test_monthly_report_html_renders_to_real_pdf(tmp_path):
    try:
        import weasyprint
    except (OSError, ImportError) as error:
        pytest.skip(f"WeasyPrint native runtime unavailable: {error}")

    contract = build_month_contract(
        [_transaction(1, -12.5, {"id": "category", "title": "Dynamic category"})],
        OWNERS,
    )
    pdf_path = tmp_path / "monthly-report.pdf"

    weasyprint.HTML(string=render(contract, "2030-04")).write_pdf(str(pdf_path))

    assert pdf_path.stat().st_size > 0
    assert pdf_path.read_bytes().startswith(b"%PDF-")


def test_monthly_report_keeps_norwegian_text_through_html_and_pdf_render(tmp_path):
    try:
        import weasyprint
    except (OSError, ImportError) as error:
        pytest.skip(f"WeasyPrint native runtime unavailable: {error}")

    title = "Kj\u00f8p p\u00e5 S\u00f8r\u00f8ya \u00e6\u00f8\u00e5"
    contract = build_month_contract(
        [_transaction(1, -12.5, {"id": "category", "title": title}, payee=title)],
        OWNERS,
    )
    html = render(contract, "2030-04")
    pdf_path = tmp_path / "monthly-report-norwegian.pdf"

    weasyprint.HTML(string=html).write_pdf(str(pdf_path))

    assert title in html
    assert pdf_path.stat().st_size > 0
    assert pdf_path.read_bytes().startswith(b"%PDF-")
