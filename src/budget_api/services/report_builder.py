"""Report builder — wraps build_month_contract() + ports derived views to JSON.

Ports _root_totals, _owner_totals, _partner_panel from accounting_html.py.
_detailed() composes accounting.py's PR2 section builders into the
`detailed` DTO (models/reports.py). Returns JSON structures matching design
doc L4 shapes exactly.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# v4_pipeline lives in src/v4_pipeline — add to sys.path for imports.
_V4_DIR = Path(__file__).resolve().parents[2] / "v4_pipeline"
if str(_V4_DIR) not in sys.path:
    sys.path.insert(0, str(_V4_DIR))

from accounting import (  # noqa: E402
    AccountingValidationError,
    SPLIT_ELIGIBLE_SECTIONS,
    build_month_contract,
    compute_split,
    detailed_cc_payments_section,
    detailed_excluded_section,
    detailed_household_totals,
    detailed_income_section,
    detailed_net_section,
    detailed_personal_sections,
    detailed_savings_section,
    has_income_records,
    load_category_parents,
    load_category_roles,
    load_detailed_section_mapping,
    load_partner_labels,
    load_split_config,
    net_category_totals,
    validate_partner_labels,
)
from data_loader import load  # noqa: E402

from budget_api.services import storage

# PR1: 5 — detailed DTO contract (models/reports.py)
# PR5: 6 — paired rows display-strings → signed numerics; restored
# normalized_transactions; income can return None.
# 7→8: paired reimbursement rows nested per category row on NetCategoryRow;
# fully-paired categories now emit their zero-net row (no separate table).
# 8→9: common-economy split — detailed.split (SplitSection | None), additive.
CALCULATION_VERSION = 9

# Breaking-contract identity marker (contracts/monthly-report-contract-v2.md).
# Readers must reject stored payloads where this is absent or != 2 BEFORE
# pydantic validation — v2 DTO fields are optional-with-defaults, so a v1
# payload would otherwise validate with null personal sections and render
# empty sections as if valid.
CONTRACT_VERSION = 2

_logger = logging.getLogger(__name__)


class IncompatibleContractError(Exception):
    """Stored report fails the contract pre-check (absent/unknown marker).

    Routers map this to HTTP 409 with a regenerate remedy. `month` is the
    report month or mega range label; `found_version` is what was stored.
    """

    def __init__(self, month: str, found_version: object) -> None:
        self.month = month
        self.found_version = found_version
        super().__init__(
            f"report {month} has incompatible contract_version "
            f"{found_version!r} (expected {CONTRACT_VERSION})"
        )


def _load_excluded_account_ids() -> set[str]:
    """Load excluded account IDs from account_mappings.json.

    Bridges budget_api partner_id schema → v4_pipeline owner schema.
    v4_pipeline load_excluded_account_ids() expects {name,owner,excluded},
    but production data has {name,partner_id,type,excluded}.
    """
    if not storage.ACCOUNT_MAPPING_PATH.exists():
        return set()
    raw = storage.read_json(storage.ACCOUNT_MAPPING_PATH)
    if not isinstance(raw, dict):
        return set()
    accounts = raw.get("accounts", {})
    if not isinstance(accounts, dict):
        return set()
    return {
        acc_id
        for acc_id, acc in accounts.items()
        if isinstance(acc, dict) and acc.get("excluded") is True
    }


# Literal owner-slot tokens. An account partner_id equal to one of these is
# already a slot, not a custom partner ID — passthrough, never a pool member.
_LEGACY_SLOTS = frozenset({"partner_a", "partner_b"})


def _partner_slot_map(raw: dict) -> dict[str, str]:
    """Custom partner ID → "partner_a"/"partner_b" slot.

    Depersonalized schema: partner IDs are user-defined (e.g. "alex").
    Derive v4_pipeline owner slots deterministically from sorted partner IDs,
    mirroring bills_builder._partner_slot_map's identity-neutral ordering.
    IDs come from the partners block AND account partner_id values — except
    literal slot tokens ("partner_a"/"partner_b") found in account
    partner_id values: those tokens are already slots, never pool members
    (unconditionally — an empty partners block still derives slots from
    account values, and a literal token must not join the sorted pool),
    and pass through to owners unchanged in _load_account_owners (mirrors
    accounting.load_unified_account_mapping). Legacy files using literal
    "partner_a"/"partner_b" partners keys map identically. Shared by
    _load_account_owners and _load_partner_labels so both resolve identical
    slots for the same file. Twin of accounting._partner_slots (keep in sync).
    """
    accounts = raw.get("accounts", {})
    if not isinstance(accounts, dict):
        accounts = {}
    partners = raw.get("partners", {})
    partner_ids = set(partners) if isinstance(partners, dict) else set()
    for acc in accounts.values():
        if isinstance(acc, dict):
            pid = acc.get("partner_id")
            if isinstance(pid, str) and pid:
                if pid in _LEGACY_SLOTS:
                    # Already a slot — never a pool member, passthrough
                    # later. Unconditional: an empty partners block must not
                    # let a literal token join the sorted pool.
                    continue
                partner_ids.add(pid)
    if len(partner_ids) > 2:
        # Pipeline is two-owner only — first two sorted IDs win, rest dropped.
        _logger.warning(
            "account_mappings.json defines %d partner IDs; only the first two "
            "(sorted) get owner slots: %s",
            len(partner_ids),
            sorted(partner_ids)[:2],
        )
    return {
        pid: f"partner_{chr(ord('a') + i)}"
        for i, pid in enumerate(sorted(partner_ids))
        if i < 2
    }


def _load_account_owners() -> dict[str, str]:
    """Load account_id → partner_a/partner_b from account_mappings.json.

    Bridges budget_api partner_id schema → v4_pipeline owner schema.
    """
    if not storage.ACCOUNT_MAPPING_PATH.exists():
        return {}
    raw = storage.read_json(storage.ACCOUNT_MAPPING_PATH)
    if not isinstance(raw, dict):
        return {}
    accounts = raw.get("accounts", {})
    if not isinstance(accounts, dict):
        return {}
    slots = _partner_slot_map(raw)
    owners = {}
    for acc_id, acc in accounts.items():
        if not isinstance(acc, dict):
            continue
        partner_id = acc.get("partner_id")
        if partner_id in slots:
            owners[acc_id] = slots[partner_id]
        elif partner_id in _LEGACY_SLOTS:
            # Literal slot under a custom-ID partners block — passthrough.
            owners[acc_id] = partner_id
    return owners


def _load_partner_labels() -> tuple[dict[str, str], list[str]]:
    """Load + validate partner labels (canonical validator; never raises).

    Source order: partner_labels.json, then account_mappings.json partners
    block, then schema-less raw values piped through the validator (missing
    file → defaults, no warnings). An unreadable/unparseable labels file
    degrades to placeholder labels plus a visible warning — generation must
    never fail because of label configuration.
    """
    raw: Any = None
    if storage.PARTNER_LABELS_PATH.exists():
        try:
            raw = storage.read_json(storage.PARTNER_LABELS_PATH)
        except (OSError, ValueError):
            labels, _ = validate_partner_labels(None)
            return labels, [
                "partner_labels.json could not be parsed; using placeholder "
                "labels"
            ]
    elif storage.ACCOUNT_MAPPING_PATH.exists():
        mappings = storage.read_json(storage.ACCOUNT_MAPPING_PATH)
        if isinstance(mappings, dict):
            partners = mappings.get("partners", {})
            if isinstance(partners, dict):
                # Partners block is keyed by custom IDs — resolve through the
                # same sorted-slot map _load_account_owners uses, else real
                # labels never match the partner_a/partner_b slots.
                slots = _partner_slot_map(mappings)
                candidate = {
                    slot: partner.get("label")
                    for pid, slot in slots.items()
                    if isinstance(partner := partners.get(pid), dict)
                }
                raw = candidate or None
            else:
                # Malformed partners block — pipe through validator so it
                # degrades to placeholders with a warning.
                raw = partners
    return validate_partner_labels(raw)


def _now_iso() -> str:
    """ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Derived view ports — DATA logic only, return JSON matching L4 shapes.
