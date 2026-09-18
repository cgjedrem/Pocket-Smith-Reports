"""Render the generic monthly accounting contract to standalone HTML."""

from html import escape
from pathlib import Path

from accounting import _paired_reimbursements
from charts import (
    COLOR_PARTNER_A,
    COLOR_PARTNER_B,
    render_horizontal_bar,
    render_partner_kpi_matrix,
)

# Shared SCSS — extracted from inline _REPORT_STYLES.
# CLI + React both read same file. Fallback to inline if missing.
_SHARED_SCSS_PATH = (
    Path(__file__).resolve().parents[2]
    / "client"
    / "src"
    / "styles"
    / "report-shared.scss"
)


def _load_shared_styles() -> str:
    """Read shared SCSS file. Fallback to inline _REPORT_STYLES if missing."""
    if _SHARED_SCSS_PATH.is_file():
        return _SHARED_SCSS_PATH.read_text(encoding="utf-8")
    return _REPORT_STYLES


THEMES = {
    "minimal": {
        "background": "#eef3f4",
        "surface": "#ffffff",
        "ink": "#19303d",
        "muted": "#5d6c75",
        "rule": "#d8e3ec",
        "track": "#e7eef3",
        "partner_a": COLOR_PARTNER_A,
        "partner_b": COLOR_PARTNER_B,
        "chart_style": "rail",
    },
    "cyberpunk": {
        "background": "#080b18",
        "surface": "#11172b",
        "ink": "#e7fbff",
        "muted": "#8ca3c7",
        "rule": "#2c4168",
        "track": "#202b49",
        "partner_a": "#25e6ff",
        "partner_b": "#ff4fcf",
        "chart_style": "pulse",
    },
    "medieval": {
        "background": "#efe3c6",
        "surface": "#fff8e7",
        "ink": "#412d1d",
        "muted": "#7a6045",
        "rule": "#d7bd87",
        "track": "#ead9b4",
        "partner_a": "#315b4b",
        "partner_b": "#9a3d2c",
        "chart_style": "banner",
    },
    "oriental": {
        "background": "#f5efe4",
        "surface": "#fffdf8",
        "ink": "#28231f",
        "muted": "#796e60",
        "rule": "#d9cdb9",
        "track": "#eee5d8",
        "partner_a": "#1f4f6f",
        "partner_b": "#c3422f",
        "chart_style": "seal",
    },
}

_REPORT_STYLES = """
    @page { size: A4; margin: 14mm; }
    :root { color: #19303d; }
    * { box-sizing: border-box; }
    body { background: #eef3f4; color: #19303d; font-family: "Aptos", "DejaVu Sans", sans-serif; font-size: 10.5pt; line-height: 1.4; margin: 0; }
    .report-header { border-top: 5px solid #d4664d; margin: 0 0 18px; padding: 16px 0 0; text-align: left; }
    .eyebrow { color: #0f6b78; font-size: 9pt; font-weight: 700; margin: 0 0 5px; }
    h1 { color: #19303d; font-family: Georgia, "DejaVu Serif", serif; font-size: 28pt; line-height: 1.1; margin: 0; }
    h2 { border-bottom: 2px solid #0f6b78; color: #19303d; font-family: Georgia, "DejaVu Serif", serif; font-size: 18pt; margin: 28px 0 7px; padding: 0 0 5px; page-break-after: avoid; }
    h3 { color: #19303d; font-size: 12pt; margin: 0 0 8px; }
    .period { color: #5d6c75; font-size: 10pt; margin: 6px 0 0; }
    .note { color: #5d6c75; font-size: 9pt; margin: 6px 0; }
    table { background: #fff; border-collapse: collapse; margin: 12px 0; width: 100%; }
    th, td { border-bottom: 1px solid #d7e0e3; padding: 6px 8px; text-align: right; vertical-align: top; }
    th { background: #19303d; color: #fff; font-size: 8.5pt; font-weight: 700; text-align: left; }
    tr:nth-child(even) td { background: #f5f8f8; }
    th:first-child, td:first-child { text-align: left; }
    thead { display: table-header-group; }
    tr { break-inside: avoid-page; page-break-inside: avoid; }
    .empty { color: #5d6c75; font-style: italic; text-align: left; }
    /* Sign-color rules mirrored from report-shared.scss — the paired
       reimbursement table cells (pos/neg/zero) depend on these. */
    .legacy-table .pos { color: #2ca02c; }
    .legacy-table .neg { color: #d62728; }
    .legacy-table .zero { color: #888; }
    .report-section { break-before: page; page-break-before: always; }
    .report-section > h2 { break-after: avoid-page; page-break-after: avoid; }
        .drilldown-card, .legacy-chart { break-inside: avoid-page; page-break-inside: avoid; }
        .drilldown summary { break-after: avoid-page; page-break-after: avoid; }
        .drilldown .tx-table { break-inside: auto; page-break-inside: auto; }
    .reconciliation-ok { color: #19755b; font-weight: bold; }
    .reconciliation-review { color: #bb553e; font-weight: bold; }
    @media print { body { background: #fff; } }
"""


def _amount(value: float) -> str:
    return f"{value:,.2f}"


def _root_totals(categories: list[dict]) -> dict[str, float | int]:
    roots = [category for category in categories if category["parent_id"] is None]
    return {
        "paid": sum(category["paid"] for category in roots),
        "received": sum(category["received"] for category in roots),
        "net": sum(category["net"] for category in roots),
        "count": sum(category["count"] for category in roots),
    }


def _owner_totals(categories: list[dict]) -> dict[str, dict[str, float]]:
    totals = {
        "partner_a": {"paid": 0.0, "received": 0.0, "net": 0.0},
        "partner_b": {"paid": 0.0, "received": 0.0, "net": 0.0},
    }
    for category in categories:
        if category["parent_id"] is not None:
            continue
        for owner, owner_totals in totals.items():
            values = category["owners"][owner]
            for field in owner_totals:
                owner_totals[field] += values[field]
    return totals


def _partner_panel(label: str, values: dict[str, float], css_class: str) -> str:
    net_class = "pos" if values["net"] >= 0 else "neg"
    return (
        f'<div class="partner-box {css_class}"><h3>{escape(label)}</h3>'
        f'<div class="row"><span class="label">Paid</span><span class="val">{_amount(values["paid"])}</span></div>'
        f'<div class="row"><span class="label">Received</span><span class="val">{_amount(values["received"])}</span></div>'
        f'<div class="row"><span class="label">Net movement</span><span class="val {net_class}">{_amount(values["net"])}</span></div>'
        "</div>"
    )


