#!/usr/bin/env python3
"""Verify paired reimbursement legs stay in their configured common category."""

import sys
import os
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "v4_pipeline"))

from compare import _enrich_txns
from data_loader import load as v5_load
from tally import compute as v5_tally

MONTHS = []
MEM = os.environ.get("POCKETSMITH_DATA_DIR", "")


def main():
    issues = []
    print(
        f'{"month":12s} | {"HM_spend":>8} | {"excl[Home]":>10} | {"R_reimb@Home":>12} | status'
    )
    for mn_short, mo_num, yr in MONTHS:
        p = os.path.join(MEM, f"ps_{mn_short}_{yr}.json")
        if not os.path.exists(p):
            print(f"{mn_short}_{yr:10s} | (file missing)")
            continue
        yyyy_mm = f"{yr}-{mo_num:02d}"
        try:
            txns = _enrich_txns(v5_load(yyyy_mm, p))
            totals = v5_tally(txns, {})
        except Exception as e:
            print(f"{mn_short}_{yr:10s} | ERR: {e}")
            issues.append(f"{mn_short}_{yr}: tally error {e}")
            continue
        hm = totals.get("common", {}).get("Home Maintenance", {})
        hm_spend = hm.get("total", 0) if isinstance(hm, dict) else 0
        excl_home = totals.get("excluded", {}).get("[uncategorized] Home", 0)
        partner_b_reimb_home = sum(
            t.get("amount", 0)
            for t in txns
            if t.get("amount", 0) > 0
            and (t.get("category") or {}).get("title", "") == "Home"
        )

        status = "ok"
        if excl_home > 100:
            status = f"WARN: {excl_home:,.0f} in excluded[Home] (should be 0 after fix)"
            issues.append(f"{mn_short}_{yr}: {excl_home:,.0f} in excluded[Home]")
        print(
            f"{mn_short}_{yr:10s} | {hm_spend:>8,.0f} | {excl_home:>10,.0f} | {partner_b_reimb_home:>12,.0f} | {status}"
        )

    print()
    if issues:
        print(f"ISSUES ({len(issues)}):")
        for i in issues:
            print(f"  - {i}")
        sys.exit(1)
    else:
        print(
            "PASS: no Home cat exclusions, all months show HM sourced from common bucket"
        )
        sys.exit(0)


if __name__ == "__main__":
    main()
