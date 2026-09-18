"""Mega report PDF — build_context() → assemble_html() → WeasyPrint → bytes.

Reuses mega CLI assemble_html() + sections/css.py CSS. CLI stays standalone.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# mega lives in src/mega — add src/ to sys.path for `import build_mega`.
_SRC_DIR = Path(__file__).resolve().parents[2]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from mega.build_mega import assemble_html, build_context, inclusive_months  # noqa: E402

from budget_api.services import mega_builder, storage


def generate_pdf(start: str, end: str) -> bytes:
    """Build mega report HTML → WeasyPrint → PDF bytes.

    Raises FileNotFoundError if any month missing ps_raw.
    Raises RuntimeError if WeasyPrint fails.
    """
    # Validate all months have ps_raw — raise FileNotFoundError if any missing.
    for month in inclusive_months(start, end):
        if not storage.monthly_ps_raw_path(month).exists():
            raise FileNotFoundError(f"no data for month {month}")

    args = mega_builder._build_namespace(start, end)
    try:
        context = build_context(args)
        html = assemble_html(context, args)
    finally:
        mega_builder._cleanup_namespace(args)

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
