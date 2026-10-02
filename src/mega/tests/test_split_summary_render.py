"""Mega HTML/PDF export — common-economy split rendering (mini-iteration
scope addition on top of the category-level split feature).

Backend build_mega_report/mega_builder already compute split_summary (JSON
API path); the mega HTML/PDF twin (assemble_html -> _render_kpi_cover ->
_render_split_summary) had NO rendering of it at all before this task (a
genuine scope gap, confirmed absent by QA — no split_summary hits in
build_mega.py or mega_pdf.py at task start).

SOURCE OF TRUTH: these tests pass in an ALREADY-COMPUTED split_summary dict
(the exact shape accounting.compute_split() returns, settlement already
label-resolved the way mega_builder.compute_mega_split_summary resolves it)
— never recompute net_category_totals/compute_split here. Twin of
budget_api/tests/test_mega_split.py (JSON-side coverage) and
v4_pipeline/tests/test_split_html.py (monthly HTML twin coverage).

LG-002: neutral fixture partner labels only (Alex/Sam), no real identifiers.
"""

import argparse
import json

import mega.build_mega as build_mega_module
from mega.build_mega import (
    _cli_split_summary,
    _render_kpi_cover,
    _render_split_summary,
    _split_section_label,
    assemble_html,
)

PARTNER_LABELS = {"partner_a": "Alex", "partner_b": "Sam"}


def _row(category_id, label, section, actual, fair, delta):
    # b-side additive complement — all fixtures in this file use 50/50
    # shares (_split_summary hardcodes partner_a/partner_b=50.0), so
    # fair_b == fair and actual_b == total - actual == 2*fair - actual
    # (total == fair*2 at 50/50); delta_b == -delta always.
    return {
        "category_id": category_id,
        "label": label,
        "section": section,
        "actual": actual,
        "fair": fair,
        "delta": delta,
        "actual_b": 2 * fair - actual,
        "fair_b": fair,
        "delta_b": -delta,
    }


def _split_summary(rows, sections, settlement):
    return {
        "shares": {"partner_a": 50.0, "partner_b": 50.0},
        "sections": sections,
        "rows": rows,
        "settlement": settlement,
    }


# --------------------------------------------------------------------------- #
# _split_section_label
# --------------------------------------------------------------------------- #


class TestSplitSectionLabel:
    def test_personal_partner_a_resolves_real_label(self):
        assert (
            _split_section_label("personal_partner_a", PARTNER_LABELS)
            == "Personal \u2014 Alex"
        )

    def test_personal_partner_b_resolves_real_label(self):
        assert (
            _split_section_label("personal_partner_b", PARTNER_LABELS)
            == "Personal \u2014 Sam"
        )

    def test_other_sections_render_raw_key(self):
        assert _split_section_label("home", PARTNER_LABELS) == "home"
        assert _split_section_label("common", PARTNER_LABELS) == "common"
        assert _split_section_label("trips", PARTNER_LABELS) == "trips"

    def test_missing_label_falls_back_to_placeholder(self):
        assert _split_section_label("personal_partner_a", {}) == "Personal \u2014 Partner A"


# --------------------------------------------------------------------------- #
# _render_split_summary
# --------------------------------------------------------------------------- #


