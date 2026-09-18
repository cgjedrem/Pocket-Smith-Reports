"""Build the MoM (Month-on-Month) report.

Usage:
    python build_mom.py --start YYYY-MM --end YYYY-MM --data-dir DATA_DIR --input-kind {live,synthetic} --output-dir OUTPUT_DIR
"""

import argparse
import sys
from pathlib import Path

# Make repository modules importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "v4_pipeline"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_loader import load  # noqa: E402
from accounting import build_month_contract  # noqa: E402
from accounting_html import render_mom as render_accounting_mom  # noqa: E402
from compare import aggregate_normalized_months  # noqa: E402
from input_contract import InputContractError, resolve_month_input  # noqa: E402


def get_month_path(month: str, data_dir: str, input_kind: str) -> str:
    """Resolve one month from the selected strict source contract."""
    return str(resolve_month_input(month, Path(data_dir), input_kind))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, help="Start month YYYY-MM")
    parser.add_argument("--end", required=True, help="End month YYYY-MM")
    parser.add_argument("--data-dir", required=True, help="Monthly source directory")
    parser.add_argument(
        "--input-kind",
        choices=("live", "synthetic"),
        required=True,
        help="Required monthly source filename contract",
    )
    parser.add_argument("--output-dir", required=True, help="Output dir for PDF/HTML")
    parser.add_argument("--name", default="mom_report", help="Output filename prefix")
    args = parser.parse_args()

    # Generate list of months from start to end inclusive
    months = []
    yr, mo = args.start.split("-")
    yr, mo = int(yr), int(mo)
    end_yr, end_mo = args.end.split("-")
    end_yr, end_mo = int(end_yr), int(end_mo)
    while (yr, mo) <= (end_yr, end_mo):
        months.append(f"{yr:04d}-{mo:02d}")
        mo += 1
        if mo > 12:
            mo = 1
            yr += 1

    print(f"Building MoM for {len(months)} months: {months[0]} → {months[-1]}")

    # Load and normalize each month before aggregation.
    monthly_data = []
    for m in months:
        try:
            path = get_month_path(m, args.data_dir, args.input_kind)
        except InputContractError as error:
            parser.error(str(error))
        txns = load(m, path)
        monthly_data.append({"month": m, "contract": build_month_contract(txns)})
        print(f"  Loaded {m}: {len(txns)} txns")

    # Aggregate
    print(f"Aggregating {len(monthly_data)} months...")
    accounting = aggregate_normalized_months(monthly_data)
    period = (
        f"{accounting['months'][0]} to {accounting['months'][-1]} "
        f"({len(accounting['months'])} months)"
    )
    print(f"  Period: {period}")

    # Render
    print("Rendering HTML...")
    html = render_accounting_mom(accounting, period)
    out_html = Path(args.output_dir) / f"{args.name}.html"
    out_html.write_text(html)
    print(f"  HTML: {out_html} ({len(html):,} chars)")

    # PDF
    print("Rendering PDF...")
    try:
        import weasyprint

        out_pdf = Path(args.output_dir) / f"{args.name}.pdf"
        weasyprint.HTML(string=html).write_pdf(out_pdf)
        print(f"  PDF: {out_pdf} ({out_pdf.stat().st_size:,} bytes)")
    except ImportError:
        print("  weasyprint not available, skipping PDF")
    except Exception as e:
        print(f"  PDF ERROR: {e}")


if __name__ == "__main__":
    main()
