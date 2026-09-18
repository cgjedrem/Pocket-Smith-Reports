"""Reports router — 5 endpoints: months, get, generate (async), status, pdf."""

from __future__ import annotations

import re
import threading
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import StreamingResponse

from budget_api.models.reports import GenerateStatus, MonthList, ReportResponse
from budget_api.services import report_builder, report_pdf, storage

router = APIRouter()

# Concurrent guard — single-process uvicorn.
_generate_lock = threading.Lock()
# Track in-progress months — prevent duplicate generation.
_generating_months: set[str] = set()

_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def _valid_month(value: str) -> bool:
    """YYYY-MM format + valid month check."""
    if not _MONTH_RE.match(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m")
    except ValueError:
        return False
    return True


def _check_month_or_400(month: str) -> None:
    """Raise 400 if invalid month format."""
    if not _valid_month(month):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid month format",
        )


# --------------------------------------------------------------------------- #
# GET /reports/months — scan ps_raw files, sorted descending.
# --------------------------------------------------------------------------- #


@router.get("/reports/months", response_model=MonthList)
def list_months() -> MonthList:
    """List months with synced data. 200, empty list if none."""
    return MonthList(months=report_builder.list_months())


# --------------------------------------------------------------------------- #
# GET /reports/monthly/{month} — read report JSON + stale check.
# --------------------------------------------------------------------------- #


@router.get("/reports/monthly/{month}", response_model=ReportResponse)
def get_monthly_report(month: str) -> ReportResponse:
    """Get monthly report JSON. 404 if not generated. 400 if invalid month."""
    _check_month_or_400(month)
    try:
        report = report_builder.read_report(month)
    except report_builder.IncompatibleContractError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"report {month} uses an incompatible stored contract — "
                f"regenerate via POST /api/reports/monthly/{month}/generate"
            ),
        ) from exc
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no report generated yet",
        )
    stale = report_builder.check_stale(month, report)
    report["stale"] = stale
    return ReportResponse.model_validate(report)


# --------------------------------------------------------------------------- #
# POST /reports/monthly/{month}/generate — async 202 + concurrent guard.
# --------------------------------------------------------------------------- #


def _run_generate(month: str) -> None:
    """Background task — build report, write JSON + status.

    Preserves started_at set by generate_report — no double-set.
    """
    # Read existing status to preserve original started_at.
    existing = report_builder.read_status(month) or {}
    started_at = existing.get("started_at") or report_builder._now_iso()
    try:
        report = report_builder.build_report(month)
        report_builder.write_report(month, report)
        report_builder.write_status(
            month,
            {
                "status": "success",
                "errors": [],
                "started_at": started_at,
                "completed_at": report_builder._now_iso(),
            },
        )
    except Exception as exc:
        report_builder.write_status(
            month,
            {
                "status": "failed",
                "errors": [str(exc)],
                "started_at": started_at,
                "completed_at": report_builder._now_iso(),
            },
        )
    finally:
        with _generate_lock:
            _generating_months.discard(month)


@router.post(
    "/reports/monthly/{month}/generate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GenerateStatus,
)
def generate_report(month: str, background_tasks: BackgroundTasks) -> GenerateStatus:
    """Start async generation. 202 immediately. Concurrent guard: 202 if running."""
    _check_month_or_400(month)

    # 404 if no ps_raw data for month.
    if not storage.monthly_ps_raw_path(month).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no data for this month",
        )

    with _generate_lock:
        if month in _generating_months:
            # Already generating — return current status.
            existing = report_builder.read_status(month)
            if existing is not None:
                return GenerateStatus.model_validate(existing)
            return GenerateStatus(status="generating", errors=[])

        # Mark generating + write initial status.
        _generating_months.add(month)
        started_at = report_builder._now_iso()
        report_builder.write_status(
            month,
            {
                "status": "generating",
                "errors": [],
                "started_at": started_at,
                "completed_at": None,
            },
        )
        background_tasks.add_task(_run_generate, month)

    return GenerateStatus(status="generating", errors=[], started_at=started_at)


# --------------------------------------------------------------------------- #
# GET /reports/monthly/{month}/status — generation status.
# --------------------------------------------------------------------------- #


@router.get("/reports/monthly/{month}/status", response_model=GenerateStatus)
def get_generate_status(month: str) -> GenerateStatus:
    """Get generation status. 404 if never generated. 400 if invalid month."""
    _check_month_or_400(month)
    status_dict = report_builder.read_status(month)
    if status_dict is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no generation has been run yet",
        )
    return GenerateStatus.model_validate(status_dict)


# --------------------------------------------------------------------------- #
# POST /reports/monthly/{month}/pdf — PDF binary stream.
# --------------------------------------------------------------------------- #


@router.post("/reports/monthly/{month}/pdf")
def export_pdf(month: str) -> StreamingResponse:
    """Generate PDF via WeasyPrint. 200 application/pdf. 404 if no report."""
    _check_month_or_400(month)

    # 404 if no report generated yet — check report JSON exists. Presence
    # only: read_report() would 409 a v1 report, but PDF regen rebuilds from
    # source regardless of stored contract (T061/T062 scope is the GET path).
    if not report_builder.storage.monthly_report_path(month).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no report generated yet",
        )

    try:
        pdf_bytes = report_pdf.generate_pdf(month)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no data for this month",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF generation failed",
        ) from exc

    import io

    filename = f"monthly_report_{month}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
