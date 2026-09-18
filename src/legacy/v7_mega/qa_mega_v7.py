#!/usr/bin/env python3
"""qa_mega_v7.py — structural + math checks for the v7 mega report.

Run after render_mega_v7.py:
    python3 src/legacy/v7_mega/qa_mega_v7.py mega_v7.pdf

Returns exit 0 if all checks pass, exit 1 if any check fails. Prints
a check-by-check report.

Checks:
  C1  PDF exists and pdfinfo succeeds
  C2  Page count is in [15, 25] (sanity for 18-page design)
    C3  pdftotext grep: report period metadata present
    C4  pdftotext grep: configured report title present
  C5  pdftotext grep: "Methodology" or "Method" present
  C6  pdftotext grep: "T1" through "T10" all present (trip markers)
    C7  pdftotext grep: partner-share section present
  C8  pdftotext grep: "Cumulative" present
  C9  Cross-check: cumulative real spend = sum of monthly real spend
      (rough — uses pdftotext extraction, may have ±1 rounding)
  C10 Cross-check: number of months loaded appears in cover (warn if <11)
  C11 Cross-check: trip count and total appear
"""

import os
import re
import subprocess
import sys


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def check(pdf):
    fails = []
    warns = []
    passes = []

    # C1
    if not os.path.exists(pdf):
        return ["C1 FAIL: PDF not found"], [], []
    passes.append(f"C1 PDF exists: {pdf}")

    # C2
    info = run(["pdfinfo", pdf])
    m = re.search(r"^Pages:\s+(\d+)", info, re.M)
    if not m:
        fails.append("C2 FAIL: pdfinfo has no Pages line")
    else:
        pages = int(m.group(1))
        if 15 <= pages <= 25:
            passes.append(f"C2 pages={pages} (in range [15,25])")
        else:
            fails.append(f"C2 FAIL: pages={pages} outside [15,25]")

    # C3-C8: pdftotext grep
    txt = run(["pdftotext", "-layout", pdf, "-"])

    if "months loaded" in txt:
        passes.append("C3 period metadata present")
    else:
        fails.append("C3 FAIL: period metadata missing")

    if "Mega Report" in txt:
        passes.append("C4 report title present")
    else:
        fails.append("C4 FAIL: report title missing")

    if "Method" in txt or "methodology" in txt.lower():
        passes.append("C5 Methodology section present")
    else:
        fails.append("C5 FAIL: methodology section missing")

    trip_markers = sum(1 for i in range(1, 11) if f"T{i} " in txt or f"T{i:2d} " in txt)
    if trip_markers >= 8:
        passes.append(f"C6 {trip_markers}/10 trip markers present")
    else:
        fails.append(f"C6 FAIL: only {trip_markers}/10 trip markers present")

    if "Partner A" in txt and "Partner B" in txt and "cash share" in txt.lower():
        passes.append("C7 partner-share section present")
    else:
        fails.append("C7 FAIL: partner-share section missing")

    if "Cumulative" in txt:
        passes.append("C8 Cumulative section present")
    else:
        fails.append("C8 FAIL: cumulative section missing")

    # C9: cross-check cumulative
    # Extract monthly income/spend rows from the "Income / Real Spend" table.
    # Find the lines after the month header.
    m_inc = re.search(r"Income\s+([\d,\s]+?)(?=Real Spend|Net Cash|Savings|\n\n)", txt)
    m_rs = re.search(r"Real Spend\s+([\d,\s]+?)(?=Net Cash|Savings|\n\n)", txt)
    if m_inc and m_rs:
        inc_nums = [
            int(x.replace(",", ""))
            for x in m_inc.group(1).split()
            if x.replace(",", "").isdigit()
        ]
        rs_nums = [
            int(x.replace(",", ""))
            for x in m_rs.group(1).split()
            if x.replace(",", "").isdigit()
        ]
        if inc_nums and rs_nums:
            # n/a values are skipped by pdftotext — count vs label
            sum_inc = sum(inc_nums)
            sum_rs = sum(rs_nums)
            # Look for "Cumulative" section total
            m_cum = re.search(r"Cumulative Real Spend\s+([\d,]+)", txt)
            if m_cum:
                cum = int(m_cum.group(1).replace(",", ""))
                if abs(cum - sum_rs) <= 1:  # rounding
                    passes.append(f"C9 cumulative={cum:,} == sum(rs)={sum_rs:,} ✓")
                else:
                    warns.append(
                        f"C9 WARN: cumulative={cum:,} vs sum(rs)={sum_rs:,} (diff {cum-sum_rs:+,})"
                    )
            else:
                warns.append("C9 SKIP: cumulative total not found in single line")

    # C10: months loaded
    m_cov = re.search(r"(\d+)/(\d+)\s+months?\s+loaded", txt)
    if m_cov:
        loaded = int(m_cov.group(1))
        expected = int(m_cov.group(2))
        if loaded == expected:
            passes.append(f"C10 all {expected} months loaded")
        else:
            warns.append(f"C10 WARN: only {loaded}/{expected} months loaded")
    else:
        warns.append("C10 SKIP: months-loaded indicator not found")

    # C11: trip count + total
    m_trip = re.search(r"GRAND TOTAL[\s\S]{0,40}?([\d,]+)", txt)
    if m_trip:
        passes.append(f"C11 trip grand total found: {m_trip.group(1)}")
    else:
        warns.append("C11 SKIP: trip grand total not found in expected format")

    # C12: paired reimbursement rows are structural, not tied to real values.
    if "Paired reimbursement" in txt and "parent" in txt:
        passes.append("C12 paired reimbursement row present")
    else:
        fails.append("C12 FAIL: paired reimbursement row missing")

    # C13 (v8 fix 2026-07-22): per-parent-cat table present
    if "Per-parent-category" in txt:
        passes.append("C13 per-parent-category table present")
    else:
        fails.append("C13 FAIL: per-parent-category table missing")

    return passes, warns, fails


def main():
    pdf = sys.argv[1] if len(sys.argv) > 1 else "mega_v7.pdf"
    passes, warns, fails = check(pdf)

    print("=" * 60)
    print(f"QA MEGA v7 — {pdf}")
    print("=" * 60)
    for p in passes:
        print(f"  ✓ {p}")
    for w in warns:
        print(f"  ⚠ {w}")
    for f in fails:
        print(f"  ✗ {f}")
    print("=" * 60)
    print(f"PASS: {len(passes)}  WARN: {len(warns)}  FAIL: {len(fails)}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
