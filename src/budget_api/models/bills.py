"""F2-BE bills dashboard snapshot models — Pydantic shapes for the per-month JSON.

Written by bills_builder during sync. Read by the dashboard endpoint.
Validated before atomic write (sync job) — trust the file on read.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


def canonical_decimal(value: Decimal) -> str:
    """Serialize a finite Decimal without rounding or exponent notation."""
    if not value.is_finite():
        raise ValueError("decimal must be finite")
    if value == 0:
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _decimal_string(value: str) -> str:
    if not re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value):
        raise ValueError("expected canonical decimal string")
    if canonical_decimal(Decimal(value)) != value:
        raise ValueError("expected canonical decimal string")
    return value


def _nonnegative(value: str) -> str:
    if Decimal(value) < 0:
        raise ValueError("amount must be nonnegative")
    return value


DecimalString = Annotated[str, Field(strict=True), AfterValidator(_decimal_string)]
Amount = Annotated[DecimalString, AfterValidator(_nonnegative)]
CategoryId = Annotated[str, Field(strict=True, pattern=r"^[1-9][0-9]*$")]
ScopeKey = Annotated[str, Field(strict=True, pattern=r"^cc-spend-v1:[0-9a-f]{64}$")]
HistoryReason = Literal[
    "open_month", "future_month", "no_cc_accounts", "missing_source_context", "invalid_source"
]


class CategorySpend(BaseModel):
    model_config = ConfigDict(strict=True)
    title: str
    amount: Amount


class CCSpendHistory(BaseModel):
    """Trusted monthly observation; unknown coverage carries no money."""

    model_config = ConfigDict(strict=True)
    status: Literal["complete", "partial", "unavailable"]
    reason: HistoryReason | None
    scope_key: ScopeKey | None
    categories: dict[CategoryId, CategorySpend] | None
    uncategorized_amount: Amount | None

    @model_validator(mode="after")
    def coverage(self):
        if self.status == "complete":
            valid = (self.reason is None and self.scope_key is not None
                     and self.categories is not None and self.uncategorized_amount is not None)
        elif self.status == "partial":
            valid = (self.reason == "open_month" and self.scope_key is not None
                     and self.categories is None and self.uncategorized_amount is None)
        else:
            valid = (self.reason in {"future_month", "no_cc_accounts",
                                     "missing_source_context", "invalid_source"}
                     and self.scope_key is None and self.categories is None
                     and self.uncategorized_amount is None)
        if not valid:
            raise ValueError("inconsistent history coverage")
        return self


EconomyGroupId = Literal["shared", "personal_partner_a", "personal_partner_b"]


class EconomyCategorySpend(CategorySpend):
    amount: DecimalString


class EconomySpendGroup(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    group_id: EconomyGroupId
    label: str
    partner_id: str | None
    partner_slot: Literal["a", "b", ""]
    categories: dict[CategoryId, EconomyCategorySpend]
    uncategorized_amount: DecimalString

    @model_validator(mode="after")
    def identity(self):
        slot = {"shared": "", "personal_partner_a": "a", "personal_partner_b": "b"}[self.group_id]
        if self.partner_slot != slot or (
            self.group_id == "shared" and self.partner_id is not None
        ) or (slot and (not self.partner_id or not self.partner_id.strip())):
            raise ValueError("invalid economy group identity")
        return self


class EconomySpendHistory(BaseModel):
    """Schema-7 report population evidence, independent of outgoing CC evidence."""

    model_config = ConfigDict(strict=True, extra="forbid")
    status: Literal["complete", "partial", "unavailable"]
    reason: HistoryReason | None
    scope_key: Annotated[str, Field(pattern=r"^economy-spend-v1:[0-9a-f]{64}$")] | None
    groups: list[EconomySpendGroup] | None

    @model_validator(mode="after")
    def coverage(self):
        if self.status == "complete":
            if self.reason is not None or self.scope_key is None or self.groups is None:
                raise ValueError("complete economy history requires evidence")
            if [g.group_id for g in self.groups] != ["shared", "personal_partner_a", "personal_partner_b"]:
                raise ValueError("economy history requires exactly three ordered groups")
            if self.groups[1].partner_id == self.groups[2].partner_id:
                raise ValueError("personal identities must be distinct")
            ids = [cid for g in self.groups for cid in g.categories]
            if len(ids) != len(set(ids)):
                raise ValueError("category IDs must be unique across economy groups")
        elif self.status == "partial":
            if self.reason != "open_month" or self.scope_key is None or self.groups is not None:
                raise ValueError("partial economy history cannot carry amounts")
        elif (self.reason not in {"future_month", "missing_source_context", "invalid_source"}
              or self.scope_key is not None or self.groups is not None):
            raise ValueError("unavailable economy history cannot carry evidence")
        return self


class BillsEvent(BaseModel):
    """One event in the bills dashboard snapshot.

    Contract:
    - title = category name (e.g. "Mortgage", "Salary (Fixture B)")
    - account = bank account name (e.g. "A-Check Nordic Bank")
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
    cc_spend_history: CCSpendHistory | None = None
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
            "split, see docs/design/f2-bills-derivations.md §13."
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

    schema_version: int = 7
    economy_spend_history: EconomySpendHistory | None = None
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
