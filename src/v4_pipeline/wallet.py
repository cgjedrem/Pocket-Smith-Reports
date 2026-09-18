"""Compute legacy neutral per-partner wallet values without pairing."""

PARTNERS = ("partner_a", "partner_b")
COMMON_FAMILY = {
    "Shared Reimbursement",
    "Shared Essentials",
    "Shared Supplies",
    "Shared Service",
    "Shared Transport",
    "Shared Purchase",
}
HOME_FAMILY = {"Housing", "Housing Service", "Protection", "Internal Reimbursement"}


def _partner_key(transaction: dict) -> str:
    partner = transaction.get("__partner")
    if partner in PARTNERS:
        return partner
    account = transaction.get("transaction_account") or transaction.get("account") or {}
    account_name = account.get("name", "") if isinstance(account, dict) else ""
    if account_name.startswith("Fixture A "):
        return "partner_a"
    if account_name.startswith("Fixture B "):
        return "partner_b"
    return "unknown"


def compute(totals: dict, txns: list[dict] = None) -> dict:
    """Compute cash flow summaries without exposing personal partner labels."""
    income = totals["income"]
    savings = totals["savings"]
    paired_reimb_events = []

    partner_a_income = income["partner_a_income"] + income["external"]["partner_a"]
    partner_b_income = income["partner_b_income"] + income["external"]["partner_b"]
    partner_a_savings = savings.get("net_partner_a", 0)
    partner_b_savings = savings.get("net_partner_b", 0)
    sections = ["home", "common", "personal_partner_a", "personal_partner_b", "trips"]
    categories = {}
    partner_a_paid_total = partner_b_paid_total = 0
    partner_a_received_total = partner_b_received_total = 0

    for section in sections:
        for category, info in totals[section].items():
            partner_a_paid = info.get("partner_a_paid", 0)
            partner_b_paid = info.get("partner_b_paid", 0)
            partner_a_received = info.get("partner_a_received", 0)
            partner_b_received = info.get("partner_b_received", 0)
            partner_a_net = partner_a_paid - partner_a_received
            partner_b_net = partner_b_paid - partner_b_received
            effective_total = partner_a_net + partner_b_net
            categories[category] = {
                "section": section,
                "gross_paid": partner_a_paid + partner_b_paid,
                "partner_a_paid": partner_a_paid,
                "partner_b_paid": partner_b_paid,
                "partner_a_received": partner_a_received,
                "partner_b_received": partner_b_received,
                "partner_a_net": partner_a_net,
                "partner_b_net": partner_b_net,
                "effective_total": effective_total,
                "partner_a_eff_pct": (
                    partner_a_net / effective_total if effective_total > 0 else 0
                ),
                "partner_b_eff_pct": (
                    partner_b_net / effective_total if effective_total > 0 else 0
                ),
                "is_reimbursement": False,
            }
            partner_a_paid_total += partner_a_paid
            partner_b_paid_total += partner_b_paid
            partner_a_received_total += partner_a_received
            partner_b_received_total += partner_b_received

    partner_a_wallet = partner_a_paid_total - partner_a_received_total
    partner_b_wallet = partner_b_paid_total - partner_b_received_total
    for info in categories.values():
        info["partner_a_pct_wallet"] = (
            info["partner_a_paid"] / partner_a_wallet if partner_a_wallet > 0 else 0
        )
        info["partner_b_pct_wallet"] = (
            info["partner_b_paid"] / partner_b_wallet if partner_b_wallet > 0 else 0
        )

    return {
        "paired_reimb_events": paired_reimb_events,
        "income": {
            "partner_a": partner_a_income,
            "partner_b": partner_b_income,
            "total": partner_a_income + partner_b_income,
        },
        "savings": {
            "partner_a": partner_a_savings,
            "partner_b": partner_b_savings,
            "total": partner_a_savings + partner_b_savings,
            "investment_net_partner_a": savings.get("investment_net_partner_a", 0),
            "investment_net_partner_b": savings.get("investment_net_partner_b", 0),
        },
        "wallets": {
            "partner_a": partner_a_wallet,
            "partner_b": partner_b_wallet,
            "total": partner_a_wallet + partner_b_wallet,
        },
        "net_cash": {
            "partner_a": partner_a_income - partner_a_wallet,
            "partner_b": partner_b_income - partner_b_wallet,
            "total": (partner_a_income - partner_a_wallet)
            + (partner_b_income - partner_b_wallet),
        },
        "cats": categories,
        "sections": sections,
    }
