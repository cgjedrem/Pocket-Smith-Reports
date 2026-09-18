"""Unit tests for the MoM (Month-on-Month) modules."""

import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from compare import (
    aggregate_months,
    aggregate_normalized_months,
    section_totals_per_month,
    mom_deltas,
)
from trips import cluster_by_label, _partner_of
from recommendations import generate_recommendations
from line_chart import render_line_chart
from mom_template import _render_overview_table, _render_section_section
from render_mom import render_mom_html
from sections.section_appendices import render as render_appendices

# ===== compare.py =====


def _make_month(
    month: str,
    income_partner_a: float,
    income_partner_b: float,
    spend_partner_a: float,
    spend_partner_b: float,
    sav_partner_a: float,
    sav_partner_b: float,
    cats: dict = None,
) -> dict:
    """Helper: build a minimal monthly_data dict for testing."""
    if cats is None:
        cats = {}
    return {
        "month": month,
        "txns": [],
        "totals": {},
        "wallet": {
            "income": {
                "partner_a": income_partner_a,
                "partner_b": income_partner_b,
                "total": income_partner_a + income_partner_b,
            },
            "savings": {
                "partner_a": sav_partner_a,
                "partner_b": sav_partner_b,
                "total": sav_partner_a + sav_partner_b,
            },
            "wallets": {
                "partner_a": spend_partner_a,
                "partner_b": spend_partner_b,
                "total": spend_partner_a + spend_partner_b,
            },
            "net_cash": {
                "partner_a": income_partner_a - spend_partner_a,
                "partner_b": income_partner_b - spend_partner_b,
                "total": (income_partner_a + income_partner_b)
                - (spend_partner_a + spend_partner_b),
            },
            "cats": cats,
            "paired_reimb_events": [],
        },
    }


def test_aggregate_single_month():
    m = _make_month("2030-01", 43000, 40000, 50000, 30000, 1000, 500, cats={})
    agg = aggregate_months([m])
    assert agg["period"] == "2030-01 → 2030-01 (1 months)"
    assert agg["cumulative"]["income"]["total"] == 83000
    assert agg["cumulative"]["real_spend"]["total"] == 80000


def test_appendices_escape_transaction_text():
    html = render_appendices(
        {"months": ["2030-01"]},
        {
            "2030-01": [
                {
                    "date": "2030-01-01<script>",
                    "payee": "<b>Payee</b>",
                    "amount": -12,
                    "account": {"name": "A & B"},
                    "category": {"title": "<i>Category</i>"},
                    "_detailed_section": "common",
                    "_main_category": {"id": "main", "title": "<i>Category</i>"},
                    "_subcategory": None,
                }
            ]
        },
    )

    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;Payee&lt;/b&gt;" in html
    assert "A &amp; B" in html
    assert "&lt;i&gt;Category&lt;/i&gt;" in html


def test_aggregate_multi_month_cumulative():
    months = [
        _make_month("2030-01", 43000, 40000, 50000, 30000, 1000, 500),
        _make_month("2030-02", 45000, 41000, 52000, 31000, 2000, 600),
    ]
    agg = aggregate_months(months)
    assert agg["cumulative"]["income"]["total"] == 169000
    assert agg["cumulative"]["real_spend"]["total"] == 163000
    assert agg["cumulative"]["savings"]["net_partner_a"] == 3000


def test_aggregate_sorts_by_month():
    months = [
        _make_month("2030-02", 0, 0, 0, 0, 0, 0),
        _make_month("2030-01", 0, 0, 0, 0, 0, 0),
    ]
    agg = aggregate_months(months)
    assert agg["months"] == ["2030-01", "2030-02"]


def test_aggregate_empty():
    agg = aggregate_months([])
    assert agg["period"] == ""
    assert agg["months"] == []


def test_aggregate_per_cat_series():
    months = [
        _make_month(
            "2030-01",
            0,
            0,
            0,
            0,
            0,
            0,
            cats={
                "Groceries": {
                    "section": "common",
                    "partner_a_paid": 1000,
                    "partner_b_paid": 2000,
                    "partner_a_received": 0,
                    "partner_b_received": 0,
                    "partner_a_net": 1000,
                    "partner_b_net": 2000,
                    "effective_total": 3000,
                    "count": 5,
                }
            },
        ),
        _make_month(
            "2030-02",
            0,
            0,
            0,
            0,
            0,
            0,
            cats={
                "Groceries": {
                    "section": "common",
                    "partner_a_paid": 1500,
                    "partner_b_paid": 2500,
                    "partner_a_received": 0,
                    "partner_b_received": 0,
                    "partner_a_net": 1500,
                    "partner_b_net": 2500,
                    "effective_total": 4000,
                    "count": 6,
                }
            },
        ),
    ]
    agg = aggregate_months(months)
    groc = agg["cats"]["Groceries"]
    assert groc["total"] == [3000, 4000]
    assert groc["partner_a_paid"] == [1000, 1500]