# --------------------------------------------------------------------------- #


def _root_totals(categories: list[dict]) -> dict[str, float | int]:
    """Sum paid/received/net/count across root categories (parent_id is None)."""
    roots = [c for c in categories if c["parent_id"] is None]
    return {
        "paid": sum(c["paid"] for c in roots),
        "received": sum(c["received"] for c in roots),
        "net": sum(c["net"] for c in roots),
        "count": sum(c["count"] for c in roots),
    }


def _owner_totals(categories: list[dict]) -> dict[str, dict[str, float]]:
    """Per-partner sum of paid/received/net across root categories."""
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


def _partner_panels(
    owner_totals: dict[str, dict[str, float]],
    partner_labels: dict[str, str],
) -> dict[str, dict[str, Any]]:
    """Partner panels — label + paid/received/net + net_class."""
    panels = {}
    for owner, label in partner_labels.items():
        values = owner_totals.get(owner, {"paid": 0.0, "received": 0.0, "net": 0.0})
        panels[owner] = {
            "label": label,
            "paid": values["paid"],
            "received": values["received"],
            "net": values["net"],
            "net_class": "pos" if values["net"] >= 0 else "neg",
        }
    return panels


# --------------------------------------------------------------------------- #
# Detailed DTO composition (PR2) — accounting.py section builders → `detailed`.
# --------------------------------------------------------------------------- #


