"""Build one registry-driven mega report in a single WeasyPrint pass."""

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import uuid
from datetime import datetime
from html import escape
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT / "src"))
V4_DIR = REPOSITORY_ROOT / "src" / "v4_pipeline"
if str(V4_DIR) not in sys.path:
    sys.path.insert(0, str(V4_DIR))
MOM_DIR = REPOSITORY_ROOT / "src" / "mom"
if str(MOM_DIR) not in sys.path:
    sys.path.insert(0, str(MOM_DIR))

try:
    from .registry import numbered_sections, section_by_id, valid_ids
except ImportError:
    from registry import numbered_sections, section_by_id, valid_ids

from accounting_html import render_mom
from accounting import (
    AccountingValidationError,
    load_category_parents,
    load_category_roles,
    load_category_titles,
    load_excluded_account_ids,
)
from build import build_month_html
from compare import aggregate_normalized_months
from input_contract import InputContractError, resolve_month_input
from sections import (
    section_appendices,
    section_cc_paydowns,
    section_common,
    section_excluded,
    section_home,
    section_income,
    section_personal,
    section_savings,
    section_trips,
)
from sections.css import get_css
from trips import cluster_by_label
from line_chart import render_line_chart
from stacked_bar_line import render_stacked_bar_with_line


class MegaValidationError(ValueError):
    """Raised before rendering when requested source data is incomplete."""


SAFE_OUTPUT_NAME = re.compile(r"[A-Za-z0-9_-]+\Z")
UTC_TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
RECOMMENDATION_SEVERITIES = {"high": 0, "medium": 1, "low": 2}


def _output_basename(value: str) -> str:
    if not SAFE_OUTPUT_NAME.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "must be an extensionless basename using letters, digits, _ or -"
        )
    return value


def inclusive_months(start: str, end: str) -> list[str]:
    try:
        first = datetime.strptime(start, "%Y-%m")
        last = datetime.strptime(end, "%Y-%m")
    except ValueError as error:
        raise MegaValidationError("--start and --end must use YYYY-MM") from error
    if first > last:
        raise MegaValidationError("--start must be before or equal to --end")
    months = []
    current = first
    while current <= last:
        months.append(current.strftime("%Y-%m"))
        current = datetime(
            current.year + (current.month == 12), current.month % 12 + 1, 1
        )
    return months


def month_data_path(month: str, data_dir: Path, input_kind: str) -> Path:
    """Resolve one month from the selected strict source contract."""
    try:
        return resolve_month_input(month, data_dir, input_kind)
    except InputContractError as error:
        raise MegaValidationError(str(error)) from error


def _transaction_description(transaction: dict) -> str:
    account = transaction.get("account") or transaction.get("transaction_account") or {}
    account_name = account.get("name", "") if isinstance(account, dict) else ""
    return (
        f"id={transaction.get('id')!r} date={transaction.get('date')!r} "
        f"amount={transaction.get('amount')!r} account={account_name!r}"
    )


def _transaction_account_id(transaction: dict) -> str:
    account = transaction.get("account")
    account_id = account.get("id") if isinstance(account, dict) else None
    if account_id not in (None, ""):
        return str(account_id)
    legacy_account = transaction.get("transaction_account")
    return str(legacy_account.get("id", "")) if isinstance(legacy_account, dict) else ""


def _load_transactions_source(data_path: Path) -> list[dict]:
    """Read source — accept bare list or {"transactions": [...]} dict.

    sync_runner writes bare list; mega CLI originally expected dict. Both
    are valid ps_raw shapes. Returns a flat list of transactions; callers
    see the bare-list shape regardless of the on-disk encoding.
    """
    raw = json.loads(data_path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict) and isinstance(raw.get("transactions"), list):
        return raw["transactions"]
    return []