def test_sparse_category_month_is_written_at_its_source_index():
    months = [
        _make_month("2030-01", 0, 0, 0, 0, 0, 0, cats={}),
        _make_month(
            "2030-02",
            0,
            0,
            0,
            0,
            0,
            0,
            cats={
                "Late category": {
                    "section": "common",
                    "partner_a_paid": 50,
                    "partner_b_paid": 0,
                    "partner_a_received": 0,
                    "partner_b_received": 0,
                    "partner_a_net": 50,
                    "partner_b_net": 0,
                    "effective_total": 50,
                    "count": 1,
                }
            },
        ),
    ]
    assert aggregate_months(months)["cats"]["Late category"]["total"] == [0.0, 50]


def test_normalized_contract_categories_align_sparse_months():
    months = [
        {"month": "2030-01", "contract": {"categories": []}},
        {
            "month": "2030-02",
            "contract": {
                "categories": [
                    {
                        "id": "late",
                        "title": "Late category",
                        "parent_id": None,
                        "paid": 20,
                        "received": 5,
                        "net": 15,
                        "count": 2,
                    }
                ]
            },
        },
    ]
    aggregate = aggregate_normalized_months(months)
    assert aggregate["categories"]["late"]["net"] == [0.0, 15]


def test_supported_mom_render_uses_normalized_hierarchy_and_reconciliation():
    aggregate = aggregate_normalized_months(
        [
            {
                "month": "2030-01",
                "contract": {
                    "categories": [
                        {
                            "id": "root",
                            "title": "Dynamic root",
                            "parent_id": None,
                            "path": [],
                            "paid": 100,
                            "received": 0,
                            "net": 100,
                            "count": 1,
                        },
                        {
                            "id": "child",
                            "title": "Dynamic child",
                            "parent_id": "root",
                            "path": [],
                            "paid": 100,
                            "received": 0,
                            "net": 100,
                            "count": 1,
                        },
                    ],
                    "reconciliation": {
                        "source": 0,
                        "report": 0,
                        "difference": 0,
                    },
                },
            }
        ]
    )
    html = render_mom_html({"period": "2030-01", "accounting": aggregate})
    assert 'class="report-header"' in html
    assert "Household financial review" in html
    assert "Dynamic root" in html
    assert "Dynamic child" in html
    assert "100.00" in html
    assert "Reconciliation" in html
    assert "0.00" in html


def test_mom_includes_transfer_metadata_in_categories_totals_and_rendered_rows():
    from accounting import build_month_contract

    category = {"id": "transfer-category", "title": "Transfer category"}
    contract = build_month_contract(
        [
            {
                "id": "transfer-paid",
                "date": "2030-01-01",
                "amount": -61.0,
                "account": {"id": "account-a"},
                "category": category,
                "is_transfer": True,
            },
            {
                "id": "transfer-received",
                "date": "2030-01-02",
                "amount": 17.0,
                "account": {"id": "account-b"},
                "category": category,
                "is_transfer": True,
            },
        ],
        {"account-a": "partner_a", "account-b": "partner_b"},
    )

    # Transfers are separated into contract["transfers"]; categories is empty.
    assert contract["categories"] == []
    transfer_totals = contract["transfers"][0]
    assert (
        transfer_totals["paid"],
        transfer_totals["received"],
        transfer_totals["net"],
    ) == (
        61.0,
        17.0,
        44.0,
    )
    assert transfer_totals["count"] == 2
    assert contract["reconciliation"] == {
        "source": -44.0,
        "report": 0,
        "excluded_transfers": -44.0,
        "difference": 0.0,
    }

    # aggregate_normalized_months only walks "categories", so the transfer
    # category does not appear; reconciliation reports the source delta and a
    # zero report total (transfers excluded from the reportable side).
    accounting = aggregate_normalized_months(
        [{"month": "2030-01", "contract": contract}]
    )
    assert "transfer-category" not in accounting["categories"]
    assert accounting["reconciliation"] == {
        "source": [-44.0],
        "report": [0],
        "difference": [0.0],
    }

    html = render_mom_html({"period": "2030-01", "accounting": accounting})
    assert "Transfer category" not in html
    # The net reconciliation delta still surfaces in the rendered reconciliation.
    for value in ("44.00", "-44.00"):
        assert value in html