def _kpi_partner_panel(
    label: str, values: dict[str, float], total_real_spend: float, css_class: str
) -> str:
    cash_class = "pos" if values["net_cash"] >= 0 else "neg"
    savings_class = "pos" if values["net_savings"] >= 0 else "neg"
    personal_share = (
        values["personal_spend"] / total_real_spend * 100 if total_real_spend else 0.0
    )
    return (
        f'<div class="partner-box {css_class}"><h3>{escape(label)}</h3>'
        f'<div class="row"><span class="label">Income</span><span class="val">{_amount(values["income"])}</span></div>'
        f'<div class="row"><span class="label">Real spend</span><span class="val">{_amount(values["real_spend"])}</span></div>'
        f'<div class="row"><span class="label">Personal spend</span><span class="val">{_amount(values["personal_spend"])} ({personal_share:.1f}%)</span></div>'
        f'<div class="row"><span class="label">Net cash</span><span class="val {cash_class}">{_amount(values["net_cash"])}</span></div>'
        f'<div class="row"><span class="label">Net saved</span><span class="val {savings_class}">{_amount(values["net_savings"])}</span></div>'
        "</div>"
    )


def _role_kpi_summary(kpis: dict[str, dict[str, float]], net_movement: float) -> str:
    total = kpis["total"]
    cards = (
        ("Total income", total["income"]),
        ("Real spend", total["real_spend"]),
        ("Net movement", net_movement),
        ("Net cash", total["net_cash"]),
        ("Net savings", total["net_savings"]),
    )
    markup = []
    for label, amount in cards:
        negative = " net-negative" if amount < 0 else ""
        markup.append(
            f'<div class="metric{negative}"><span class="metric-label">{label}</span>'
            f'<span class="metric-value">{_amount(amount)}</span></div>'
        )
    return "".join(markup)


def _kpi_overview_charts(
    kpis: dict[str, dict[str, float]],
    partner_labels: dict[str, str],
    theme: dict[str, str],
) -> str:
    chart_definitions = (
        ("1. Income", "income"),
        ("2. Real spend", "real_spend"),
        ("3. Net savings", "net_savings"),
    )
    series = []
    for title, field in chart_definitions:
        series.append(
            (
                title,
                [
                    (
                        partner_labels["partner_a"],
                        kpis["partner_a"][field],
                        theme["partner_a"],
                    ),
                    (
                        partner_labels["partner_b"],
                        kpis["partner_b"][field],
                        theme["partner_b"],
                    ),
                ],
            )
        )
    return (
        '<section class="overview-chart overview-matrix">'
        f"{render_partner_kpi_matrix(series, theme, width=720, style=theme['chart_style'])}"
        "</section>"
    )


def _category_highlights(categories: list[dict]) -> str:
    roots = [category for category in categories if category["parent_id"] is None]
    if not roots:
        return '<p class="empty">No reportable category movements.</p>'
    highlights = sorted(roots, key=lambda category: abs(category["net"]), reverse=True)[
        :5
    ]
    largest = max(abs(category["net"]) for category in highlights) or 1
    rows = []
    for category in highlights:
        width = abs(category["net"]) / largest * 100
        rows.append(
            '<div class="category-highlight">'
            f'<div class="highlight-title">{escape(category["title"])}</div>'
            f'<div class="bar-track"><div class="bar" style="width:{width:.1f}%"></div></div>'
            f'<div class="highlight-value">{_amount(category["net"])} net</div></div>'
        )
    return "".join(rows)


def _subcategory_overviews(categories: list[dict]) -> str:
    roots = [category for category in categories if category["parent_id"] is None]
    sections = []
    for root in roots:
        children = [
            category for category in categories if category["parent_id"] == root["id"]
        ]
        if not children:
            continue
        children.sort(key=lambda category: abs(category["net"]), reverse=True)
        largest = max(abs(category["net"]) for category in children) or 1
        rows = []
        for category in children:
            width = abs(category["net"]) / largest * 100
            rows.append(
                '<div class="category-highlight">'
                f'<div class="highlight-title">{escape(category["title"])}</div>'
                f'<div class="bar-track"><div class="bar" style="width:{width:.1f}%"></div></div>'
                f'<div class="highlight-value">{_amount(category["net"])} net</div></div>'
            )
        sections.append(
            f'<section class="subcat-chart"><h3>{escape(root["title"])} subcategories</h3>'
            f"{''.join(rows)}</section>"
        )
    return "".join(sections) or '<p class="empty">No subcategories to compare.</p>'


def _transaction_drilldowns(records: list[dict], partner_labels: dict[str, str]) -> str:
    groups: dict[tuple[str, str], dict[str, object]] = {}
    for record in records:
        path = record["category_path"]
        root, leaf = path[0], path[-1]
        key = (root["id"], leaf["id"])
        group = groups.setdefault(
            key,
            {"root": root, "leaf": leaf, "records": []},
        )
        group["records"].append(record)

    cards = []
    for group in sorted(
        groups.values(),
        key=lambda item: (item["root"]["title"], item["leaf"]["title"]),
    ):
        root = group["root"]
        leaf = group["leaf"]
        title = (
            leaf["title"]
            if root["id"] == leaf["id"]
            else f'{root["title"]} / {leaf["title"]}'
        )
        rows = []
        for record in sorted(
            group["records"], key=lambda item: (item["date"], item["id"] or "")
        ):
            owner = partner_labels[record["owner"]]
            payee = record["payee"] or "Unspecified"
            note = record["note"] or "-"
            rows.append(
                "<tr>"
                f'<td>{escape(record["date"])}</td><td>{escape(payee)}</td>'
                f"<td>{escape(owner)}</td><td>{escape(note)}</td>"
                f'<td>{record["amount"]:+,.2f}</td></tr>'
            )
        cards.append(
            '<section class="drilldown-card">'
            f"<h3>{escape(title)}</h3>"
            '<table class="tx-table"><thead><tr><th>Date</th><th>Payee</th><th>Owner</th><th>Note</th><th>Amount</th></tr></thead>'
            f"<tbody>{''.join(rows)}</tbody></table></section>"
        )
    return "".join(cards) or '<p class="empty">No reportable transactions.</p>'


def _category_rows(categories: list[dict]) -> str:
    if not categories:
        return '<tr><td class="empty" colspan="5">No reportable movements.</td></tr>'
    rows = []
    for category in categories:
        depth = max(len(category["path"]) - 1, 0)
        title = "&nbsp;" * (depth * 4) + escape(category["title"])
        rows.append(
            "<tr>"
            f"<td>{title}</td><td>{_amount(category['paid'])}</td>"
            f"<td>{_amount(category['received'])}</td><td>{_amount(category['net'])}</td>"
            f"<td>{category['count']}</td>"
            "</tr>"
        )
    return "".join(rows)


