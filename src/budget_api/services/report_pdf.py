"""Report PDF — invokes build_month_html() → render_html() → WeasyPrint → bytes.

Reads shared SCSS from client/src/styles/report-shared.scss (via accounting_html).
"""

from __future__ import annotations

import logging
import sys
import tempfile
from pathlib import Path

# v4_pipeline lives in src/v4_pipeline — add to sys.path for imports.
_V4_DIR = Path(__file__).resolve().parents[2] / "v4_pipeline"
if str(_V4_DIR) not in sys.path:
    sys.path.insert(0, str(_V4_DIR))

from accounting import (  # noqa: E402
    build_month_contract,
    load_category_parents,
    load_category_roles,
    load_detailed_section_mapping,
)
from accounting_html import render as render_html  # noqa: E402
from data_loader import load  # noqa: E402

from budget_api.services import storage

logger = logging.getLogger(__name__)
from budget_api.services.report_builder import (
    _load_account_owners,
    _load_excluded_account_ids,
    _load_partner_labels,
    _load_transactions,
)


def generate_pdf(month: str) -> bytes:
    """Build monthly report HTML → WeasyPrint → PDF bytes.

    Raises FileNotFoundError if no ps_raw data for month.
    Raises RuntimeError if WeasyPrint fails.
    """
    ps_raw_path = storage.monthly_ps_raw_path(month)
    if not ps_raw_path.exists():
        raise FileNotFoundError(f"no data for month {month}")

    # Load config — bridge budget_api schema → v4_pipeline schema.
    # Paths computed at call time — storage.PRIVATE_DATA_DIR monkeypatched in tests.
    private = storage.PRIVATE_DATA_DIR
    excluded = _load_excluded_account_ids()
    transactions = _load_transactions(month, ps_raw_path, excluded)
    account_owners = _load_account_owners()
    detailed_section_mapping = load_detailed_section_mapping(
        private / "detailed_section_mapping.json"
    )
    partner_labels, label_warnings = _load_partner_labels()
    for warning in label_warnings:
        logger.warning("partner-label validation: %s", warning)

    category_roles = None
    roles_path = private / "category_roles.json"
    if roles_path.exists():
        category_roles = load_category_roles(roles_path)

    # category_parents — from catalog, for role resolution.
    category_parents = None
    catalog_path = private / "category_catalog.json"
    if catalog_path.exists():
        category_parents = load_category_parents(catalog_path)

    # Build contract directly.
    contract = build_month_contract(
        transactions,
        account_owners=account_owners,
        category_roles=category_roles,
        detailed_section_mapping=detailed_section_mapping,
        category_parents=category_parents,
    )

    # Render HTML — accounting_html reads shared SCSS internally.
    html = render_html(contract, month, partner_labels, "minimal")

    # WeasyPrint → PDF bytes.
    import weasyprint

    with tempfile.NamedTemporaryFile(
        suffix=".html", delete=False, mode="w", encoding="utf-8"
    ) as tmp:
        tmp.write(html)
        tmp_path = tmp.name

    try:
        pdf_bytes = weasyprint.HTML(filename=tmp_path).write_pdf()
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if not pdf_bytes or not pdf_bytes.startswith(b"%PDF-"):
        raise RuntimeError("WeasyPrint did not produce a valid PDF")

    return pdf_bytes