def _resolve_split_settlement(
    settlement: dict[str, Any] | None, partner_labels: dict[str, str]
) -> dict[str, Any] | None:
    """Slot-keyed settlement (partner_a/partner_b) → real display labels."""
    if settlement is None:
        return None
    return {
        "from_partner": partner_labels.get(
            settlement["from_partner"], settlement["from_partner"]
        ),
        "to_partner": partner_labels.get(
            settlement["to_partner"], settlement["to_partner"]
        ),
        "amount": settlement["amount"],
    }


def _detailed(
    normalized_transactions: list[dict[str, Any]],
    detailed_section_mapping: dict[str, Any] | None,
    savings_summary: dict[str, Any] | None,
    split_config: dict[str, Any] | None = None,
    partner_labels: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Compose the `detailed` DTO from accounting.py's section builders.

    None when detailed_section_mapping is unavailable — never fabricate
    zeros for a section that has no underlying data.
    """
    if detailed_section_mapping is None:
        return None
    records = normalized_transactions
    mapping = detailed_section_mapping
    personal = detailed_personal_sections(records, mapping)
    # income=None on no-income months (old-UI parity: FE shows
    # "No income this month." rather than a zero-filled table).
    income = (
        detailed_income_section(records, mapping)
        if has_income_records(records, mapping)
        else None
    )
    split = None
    if split_config is not None:
        section_nets = {
            section: net_category_totals(records, section, mapping)
            for section in SPLIT_ELIGIBLE_SECTIONS
        }
        split = compute_split(
            section_nets, split_config["shares"], split_config["sections"]
        )
        if split is not None:
            split["settlement"] = _resolve_split_settlement(
                split["settlement"], partner_labels or {}
            )
    return {
        "income": income,
        "savings": detailed_savings_section(records, savings_summary, mapping),
        "home": detailed_net_section(records, "home", mapping),
        "common": detailed_net_section(records, "common", mapping),
        "personal_partner_a": personal["personal_partner_a"],
        "personal_partner_b": personal["personal_partner_b"],
        "trips": detailed_net_section(records, "trips", mapping),
        "cc_payments": detailed_cc_payments_section(records, mapping),
        "excluded": detailed_excluded_section(records, mapping),
        "household_totals": detailed_household_totals(records, mapping),
        "split": split,
    }


def _personal_share(kpis: dict[str, Any] | None) -> float | None:
    """personal_spend / total_real_spend * 100 — None when kpis unavailable
    or real_spend is exactly 0 (design doc L2)."""
    if kpis is None:
        return None
    total = kpis.get("total", {})
    real_spend = total.get("real_spend", 0.0)
    if real_spend == 0:
        return None
    return total.get("personal_spend", 0.0) / real_spend * 100


def _partner_personal_share(kpis: dict[str, Any] | None, role: str) -> float | None:
    """Per-partner personal_spend / household total.real_spend * 100.

    Household denominator matches the old KpiPartnerPanel rendering
    ("personal_spend (X.X%)" per partner). None when kpis unavailable or
    real_spend is exactly 0 (never fabricate a 0% for an undefined ratio).
    """
    if kpis is None:
        return None
    total = kpis.get("total", {})
    real_spend = total.get("real_spend", 0.0)
    if real_spend == 0:
        return None
    partner = kpis.get(role, {})
    return partner.get("personal_spend", 0.0) / real_spend * 100


# --------------------------------------------------------------------------- #
# Build + storage — build_report, write/read report + status, stale check.
# --------------------------------------------------------------------------- #


def _load_transactions(month: str, ps_raw_path: Path, excluded: set[str]) -> list[dict]:
    """Load transactions from ps_raw, bridging list vs dict format.

    sync_runner writes bare list; v4_pipeline data_loader expects {transactions: [...]}.
    Writes temp wrapped file if needed.
    """
    import json as _json
    import tempfile

    raw = _json.loads(ps_raw_path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        # Wrap list → {transactions: [...]} for data_loader.
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", suffix=".json", delete=False
        ) as tmp:
            _json.dump({"transactions": raw}, tmp)
            tmp_path = tmp.name
        try:
            return load(month, tmp_path, excluded)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    return load(month, str(ps_raw_path), excluded)


def build_report(month: str) -> dict[str, Any]:
    """Load data, call build_month_contract, port derived views to JSON.

    Returns the public report DTO — contract fields ported to JSON plus
    pre-computed views + partner_labels + txn_count. The API schema
    (reports.py ReportResponse) is the authoritative surface; see
    DetailedSections for the per-section presentation contract.
    """
    ps_raw_path = storage.monthly_ps_raw_path(month)
    if not ps_raw_path.exists():
        raise FileNotFoundError(f"no data for month {month}")

    # Load config — bridge budget_api schema → v4_pipeline schema.
    # Paths computed at call time — storage.PRIVATE_DATA_DIR monkeypatched in tests.
    private = storage.PRIVATE_DATA_DIR
    excluded = _load_excluded_account_ids()
    transactions = _load_transactions(month, ps_raw_path, excluded)
    account_owners = _load_account_owners()
    try:
        detailed_section_mapping = load_detailed_section_mapping(
            private / "detailed_section_mapping.json"
        )
    except AccountingValidationError as exc:
        raise AccountingValidationError(
            f"detailed section mapping invalid for month {month}: {exc}"
        ) from exc
    partner_labels, label_warnings = _load_partner_labels()
    for warning in label_warnings:
        _logger.warning("partner-label validation: %s", warning)

    # category_roles — optional, only if file exists.
    category_roles = None
    roles_path = private / "category_roles.json"
    if roles_path.exists():
        category_roles = load_category_roles(roles_path)

    # category_parents — from catalog, for role resolution.
    category_parents = None
    catalog_path = private / "category_catalog.json"
    if catalog_path.exists():
        category_parents = load_category_parents(catalog_path)

    # Common-economy split config — optional, missing/disabled => split=None.
    try:
        split_config = load_split_config(storage.SPLIT_CONFIG_PATH)
    except AccountingValidationError as exc:
        raise AccountingValidationError(
            f"split config invalid for month {month}: {exc}"
        ) from exc

    contract = build_month_contract(
        transactions,
        account_owners=account_owners,
        category_roles=category_roles,
        detailed_section_mapping=detailed_section_mapping,
        category_parents=category_parents,
    )

    # Port derived views to JSON.
    categories = contract["categories"]
    records = contract["normalized_transactions"]
    root_totals = _root_totals(categories)
    owner_totals = _owner_totals(categories)
    partner_panels = _partner_panels(owner_totals, partner_labels)
    reconciliation = contract["reconciliation"]
    detailed_mapping = contract.get("detailed_section_mapping")
    kpis = contract.get("kpis")

    return {
        "month": month,
        "contract_version": CONTRACT_VERSION,
        "calculation_version": CALCULATION_VERSION,
        "txn_count": len(records),
        "normalized_transactions": records,
        "categories": categories,
        "reconciliation": reconciliation,
        "detailed_section_mapping": detailed_mapping,
        "kpis": kpis,
        "savings_summary": contract["savings_summary"],
        "root_totals": root_totals,
        "owner_totals": owner_totals,
        "partner_panels": partner_panels,
        "partner_labels": partner_labels,
        "warnings": label_warnings,
        "detailed": _detailed(
            records,
            detailed_mapping,
            contract["savings_summary"],
            split_config,
            partner_labels,
        ),
        "personal_share": _personal_share(kpis),
        "personal_share_partner_a": _partner_personal_share(kpis, "partner_a"),
        "personal_share_partner_b": _partner_personal_share(kpis, "partner_b"),
        "balanced": reconciliation["difference"] == 0.0,
    }


def write_report(month: str, report_dict: dict[str, Any]) -> None:
    """Write report JSON atomically to {month}_monthly_report.json."""
    storage.atomic_write_json(storage.monthly_report_path(month), report_dict)


def read_report(month: str) -> dict[str, Any] | None:
    """Read report JSON. None if missing.

    Raises IncompatibleContractError when contract_version is absent or not
    the current marker — BEFORE any model validation (v1 payloads with old
    keys would otherwise validate with null sections and render empty).
    """
    report = storage.read_json(storage.monthly_report_path(month))
    if report is None:
        return None
    found = report.get("contract_version") if isinstance(report, dict) else None
    if found != CONTRACT_VERSION:
        raise IncompatibleContractError(month, found)
    return report


def write_status(month: str, status_dict: dict[str, Any]) -> None:
    """Write generate status atomically to {month}_monthly_report_status.json."""
    storage.atomic_write_json(storage.monthly_report_status_path(month), status_dict)


def read_status(month: str) -> dict[str, Any] | None:
    """Read generate status. None if missing."""
    return storage.read_json(storage.monthly_report_status_path(month))


def check_stale(month: str, report_dict: dict[str, Any]) -> bool:
    """Stale if report calculations or source transaction count differ."""
    if report_dict.get("calculation_version") != CALCULATION_VERSION:
        return True
    ps_raw_path = storage.monthly_ps_raw_path(month)
    if not ps_raw_path.exists():
        return True  # no source data → stale
    try:
        raw = json.loads(ps_raw_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return True
    # ps_raw is a list of transactions (sync_runner writes list directly).
    raw_count = len(raw) if isinstance(raw, list) else len(raw.get("transactions", []))
    report_count = report_dict.get("txn_count", 0)
    return raw_count != report_count


_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def list_months() -> list[str]:
    """Scan data/private for *_ps_raw.json. Sorted descending."""
    private = storage.PRIVATE_DATA_DIR
    if not private.exists():
        return []
    months = []
    for path in private.glob("*_ps_raw.json"):
        stem = path.stem  # e.g. "2026-07_ps_raw"
        month = stem.replace("_ps_raw", "")
        if _MONTH_RE.match(month):
            months.append(month)
    return sorted(months, reverse=True)
