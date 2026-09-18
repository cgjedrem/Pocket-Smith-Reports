"""Render a validated synthetic MoM report and atomically publish HTML/PDF."""

import argparse
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))
SOURCE_DIR = MODULE_DIR.parent
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))
PIPELINE_DIR = MODULE_DIR.parent / "v4_pipeline"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from accounting import build_month_contract
from accounting_html import render_mom as render_accounting_mom
from data_loader import load
from compare import aggregate_normalized_months
from input_contract import InputContractError, resolve_month_input


def render_mom_html(agg):
    return render_accounting_mom(agg["accounting"], agg["period"])


def _inclusive_months(start: str, end: str) -> list[str]:
    try:
        first = datetime.strptime(start, "%Y-%m")
        last = datetime.strptime(end, "%Y-%m")
    except ValueError as error:
        raise ValueError("--start and --end must use YYYY-MM") from error
    if first > last:
        raise ValueError("--start must be before or equal to --end")

    months = []
    current = first
    while current <= last:
        months.append(current.strftime("%Y-%m"))
        current = datetime(
            current.year + (current.month == 12),
            current.month % 12 + 1,
            1,
        )
    return months


def _month_data_path(month: str, data_dir: Path, input_kind: str) -> Path:
    """Resolve one month from the selected strict source contract."""
    return resolve_month_input(month, data_dir, input_kind)


def _build_aggregate(start: str, end: str, data_dir: Path, input_kind: str) -> dict:
    monthly_data = []
    for month in _inclusive_months(start, end):
        try:
            data_path = _month_data_path(month, data_dir, input_kind)
        except InputContractError as error:
            raise ValueError(str(error)) from error
        try:
            transactions = load(month, str(data_path))
            contract = build_month_contract(transactions)
        except (OSError, ValueError) as error:
            raise ValueError(
                f"Required month {month} is invalid: {data_path}"
            ) from error
        monthly_data.append({"month": month, "contract": contract})

    accounting = aggregate_normalized_months(monthly_data)
    return {
        "accounting": accounting,
        "period": f"{start} to {end} ({len(monthly_data)} months)",
    }


def _publish_report(html: str, output_dir: Path, output_name: str) -> tuple[Path, Path]:
    import weasyprint

    output_dir.mkdir(parents=True, exist_ok=True)
    final_html = output_dir / f"{output_name}.html"
    final_pdf = output_dir / f"{output_name}.pdf"
    with tempfile.TemporaryDirectory(prefix=".mom-stage-", dir=output_dir) as stage:
        stage_dir = Path(stage)
        stage_html = stage_dir / final_html.name
        stage_pdf = stage_dir / final_pdf.name
        stage_html.write_text(html, encoding="utf-8")
        weasyprint.HTML(filename=str(stage_html)).write_pdf(str(stage_pdf))
        if not stage_pdf.is_file() or stage_pdf.stat().st_size == 0:
            raise RuntimeError("WeasyPrint did not create a non-empty PDF")

        backup_html = stage_dir / f"{final_html.name}.previous"
        backup_pdf = stage_dir / f"{final_pdf.name}.previous"
        html_backed_up = False
        pdf_backed_up = False
        html_published = False
        pdf_published = False
        try:
            if final_html.exists():
                os.replace(final_html, backup_html)
                html_backed_up = True
            if final_pdf.exists():
                os.replace(final_pdf, backup_pdf)
                pdf_backed_up = True
            os.replace(stage_html, final_html)
            html_published = True
            os.replace(stage_pdf, final_pdf)
            pdf_published = True
        except OSError:
            if html_published:
                final_html.unlink(missing_ok=True)
            if pdf_published:
                final_pdf.unlink(missing_ok=True)
            if html_backed_up:
                os.replace(backup_html, final_html)
            if pdf_backed_up:
                os.replace(backup_pdf, final_pdf)
            raise
    return final_html, final_pdf


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="First inclusive month (YYYY-MM)")
    ap.add_argument("--end", required=True, help="Last inclusive month (YYYY-MM)")
    ap.add_argument(
        "--data-dir", type=Path, required=True, help="Monthly source directory"
    )
    ap.add_argument("--input-kind", choices=("live", "synthetic"), required=True)
    ap.add_argument(
        "--output-dir", type=Path, required=True, help="Published report directory"
    )
    ap.add_argument("--name", default="mom_report")
    ap.add_argument(
        "--section",
        default="all",
        help="Report to render: all or accounting",
    )
    args = ap.parse_args(argv)

    print(f"Building MoM report {args.start} to {args.end} (section={args.section})...")
    if args.section not in ("all", "accounting"):
        ap.error("Only normalized accounting rendering is supported.")
    agg = _build_aggregate(args.start, args.end, args.data_dir, args.input_kind)
    print(
        f"  {len(agg['accounting']['months'])} months, "
        f"{len(agg['accounting']['categories'])} category nodes"
    )

    html = render_mom_html(agg)
    output_name = f"{args.name}_{args.section}" if args.section != "all" else args.name
    out_html, out_pdf = _publish_report(html, args.output_dir, output_name)
    print(f"  HTML: {out_html} ({len(html):,} chars)")
    print(f"  PDF: {out_pdf} ({out_pdf.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
