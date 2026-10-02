"""Mega report builder — wraps build_context() + ports derived views to JSON.

Constructs argparse.Namespace from data/private/ config, calls
mega.build_mega.build_context(), serializes detail_agg + salary_allocation +
recommendations + monthly_kpi_pages to JSON. Writes report + status.
"""

from __future__ import annotations

import argparse
import logging
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# mega lives in src/mega — add src/ to sys.path for `import build_mega`.
# storage.py parents[3] = repo root; same depth here (services→budget_api→src→repo).
_SRC_DIR = Path(__file__).resolve().parents[2]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from mega.build_mega import (  # noqa: E402 — sys.path injected above
    build_context,
    inclusive_months,
    MegaValidationError,
)

from budget_api.services import storage

_logger = logging.getLogger(__name__)
from budget_api.services.report_builder import (
    CONTRACT_VERSION,
    IncompatibleContractError,
    _load_account_owners,
    _load_partner_labels,
    _resolve_split_settlement,
)

# report_builder put v4_pipeline on sys.path above.
from accounting import (  # noqa: E402
    AccountingValidationError,
    DEFAULT_PARTNER_LABELS,
    _resolve_allowed_category_ids,
    compute_split,
    load_category_parents,
    load_detailed_section_mapping,
    load_split_config,
    net_category_totals,
)

# PR1: mega parity marker; 1→2: common-economy split — split_summary
# (aggregated per-month via accounting.net_category_totals(), additive;
# iteration 4 finding 1: was detail_agg["cats"], switched to fix
# transfer double-counting — see _split_category_nets).
# 2→3: two-sided split columns — split_summary rows share SplitCategoryRow
# with the monthly build, so they gain the same derived `section` + b-side
# actual_b/fair_b/delta_b. Same under-populated stored-payload risk as
# monthly 9→10 (pre-v3 rows validate with None defaults → em-dash), so bumped
# in lockstep.
MEGA_CALCULATION_VERSION = 3

_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
_MEGA_REPORT_FILE_RE = re.compile(r"^(\d{4}-\d{2})_(\d{4}-\d{2})_mega_report\.json$")