class TestRenderSplitSummary:
    def test_none_omits_block_entirely(self):
        assert _render_split_summary(None, PARTNER_LABELS) == ""

    def test_empty_rows_shows_canonical_empty_copy(self):
        html = _render_split_summary(_split_summary([], [], None), PARTNER_LABELS)
        assert "Common economy split" in html
        assert (
            "No categories in the selected split sections this month." in html
        )
        assert "<table" not in html
        assert "Settlement" not in html

    def test_settlement_dict_renders_sentence_below_totals_row(self):
        """Settlement sentence RESTORED (user request): when the input
        summary carries a settlement dict it renders BELOW the totals row
        — totals row stays the table's last element."""
        rows = [_row("c_rent", "Rent", "home", 2000.0, 1000.0, 1000.0)]
        settlement = {"from_partner": "Sam", "to_partner": "Alex", "amount": 1000.0}
        html = _render_split_summary(
            _split_summary(rows, ["home"], settlement), PARTNER_LABELS
        )
        # Sentence hand-computed from the fixture: Sam owes Alex 1,000.00
        # NOK (labels already resolved in the input dict).
        sentence = "<p><b>Settlement: Sam owes Alex 1,000.00 NOK.</b></p>"
        assert sentence in html
        # Totals hand-computed from the fixture row: actual 2000, fair
        # 1000, delta 1000; b-side complements 0 / 1000 / -1000.
        totals_row = (
            '<tr><th scope="row">Total</th>'
            "<td>2,000.00 NOK</td><td>1,000.00 NOK</td><td>1,000.00 NOK</td>"
            "<td>0.00 NOK</td><td>1,000.00 NOK</td><td>-1,000.00 NOK</td></tr>"
        )
        assert totals_row in html
        # Order: totals row sits AFTER the section table, and the
        # settlement sentence sits AFTER the totals row (last element).
        assert html.index('<th scope="row">Total</th>') > html.index("</table>")
        assert html.index(sentence) > html.index('<th scope="row">Total</th>')

    def test_balanced_rows_totals_zero_deltas_already_even_note(self):
        """Balanced single row (delta 0): totals row renders 0.00 deltas
        and the settlement note renders the no-transfer "(already even)"
        wording below it — never a fabricated transfer amount."""
        rows = [_row("c_rent", "Rent", "home", 1000.0, 1000.0, 0.0)]
        html = _render_split_summary(
            _split_summary(rows, ["home"], None), PARTNER_LABELS
        )
        note = "<p>Settlement: — (already even).</p>"
        assert note in html
        assert html.index(note) > html.index('<th scope="row">Total</th>')
        assert "owes" not in html
        assert (
            '<tr><th scope="row">Total</th>'
            "<td>1,000.00 NOK</td><td>1,000.00 NOK</td><td>0.00 NOK</td>"
            "<td>1,000.00 NOK</td><td>1,000.00 NOK</td><td>0.00 NOK</td></tr>"
            in html
        )

    def test_balanced_split_totals_row_zero_deltas_no_fabricated_transfer(self):
        """Balanced split overall (deltas cancel): the totals row shows
        0.00 / 0.00 deltas AND the settlement note renders "(already
        even)" below it — NO bold 'X owes Y' sentence, NO fabricated
        transfer amount. Two rows with +50/-50 deltas so the zero only
        appears in the totals row."""
        rows = [
            _row("c_rent", "Rent", "home", 1050.0, 1000.0, 50.0),
            _row("c_groceries", "Groceries", "common", 950.0, 1000.0, -50.0),
        ]
        html = _render_split_summary(
            _split_summary(rows, ["home", "common"], None), PARTNER_LABELS
        )
        note = "<p>Settlement: — (already even).</p>"
        assert note in html
        assert html.index(note) > html.index('<th scope="row">Total</th>')
        assert "owes" not in html
        assert "<b>Settlement" not in html
        # Totals hand-computed: actual 2000, fair 2000, delta 0; b-side
        # 2000 / 2000 / 0 — identities delta_total == -delta_b_total and
        # fair_total + fair_b_total == actual_total + actual_b_total hold.
        assert (
            '<tr><th scope="row">Total</th>'
            "<td>2,000.00 NOK</td><td>2,000.00 NOK</td><td>0.00 NOK</td>"
            "<td>2,000.00 NOK</td><td>2,000.00 NOK</td><td>0.00 NOK</td></tr>"
            in html
        )

    def test_totals_row_sums_raw_then_formats_once(self):
        """Rounding rule: sum raw floats, format once — NOT sum of rounded
        rows. Two rows with fair/delta 0.004 each render 0.00 per row, but
        the raw totals (0.008) format 0.01 — round-then-sum would print
        0.00."""
        rows = [
            _row("c_rent", "Rent", "home", 0.008, 0.004, 0.004),
            _row("c_groceries", "Groceries", "common", 0.008, 0.004, 0.004),
        ]
        html = _render_split_summary(
            _split_summary(rows, ["home", "common"], None), PARTNER_LABELS
        )
        assert (
            '<tr><th scope="row">Total</th>'
            "<td>0.02 NOK</td><td>0.01 NOK</td><td>0.01 NOK</td>"
            "<td>0.00 NOK</td><td>0.01 NOK</td><td>-0.01 NOK</td></tr>"
            in html
        )

    def test_totals_row_snaps_negative_float_dust_no_minus_0_00(self):
        """-0.00 guard: raw delta total −0.002 (sub-half-cent float dust)
        snaps to 0.00 in the totals row — '-0.00' would wrongly signal an
        imbalance on a balanced split. Row cells keep raw formatting
        (pre-existing _amount behavior, out of scope)."""
        rows = [
            {
                "category_id": "c_rent",
                "label": "Rent",
                "section": "home",
                "actual": 999.996,
                "fair": 999.998,
                "delta": -0.002,
                "actual_b": 1000.0,
                "fair_b": 999.998,
                "delta_b": 0.002,
            }
        ]
        html = _render_split_summary(
            _split_summary(rows, ["home"], None), PARTNER_LABELS
        )
        assert (
            '<tr><th scope="row">Total</th>'
            "<td>1,000.00 NOK</td><td>1,000.00 NOK</td><td>0.00 NOK</td>"
            "<td>1,000.00 NOK</td><td>1,000.00 NOK</td><td>0.00 NOK</td></tr>"
            in html
        )

    def test_rows_grouped_by_section_in_canonical_order(self):
        """Sections given out of canonical order in the input (rows/sections
        are already compute_split-sorted upstream in real use, but this
        function must not silently depend on caller ordering beyond what it
        iterates) — grouping walks split_summary['sections'] in the order
        given, one <h4> heading + <table> per non-empty section, category
        rows only inside their own section's table."""
        rows = [
            _row("c_rent", "Rent", "home", 100.0, 50.0, 50.0),
            _row("c_groceries", "Groceries", "common", 200.0, 100.0, 100.0),
            _row("c_flights", "Flights", "trips", 300.0, 150.0, 150.0),
            _row("c_hobby_a", "Hobby A", "personal_partner_a", 40.0, 20.0, 20.0),
            _row("c_hobby_b", "Hobby B", "personal_partner_b", 60.0, 30.0, 30.0),
        ]
        sections = [
            "home",
            "common",
            "trips",
            "personal_partner_a",
            "personal_partner_b",
        ]
        html = _render_split_summary(
            _split_summary(rows, sections, None), PARTNER_LABELS
        )
        # Section headings appear in canonical order.
        positions = [html.index(f"<h4>{label}</h4>") for label in (
            "home",
            "common",
            "trips",
            "Personal \u2014 Alex",
            "Personal \u2014 Sam",
        )]
        assert positions == sorted(positions)
        # Each category row sits after its own section heading and before
        # the next one.
        assert positions[0] < html.index("Rent") < positions[1]
        assert positions[1] < html.index("Groceries") < positions[2]
        assert positions[2] < html.index("Flights") < positions[3]
        assert positions[3] < html.index("Hobby A") < positions[4]
        assert positions[4] < html.index("Hobby B")

    def test_alpha_section_after_canonical_order(self):
        """A section not in the canonical 5 (e.g. 'income_salary') is still
        renderable if the caller's `sections` list includes it (compute_split
        itself sorts alpha-after-canonical; this function trusts the given
        order, doesn't re-sort)."""
        rows = [
            _row("c_rent", "Rent", "home", 100.0, 50.0, 50.0),
            _row("c_salary", "Salary", "income_salary", -500.0, -250.0, -250.0),
        ]
        html = _render_split_summary(
            _split_summary(rows, ["home", "income_salary"], None), PARTNER_LABELS
        )
        assert html.index("<h4>home</h4>") < html.index("<h4>income_salary</h4>")

    def test_amounts_use_comma_grouped_two_decimal_nok_formatting(self):
        rows = [_row("c_rent", "Rent", "home", 12345.6, 6172.8, 6172.8)]
        html = _render_split_summary(
            _split_summary(rows, ["home"], None), PARTNER_LABELS
        )
        assert "12,345.60 NOK" in html
        assert "6,172.80 NOK" in html

    def test_category_label_escaped(self):
        rows = [_row("c_x", "Rent & <b>Utilities</b>", "home", 1.0, 1.0, 0.0)]
        html = _render_split_summary(
            _split_summary(rows, ["home"], None), PARTNER_LABELS
        )
        assert "Rent &amp; &lt;b&gt;Utilities&lt;/b&gt;" in html
        assert "<b>Utilities</b>" not in html

    def test_both_partners_columns_present_seven_column_header(self):
        """USER-REQUESTED change: both partners' columns visible, not just
        partner_a's. Header row is Category + 3 cols per partner (7 total),
        real labels (Alex/Sam), not generic 'Partner A/B'."""
        rows = [_row("c_rent", "Rent", "home", 100.0, 50.0, 50.0)]
        html = _render_split_summary(
            _split_summary(rows, ["home"], None), PARTNER_LABELS
        )
        assert (
            '<th scope="col">Category</th>'
            '<th scope="col">Alex actual</th>'
            '<th scope="col">Alex fair share</th>'
            '<th scope="col">Alex delta</th>'
            '<th scope="col">Sam actual</th>'
            '<th scope="col">Sam fair share</th>'
            '<th scope="col">Sam delta</th>' in html
        )
        # Two 7-column tables now: the section table + the totals table
        # (totals table repeats the header so cells stay identifiable).
        assert html.count('<th scope="col">') == 14
        # Row data: Alex 100.00/50.00/50.00, Sam (complement) 0.00/50.00/-50.00.
        assert "<td>100.00 NOK</td><td>50.00 NOK</td><td>50.00 NOK</td>" in html
        assert "<td>0.00 NOK</td><td>50.00 NOK</td><td>-50.00 NOK</td>" in html


