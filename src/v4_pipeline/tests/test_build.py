import sys
from pathlib import Path

import build
from accounting import PRIVATE_CATEGORY_CATALOG, PRIVATE_DETAILED_SECTION_MAP


def test_live_cli_uses_private_category_catalog(monkeypatch, tmp_path: Path):
    data_path = tmp_path / "2026-04_ps_raw.json"
    captured = {}

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build.py",
            "--month",
            "2026-04",
            "--data-dir",
            str(tmp_path),
            "--input-kind",
            "live",
        ],
    )
    monkeypatch.setattr(build, "resolve_month_input", lambda *_args: data_path)
    monkeypatch.setattr(build, "load_excluded_account_ids", lambda: set())
    monkeypatch.setattr(
        build,
        "build_month_html",
        lambda *_args, **kwargs: captured.update(kwargs) or {"html": "<html></html>"},
    )
    monkeypatch.setattr(
        build,
        "_publish_report",
        lambda *_args: (tmp_path / "report.html", tmp_path / "report.pdf"),
    )

    assert build.main() == 0
    # build.py no longer imports/forwards PRIVATE_CATEGORY_CATALOG; it derives
    # the category catalog from the detailed section map's parent directory.
    # The live CLI defaults detailed_section_map to PRIVATE_DETAILED_SECTION_MAP,
    # whose sibling category_catalog.json equals PRIVATE_CATEGORY_CATALOG.
    assert captured["detailed_section_map"] == PRIVATE_DETAILED_SECTION_MAP
    assert (
        PRIVATE_CATEGORY_CATALOG
        == Path(PRIVATE_DETAILED_SECTION_MAP).parent / "category_catalog.json"
    )
