"""Normalized generic accounting for supported report paths."""

from __future__ import annotations

import json
import logging
import math
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

# New pattern for this module (iteration 4, finding 3): accounting.py was
# previously logging-free/pure (see the compute_split section docstring
# below). Adding just enough logging to surface an otherwise-silent
# best-effort degradation (_resolve_allowed_category_ids, catalog-absent
# case) in report-build logs — same _logger convention already used by
# report_builder.py/mega_builder.py, extended here on purpose.
_logger = logging.getLogger(__name__)

PARTNERS = ("partner_a", "partner_b")
KPI_ROLES = {"income", "savings", "spend", "personal_spend", "investment", "exclude"}
DETAILED_CATEGORY_SECTIONS = {
    "income_salary",
    "income_third_party",
    "savings",
    "home",
    "common",
    "personal_partner_a",
    "personal_partner_b",
    "trips",
    "cc_payments",
    "excluded",
}
DETAILED_ACCOUNT_ROLES = {
    "credit_card",
    "savings_partner_a",
    "savings_partner_b",
}
# Common-economy split — Gate 1's 3 candidate sections. Since Gate 2
# (category-level split selection), this is no longer an eligibility
# restriction for compute_split (any catalog category can be selected) —
# it's kept only for legacy split_config.json migration semantics
# (migrate_legacy_split_sections rejects an old sections-only file whose
# values fall outside this set) and the GET-default response shape. Twin of
# budget_api.models.settings.SPLIT_ELIGIBLE_SECTIONS (keep in sync —
# v4_pipeline cannot import budget_api).
SPLIT_ELIGIBLE_SECTIONS = frozenset({"home", "common", "trips"})
PRIVATE_ACCOUNT_MAPPING = (
    Path(__file__).resolve().parents[2] / "data" / "private" / "account_mappings.json"
)
PRIVATE_DETAILED_SECTION_MAP = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "private"
    / "detailed_section_mapping.json"
)
PRIVATE_CATEGORY_CATALOG = (
    Path(__file__).resolve().parents[2] / "data" / "private" / "category_catalog.json"
)
PRIVATE_SPLIT_CONFIG = (
    Path(__file__).resolve().parents[2] / "data" / "private" / "split_config.json"
)
DEFAULT_PARTNER_LABELS = {"partner_a": "Partner A", "partner_b": "Partner B"}
MAX_PARTNER_LABEL_LENGTH = 64
RESERVED_PARTNER_PLACEHOLDERS = {label.lower() for label in DEFAULT_PARTNER_LABELS.values()}


def validate_partner_labels(raw: Any) -> tuple[dict[str, str], list[str]]:
    """Canonical partner-label validation (contracts/partner-labels-config.md).

    Accepts any parsed JSON value. Returns (labels, warnings) where labels are
    always renderable: any violation degrades the affected partner(s) to the
    neutral placeholder plus a visible warning. Never raises, never returns a
    bad value.
    """
    labels = dict(DEFAULT_PARTNER_LABELS)
    warnings: list[str] = []
    if raw is None:
        return labels, warnings
    if not isinstance(raw, dict):
        warnings.append(
            "partner_label configuration is not an object; using default labels"
        )
        return labels, warnings
    extras = sorted(set(raw) - set(PARTNERS))
    if extras:
        warnings.append(
            "partner_label configuration has unknown key(s) "
            + ", ".join(repr(extra) for extra in extras)
            + "; ignored"
        )
    validated: dict[str, str] = {}
    for owner in PARTNERS:
        if owner not in raw:
            warnings.append(
                f"partner_label configuration is missing {owner!r}; "
                "using placeholder"
            )
            continue
        value = raw[owner]
        if not isinstance(value, str):
            warnings.append(
                f"partner_label {owner!r} is not a string; using placeholder"
            )
            continue
        label = value.strip()
        if not label:
            warnings.append(
                f"partner_label {owner!r} is empty; using placeholder"
            )
            continue
        if label.lower() in RESERVED_PARTNER_PLACEHOLDERS:
            warnings.append(
                f"partner_label {owner!r} uses a reserved placeholder value; "
                "rejected"
            )
            continue
        if len(label) > MAX_PARTNER_LABEL_LENGTH:
            warnings.append(
                f"partner_label {owner!r} exceeds {MAX_PARTNER_LABEL_LENGTH} "
                "characters; truncated"
            )
            label = label[:MAX_PARTNER_LABEL_LENGTH]
        validated[owner] = label
    lowered: dict[str, str] = {}
    duplicate = False
    for owner, label in validated.items():
        key = label.lower()
        if key in lowered:
            duplicate = True
            warnings.append(
                "partner labels must be distinct; "
                f"{owner!r} duplicates {lowered[key]!r}; "
                "both partners use placeholders"
            )
        else:
            lowered[key] = owner
    if duplicate:
        return labels, warnings
    labels.update(validated)
    return labels, warnings


class AccountingValidationError(ValueError):
    """Raised when report input cannot support reliable accounting."""


def _required_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AccountingValidationError(f"{field} must be an object")
    return value


def _required_identifier(value: Any, field: str) -> str:
    if value is None or value == "":
        raise AccountingValidationError(f"{field} is required")
    return str(value)