def _detailed_section(record: dict, mapping: dict[str, dict[str, str]]) -> str:
    category_id = record["category_path"][-1]["id"]
    return mapping["category_sections"].get(category_id, "common")


def _routed_detailed_section(record: dict, mapping: dict[str, dict[str, str]]) -> str:
    # Transfers route to Excluded unless their category is Home/Savings/Excluded.
    section = _detailed_section(record, mapping)
    if record.get("is_transfer") and section not in {"home", "savings", "excluded"}:
        return "excluded"
    return section


def _legacy_section_rows(
    records: list[dict],
    section: str,
    partner_labels: dict[str, str],
    mapping: dict[str, dict[str, str]],
) -> str:
    categories: dict[str, dict[str, float | str]] = {}
    for record in records:
        category = record["category_path"][-1]
        record_section = _routed_detailed_section(record, mapping)
        if record_section != section:
            continue
        root = record["category_path"][0]
        category_title = (
            category["title"]
            if root["id"] == category["id"]
            else f'{root["title"]} / {category["title"]}'
        )
        row = categories.setdefault(
            category["id"],
            {"title": category_title, "partner_a": 0.0, "partner_b": 0.0, "total": 0.0},
        )
        amount = max(-record["amount"], 0.0)
        row[record["owner"]] += amount
        row["total"] += amount
    if not categories:
        return '<p class="empty">No reportable movements.</p>'
    rows = []
    totals = {"partner_a": 0.0, "partner_b": 0.0, "total": 0.0}
    for row in sorted(categories.values(), key=lambda item: -item["total"]):
        for key in totals:
            totals[key] += row[key]
        rows.append(
            f'<tr><td>{escape(row["title"])}</td><td>{_amount(row["partner_a"])}</td>'
            f'<td>{_amount(row["partner_b"])}</td><td>{_amount(row["total"])}</td></tr>'
        )
    return (
        '<table class="legacy-table"><thead><tr><th>Category</th>'
        f'<th>{escape(partner_labels["partner_a"])} paid</th>'
        f'<th>{escape(partner_labels["partner_b"])} paid</th><th>Total</th></tr></thead><tbody>'
        f'{"".join(rows)}<tr class="legacy-total"><td>Section total</td>'
        f'<td>{_amount(totals["partner_a"])}</td><td>{_amount(totals["partner_b"])}</td>'
        f'<td>{_amount(totals["total"])}</td></tr></tbody></table>'
    )


def _income_section(
    records: list[dict],
    partner_labels: dict[str, str],
    mapping: dict[str, dict[str, str]],
) -> str:
    income_records = [
        record
        for record in records
        if _routed_detailed_section(record, mapping)
        in {"income_salary", "income_third_party"}
    ]
    sources = {
        "salary": {"partner_a": 0.0, "partner_b": 0.0},
        "third_party": {"partner_a": 0.0, "partner_b": 0.0},
    }
    drilldowns: dict[str, list[dict]] = {
        "Salary": [],
        "Third Party Income": [],
    }
    for record in income_records:
        source = (
            "salary"
            if _detailed_section(record, mapping) == "income_salary"
            else "third_party"
        )
        sources[source][record["owner"]] += record["amount"]
        drilldowns[("Salary" if source == "salary" else "Third Party Income")].append(
            record
        )
    salary = sources["salary"]
    third_party = sources["third_party"]
    total_a = salary["partner_a"] + third_party["partner_a"]
    total_b = salary["partner_b"] + third_party["partner_b"]
    total_income = total_a + total_b

    def row(label: str, values: dict[str, float], total: float) -> str:
        # per-row pct: partner share of that row's total
        # household pct: row share of total income
        return (
            f"<tr><td>{label}</td><td>{_amount(values['partner_a'])}</td>"
            f"<td>{_amount(values['partner_b'])}</td><td>{_amount(total)}</td>"
            f"<td><b>{values['partner_a'] / total * 100 if total else 0:.1f}%</b></td>"
            f"<td><b>{values['partner_b'] / total * 100 if total else 0:.1f}%</b></td>"
            f"<td><b>{total / total_income * 100 if total_income else 0:.1f}%</b></td></tr>"
        )

    parts = [
        '<section class="report-section legacy-section"><h2>1. Income</h2>'
        '<table class="legacy-table income-table"><thead><tr><th>Source</th>'
        f'<th>{escape(partner_labels["partner_a"])}</th><th>{escape(partner_labels["partner_b"])}</th>'
        f'<th>Total</th><th>% {escape(partner_labels["partner_a"])}</th>'
        f'<th>% {escape(partner_labels["partner_b"])}</th><th>% of income</th></tr></thead><tbody>',
        row("Salary", salary, salary["partner_a"] + salary["partner_b"]),
        row(
            "Third Party Income",
            third_party,
            third_party["partner_a"] + third_party["partner_b"],
        ),
        f'<tr class="legacy-total"><td>Total Income</td><td>{_amount(total_a)}</td><td>{_amount(total_b)}</td>'
        f"<td>{_amount(total_income)}</td><td>{total_a / total_income * 100 if total_income else 0:.1f}%</td>"
        f"<td>{total_b / total_income * 100 if total_income else 0:.1f}%</td><td>100.0%</td></tr></tbody></table>",
        f'<p class="note">Note: <b>% {escape(partner_labels["partner_a"])}</b> = {escape(partner_labels["partner_a"])}&apos;s amount / row total. '
        f'<b>% {escape(partner_labels["partner_b"])}</b> = {escape(partner_labels["partner_b"])}&apos;s amount / row total. '
        "<b>% of income</b> = row total / household total.</p>",
    ]
    for label, source_records in drilldowns.items():
        if not source_records:
            continue
        rows = []
        for record in sorted(
            source_records, key=lambda item: (item["date"], item["id"] or "")
        ):
            rows.append(
                f'<tr><td>{escape(record["date"])}</td><td>{escape(record["payee"] or "Unspecified")}</td>'
                f'<td>{escape(partner_labels[record["owner"]])}</td><td>{escape(record["note"] or "-")}</td>'
                f'<td>{record["amount"]:+,.2f}</td></tr>'
            )
        source_total = sum(record["amount"] for record in source_records)
        parts.append(
            '<section class="drilldown-card">'
            f"<h3>{label} - {_amount(source_total)} NOK - {len(source_records)} txns</h3>"
            '<table class="tx-table"><thead><tr><th>Date</th><th>Payee</th><th>Account</th><th>Note</th><th>Amount</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></section>'
        )
    parts.append("</section>")
    return "".join(parts)


