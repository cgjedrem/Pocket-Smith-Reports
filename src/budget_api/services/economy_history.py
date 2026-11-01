"""Sync-only report-population evidence. Never invoked by history GETs."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext
import hashlib
import json
import math

from budget_api.models.bills import EconomySpendHistory, canonical_decimal
from budget_api.services.bills_derivations import MonthAcquisition, exact_decimal_precision
from budget_api.services import report_builder, storage
from v4_pipeline.accounting import detailed_spending_groups
from v4_pipeline.data_loader import prepare_transactions


@dataclass(frozen=True)
class EconomyContext:
    inputs: report_builder.AccountingInputs
    excluded_account_ids: frozenset[str]


def load_economy_context(month: str) -> EconomyContext:
    """Use exactly the report config loader, once per sync, with no report reads."""
    return EconomyContext(
        report_builder.load_accounting_inputs(
            month, private_dir=storage.PRIVATE_DATA_DIR,
            account_mapping_path=storage.ACCOUNT_MAPPING_PATH,
            split_config_path=storage.SPLIT_CONFIG_PATH,
        ),
        frozenset(report_builder.load_excluded_account_ids(storage.ACCOUNT_MAPPING_PATH)),
    )


def build_economy_history(
    month: str, transactions: list[dict], account_mappings: dict,
    acquisition: MonthAcquisition | None, context: EconomyContext | None,
) -> EconomySpendHistory:
    def unavailable(reason):
        return EconomySpendHistory(status="unavailable", reason=reason, scope_key=None, groups=None)

    if acquisition is None:
        return unavailable("missing_source_context")
    try:
        if not isinstance(acquisition, MonthAcquisition) or not acquisition.valid_for(month, transactions):
            return unavailable("invalid_source")
        if context is None:
            return unavailable("missing_source_context")
        slots = report_builder.partner_slot_map(account_mappings)
        if (set(slots.values()) != {"partner_a", "partner_b"} or len(slots) != 2
                or set(account_mappings.get("partners", {})) != set(slots)):
            return unavailable("invalid_source")
        inputs = context.inputs
        if (not inputs.category_parents
                or not inputs.detailed_section_mapping.get("category_sections")):
            return unavailable("missing_source_context")
        accounts = account_mappings.get("accounts")
        if not isinstance(accounts, dict) or not accounts or not inputs.account_owners:
            return unavailable("invalid_source")
        excluded = set()
        for aid, account in accounts.items():
            if (not isinstance(aid, str) or not aid or not isinstance(account, dict)
                    or type(account.get("excluded")) is not bool):
                return unavailable("invalid_source")
            if account["excluded"]:
                excluded.add(aid)
            else:
                owner = slots.get(account.get("partner_id"), account.get("partner_id"))
                if owner not in {"partner_a", "partner_b"} or inputs.account_owners.get(aid) != owner:
                    return unavailable("invalid_source")
        if excluded != set(context.excluded_account_ids):
            return unavailable("invalid_source")
        # Strictly validate the acquired collection before the permissive report
        # loader can filter it. Pending closed-month records cannot prove parity
        # with reports (which do not filter status), so fail closed rather than
        # silently publish a different spending population.
        for txn in transactions:
            if (not isinstance(txn, dict) or not isinstance(txn.get("date"), str)
                    or not txn["date"].startswith(month + "-")
                    or txn.get("status") != "posted"):
                return unavailable("invalid_source")
            date.fromisoformat(txn["date"])
            amount = txn.get("amount")
            if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount):
                return unavailable("invalid_source")
        prepared = prepare_transactions(month, deepcopy(transactions), set(context.excluded_account_ids))
        contract = report_builder.build_contract(prepared, inputs)
        mapping = contract.get("detailed_section_mapping")
        if mapping is None:
            return unavailable("missing_source_context")
        scope_policy = {
            "version": "report-detailed-net-v1",
            "groups": {"shared": ["home", "common"],
                       "personal_partner_a": ["personal_partner_a"],
                       "personal_partner_b": ["personal_partner_b"]},
            "owners": inputs.account_owners,
            "excluded": sorted(context.excluded_account_ids),
            "sections": inputs.detailed_section_mapping,
            "category_roles": inputs.category_roles,
            "parents": inputs.category_parents,
            "slots": slots,
        }
        scope = "economy-spend-v1:" + hashlib.sha256(json.dumps(
            scope_policy, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode()).hexdigest()
        acquired_month = acquisition.started_at.strftime("%Y-%m")
        if month > acquired_month:
            return unavailable("future_month")
        if month == acquired_month:
            return EconomySpendHistory(status="partial", reason="open_month", scope_key=scope, groups=None)
        groups = []
        for gid, category_groups in detailed_spending_groups(
            contract["normalized_transactions"], mapping,
        ).items():
            slot = "" if gid == "shared" else gid[-1]
            pid = next((pid for pid, role in slots.items() if role == "partner_" + slot), None)
            label = ("Shared economy" if pid is None else
                     account_mappings["partners"][pid].get("label") or f"Partner {slot.upper()}")
            categories = {}
            uncategorized = "0"
            for category in category_groups:
                amounts = [Decimal(str(r["amount"])) for r in category["records"]]
                with localcontext() as exact:
                    exact.prec = exact_decimal_precision(amounts)
                    net = canonical_decimal(-sum(amounts, Decimal(0)))
                if category["category_id"] == "uncategorized":
                    uncategorized = net
                else:
                    categories[category["category_id"]] = {"title": category["title"], "amount": net}
            groups.append(dict(group_id=gid, label=label, partner_id=pid, partner_slot=slot,
                               categories=categories, uncategorized_amount=uncategorized))
        return EconomySpendHistory(status="complete", reason=None, scope_key=scope, groups=groups)
    except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
        return unavailable("invalid_source")
