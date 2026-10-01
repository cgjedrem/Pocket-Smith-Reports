"""HTML/PDF parity block — accounting_html.render(split_config=...).

Confirms: (1) no split_config => byte-identical to before (no new markup,
existing callers unaffected — additive param default None); (2) with an
enabled category-based split config, the "Common economy split" block
appears with the per-category actual/fair/delta table whose numbers match
accounting.compute_split() exactly plus a per-column totals row (raw
sums, formatted once) as the LAST table row, followed by the settlement
sentence BELOW the table (restored per user request — totals row AND
plain-language summary both; balanced splits render the "already even"
note, never a fabricated 0.00 transfer); (3) an enabled config with zero
categories selected still renders the section (empty state is ALLOWED
per design, not omitted — "No data" copy, and NO settlement sentence in
that state), matching the JSON DTO's non-None SplitSection in that state.
"""

from accounting import (
    _resolve_allowed_category_ids,
    build_month_contract,
    compute_split,
    net_category_totals,
)
from accounting_html import render

OWNERS = {"account-a": "partner_a", "account-b": "partner_b"}

HOME = {"id": "home-cat", "title": "Home"}
COMMON = {"id": "common-cat", "title": "Common"}

DETAILED_SECTION_MAPPING = {
    "category_sections": {"home-cat": "home", "common-cat": "common"},
    "account_roles": {},
}

PARTNER_LABELS = {"partner_a": "Fixture A", "partner_b": "Fixture B"}


def _transaction(transaction_id, amount, category, account_id):
    return {
        "id": transaction_id,
        "date": "2030-04-01",
        "amount": amount,
        "account": {"id": account_id},
        "category": category,
    }


def _contract():
    transactions = [
        _transaction(1, -1000.0, HOME, "account-a"),
        _transaction(2, -400.0, HOME, "account-b"),
        _transaction(3, -600.0, COMMON, "account-a"),
        _transaction(4, -600.0, COMMON, "account-b"),
    ]
    return build_month_contract(
        transactions,
        OWNERS,
        detailed_section_mapping=DETAILED_SECTION_MAPPING,
    )


def test_no_split_config_no_block_rendered():
    html = render(_contract(), "2030-04", PARTNER_LABELS)
    assert "Common economy split" not in html


def test_enabled_split_config_renders_block_matching_compute_split():
    contract = _contract()
    split_config = {
        "shares": {"partner_a": 60.0, "partner_b": 40.0},
        "categories": ["home-cat", "common-cat"],
    }
    html = render(contract, "2030-04", PARTNER_LABELS, split_config=split_config)
    assert "Common economy split" in html

    records = contract["normalized_transactions"]
    allowed_ids = _resolve_allowed_category_ids(split_config["categories"], None)
    category_nets = net_category_totals(records, allowed_ids, DETAILED_SECTION_MAPPING)
    expected = compute_split(category_nets, split_config["shares"])
    for row in expected["rows"]:
        assert f"{row['actual']:,.2f}" in html
        assert f"{row['fair']:,.2f}" in html
        assert f"{row['actual_b']:,.2f}" in html
        assert f"{row['fair_b']:,.2f}" in html
    # 7-column header — Category + both partners' actual/fair/delta,
    # real labels (not generic "Partner A/B").
    assert (
        "<th>Category</th><th>Fixture A actual</th><th>Fixture A fair share</th>"
        "<th>Fixture A delta</th><th>Fixture B actual</th>"
        "<th>Fixture B fair share</th><th>Fixture B delta</th>" in html
    )
    # Settlement sentence RESTORED (user request), positioned BELOW the
    # totals row. Hand-computed: A deltas home +160 / common −120 → net
    # +40, so Fixture B owes Fixture A 40.00 (exact pre-removal wording).
    assert expected["settlement"] is not None
    sentence = (
        '<p class="note"><b>Settlement: Fixture B owes Fixture A 40.00.</b></p>'
    )
    assert sentence in html

    # Totals row — sums hand-computed from the fixture (not via
    # compute_split): home A 1000 / B 400 (total 1400 → fair 840/560,
    # delta +160/−160); common A 600 / B 600 (total 1200 → fair 720/480,
    # delta −120/+120). Row sums: actual 1600, fair 1560, delta +40;
    # b-side 1000 / 1040 / −40 — identities: delta_total ≈ −delta_b_total,
    # fair_total + fair_b_total == actual_total + actual_b_total (2600).
    assert (
        '<tr class="legacy-total"><td>Total</td>'
        "<td>1,600.00</td><td>1,560.00</td><td>40.00</td>"
        "<td>1,000.00</td><td>1,040.00</td><td>-40.00</td></tr>" in html
    )
    # Order: settlement sentence sits AFTER the split totals row (and
    # still inside the split section). Anchor past "split-table" so an
    # income/savings legacy-total earlier in the page can't false-pass —
    # index() after the anchor is the split totals row specifically.
    split_start = html.index("split-table")
    totals_idx = html.index('class="legacy-total"', split_start)
    sentence_idx = html.index(sentence)
    assert totals_idx < sentence_idx < html.index("</section>", sentence_idx)


def test_no_categories_selected_block_still_renders_empty():
    """Design decision: enabled=true + zero categories selected is
    ALLOWED, not omitted — the section still renders (no rows, no table)
    rather than disappearing entirely."""
    contract = _contract()
    split_config = {"shares": {"partner_a": 50.0, "partner_b": 50.0}, "categories": []}
    html = render(contract, "2030-04", PARTNER_LABELS, split_config=split_config)
    assert "Common economy split" in html
    # Canonical copy — parity with React's DetailedSections.tsx empty state
    # (iteration 4, finding 4), not the generic legacy-section message.
    assert "No categories in the selected split sections this month." in html
    # Nothing else in the empty state — no table, no settlement sentence.
    assert "Settlement" not in html