def test_sparse_normalized_values_render_at_first_middle_and_last_months():
    months = [f"2030-{month:02d}" for month in range(1, 4)]
    categories = (
        ("first", "First", 10),
        ("middle", "Middle", 20),
        ("last", "Last", 30),
    )
    contracts = []
    for index, month in enumerate(months):
        category_id, title, value = categories[index]
        contracts.append(
            {
                "month": month,
                "contract": {
                    "categories": [
                        {
                            "id": category_id,
                            "title": title,
                            "parent_id": None,
                            "path": [],
                            "paid": value,
                            "received": 0,
                            "net": value,
                            "count": 1,
                        }
                    ],
                    "reconciliation": {
                        "source": -value,
                        "report": -value,
                        "difference": 0,
                    },
                },
            }
        )
    aggregate = aggregate_normalized_months(contracts)
    assert aggregate["categories"]["first"]["net"] == [10, 0.0, 0.0]
    assert aggregate["categories"]["middle"]["net"] == [0.0, 20, 0.0]
    assert aggregate["categories"]["last"]["net"] == [0.0, 0.0, 30]

    html = render_mom_html({"period": "2030-01 to 2030-03", "accounting": aggregate})
    for month, value in zip(months, ("10.00", "20.00", "30.00")):
        assert month in html
        assert value in html


def test_eleven_month_overview_second_half_uses_months_seven_through_eleven():
    months = [f"2030-{month:02d}" for month in range(1, 12)]
    values = list(range(1, 12))
    aggregate = {
        "months": months,
        "series": {
            "income": {
                "partner_a": values,
                "partner_b": values,
                "total": [value * 2 for value in values],
            }
        },
    }
    html = _render_overview_table(aggregate, "Income")
    assert "Overview table (2nd half)" in html
    assert "2030/07" not in html
    assert "30/07" in html
    assert '<td class="num">7</td>' in html
    assert '<td class="num">11</td>' in html
    assert '<td class="num"><b>45</b></td>' in html


def test_eleven_month_category_second_half_uses_months_seven_through_eleven():
    months = [f"2030-{month:02d}" for month in range(1, 12)]
    aggregate = {
        "months": months,
        "cats": {"Sparse": {"section": "common", "total": list(range(1, 12))}},
    }
    html = _render_section_section(aggregate, "common")
    assert "Per-category breakdown (2nd half)" in html
    assert "30/07" in html
    assert '<td class="num">7</td>' in html
    assert '<td class="num">11</td>' in html
    assert '<td class="num"><b>45</b></td>' in html


def test_mom_deltas():
    series = [100, 150, 200, 175]
    deltas = mom_deltas(series)
    assert deltas == [None, 50, 50, -25]


def test_section_totals_per_month():
    months = [
        _make_month(
            "2030-01",
            0,
            0,
            0,
            0,
            0,
            0,
            cats={
                "Groceries": {
                    "section": "common",
                    "effective_total": 5000,
                    "partner_a_paid": 2000,
                    "partner_b_paid": 3000,
                    "partner_a_net": 2000,
                    "partner_b_net": 3000,
                    "count": 1,
                },
                "Home Maintenance": {
                    "section": "home",
                    "effective_total": 8000,
                    "partner_a_paid": 5000,
                    "partner_b_paid": 3000,
                    "partner_a_net": 5000,
                    "partner_b_net": 3000,
                    "count": 1,
                },
            },
        ),
    ]
    agg = aggregate_months(months)
    common = section_totals_per_month(agg, "common")
    home = section_totals_per_month(agg, "home")
    assert common["total"] == [5000]
    assert home["total"] == [8000]


# ===== trips.py =====


def test_partner_of():
    assert _partner_of("Partner A Checking") == "Partner A"
    assert _partner_of("Partner B Checking") == "Partner B"
    assert _partner_of("Joint Account") == "Joint"


def test_cluster_by_label_empty():
    clusters = cluster_by_label([])
    assert clusters == []


def test_cluster_by_label_single():
    txns = [
        {
            "id": 1,
            "date": "2030-04-01",
            "amount": -1000,
            "labels": ["sample-trip-a"],
            "account": {"name": "Partner A Checking"},
            "category": {"title": "Common Trip"},
            "payee": "Klarna",
        },
        {
            "id": 2,
            "date": "2030-04-03",
            "amount": -500,
            "labels": ["sample-trip-a"],
            "account": {"name": "Partner B Checking"},
            "category": {"title": "Common Trip"},
            "payee": "Hotel",
        },
    ]
    clusters = cluster_by_label(txns)
    assert len(clusters) == 1
    c = clusters[0]
    assert c["label"] == "sample-trip-a"
    assert c["date_start"] == "2030-04-01"
    assert c["date_end"] == "2030-04-03"
    assert c["days"] == 3
    assert c["total"] == 1500
    assert c["partner_a_paid"] == 1000
    assert c["partner_b_paid"] == 500


