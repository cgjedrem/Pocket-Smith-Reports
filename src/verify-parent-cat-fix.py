#!/usr/bin/env python3
"""Verify the parent-category accounting contract using explicit paths."""

import argparse
from pathlib import Path
import subprocess


def check_code_intact(tally_path: Path, trend_path: Path):
    failures = []
    tally = tally_path.read_text(encoding="utf-8")
    trend = trend_path.read_text(encoding="utf-8")
    for symbol in (
        "PARENT_TO_SUB_ALIAS",
        "paired_reimbursement_count",
        "paired_reimbursement_gross",
    ):
        if symbol not in tally:
            failures.append(f"{tally_path.name} missing {symbol}")
    if "def per_parent_category_series" not in trend:
        failures.append(f"{trend_path.name} missing per_parent_category_series()")
    return failures


def check_pdf(pdf: Path):
    if not pdf.exists():
        return [f"PDF not found: {pdf}"]
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        return [f"pdftotext failed: {result.stderr.strip()}"]
    return [
        f"PDF missing {label!r} row"
        for label in ("Per-parent-category", "Paired reimbursement", "Home (parent)")
        if label not in result.stdout
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tally", type=Path, required=True)
    parser.add_argument("--trend", type=Path, required=True)
    parser.add_argument("--pdf", type=Path)
    args = parser.parse_args()
    failures = check_code_intact(args.tally, args.trend)
    if args.pdf:
        failures.extend(check_pdf(args.pdf))
    for failure in failures:
        print(f"FAIL: {failure}")
    if failures:
        return 1
    print("PASS: configured parent-category checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
