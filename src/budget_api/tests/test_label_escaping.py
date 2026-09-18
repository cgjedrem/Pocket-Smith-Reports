"""T050 (budget_api side): label warnings surface into the report payload and
the server log; labels with HTML/JS are escaped in the PDF-source HTML.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from budget_api.services import report_builder, report_pdf

XSS_LABEL = "<img src=x onerror=alert(1)>"
XSS_ESCAPED = "&lt;img src=x onerror=alert(1)&gt;"

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _write_report_fixtures(private: Path, labels: dict[str, str]) -> None:
    fixture = json.loads(
        (_REPO_ROOT / "data" / "sample_apr_2026.json").read_text(encoding="utf-8")
    )
    (private / "2026-04_ps_raw.json").write_text(
        json.dumps(fixture), encoding="utf-8"
    )
    mapping = json.loads(
        (_REPO_ROOT / "data" / "sample_apr_2026_detailed_section_mapping.json")
        .read_text(encoding="utf-8")
    )
    (private / "detailed_section_mapping.json").write_text(
        json.dumps(mapping), encoding="utf-8"
    )
    (private / "partner_labels.json").write_text(
        json.dumps(labels), encoding="utf-8"
    )


def test_warnings_field_carries_label_validation(tmp_private_dir: Path):
    """Reserved label → validator warning lands in the payload's warnings."""
    _write_report_fixtures(
        tmp_private_dir, {"partner_a": "Fixture A", "partner_b": "Partner B"}
    )
    report = report_builder.build_report("2026-04")
    assert any("reserved placeholder" in w for w in report["warnings"])


def test_pdf_source_escapes_xss_label_and_logs_warnings(
    tmp_private_dir: Path, monkeypatch: pytest.MonkeyPatch, caplog
):
    _write_report_fixtures(
        tmp_private_dir, {"partner_a": XSS_LABEL, "partner_b": "Partner B"}
    )

    captured: dict[str, str] = {}

    class _FakeHTML:
        def __init__(self, filename: str):
            captured["html"] = Path(filename).read_text(encoding="utf-8")

        def write_pdf(self) -> bytes:
            return b"%PDF-1.4 fake"

    fake_weasyprint = types.SimpleNamespace(HTML=_FakeHTML)
    monkeypatch.setitem(sys.modules, "weasyprint", fake_weasyprint)

    with caplog.at_level("WARNING", logger="budget_api.services.report_pdf"):
        pdf = report_pdf.generate_pdf("2026-04")

    assert pdf.startswith(b"%PDF-")
    assert XSS_ESCAPED in captured["html"]
    assert XSS_LABEL not in captured["html"]
    assert any(
        "partner-label validation" in record.message
        for record in caplog.records
    )