def _savings_section(
    records: list[dict],
    savings_summary: dict[str, dict[str, float]],
    partner_labels: dict[str, str],
    mapping: dict[str, dict[str, str]],
) -> str:
    savings_records = [
        record
        for record in records
        if _routed_detailed_section(record, mapping) == "savings"
    ]
    incomes = {"partner_a": 0.0, "partner_b": 0.0}
    for record in records:
        section = _routed_detailed_section(record, mapping)
        if section in {"income_salary", "income_third_party"}:
            incomes[record["owner"]] += record["amount"]

    def values(owner: str) -> tuple[float, float, float, float, float]:
        incoming = savings_summary[owner]["to_savings"]
        outgoing = savings_summary[owner]["from_savings"]
        net_saved = savings_summary[owner]["net_saved"]
        income = incomes[owner]
        rate = net_saved / income * 100 if income else 0.0
        return incoming, outgoing, net_saved, income, rate

    partner_a = values("partner_a")
    partner_b = values("partner_b")
    household = tuple(partner_a[index] + partner_b[index] for index in range(4))
    household_rate = household[2] / household[3] * 100 if household[3] else 0.0
    parts = [
        '<section class="report-section legacy-section"><h2>2. Savings</h2>',
        '<table class="legacy-table savings-table"><thead><tr><th>Partner</th>'
        "<th>To savings (in)</th><th>From savings (out)</th><th>Net saved</th>"
        "<th>Income</th><th>Savings rate</th></tr></thead><tbody>",
    ]
    for label, row in (
        (partner_labels["partner_a"], partner_a),
        (partner_labels["partner_b"], partner_b),
    ):
        parts.append(
            f"<tr><td>{escape(label)}</td><td>{_amount(row[0])}</td><td>{_amount(row[1])}</td>"
            f"<td><b>{_amount(row[2])}</b></td><td>{_amount(row[3])}</td><td>{row[4]:.1f}%</td></tr>"
        )
    parts.append(
        f'<tr class="legacy-total"><td>Household</td><td>{_amount(household[0])}</td>'
        f"<td>{_amount(household[1])}</td><td>{_amount(household[2])}</td>"
        f"<td>{_amount(household[3])}</td><td>{household_rate:.1f}%</td></tr></tbody></table>"
    )
    groups: dict[str, list[dict]] = {}
    for record in savings_records:
        groups.setdefault(record["category_path"][-1]["title"], []).append(record)
    for title, group in groups.items():
        total = sum(abs(record["amount"]) for record in group)
        rows = []
        for record in sorted(group, key=lambda item: (item["date"], item["id"] or "")):
            rows.append(
                f'<tr><td>{escape(record["date"])}</td><td>{escape(record["payee"] or "Unspecified")}</td>'
                f'<td>{escape(record["account_name"] or partner_labels[record["owner"]])}</td>'
                f'<td>{escape(record["note"] or "-")}</td><td>{record["amount"]:+,.2f}</td></tr>'
            )
        parts.append(
            '<section class="drilldown-card">'
            f"<h3>{escape(title)} - {_amount(total)} NOK - {len(group)} txns</h3>"
            '<table class="tx-table"><thead><tr><th>Date</th><th>Payee</th><th>Account</th><th>Note</th><th>Amount</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></section>'
        )
    parts.append("</section>")
    return "".join(parts)


def _legacy_records(
    records: list[dict], section: str, mapping: dict[str, dict[str, str]]
) -> list[dict]:
    return [
        record
        for record in records
        if _routed_detailed_section(record, mapping) == section
    ]


def _legacy_category_groups(records: list[dict]) -> list[dict]:
    groups: dict[str, dict] = {}
    for record in records:
        category = record["category_path"][-1]
        root = record["category_path"][0]
        title = (
            category["title"]
            if root["id"] == category["id"]
            else f'{root["title"]} / {category["title"]}'
        )
        group = groups.setdefault(
            category["id"],
            {
                "title": title,
                "paid": {"partner_a": 0.0, "partner_b": 0.0},
                "received": {"partner_a": 0.0, "partner_b": 0.0},
                "records": [],
            },
        )
        group["records"].append(record)
        direction = "paid" if record["amount"] < 0 else "received"
        group[direction][record["owner"]] += abs(record["amount"])
    return sorted(
        groups.values(),
        key=lambda group: -sum(abs(record["amount"]) for record in group["records"]),
    )


def _legacy_drilldown(groups: list[dict]) -> str:
    parts = []
    for group in groups:
        records = group["records"]
        total = sum(abs(record["amount"]) for record in records)
        rows = []
        for record in sorted(
            records, key=lambda item: (item["date"], item["id"] or "")
        ):
            rows.append(
                f'<tr><td>{escape(record["date"])}</td><td>{escape(record["payee"] or "")}</td>'
                f'<td>{escape(record["account_name"] or "")}</td><td>{escape(record["note"] or "")}</td>'
                f'<td>{record["amount"]:+,.2f}</td></tr>'
            )
        parts.append(
            '<details class="drilldown"><summary>'
            f'<b>{escape(group["title"])}</b> - {_amount(total)} NOK - {len(records)} txns'
            '</summary><table class="tx-table"><thead><tr><th>Date</th><th>Payee</th><th>Account</th><th>Note</th><th>Amount</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></details>'
        )
    return "".join(parts)


def _legacy_section_chart(
    groups: list[dict], title: str, theme: dict[str, str], bar_height: int = 40
) -> str:
    data = []
    for group in groups:
        total = (
            group["paid"]["partner_a"]
            + group["paid"]["partner_b"]
            - group["received"]["partner_a"]
            - group["received"]["partner_b"]
        )
        if total > 0:
            data.append((group["title"], total))
    if not data:
        return ""
    return (
        '<section class="legacy-chart">'
        f'{render_horizontal_bar(data, title=title, width=1100, bar_height=bar_height, color_map={group["title"]: theme["partner_a"] if index % 2 == 0 else theme["partner_b"] for index, group in enumerate(groups)}, ink=theme["ink"], track=theme["track"])}'
        "</section>"
    )


