"""Reusable synthetic runway world. Caller supplies isolated temporary root."""

from copy import deepcopy
from datetime import datetime, timezone
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
