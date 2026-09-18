"""Load PocketSmith JSON from an explicit path, filter to a month.

Each txn is a dict with: id, date, amount, account{id,name}, category{id,title}.
We add __partner based on account ownership.
"""

# Synthetic fixture ownership mapping.
PARTNER_BY_ACCOUNT_NAME = {
    "Fixture A Checking": "partner_a",
    "Fixture A Credit": "partner_a",
    "Fixture A Savings": "partner_a",
    "Fixture B Checking": "partner_b",
    "Fixture B Credit": "partner_b",
    "Fixture B Savings": "partner_b",
}


def _repair_mojibake(value):
    if not isinstance(value, str) or not any(marker in value for marker in ("Ã", "Â")):
        return value
    try:
        repaired = value.encode("latin-1").decode("utf-8")
    except UnicodeError:
        return value
    return repaired if "�" not in repaired else value


def _repair_transaction_text(transaction: dict) -> None:
    for field in ("payee", "note"):
        if field in transaction:
            transaction[field] = _repair_mojibake(transaction[field])
    category = transaction.get("category")
    if isinstance(category, dict) and "title" in category:
        category["title"] = _repair_mojibake(category["title"])


def _transaction_account(transaction: dict) -> dict:
    account = transaction.get("account") or transaction.get("transaction_account") or {}
    return account if isinstance(account, dict) else {}


def _transaction_account_id(transaction: dict) -> str:
    for field in ("account", "transaction_account"):
        account = transaction.get(field)
        if isinstance(account, dict) and account.get("id") not in (None, ""):
            return str(account["id"])
    return ""


def load(
    month: str, data_path: str, excluded_account_ids: set[str] | None = None
) -> list[dict]:
    """Load txns from a PocketSmith JSON file, filter to YYYY-MM.

    Adds __partner to each txn. Returns list of dicts.
    """
    import json

    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)

    # Accept both bare list and {"transactions": [...]} dict shapes.
    # sync_runner writes bare list; some tooling wraps in dict. Coerce
    # non-list values (null, str, dict-of-str, etc.) to [] so downstream
    # iteration is safe.
    if isinstance(data, list):
        transactions = data
    elif isinstance(data, dict):
        raw_txns = data.get("transactions")
        transactions = raw_txns if isinstance(raw_txns, list) else []
    else:
        transactions = []

    excluded_account_ids = excluded_account_ids or set()
    out = []
    for t in transactions:
        date = t.get("date", "")
        if not date.startswith(month):
            continue
        acct = _transaction_account(t)
        account_id = _transaction_account_id(t)
        if account_id in excluded_account_ids:
            continue
        name = acct.get("name", "?")
        partner = PARTNER_BY_ACCOUNT_NAME.get(name)
        if not isinstance(t.get("category"), dict):
            t["category"] = {"id": "uncategorized", "title": "Uncategorized"}
            t.pop("category_hierarchy", None)
        _repair_transaction_text(t)
        t["__account_name"] = name
        t["__partner"] = partner or "unknown"
        out.append(t)
    return out