def _legacy_net_section(
    title: str,
    records: list[dict],
    section: str,
    partner_labels: dict[str, str],
    theme: dict[str, str],
    mapping: dict[str, dict[str, str]],
    note: str = "",
    chart_title: str = "",
    chart_bar_height: int = 40,
) -> str:
    groups = _legacy_category_groups(_legacy_records(records, section, mapping))
    parts = [f'<section class="report-section legacy-section"><h2>{title}</h2>']
    if not groups:
        parts.append('<p class="empty">No data this month.</p></section>')
        return "".join(parts)
    totals = {"partner_a": 0.0, "partner_b": 0.0}
    rows = []
    paired_rows = []
    for group in groups:
        net_a = group["paid"]["partner_a"] - group["received"]["partner_a"]
        net_b = group["paid"]["partner_b"] - group["received"]["partner_b"]
        total = net_a + net_b
        totals["partner_a"] += net_a
        totals["partner_b"] += net_b
        paired = _paired_reimbursements(group)
        if paired:
            for first, second in paired:
                received = first if first["amount"] > 0 else second
                paid = second if first["amount"] > 0 else first
                amount = abs(received["amount"])
                values = {
                    "partner_a": (
                        f"+{_amount(amount)}"
                        if received["owner"] == "partner_a"
                        else f"-{_amount(amount)}"
                    ),
                    "partner_b": (
                        f"+{_amount(amount)}"
                        if received["owner"] == "partner_b"
                        else f"-{_amount(amount)}"
                    ),
                }
                # Sign classes mirror the React DTO (`_sign_class` in
                # accounting.py): recipient column "pos", payer column "neg",
                # the always-zero total column "zero" — .legacy-table SCSS
                # rules color them green/red/muted in both renderers.
                classes = {
                    "partner_a": (
                        "pos" if received["owner"] == "partner_a" else "neg"
                    ),
                    "partner_b": (
                        "pos" if received["owner"] == "partner_b" else "neg"
                    ),
                }
                paired_rows.append(
                    f'<tr class="reimb-row"><td><i>{escape(group["title"])} (paired reimbursement)</i></td>'
                    f'<td class="{classes["partner_a"]}">{values["partner_a"]}</td>'
                    f'<td class="{classes["partner_b"]}">{values["partner_b"]}</td>'
                    f'<td class="zero"><b>0.00</b></td></tr>'
                )
        share_a = net_a / total * 100 if total else 0.0
        share_b = net_b / total * 100 if total else 0.0
        if not paired or total:
            rows.append(
                f'<tr><td>{escape(group["title"])}</td><td>{_amount(net_a)}</td><td>{_amount(net_b)}</td>'
                f"<td><b>{_amount(total)}</b></td><td><b>{share_a:.1f}%</b> / {share_b:.1f}%</td></tr>"
            )
    total = totals["partner_a"] + totals["partner_b"]
    total_share_a = totals["partner_a"] / total * 100 if total else 0.0
    total_share_b = totals["partner_b"] / total * 100 if total else 0.0
    paired_table = ""
    if paired_rows:
        paired_table = (
            '<table class="legacy-table net-table">'
            "<caption>Paired reimbursements (net 0, shown for transparency)</caption>"
            f'<thead><tr><th>Category</th><th>{escape(partner_labels["partner_a"])}</th>'
            f'<th>{escape(partner_labels["partner_b"])}</th><th>Total</th></tr></thead>'
            f'<tbody>{"".join(paired_rows)}</tbody></table>'
        )
    parts.extend(
        [
            '<table class="legacy-table net-table"><thead><tr><th>Category</th>'
            f'<th>{escape(partner_labels["partner_a"])} net</th>'
            f'<th>{escape(partner_labels["partner_b"])} net</th><th>Total</th>'
            f"<th>% {escape(partner_labels['partner_a'])} / {escape(partner_labels['partner_b'])}</th></tr></thead><tbody>",
            "".join(rows),
            f'<tr class="legacy-total"><td>Total</td><td>{_amount(totals["partner_a"])}</td><td>{_amount(totals["partner_b"])}</td><td>{_amount(total)}</td><td>{total_share_a:.1f}% / {total_share_b:.1f}%</td></tr></tbody></table>',
            note,
            paired_table,
            (
                _legacy_section_chart(groups, chart_title, theme, chart_bar_height)
                if chart_title
                else ""
            ),
            _legacy_drilldown(groups),
            "</section>",
        ]
    )
    return "".join(parts)


def _cc_payments_section(
    records: list[dict],
    partner_labels: dict[str, str],
    mapping: dict[str, dict[str, str]],
) -> str:
    payments = [
        record
        for record in records
        if _routed_detailed_section(record, mapping) == "cc_payments"
        and record["amount"] < 0
    ]
    totals = {
        owner: sum(-record["amount"] for record in payments if record["owner"] == owner)
        for owner in ("partner_a", "partner_b")
    }
    household = totals["partner_a"] + totals["partner_b"]
    parts = [
        '<section class="report-section legacy-section"><h2>8. CC Payments</h2>',
        '<table class="legacy-table cc-payment-table"><thead><tr><th>Owner</th><th>CC paid</th></tr></thead><tbody>',
        f'<tr><td>{escape(partner_labels["partner_a"])}</td><td>{_amount(totals["partner_a"])}</td></tr>',
        f'<tr><td>{escape(partner_labels["partner_b"])}</td><td>{_amount(totals["partner_b"])}</td></tr>',
        f'<tr class="legacy-total"><td>Household</td><td>{_amount(household)}</td></tr></tbody></table>',
    ]
    if payments:
        rows = []
        for record in sorted(
            payments, key=lambda item: (item["date"], item["id"] or "")
        ):
            rows.append(
                f'<tr><td>{escape(record["date"])}</td><td>{escape(record["payee"] or "Unspecified")}</td>'
                f'<td>{escape(record["account_name"] or partner_labels[record["owner"]])}</td>'
                f'<td>{-record["amount"]:,.2f}</td></tr>'
            )
        parts.extend(
            [
                '<details class="drilldown"><summary>CC payment details</summary>',
                '<table class="tx-table"><thead><tr><th>Date</th><th>Payee</th><th>Account</th><th>Paid</th></tr></thead>',
                f'<tbody>{"".join(rows)}</tbody></table></details>',
            ]
        )
    return "".join(parts) + "</section>"


