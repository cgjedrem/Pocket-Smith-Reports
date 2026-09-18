"""Mega reports router — 5 endpoints: list, get, generate (async), status, pdf.

Mirrors reports.py pattern. Range validation: format + start ≤ end + all
months have ps_raw. Concurrent guard: threading.Lock + _generating_ranges set.
"""

from __future__ import annotations

import io
import re
import threading
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import StreamingResponse

from budget_api.models.mega_reports import MegaReportList, MegaReportResponse
from budget_api.models.reports import GenerateStatus
from budget_api.services import mega_builder, mega_pdf, storage

router = APIRouter()

# Concurrent guard — single-process uvicorn.
_generate_lock = threading.Lock()
# Track in-progress ranges — prevent duplicate generation.
_generating_ranges: set[tuple[str, str]] = set()

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


def _check_month_or_400(value: str) -> None:
    """Raise 400 if invalid month format."""
    if not _valid_month(value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid month format",
        )


def _check_range_or_400(start: str, end: str) -> None:
    """Validate both months format, start ≤ end, all months have ps_raw."""
    _check_month_or_400(start)
    _check_month_or_400(end)
    try:
        first = datetime.strptime(start, "%Y-%m")
        last = datetime.strptime(end, "%Y-%m")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid month format",
        )
    if first > last:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start must be before or equal to end",
        )
    # All months in range must have ps_raw.
    try:
        mega_builder._validate_months(start, end)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


# --------------------------------------------------------------------------- #
# GET /mega-reports — scan mega_report files, sorted newest first.
# --------------------------------------------------------------------------- #


@router.get("/mega-reports", response_model=MegaReportList)
def list_mega_reports() -> MegaReportList:
    """List generated mega report ranges. 200, empty list if none."""
    return MegaReportList(reports=mega_builder.list_mega_reports())


# --------------------------------------------------------------------------- #
# GET /mega-reports/{start}/{end} — read report JSON + stale check.
# --------------------------------------------------------------------------- #


@router.get("/mega-reports/{start}/{end}", response_model=MegaReportResponse)
def get_mega_report(start: str, end: str) -> MegaReportResponse:
    """Get mega report JSON. 404 if not generated. 400 if invalid range/months."""
    _check_range_or_400(start, end)
    try:
        report = mega_builder.read_mega_report(start, end)
    except mega_builder.IncompatibleContractError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"mega report {start}..{end} uses an incompatible stored "
                f"contract — regenerate via POST /api/mega-reports/{start}/{end}/generate"
            ),
        ) from exc
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no report generated yet",
        )
    stale = mega_builder.check_mega_stale(start, end, report)
    report["stale"] = stale
    return MegaReportResponse.model_validate(report)


# --------------------------------------------------------------------------- #
# POST /mega-reports/{start}/{end}/generate — async 202 + concurrent guard.
# --------------------------------------------------------------------------- #


def _run_generate(start: str, end: str) -> None:
    """Background task — build report, write JSON + status.

    Preserves started_at set by generate_mega_report — no double-set.
    """
    existing = mega_builder.read_mega_status(start, end) or {}
    started_at = existing.get("started_at") or mega_builder._now_iso()
    try:
        report = mega_builder.build_mega_report(start, end)
        mega_builder.write_mega_report(start, end, report)
        mega_builder.write_mega_status(
            start,
            end,
            {
                "status": "success",
                "errors": [],
                "started_at": started_at,
                "completed_at": mega_builder._now_iso(),
            },
        )
    except Exception as exc:
        mega_builder.write_mega_status(
            start,
            end,
            {
                "status": "failed",
                "errors": [str(exc)],
                "started_at": started_at,
                "completed_at": mega_builder._now_iso(),
            },
        )
    finally:
        with _generate_lock:
            _generating_ranges.discard((start, end))


@router.post(
    "/mega-reports/{start}/{end}/generate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GenerateStatus,
)
def generate_mega_report(
    start: str, end: str, background_tasks: BackgroundTasks
) -> GenerateStatus:
    """Start async generation. 202 immediately. Concurrent guard: 202 if running."""
    _check_range_or_400(start, end)

    key = (start, end)
    with _generate_lock:
        if key in _generating_ranges:
            # Already generating — return current status.
            existing = mega_builder.read_mega_status(start, end)
            if existing is not None:
                return GenerateStatus.model_validate(existing)
            return GenerateStatus(status="generating", errors=[])

        # Mark generating + write initial status.
        _generating_ranges.add(key)
        started_at = mega_builder._now_iso()
        mega_builder.write_mega_status(
            start,
            end,
            {
                "status": "generating",
                "errors": [],
                "started_at": started_at,
                "completed_at": None,
            },
        )
        background_tasks.add_task(_run_generate, start, end)

    return GenerateStatus(status="generating", errors=[], started_at=started_at)


# --------------------------------------------------------------------------- #
# GET /mega-reports/{start}/{end}/status — generation status.
# --------------------------------------------------------------------------- #


@router.get("/mega-reports/{start}/{end}/status", response_model=GenerateStatus)
def get_mega_generate_status(start: str, end: str) -> GenerateStatus:
    """Get generation status. 404 if never generated. 400 if invalid month."""
    _check_month_or_400(start)
    _check_month_or_400(end)
    status_dict = mega_builder.read_mega_status(start, end)
    if status_dict is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no generation has been run yet",
        )
    return GenerateStatus.model_validate(status_dict)


# --------------------------------------------------------------------------- #
# POST /mega-reports/{start}/{end}/pdf — PDF binary stream.
# --------------------------------------------------------------------------- #


@router.post("/mega-reports/{start}/{end}/pdf")
def export_mega_pdf(start: str, end: str) -> StreamingResponse:
    """Generate PDF via WeasyPrint. 200 application/pdf. 404 if no report."""
    _check_range_or_400(start, end)

    # 404 if no report generated yet — check report JSON exists. Presence
    # only (not read_mega_report): PDF regen rebuilds from source regardless
    # of stored contract (T061/T062 scope is the GET path).
    if not mega_builder.storage.mega_report_path(start, end).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no report generated yet",
        )

    try:
        pdf_bytes = mega_pdf.generate_pdf(start, end)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no data for this range",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF generation failed",
        ) from exc

    filename = f"mega_report_{start}_{end}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