def test_perfectly_balanced_split_totals_row_zero_deltas_already_even_note():
    """Balanced split: settlement is None, so the sentence renders the
    original no-transfer wording "(already even)" BELOW the totals row —
    never a fabricated 0.00 transfer; deltas still render 0.00 (never
    -0.00)."""
    contract = _contract()
    split_config = {
        "shares": {"partner_a": 50.0, "partner_b": 50.0},
        "categories": ["common-cat"],
    }
    html = render(contract, "2030-04", PARTNER_LABELS, split_config=split_config)
    assert "Common economy split" in html
    # Fixture hand-computed: common A 600 / B 600 (total 1200 → fair
    # 600/600, delta 0/0) — single row, totals == row values.
    assert (
        '<tr class="legacy-total"><td>Total</td>'
        "<td>600.00</td><td>600.00</td><td>0.00</td>"
        "<td>600.00</td><td>600.00</td><td>0.00</td></tr>" in html
    )
    # settlement None → "(already even)" note, no "owes", no transfer
    # amount — and the note sits AFTER the totals row.
    note = '<p class="note">Settlement: — (already even).</p>'
    assert note in html
    # Anchor past "split-table" — income/savings sections render their own
    # legacy-total rows earlier; a bare first-match would false-pass.
    split_totals_idx = html.index(
        'class="legacy-total"', html.index("split-table")
    )
    assert html.index(note) > split_totals_idx
    assert "owes" not in html
    assert "-0.00" not in html


def test_totals_row_sums_raw_then_formats_once():
    """Rounding rule: sum raw floats, format once — NOT sum of rounded
    rows. Two categories each A-paid 0.008 at 50/50: each row's fair
    (0.004) and delta (0.004) format 0.00, but the raw totals (0.008)
    format 0.01 — a round-then-sum implementation would print 0.00."""
    transactions = [
        _transaction(1, -0.008, HOME, "account-a"),
        _transaction(2, -0.008, COMMON, "account-a"),
    ]
    contract = build_month_contract(
        transactions,
        OWNERS,
        detailed_section_mapping=DETAILED_SECTION_MAPPING,
    )
    split_config = {
        "shares": {"partner_a": 50.0, "partner_b": 50.0},
        "categories": ["home-cat", "common-cat"],
    }
    html = render(contract, "2030-04", PARTNER_LABELS, split_config=split_config)
    assert (
        '<tr class="legacy-total"><td>Total</td>'
        "<td>0.02</td><td>0.01</td><td>0.01</td>"
        "<td>0.00</td><td>0.01</td><td>-0.01</td></tr>" in html
    )


def test_totals_row_snaps_negative_float_dust_to_zero_no_minus_0_00():
    """-0.00 guard: a near-balanced split whose raw delta total is tiny
    negative (−0.002, from float arithmetic below half a cent) must render
    0.00 in the totals row — '-0.00' would wrongly signal an imbalance."""
    transactions = [
        _transaction(1, -999.996, HOME, "account-a"),
        _transaction(2, -1000.0, HOME, "account-b"),
    ]
    contract = build_month_contract(
        transactions,
        OWNERS,
        detailed_section_mapping=DETAILED_SECTION_MAPPING,
    )
    split_config = {
        "shares": {"partner_a": 50.0, "partner_b": 50.0},
        "categories": ["home-cat"],
    }
    html = render(contract, "2030-04", PARTNER_LABELS, split_config=split_config)
    # Hand-computed: total 1999.996 → fair 999.998 each; delta A
    # 999.996−999.998 = −0.002, delta B +0.002 — both totals snap to 0.00.
    assert (
        '<tr class="legacy-total"><td>Total</td>'
        "<td>1,000.00</td><td>1,000.00</td><td>0.00</td>"
        "<td>1,000.00</td><td>1,000.00</td><td>0.00</td></tr>" in html
    )
    # "-0.00" nowhere in the totals row (row cells keep raw _amount
    # formatting — a pre-existing per-row quirk, out of scope here).
    # Anchor on split-table first — income/savings sections render their
    # own legacy-total rows earlier in the page, so a bare first-match
    # would slice the wrong totals row and never see the split one.
    split_start = html.index("split-table")
    totals_row = html[
        html.index('class="legacy-total"', split_start) : html.index(
            "</tbody>", split_start
        )
    ]
    assert "-0.00" not in totals_row


def test_parent_category_selection_expands_to_descendants():
    """A category_parents map lets a selected parent pull in its
    descendant leaf categories — same numbers as selecting both leaves
    directly."""
    contract = _contract()
    category_parents = {"home-cat": "root", "common-cat": "root", "root": None}
    split_config = {
        "shares": {"partner_a": 60.0, "partner_b": 40.0},
        "categories": ["root"],
    }
    html = render(
        contract,
        "2030-04",
        PARTNER_LABELS,
        split_config=split_config,
        category_parents=category_parents,
    )
    records = contract["normalized_transactions"]
    allowed_ids = _resolve_allowed_category_ids(["root"], category_parents)
    category_nets = net_category_totals(records, allowed_ids, DETAILED_SECTION_MAPPING)
    expected = compute_split(category_nets, split_config["shares"])
    assert len(expected["rows"]) == 2
    for row in expected["rows"]:
        assert f"{row['actual']:,.2f}" in html