def _legacy_personal_sections(
    records: list[dict],
    partner_labels: dict[str, str],
    theme: dict[str, str],
    mapping: dict[str, dict[str, str]],
) -> str:
    grouped = {
        section: _legacy_category_groups(_legacy_records(records, section, mapping))
        for section in ("personal_partner_a", "personal_partner_b")
    }
    personal_total = sum(
        group["paid"]["partner_a"]
        + group["paid"]["partner_b"]
        - group["received"]["partner_a"]
        - group["received"]["partner_b"]
        for groups in grouped.values()
        for group in groups
    )
    household_total = sum(
        group["paid"]["partner_a"]
        + group["paid"]["partner_b"]
        - group["received"]["partner_a"]
        - group["received"]["partner_b"]
        for section in (
            "home",
            "common",
            "personal_partner_a",
            "personal_partner_b",
            "trips",
        )
        for group in _legacy_category_groups(_legacy_records(records, section, mapping))
    )
    parts = []
    for number, section, partner_key in (
        (5, "personal_partner_a", "partner_a"),
        (6, "personal_partner_b", "partner_b"),
    ):
        partner_label = partner_labels[partner_key]
        title = f"{number}. {partner_label}"
        groups = grouped[section]
        parts.append(
            f'<section class="report-section legacy-section"><h2>{escape(title)}</h2>'
        )
        if not groups:
            parts.append(
                '<p class="empty">No personal spending this month.</p></section>'
            )
            continue
        rows = []
        subtotal = 0.0
        for group in groups:
            paid_a = group["paid"]["partner_a"]
            paid_b = group["paid"]["partner_b"]
            total = (
                paid_a
                + paid_b
                - group["received"]["partner_a"]
                - group["received"]["partner_b"]
            )
            subtotal += total
            rows.append(
                f'<tr><td>{escape(group["title"])}</td><td>{_amount(paid_a)}</td><td>{_amount(paid_b)}</td><td><b>{_amount(total)}</b></td>'
                f"<td><b>{total / personal_total * 100 if personal_total else 0:.1f}%</b></td><td><b>{total / household_total * 100 if household_total else 0:.1f}%</b></td></tr>"
            )
        parts.extend(
            [
                '<table class="legacy-table personal-table"><thead><tr><th>Category</th>'
                f'<th>{escape(partner_labels["partner_a"])} paid</th>'
                f'<th>{escape(partner_labels["partner_b"])} paid</th><th>Total</th>'
                "<th>% of personal</th><th>% of total spending</th></tr></thead><tbody>",
                "".join(rows),
                f'<tr class="legacy-total"><td>Subtotal</td><td></td><td></td><td>{_amount(subtotal)}</td><td>100.0%</td><td>{subtotal / household_total * 100 if household_total else 0:.1f}%</td></tr></tbody></table>',
                _legacy_section_chart(
                    groups,
                    f"{partner_label} personal by category",
                    theme,
                    36,
                ),
                _legacy_drilldown(groups),
                "</section>",
            ]
        )
    return "".join(parts)


def _legacy_excluded_section(
    records: list[dict],
    partner_labels: dict[str, str],
    mapping: dict[str, dict[str, str]],
) -> str:
    groups = _legacy_category_groups(_legacy_records(records, "excluded", mapping))
    parts = [
        '<section class="report-section legacy-section"><h2>9. Excluded (Internal transfers)</h2>'
    ]
    if not groups:
        return (
            "".join(parts)
            + '<p class="empty">No excluded items this month.</p></section>'
        )
    rows = []
    total = 0.0
    for group in groups:
        paid_a = sum(
            abs(record["amount"])
            for record in group["records"]
            if record["owner"] == "partner_a"
        )
        paid_b = sum(
            abs(record["amount"])
            for record in group["records"]
            if record["owner"] == "partner_b"
        )
        category_total = paid_a + paid_b
        total += category_total
        rows.append(
            f'<tr><td>{escape(group["title"])}</td><td>{_amount(paid_a)}</td><td>{_amount(paid_b)}</td><td>{_amount(category_total)}</td></tr>'
        )
    parts.extend(
        [
            '<table class="legacy-table excluded-table"><thead><tr><th>Category</th>'
            f'<th>{escape(partner_labels["partner_a"])} paid</th>'
            f'<th>{escape(partner_labels["partner_b"])} paid</th><th>Total</th></tr></thead><tbody>',
            "".join(rows),
            f'<tr class="legacy-total"><td>Total Excluded</td><td></td><td></td><td>{_amount(total)}</td></tr></tbody></table>',
            '<p class="note">Only categories explicitly mapped to Excluded appear here.</p>',
            _legacy_drilldown(groups),
            "</section>",
        ]
    )
    return "".join(parts)


def _legacy_sections(
    records: list[dict],
    savings_summary: dict[str, dict[str, float]],
    partner_labels: dict[str, str],
    theme: dict[str, str],
    mapping: dict[str, dict[str, str]],
) -> str:
    home_note = '<p class="note">The Home reimbursement rows show both cash legs. They cancel in household total, while the partner net columns show who actually paid after reimbursement.</p>'
    common_note = '<p class="note">The Common net columns subtract reimbursements from the recipient and add them to the sender. No 50/50 split is assumed.</p>'
    return (
        _income_section(records, partner_labels, mapping)
        + _savings_section(records, savings_summary, partner_labels, mapping)
        + _legacy_net_section(
            "3. Home (Mortgage, Per Olav Loan, USBL, Insurance)",
            records,
            "home",
            partner_labels,
            theme,
            mapping,
            home_note,
        )
        + _legacy_net_section(
            "4. Common (Groceries, Hello Fresh, Restaurants, etc.)",
            records,
            "common",
            partner_labels,
            theme,
            mapping,
            common_note,
            "Common spending by category",
        )
        + _legacy_personal_sections(records, partner_labels, theme, mapping)
        + _legacy_net_section(
            "7. Trips (Common + Personal)",
            records,
            "trips",
            partner_labels,
            theme,
            mapping,
            chart_title="Trips spending by category",
            chart_bar_height=50,
        )
        + _cc_payments_section(records, partner_labels, mapping)
        + _legacy_excluded_section(records, partner_labels, mapping)
    )