def _now_iso() -> str:
    """UTC ISO timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _build_namespace(
    start: str, end: str, partner_labels: dict[str, str] | None = None
) -> argparse.Namespace:
    """Construct argparse.Namespace build_context expects.

    Bridges budget_api account_mappings partner_id schema → mega expected
    account_owner_map path format ({account_id: "partner_a"|"partner_b"}).
    Writes bridged owners dict to temp JSON, passes temp path, cleans up.
    partner_labels: pass pre-loaded labels to skip a second file load
    (build_mega_report loads once and logs the warnings); None loads here.
    """
    private = storage.PRIVATE_DATA_DIR

    # account_owner_map — build_month_html→load_account_owners(path) expects
    # JSON dict {account_id: "partner_a"|"partner_b"}. Bridge from account_mappings.
    owners = _load_account_owners()
    tmp_path: str | None = None
    account_owner_map: str | None = None
    if owners:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", suffix=".json", delete=False
        ) as tmp:
            json.dump(owners, tmp)
            tmp_path = tmp.name
        account_owner_map = tmp_path

    # partner_label_map — bridge via _load_partner_labels so the
    # account_mappings partners fallback (custom IDs) resolves too. Only real
    # labels get a temp map; placeholder defaults keep None (mega build's own
    # placeholder fallback path).
    labels = partner_labels if partner_labels is not None else _load_partner_labels()[0]
    label_tmp_path: str | None = None
    partner_label_map: str | None = None
    if labels != DEFAULT_PARTNER_LABELS:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", suffix=".json", delete=False
        ) as tmp:
            json.dump(labels, tmp)
            label_tmp_path = tmp.name
        partner_label_map = label_tmp_path

    # category_role_map — optional.
    category_role_map = None
    roles_path = private / "category_roles.json"
    if roles_path.exists():
        category_role_map = str(roles_path)

    # category_catalog — optional but needed for role resolution.
    category_catalog = None
    catalog_path = private / "category_catalog.json"
    if catalog_path.exists():
        category_catalog = str(catalog_path)

    # recommendations_artifact — optional.
    recommendations_artifact = private / "recommendations.json"

    args = argparse.Namespace(
        start=start,
        end=end,
        data_dir=private,
        input_kind="live",
        category_role_map=category_role_map,
        account_owner_map=account_owner_map,
        detailed_section_map=str(storage.DETAILED_SECTION_MAPPING_PATH),
        category_catalog=category_catalog,
        partner_a_label=None,
        partner_b_label=None,
        partner_label_map=partner_label_map,
        theme="minimal",
        exclude_account_id=[],
        only=None,
        recommendations_artifact=recommendations_artifact,
        savings_account_id=None,
        name="mega_report",
        output_dir=storage.REPOSITORY_ROOT / "out",
    )
    # Stash tmp paths for cleanup by caller via _cleanup_namespace.
    args._owner_map_tmp = tmp_path
    args._label_map_tmp = label_tmp_path
    return args


def _cleanup_namespace(args: argparse.Namespace) -> None:
    """Remove temp account_owner_map/partner_label_map files if created."""
    for attr in ("_owner_map_tmp", "_label_map_tmp"):
        tmp_path = getattr(args, attr, None)
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


def _monthly_kpi_pages(
    monthly_results: list[tuple[str, dict[str, Any]]],
    detail_agg: dict[str, Any],
) -> list[dict[str, Any]]:
    """Port _monthly_kpi_values logic → JSON shape from design doc L4.

    For each month+index: check contract kpis for required fields, else fall
    back to agg series. Extract income/real_spend/net_cash/net_savings/investment
    per partner.
    """
    pages: list[dict[str, Any]] = []
    owners = ("partner_a", "partner_b", "total")
    required = ("income", "real_spend", "net_cash", "net_savings")
    series = detail_agg["series"]
    savings = series["savings"]
    for index, (month, result) in enumerate(monthly_results):
        kpis = result["contract"].get("kpis")
        has_role_kpis = isinstance(kpis, dict) and not any(
            not isinstance(kpis.get(owner), dict)
            or any(
                not isinstance(kpis[owner].get(metric), (int, float))
                for metric in required
            )
            for owner in owners
        )
        if not has_role_kpis:
            kpis = {
                "partner_a": {
                    "income": series["income"]["partner_a"][index],
                    "real_spend": series["real_spend"]["partner_a"][index],
                    "net_cash": series["net_cash"]["partner_a"][index],
                    "net_savings": savings["net_partner_a"][index],
                },
                "partner_b": {
                    "income": series["income"]["partner_b"][index],
                    "real_spend": series["real_spend"]["partner_b"][index],
                    "net_cash": series["net_cash"]["partner_b"][index],
                    "net_savings": savings["net_partner_b"][index],
                },
                "total": {
                    "income": series["income"]["total"][index],
                    "real_spend": series["real_spend"]["total"][index],
                    "net_cash": series["net_cash"]["total"][index],
                    "net_savings": savings["total"][index],
                },
            }
        # investment — optional, only if all owners have it.
        has_investment = all(
            isinstance(kpis[owner].get("investment"), (int, float)) for owner in owners
        )
        page_kpis: dict[str, dict[str, float]] = {}
        for owner in owners:
            entry = {
                "income": float(kpis[owner]["income"]),
                "real_spend": float(kpis[owner]["real_spend"]),
                "net_cash": float(kpis[owner]["net_cash"]),
                "net_savings": float(kpis[owner]["net_savings"]),
            }
            if has_investment:
                entry["investment"] = float(kpis[owner]["investment"])
            page_kpis[owner] = entry
        pages.append({"month": month, "kpis": page_kpis})
    return pages


def _split_category_nets(
    monthly_results: list[tuple[str, dict[str, Any]]],
    allowed_category_ids: set[str],
    detailed_section_mapping: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    """Per-category net totals for the mega split, summed across every
    constituent month.

    Calls accounting.net_category_totals() PER MONTH on that month's own
    normalized_transactions, then sums the resulting rows by category_id —
    reuses the EXACT SAME transfer-drop predicate monthly reports use (a
    transfer whose natural section isn't home/savings/excluded isn't real
    partner spend, dropped) so mega split dollar totals match summed
    monthly split totals instead of double-counting transfer noise.

    Fixed (iteration 4, finding 1): previously summed detail_agg["cats"]
    partner nets — detail_agg aggregates ALL normalized records with NO
    is_transfer gate (build_mega.py::_detail_agg feeds mega's own
    home/common/trips totals, a different, unconditional aggregation
    that's out of scope here) — reusing it for the split double-counted
    transfers vs monthly split sums.
    """
    totals: dict[str, dict[str, Any]] = {}
    for _month, result in monthly_results:
        records = result["contract"].get("normalized_transactions", [])
        rows = net_category_totals(records, allowed_category_ids, detailed_section_mapping)
        for row in rows:
            entry = totals.setdefault(
                row["category_id"],
                {
                    "category_id": row["category_id"],
                    "category_title": row["category_title"],
                    "section": row["section"],
                    "net_partner_a": 0.0,
                    "net_partner_b": 0.0,
                },
            )
            entry["net_partner_a"] += row["net_partner_a"]
            entry["net_partner_b"] += row["net_partner_b"]
    return list(totals.values())


def _txn_counts(monthly_results: list[tuple[str, dict[str, Any]]]) -> dict[str, int]:
    """Per-month len of ps_raw transactions (raw source count)."""
    counts: dict[str, int] = {}
    for month, _result in monthly_results:
        ps_raw_path = storage.monthly_ps_raw_path(month)
        if not ps_raw_path.exists():
            counts[month] = 0
            continue
        try:
            raw = json.loads(ps_raw_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            counts[month] = 0
            continue
        counts[month] = (
            len(raw) if isinstance(raw, list) else len(raw.get("transactions", []))
        )
    return counts


def compute_mega_split_summary(
    start: str,
    end: str,
    monthly_results: list[tuple[str, dict[str, Any]]],
    partner_labels: dict[str, str],
) -> dict[str, Any] | None:
    """Common-economy split_summary for a mega window — SINGLE source of
    truth reused by both build_mega_report (JSON/API path) and mega_pdf
    (HTML/PDF path, via assemble_html's split_summary param) so neither
    duplicates the split math. None when missing/disabled config, or
    detailed_section_mapping absent (net_category_totals() needs it to
    derive each record's natural section — same gate report_builder.
    _detailed() uses for monthly).
    """
    try:
        detailed_section_mapping = None
        if storage.DETAILED_SECTION_MAPPING_PATH.exists():
            detailed_section_mapping = load_detailed_section_mapping(
                storage.DETAILED_SECTION_MAPPING_PATH
            )
        category_parents = None
        if storage.CATEGORY_CATALOG_PATH.exists():
            category_parents = load_category_parents(storage.CATEGORY_CATALOG_PATH)
        split_config = load_split_config(
            storage.SPLIT_CONFIG_PATH, category_parents, detailed_section_mapping
        )
    except AccountingValidationError as exc:
        raise AccountingValidationError(
            f"split config invalid for mega {start}..{end}: {exc}"
        ) from exc
    if split_config is None or detailed_section_mapping is None:
        return None
    allowed_ids = _resolve_allowed_category_ids(
        split_config["categories"], category_parents
    )
    category_nets = _split_category_nets(
        monthly_results, allowed_ids, detailed_section_mapping
    )
    split_summary = compute_split(category_nets, split_config["shares"])
    split_summary["settlement"] = _resolve_split_settlement(
        split_summary["settlement"], partner_labels
    )
    return split_summary


def build_mega_report(start: str, end: str) -> dict[str, Any]:
    """Build mega report dict matching MegaReportResponse shape.

    Calls _build_namespace, build_context, extracts detail_agg/
    salary_allocation/recommendations/monthly_results, builds
    monthly_kpi_pages + txn_counts.
    """
    _validate_months(start, end)
    # Load labels once — _build_namespace reuses them (no second file read).
    partner_labels, label_warnings = _load_partner_labels()
    for warning in label_warnings:
        _logger.warning("partner-label validation: %s", warning)
    args = _build_namespace(start, end, partner_labels=partner_labels)
    try:
        context = build_context(args)
    finally:
        _cleanup_namespace(args)

    monthly_results = context["monthly_results"]
    detail_agg = context["detail_agg"]
    salary_allocation = context["salary_allocation"]
    recommendations = context.get("recommendations")

    # Common-economy split — optional, missing/disabled => split_summary=None.
    split_summary = compute_mega_split_summary(
        start, end, monthly_results, partner_labels
    )

    return {
        "start": start,
        "end": end,
        "contract_version": CONTRACT_VERSION,
        "calculation_version": MEGA_CALCULATION_VERSION,
        "txn_counts": _txn_counts(monthly_results),
        "months": detail_agg["months"],
        "partner_labels": partner_labels,
        "warnings": label_warnings,
        "detail_agg": detail_agg,
        "salary_allocation": salary_allocation,
        "recommendations": recommendations,
        "monthly_kpi_pages": _monthly_kpi_pages(monthly_results, detail_agg),
        "appendix_transactions": context.get("appendix_transactions", {}),
        "split_summary": split_summary,
    }


def write_mega_report(start: str, end: str, report_dict: dict[str, Any]) -> None:
    """Write mega report JSON atomically."""
    storage.atomic_write_json(storage.mega_report_path(start, end), report_dict)


def read_mega_report(start: str, end: str) -> dict[str, Any] | None:
    """Read mega report JSON. None if missing.

    Raises IncompatibleContractError when contract_version is absent or not
    the current marker — BEFORE validation (same reject-before-validate rule
    as monthly reports; the optional-with-defaults convention would mask v1).
    """
    report = storage.read_json(storage.mega_report_path(start, end))
    if report is None:
        return None
    found = report.get("contract_version") if isinstance(report, dict) else None
    if found != CONTRACT_VERSION:
        raise IncompatibleContractError(f"{start}_{end}", found)
    return report


def write_mega_status(start: str, end: str, status_dict: dict[str, Any]) -> None:
    """Write mega generate status atomically."""
    storage.atomic_write_json(storage.mega_report_status_path(start, end), status_dict)


def read_mega_status(start: str, end: str) -> dict[str, Any] | None:
    """Read mega generate status. None if missing."""
    return storage.read_json(storage.mega_report_status_path(start, end))


def check_mega_stale(start: str, end: str, report_dict: dict[str, Any]) -> bool:
    """Stale if version mismatch OR any month txn_count mismatch vs ps_raw."""
    if report_dict.get("calculation_version") != MEGA_CALCULATION_VERSION:
        return True
    txn_counts = report_dict.get("txn_counts", {})
    for month in inclusive_months(start, end):
        ps_raw_path = storage.monthly_ps_raw_path(month)
        if not ps_raw_path.exists():
            return True
        try:
            raw = json.loads(ps_raw_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return True
        raw_count = (
            len(raw) if isinstance(raw, list) else len(raw.get("transactions", []))
        )
        if txn_counts.get(month, 0) != raw_count:
            return True
    return False


def list_mega_reports() -> list[dict[str, str]]:
    """Scan PRIVATE_DATA_DIR for *_mega_report.json. Sorted newest first.

    Sort by start descending, then end descending.
    """
    private = storage.PRIVATE_DATA_DIR
    if not private.exists():
        return []
    reports: list[dict[str, str]] = []
    for path in private.iterdir():
        match = _MEGA_REPORT_FILE_RE.match(path.name)
        if match:
            reports.append({"start": match.group(1), "end": match.group(2)})
    reports.sort(key=lambda r: (r["start"], r["end"]), reverse=True)
    return reports


def _validate_months(start: str, end: str) -> None:
    """Check all months in range have ps_raw. Raise ValueError if missing."""
    for month in inclusive_months(start, end):
        if not storage.monthly_ps_raw_path(month).exists():
            raise ValueError(f"month {month} has no data, sync it first")
