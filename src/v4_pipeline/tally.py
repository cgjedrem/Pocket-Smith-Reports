"""Tally transactions into neutral partner contract sections."""

from collections import defaultdict

PARTNERS = ("partner_a", "partner_b")


def _bucket():
    return {
        "total": 0,
        "partner_a_paid": 0,
        "partner_b_paid": 0,
        "partner_a_received": 0,
        "partner_b_received": 0,
    }


def _section(category: str) -> str | None:
    title = category or ""
    if title in ("Income (Partner A)", "Income (Partner B)", "External Income"):
        return "income"
    if title.startswith("Savings (Partner") or title == "Investment Contribution":
        return "savings"
    if title in ("Housing", "Housing Service", "Protection"):
        return "home"
    if title in (
        "Internal Card Transfer",
        "Internal Account Transfer",
        "Internal Reimbursement",
    ):
        return "excluded"
    if "Travel" in title:
        return "trips"
    if title == "Shared Reimbursement":
        return "common_donations"
    if title in (
        "Shared Essentials",
        "Shared Supplies",
        "Shared Service",
        "Shared Transport",
        "Shared Purchase",
    ):
        return "common"
    if "Partner A" in title:
        return "personal_partner_a"
    if "Partner B" in title:
        return "personal_partner_b"
    if not title:
        return None
    return "common"


def compute(txns: list[dict], rules: dict = None) -> dict:
    """Tally transactions with cash attribution by neutral partner key."""
    result = {
        "income": {
            "partner_a_income": 0,
            "partner_b_income": 0,
            "external": {"partner_a": 0, "partner_b": 0},
        },
        "savings": {
            "partner_a_savings_in": 0,
            "partner_a_savings_out": 0,
            "partner_b_savings_in": 0,
            "partner_b_savings_out": 0,
            "investment_net_partner_a": 0,
            "investment_net_partner_b": 0,
        },
        "home": defaultdict(_bucket),
        "common": defaultdict(_bucket),
        "common_donations": defaultdict(_bucket),
        "personal_partner_a": defaultdict(_bucket),
        "personal_partner_b": defaultdict(_bucket),
        "trips": defaultdict(_bucket),
        "excluded": defaultdict(
            lambda: {
                "total": 0,
                "partner_a_paid": 0,
                "partner_b_paid": 0,
            }
        ),
        "uncategorized": [],
        "drilldown": defaultdict(lambda: defaultdict(list)),
    }

    for transaction in txns:
        amount = transaction.get("amount", 0) or 0
        category = transaction.get("category") or {}
        category_title = (
            category.get("title", "?") if isinstance(category, dict) else "?"
        )
        partner = transaction.get("__partner", "unknown")
        uncategorized = not category_title or category_title == "?"
        section = _section(category_title) if not uncategorized else None
        if section is None:
            section = f"personal_{partner}" if partner in PARTNERS else "common"
            category_title = "Uncategorized"
        absolute_amount = abs(amount)

        result["drilldown"][section][category_title].append(
            {
                "id": transaction.get("id"),
                "date": transaction.get("date"),
                "payee": transaction.get("payee", ""),
                "amount": amount,
                "account": transaction.get("__account_name", ""),
                "note": transaction.get("note", ""),
            }
        )

        if section == "excluded":
            excluded = result["excluded"][category_title]
            excluded["total"] += absolute_amount
            if partner in PARTNERS:
                excluded[f"{partner}_paid"] += absolute_amount
            continue

        if section == "savings":
            if category_title.startswith("Savings (") and partner in PARTNERS:
                direction = "in" if amount < 0 else "out"
                result["savings"][f"{partner}_savings_{direction}"] += absolute_amount
            elif category_title == "Investment Contribution" and partner in PARTNERS:
                result["savings"][f"investment_net_{partner}"] += -amount
            continue

        if section == "income":
            if category_title == "Income (Partner A)":
                result["income"]["partner_a_income"] += amount
            elif category_title == "Income (Partner B)":
                result["income"]["partner_b_income"] += amount
            elif category_title == "External Income" and partner in PARTNERS:
                result["income"]["external"][partner] += amount
            continue

        bucket = result[section][category_title]
        bucket["total"] += absolute_amount
        if partner in PARTNERS:
            movement = "paid" if amount < 0 else "received"
            bucket[f"{partner}_{movement}"] += absolute_amount

    savings = result["savings"]
    savings["net_partner_a"] = (
        savings["partner_a_savings_in"] - savings["partner_a_savings_out"]
    )
    savings["net_partner_b"] = (
        savings["partner_b_savings_in"] - savings["partner_b_savings_out"]
    )
    return {
        "income": result["income"],
        "savings": savings,
        "home": {key: dict(value) for key, value in result["home"].items()},
        "common": {key: dict(value) for key, value in result["common"].items()},
        "personal_partner_a": {
            key: dict(value) for key, value in result["personal_partner_a"].items()
        },
        "personal_partner_b": {
            key: dict(value) for key, value in result["personal_partner_b"].items()
        },
        "trips": {key: dict(value) for key, value in result["trips"].items()},
        "excluded": {key: dict(value) for key, value in result["excluded"].items()},
        "uncategorized": result["uncategorized"],
        "drilldown": {
            section: {key: list(value) for key, value in categories.items()}
            for section, categories in result["drilldown"].items()
        },
    }
