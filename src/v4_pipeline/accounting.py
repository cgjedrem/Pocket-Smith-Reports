"""Normalized generic accounting for supported report paths."""

from __future__ import annotations

import json
import math
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

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
    if set(partners) != set(PARTNERS):
        raise AccountingValidationError(
            "Unified account mapping must define exactly both partners"
        )
    labels = {}
    for owner in PARTNERS:
        partner = _required_mapping(
            partners[owner], f"unified account mapping.partners.{owner}"
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
        # owner/partner_id may be None for joint accounts.
        if owner_value is not None and (
            not isinstance(owner_value, str) or owner_value not in PARTNERS
        ):
            raise AccountingValidationError(
                "Unified account mapping has an invalid owner"
            )
        if type(account["excluded"]) is not bool:
            raise AccountingValidationError(
                "Unified account mapping has an invalid exclusion"
            )
        parsed_accounts[account_id] = {**account, "owner": owner_value}
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
                category_id, roles, category_parents, "Category role mapping"
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
        )


def _resolve_category_mapping(
    category_id: str,
    mapping: dict[str, str],
    category_parents: dict[str, str | None] | None,
    label: str,
) -> str:
    current_id = category_id
    visited: set[str] = set()
    while True:
        mapped = mapping.get(current_id)
        if mapped is not None:
            return mapped
        if category_parents is None:
            raise _unmapped_category_error(label, category_id)
        if current_id in visited:
            raise AccountingValidationError("Category catalog hierarchy has a cycle")
        visited.add(current_id)
        if current_id not in category_parents:
            raise AccountingValidationError(
                f"Category catalog has no category ID {current_id!r}"
            )
        parent_id = category_parents[current_id]
        if parent_id is None:
            raise _unmapped_category_error(label, category_id)
        current_id = parent_id


def _unmapped_category_error(label: str, category_id: str) -> AccountingValidationError:
    if label == "Detailed section mapping":
        return AccountingValidationError(
            f"Detailed section mapping has no section for category ID {category_id!r}"
        )
    return AccountingValidationError("A reportable category has no KPI role")


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
            category_id, roles, category_parents, "Category role mapping"
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
        for first, second in pairs:
            received = first if first["amount"] > 0 else second
            amount = abs(received["amount"])
            pa_val = amount if received["owner"] == "partner_a" else -amount
            pb_val = -pa_val
            paired_rows.append(
                {
                    "category_title": group["title"],
                    "partner_a": pa_val,
                    "partner_a_class": _sign_class(pa_val),
                    "partner_b": pb_val,
                    "partner_b_class": _sign_class(pb_val),
                    "total": 0.0,
                    "total_class": "zero",
                }
            )

        # Skip category row only if fully paired (net 0).
        if not pairs or g_total != 0:
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
