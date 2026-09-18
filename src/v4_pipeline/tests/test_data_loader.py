"""
Unit tests for data_loader.py

Covers:
  - Month filter (only YYYY-MM txns pass)
  - account.name → __account_name enrichment (so tally can read payer)
  - Empty data, missing keys
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from accounting import build_month_contract
from accounting_html import render
from data_loader import load


def test_load_filters_to_one_month(txns):
    """Only Apr 2026 txns are loaded (no Mar/May leakage)."""
    assert len(txns) == 43, "Expected all synthetic Apr 2026 transactions"
    for t in txns:
        assert t["date"].startswith("2026-04"), f"Leaked txn: {t['date']}"


def test_load_enriches_account_name(txns):
    """Every txn has __account_name set from account.name (else tally payer = Joint)."""
    for t in txns:
        assert "__account_name" in t, f"Missing __account_name on {t.get('payee')}"
        assert t["__account_name"], f"Empty __account_name on {t.get('payee')}"
        assert t["__account_name"] in {
            "Fixture A Checking",
            "Fixture B Checking",
            "Fixture A Savings",
            "Fixture B Savings",
        }


def test_sample_fixture_uses_deterministic_synthetic_ids(txns):
    """Tracked fixture IDs stay in the reserved synthetic range."""
    assert {t["id"] for t in txns} == set(range(100001, 100044))


def test_load_handles_already_enriched():
    """The v4 loader always re-derives __account_name from account.name.

    This is by design — the loader is the single source of truth for
    account attribution. Any pre-existing __account_name is overwritten.
    Documented behavior, not a bug.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(
            {
                "transactions": [
                    {
                        "id": 1,
                        "date": "2026-04-15",
                        "amount": -100,
                        "payee": "test",
                        "account": {"id": 1, "name": "Fixture A Checking"},
                        "__account_name": "OLD VALUE TO BE OVERWRITTEN",
                        "category": {"id": 1, "title": "Groceries"},
                    }
                ]
            },
            f,
        )
        path = f.name
    try:
        txns = load("2026-04", path)
        # Loader re-derives from account.name
        assert txns[0]["__account_name"] == "Fixture A Checking"
    finally:
        Path(path).unlink()


def test_load_excludes_explicit_accounts_and_normalizes_missing_category():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(
            {
                "transactions": [
                    {
                        "id": 1,
                        "date": "2026-04-15",
                        "amount": -100,
                        "account": {"id": "excluded", "name": "Fixture A Checking"},
                    },
                    {
                        "id": 2,
                        "date": "2026-04-16",
                        "amount": -50,
                        "account": {"id": "included", "name": "Fixture B Checking"},
                        "category": None,
                    },
                ]
            },
            f,
        )
        path = f.name
    try:
        txns = load("2026-04", path, {"excluded"})
        assert [transaction["id"] for transaction in txns] == [2]
        assert txns[0]["category"] == {
            "id": "uncategorized",
            "title": "Uncategorized",
        }
    finally:
        Path(path).unlink()


def test_load_excludes_legacy_transaction_account():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(
            {
                "transactions": [
                    {
                        "id": "legacy-excluded",
                        "date": "2026-04-15",
                        "amount": -100,
                        "account": {"name": "Fixture A Checking"},
                        "transaction_account": {
                            "id": "excluded",
                            "name": "Fixture A Checking",
                        },
                        "category": {"id": "common", "title": "Common"},
                    },
                    {
                        "id": "included",
                        "date": "2026-04-16",
                        "amount": -50,
                        "account": {"id": "included", "name": "Fixture B Checking"},
                        "category": {"id": "common", "title": "Common"},
                    },
                ]
            },
            f,
        )
        path = f.name
    try:
        transactions = load("2026-04", path, {"excluded"})
        assert [transaction["id"] for transaction in transactions] == ["included"]
    finally:
        Path(path).unlink()


def test_load_repairs_utf8_text_stored_as_latin1_mojibake():
    mojibake_purchase = "Kj\u00c3\u00b8p"
    purchase = "Kj\u00f8p"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(
            {
                "transactions": [
                    {
                        "id": 1,
                        "date": "2026-04-15",
                        "amount": -100,
                        "payee": mojibake_purchase,
                        "account": {"id": "included", "name": "Fixture A Checking"},
                        "category": {
                            "id": "fund",
                            "title": f"{mojibake_purchase} Kron Fund",
                        },
                    }
                ]
            },
            f,
        )
        path = f.name
    try:
        transaction = load("2026-04", path)[0]
        assert transaction["payee"] == purchase
        assert transaction["category"]["title"] == f"{purchase} Kron Fund"
    finally:
        Path(path).unlink()


def test_load_decodes_utf8_norwegian_characters_without_mojibake(tmp_path):
    text = "Kj\u00f8p p\u00e5 S\u00f8r\u00f8ya \u00e6\u00f8\u00e5"
    category_title = "S\u00e6rlig \u00f8konomi"
    path = tmp_path / "norwegian.json"
    path.write_text(
        json.dumps(
            {
                "transactions": [
                    {
                        "id": 1,
                        "date": "2026-04-15",
                        "amount": -100,
                        "payee": text,
                        "account": {"id": "included", "name": "Fixture A Checking"},
                        "category": {"id": "fund", "title": category_title},
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    transaction = load("2026-04", path)[0]

    assert transaction["payee"] == text
    assert transaction["category"]["title"] == category_title


@pytest.mark.pdf_renderer
def test_utf8_json_loader_to_html_to_real_pdf_chain(tmp_path):
    try:
        import weasyprint
    except OSError as error:
        pytest.skip(f"WeasyPrint native runtime unavailable: {error}")

    title = "Kj\u00f8p p\u00e5 S\u00f8r\u00f8ya \u00e6\u00f8\u00e5"
    data_path = tmp_path / "norwegian.json"
    data_path.write_text(
        json.dumps(
            {
                "transactions": [
                    {
                        "id": 1,
                        "date": "2026-04-15",
                        "amount": -100,
                        "payee": title,
                        "account": {"id": "norwegian-account", "name": "Local"},
                        "category": {"id": "norwegian-category", "title": title},
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    transactions = load("2026-04", data_path)
    html = render(
        build_month_contract(transactions, {"norwegian-account": "partner_a"}),
        "2026-04",
    )
    pdf_path = tmp_path / "norwegian.pdf"
    weasyprint.HTML(string=html).write_pdf(str(pdf_path))

    assert title in html
    assert pdf_path.read_bytes().startswith(b"%PDF-")
    extractor = shutil.which("pdftotext")
    if extractor:
        import subprocess

        extracted = subprocess.run(
            [extractor, str(pdf_path), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
        assert title in extracted.stdout


def test_load_returns_empty_list_for_no_match():
    """Loading a month with no txns returns []."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(
            {
                "transactions": [
                    {
                        "id": 1,
                        "date": "2025-12-31",
                        "amount": 100,
                        "payee": "x",
                        "account": {"name": "x"},
                    },
                    {
                        "id": 2,
                        "date": "2026-02-01",
                        "amount": 100,
                        "payee": "x",
                        "account": {"name": "x"},
                    },
                ]
            },
            f,
        )
        path = f.name
    try:
        txns = load("2026-01", path)
        assert txns == []
    finally:
        Path(path).unlink()


def test_load_missing_file_raises():
    """FileNotFoundError on missing path."""
    with pytest.raises(FileNotFoundError):
        load("2026-04", "/nonexistent/path.json")
