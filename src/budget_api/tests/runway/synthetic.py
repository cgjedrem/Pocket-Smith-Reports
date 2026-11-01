"""Reusable synthetic runway world. Caller supplies isolated temporary root."""

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path

NOW = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
A, B, SAVINGS, CARD = "1100001", "1100007", "1100002", "1100003"
MONTHS = ["2026-07", "2026-08", "2026-09"]


def transaction(number=1, account=A, amount=-100, month="2026-07", **extra):
    return {
        "id": 100001 + number,
        "transaction_account": {"id": int(account)},
        "date": f"{month}-15",
        "status": "posted",
        "amount": amount,
        "payee": "Synthetic purchase",
        **extra,
    }


def complete(month, transactions):
    last = 30 if month == "2026-09" else 31
    return {
        "transactions": transactions,
        "provenance": {
            "collected_at": "2026-10-01T00:15:00+00:00",
            "coverage_start": f"{month}-01",
            "coverage_end": f"{month}-{last}",
            "complete": True,
        },
    }


def pocketsmith_transaction(number, account, amount, month, is_transfer=None, category_is_transfer=False):
    """Transaction with the full PocketSmith field set. Every value is synthetic.

    Real rows often carry is_transfer null, so null is the default.
    """
    return {
        "amount": amount,
        "amount_in_base_currency": amount,
        "category": {
            "children": [], "colour": "#000000", "created_at": "2025-01-01T00:00:00Z",
            "id": 2100050, "is_bill": False, "is_transfer": category_is_transfer,
            "parent_id": None, "refund_behaviour": None, "roll_up": False,
            "rollover_type": None, "title": "Synthetic category", "updated_at": "2025-01-01T00:00:00Z",
        },
        "cheque_number": None,
        "closing_balance": 1000.0,
        "created_at": f"{month}-15T08:00:00Z",
        "date": f"{month}-15",
        "id": 100200 + number,
        "is_transfer": is_transfer,
        "labels": [],
        "memo": None,
        "needs_review": False,
        "note": None,
        "original_payee": "SYNTHETIC PAYEE",
        "payee": "Synthetic payee",
        "status": "posted",
        "transaction_account": {
            "account_id": 9100001, "created_at": "2025-01-01T00:00:00Z", "currency_code": "NOK",
            "current_balance": 1000.0, "current_balance_date": "2026-10-14",
            "current_balance_exchange_rate": None, "current_balance_in_base_currency": 1000.0,
            "current_balance_source": "data_feed", "data_feeds_account_id": "synthetic-feed-account",
            "data_feeds_balance_type": "balance", "data_feeds_connection_id": "synthetic-feed-connection",
            "has_safe_balance_adjustment": False, "id": int(account), "include_in_net_worth": True,
            "institution": {"id": 9200001, "title": "Synthetic Bank"}, "is_net_worth": True,
            "latest_feed_name": "Synthetic feed", "name": "Synthetic account", "number": "0000",
            "offline": False, "safe_balance": None, "safe_balance_in_base_currency": None,
            "starting_balance": 0.0, "starting_balance_date": "2025-01-01", "type": "bank",
            "updated_at": "2026-10-14T00:00:00Z",
        },
        "type": "debit",
        "updated_at": f"{month}-16T08:00:00Z",
        "upload_source": "data_feed",
    }


def pocketsmith_month(month, index):
    """Raw month as the sync writes it: bare top-level list, no provenance block.

    Amounts scale with index + 1. Reports net per scale unit: partner A 317.75, partner B 91.00.
    """
    scale = index + 1
    purchases = [  # account, amount, transaction is_transfer, category is_transfer
        (A, "-120.50", None, False),  # counts. null flag
        (A, "-80.25", False, False),  # counts
        (A, "-300.00", True, False),  # transfer at transaction level
        (B, "-45.10", None, False),  # counts
        (B, "-15.90", None, False),  # counts
        (A, "20.00", None, False),  # refund. net reduces A
        (CARD, "-60.00", None, False),  # counts for card owner A
        (B, "-200.00", None, True),  # transfer at category level
        (SAVINGS, "-77.00", None, False),  # savings acct, common category. Reports count it for owner A
        (B, "-30.00", False, False),  # counts
    ]
    return [
        pocketsmith_transaction(index * 100 + number, account, float(Decimal(amount) * scale), month, flag, category_flag)
        for number, (account, amount, flag, category_flag) in enumerate(purchases, 1)
    ]


class World:
    def __init__(self, root: Path):
        self.root = root
        self.data = {
            "account_mappings.json": {
                "partners": {"partner_a": {"label": "Partner A"}, "partner_b": {"label": "Partner B"}},
                "accounts": {
                    account: {"partner_id": owner, "type": kind, "excluded": False}
                    for account, owner, kind in [
                        (A, "partner_a", "checking"), (B, "partner_b", "checking"),
                        (SAVINGS, "partner_a", "savings"), (CARD, "partner_a", "cc"),
                    ]
                },
            },
            "account_catalog.json": {
                "provenance": {"collected_at": "2026-10-15T11:00:00+00:00"},
                "accounts": [
                    {"id": int(account), "name": f"Synthetic account {index}",
                     "current_balance": balance, "currency_code": "NOK",
                     "current_balance_date": "2026-10-15T11:00:00+00:00"}
                    for index, (account, balance) in enumerate([(A, 90000), (B, 30000), (SAVINGS, -2000), (CARD, -500)])
                ],
            },
            "category_catalog.json": {"categories": []},
            # Reports need a section per leaf. No-category rows load as "uncategorized".
            "detailed_section_mapping.json": {
                "category_sections": {"uncategorized": "common", "2100050": "common"},
                "account_roles": {},
            },
            "runway_config.json": {"schema_version": 1, "liquid_account_ids": [A, B]},
        }
        for index, month in enumerate(MONTHS):
            self.data[f"{month}_ps_raw.json"] = complete(month, [
                transaction(index * 10 + 1, A, -(20000 + index * 10000), month),
                transaction(index * 10 + 2, B, -(50000 + index * 10000), month),
            ])

    def write(self):
        for name, data in self.data.items():
            (self.root / name).write_text(json.dumps(data), encoding="utf-8")

    def remove(self, name):
        self.data.pop(name, None)
        (self.root / name).unlink(missing_ok=True)

    def result(self):
        self.write()
        from budget_api.services.runway import calculate_runway
        return calculate_runway(now=NOW).model_dump(mode="json")

    def clone_month(self, source, target):
        self.data[f"{target}_ps_raw.json"] = deepcopy(self.data[f"{source}_ps_raw.json"])

    def use_large_history(self):
        for index in range(16):
            self.data["account_mappings.json"]["accounts"][str(1100100 + index)] = {
                "partner_id": "partner_a", "type": "cc", "excluded": False,
            }
        for index, month in enumerate(MONTHS):
            count = 3334 if index == 0 else 3333
            self.data[f"{month}_ps_raw.json"] = complete(month, [
                transaction(index * 10000 + n, A if n % 2 else B, -10, month)
                for n in range(count)
            ])