# --------------------------------------------------------------------------- #
# _render_kpi_cover wiring — split_summary_wrap only present when non-empty.
# --------------------------------------------------------------------------- #


def _kpi_agg():
    months = ["2026-01"]
    return {
        "months": months,
        "series": {
            "income": {"partner_a": [0.0], "partner_b": [0.0], "total": [0.0]},
            "real_spend": {"total": [0.0]},
            "net_cash": {"total": [0.0]},
            "savings": {"total": [0.0]},
        },
        "cumulative": {
            "income": {"partner_a": 0.0, "partner_b": 0.0, "total": 0.0},
            "real_spend": {"total": 0.0},
            "net_cash": {"total": 0.0},
            "savings": {"total": 0.0},
        },
    }


class TestRenderKpiCoverSplitWiring:
    def test_no_split_summary_wrap_when_none(self):
        html = _render_kpi_cover(
            1, "KPI Cover", _kpi_agg(), PARTNER_LABELS, "2026-01 to 2026-01"
        )
        assert "mega-split-summary-wrap" not in html
        assert "Common economy split" not in html

    def test_split_summary_wrap_present_when_given(self):
        rows = [_row("c_rent", "Rent", "home", 100.0, 50.0, 50.0)]
        settlement = {"from_partner": "Sam", "to_partner": "Alex", "amount": 50.0}
        summary = _split_summary(rows, ["home"], settlement)
        html = _render_kpi_cover(
            1,
            "KPI Cover",
            _kpi_agg(),
            PARTNER_LABELS,
            "2026-01 to 2026-01",
            None,
            summary,
        )
        assert 'class="mega-split-summary-wrap"' in html
        assert "Common economy split" in html
        # Totals row AND the settlement sentence below it both render.
        assert '<th scope="row">Total</th>' in html
        assert "Settlement: Sam owes Alex 50.00 NOK." in html


