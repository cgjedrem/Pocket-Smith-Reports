"""Regenerate mega reports with the new appendix_transactions field.

Run after backend changes that add new fields to MegaReportResponse.
Usage: python scripts/regen_mega_reports.py [start] [end]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from budget_api.services.mega_builder import (  # noqa: E402
    build_mega_report,
    write_mega_report,
)


def main() -> None:
    pairs: list[tuple[str, str]] = []
    if len(sys.argv) >= 3:
        pairs.append((sys.argv[1], sys.argv[2]))
    else:
        pairs.extend(
            [
                ("2025-08", "2026-07"),
                ("2025-08", "2025-12"),
            ]
        )
    for start, end in pairs:
        print(f"Building {start} -> {end} ...", flush=True)
        report = build_mega_report(start, end)
        write_mega_report(start, end, report)
        n = sum(len(v) for v in (report.get("appendix_transactions") or {}).values())
        print(
            f"  wrote {start}_{end}_mega_report.json (appendix txns: {n})", flush=True
        )


if __name__ == "__main__":
    main()
