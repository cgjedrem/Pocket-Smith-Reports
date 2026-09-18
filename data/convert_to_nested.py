"""Convert a flat PocketSmith-compatible export to nested transaction data."""

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"{label} file does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} file is not valid JSON: {path}") from error


def _validate_flat_export(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("transactions"), list):
        raise ValueError("input must be an object with a transactions list")

    transactions = data["transactions"]
    for index, transaction in enumerate(transactions):
        if not isinstance(transaction, dict):
            raise ValueError(f"transaction {index} must be an object")
        required = ("id", "date", "amount", "payee", "category")
        missing = [field for field in required if field not in transaction]
        if missing:
            raise ValueError(f"transaction {index} is missing: {', '.join(missing)}")
        if not isinstance(transaction["category"], str):
            raise ValueError(f"transaction {index} category must be a string")
    return transactions


def _load_mapping(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    mapping = _load_json(path, "mapping")
    if not isinstance(mapping, dict):
        raise ValueError("mapping must be a JSON object keyed by category name")
    return mapping


def convert(
    data: dict[str, Any], mapping: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Convert flat transactions with optional caller-owned category metadata."""
    transactions = _validate_flat_export(data)
    mapping = mapping or {}
    nested_transactions = []
    for transaction in transactions:
        category_name = transaction["category"]
        category_metadata = mapping.get(category_name, {})
        if not isinstance(category_metadata, dict):
            raise ValueError(
                f"mapping for category {category_name!r} must be an object"
            )
        nested_transactions.append(
            {
                "id": transaction["id"],
                "date": transaction["date"],
                "amount": transaction["amount"],
                "payee": transaction["payee"],
                "note": transaction.get("note", ""),
                "account": category_metadata.get(
                    "account", {"id": 0, "name": "Unassigned"}
                ),
                "category": {
                    "id": category_metadata.get("category_id", 0),
                    "title": category_name,
                },
            }
        )
    return {
        "fetched_at": data.get("fetched_at"),
        "source": data.get("source"),
        "transactions": nested_transactions,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, required=True, help="Flat JSON export path"
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="Nested JSON output path"
    )
    parser.add_argument(
        "--mapping", type=Path, help="Optional JSON category metadata mapping"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        output = convert(_load_json(args.input, "input"), _load_mapping(args.mapping))
    except ValueError as error:
        print(f"error: {error}")
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Saved {len(output['transactions'])} nested transactions to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
