"""Runway request, settings, and response contracts (calculation v2: household net basis)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints, field_validator

AccountId = Annotated[str, StringConstraints(strict=True, pattern=r"^[1-9][0-9]*$")]
# Signed. Net spending can be <= 0 (refunds). Average <= 0 -> nonpositive_burn issue.
Money = Annotated[float, Field(allow_inf_nan=False)]
PositiveRatio = Annotated[float, Field(gt=0, allow_inf_nan=False)]
CurrencyStatus = Literal["verified", "unverified", "conflict"]
Freshness = Literal["fresh", "stale", "unknown"]
SelectionStatus = Literal["unconfigured", "empty", "valid", "invalid"]


class RunwayUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    liquid_account_ids: list[AccountId]

    @field_validator("liquid_account_ids")
    @classmethod
    def unique_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Select each liquid account only once")
        return value


class RunwayConfig(RunwayUpdate):
    schema_version: StrictInt = 1

    @field_validator("schema_version")
    @classmethod
    def supported_version(cls, value: int) -> int:
        if value != 1:
            raise ValueError("Unsupported runway settings version")
        return value


class Issue(BaseModel):
    code: str
    severity: Literal["blocking", "qualification"]
    month: str | None = None
    account_id: str | None = None
    partner_id: str | None = None


class Owner(BaseModel):
    partner_id: str
    partner_slot: Literal["a", "b", ""]
    label: str


class AccountOption(BaseModel):
    id: str
    name: str
    partner_id: str | None
    type: Literal["checking", "savings", "cc", "investment"] | None
    excluded: bool
    selected: bool
    eligible: bool
    issues: list[Issue]


class RunwaySettings(BaseModel):
    schema_version: Literal[1] = 1
    liquid_account_ids: list[str]
    selection_status: SelectionStatus
    owners: list[Owner]
    accounts: list[AccountOption]
    issues: list[Issue]


class SelectedAccount(AccountOption):
    balance: Money | None
    currency_code: str | None
    currency_status: CurrencyStatus
    balance_date: str | None
    balance_date_precision: Literal["date", "datetime", "unknown"]
    balance_freshness: Freshness


class OwnerObservation(BaseModel):
    partner_id: str
    spending: Money | None
    currency_code: str | None
    currency_status: CurrencyStatus


class MonthObservation(BaseModel):
    month: str
    status: Literal["included", "excluded"]
    coverage: Literal["complete", "unverified", "partial", "invalid", "missing"]
    collected_at: str | None = None
    freshness: Freshness = "unknown"
    coverage_start: str | None = None
    coverage_end: str | None = None
    owners: list[OwnerObservation]
    household_spending: Money | None = None
    household_currency_code: str | None = None
    issues: list[Issue]


class Measures(BaseModel):
    selected_account_ids: list[str]
    reserves: Money | None
    average_monthly_spending: Money | None
    runway_months: PositiveRatio | None
    runway_display: str | None
    currency_code: str | None
    reserves_currency_code: str | None
    spending_currency_code: str | None
    currency_status: CurrencyStatus
    status: Literal["available", "qualified", "unavailable"]
    issues: list[Issue]


class OwnerResult(Measures):
    owner: Owner


class SplitShares(BaseModel):
    partner_a: float
    partner_b: float


class RunwayResponse(BaseModel):
    schema_version: Literal[1] = 1
    calculation_version: Literal[2] = 2
    calculated_at: str
    as_of_month: str
    basis: Literal["household_net_spending"] = "household_net_spending"
    # Owner burn: split config shares on split categories, else who paid.
    owner_attribution: Literal["common_economy_split", "payer"] = "payer"
    split_shares: SplitShares | None = None
    candidate_months: list[str] = Field(min_length=3, max_length=3)
    included_months: list[str]
    included_month_count: int = Field(ge=0, le=3)
    selection_status: SelectionStatus | Literal["invalid_settings"]
    selected_account_ids: list[str] | None
    selected_accounts: list[SelectedAccount]
    catalog_collected_at: str | None
    catalog_freshness: Freshness
    observations: list[MonthObservation] = Field(min_length=3, max_length=3)
    owners: list[OwnerResult]
    household: Measures
    issues: list[Issue]