# --------------------------------------------------------------------------- #
# assemble_html — end-to-end param threading (args.only="kpi_cover" isolates
# the one section that needs split_summary, avoiding a full detail_agg mock).
# --------------------------------------------------------------------------- #


def _mock_context():
    months = ["2026-01"]
    monthly_result = {
        "partner_labels": PARTNER_LABELS,
        "body_class": "mega-monthly",
        "contract": {"kpis": None, "normalized_transactions": []},
    }
    return {
        "monthly_results": [(months[0], monthly_result)],
        "recommendations": None,
        "accounting": {
            "months": months,
            "categories": {},
            "reconciliation": {"source": [0.0], "report": [0.0], "difference": [0.0]},
        },
        "detail_agg": _kpi_agg(),
        "salary_allocation": {"income": 0.0, "entries": [], "unavailable_reason": None},
        "appendix_transactions": {},
    }


def _mock_args():
    return argparse.Namespace(start="2026-01", end="2026-01", only="kpi_cover")


class TestAssembleHtmlSplitSummaryParam:
    def test_default_none_omits_block(self):
        html = assemble_html(_mock_context(), _mock_args())
        assert "Common economy split" not in html

    def test_split_summary_threaded_into_output(self):
        rows = [_row("c_rent", "Rent", "home", 100.0, 50.0, 50.0)]
        settlement = {"from_partner": "Sam", "to_partner": "Alex", "amount": 50.0}
        summary = _split_summary(rows, ["home"], settlement)
        html = assemble_html(_mock_context(), _mock_args(), split_summary=summary)
        assert "Common economy split" in html
        assert '<th scope="row">Total</th>' in html
        # Settlement sentence restored below the totals row.
        assert "Settlement: Sam owes Alex 50.00 NOK." in html
        assert "Rent" in html

    def test_existing_caller_shape_unaffected_positional_args_only(self):
        """The 2-positional-arg form (no split_summary) must keep working
        for any caller without a computed summary (additive param, default
        None omits the block). CLI main() itself now computes and passes a
        summary — see TestCliSplitSummary below."""
        html = assemble_html(_mock_context(), _mock_args())
        assert "<!doctype html>" in html


