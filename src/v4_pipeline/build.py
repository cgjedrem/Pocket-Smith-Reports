"""Build a monthly neutral partner report."""

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import uuid
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
SOURCE_DIR = HERE.parent
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from accounting import (
    PRIVATE_DETAILED_SECTION_MAP,
    build_month_contract,
    load_category_parents,
    load_excluded_account_ids,
    load_account_owners,
    load_category_roles,
    load_detailed_section_mapping,
    load_partner_labels,
)
from accounting_html import render as render_html
from data_loader import load
from input_contract import InputContractError, resolve_month_input

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PUBLISHED_OUTPUT_DIR = REPOSITORY_ROOT / "out"
SAFE_OUTPUT_NAME = re.compile(r"[A-Za-z0-9_-]+\Z")


def _output_basename(value: str) -> str:
    if not SAFE_OUTPUT_NAME.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "must be an extensionless basename using letters, digits, _ or -"
        )
    return value


def _write_manifest(path: Path, html_path: Path, pdf_path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "html": html_path.relative_to(PUBLISHED_OUTPUT_DIR).as_posix(),
                "pdf": pdf_path.relative_to(PUBLISHED_OUTPUT_DIR).as_posix(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _cleanup_recovery_directory(path: Path) -> None:
    try:
        shutil.rmtree(path)
    except OSError:
        pass


@contextmanager
def _publisher_lock(output_name: str, timeout_seconds: float = 30.0):
    lock_name = hashlib.sha256(output_name.encode("ascii")).hexdigest() + ".lock"
    lock_dir = PUBLISHED_OUTPUT_DIR / ".v4-locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / lock_name
    deadline = time.monotonic() + timeout_seconds

    with lock_path.open("a+b") as lock_file:
        if lock_file.tell() == 0:
            lock_file.write(b"\0")
            lock_file.flush()
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        f"Timed out waiting {timeout_seconds:g}s for publisher lock "
                        f"for '{output_name}'"
                    )
                time.sleep(0.05)
        try:
            yield
        finally:
            if os.name == "nt":
                import msvcrt

                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _publish_report(html: str, output_name: str) -> tuple[Path, Path]:
    output_name = _output_basename(output_name)
    PUBLISHED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with _publisher_lock(output_name):
        return _publish_report_locked(html, output_name)


def _publish_report_locked(html: str, output_name: str) -> tuple[Path, Path]:
    import weasyprint

    output_name = _output_basename(output_name)
    PUBLISHED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    final_html = PUBLISHED_OUTPUT_DIR / f"{output_name}.html"
    final_pdf = PUBLISHED_OUTPUT_DIR / f"{output_name}.pdf"
    final_manifest = PUBLISHED_OUTPUT_DIR / f"{output_name}.manifest.json"
    release_dir = PUBLISHED_OUTPUT_DIR / ".published" / output_name / uuid.uuid4().hex
    recovery_dir = PUBLISHED_OUTPUT_DIR / f".v4-recovery-{uuid.uuid4().hex}"
    with tempfile.TemporaryDirectory(
        prefix=".v4-stage-", dir=PUBLISHED_OUTPUT_DIR
    ) as stage:
        stage_dir = Path(stage)
        stage_html = stage_dir / final_html.name
        stage_pdf = stage_dir / final_pdf.name
        stage_manifest = stage_dir / final_manifest.name
        stage_html.write_text(html, encoding="utf-8")
        weasyprint.HTML(filename=str(stage_html)).write_pdf(str(stage_pdf))
        if (
            not stage_pdf.is_file()
            or stage_pdf.stat().st_size == 0
            or not stage_pdf.read_bytes().startswith(b"%PDF-")
        ):
            raise RuntimeError("WeasyPrint did not create a valid PDF")

        release_dir.mkdir(parents=True)
        release_html = release_dir / final_html.name
        release_pdf = release_dir / final_pdf.name
        shutil.copy2(stage_html, release_html)
        shutil.copy2(stage_pdf, release_pdf)
        _write_manifest(stage_manifest, release_html, release_pdf)

        recovery_dir.mkdir()
        backup_html = recovery_dir / final_html.name
        backup_pdf = recovery_dir / final_pdf.name
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
            os.replace(stage_manifest, final_manifest)
        except OSError as publish_error:
            rollback_errors = []
            if html_published:
                try:
                    final_html.unlink(missing_ok=True)
                except OSError as rollback_error:
                    rollback_errors.append(rollback_error)
            if pdf_published:
                try:
                    final_pdf.unlink(missing_ok=True)
                except OSError as rollback_error:
                    rollback_errors.append(rollback_error)
            if html_backed_up:
                try:
                    os.replace(backup_html, final_html)
                except OSError as rollback_error:
                    rollback_errors.append(rollback_error)
            if pdf_backed_up:
                try:
                    os.replace(backup_pdf, final_pdf)
                except OSError as rollback_error:
                    rollback_errors.append(rollback_error)
            if rollback_errors:
                raise RuntimeError(
                    "Publish failed and rollback failed; prior report artifacts retained at "
                    f"{recovery_dir}"
                ) from publish_error
            _cleanup_recovery_directory(recovery_dir)
            shutil.rmtree(release_dir, ignore_errors=True)
            raise
        _cleanup_recovery_directory(recovery_dir)
    return final_html, final_pdf


def build_month_html(
    month: str,
    data_path: str | Path,
    *,
    exclude_account_ids: list[str] | None = None,
    category_role_map: str | Path | None = None,
    account_owner_map: str | Path | None = None,
    detailed_section_map: str | Path = PRIVATE_DETAILED_SECTION_MAP,
    partner_a_label: str | None = None,
    partner_b_label: str | None = None,
    partner_label_map: str | Path | None = None,
    theme: str = "minimal",
    savings_account_ids: list[str] | None = None,
    unified_excluded_account_ids: set[str] | None = None,
) -> dict[str, object]:
    """Build a monthly report body and rendering context before publishing."""
    excluded_account_ids = set(exclude_account_ids or [])
    if unified_excluded_account_ids is not None:
        excluded_account_ids.update(unified_excluded_account_ids)
    transactions = load(month, str(data_path), excluded_account_ids)
    category_roles = (
        load_category_roles(category_role_map) if category_role_map else None
    )
    account_owners = load_account_owners(account_owner_map)
    detailed_section_mapping = load_detailed_section_mapping(detailed_section_map)
    # Load category parents from sibling catalog when present — needed for
    # parent-chain walk in _resolve_category_mapping when a leaf category
    # isn't directly mapped in detailed_section_map.
    catalog_path = Path(detailed_section_map).parent / "category_catalog.json"
    category_parents = (
        load_category_parents(catalog_path) if catalog_path.exists() else None
    )
    partner_labels = load_partner_labels(partner_label_map)
    if partner_a_label:
        partner_labels["partner_a"] = partner_a_label
    if partner_b_label:
        partner_labels["partner_b"] = partner_b_label
    contract = build_month_contract(
        transactions,
        account_owners=account_owners,
        category_roles=category_roles,
        savings_account_ids=(set(savings_account_ids) if savings_account_ids else None),
        detailed_section_mapping=detailed_section_mapping,
        category_parents=category_parents,
    )
    html = render_html(contract, month, partner_labels, theme)
    body_start = html.index(">", html.index("<body")) + 1
    body_end = html.rindex("</body>")
    css_start = html.index("<style>") + len("<style>")
    css_end = html.index("</style>", css_start)
    return {
        "body_html": html[body_start:body_end],
        "css": html[css_start:css_end],
        "body_class": f"theme-{theme}",
        "html": html,
        "contract": contract,
        "partner_labels": partner_labels,
        "theme": theme,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True, help="YYYY-MM")
    parser.add_argument(
        "--data-dir", type=Path, required=True, help="Monthly source directory"
    )
    parser.add_argument("--input-kind", choices=("live", "synthetic"), required=True)
    parser.add_argument(
        "--name",
        type=_output_basename,
        default=None,
        help="Extensionless output basename ([A-Za-z0-9_-]+)",
    )
    parser.add_argument(
        "--exclude-account-id",
        action="append",
        default=[],
        help="Ignore this account ID for this local report (repeatable)",
    )
    parser.add_argument(
        "--category-role-map",
        help="JSON map from category ID to income, savings, personal_spend, investment, or exclude",
    )
    parser.add_argument(
        "--account-owner-map",
        help="JSON map from account ID to partner_a or partner_b",
    )
    parser.add_argument(
        "--detailed-section-map",
        default=PRIVATE_DETAILED_SECTION_MAP,
        help="JSON map with category_sections and account_roles keyed by stable IDs",
    )
    parser.add_argument("--partner-a-label", help="Override configured partner A label")
    parser.add_argument("--partner-b-label", help="Override configured partner B label")
    parser.add_argument(
        "--partner-label-map",
        help="JSON map from partner_a and partner_b to report labels",
    )
    parser.add_argument(
        "--theme",
        choices=("minimal", "cyberpunk", "medieval", "oriental"),
        default="minimal",
        help="Visual report theme",
    )
    parser.add_argument(
        "--savings-account-id",
        action="append",
        default=None,
        help="Account ID included in net-savings movement (repeatable)",
    )
    args = parser.parse_args()

    try:
        data_path = resolve_month_input(args.month, args.data_dir, args.input_kind)
        unified_excluded_account_ids = (
            load_excluded_account_ids() if args.input_kind == "live" else set()
        )
    except InputContractError as error:
        parser.error(str(error))

    start = time.time()
    build_result = build_month_html(
        args.month,
        data_path,
        exclude_account_ids=args.exclude_account_id,
        category_role_map=args.category_role_map,
        account_owner_map=args.account_owner_map,
        detailed_section_map=args.detailed_section_map,
        partner_a_label=args.partner_a_label,
        partner_b_label=args.partner_b_label,
        partner_label_map=args.partner_label_map,
        theme=args.theme,
        savings_account_ids=args.savings_account_id,
        unified_excluded_account_ids=unified_excluded_account_ids,
    )
    html = str(build_result["html"])
    output_name = args.name or f"{args.month.replace('-', '')}_partner_report"
    output_html, output_pdf = _publish_report(html, output_name)
    print(f"HTML: {output_html}")
    print(f"PDF: {output_pdf}")
    print(f"Done in {time.time() - start:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