def validate_categories(month: str, data_path: Path) -> None:
    try:
        source = json.loads(data_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MegaValidationError(
            f"Required month {month} is invalid: {data_path}"
        ) from error
    # Accept both bare list and {"transactions": [...]} dict shapes.
    if isinstance(source, dict):
        transactions = source.get("transactions")
    elif isinstance(source, list):
        transactions = source
    else:
        transactions = None
    if not isinstance(transactions, list):
        raise MegaValidationError(f"Required month {month} is invalid: {data_path}")
    offenders = []
    for index, transaction in enumerate(transactions):
        if not isinstance(transaction, dict):
            offenders.append(f"row={index} value={transaction!r}")
            continue
        if not str(transaction.get("date", "")).startswith(month):
            continue
        category = transaction.get("category")
        if (
            not isinstance(category, dict)
            or not category.get("id")
            or not category.get("title")
        ):
            offenders.append(_transaction_description(transaction))
    if offenders:
        raise MegaValidationError(
            f"Uncategorized or missing-category transactions for {month}: "
            + "; ".join(offenders)
        )


def build_context(args: argparse.Namespace) -> dict[str, object]:
    category_roles = (
        load_category_roles(args.category_role_map)
        if args.category_role_map is not None and args.category_catalog is not None
        else None
    )
    try:
        category_parents = (
            load_category_parents(args.category_catalog)
            if args.category_catalog is not None
            else None
        )
        category_titles = (
            load_category_titles(args.category_catalog)
            if args.category_catalog is not None
            else None
        )
    except AccountingValidationError as error:
        raise MegaValidationError(f"Category catalog is invalid: {error}") from error
    monthly_results = []
    raw_transactions = {}
    unified_excluded_account_ids = (
        load_excluded_account_ids() if args.input_kind == "live" else set()
    )
    for month in inclusive_months(args.start, args.end):
        path = month_data_path(month, args.data_dir, args.input_kind)
        validate_categories(month, path)
        included_transactions = [
            transaction
            for transaction in _load_transactions_source(path)
            if _transaction_account_id(transaction) not in unified_excluded_account_ids
        ]
        result = build_month_html(
            month,
            path,
            exclude_account_ids=args.exclude_account_id,
            category_role_map=args.category_role_map,
            account_owner_map=args.account_owner_map,
            detailed_section_map=args.detailed_section_map,
            partner_a_label=args.partner_a_label,
            partner_b_label=args.partner_b_label,
            partner_label_map=args.partner_label_map,
            theme=args.theme,
            unified_excluded_account_ids=unified_excluded_account_ids,
        )
        contract = result["contract"]
        detailed_section_mapping = contract.get("detailed_section_mapping", {})
        section_map = detailed_section_mapping.get("category_sections", {})
        normalized_by_id = {
            str(record["id"]): record
            for record in contract.get("normalized_transactions", [])
        }
        raw_transactions[month] = []
        for transaction in included_transactions:
            record = normalized_by_id.get(str(transaction.get("id")))
            if record is None:
                continue
            detailed_section = section_map.get(
                str(record["category_path"][-1]["id"]), "common"
            )
            raw_transactions[month].append(
                {**transaction, "_detailed_section": detailed_section}
            )
        monthly_results.append((month, result))
    try:
        accounting = aggregate_normalized_months(
            [
                {"month": month, "contract": result["contract"]}
                for month, result in monthly_results
            ]
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise MegaValidationError(f"Accounting data is invalid: {error}") from error
    detail_agg = _detail_agg(monthly_results, raw_transactions)
    return {
        "monthly_results": monthly_results,
        "accounting": accounting,
        "detail_agg": detail_agg,
        "appendix_transactions": _appendix_transactions(monthly_results),
        "salary_allocation": _salary_allocation(
            [
                record
                for _, result in monthly_results
                for record in result["contract"].get("normalized_transactions", [])
            ],
            category_roles,
            category_parents,
            detail_agg["cumulative"]["income"]["total"],
            _period_role_allocations(monthly_results),
            category_titles,
        ),
        "raw_transactions": raw_transactions,
        "recommendations": _load_requested_recommendations(args),
    }


def _appendix_transactions(monthly_results):
    section_routes = {
        "income_salary": "income",
        "income_third_party": "income",
        "savings": "savings",
        "home": "home",
        "common": "common",
        "personal_partner_a": "personal_partner_a",
        "personal_partner_b": "personal_partner_b",
        "trips": "trips",
    }
    transactions = {}
    for month, result in monthly_results:
        mapping = result["contract"].get("detailed_section_mapping", {})
        section_map = mapping.get("category_sections", {})
        rows = []
        for record in result["contract"].get("normalized_transactions", []):
            category_path = record["category_path"]
            leaf = category_path[-1]
            section = section_routes.get(section_map.get(str(leaf["id"])))
            if section is None:
                continue
            root = category_path[0]
            # First PS label = trip label (trips cluster by shared label).
            labels = record.get("labels") or []
            trip_label = labels[0].strip() if labels else None
            rows.append(
                {
                    "id": record.get("id"),
                    "date": record["date"],
                    "amount": record["amount"],
                    "payee": record["payee"],
                    "account": {"name": record["account_name"]},
                    "_detailed_section": section,
                    "_main_category": root,
                    "_subcategory": (None if root["id"] == leaf["id"] else leaf),
                    "_trip_label": trip_label if section == "trips" else None,
                }
            )
        transactions[month] = rows
    return transactions


def _load_requested_recommendations(
    args: argparse.Namespace,
) -> dict[str, object] | None:
    artifact_path = getattr(
        args,
        "recommendations_artifact",
        REPOSITORY_ROOT / "data" / "private" / "recommendations.json",
    )
    if args.only not in (None, "recommendations"):
        return None
    artifact = load_recommendations(artifact_path, args.start, args.end)
    if args.only == "recommendations" and artifact is None:
        raise MegaValidationError(
            f"Recommendations artifact is required for --only recommendations: {artifact_path}"
        )
    return artifact


def load_recommendations(path: Path, start: str, end: str) -> dict[str, object] | None:
    path = Path(path)
    if not path.is_file():
        return None
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MegaValidationError(
            f"Recommendations artifact is invalid: {path}"
        ) from error
    required = {"schema_version", "generated_at", "period", "recommendations"}
    if not isinstance(artifact, dict) or set(artifact) != required:
        raise MegaValidationError("Recommendations artifact has an invalid schema")
    period = artifact["period"]
    recommendations = artifact["recommendations"]
    if (
        artifact["schema_version"] != "1"
        or not isinstance(artifact["generated_at"], str)
        or not isinstance(period, dict)
        or set(period) != {"start", "end"}
        or not all(isinstance(period[key], str) for key in ("start", "end"))
        or not isinstance(recommendations, list)
    ):
        raise MegaValidationError("Recommendations artifact has an invalid schema")
    try:
        if not UTC_TIMESTAMP.fullmatch(artifact["generated_at"]):
            raise ValueError
        datetime.strptime(artifact["generated_at"], "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise MegaValidationError(
            "Recommendations artifact has an invalid generated_at"
        ) from error
    if period != {"start": start, "end": end}:
        raise MegaValidationError(
            f"Recommendations artifact period {period!r} does not match {start} to {end}"
        )
    validated = []
    for recommendation in recommendations:
        if (
            not isinstance(recommendation, dict)
            or set(recommendation) != {"id", "title", "body", "severity", "evidence"}
            or not all(
                isinstance(recommendation[key], str)
                for key in ("id", "title", "body", "severity")
            )
            or recommendation["severity"] not in RECOMMENDATION_SEVERITIES
            or not isinstance(recommendation["evidence"], list)
            or not all(isinstance(item, str) for item in recommendation["evidence"])
        ):
            raise MegaValidationError(
                "Recommendations artifact has an invalid recommendation"
            )
        validated.append(recommendation)
    artifact["recommendations"] = validated
    return artifact


def _detail_agg(monthly_results, raw_transactions):
    months = [month for month, _ in monthly_results]
    count = len(months)
    cats = {}
    excluded_transactions = {month: [] for month in months}
    cc_paydowns = {}
    trip_transactions = []
    for index, (month, result) in enumerate(monthly_results):
        contract = result["contract"]
        mapping = contract.get("detailed_section_mapping", {})
        section_map = mapping.get("category_sections", {})
        account_roles = mapping.get("account_roles", {})
        normalized_by_id = {
            str(record.get("id")): record
            for record in contract.get("normalized_transactions", [])
            if record.get("id") is not None
        }
        for record in contract.get("normalized_transactions", []):
            leaf = record["category_path"][-1]
            leaf_id = str(leaf["id"])
            section = section_map.get(leaf_id, "common")
            category = cats.setdefault(
                leaf_id,
                {
                    "title": leaf["title"],
                    "section": section,
                    "partner_a_paid": [0.0] * count,
                    "partner_b_paid": [0.0] * count,
                    "partner_a_received": [0.0] * count,
                    "partner_b_received": [0.0] * count,
                    "partner_a_net": [0.0] * count,
                    "partner_b_net": [0.0] * count,
                    "total": [0.0] * count,
                    "count": [0] * count,
                    "is_reimbursement": False,
                },
            )
            owner = record["owner"]
            amount = record["amount"]
            paid_key = f"{owner}_paid"
            received_key = f"{owner}_received"
            net_key = f"{owner}_net"
            if amount < 0:
                category[paid_key][index] += -amount
                category[net_key][index] += -amount
            else:
                category[received_key][index] += amount
                category[net_key][index] -= amount
            category["total"][index] += -amount
            category["count"][index] += 1
            if section == "excluded":
                excluded_transactions[month].append(
                    {
                        "date": record["date"],
                        "description": record["payee"] or record["note"],
                        "category": leaf["title"],
                        "owner": owner,
                        "amount": amount,
                    }
                )
            if (
                section == "cc_payments"
                and amount > 0
                and account_roles.get(record["account_id"]) == "credit_card"
            ):
                card = record["account_name"]
                cc_paydowns.setdefault(card, {})[month] = (
                    cc_paydowns.setdefault(card, {}).get(month, 0.0) + amount
                )
        for transaction in raw_transactions.get(month, []):
            raw_category_id = str((transaction.get("category") or {}).get("id"))
            if section_map.get(raw_category_id) != "trips":
                continue
            record = normalized_by_id.get(str(transaction.get("id")))
            if record is None:
                raise MegaValidationError(
                    f"Trip transaction has no normalized owner: {transaction.get('id')!r}"
                )
            trip_transactions.append({**transaction, "owner": record["owner"]})

    def section_series(section):
        result = {
            "partner_a": [0.0] * count,
            "partner_b": [0.0] * count,
            "total": [0.0] * count,
        }
        for category in cats.values():
            if category["section"] != section:
                continue
            for index in range(count):
                result["partner_a"][index] += category["partner_a_net"][index]
                result["partner_b"][index] += category["partner_b_net"][index]
                result["total"][index] += category["total"][index]
        return result

    def income_series():
        result = {
            "partner_a": [0.0] * count,
            "partner_b": [0.0] * count,
            "total": [0.0] * count,
        }
        for category in cats.values():
            if category["section"] not in {"income_salary", "income_third_party"}:
                continue
            for index in range(count):
                for owner in ("partner_a", "partner_b"):
                    result[owner][index] += category[f"{owner}_received"][index]
                result["total"][index] += (
                    category["partner_a_received"][index]
                    + category["partner_b_received"][index]
                )
        return result

    income = income_series()
    savings = section_series("savings")
    savings_series = {
        "net_partner_a": savings["partner_a"],
        "net_partner_b": savings["partner_b"],
        "total": savings["total"],
        "investment_net_partner_a": [0.0] * count,
        "investment_net_partner_b": [0.0] * count,
        "investment_net_total": [0.0] * count,
    }
    personal_a = section_series("personal_partner_a")
    personal_b = section_series("personal_partner_b")
    real_spend = {
        "partner_a": [0.0] * count,
        "partner_b": [0.0] * count,
        "total": [0.0] * count,
    }
    net_cash = {"partner_a": [], "partner_b": [], "total": []}
    for section in ("home", "common", "personal_partner_a", "personal_partner_b", "trips"):
        values = section_series(section)
        for index in range(count):
            real_spend["partner_a"][index] += values["partner_a"][index]
            real_spend["partner_b"][index] += values["partner_b"][index]
            real_spend["total"][index] += values["total"][index]
    for index, (_, result) in enumerate(monthly_results):
        kpis = result["contract"].get("kpis", {})
        has_role_kpis = all(
            isinstance(kpis.get(owner, {}).get("net_cash"), (int, float))
            for owner in ("partner_a", "partner_b", "total")
        )
        for owner in ("partner_a", "partner_b", "total"):
            net_cash[owner].append(
                float(kpis[owner]["net_cash"])
                if has_role_kpis
                else income[owner][index] - real_spend[owner][index]
            )
        has_savings_kpis = all(
            isinstance(kpis.get(owner, {}).get("net_savings"), (int, float))
            and isinstance(kpis.get(owner, {}).get("investment"), (int, float))
            for owner in ("partner_a", "partner_b", "total")
        )
        if has_savings_kpis:
            savings_series["net_partner_a"][index] = float(
                kpis["partner_a"]["net_savings"]
            )
            savings_series["net_partner_b"][index] = float(
                kpis["partner_b"]["net_savings"]
            )
            savings_series["total"][index] = float(kpis["total"]["net_savings"])
            savings_series["investment_net_partner_a"][index] = float(
                kpis["partner_a"]["investment"]
            )
            savings_series["investment_net_partner_b"][index] = float(
                kpis["partner_b"]["investment"]
            )
            savings_series["investment_net_total"][index] = float(
                kpis["total"]["investment"]
            )
    return {
        "months": months,
        "cats": cats,
        "paired_reimbs": [],
        "cc_paydowns": cc_paydowns,
        "excluded_transactions": excluded_transactions,
        "trips": cluster_by_label(trip_transactions),
        "series": {
            "income": income,
            "savings": savings_series,
            "real_spend": real_spend,
            "net_cash": net_cash,
        },
        "cumulative": {
            "income": {key: sum(values) for key, values in income.items()},
            "savings": {
                "net_partner_a": sum(savings_series["net_partner_a"]),
                "net_partner_b": sum(savings_series["net_partner_b"]),
                "total": sum(savings_series["total"]),
                "investment_net_partner_a": sum(
                    savings_series["investment_net_partner_a"]
                ),
                "investment_net_partner_b": sum(
                    savings_series["investment_net_partner_b"]
                ),
                "investment_net_total": sum(savings_series["investment_net_total"]),
            },
            "real_spend": {key: sum(values) for key, values in real_spend.items()},
            "net_cash": {key: sum(values) for key, values in net_cash.items()},
        },
    }


def _placeholder(number: int, title: str) -> str:
    return f'<section class="mega-section"><h2>{number}. {escape(title)}</h2><p>Section foundation ready for a later slice.</p></section>'


def _render_detail_section(identifier, number, title, agg, partner_labels):
    renderer = {
        "income": section_income.render,
        "savings": section_savings.render,
        "home": section_home.render,
        "common": section_common.render,
        "personal_partner_a": section_personal.render,
        "personal_partner_b": section_personal.render,
        "trips": section_trips.render,
        "cc_paydowns": section_cc_paydowns.render,
        "excluded": section_excluded.render,
    }.get(identifier)
    if renderer is None:
        return None
    if identifier in {"personal_partner_a", "personal_partner_b"}:
        return renderer(agg, identifier, partner_labels, number, title)
    return renderer(agg, partner_labels, number, title)


def _running_total(values):
    total = 0.0
    result = []
    for value in values:
        total += value
        result.append(total)
    return result


def _effective_category_role(category_id, category_roles, category_parents):
    """Return nearest explicit role; child mappings override parent mappings."""
    current_id = str(category_id)
    visited = set()
    while current_id not in visited:
        visited.add(current_id)
        role = category_roles.get(current_id)
        if role is not None:
            return role
        parent_id = category_parents.get(current_id)
        if parent_id is None:
            return None
        current_id = parent_id
    raise MegaValidationError("Category catalog hierarchy has a cycle")


def _main_category_spend(
    records, category_roles, category_parents, category_titles=None
):
    """Aggregate signed real spend by catalog root; omit non-positive nets."""
    if category_roles is None or category_parents is None:
        return []
    if not isinstance(category_titles, dict):
        raise MegaValidationError(
            "Category catalog title metadata is required for salary allocations"
        )
    totals = {}
    for record in records:
        category_path = record.get("category_path", [])
        if not category_path:
            continue
        leaf = category_path[-1]
        leaf_id = str(leaf["id"])
        if _effective_category_role(leaf_id, category_roles, category_parents) not in {
            "spend",
            "personal_spend",
        }:
            continue
        amount = float(record["amount"])
        root_id = leaf_id
        root_seen = set()
        while True:
            if root_id in root_seen:
                raise MegaValidationError("Category catalog hierarchy has a cycle")
            root_seen.add(root_id)
            if root_id not in category_parents:
                raise MegaValidationError(
                    f"Category catalog has no category ID {root_id!r}"
                )
            parent_id = category_parents[root_id]
            if parent_id is None:
                break
            root_id = parent_id
        root_title = category_titles.get(root_id)
        if (
            not isinstance(root_title, str)
            or not root_title.strip()
            or root_title.strip().isdigit()
        ):
            raise MegaValidationError(
                f"Category catalog has an invalid display title for category ID {root_id!r}"
            )
        entry = totals.setdefault(
            root_id,
            {"id": root_id, "title": root_title, "amount": 0.0},
        )
        entry["amount"] += -amount
    return sorted(
        (entry for entry in totals.values() if entry["amount"] > 0),
        key=lambda entry: (entry["title"], entry["id"]),
    )


def _period_role_allocations(monthly_results):
    """Return savings roles only when every month supplies the v4 KPI contract."""
    totals = {"net_savings": 0.0, "investment": 0.0}
    for _, result in monthly_results:
        values = result["contract"].get("kpis", {}).get("total", {})
        if not all(isinstance(values.get(key), (int, float)) for key in totals):
            return None
        for key in totals:
            totals[key] += float(values[key])
    return totals


def _salary_allocation(
    records,
    category_roles,
    category_parents,
    income,
    role_allocations,
    category_titles=None,
):
    """Build period costs plus role-KPI savings allocations from stable IDs."""
    if category_roles is None or category_parents is None:
        return {
            "income": float(income),
            "entries": [],
            "unavailable_reason": (
                "category role map and category catalog are required."
            ),
        }
    if role_allocations is None:
        return {
            "income": float(income),
            "entries": [],
            "unavailable_reason": (
                "complete net savings and investment KPIs are required for every month."
            ),
        }
    entries = _main_category_spend(
        records, category_roles, category_parents, category_titles
    )
    for key, title in (
        ("net_savings", "Net savings"),
        ("investment", "Investment net"),
    ):
        amount = role_allocations[key]
        if amount:
            entries.append({"id": f"role-{key}", "title": title, "amount": amount})
    return {"income": float(income), "entries": entries}


def _salary_allocation_title(value):
    if not isinstance(value, str) or not value.strip() or value.strip().isdigit():
        raise MegaValidationError(
            "Salary allocation entry title must be a non-numeric, non-empty string"
        )
    return value


def _render_salary_allocation(salary_allocation):
    income = salary_allocation["income"]
    unavailable_reason = salary_allocation.get("unavailable_reason")
    if unavailable_reason is not None:
        return (
            '<section class="mega-salary-allocation"><h3>Salary allocation</h3>'
            f"<p>Unavailable: {escape(unavailable_reason)}</p></section>"
        )
    if income <= 0:
        return (
            '<section class="mega-salary-allocation"><h3>Salary allocation</h3>'
            "<p>Unavailable: total period income is zero or negative.</p></section>"
        )
    entries = salary_allocation["entries"]
    rows = "".join(
        "<tr>"
        f"<th scope=\"row\">{escape(_salary_allocation_title(entry.get('title')))}</th>"
        f"<td>{entry['amount']:,.2f} NOK</td>"
        f"<td>{entry['amount'] / income * 100:,.1f}%</td>"
        "</tr>"
        for entry in entries
    )
    allocated = sum(entry["amount"] for entry in entries)
    remaining = income - allocated
    remaining_label = (
        "Remaining income after listed allocations"
        if remaining >= 0
        else "Listed allocations exceed income"
    )
    return (
        '<section class="mega-salary-allocation"><h3>Salary allocation</h3>'
        f"<p>Total period income: {income:,.2f} NOK</p>"
        '<table><thead><tr><th scope="col">Allocation</th><th scope="col">Amount</th>'
        '<th scope="col">Percent of income</th></tr></thead><tbody>'
        f"{rows}"
        f'<tr><th scope="row">Listed allocations</th><td>{allocated:,.2f} NOK</td>'
        f"<td>{allocated / income * 100:,.1f}%</td></tr>"
        f'<tr><th scope="row">{remaining_label}</th><td>{abs(remaining):,.2f} NOK</td>'
        f"<td>{abs(remaining) / income * 100:,.1f}%</td></tr>"
        "</tbody></table></section>"
    )


def _render_kpi_cover(
    number, title, agg, partner_labels, period, salary_allocation=None
):
    cumulative = agg["cumulative"]
    cards = (
        ("Total income", cumulative["income"]["total"]),
        ("Real spend", cumulative["real_spend"]["total"]),
        ("Net cash", cumulative["net_cash"]["total"]),
        ("Net savings", cumulative["savings"]["total"]),
        (
            f"{partner_labels.get('partner_a', 'Partner A')} income",
            cumulative["income"]["partner_a"],
        ),
        (
            f"{partner_labels.get('partner_b', 'Partner B')} income",
            cumulative["income"]["partner_b"],
        ),
    )
    card_html = "".join(
        f'<article class="mega-kpi-card"><span>{escape(label)}</span><strong>{value:,.2f} NOK</strong></article>'
        for label, value in cards
    )
    months = agg["months"]
    series = agg["series"]
    charts = (
        render_stacked_bar_with_line(
            months,
            series["income"]["partner_a"],
            series["income"]["partner_b"],
            _running_total(series["income"]["total"]),
            title="Income",
            show_value_labels=False,
            partner_a_label=partner_labels.get("partner_a", "Partner A"),
            partner_b_label=partner_labels.get("partner_b", "Partner B"),
        ),
        render_line_chart(
            months,
            {"Real spend": series["real_spend"]["total"]},
            "Real spend",
            show_value_labels=False,
        ),
        render_line_chart(
            months,
            {"Net cash": series["net_cash"]["total"]},
            "Net cash",
            show_value_labels=False,
        ),
        render_line_chart(
            months,
            {"Net savings cumulative": _running_total(series["savings"]["total"])},
            "Savings",
            show_value_labels=False,
        ),
    )
    # Charts go in the 3-col grid (chart 1: stacked bar + line; charts 2-4: 3 line charts).
    salary_allocation_html = _render_salary_allocation(
        salary_allocation or {"income": 0.0, "entries": []}
    )
    return (
        f'<section class="mega-section mega-kpi-cover"><h2>{number}. {escape(title)}</h2>'
        f'<h1>Household Report</h1><p class="mega-period">{escape(period)}</p><div class="mega-kpi-grid">{card_html}</div></section>'
        f'<section class="mega-kpi-charts mega-kpi-charts-3col">{"".join(f"<div>{chart}</div>" for chart in charts)}</section>'
        f'<section class="mega-salary-allocation-wrap">{salary_allocation_html}</section>'
    )


def _monthly_kpi_values(result, agg, index):
    kpis = result["contract"].get("kpis")
    required = ("income", "real_spend", "net_cash", "net_savings")
    owners = ("partner_a", "partner_b", "total")
    has_role_kpis = isinstance(kpis, dict) and not any(
        not isinstance(kpis.get(owner), dict)
        or any(
            not isinstance(kpis[owner].get(metric), (int, float)) for metric in required
        )
        for owner in owners
    )
    if not has_role_kpis:
        savings = agg["series"]["savings"]
        kpis = {
            "partner_a": {
                "income": agg["series"]["income"]["partner_a"][index],
                "real_spend": agg["series"]["real_spend"]["partner_a"][index],
                "net_cash": agg["series"]["net_cash"]["partner_a"][index],
                "net_savings": savings["net_partner_a"][index],
            },
            "partner_b": {
                "income": agg["series"]["income"]["partner_b"][index],
                "real_spend": agg["series"]["real_spend"]["partner_b"][index],
                "net_cash": agg["series"]["net_cash"]["partner_b"][index],
                "net_savings": savings["net_partner_b"][index],
            },
            "total": {
                "income": agg["series"]["income"]["total"][index],
                "real_spend": agg["series"]["real_spend"]["total"][index],
                "net_cash": agg["series"]["net_cash"]["total"][index],
                "net_savings": savings["total"][index],
            },
        }
    metrics = [
        ("Income", "income"),
        ("Real spend", "real_spend"),
        ("Net cash", "net_cash"),
        ("Net savings", "net_savings"),
    ]
    if all(isinstance(kpis[owner].get("investment"), (int, float)) for owner in owners):
        metrics.append(("Investment net", "investment"))
    return [(label, key, kpis) for label, key in metrics]


def _render_monthly_kpi_page(month, result, agg, index, number, title):
    partner_labels = result["partner_labels"]
    cards = []
    for label, key, kpis in _monthly_kpi_values(result, agg, index):
        for owner, owner_label in (
            ("partner_a", partner_labels["partner_a"]),
            ("partner_b", partner_labels["partner_b"]),
            ("total", "Household"),
        ):
            cards.append(
                '<article class="mega-monthly-kpi-card">'
                f"<span>{escape(label)} - {escape(owner_label)}</span>"
                f"<strong>{kpis[owner][key]:,.2f} NOK</strong>"
                "</article>"
            )
    return (
        f'<section class="mega-monthly-kpi-page" data-month="{escape(month)}">'
        f"<h2>{number}. {escape(title)}: {escape(month)}</h2>"
        f'<div class="mega-monthly-kpi-grid">{"".join(cards)}</div></section>'
    )


def _render_recommendations(number, title, artifact):
    ordered = sorted(
        enumerate(artifact["recommendations"]),
        key=lambda item: RECOMMENDATION_SEVERITIES[item[1]["severity"]],
    )
    entries = []
    for _, recommendation in ordered:
        evidence = "".join(
            f"<li>{escape(item)}</li>" for item in recommendation["evidence"]
        )
        entries.append(
            '<article class="mega-recommendation">'
            f'<span class="severity severity-{escape(recommendation["severity"])}">{escape(recommendation["severity"])}</span>'
            f'<h3>{escape(recommendation["title"])}</h3><p>{escape(recommendation["body"])}</p><ul>{evidence}</ul></article>'
        )
    return f'<section class="mega-section"><h2>{number}. {escape(title)}</h2><p class="mega-agent-note">Agent-generated {escape(artifact["generated_at"])} - not from pipeline math.</p>{"".join(entries)}</section>'


def _scope_monthly_css(css: str) -> str:
    def scope_selector(selector: str) -> str:
        selector = selector.strip()
        if selector in {"html", "body", ":root"}:
            return ".mega-monthly"
        for root in ("html", "body", ":root"):
            if selector.startswith(root + ".") or selector.startswith(root + ":"):
                return ".mega-monthly" + selector[len(root) :]
            if selector.startswith(root + " "):
                return ".mega-monthly " + selector[len(root) :].lstrip()
        return f".mega-monthly {selector}"

    def scope_blocks(source: str) -> str:
        result = []
        position = 0
        while position < len(source):
            opening = source.find("{", position)
            if opening == -1:
                result.append(source[position:])
                break
            selector = source[position:opening].strip()
            depth = 1
            closing = opening + 1
            while closing < len(source) and depth:
                depth += (source[closing] == "{") - (source[closing] == "}")
                closing += 1
            if depth:
                raise MegaValidationError("Monthly CSS has an unclosed block")
            content = source[opening + 1 : closing - 1]
            if selector.startswith("@page"):
                pass
            elif selector.startswith("@keyframes"):
                result.append(f"{selector} {{{content}}}")
            elif selector.startswith("@"):
                result.append(f"{selector} {{{scope_blocks(content)}}}")
            else:
                scoped = ", ".join(scope_selector(item) for item in selector.split(","))
                result.append(f"{scoped} {{{content}}}")
            position = closing
        return "".join(result)

    return scope_blocks(css)


@contextmanager
def _publisher_lock(output_dir: Path, output_name: str, timeout_seconds: float = 30.0):
    lock_name = hashlib.sha256(output_name.encode("ascii")).hexdigest() + ".lock"
    lock_dir = output_dir / ".mega-locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / lock_name
    deadline = time.monotonic() + timeout_seconds

    with lock_path.open("a+b") as lock_file:
        if lock_file.tell() == 0:
            lock_file.write(b"\0")
            lock_file.flush()
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        f"Timed out waiting {timeout_seconds:g}s for publisher lock "
                        f"for '{output_name}'"
                    )
                time.sleep(0.05)
        try:
            yield
        finally:
            if os.name == "nt":
                import msvcrt

                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def assemble_html(context: dict[str, object], args: argparse.Namespace) -> str:
    monthly_results = context["monthly_results"]
    first_result = monthly_results[0][1]
    recommendations = context["recommendations"]
    active = numbered_sections(include_recommendations=recommendations is not None)
    selected = [
        item for item in active if args.only is None or item[1].identifier == args.only
    ]
    partner_labels = first_result["partner_labels"]
    titles = {
        "personal_partner_a": f"Personal spending - {partner_labels.get('partner_a', 'Partner A')}",
        "personal_partner_b": f"Personal spending - {partner_labels.get('partner_b', 'Partner B')}",
    }
    period = f"{args.start} to {args.end} ({len(monthly_results)} months)"
    mom_html = render_mom(context["accounting"], period)
    css_start = mom_html.index("<style>") + len("<style>")
    css_end = mom_html.index("</style>", css_start)
    appendix_css = mom_html[css_start:css_end]
    parts = [
        '<!doctype html><html><head><meta charset="utf-8"><title>Mega financial report</title><style>',
        appendix_css,
        get_css(),
        ".mega-section { break-before: page; page-break-before: always; } .mega-section:first-child { break-before: auto; page-break-before: auto; } .mega-section h2 { margin-top: 0; } .mega-kpi-cover { break-before: auto; page-break-before: auto; } .mega-period { text-align: center; } .mega-kpi-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; } .mega-kpi-card { border: 1px solid #d8e3ec; padding: 12px; } .mega-kpi-card strong { display: block; font-size: 16pt; } .mega-kpi-charts { break-before: page; page-break-before: always; display: grid; grid-template-columns: 1fr 1fr; gap: 14px; } .mega-kpi-charts-3col { grid-template-columns: 1fr 1fr 1fr; } .mega-kpi-charts-3col > div { min-width: 0; } .mega-monthly-kpi-page { break-before: page; page-break-before: always; } .mega-monthly-kpi-page h2 { margin-top: 0; } .mega-monthly-kpi-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; } .mega-monthly-kpi-card { border: 1px solid #d8e3ec; break-inside: avoid; page-break-inside: avoid; padding: 10px; } .mega-monthly-kpi-card span, .mega-monthly-kpi-card strong { display: block; } .mega-monthly-kpi-card strong { font-size: 15pt; margin: 4px 0; } .severity { font-weight: bold; text-transform: uppercase; } .severity-high { color: #a00; } .severity-medium { color: #a60; } .severity-low { color: #067; }",
        "</style></head>",
        f'<body class="{escape(str(first_result["body_class"]))}">',
    ]
    for number, section in selected:
        title = titles.get(section.identifier, section.title)
        if section.identifier == "kpi_cover":
            rendered = _render_kpi_cover(
                number,
                title,
                context["detail_agg"],
                partner_labels,
                period,
                context["salary_allocation"],
            )
        elif section.identifier == "recommendations":
            rendered = _render_recommendations(number, title, recommendations)
        elif section.identifier == "monthlies":
            rendered = []
            for index, (month, result) in enumerate(monthly_results):
                rendered.append(
                    _render_monthly_kpi_page(
                        month, result, context["detail_agg"], index, number, title
                    )
                )
            parts.extend(rendered)
            continue
        elif section.identifier == "appendices":
            rendered = section_appendices.render(
                context["detail_agg"],
                context["appendix_transactions"],
                partner_labels,
                number,
                title,
            )
        elif section.identifier == "excluded":
            rendered = section_excluded.render(
                context["detail_agg"],
                partner_labels,
                number,
                title,
            )
        else:
            detail_html = _render_detail_section(
                section.identifier, number, title, context["detail_agg"], partner_labels
            )
            rendered = detail_html or _placeholder(number, title)
        if rendered.startswith('<section class="mega-section'):
            parts.append(rendered)
        else:
            parts.append(f'<section class="mega-section">{rendered}</section>')
    return "".join(parts) + "</body></html>"


def _publish(html: str, output_dir: Path, name: str) -> tuple[Path, Path]:
    name = _output_basename(name)
    output_dir.mkdir(parents=True, exist_ok=True)
    with _publisher_lock(output_dir, name):
        return _publish_locked(html, output_dir, name)


def _publish_locked(html: str, output_dir: Path, name: str) -> tuple[Path, Path]:
    import weasyprint

    name = _output_basename(name)
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / f"{name}.html"
    pdf_path = output_dir / f"{name}.pdf"
    with tempfile.TemporaryDirectory(prefix=".mega-stage-", dir=output_dir) as stage:
        stage_dir = Path(stage)
        stage_html = stage_dir / html_path.name
        stage_pdf = stage_dir / pdf_path.name
        stage_html.write_text(html, encoding="utf-8")
        weasyprint.HTML(filename=str(stage_html)).write_pdf(str(stage_pdf))
        if (
            not stage_pdf.is_file()
            or stage_pdf.stat().st_size == 0
            or not stage_pdf.read_bytes().startswith(b"%PDF-")
        ):
            raise RuntimeError("WeasyPrint did not create a valid PDF")

        backup_dir = output_dir / f".mega-recovery-{uuid.uuid4().hex}"
        backup_dir.mkdir()
        backup_html = backup_dir / html_path.name
        backup_pdf = backup_dir / pdf_path.name
        html_backed_up = pdf_backed_up = html_published = pdf_published = False
        try:
            if html_path.exists():
                os.replace(html_path, backup_html)
                html_backed_up = True
            if pdf_path.exists():
                os.replace(pdf_path, backup_pdf)
                pdf_backed_up = True
            os.replace(stage_html, html_path)
            html_published = True
            os.replace(stage_pdf, pdf_path)
            pdf_published = True
        except OSError as publish_error:
            rollback_errors = []
            if html_published:
                try:
                    html_path.unlink(missing_ok=True)
                except OSError as rollback_error:
                    rollback_errors.append(rollback_error)
            if pdf_published:
                try:
                    pdf_path.unlink(missing_ok=True)
                except OSError as rollback_error:
                    rollback_errors.append(rollback_error)
            if html_backed_up:
                try:
                    os.replace(backup_html, html_path)
                except OSError as rollback_error:
                    rollback_errors.append(rollback_error)
            if pdf_backed_up:
                try:
                    os.replace(backup_pdf, pdf_path)
                except OSError as rollback_error:
                    rollback_errors.append(rollback_error)
            if rollback_errors:
                raise RuntimeError(
                    "Publish failed and rollback failed; prior report artifacts retained at "
                    f"{backup_dir}"
                ) from publish_error
            shutil.rmtree(backup_dir, ignore_errors=True)
            raise
        shutil.rmtree(backup_dir, ignore_errors=True)
    return html_path, pdf_path


def _output_name(args: argparse.Namespace) -> str:
    if args.only:
        return f"{args.name}_{args.only}"
    reserved_suffixes = tuple(f"_{identifier}" for identifier in valid_ids(True))
    if args.name.endswith(reserved_suffixes):
        raise MegaValidationError(
            "--name ending in a section ID is reserved for --only output names"
        )
    return args.name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--input-kind", choices=("live", "synthetic"), required=True)
    parser.add_argument("--output-dir", type=Path, default=REPOSITORY_ROOT / "out")
    parser.add_argument("--name", type=_output_basename, default="mega_report")
    parser.add_argument("--only")
    parser.add_argument("--theme", choices=("minimal",), default="minimal")
    parser.add_argument("--exclude-account-id", action="append", default=[])
    parser.add_argument("--category-role-map")
    parser.add_argument("--account-owner-map")
    parser.add_argument("--detailed-section-map", default=None)
    parser.add_argument("--category-catalog", default=None)
    parser.add_argument("--partner-a-label")
    parser.add_argument("--partner-b-label")
    parser.add_argument("--partner-label-map")
    parser.add_argument(
        "--savings-account-id", action="append", default=None, help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--recommendations-artifact",
        type=Path,
        default=REPOSITORY_ROOT / "data" / "private" / "recommendations.json",
    )
    args = parser.parse_args(argv)
    if args.savings_account_id:
        parser.error(
            "--savings-account-id is no longer supported; net savings is "
            "derived from transactions on accounts mapped to savings roles in "
            "--detailed-section-map"
        )
    if args.detailed_section_map is None:
        from accounting import PRIVATE_DETAILED_SECTION_MAP

        args.detailed_section_map = PRIVATE_DETAILED_SECTION_MAP
    if args.category_catalog is None and args.input_kind == "live":
        from accounting import PRIVATE_CATEGORY_CATALOG

        args.category_catalog = PRIVATE_CATEGORY_CATALOG
    if args.only and args.only not in valid_ids(include_recommendations=True):
        parser.exit(
            1,
            f"{parser.prog}: error: Unknown section ID {args.only!r}. "
            f"Valid IDs: {', '.join(valid_ids(include_recommendations=True))}\n",
        )
    try:
        context = build_context(args)
        html = assemble_html(context, args)
    except (MegaValidationError, OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"{parser.prog}: error: {error}\n")
    try:
        output_name = _output_name(args)
        html_path, pdf_path = _publish(html, args.output_dir, output_name)
    except Exception as error:
        parser.exit(1, f"{parser.prog}: error: {error}\n")
    print(f"HTML: {html_path}")
    print(f"PDF: {pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