# --------------------------------------------------------------------------- #
# CLI split wiring — main()/_cli_split_summary (the CLI previously called
# assemble_html(context, args) with no split summary, so the split block was
# silently omitted even with an enabled split_config.json). The CLI stays
# standalone (no budget_api import), so _cli_split_summary re-derives the
# summary from the same v4_pipeline primitives with the CLI's own paths.
# --------------------------------------------------------------------------- #


def _cli_record(record_id, amount, owner, category_id, category_title="Cat"):
    """normalized_transactions record shape (twin of v4_pipeline
    test_split.py's _record)."""
    return {
        "id": record_id,
        "date": "2026-01-05",
        "amount": amount,
        "payee": None,
        "note": None,
        "account_id": "acc",
        "account_name": None,
        "owner": owner,
        "category_path": [{"id": category_id, "title": category_title}],
        "is_transfer": False,
    }


def _cli_context(records):
    monthly_result = {
        "partner_labels": PARTNER_LABELS,
        "body_class": "mega-monthly",
        "contract": {"kpis": None, "normalized_transactions": records},
    }
    return {"monthly_results": [("2026-01", monthly_result)]}


def _cli_args(split_config=None, detailed_section_map=None):
    return argparse.Namespace(
        split_config=split_config,
        detailed_section_map=detailed_section_map,
        category_catalog=None,
    )


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