def render(
    contract: dict,
    month: str,
    partner_labels: dict[str, str] | None = None,
    theme_name: str = "minimal",
) -> str:
    """Render a report with categories, transfer appendix, and reconciliation."""
    reconciliation = contract["reconciliation"]
    totals = _root_totals(contract["categories"])
    owners = _owner_totals(contract["categories"])
    kpis = contract.get("kpis")
    detailed_section_mapping = contract.get(
        "detailed_section_mapping", {"category_sections": {}, "account_roles": {}}
    )
    partner_labels = partner_labels or {
        "partner_a": "Partner A",
        "partner_b": "Partner B",
    }
    if theme_name not in THEMES:
        raise ValueError(f"Unknown report theme: {theme_name}")
    theme = THEMES[theme_name]
    balanced = reconciliation["difference"] == 0
    styles = _load_shared_styles() + """
        .overview-page header { margin-bottom: 14px; text-align: center; }
        .overview-page h1 { color: #1f77b4; font-family: Arial, sans-serif; font-size: 26pt; line-height: 1.1; margin: 0 0 4px; }
        .overview-page .period { color: #555; font-size: 11pt; margin: 0; }
        .summary { display: flex; flex-wrap: wrap; gap: 12px; margin: 12px 0 18px; }
        .metric { background: #f0f7fc; border: 1px solid #1f77b4; border-radius: 6px; flex: 1 1 30%; min-width: 0; overflow-wrap: anywhere; padding: 12px; text-align: center; }
        .metric-label { color: #555; display: block; font-size: 10pt; }
        .metric-value { color: #1f77b4; display: block; font-family: Arial, sans-serif; font-size: 20pt; font-weight: 700; margin-top: 4px; }
        .metric.net-negative .metric-value { color: #d62728; }
        .partner-row { display: flex; gap: 12px; margin: 12px 0 18px; }
        .partner-box { background: #fff; border: 1px solid #ccc; border-radius: 6px; flex: 1; padding: 12px; }
        .partner-box.partner-a { border-color: #1f77b4; }
        .partner-box.partner-b { border-color: #ff7f0e; }
        .partner-box .row { border-bottom: 1px solid #eee; display: flex; justify-content: space-between; padding: 4px 0; }
        .partner-box .row:last-child { border-bottom: none; }
        .partner-box .label { color: #555; }
        .partner-box .val { font-weight: 700; }
        .partner-box .pos { color: #2ca02c; }
        .partner-box .neg { color: #d62728; }
        .overview-page { display: flex; flex-direction: column; min-height: 269mm; page-break-after: always; }
        .overview-charts { display: flex; flex: 1; flex-direction: column; gap: 10px; min-height: 0; }
        .overview-chart { align-items: flex-start; background: var(--theme-surface); border: 1px solid var(--theme-rule); border-radius: 4px; display: flex; flex: 1; min-height: 0; overflow: hidden; padding: 8px; }
        .overview-chart svg { display: block; height: auto; margin: 0 auto; max-width: 720px; width: 100%; }
        .highlights { display: grid; gap: 8px; margin: 12px 0; }
        .category-highlight { display: grid; gap: 6px; grid-template-columns: 32% 1fr 18%; align-items: center; }
        .highlight-title { font-weight: 700; }
        .highlight-value { font-variant-numeric: tabular-nums; text-align: right; }
        .bar-track { background: #e8edf2; height: 10px; }
        .bar { background: #0f6b78; height: 100%; }
        .subcat-chart { background: #fff; border: 1px solid #d7e0e3; border-radius: 4px; margin: 12px 0; padding: 12px; }
        .tx-table { font-size: 8.5pt; }
        .tx-table td:last-child, .tx-table th:last-child { text-align: right; }
        .drilldown-card { background: #fff; border: 1px solid #d7e0e3; border-radius: 4px; margin: 10px 0; padding: 10px; page-break-inside: avoid; }
        .legacy-table .legacy-total td { font-weight: 700; }
        .legacy-chart { margin: 16px 0; padding: 12px; page-break-inside: avoid; }
        .legacy-chart svg { display: block; height: auto; max-width: 100%; width: 100%; }
    """
    theme_styles = f"""
        body.theme-{theme_name} {{ background: {theme['background']}; color: {theme['ink']}; --theme-surface: {theme['surface']}; --theme-rule: {theme['rule']}; }}
        body.theme-{theme_name} .overview-page {{ background: {theme['background']}; }}
        body.theme-{theme_name} .metric {{ background: {theme['surface']}; border-color: {theme['partner_a']}; }}
        body.theme-{theme_name} .metric-value, body.theme-{theme_name} .overview-page h1 {{ color: {theme['partner_a']}; }}
        body.theme-{theme_name} .partner-box {{ background: {theme['surface']}; border-color: {theme['partner_a']}; }}
        body.theme-{theme_name} .partner-box.partner-b {{ border-color: {theme['partner_b']}; }}
        body.theme-{theme_name} .partner-box .label, body.theme-{theme_name} .overview-page .period {{ color: {theme['muted']}; }}
        body.theme-{theme_name} .partner-box .val {{ color: {theme['ink']}; }}
        body.theme-{theme_name} .partner-box .pos {{ color: #2ca02c; }}
        body.theme-{theme_name} .partner-box .neg, body.theme-{theme_name} .metric.net-negative .metric-value {{ color: #d62728; }}
        body.theme-{theme_name} .legacy-section {{ background: {theme['background']}; color: {theme['ink']}; }}
        body.theme-{theme_name} .legacy-section h2 {{ border-bottom-color: {theme['partner_a']}; color: {theme['ink']}; }}
        body.theme-{theme_name} .legacy-section h3 {{ color: {theme['ink']}; }}
        body.theme-{theme_name} .legacy-section .note, body.theme-{theme_name} .legacy-section .empty {{ color: {theme['muted']}; }}
        body.theme-{theme_name} .legacy-section table {{ background: {theme['surface']}; }}
        body.theme-{theme_name} .legacy-section th {{ background: {theme['ink']}; color: {theme['surface']}; }}
        body.theme-{theme_name} .legacy-section th, body.theme-{theme_name} .legacy-section td {{ border-bottom-color: {theme['rule']}; }}
        body.theme-{theme_name} .legacy-section tr:nth-child(even) td {{ background: {theme['track']}; }}
        body.theme-{theme_name} .legacy-section .legacy-total td {{ background: {theme['surface']}; border-top: 2px solid {theme['partner_a']}; }}
        body.theme-{theme_name} .legacy-section .drilldown {{ background: {theme['surface']}; border: 1px solid {theme['rule']}; margin: 12px 0; padding: 8px; }}
        body.theme-{theme_name} .legacy-section .drilldown summary {{ color: {theme['ink']}; cursor: pointer; }}
        body.theme-{theme_name} .legacy-chart {{ background: {theme['surface']}; border: 2px solid {theme['partner_a']}; border-radius: 4px; }}
        body.theme-cyberpunk .overview-page {{ border: 1px solid #25e6ff; box-shadow: 0 0 22px #25e6ff55; font-family: "DejaVu Sans Mono", monospace; padding: 12px; }}
        body.theme-cyberpunk .overview-page h1 {{ letter-spacing: 1px; text-shadow: 0 0 9px #25e6ff; }}
        body.theme-cyberpunk .metric, body.theme-cyberpunk .partner-box {{ box-shadow: inset 0 0 15px #25e6ff1f; border-radius: 0; }}
        body.theme-cyberpunk .legacy-section {{ font-family: "DejaVu Sans Mono", monospace; }}
        body.theme-cyberpunk .legacy-chart {{ box-shadow: inset 0 0 18px #25e6ff1f, 0 0 14px #25e6ff44; border-radius: 0; }}
        body.theme-medieval .overview-page {{ border: 8px double #a47b3c; font-family: Georgia, "DejaVu Serif", serif; padding: 10px; }}
        body.theme-medieval .overview-page h1 {{ color: #6f321f; font-family: Georgia, "DejaVu Serif", serif; }}
        body.theme-medieval .metric, body.theme-medieval .partner-box {{ border-radius: 0; box-shadow: 3px 3px 0 #d7bd87; }}
        body.theme-medieval .legacy-section {{ font-family: Georgia, "DejaVu Serif", serif; }}
        body.theme-medieval .legacy-chart, body.theme-medieval .legacy-section .drilldown {{ border-radius: 0; box-shadow: 3px 3px 0 #d7bd87; }}
        body.theme-oriental .overview-page {{ border-top: 5px solid #c3422f; border-bottom: 5px solid #1f4f6f; padding: 12px; }}
        body.theme-oriental .overview-page h1 {{ color: #c3422f; font-family: Georgia, "DejaVu Serif", serif; }}
        body.theme-oriental .metric, body.theme-oriental .partner-box {{ border-radius: 0; border-width: 1px 1px 4px; }}
        body.theme-oriental .legacy-section h2 {{ border-bottom-width: 4px; }}
        body.theme-oriental .legacy-chart {{ border-color: #c3422f #1f4f6f; border-radius: 0; }}
    """
    reconciliation_state = "Balanced" if balanced else "Review required"
    reconciliation_class = "reconciliation-ok" if balanced else "reconciliation-review"
    if kpis:
        summary_markup = _role_kpi_summary(kpis, totals["net"])
        partner_markup = _kpi_partner_panel(
            partner_labels["partner_a"],
            kpis["partner_a"],
            kpis["total"]["real_spend"],
            "partner-a",
        ) + _kpi_partner_panel(
            partner_labels["partner_b"],
            kpis["partner_b"],
            kpis["total"]["real_spend"],
            "partner-b",
        )
    else:
        net_metric_class = "metric net-negative" if totals["net"] < 0 else "metric"
        summary_markup = (
            '<div class="metric"><span class="metric-label">Paid</span>'
            f'<span class="metric-value">{_amount(totals["paid"])}</span></div>'
            '<div class="metric"><span class="metric-label">Received</span>'
            f'<span class="metric-value">{_amount(totals["received"])}</span></div>'
            f'<div class="{net_metric_class}">'
            '<span class="metric-label">Net movement</span>'
            f'<span class="metric-value">{_amount(totals["net"])}</span></div>'
            '<div class="metric"><span class="metric-label">Movements</span>'
            f'<span class="metric-value">{totals["count"]}</span></div>'
        )
        partner_markup = _partner_panel(
            partner_labels["partner_a"], owners["partner_a"], "partner-a"
        ) + _partner_panel(
            partner_labels["partner_b"], owners["partner_b"], "partner-b"
        )
    return (
        f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Monthly report {escape(month)}</title><style>{styles}{theme_styles}</style></head><body class="theme-{theme_name}">'
        '<section class="overview-page">'
        f'<header><h1>Household Financial Report - {escape(month)}</h1><p class="period">Monthly accounting report · all amounts in NOK</p></header>'
        '<section class="summary" aria-label="Report movements">'
        f"{summary_markup}</section>"
        '<section class="partner-row" aria-label="Partner movements">'
        f"{partner_markup}</section>"
        '<section class="overview-charts">'
        f"{_kpi_overview_charts(kpis, partner_labels, theme) if kpis else '<p class=\"empty\">KPI role map required for overview charts.</p>'}</section></section>"
        f"{_legacy_sections(contract.get('normalized_transactions', []), contract['savings_summary'], partner_labels, theme, detailed_section_mapping)}</body></html>"
    )


