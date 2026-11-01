"""Read-only, bounded evaluation of persisted report-economy observations."""

from dataclasses import dataclass

from budget_api.models.bills import EconomySpendHistory, canonical_decimal
from budget_api.models.lifestyle_creep import (
    ReportHistoryIssue, ReportLifestyleCreepResponse, ReportLifestyleGroup,
)
from budget_api.services import lifestyle_creep as evaluator

GROUPS = ("shared", "personal_partner_a", "personal_partner_b")
LABELS = ("Shared economy", "Partner A", "Partner B")


@dataclass(frozen=True)
class CategoryHistory:
    status: str
    scope_key: str
    categories: dict
    uncategorized_amount: str


def read_report_lifestyle_creep(selection: evaluator.Selection) -> ReportLifestyleCreepResponse:
    """No config, report, network, sync, repair, fallback, or write operations."""
    months = list(selection.window_months)
    issues = []
    current = evaluator._current_month()
    unsafe = [m for m in months if m >= current]
    loaded = []
    if unsafe:
        issues = [ReportHistoryIssue(
            month=m, partner_id=None, group_id=None,
            code="partial_month" if m == current else "unavailable_history",
            reason="open_month" if m == current else "future_month",
        ) for m in unsafe]
    else:
        # Parse and validate the entire window before exposing any amounts.
        for month in months:
            record = evaluator._read_envelope(month)
            history = None
            if record is None:
                code, reason = "missing_snapshot", None
            elif record.get("schema_version", 1) < 7:
                if record.get("economy_spend_history") is not None:
                    raise ValueError("economy evidence incompatible with saved schema")
                code, reason = "legacy_history", None
            elif record.get("economy_spend_history") is None:
                code, reason = "legacy_history", None
            else:
                history = EconomySpendHistory.model_validate(record["economy_spend_history"])
                code = {"complete": None, "partial": "partial_month",
                        "unavailable": "unavailable_history"}[history.status]
                reason = history.reason
            loaded.append(history)
            if code:
                issues.append(ReportHistoryIssue(
                    month=month, partner_id=None, group_id=None, code=code, reason=reason,
                ))
    ready = not issues and len(loaded) == len(months)
    if ready:
        identities = {
            tuple((g.group_id, g.partner_id, g.partner_slot) for g in h.groups) for h in loaded
        }
        if len({h.scope_key for h in loaded}) != 1 or len(identities) != 1:
            ready = False
            issues = [ReportHistoryIssue(
                month=m, partner_id=None, group_id=None, code="scope_changed",
            ) for m in months]
    groups = []
    for i, gid in enumerate(GROUPS):
        display = next((h.groups[i] for h in reversed(loaded)
                        if h is not None and h.status == "complete"), None)
        categories, uncategorized = [], []
        if ready:
            observations = [CategoryHistory(
                h.status, h.scope_key, h.groups[i].categories, h.groups[i].uncategorized_amount,
            ) for h in loaded]
            categories, uncategorized = evaluator.evaluate_categories(
                months, observations, selection.threshold, signed=True,
            )
        groups.append(ReportLifestyleGroup(
            group_id=gid, label=display.label if display else LABELS[i],
            partner_id=display.partner_id if display else None,
            partner_slot=("", "a", "b")[i],
            status="ready" if ready else "insufficient_history",
            categories=categories, uncategorized_samples=uncategorized,
        ))
    return ReportLifestyleCreepResponse(
        month=selection.month, reference_start=selection.reference_start,
        reference_end=selection.reference_end, window_months=months,
        evaluation_months=[selection.month], baseline_months=len(months) - 1,
        threshold_percent=canonical_decimal(selection.threshold),
        status="ready" if ready else "insufficient_history", issues=issues, groups=groups,
        history_guidance=(None if ready else
                          "Use completed months. Check report mappings, then explicitly re-sync "
                          "every selected month with one consistent configuration. "
                          "Reading or retrying never creates report-economy history."),
    )
