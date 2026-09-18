"""F2-BE bills dashboard snapshot models — Pydantic shapes for the per-month JSON.

Written by bills_builder during sync. Read by the dashboard endpoint.
Validated before atomic write (sync job) — trust the file on read.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BillsEvent(BaseModel):
    """One event in the bills dashboard snapshot.

    Contract:
    - title = category name (e.g. "Mortgage", "Salary (Fixture B)")
    - account = bank account name (e.g. "FxA Check Handelsbanken")
    """

    id: str
    date: str  # YYYY-MM-DD
    day: int  # 1-31
    title: str
    type: Literal["bill", "buy", "savings", "salary"]
    account: str
    partner: str
    # Additive schema-5 fields. Default "" = pre-field (schema-4) snapshot.
    partner_id: str = ""
    partner_slot: str = ""  # BE-assigned, deterministic sorted-partner_id order
    amount: float
    is_cc_payment: bool = False
    is_matched: bool | None = None


class PartnerBills(BaseModel):
    """Per-partner derived fields for the bills dashboard."""

    partner: str
    # Additive schema-5 fields. Default "" = pre-field (schema-4) snapshot.
    partner_id: str = ""
    partner_slot: str = ""  # deterministic, sorted-partner_id order → "a"/"b"
    salary: float
    bills: float
    # Sum of type="buy" events per partner. Budget = salary - bills - planned_cc_buys.
    # Distinct from real_cc_bill / estimated_cc_bill (realized card spend).
    planned_cc_buys: float = Field(
        default=0.0,
        description=(
            "Sum of buy-bucket events for this partner (planned CC purchases). "
            "Used by the Budget zone; distinct from real_cc_bill / "
            "estimated_cc_bill (realized card spend)."
        ),
    )
    everyday_budget: float | None = Field(
        default=None,
        description=(
            "CC spending allowance for this month, funded by next month's "
            "income: salary(m+1) - bills(m+1) - planned_cc_buys(m+1). "
            "None when m+1 data doesn't exist (last month of sync window) "
            "— FE hides the budget zone on null. Negative stays negative."
        ),
    )
    savings_transfer: float
    savings_planned: float = Field(
        default=0.0,
        description=(
            "Planned savings flow for the month: salary - bills - cc_bill "
            "(past months use real_cc_bill, current/future estimated_cc_bill). "
            "Static, event-derived. Default 0.0 = snapshot written before "
            "the field existed (pre-field file, re-sync to populate)."
        ),
    )
    savings_delta: float | None = Field(
        default=None,
        description=(
            "Actual savings flow: signed net of posted transactions on the "
            "partner's SAVINGS accounts, in-month. Applies to past AND "
            "current months — checking-account activity (salary timing, "
            "CC paydowns, reimbursements) never counts. Future: None — "
            "no reality exists yet. None + warning when chain kwargs are "
            "absent (standalone build). NOTE: the balance back-walk chain "
            "internally uses combined bills+savings deltas — deliberate "
            "split, see designs/f2-bills-derivations.md §13."
        ),
    )
    savings_balance: float
    estimated_cc_bill: float | None
    real_cc_bill: float | None
    real_bills: float | None = Field(
        default=None,
        description=(
            "Sum of posted checking-account debits (excluding cc_payment + "
            "transfer + exclude-role categories). Past months only."
        ),
    )
    cc_usage: float | None = Field(
        default=None,
        description=(
            "Total real posted CC spend, per partner, per month. Posted CC "
            "txns (excl. CC-paydown, transfers, exclude-role). None when no "
            "real CC activity in the window."
        ),
    )
    cc_usage_by_category: dict[str, float] | None = Field(
        default=None,
        description=(
            "Real posted CC spend per category TITLE (same mapping snapshot "
            "events use: title = category title). Same filters/population as "
            "cc_usage — posted CC txns on the partner's non-excluded CC "
            "accounts, excl. CC-paydown, transfers, exclude-role — so values "
            "sum to cc_usage. Past and current months only. None when no "
            "real CC activity in the window (same gate as cc_usage); "
            "pre-field snapshots read None — FE hides the view on null."
        ),
    )
    budget_usage: float
    net: float
    status: Literal["covered", "partial", "shortfall"]
    events: list[BillsEvent]


class SourceCounts(BaseModel):
    """Debug aid — counts from the PS fetch + filter pipeline."""

    ps_events_fetched: int
    ps_transactions_fetched: int
    events_kept_after_filter: int


class BillsSnapshot(BaseModel):
    """Top-level snapshot for one month. Written to bills_dashboard_YYYY-MM.json."""

    schema_version: int = 5
    month: str  # YYYY-MM
    month_label: str
    is_past: bool
    is_current: bool
    is_future: bool
    synced_at: str  # ISO 8601
    bills_count: int
    buys_count: int
    warnings: list[str]
    partners: list[PartnerBills]
    source_counts: SourceCounts
