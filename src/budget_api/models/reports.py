"""Report pydantic models — MonthList, GenerateStatus, ReportResponse.

PR1 of the monthly-reports-logic-migration (see
designs/monthly-reports-logic-migration.md, L1-L5 APPROVED) adds the
`detailed` DTO contract below. Contracts only — no builder logic yet
(PR2). All new fields are optional/default-None so reports written by the
pre-PR1 backend still deserialize unchanged.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# Sign-class enum for every money field's sibling `<field>_class`. Amount sign
# convention is paid-negative verbatim (paid sums negatives, received sums
# positives, net = paid - received) per design doc L4.
SignClass = Literal["pos", "neg", "zero"]


class MonthList(BaseModel):
    """GET /api/reports/months — sorted descending month list."""

    months: list[str]


class GenerateStatus(BaseModel):
    """GET /api/reports/monthly/{month}/status — generation lifecycle."""

    status: Literal["generating", "success", "failed"]
    errors: list[str] = []
    started_at: str | None = None
    completed_at: str | None = None


# --------------------------------------------------------------------------- #
# Detailed section DTOs (PR1 contracts, PR2 populates via report_builder).
# Percentages are 0-100 floats or None — None means the denominator was 0
# (never fabricate a 0% for an undefined ratio).
# --------------------------------------------------------------------------- #


class IncomeRow(BaseModel):
    """One income source row (salary or third-party)."""

    partner_a: float
    partner_a_class: SignClass
    partner_b: float
    partner_b_class: SignClass
    total: float
    total_class: SignClass
    row_pct_partner_a: float | None
    row_pct_partner_b: float | None
    household_pct: float | None


class IncomeSection(BaseModel):
    """detailed.income — salary vs third-party split, per §1 of the report."""

    salary: IncomeRow
    third_party: IncomeRow
    total_partner_a: float
    total_partner_a_class: SignClass
    total_partner_b: float
    total_partner_b_class: SignClass
    total_income: float
    total_income_class: SignClass


class SavingsPartnerRow(BaseModel):
    """Per-partner (or household) savings row.

    to_savings/from_savings come from account-role flows; the category-routed
    "kron_net" leg always adds into to_savings regardless of sign (see
    accounting.savings_summary — documented, not a bug).
    """

    to_savings: float
    to_savings_class: SignClass
    from_savings: float
    from_savings_class: SignClass
    net_saved: float
    net_saved_class: SignClass
    income: float
    income_class: SignClass
    rate: float | None  # net_saved / income * 100; None when income == 0


class SavingsSection(BaseModel):
    """detailed.savings — null when savings_summary is unavailable (existing
    "Savings summary unavailable" frontend fallback is preserved)."""

    partner_a: SavingsPartnerRow
    partner_b: SavingsPartnerRow
    household: SavingsPartnerRow


class PairedReimbursementRow(BaseModel):
    """Explicit paired-reimbursement display row — nets to zero by construction.

    partner_a/partner_b are signed numerics: positive when that partner
    received the reimbursement (from that partner's perspective the money
    moved in), matching the frontend's old "+123.45" / "-123.45" rendering.

    Per-partner fields default to 0/"zero" so stored reports written before
    this shape replaced the old pair_display strings still validate —
    those reports are stale (calculation_version) and regenerate once.
    """

    category_title: str
    partner_a: float = 0.0
    partner_a_class: SignClass = "zero"
    partner_b: float = 0.0
    partner_b_class: SignClass = "zero"
    total: float  # always 0.0
    total_class: SignClass  # always "zero"


class NetCategoryRow(BaseModel):
    """One category row within a net section (home/common/trips)."""

    category_title: str
    partner_a_net: float
    partner_a_net_class: SignClass
    partner_b_net: float
    partner_b_net_class: SignClass
    total: float
    total_class: SignClass
    g_share_partner_a: float | None  # partner_a share of this row's total
    g_share_partner_b: float | None


class NetSection(BaseModel):
    """detailed.{home, common, trips} — per-category paid/received/net per
    partner, paired-reimbursement rows rendered explicitly, plus totals."""

    rows: list[NetCategoryRow]
    paired_reimbursements: list[PairedReimbursementRow]
    total_partner_a: float
    total_partner_a_class: SignClass
    total_partner_b: float
    total_partner_b_class: SignClass
    total: float
    total_class: SignClass
    share_partner_a: float | None
    share_partner_b: float | None


class PersonalCategoryRow(BaseModel):
    """One category row within a personal section."""

    category_title: str
    paid_partner_a: float
    paid_partner_a_class: SignClass
    paid_partner_b: float
    paid_partner_b_class: SignClass
    total: float
    total_class: SignClass
    pct_personal: float | None  # row total share of personal_total
    pct_household: float | None  # row total share of household_total


class PersonalSection(BaseModel):
    """detailed.{personal_partner_a, personal_partner_b} — personal_total and
    household_total are shared across both personal sections (see
    DetailedSections.tsx PersonalSection: personal_total = both personal
    sections combined; household_total = home+common+personal*2+trips)."""

    rows: list[PersonalCategoryRow]
    # PR5 additive — per-section subtotal (sum of this section's own row
    # totals; legacy "Subtotal" row). Default-None so stored reports written
    # before PR5 still validate on GET — frontend falls back to personal_total
    # (same nullable-fallback convention as kpis.net_cash_class, PR4).
    subtotal: float | None = None
    subtotal_class: SignClass | None = None
    personal_total: float
    personal_total_class: SignClass
    household_total: float
    household_total_class: SignClass
    pct_personal: float | None  # subtotal share of personal_total (100 when nonzero)
    pct_household: float | None  # subtotal share of household_total


class CcPaymentsSection(BaseModel):
    """detailed.cc_payments — per-owner paid sums (amount < 0 rows only)."""

    partner_a_paid: float
    partner_a_paid_class: SignClass
    partner_b_paid: float
    partner_b_paid_class: SignClass
    household_paid: float
    household_paid_class: SignClass


class ExcludedCategoryRow(BaseModel):
    """One category row within the excluded section (paid-only, no net)."""

    category_title: str
    paid_partner_a: float
    paid_partner_a_class: SignClass
    paid_partner_b: float
    paid_partner_b_class: SignClass
    total: float
    total_class: SignClass


class ExcludedSection(BaseModel):
    """detailed.excluded — per-partner paid sums, no net column."""

    rows: list[ExcludedCategoryRow]
    total: float
    total_class: SignClass


class HouseholdTotals(BaseModel):
    """detailed.household_totals — composition of
    [home, common, personal_partner_a, personal_partner_b, trips]."""

    partner_a: float
    partner_a_class: SignClass
    partner_b: float
    partner_b_class: SignClass
    total: float
    total_class: SignClass


class DetailedSections(BaseModel):
    """report.detailed — one fully pre-computed object per report section.

    Each section is None when its underlying data is unavailable (existing
    stored-report nullable-semantics rule — never fabricate zeros). Not
    populated until PR2; PR1 only adds the contract.
    """

    income: IncomeSection | None = None
    savings: SavingsSection | None = None
    home: NetSection | None = None
    common: NetSection | None = None
    personal_partner_a: PersonalSection | None = None
    personal_partner_b: PersonalSection | None = None
    trips: NetSection | None = None
    cc_payments: CcPaymentsSection | None = None
    excluded: ExcludedSection | None = None
    household_totals: HouseholdTotals | None = None


class ReportResponse(BaseModel):
    """GET /api/reports/monthly/{month} — contract + pre-computed views + stale flag."""

    month: str
    stale: bool
    txn_count: int
    # Breaking-contract marker; read path rejects absent/!= 2 before this
    # model validates, so the default only matters for additive consumers.
    contract_version: int = 2
    # Raw contract
    # Default [] so reports stored while the PR4 backend dropped this field
    # still validate and can be regenerated from the report view (strict
    # required would 500 on GET before the Regenerate button renders).
    normalized_transactions: list[dict] = []
    categories: list[dict]
    reconciliation: dict
    detailed_section_mapping: dict | None = None
    kpis: dict | None = None
    savings_summary: dict | None = None
    # Pre-computed presentation views
    root_totals: dict
    owner_totals: dict
    partner_panels: dict
    partner_labels: dict
    # Additive label-validation warnings (placeholder degradation etc.).
    # Default [] so reports stored before this field validate unchanged.
    warnings: list[str] = []
    # PR1 additive contract — populated starting PR2. Optional/None so
    # reports written by the pre-PR1 backend still deserialize.
    detailed: DetailedSections | None = None
    personal_share: float | None = None  # personal_spend / total_real_spend * 100
    # Per-partner personal-spend share against the household real_spend
    # denominator — restored per-partner UI parity (old KpiPartnerPanel
    # rendered "personal_spend (X.X%)"). None when kpis are unavailable or
    # the denominator is zero; populated starting PR2.
    personal_share_partner_a: float | None = None
    personal_share_partner_b: float | None = None
    balanced: bool | None = None  # reconciliation.difference == 0