class TestCliSplitSummary:
    def test_none_without_split_config_arg(self):
        """No --split-config path (e.g. a synthetic run) — never silently
        picks up a config; block omitted."""
        assert _cli_split_summary(_cli_context([]), _cli_args()) is None

    def test_none_when_config_file_missing(self, tmp_path):
        args = _cli_args(split_config=str(tmp_path / "absent.json"))
        assert _cli_split_summary(_cli_context([]), args) is None

    def test_none_when_config_disabled(self, tmp_path):
        config = _write_json(
            tmp_path / "split_config.json",
            {
                "enabled": False,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["c1"],
            },
        )
        assert _cli_split_summary(_cli_context([]), _cli_args(split_config=config)) is None

    def test_none_when_detailed_section_mapping_missing(self, tmp_path):
        """Same gate as the API path (mega_builder.compute_mega_split_
        summary) — net_category_totals needs the mapping to derive each
        record's natural section, so no mapping => no split block."""
        config = _write_json(
            tmp_path / "split_config.json",
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["c1"],
            },
        )
        args = _cli_args(split_config=config, detailed_section_map=None)
        assert _cli_split_summary(_cli_context([]), args) is None

    def test_computes_split_from_monthly_normalized_records(self, tmp_path):
        mapping = _write_json(
            tmp_path / "mapping.json",
            {"category_sections": {"c1": "home"}, "account_roles": {}},
        )
        config = _write_json(
            tmp_path / "split_config.json",
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["c1"],
            },
        )
        records = [_cli_record("t1", -1000.0, "partner_a", "c1", "Rent")]
        args = _cli_args(split_config=config, detailed_section_map=mapping)
        summary = _cli_split_summary(_cli_context(records), args)
        assert summary is not None
        assert summary["shares"] == {"partner_a": 50.0, "partner_b": 50.0}
        assert [row["category_id"] for row in summary["rows"]] == ["c1"]
        # partner_a paid the whole 1000 at 50/50 — partner_b owes 500.
        # Slot-keyed here; _render_split_summary resolves labels at render.
        assert summary["settlement"] == {
            "from_partner": "partner_b",
            "to_partner": "partner_a",
            "amount": 500.0,
        }

    def test_main_threads_split_summary_into_assemble_html(
        self, tmp_path, monkeypatch
    ):
        """CLI regression: main() must compute and pass the split summary
        (was: assemble_html(context, args) with none -> block omitted even
        with an enabled split_config.json)."""
        mapping = _write_json(
            tmp_path / "mapping.json",
            {"category_sections": {"c1": "home"}, "account_roles": {}},
        )
        config = _write_json(
            tmp_path / "split_config.json",
            {
                "enabled": True,
                "shares": {"partner_a": 50.0, "partner_b": 50.0},
                "categories": ["c1"],
            },
        )
        records = [_cli_record("t1", -1000.0, "partner_a", "c1", "Rent")]
        monkeypatch.setattr(
            build_mega_module, "build_context", lambda args: _cli_context(records)
        )
        captured = {}

        def _fake_assemble_html(context, args, split_summary=None):
            captured["split_summary"] = split_summary
            return "<html></html>"

        monkeypatch.setattr(build_mega_module, "assemble_html", _fake_assemble_html)
        monkeypatch.setattr(
            build_mega_module,
            "_publish",
            lambda html, output_dir, name: (
                tmp_path / "out.html",
                tmp_path / "out.pdf",
            ),
        )
        rc = build_mega_module.main(
            [
                "--start", "2026-01",
                "--end", "2026-01",
                "--data-dir", str(tmp_path),
                "--input-kind", "synthetic",
                "--detailed-section-map", mapping,
                "--split-config", config,
            ]
        )
        assert rc == 0
        assert captured["split_summary"] is not None
        assert captured["split_summary"]["settlement"] == {
            "from_partner": "partner_b",
            "to_partner": "partner_a",
            "amount": 500.0,
        }