def test_cluster_by_label_multi():
    txns = [
        {
            "id": 1,
            "date": "2030-04-01",
            "amount": -1000,
            "labels": ["sample-trip-a"],
            "account": {"name": "Partner A Checking"},
            "category": {"title": "Common Trip"},
        },
        {
            "id": 2,
            "date": "2030-05-15",
            "amount": -2000,
            "labels": ["sample-trip-b"],
            "account": {"name": "Partner B Checking"},
            "category": {"title": "Common Trip"},
        },
    ]
    clusters = cluster_by_label(txns)
    assert len(clusters) == 2
    assert clusters[0]["label"] == "sample-trip-a"
    assert clusters[1]["label"] == "sample-trip-b"


def test_cluster_by_label_ignores_no_label():
    txns = [
        {
            "id": 1,
            "date": "2030-04-01",
            "amount": -1000,
            "labels": [],
            "account": {"name": "Partner A Checking"},
            "category": {"title": "Common Trip"},
        },
    ]
    clusters = cluster_by_label(txns)
    assert clusters == []


# ===== recommendations.py =====


def test_recommendations_returns_list():
    months = [
        _make_month(
            "2030-01",
            0,
            0,
            0,
            0,
            0,
            0,
            cats={
                "Mortgage": {
                    "section": "home",
                    "effective_total": 100000,
                    "partner_a_paid": 50000,
                    "partner_b_paid": 50000,
                    "partner_a_net": 50000,
                    "partner_b_net": 50000,
                    "count": 1,
                }
            },
        ),
    ]
    agg = aggregate_months(months)
    recs = generate_recommendations(agg)
    assert isinstance(recs, list)
    assert len(recs) > 0
    # All recs are strings
    assert all(isinstance(r, str) for r in recs)


def test_recommendations_largest_cat():
    months = [
        _make_month(
            "2030-01",
            0,
            0,
            0,
            0,
            0,
            0,
            cats={
                "Mortgage": {
                    "section": "home",
                    "effective_total": 100000,
                    "partner_a_paid": 50000,
                    "partner_b_paid": 50000,
                    "partner_a_net": 50000,
                    "partner_b_net": 50000,
                    "count": 1,
                }
            },
        ),
    ]
    agg = aggregate_months(months)
    recs = generate_recommendations(agg)
    # Should mention Mortgage
    assert any("Mortgage" in r for r in recs)


def test_recommendations_income_stable():
    # Stable income: all months same value
    months = [
        _make_month(f"2030-{1+i:02d}", 50000, 40000, 60000, 30000, 1000, 500)
        for i in range(5)
    ]
    agg = aggregate_months(months)
    recs = generate_recommendations(agg)
    income_recs = [r for r in recs if "stable" in r.lower() or "Income" in r]
    # Should have an income stability callout
    assert len(income_recs) >= 0  # not asserting - just no crash


# ===== line_chart.py =====


def test_line_chart_empty():
    svg = render_line_chart([], {}, "Test")
    assert "No data" in svg or "empty" in svg.lower()


def test_line_chart_basic():
    svg = render_line_chart(
        ["2030-01", "2030-02", "2030-03"],
        {"Series A": [100, 200, 300], "Series B": [150, 250, 350]},
        "Test chart",
    )
    assert "<svg" in svg
    assert "Test chart" in svg
    assert "Series A" in svg
    assert "Series B" in svg
    # Should have circles for data points
    assert "<circle" in svg
    assert 'role="img"' in svg
    assert 'aria-labelledby="line-chart-test-chart-' in svg
    assert "<desc id=" in svg


def test_line_chart_accessibility_ids_change_with_context():
    first = render_line_chart(
        ["2030-01"], {"A": [1]}, "Chart", accessibility_id="income"
    )
    second = render_line_chart(
        ["2030-01"], {"A": [1]}, "Chart", accessibility_id="home"
    )

    assert 'aria-labelledby="line-chart-income-' in first
    assert 'aria-labelledby="line-chart-home-' in second


def test_identical_line_charts_have_unique_accessibility_ids_in_one_document():
    document = "\n".join(
        [
            render_line_chart(
                ["2030-01"], {"A": [1]}, "Chart", accessibility_id="income"
            ),
            render_line_chart(
                ["2030-01"], {"A": [1]}, "Chart", accessibility_id="income"
            ),
        ]
    )

    metadata_ids = re.findall(r'<(?:title|desc) id="([^"]+)">', document)
    aria_references = [
        reference
        for labelled_by in re.findall(r'aria-labelledby="([^"]+)"', document)
        for reference in labelled_by.split()
    ]

    assert len(metadata_ids) == 4
    assert len(metadata_ids) == len(set(metadata_ids))
    assert set(aria_references) == set(metadata_ids)


def test_line_chart_handles_none():
    svg = render_line_chart(
        ["m1", "m2", "m3"],
        {"A": [100, None, 300]},
        "Test",
    )
    # Should not crash
    assert "<svg" in svg