def _optional_text(value: Any, field: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise AccountingValidationError(f"{field} must be a string")
    return value


def _category_title(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value.strip().isdigit():
        raise AccountingValidationError(
            f"{field} must be a non-numeric, non-empty string"
        )
    return value


def _category_node(value: Any, field: str) -> dict[str, str]:
    node = _required_mapping(value, field)
    return {
        "id": _required_identifier(node.get("id"), f"{field}.id"),
        "title": _category_title(node.get("title"), f"{field}.title"),
    }


def _literal_transfer_flag(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise AccountingValidationError(f"{field} must be a boolean")
    return value


def _partner_slots(partners: dict[str, Any]) -> dict[str, str]:
    """Custom partner ID → "partner_a"/"partner_b" slot.

    Twin of budget_api.services.report_builder._partner_slot_map (keep in
    sync) — v4_pipeline cannot import budget_api (report_builder imports
    accounting). Same ordering rule: sorted partner IDs, first → partner_a,
    second → partner_b. Same passthrough rule as the twin: account
    owner/partner_id values equal to a literal slot token
    ("partner_a"/"partner_b") are never pool members — when the partners
    block uses custom IDs they pass through to owners unchanged (applied in
    load_unified_account_mapping). Unlike the twin, only partners-block keys
    feed the map (labels live in that block, so it is mandatory here); the
    twin also scans account partner_id values because its partners block may
    be absent. Legacy literal "partner_a"/"partner_b" keys map identically.
    """
    return {
        pid: f"partner_{chr(ord('a') + i)}"
        for i, pid in enumerate(sorted(partners))
        if i < 2
    }


def load_unified_account_mapping(
    mapping_path: str | Path | None = None,
) -> tuple[dict[str, str], dict[str, str], dict[str, dict[str, Any]]]:
    """Load the human-maintained unified private account mapping."""
    try:
        mapping = json.loads(
            Path(mapping_path or PRIVATE_ACCOUNT_MAPPING).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise AccountingValidationError(
            "Unified account mapping is unreadable"
        ) from error
    mapping = _required_mapping(mapping, "unified account mapping")
    if set(mapping) != {"schema_version", "partners", "accounts"}:
        raise AccountingValidationError("Unified account mapping has invalid fields")
    if type(mapping["schema_version"]) is not int or mapping["schema_version"] != 1:
        raise AccountingValidationError(
            "Unified account mapping has an invalid schema version"
        )
    partners = _required_mapping(
        mapping["partners"], "unified account mapping.partners"
    )
    # Depersonalized schema — partners block keys are user-defined IDs, not
    # the literal slots. Require exactly two.
    if len(partners) != 2:
        raise AccountingValidationError(
            "Unified account mapping must define exactly both partners"
        )
    slots = _partner_slots(partners)
    slot_ids = {slot: pid for pid, slot in slots.items()}
    labels = {}
    for owner in PARTNERS:
        partner = _required_mapping(
            partners[slot_ids[owner]],
            f"unified account mapping.partners.{slot_ids[owner]}",
        )
        # savings_category_id optional (bills feature), no other extra keys allowed.
        if set(partner) - {"label", "savings_category_id"}:
            raise AccountingValidationError(
                "Unified account mapping has an invalid partner label"
            )
        if not isinstance(partner.get("label"), str) or not partner["label"]:
            raise AccountingValidationError(
                "Unified account mapping has an invalid partner label"
            )
        if "savings_category_id" in partner and (
            type(partner["savings_category_id"]) is not int
        ):
            raise AccountingValidationError(
                "Unified account mapping has an invalid savings_category_id"
            )
        labels[owner] = partner["label"]
    if labels["partner_a"] == labels["partner_b"]:
        raise AccountingValidationError(
            "Unified account mapping partner labels must be distinct"
        )
    accounts = _required_mapping(
        mapping["accounts"], "unified account mapping.accounts"
    )
    parsed_accounts = {}
    for account_id, account in accounts.items():
        if not isinstance(account_id, str) or not account_id:
            raise AccountingValidationError(
                "Unified account mapping has an invalid account ID"
            )
        account = _required_mapping(
            account, f"unified account mapping.accounts.{account_id}"
        )
        # Accept owner or partner_id alias; type is optional metadata.
        owner_value = account.get("owner", account.get("partner_id"))
        if set(account) - {"name", "owner", "partner_id", "type", "excluded"}:
            raise AccountingValidationError(
                "Unified account mapping has invalid account fields"
            )
        if not isinstance(account["name"], str) or not account["name"]:
            raise AccountingValidationError(
                "Unified account mapping has an invalid account name"
            )
        # owner/partner_id may be None for joint accounts. Custom partner IDs
        # resolve to their slot; literal slots pass through unchanged.
        if owner_value is not None and (
            not isinstance(owner_value, str)
            or (owner_value not in slots and owner_value not in PARTNERS)
        ):
            raise AccountingValidationError(
                "Unified account mapping has an invalid owner"
            )
        if type(account["excluded"]) is not bool:
            raise AccountingValidationError(
                "Unified account mapping has an invalid exclusion"
            )
        parsed_accounts[account_id] = {
            **account,
            "owner": slots.get(owner_value, owner_value),
        }
    return (
        {
            account_id: account["owner"]
            for account_id, account in parsed_accounts.items()
        },
        labels,
        parsed_accounts,
    )


def load_account_owners(mapping_path: str | Path | None = None) -> dict[str, str]:
    """Load the unified default or an explicit legacy owner-only map."""
    legacy_path = mapping_path or os.environ.get("POCKETSMITH_ACCOUNT_OWNER_MAP")
    if legacy_path is None:
        if not PRIVATE_ACCOUNT_MAPPING.exists():
            return {}
        owners, _labels, _accounts = load_unified_account_mapping()
        return owners
    path = Path(legacy_path)
    if not path.exists():
        return {}
    try:
        mapping = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AccountingValidationError(
            "Account ownership mapping is unreadable"
        ) from error
    mapping = _required_mapping(mapping, "account ownership mapping")
    owners = {str(account_id): owner for account_id, owner in mapping.items()}
    if any(owner not in PARTNERS for owner in owners.values()):
        raise AccountingValidationError(
            "Account ownership mapping has an invalid owner"
        )
    return owners


def load_excluded_account_ids() -> set[str]:
    """Load excluded IDs from the unified production map when present."""
    if not PRIVATE_ACCOUNT_MAPPING.exists():
        return set()
    _owners, _labels, accounts = load_unified_account_mapping()
    return {
        account_id for account_id, account in accounts.items() if account["excluded"]
    }


def load_partner_labels(mapping_path: str | Path | None = None) -> dict[str, str]:
    """Load unified default labels or an explicit legacy label-only map.

    Parsed values are piped through validate_partner_labels (never raises for
    value problems); any degradation warnings go to stderr. An unreadable or
    non-object mapping still fails loudly (AccountingValidationError).
    """
    if mapping_path is None:
        if not PRIVATE_ACCOUNT_MAPPING.exists():
            return dict(DEFAULT_PARTNER_LABELS)
        _owners, labels, _accounts = load_unified_account_mapping()
        labels, warnings = validate_partner_labels(labels)
    else:
        path = Path(mapping_path)
        if not path.exists():
            return dict(DEFAULT_PARTNER_LABELS)
        try:
            mapping = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise AccountingValidationError(
                "Partner label mapping is unreadable"
            ) from error
        mapping = _required_mapping(mapping, "partner label mapping")
        labels, warnings = validate_partner_labels(mapping)
    for warning in warnings:
        print(f"partner-label validation: {warning}", file=sys.stderr)
    return labels


def load_category_roles(mapping_path: str | Path) -> dict[str, str]:
    """Load explicit local category roles for KPI calculations."""
    try:
        mapping = json.loads(Path(mapping_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AccountingValidationError(
            "Category role mapping is unreadable"
        ) from error
    mapping = _required_mapping(mapping, "category role mapping")
    roles = {str(category_id): role for category_id, role in mapping.items()}
    if any(role not in KPI_ROLES for role in roles.values()):
        raise AccountingValidationError("Category role mapping has an invalid role")
    return roles


def load_detailed_section_mapping(
    mapping_path: str | Path,
) -> dict[str, dict[str, str]]:
    """Load local stable-ID routing for detailed monthly report sections."""
    try:
        mapping = json.loads(Path(mapping_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AccountingValidationError(
            "Detailed section mapping is unreadable"
        ) from error
    return _detailed_section_mapping(mapping)


def load_category_parents(catalog_path: str | Path) -> dict[str, str | None]:
    """Load authoritative parent IDs from a PocketSmith category catalog."""
    try:
        catalog = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AccountingValidationError("Category catalog is unreadable") from error
    catalog = _required_mapping(catalog, "category catalog")
    categories = catalog.get("categories")
    if not isinstance(categories, list):
        raise AccountingValidationError("Category catalog.categories must be a list")
    parents: dict[str, str | None] = {}

    def add_categories(
        nodes: list[Any], tree_parent_id: str | None, field: str
    ) -> None:
        for index, category in enumerate(nodes):
            category = _required_mapping(category, f"{field}[{index}]")
            category_id = _required_identifier(
                category.get("id"), f"{field}[{index}].id"
            )
            parent_id = category.get("parent_id")
            if parent_id is not None:
                parent_id = _required_identifier(
                    parent_id, f"{field}[{index}].parent_id"
                )
            if tree_parent_id is not None:
                if parent_id is not None and parent_id != tree_parent_id:
                    raise AccountingValidationError(
                        "Category catalog child conflicts with its parent ID"
                    )
                parent_id = tree_parent_id
            if category_id in parents:
                raise AccountingValidationError(
                    "Category catalog has duplicate category IDs"
                )
            parents[category_id] = parent_id
            children = category.get("children", [])
            if not isinstance(children, list):
                raise AccountingValidationError(
                    f"{field}[{index}].children must be a list"
                )
            add_categories(children, category_id, f"{field}[{index}].children")

    add_categories(categories, None, "category catalog.categories")
    for category_id, parent_id in parents.items():
        if parent_id is not None and parent_id not in parents:
            raise AccountingValidationError(
                f"Category catalog parent is missing for category ID {category_id!r}"
            )
    return parents


def load_category_titles(catalog_path: str | Path) -> dict[str, str]:
    """Load authoritative display titles keyed by PocketSmith category ID."""
    try:
        catalog = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AccountingValidationError("Category catalog is unreadable") from error
    catalog = _required_mapping(catalog, "category catalog")
    categories = catalog.get("categories")
    if not isinstance(categories, list):
        raise AccountingValidationError("Category catalog.categories must be a list")
    titles: dict[str, str] = {}

    def add_categories(nodes: list[Any], field: str) -> None:
        for index, category in enumerate(nodes):
            category = _required_mapping(category, f"{field}[{index}]")
            category_id = _required_identifier(
                category.get("id"), f"{field}[{index}].id"
            )
            if category_id in titles:
                raise AccountingValidationError(
                    "Category catalog has duplicate category IDs"
                )
            titles[category_id] = _category_title(
                category.get("title"), f"{field}[{index}].title"
            )
            children = category.get("children", [])
            if not isinstance(children, list):
                raise AccountingValidationError(
                    f"{field}[{index}].children must be a list"
                )
            add_categories(children, f"{field}[{index}].children")

    add_categories(categories, "category catalog.categories")
    return titles


def savings_movement_totals(
    records: list[dict[str, Any]], mapping: dict[str, dict[str, str]]
) -> dict[str, dict[str, float]]:
    """Return legacy in/out fields from shared savings calculation."""
    summary = savings_summary(records, mapping, None, None)
    return {
        owner: {
            "in": summary[owner]["to_savings"],
            "out": summary[owner]["from_savings"],
        }
        for owner in PARTNERS
    }


def savings_summary(
    records: list[dict[str, Any]],
    mapping: dict[str, dict[str, str]] | None,
    roles: dict[str, str] | None,
    category_parents: dict[str, str | None] | None,
) -> dict[str, dict[str, float]]:
    """Calculate account flows plus abs(partner Kron net) once."""
    summary = {
        owner: {
            "to_savings": 0.0,
            "from_savings": 0.0,
            "kron_net": 0.0,
            "net_saved": 0.0,
        }
        for owner in PARTNERS
    }
    if mapping is not None:
        _validated_savings_account_ids(records, mapping)
    account_roles = mapping["account_roles"] if mapping is not None else {}
    sections = mapping["category_sections"] if mapping is not None else {}
    for record in records:
        category_id = record["category_path"][-1]["id"]
        role = (
            _resolve_category_mapping(
                category_id,
                roles,
                category_parents,
                "Category role mapping",
                records,
            )
            if roles is not None
            else None
        )
        values = summary[record["owner"]]
        if sections.get(category_id) == "savings" or role == "investment":
            values["kron_net"] += record["amount"]
        if account_roles.get(record["account_id"]) not in {
            "savings_partner_a",
            "savings_partner_b",
        }:
            continue
        if record["amount"] >= 0:
            values["to_savings"] += record["amount"]
        else:
            values["from_savings"] += abs(record["amount"])

    for values in summary.values():
        values["to_savings"] += abs(values["kron_net"])
        values["net_saved"] = values["to_savings"] - values["from_savings"]
    total = {
        field: sum(summary[owner][field] for owner in PARTNERS)
        for field in ("to_savings", "from_savings", "kron_net", "net_saved")
    }
    return {**summary, "total": total}


def _is_savings_movement(
    record: dict[str, Any], mapping: dict[str, dict[str, str]]
) -> bool:
    account_role = mapping["account_roles"].get(record["account_id"])
    category_id = record["category_path"][-1]["id"]
    return account_role in {"savings_partner_a", "savings_partner_b"} or (
        mapping["category_sections"].get(category_id) == "savings"
    )


def _savings_signed_amount(
    record: dict[str, Any], mapping: dict[str, dict[str, str]]
) -> float:
    """Return the savings-perspective signed amount for one savings movement.

    Category-routed records flip the sign, including overlap with a savings
    account role. Other savings-account records keep the raw transaction sign.
    """
    category_id = record["category_path"][-1]["id"]
    if mapping["category_sections"].get(category_id) == "savings":
        return -record["amount"]
    account_role = mapping["account_roles"].get(record["account_id"])
    if account_role in {"savings_partner_a", "savings_partner_b"}:
        return record["amount"]
    return record["amount"]


def _detailed_section_mapping(value: Any) -> dict[str, dict[str, str]]:
    mapping = _required_mapping(value, "detailed section mapping")
    category_sections = _required_mapping(
        mapping.get("category_sections"), "detailed section mapping.category_sections"
    )
    account_roles = _required_mapping(
        mapping.get("account_roles"), "detailed section mapping.account_roles"
    )
    sections = {
        str(category_id): role for category_id, role in category_sections.items()
    }
    accounts = {str(account_id): role for account_id, role in account_roles.items()}
    if any(role not in DETAILED_CATEGORY_SECTIONS for role in sections.values()):
        raise AccountingValidationError(
            "Detailed section mapping has an invalid category section"
        )
    if any(role not in DETAILED_ACCOUNT_ROLES for role in accounts.values()):
        raise AccountingValidationError(
            "Detailed section mapping has an invalid account role"
        )
    return {"category_sections": sections, "account_roles": accounts}


def _validate_detailed_section_categories(
    records: list[dict[str, Any]],
    mapping: dict[str, dict[str, str]],
    category_parents: dict[str, str | None] | None,
) -> None:
    category_sections = mapping["category_sections"]
    for record in records:
        category_id = record["category_path"][-1]["id"]
        category_sections[category_id] = _resolve_category_mapping(
            category_id,
            category_sections,
            category_parents,
            "Detailed section mapping",
            records,
        )


def _category_id_hint(category_id: str) -> str:
    """Extra context for the synthetic 'uncategorized' catalog ID."""
    if category_id == "uncategorized":
        return (
            " (category ID 'uncategorized' = transaction has no category "
            "assigned in PocketSmith)"
        )
    return ""


def _format_affected_transactions(
    records: list[dict[str, Any]] | None, category_id: str, limit: int = 10
) -> str:
    """Render up to `limit` txns whose category path touches category_id.

    For error messages only — lets user find/fix the offending data. Bounded
    so one bad mapping doesn't dump a whole month of txns into a string.
    """
    if not records:
        return ""
    matches = [
        record
        for record in records
        if any(
            node.get("id") == category_id
            for node in record.get("category_path", [])
        )
    ]
    if not matches:
        return ""
    lines = []
    for record in matches[:limit]:
        leaf = record["category_path"][-1]
        lines.append(
            "id={!r} date={!r} payee={!r} amount={!r} category={!r} "
            "(category_id={!r})".format(
                record.get("id"),
                record.get("date"),
                record.get("payee"),
                record.get("amount"),
                leaf.get("title"),
                leaf.get("id"),
            )
        )
    suffix = " Affected transactions: " + "; ".join(lines)
    remaining = len(matches) - limit
    if remaining > 0:
        suffix += f"; +{remaining} more"
    return suffix


def _resolve_category_mapping(
    category_id: str,
    mapping: dict[str, str],
    category_parents: dict[str, str | None] | None,
    label: str,
    records: list[dict[str, Any]] | None = None,
) -> str:
    current_id = category_id
    visited: set[str] = set()
    while True:
        mapped = mapping.get(current_id)
        if mapped is not None:
            return mapped
        if category_parents is None:
            raise _unmapped_category_error(label, category_id, records)
        if current_id in visited:
            raise AccountingValidationError("Category catalog hierarchy has a cycle")
        visited.add(current_id)
        if current_id not in category_parents:
            raise AccountingValidationError(
                f"Category catalog has no category ID {current_id!r}"
                + _category_id_hint(current_id)
                + _format_affected_transactions(records, category_id)
            )
        parent_id = category_parents[current_id]
        if parent_id is None:
            raise _unmapped_category_error(label, category_id, records)
        current_id = parent_id


def _unmapped_category_error(
    label: str,
    category_id: str,
    records: list[dict[str, Any]] | None = None,
) -> AccountingValidationError:
    hint = _category_id_hint(category_id)
    details = _format_affected_transactions(records, category_id)
    if label == "Detailed section mapping":
        return AccountingValidationError(
            f"Detailed section mapping has no section for category ID {category_id!r}"
            + hint
            + details
        )
    return AccountingValidationError(
        f"A reportable category has no KPI role for category ID {category_id!r}"
        + hint
        + details
    )


def _synthetic_owner(
    transaction: dict[str, Any], account: dict[str, Any]
) -> str | None:
    """Permit only tracked synthetic records to use non-private fixture ownership."""
    transaction_id = transaction.get("id")
    account_name = account.get("name")
    if not isinstance(transaction_id, int) or not 100000 <= transaction_id < 200000:
        return None
    if isinstance(account_name, str) and account_name.startswith("Fixture A "):
        return "partner_a"
    if isinstance(account_name, str) and account_name.startswith("Fixture B "):
        return "partner_b"
    return None


def normalize_transactions(
    transactions: list[dict[str, Any]], account_owners: dict[str, str] | None = None
) -> list[dict[str, Any]]:
    """Validate and normalize transactions before report aggregation."""
    owners = load_account_owners() if account_owners is None else dict(account_owners)
    if any(owner not in PARTNERS for owner in owners.values()):
        raise AccountingValidationError(
            "Account ownership mapping has an invalid owner"
        )
    normalized = []
    category_titles: dict[str, str] = {}
    category_parents: dict[str, str | None] = {}
    for index, transaction in enumerate(transactions):
        transaction = _required_mapping(transaction, f"transactions[{index}]")
        amount = transaction.get("amount")
        if (
            isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or not math.isfinite(amount)
        ):
            raise AccountingValidationError(
                f"transactions[{index}].amount must be finite"
            )
        date_value = transaction.get("date")
        if not isinstance(date_value, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}", date_value
        ):
            raise AccountingValidationError(f"transactions[{index}].date is required")
        try:
            date.fromisoformat(date_value)
        except ValueError as error:
            raise AccountingValidationError(
                f"transactions[{index}].date is invalid"
            ) from error
        account = transaction.get("account") or transaction.get("transaction_account")
        account = _required_mapping(account, f"transactions[{index}].account")
        account_id = _required_identifier(
            account.get("id"), f"transactions[{index}].account.id"
        )
        owner = owners.get(account_id) or _synthetic_owner(transaction, account)
        if owner not in PARTNERS:
            raise AccountingValidationError(
                f"transactions[{index}] has no account-ID owner mapping"
            )
        category = _category_node(
            transaction.get("category"), f"transactions[{index}].category"
        )
        hierarchy = transaction.get("category_hierarchy")
        parent = transaction["category"].get("parent") or transaction["category"].get(
            "parent_category"
        )
        if hierarchy is None:
            hierarchy = (
                [
                    _category_node(parent, f"transactions[{index}].category.parent"),
                    category,
                ]
                if parent
                else [category]
            )
        if not isinstance(hierarchy, list) or not hierarchy:
            raise AccountingValidationError(
                f"transactions[{index}].category_hierarchy must be non-empty"
            )
        path = [
            _category_node(node, f"transactions[{index}].category_hierarchy")
            for node in hierarchy
        ]
        if path[-1] != category:
            raise AccountingValidationError(
                f"transactions[{index}] hierarchy leaf must match category"
            )
        if parent is not None:
            parent_node = _category_node(
                parent, f"transactions[{index}].category.parent"
            )
            if len(path) < 2 or path[-2] != parent_node:
                raise AccountingValidationError(
                    f"transactions[{index}] hierarchy conflicts with category parent"
                )
        if len({node["id"] for node in path}) != len(path):
            raise AccountingValidationError(
                f"transactions[{index}] category hierarchy has a cycle"
            )
        for path_index, node in enumerate(path):
            known_title = category_titles.setdefault(node["id"], node["title"])
            if known_title != node["title"]:
                raise AccountingValidationError(
                    f"transactions[{index}] category ID has a conflicting title"
                )
            parent_id = path[path_index - 1]["id"] if path_index else None
            if (
                node["id"] in category_parents
                and category_parents[node["id"]] != parent_id
            ):
                raise AccountingValidationError(
                    f"transactions[{index}] category ID has a conflicting parent"
                )
            category_parents[node["id"]] = parent_id
        normalized.append(
            {
                "id": transaction.get("id"),
                "date": date_value,
                "amount": float(amount),
                "payee": _optional_text(
                    transaction.get("payee"), f"transactions[{index}].payee"
                ),
                "note": _optional_text(
                    transaction.get("note"), f"transactions[{index}].note"
                ),
                "account_id": account_id,
                "account_name": _optional_text(
                    account.get("name"), f"transactions[{index}].account.name"
                ),
                "owner": owner,
                "category_path": path,
                "is_transfer": (
                    _literal_transfer_flag(
                        transaction["is_transfer"], f"transactions[{index}].is_transfer"
                    )
                    if transaction.get("is_transfer") is not None
                    else False
                )
                or (
                    _literal_transfer_flag(
                        transaction["category"]["is_transfer"],
                        f"transactions[{index}].category.is_transfer",
                    )
                    if transaction["category"].get("is_transfer") is not None
                    else False
                ),
                # Trip clustering in src/mom/trips.py groups txns by the first
                # PS label. Preserve raw labels so downstream code can attach
                # txns to their trip cluster.
                "labels": _optional_labels(
                    transaction.get("labels"), f"transactions[{index}].labels"
                ),
            }
        )
    return normalized


def _optional_labels(value: Any, path: str) -> list[str]:
    """Normalize a PS labels field to a list of stripped strings.

    PS sometimes returns null or a non-list. Coerce to an empty list so
    downstream trip clustering treats the txn as untagged.
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise AccountingValidationError(f"{path} must be a list of strings")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise AccountingValidationError(f"{path} entries must be strings")
        stripped = item.strip()
        if stripped:
            out.append(stripped)
    return out


def _new_bucket(
    node: dict[str, str], parent_id: str | None, path: list[dict[str, str]]
) -> dict[str, Any]:
    return {
        "id": node["id"],
        "title": node["title"],
        "parent_id": parent_id,
        "path": [dict(item) for item in path],
        "paid": 0.0,
        "received": 0.0,
        "net": 0.0,
        "count": 0,
        "owners": {
            owner: {"paid": 0.0, "received": 0.0, "net": 0.0} for owner in PARTNERS
        },
    }


def _aggregate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for record in records:
        amount = record["amount"]
        paid, received = max(-amount, 0.0), max(amount, 0.0)
        for path_index, node in enumerate(record["category_path"]):
            bucket = buckets.setdefault(
                node["id"],
                _new_bucket(
                    node,
                    (
                        record["category_path"][path_index - 1]["id"]
                        if path_index
                        else None
                    ),
                    record["category_path"][: path_index + 1],
                ),
            )
            bucket["paid"] += paid
            bucket["received"] += received
            bucket["net"] += paid - received
            bucket["count"] += 1
            owner = bucket["owners"][record["owner"]]
            owner["paid"] += paid
            owner["received"] += received
            owner["net"] += paid - received
    return sorted(
        buckets.values(),
        key=lambda bucket: (len(bucket["path"]), bucket["title"], bucket["id"]),
    )


def _role_kpis(
    records: list[dict[str, Any]],
    roles: dict[str, str],
    category_parents: dict[str, str | None] | None,
    detailed_section_mapping: dict[str, dict[str, str]] | None,
    summary: dict[str, dict[str, float]],
) -> dict[str, Any]:
    totals = {
        owner: {
            "income": 0.0,
            "real_spend": 0.0,
            "personal_spend": 0.0,
            "net_cash": 0.0,
            "net_savings": 0.0,
            "investment": 0.0,
        }
        for owner in (*PARTNERS, "total")
    }
    for record in records:
        amount = record["amount"]
        category_id = record["category_path"][-1]["id"]
        role = _resolve_category_mapping(
            category_id, roles, category_parents, "Category role mapping", records
        )
        if role == "exclude":
            continue
        values = totals[record["owner"]]
        total_values = totals["total"]
        if role == "income":
            values["income"] += amount
            total_values["income"] += amount
        elif role in {"spend", "personal_spend"}:
            values["real_spend"] -= amount
            total_values["real_spend"] -= amount
            if role == "personal_spend":
                values["personal_spend"] -= amount
                total_values["personal_spend"] -= amount
        elif role == "investment":
            values["investment"] -= amount
            total_values["investment"] -= amount
    for owner, values in totals.items():
        values["net_savings"] = summary[owner]["net_saved"]
    for values in totals.values():
        values["net_cash"] = values["income"] - values["real_spend"]
        values["net_cash_class"] = _sign_class(values["net_cash"])
    return totals


def savings_account_ids_from_mapping(
    mapping: dict[str, Any] | None,
) -> set[str]:
    """Return savings account IDs from mapping account_roles.

    Filters account_roles for keys where role starts with ``savings_``.
    Does not validate ownership — use :func:`_validated_savings_account_ids`
    for that.
    """
    if mapping is None:
        return set()
    account_roles = mapping.get("account_roles", {})
    return {
        account_id
        for account_id, account_role in account_roles.items()
        if isinstance(account_role, str) and account_role.startswith("savings_")
    }


def _validated_savings_account_ids(
    records: list[dict[str, Any]],
    detailed_section_mapping: dict[str, dict[str, str]] | None,
) -> set[str]:
    """Return mapped savings account sides after ownership validation."""
    if detailed_section_mapping is None:
        return set()
    account_roles = detailed_section_mapping["account_roles"]
    savings_account_ids = {
        account_id
        for account_id, account_role in account_roles.items()
        if account_role in {"savings_partner_a", "savings_partner_b"}
    }
    for record in records:
        account_role = account_roles.get(record["account_id"])
        if account_role is not None and account_role.startswith("savings_"):
            expected_role = f"savings_{record['owner']}"
            if account_role != expected_role:
                raise AccountingValidationError(
                    "Savings account role does not match the mapped account owner"
                )
    return savings_account_ids


def build_month_contract(
    transactions: list[dict[str, Any]],
    account_owners: dict[str, str] | None = None,
    category_roles: dict[str, str] | None = None,
    savings_account_ids: set[str] | None = None,
    detailed_section_mapping: dict[str, Any] | None = None,
    category_parents: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Build generic paid/received/net report data and reconciliation."""
    normalized = normalize_transactions(transactions, account_owners)
    report_records = [record for record in normalized if not record["is_transfer"]]
    transfer_records = [record for record in normalized if record["is_transfer"]]
    source = sum(record["amount"] for record in normalized)
    report_total = sum(record["amount"] for record in report_records)
    excluded_transfers = sum(record["amount"] for record in transfer_records)
    contract = {
        "normalized_transactions": normalized,
        "categories": _aggregate(report_records),
        "transfers": _aggregate(transfer_records),
        "reconciliation": {
            "source": source,
            "report": report_total,
            "excluded_transfers": excluded_transfers,
            "difference": source - report_total - excluded_transfers,
        },
    }
    mapping = None
    if detailed_section_mapping is not None:
        mapping = _detailed_section_mapping(detailed_section_mapping)
        _validate_detailed_section_categories(normalized, mapping, category_parents)
        contract["detailed_section_mapping"] = mapping
    summary = savings_summary(normalized, mapping, category_roles, category_parents)
    contract["savings_summary"] = summary
    if category_roles is not None:
        contract["kpis"] = _role_kpis(
            normalized, category_roles, category_parents, mapping, summary
        )
    return contract


# --------------------------------------------------------------------------- #
# Detailed section builders (PR2 of monthly-reports-logic-migration).
#
# Produce the `detailed` DTO shapes from models/reports.py (budget_api),
# server-side, as parity ports of client/src/components/reports/
# DetailedSections.tsx. Domain math only — report_builder._detailed()
# composes these into the response.
# --------------------------------------------------------------------------- #

# household_totals composition — canonical server-side constant. The client
# renders this composition from the payload; it keeps no copy of its own.
HOUSEHOLD_COMPOSITION = (
    "home",
    "common",
    "personal_partner_a",
    "personal_partner_b",
    "trips",
)


def _paired_reimbursements(group: dict) -> list[tuple[dict, dict]]:
    """Match +/- amounts within a category, different owners.

    Sort (date, id) then greedy first-match: same owner never pairs, amount
    must be the exact negation, zero amounts never pair.
    """
    records = sorted(
        # str() tie-break: ids are numeric upstream but may be missing (None)
        # — mixing int with "" in the tuple key raises TypeError. Mirrors the
        # frontend comparator (String(id ?? "")); None-only, so id=0 stringifies
        # to "0" like the FE (0 is not nullish there, not falsy-filtered).
        group["records"],
        key=lambda item: (item["date"], "" if item["id"] is None else str(item["id"])),
    )
    pairs = []
    used: set[int] = set()
    for index, record in enumerate(records):
        if index in used:
            continue
        for match_index, candidate in enumerate(records[index + 1 :], index + 1):
            if match_index in used:
                continue
            if (
                record["owner"] != candidate["owner"]
                and record["amount"] == -candidate["amount"]
                and record["amount"] != 0
            ):
                used.update((index, match_index))
                pairs.append((record, candidate))
                break
    return pairs


def _sign_class(value: float) -> str:
    """"pos"/"neg"/"zero" for a money field. Exact-zero compare (-0.0 counts as zero)."""
    if value == 0:
        return "zero"
    return "pos" if value > 0 else "neg"


def _safe_pct(numerator: float, denominator: float) -> float | None:
    """numerator/denominator*100, or None on div-by-zero (never fabricate 0%)."""
    if denominator == 0:
        return None
    return numerator / denominator * 100


def _section_of(record: dict[str, Any], mapping: dict[str, dict[str, str]]) -> str:
    """Raw (unrouted) detailed section for one record's leaf category."""
    category_id = record["category_path"][-1]["id"]
    return mapping["category_sections"].get(category_id, "common")


def _routed_section(record: dict[str, Any], mapping: dict[str, dict[str, str]]) -> str:
    """Detailed section for one record. Transfers route to excluded unless
    their category is home/savings/excluded (mirrors `_routed_detailed_section`
    in accounting_html.py)."""
    section = _section_of(record, mapping)
    if record.get("is_transfer") and section not in {"home", "savings", "excluded"}:
        return "excluded"
    return section


def _records_in_section(
    records: list[dict[str, Any]], section: str, mapping: dict[str, dict[str, str]]
) -> list[dict[str, Any]]:
    return [record for record in records if _routed_section(record, mapping) == section]


def _category_groups(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group records by leaf category — paid/received per owner + records.

    Sorted by total abs(amount) descending (CLI `_legacy_category_groups`).
    """
    groups: dict[str, dict[str, Any]] = {}
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
                "category_id": category["id"],
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


INCOME_SECTIONS = {"income_salary", "income_third_party"}


def has_income_records(
    records: list[dict[str, Any]], mapping: dict[str, dict[str, str]]
) -> bool:
    """True when any record routes to an income section. report_builder uses
    this to emit detailed.income=None on no-income months (old-UI parity: the
    frontend renders 'No income this month.' instead of a zero-filled table)."""
    return any(_routed_section(record, mapping) in INCOME_SECTIONS for record in records)


def detailed_income_section(
    records: list[dict[str, Any]], mapping: dict[str, dict[str, str]]
) -> dict[str, Any]:
    """detailed.income — salary vs third-party split, row/household pct."""
    sources = {
        "salary": {"partner_a": 0.0, "partner_b": 0.0},
        "third_party": {"partner_a": 0.0, "partner_b": 0.0},
    }
    for record in records:
        if _routed_section(record, mapping) not in INCOME_SECTIONS:
            continue
        key = "salary" if _section_of(record, mapping) == "income_salary" else "third_party"
        sources[key][record["owner"]] += record["amount"]

    salary, third_party = sources["salary"], sources["third_party"]
    salary_total = salary["partner_a"] + salary["partner_b"]
    third_party_total = third_party["partner_a"] + third_party["partner_b"]
    total_a = salary["partner_a"] + third_party["partner_a"]
    total_b = salary["partner_b"] + third_party["partner_b"]
    total_income = total_a + total_b

    def row(values: dict[str, float], row_total: float) -> dict[str, Any]:
        return {
            "partner_a": values["partner_a"],
            "partner_a_class": _sign_class(values["partner_a"]),
            "partner_b": values["partner_b"],
            "partner_b_class": _sign_class(values["partner_b"]),
            "total": row_total,
            "total_class": _sign_class(row_total),
            "row_pct_partner_a": _safe_pct(values["partner_a"], row_total),
            "row_pct_partner_b": _safe_pct(values["partner_b"], row_total),
            "household_pct": _safe_pct(row_total, total_income),
        }

    return {
        "salary": row(salary, salary_total),
        "third_party": row(third_party, third_party_total),
        "total_partner_a": total_a,
        "total_partner_a_class": _sign_class(total_a),
        "total_partner_b": total_b,
        "total_partner_b_class": _sign_class(total_b),
        "total_income": total_income,
        "total_income_class": _sign_class(total_income),
    }


def _savings_row(
    to_savings: float, from_savings: float, net_saved: float, income: float
) -> dict[str, Any]:
    return {
        "to_savings": to_savings,
        "to_savings_class": _sign_class(to_savings),
        "from_savings": from_savings,
        "from_savings_class": _sign_class(from_savings),
        "net_saved": net_saved,
        "net_saved_class": _sign_class(net_saved),
        "income": income,
        "income_class": _sign_class(income),
        "rate": _safe_pct(net_saved, income),
    }


def detailed_savings_section(
    records: list[dict[str, Any]],
    savings_summary_dict: dict[str, dict[str, float]] | None,
    mapping: dict[str, dict[str, str]],
) -> dict[str, Any] | None:
    """detailed.savings — None when savings_summary is unavailable."""
    if not savings_summary_dict:
        return None
    incomes = {"partner_a": 0.0, "partner_b": 0.0}
    for record in records:
        if _routed_section(record, mapping) in {"income_salary", "income_third_party"}:
            incomes[record["owner"]] += record["amount"]
    household_income = incomes["partner_a"] + incomes["partner_b"]
    pa = savings_summary_dict["partner_a"]
    pb = savings_summary_dict["partner_b"]
    total = savings_summary_dict["total"]
    return {
        "partner_a": _savings_row(
            pa["to_savings"], pa["from_savings"], pa["net_saved"], incomes["partner_a"]
        ),
        "partner_b": _savings_row(
            pb["to_savings"], pb["from_savings"], pb["net_saved"], incomes["partner_b"]
        ),
        "household": _savings_row(
            total["to_savings"],
            total["from_savings"],
            total["net_saved"],
            household_income,
        ),
    }


def detailed_net_section(
    records: list[dict[str, Any]], section: str, mapping: dict[str, dict[str, str]]
) -> dict[str, Any]:
    """detailed.{home, common, trips} — per-category paid/received/net per
    partner, paired-reimbursement rows rendered explicitly, plus totals."""
    groups = _category_groups(_records_in_section(records, section, mapping))
    rows: list[dict[str, Any]] = []
    paired_rows: list[dict[str, Any]] = []
    total_a = 0.0
    total_b = 0.0
    for group in groups:
        net_a = group["paid"]["partner_a"] - group["received"]["partner_a"]
        net_b = group["paid"]["partner_b"] - group["received"]["partner_b"]
        g_total = net_a + net_b
        total_a += net_a
        total_b += net_b

        pairs = _paired_reimbursements(group)
        group_paired_rows: list[dict[str, Any]] = []
        for first, second in pairs:
            received = first if first["amount"] > 0 else second
            amount = abs(received["amount"])
            pa_val = amount if received["owner"] == "partner_a" else -amount
            pb_val = -pa_val
            paired_row = {
                "category_title": group["title"],
                "partner_a": pa_val,
                "partner_a_class": _sign_class(pa_val),
                "partner_b": pb_val,
                "partner_b_class": _sign_class(pb_val),
                "total": 0.0,
                "total_class": "zero",
            }
            group_paired_rows.append(paired_row)
            paired_rows.append(paired_row)

        # Always emit the category row — fully-paired (zero-net) categories
        # now carry their transparency rows nested in `paired_reimbursements`,
        # so skipping the row would leave the pair rows no anchor. Section-level
        # `paired_reimbursements` stays flattened for backward compatibility.
        rows.append(
            {
                "category_title": group["title"],
                "partner_a_net": net_a,
                "partner_a_net_class": _sign_class(net_a),
                "partner_b_net": net_b,
                "partner_b_net_class": _sign_class(net_b),
                "total": g_total,
                "total_class": _sign_class(g_total),
                "g_share_partner_a": _safe_pct(net_a, g_total),
                "g_share_partner_b": _safe_pct(net_b, g_total),
                "paired_reimbursements": group_paired_rows,
            }
        )

    total = total_a + total_b
    return {
        "rows": rows,
        "paired_reimbursements": paired_rows,
        "total_partner_a": total_a,
        "total_partner_a_class": _sign_class(total_a),
        "total_partner_b": total_b,
        "total_partner_b_class": _sign_class(total_b),
        "total": total,
        "total_class": _sign_class(total),
        "share_partner_a": _safe_pct(total_a, total),
        "share_partner_b": _safe_pct(total_b, total),
    }


# --------------------------------------------------------------------------- #
# Common-economy split (design doc "common economy split" Gate 1, category-
# level selection Gate 2).
#
# One global partner_a/partner_b % pair (sums to 100, validated at the API
# boundary in budget_api.routers.settings) applied to per-category net
# totals across user-chosen CATEGORY IDs (any catalog tree level — a
# selected parent expands to every descendant via
# _resolve_allowed_category_ids). Section is now a DERIVED, per-row display
# grouping, not the selection unit — SPLIT_ELIGIBLE_SECTIONS only matters
# for legacy sections-only config migration/GET-default semantics.
# Pure — no file I/O, no partner-label resolution (config + output stay in
# slot terms; real labels are resolved one layer up by report_builder /
# accounting_html using the same partner-label loader). One documented
# exception: _resolve_allowed_category_ids logs (module-level _logger) on
# the catalog-absent best-effort path (iteration 4, finding 3) — a
# diagnostic side effect only, return value is unaffected.
# --------------------------------------------------------------------------- #

# Display grouping order for split rows/sections — home/common/trips first
# (original Gate 1 candidates), then the two personal sections, then
# anything else (cc_payments, excluded, savings, income_*, ...) alphabetically.
_SPLIT_SECTION_CANONICAL_ORDER = (
    "home",
    "common",
    "trips",
    "personal_partner_a",
    "personal_partner_b",
)


def _split_section_sort_key(section: str) -> tuple[int, Any]:
    if section in _SPLIT_SECTION_CANONICAL_ORDER:
        return (0, _SPLIT_SECTION_CANONICAL_ORDER.index(section))
    return (1, section)


def _ordered_sections(sections: Any) -> list[str]:
    """Distinct section values, canonical order first then alpha for the rest."""
    unique = set(sections)
    canonical = [s for s in _SPLIT_SECTION_CANONICAL_ORDER if s in unique]
    extra = sorted(unique - set(_SPLIT_SECTION_CANONICAL_ORDER))
    return canonical + extra


def _resolve_allowed_category_ids(
    selected_ids: Any,
    category_parents: dict[str, str | None] | None,
) -> set[str]:
    """Expand selected category IDs (any catalog tree level) to the full
    descendant closure — selecting a parent category includes every
    descendant (leaf or intermediate) beneath it.

    Single source of truth for "parent selection includes descendants" —
    every caller (report_builder, accounting_html, mega_builder, the CLI
    build.py path) reuses this instead of independently re-deriving
    inclusion from category_path ancestors. Matching mechanism chosen:
    expand-then-leaf-membership-check, not ancestor-walk-per-record — one
    set built once per report, then a plain `in` check per record.

    category_parents: child_id -> parent_id map covering every catalog
    node (accounting.load_category_parents). None (no catalog on disk) =>
    no expansion possible; selected IDs pass through unchanged (same
    permissive-skip convention as the rest of this module when the catalog
    is unavailable — a leaf-only selection still works correctly).

    category_parents=None + a non-empty selection is undiagnosable here —
    with no catalog we can't tell a parent ID (which needed expansion and
    silently gets zero leaf matches) from a leaf ID (which works fine) — so
    this doesn't raise (best-effort convention: split still computes,
    leaf-only selections still work). It DOES log loudly so a fresh-install
    silent-empty-split isn't invisible in report build logs (iteration 4,
    finding 3).
    """
    selected = set(selected_ids)
    if category_parents is None:
        if selected:
            _logger.warning(
                "split category selection resolved with no category catalog "
                "loaded — %d selected id(s) treated as literal leaf matches, "
                "any that are actually parent-category IDs will match zero "
                "records (best-effort, not raised): %s",
                len(selected),
                sorted(selected),
            )
        return selected
    children: dict[str, list[str]] = {}
    for child_id, parent_id in category_parents.items():
        if parent_id is not None:
            children.setdefault(parent_id, []).append(child_id)
    allowed: set[str] = set()
    stack = list(selected)
    while stack:
        current = stack.pop()
        if current in allowed:
            continue
        allowed.add(current)
        stack.extend(children.get(current, []))
    return allowed


def net_category_totals(
    records: list[dict[str, Any]],
    allowed_category_ids: set[str],
    mapping: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    """Per-category net totals for the common-economy split, filtered by
    leaf category-ID membership (category-level selection — the caller
    expands any selected parent categories via
    _resolve_allowed_category_ids() first and passes the resulting set).

    Each row carries its derived `section`
    (home/common/trips/personal_partner_a/personal_partner_b/... — no
    eligibility restriction any more; SPLIT_ELIGIBLE_SECTIONS is legacy-
    config migration/default semantics only).

    Same transfer-routing rule as _records_in_section/_routed_section: a
    record whose natural (unrouted) section isn't home/savings/excluded is
    dropped when it's a transfer (internal money movement, not real
    partner spend) — keeps split numbers identical to the sibling
    detailed_net_section/detailed_personal_sections DTO blocks for the
    same categories (and to a legacy sections-only config translated to
    its equivalent category-ID set).
    """
    kept = []
    for record in records:
        leaf_id = record["category_path"][-1]["id"]
        if leaf_id not in allowed_category_ids:
            continue
        natural_section = _section_of(record, mapping)
        if record.get("is_transfer") and natural_section not in {
            "home",
            "savings",
            "excluded",
        }:
            continue
        kept.append(record)
    groups = _category_groups(kept)
    rows = []
    for group in groups:
        net_a = group["paid"]["partner_a"] - group["received"]["partner_a"]
        net_b = group["paid"]["partner_b"] - group["received"]["partner_b"]
        section = mapping["category_sections"].get(group["category_id"], "common")
        rows.append(
            {
                "category_id": group["category_id"],
                "category_title": group["title"],
                "section": section,
                "net_partner_a": net_a,
                "net_partner_b": net_b,
            }
        )
    return rows


def compute_split(
    category_nets: list[dict[str, Any]],
    shares: dict[str, float],
) -> dict[str, Any]:
    """Common-economy split — per-category actual/fair/delta + one netted
    settlement across whatever categories the caller already filtered in.

    category_nets: net_category_totals()-shaped rows (category_id,
    category_title, section, net_partner_a, net_partner_b) — already
    filtered to the selected categories (any derived section, no
    eligibility restriction). This function only nets + sorts; it does not
    filter by category or section any more (that's net_category_totals'
    / _split_category_nets' job, category-ID-based, upstream of this call).
    shares: {"partner_a": pct, "partner_b": pct} — trusted to already sum to
    100 (validated at the API boundary); this function does not re-validate.

    Rows carry partner_a's perspective (actual/fair/delta) AND partner_b's
    exact complement (actual_b/fair_b/delta_b) additively — two-partner
    system, shares sum to 100%, so actual_b = total - actual,
    fair_b = total * share_b_fraction (== total - fair), delta_b = -delta.
    a-side fields unchanged for backward compat; b-side added on top.

    Rows are grouped by derived section in canonical display order (home,
    common, trips, personal_partner_a, personal_partner_b, then anything
    else alphabetically) — stable sort, so within each section rows keep
    net_category_totals' original (abs-amount-descending) order.

    Always returns a dict (never None) — an empty `category_nets` (e.g. an
    enabled config with zero categories selected) is a valid, allowed
    state: empty rows, settlement None, sections []. settlement is None
    when the net imbalance is exactly 0 (within tolerance) — never
    fabricate a zero-amount transfer.
    """
    share_a_fraction = shares["partner_a"] / 100.0
    share_b_fraction = shares["partner_b"] / 100.0
    rows: list[dict[str, Any]] = []
    delta_total_a = 0.0
    for category in category_nets:
        net_a = category["net_partner_a"]
        net_b = category["net_partner_b"]
        total = net_a + net_b
        fair_a = total * share_a_fraction
        delta_a = net_a - fair_a
        delta_total_a += delta_a
        # b-side additive — exact complement of a-side (shares sum to 100%).
        actual_b = total - net_a
        fair_b = total * share_b_fraction
        delta_b = actual_b - fair_b
        rows.append(
            {
                "category_id": category["category_id"],
                "label": category["category_title"],
                "section": category["section"],
                "actual": net_a,
                "fair": fair_a,
                "delta": delta_a,
                "actual_b": actual_b,
                "fair_b": fair_b,
                "delta_b": delta_b,
            }
        )
    # Stable sort — groups rows by derived section without disturbing the
    # abs-amount-descending order net_category_totals already produced
    # within each section.
    rows.sort(key=lambda row: _split_section_sort_key(row["section"]))
    settlement = None
    # Tolerance, not `!= 0` — float sums over many non-round-share
    # categories land on ~1e-15 noise for a genuinely balanced split
    # (33.33/66.67 etc). Same tolerance convention as the shares-sum check
    # in normalize_split_config. Row-level actual/fair/delta stay unrounded
    # (display-layer rounding only) — this only guards the settlement gate.
    if abs(delta_total_a) > 1e-6:
        if delta_total_a > 0:
            # partner_a paid more than their fair share overall — partner_b
            # owes them the difference.
            settlement = {
                "from_partner": "partner_b",
                "to_partner": "partner_a",
                "amount": delta_total_a,
            }
        else:
            settlement = {
                "from_partner": "partner_a",
                "to_partner": "partner_b",
                "amount": -delta_total_a,
            }
    return {
        "shares": {"partner_a": shares["partner_a"], "partner_b": shares["partner_b"]},
        "sections": _ordered_sections(row["section"] for row in rows),
        "rows": rows,
        "settlement": settlement,
    }


def migrate_legacy_split_sections(
    sections: list[str], detailed_section_mapping: dict[str, dict[str, str]]
) -> list[str]:
    """Legacy sections-only split_config.json (pre category-picker) ->
    equivalent category-ID list.

    Via detailed_section_mapping.json's LEAF keys, NOT catalog-parent
    expansion — a category is included iff its currently-mapped section
    was in the legacy `sections` list (design doc: "leaf mapping; not
    catalog expansion"). Sorted for deterministic output (dict iteration
    order isn't a stable contract).
    """
    legacy_sections = set(sections)
    category_sections = detailed_section_mapping.get("category_sections", {})
    return sorted(
        category_id
        for category_id, section in category_sections.items()
        if section in legacy_sections
    )


def derive_split_sections(
    categories: list[str],
    detailed_section_mapping: dict[str, dict[str, str]] | None,
    category_parents: dict[str, str | None] | None,
) -> list[str]:
    """Distinct sections the given (unexpanded) selected category IDs
    resolve to, in canonical display order — SplitConfig.sections
    (backward-compat derived field on GET/PUT responses).

    Best-effort / non-raising (unlike _resolve_category_mapping): a
    selected category with no section mapping anywhere in its ancestor
    chain (e.g. a catalog category with zero historical transactions, so
    detailed_section_mapping.json never got an entry for it) is simply
    skipped, not an error — this is a display-only derived field, not the
    strict report-build-time resolution path (net_category_totals, which
    only ever sees leaf IDs that already have real transactions and are
    therefore already validated/resolved).
    """
    if detailed_section_mapping is None:
        return []
    allowed = _resolve_allowed_category_ids(categories, category_parents)
    category_sections = detailed_section_mapping.get("category_sections", {})
    present: set[str] = set()
    for category_id in allowed:
        section = category_sections.get(category_id)
        if section is None and category_parents is not None:
            current = category_parents.get(category_id)
            visited: set[str] = set()
            while current is not None and current not in visited:
                visited.add(current)
                section = category_sections.get(current)
                if section is not None:
                    break
                current = category_parents.get(current)
        if section is not None:
            present.add(section)
    return _ordered_sections(present)


def normalize_split_config(
    raw: Any,
    valid_category_ids: set[str] | None = None,
    detailed_section_mapping: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any] | None:
    """Validate + normalize a parsed split_config.json. None when disabled.

    New schema (category-level split selection): {enabled, shares,
    categories, sections}. `categories` (list of catalog category IDs, any
    tree level) is the source of truth and is what this function returns;
    `sections` is a derived/back-compat field the API writes alongside it
    but is ignored here whenever `categories` is present.

    A config with only `sections` (pre-category-picker file) is
    auto-translated via migrate_legacy_split_sections() — requires
    `detailed_section_mapping`; raises if it's not supplied.

    valid_category_ids: full catalog ID set — an explicit `categories`
    entry not in this set raises (defensive re-check; PUT already
    validates at the API boundary). None skips validation (some
    callers/tests don't have a catalog handy) — legacy-translated
    categories are never re-validated against the catalog (they come from
    the leaf mapping file, already known-valid).

    Writes are already validated at the API boundary
    (budget_api.routers.settings) — this is a defensive re-check for
    report-build time (manual file edits, drift); raises loudly like the
    other private-config loaders in this module, it does not silently
    degrade a malformed file.
    """
    raw = _required_mapping(raw, "split config")
    if set(raw) - {"enabled", "shares", "categories", "sections"}:
        raise AccountingValidationError("Split config has invalid fields")
    enabled = raw.get("enabled")
    if type(enabled) is not bool:
        raise AccountingValidationError("Split config.enabled must be a boolean")
    if not enabled:
        return None
    shares_raw = _required_mapping(raw.get("shares"), "split config.shares")
    if set(shares_raw) != {"partner_a", "partner_b"}:
        raise AccountingValidationError(
            "Split config.shares must have exactly partner_a and partner_b"
        )
    shares: dict[str, float] = {}
    for key, value in shares_raw.items():
        if type(value) not in (int, float) or type(value) is bool:
            raise AccountingValidationError(
                f"Split config.shares.{key} must be numeric"
            )
        # NaN/Inf compare false in every range/sum check below (NaN < 0 is
        # False, NaN > 100 is False, abs(NaN + x - 100) > 1e-6 is False too)
        # — reject non-finite explicitly, before any range/sum math runs.
        if not math.isfinite(value):
            raise AccountingValidationError(
                f"Split config.shares.{key} must be a finite number"
            )
        if value < 0 or value > 100:
            raise AccountingValidationError(
                f"Split config.shares.{key} must be between 0 and 100"
            )
        shares[key] = float(value)
    if abs(shares["partner_a"] + shares["partner_b"] - 100.0) > 1e-6:
        raise AccountingValidationError("Split config.shares must sum to 100")

    if "categories" in raw:
        categories_raw = raw.get("categories")
        if not isinstance(categories_raw, list) or any(
            type(category_id) is not str for category_id in categories_raw
        ):
            raise AccountingValidationError(
                "Split config.categories must be a list of strings"
            )
        if valid_category_ids is not None:
            unknown = sorted(set(categories_raw) - valid_category_ids)
            if unknown:
                raise AccountingValidationError(
                    "Split config.categories has unknown category ID(s): "
                    + ", ".join(unknown)
                )
    elif "sections" in raw:
        sections_raw = raw.get("sections")
        if not isinstance(sections_raw, list) or any(
            type(section) is not str for section in sections_raw
        ):
            raise AccountingValidationError(
                "Split config.sections must be a list of strings"
            )
        unknown_sections = sorted(set(sections_raw) - SPLIT_ELIGIBLE_SECTIONS)
        if unknown_sections:
            raise AccountingValidationError(
                "Split config.sections has unknown section(s): "
                + ", ".join(unknown_sections)
            )
        if detailed_section_mapping is None:
            raise AccountingValidationError(
                "Split config.sections (legacy) requires the detailed "
                "section mapping to translate into category IDs"
            )
        categories_raw = migrate_legacy_split_sections(
            sections_raw, detailed_section_mapping
        )
    else:
        raise AccountingValidationError(
            "Split config must have a categories or sections field"
        )

    seen: set[str] = set()
    categories: list[str] = []
    for category_id in categories_raw:
        if category_id not in seen:
            seen.add(category_id)
            categories.append(category_id)
    return {"shares": shares, "categories": categories}


def load_split_config(
    config_path: str | Path | None = None,
    category_parents: dict[str, str | None] | None = None,
    detailed_section_mapping: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any] | None:
    """Load common-economy split config. None when the file is absent or the
    feature is disabled — additive: no split_config.json means behavior is
    identical to before the feature existed.

    category_parents: full catalog ID->parent map — its keys double as the
    valid-category-ID universe for defensive re-validation. None skips
    validation (catalog file missing).
    detailed_section_mapping: needed only to translate a legacy
    sections-only config file (see normalize_split_config); None + a
    legacy file raises.
    """
    path = Path(config_path) if config_path is not None else PRIVATE_SPLIT_CONFIG
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AccountingValidationError("Split config is unreadable") from error
    valid_category_ids = (
        set(category_parents) if category_parents is not None else None
    )
    return normalize_split_config(raw, valid_category_ids, detailed_section_mapping)


def _net_section_total(groups: list[dict[str, Any]]) -> float:
    return sum(
        group["paid"]["partner_a"]
        + group["paid"]["partner_b"]
        - group["received"]["partner_a"]
        - group["received"]["partner_b"]
        for group in groups
    )


def detailed_personal_sections(
    records: list[dict[str, Any]], mapping: dict[str, dict[str, str]]
) -> dict[str, dict[str, Any]]:
    """detailed.{personal_partner_a, personal_partner_b} — personal_total and
    household_total are shared across both personal sections."""
    grouped = {
        section: _category_groups(_records_in_section(records, section, mapping))
        for section in ("personal_partner_a", "personal_partner_b")
    }
    personal_total = sum(_net_section_total(groups) for groups in grouped.values())
    household_total = sum(
        _net_section_total(_category_groups(_records_in_section(records, section, mapping)))
        for section in HOUSEHOLD_COMPOSITION
    )

    result: dict[str, dict[str, Any]] = {}
    for section in ("personal_partner_a", "personal_partner_b"):
        groups = grouped[section]
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
                {
                    "category_title": group["title"],
                    "paid_partner_a": paid_a,
                    "paid_partner_a_class": _sign_class(paid_a),
                    "paid_partner_b": paid_b,
                    "paid_partner_b_class": _sign_class(paid_b),
                    "total": total,
                    "total_class": _sign_class(total),
                    "pct_personal": _safe_pct(total, personal_total),
                    "pct_household": _safe_pct(total, household_total),
                }
            )
        result[section] = {
            "rows": rows,
            # Per-section subtotal — this section's own row totals. Rendered as
            # the section's "Subtotal" row (legacy HTML line; PR2 DTO exposed
            # only shared personal_total — parity break, fixed PR5).
            "subtotal": subtotal,
            "subtotal_class": _sign_class(subtotal),
            "personal_total": personal_total,
            "personal_total_class": _sign_class(personal_total),
            "household_total": household_total,
            "household_total_class": _sign_class(household_total),
            # Legacy convention (accounting_html._legacy_personal_sections):
            # subtotal row always reads 100% of "its own" personal — not a
            # share of the combined personal_total. None only when this
            # section has no spend at all (div-by-zero-shaped ambiguity).
            "pct_personal": 100.0 if subtotal != 0 else None,
            "pct_household": _safe_pct(subtotal, household_total),
        }
    return result


def detailed_cc_payments_section(
    records: list[dict[str, Any]], mapping: dict[str, dict[str, str]]
) -> dict[str, Any]:
    """detailed.cc_payments — per-owner paid sums (amount < 0 rows only)."""
    payments = [
        record
        for record in _records_in_section(records, "cc_payments", mapping)
        if record["amount"] < 0
    ]
    totals = {"partner_a": 0.0, "partner_b": 0.0}
    for record in payments:
        totals[record["owner"]] += abs(record["amount"])
    household = totals["partner_a"] + totals["partner_b"]
    return {
        "partner_a_paid": totals["partner_a"],
        "partner_a_paid_class": _sign_class(totals["partner_a"]),
        "partner_b_paid": totals["partner_b"],
        "partner_b_paid_class": _sign_class(totals["partner_b"]),
        "household_paid": household,
        "household_paid_class": _sign_class(household),
    }


def detailed_excluded_section(
    records: list[dict[str, Any]], mapping: dict[str, dict[str, str]]
) -> dict[str, Any]:
    """detailed.excluded — per-partner paid sums, no net column."""
    groups = _category_groups(_records_in_section(records, "excluded", mapping))
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
            {
                "category_title": group["title"],
                "paid_partner_a": paid_a,
                "paid_partner_a_class": _sign_class(paid_a),
                "paid_partner_b": paid_b,
                "paid_partner_b_class": _sign_class(paid_b),
                "total": category_total,
                "total_class": _sign_class(category_total),
            }
        )
    return {"rows": rows, "total": total, "total_class": _sign_class(total)}


def detailed_household_totals(
    records: list[dict[str, Any]], mapping: dict[str, dict[str, str]]
) -> dict[str, Any]:
    """detailed.household_totals — composition of
    [home, common, personal_partner_a, personal_partner_b, trips]."""
    partner_a = 0.0
    partner_b = 0.0
    for section in HOUSEHOLD_COMPOSITION:
        for group in _category_groups(_records_in_section(records, section, mapping)):
            partner_a += group["paid"]["partner_a"] - group["received"]["partner_a"]
            partner_b += group["paid"]["partner_b"] - group["received"]["partner_b"]
    total = partner_a + partner_b
    return {
        "partner_a": partner_a,
        "partner_a_class": _sign_class(partner_a),
        "partner_b": partner_b,
        "partner_b_class": _sign_class(partner_b),
        "total": total,
        "total_class": _sign_class(total),
    }
