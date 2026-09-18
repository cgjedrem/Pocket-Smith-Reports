"""Mega report pydantic models — MegaReportList, MegaReportRange, MegaReportResponse.

GenerateStatus imported from models.reports (F1.2) — no redefinition.
"""

from __future__ import annotations

from pydantic import BaseModel

from budget_api.models.reports import GenerateStatus  # noqa: F401 — re-exported


class MegaReportRange(BaseModel):
    """One generated mega report range."""

    start: str
    end: str


class MegaReportList(BaseModel):
    """GET /api/mega-reports — sorted newest first."""

    reports: list[MegaReportRange]


class MegaReportResponse(BaseModel):
    """GET /api/mega-reports/{start}/{end} — contract + pre-computed views + stale flag."""

    start: str
    end: str
    stale: bool
    # Same v2 marker as monthly reports; rejected by read path before validate.
    contract_version: int = 2
    calculation_version: int
    txn_counts: dict[str, int]
    months: list[str]
    partner_labels: dict[str, str]
    # Additive label-validation warnings (placeholder degradation etc.).
    # Default [] so reports stored before this field validate unchanged.
    warnings: list[str] = []
    # Core aggregation
    detail_agg: dict
    salary_allocation: dict
    recommendations: dict | None = None
    monthly_kpi_pages: list[dict]
    # Per-month raw txns routed to each detailed section (Income, Savings, etc.).
    # Mirrors the CLI appendix: Date | Payee | Account | Amount per subcat.
    appendix_transactions: dict[str, list[dict]] | None = None