def _mom_rows(entries: dict, months: list[str]) -> str:
    children: dict[str | None, list[dict]] = {}
    for entry in entries.values():
        children.setdefault(entry["parent_id"], []).append(entry)

    ordered: list[tuple[int, dict]] = []

    def visit(parent_id: str | None, depth: int) -> None:
        for entry in sorted(
            children.get(parent_id, []), key=lambda item: (item["title"], item["id"])
        ):
            ordered.append((depth, entry))
            visit(entry["id"], depth + 1)

    visit(None, 0)
    rows = []
    for depth, entry in ordered:
        title = "&nbsp;" * (depth * 4) + escape(entry["title"])
        for index, month in enumerate(months):
            rows.append(
                "<tr>"
                f"<td>{title if index == 0 else ''}</td><td>{escape(month)}</td>"
                f"<td>{_amount(entry['paid'][index])}</td>"
                f"<td>{_amount(entry['received'][index])}</td><td>{_amount(entry['net'][index])}</td>"
                "</tr>"
            )
    return "".join(rows) or '<tr><td colspan="5">None</td></tr>'


def render_mom(accounting: dict, period: str) -> str:
    """Render the normalized multi-month accounting contract."""
    reconciliation = accounting["reconciliation"]
    months = accounting["months"]
    styles = _load_shared_styles()
    reconciliation_rows = "".join(
        "<tr>"
        f"<td>{escape(month)}</td><td>{_amount(reconciliation['source'][index])}</td>"
        f"<td>{_amount(reconciliation['report'][index])}</td>"
        f"<td>{_amount(reconciliation['difference'][index])}</td></tr>"
        for index, month in enumerate(months)
    )
    return (
        f'<!doctype html><html><head><meta charset="utf-8"><title>MoM accounting report {escape(period)}</title><style>{styles}</style></head><body>'
        f'<header class="report-header"><p class="eyebrow">Household financial review</p><h1>Month-on-month accounting report</h1><p class="period">Period: {escape(period)}</p></header>'
        "<h2>Category accounting</h2><table><thead><tr><th>Category</th><th>Month</th><th>Paid</th><th>Received</th><th>Net</th></tr></thead><tbody>"
        f"{_mom_rows(accounting['categories'], months)}</tbody></table>"
        "<h2>Reconciliation</h2><table><thead><tr><th>Month</th><th>Source</th><th>Report</th><th>Difference</th></tr></thead><tbody>"
        f"{reconciliation_rows}</tbody></table></body></html>"
    )
