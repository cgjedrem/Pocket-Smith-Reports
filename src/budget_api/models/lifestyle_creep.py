"""Lifestyle-creep wire models. New decimals remain canonical strings."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from budget_api.models.bills import Amount, CategoryId, DecimalString, EconomyGroupId, HistoryReason


def _month(value: str) -> str:
    date.fromisoformat(value + "-01")
    return value


def _identity(value: str) -> str:
    if not value.strip():
        raise ValueError("identity must be nonempty")
    return value


def _threshold(value: str) -> str:
    if not Decimal(1) <= Decimal(value) <= Decimal(100):
        raise ValueError("threshold must be between 1 and 100")
    return value


Month = Annotated[str, Field(pattern=r"^[0-9]{4}-[0-9]{2}$"), AfterValidator(_month)]
PartnerId = Annotated[str, AfterValidator(_identity)]
Threshold = Annotated[DecimalString, AfterValidator(_threshold)]
PartnerSlot = Literal["a", "b", ""]


class ContractModel(BaseModel):
    model_config = ConfigDict(strict=True)


class HistoryIssue(ContractModel):
    month: Month
    partner_id: PartnerId | None
    code: Literal["missing_snapshot", "legacy_history", "partial_month",
                  "missing_partner_identity", "missing_partner", "unavailable_history",
                  "scope_changed", "no_stable_partners"]
    reason: HistoryReason | None = None


class MonthlyAmount(ContractModel):
    month: Month
    amount: Amount


class Comparison(ContractModel):
    month: Month
    baseline_months: list[Month] = Field(min_length=2, max_length=24)
    baseline_amount: Amount
    spending_amount: Amount
    change_amount: DecimalString
    growth_percent: DecimalString | None


class LifestyleCategory(ContractModel):
    category_id: CategoryId
    category_title: str
    samples: list[MonthlyAmount] = Field(min_length=3, max_length=25)
    comparison: Comparison
    latest_month_over_month_percent: DecimalString | None
    is_above_threshold: bool
    suppression_reason: Literal["zero_baseline", "low_frequency"] | None

    @model_validator(mode="after")
    def comparison_matches_samples(self):
        months = [s.month for s in self.samples]
        if self.comparison.month != months[-1] or self.comparison.baseline_months != months[:-1]:
            raise ValueError("comparison does not match sample window")
        if self.is_above_threshold and self.suppression_reason is not None:
            raise ValueError("suppressed category cannot exceed threshold")
        return self


class LifestylePartner(ContractModel):
    partner_id: PartnerId
    partner_slot: PartnerSlot
    partner: str
    status: Literal["ready", "insufficient_history"]
    categories: list[LifestyleCategory]
    uncategorized_samples: list[MonthlyAmount]

    @model_validator(mode="after")
    def coverage(self):
        if self.status == "ready":
            months = [s.month for s in self.uncategorized_samples]
            if not 3 <= len(months) <= 25:
                raise ValueError("ready partner requires 2 through 24 reference months and a target")
            if any([s.month for s in c.samples] != months for c in self.categories):
                raise ValueError("category and uncategorized samples must match")
        elif self.categories or self.uncategorized_samples:
            raise ValueError("incomplete partner cannot carry money")
        return self


class SignedMonthlyAmount(MonthlyAmount):
    amount: DecimalString


class SignedComparison(Comparison):
    baseline_amount: DecimalString
    spending_amount: DecimalString


class ReportLifestyleCategory(LifestyleCategory):
    samples: list[SignedMonthlyAmount] = Field(min_length=3, max_length=25)
    comparison: SignedComparison
    suppression_reason: Literal["zero_baseline", "negative_baseline", "low_frequency"] | None


class ReportLifestyleGroup(ContractModel):
    group_id: EconomyGroupId
    label: str
    partner_id: PartnerId | None
    partner_slot: PartnerSlot
    status: Literal["ready", "insufficient_history"]
    categories: list[ReportLifestyleCategory]
    uncategorized_samples: list[SignedMonthlyAmount]

    @model_validator(mode="after")
    def coverage(self):
        LifestylePartner.coverage(self)
        expected_slot = {"shared": "", "personal_partner_a": "a", "personal_partner_b": "b"}[self.group_id]
        if self.partner_slot != expected_slot or (self.group_id == "shared" and self.partner_id is not None):
            raise ValueError("invalid report group identity")
        if len({c.category_id for c in self.categories}) != len(self.categories):
            raise ValueError("duplicate group category")
        return self


class ReportHistoryIssue(HistoryIssue):
    group_id: EconomyGroupId | None = None


class LifestyleSelectionResponse(ContractModel):
    month: Month
    reference_start: Month
    reference_end: Month
    window_months: list[Month] = Field(min_length=3, max_length=25)
    evaluation_months: list[Month] = Field(min_length=1, max_length=1)
    baseline_months: int = Field(ge=2, le=24)
    threshold_percent: Threshold
    status: Literal["ready", "partial", "insufficient_history"]
    @model_validator(mode="after")
    def window_and_coverage(self):
        parsed = date.fromisoformat(self.month + "-01")
        index = (parsed.year - 1) * 12 + parsed.month - 1
        first = date.fromisoformat(self.reference_start + "-01")
        last = date.fromisoformat(self.reference_end + "-01")
        start = (first.year - 1) * 12 + first.month - 1
        end = (last.year - 1) * 12 + last.month - 1
        if start < 0 or not 2 <= end - start + 1 <= 24 or end >= index:
            raise ValueError("response has an invalid reference range")
        reference = [f"{i // 12 + 1:04d}-{i % 12 + 1:02d}" for i in range(start, end + 1)]
        expected = reference + [self.month]
        if (self.window_months != expected or self.evaluation_months != [self.month]
                or self.baseline_months != len(reference)):
            raise ValueError("response does not match target and reference months")
        rows = self.partners if hasattr(self, "partners") else self.groups
        for partner in rows:
            if partner.status == "ready":
                if [s.month for s in partner.uncategorized_samples] != expected:
                    raise ValueError("uncategorized samples do not match window")
                if any([s.month for s in c.samples] != expected for c in partner.categories):
                    raise ValueError("category samples do not match window")
        ready_count = sum(p.status == "ready" for p in rows)
        expected_status = ("insufficient_history" if not ready_count else
                           "partial" if self.issues or ready_count != len(rows) else "ready")
        if self.status != expected_status:
            raise ValueError("response status does not match coverage")
        return self


class LifestyleCreepResponse(LifestyleSelectionResponse):
    issues: list[HistoryIssue]
    partners: list[LifestylePartner]


class ReportLifestyleCreepResponse(LifestyleSelectionResponse):
    grouping: Literal["report"] = "report"
    history_guidance: str | None = None
    status: Literal["ready", "insufficient_history"]
    issues: list[ReportHistoryIssue]
    groups: list[ReportLifestyleGroup] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def fixed_groups(self):
        if [g.group_id for g in self.groups] != ["shared", "personal_partner_a", "personal_partner_b"]:
            raise ValueError("report response requires three ordered groups")
        if any(g.status == "ready" and g.group_id != "shared" and not g.partner_id for g in self.groups):
            raise ValueError("ready personal group requires stable identity")
        if (all(g.status == "ready" for g in self.groups)
                and self.groups[1].partner_id == self.groups[2].partner_id):
            raise ValueError("personal group identities must differ")
        ids = [category.category_id for group in self.groups for category in group.categories]
        if len(ids) != len(set(ids)):
            raise ValueError("category identity cannot span report groups")
        return self
