"""Exact lifestyle-creep evaluation and bounded saved-history access."""

from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from datetime import date
from dataclasses import dataclass
import json
import math
import re

from budget_api.models.bills import CCSpendHistory, canonical_decimal
from budget_api.models.lifestyle_creep import (
    Comparison, HistoryIssue, LifestyleCategory, LifestyleCreepResponse, LifestylePartner,
    ReportLifestyleCategory, SignedComparison,
)
from budget_api.services.bills_derivations import exact_decimal_precision
from budget_api.services import storage


def _month_index(month: str) -> int:
    if not isinstance(month, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}", month):
        raise ValueError("invalid month format")
    try:
        parsed = date.fromisoformat(month + "-01")
    except ValueError:
        raise ValueError("invalid calendar month") from None
    return (parsed.year - 1) * 12 + parsed.month - 1


def _month_at(index: int) -> str:
    return f"{index // 12 + 1:04d}-{index % 12 + 1:02d}"


def _current_month() -> str:
    today = date.today()
    return f"{today.year:04d}-{today.month:02d}"


@dataclass(frozen=True)
class Selection:
    month: str
    window_months: tuple[str, ...]
    threshold: Decimal

    @property
    def reference_start(self) -> str:
        return self.window_months[0]

    @property
    def reference_end(self) -> str:
        return self.window_months[-2]


def validate_selection(
    month: str, threshold_percent: str | None = None,
    reference_start: str | None = None, reference_end: str | None = None,
) -> Selection:
    """Validate raw selection completely before resolving any storage paths."""
    index = _month_index(month)
    if index > _month_index(_current_month()):
        raise ValueError("month must not be later than the current month")
    if (reference_start is None) != (reference_end is None):
        raise ValueError("reference_start and reference_end must be supplied together")
    if reference_start is None:
        start, end = index - 3, index - 1
    else:
        start, end = _month_index(reference_start), _month_index(reference_end)
        if not 2 <= end - start + 1 <= 24:
            raise ValueError("reference range must contain 2 through 24 consecutive months")
        if end >= index:
            raise ValueError("reference_end must be earlier than month")
    if start < 0:
        raise ValueError("reference range precedes the earliest representable month")
    raw = "20" if threshold_percent is None else threshold_percent
    if not isinstance(raw, str) or not re.fullmatch(
        r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", raw,
    ):
        raise ValueError("threshold_percent must be a finite decimal between 1 and 100")
    try:
        threshold = Decimal(raw)
        if not threshold.is_finite() or not 1 <= threshold <= 100:
            raise ValueError("threshold_percent must be between 1 and 100")
    except ArithmeticError:
        raise ValueError("threshold_percent must be a finite decimal between 1 and 100") from None
    return Selection(month, tuple(_month_at(i) for i in range(start, end + 1)) + (month,), threshold)


def evaluate_categories(
    months: list[str], histories: list, threshold: Decimal, *, signed: bool = False,
) -> tuple[list, list]:
    """Shared exact comparison math for outgoing CC and signed report evidence."""
    if (not 3 <= len(months) <= 25 or len(histories) != len(months)
            or any(h.status != "complete" for h in histories)
            or len({h.scope_key for h in histories}) != 1
            or not threshold.is_finite() or not 1 <= threshold <= 100):
        raise ValueError("evaluation requires 2 through 24 reference months and a target")
    indices = [_month_index(m) for m in months]
    if (indices[:-1] != list(range(indices[0], indices[0] + len(indices) - 1))
            or indices[-1] <= indices[-2]):
        raise ValueError("reference months must be consecutive and precede the target")
    reference_count = len(months) - 1
    reference_months = months[:-1]
    ids = sorted({cid for h in histories for cid in h.categories})
    categories = []
    for cid in ids:
        values = [Decimal(h.categories[cid].amount) if cid in h.categories else Decimal(0)
                  for h in histories]
        title = next((h.categories[cid].title for h in reversed(histories)
                      if cid in h.categories and h.categories[cid].title), cid)
        with localcontext() as exact:
            exact.prec = exact_decimal_precision(values + [threshold, Decimal(100)])
            reference = values[:-1]
            baseline_total = sum(reference, Decimal(0))
            baseline_count = sum(value > 0 for value in reference)
            numerator = reference_count * values[-1] - baseline_total
            reason = ("zero_baseline" if baseline_total == 0
                      else "negative_baseline" if baseline_total < 0
                      else "low_frequency" if baseline_count < 2 else None)
            above_threshold = (
                reason is None and 100 * numerator > threshold * baseline_total
            )
            # Explanation rounding only. Verdict already exact.
            with localcontext() as display:
                display.prec = 28
                display.rounding = ROUND_HALF_EVEN
                baseline_amount = baseline_total / reference_count
                change_amount = numerator / reference_count
                comparison = (SignedComparison if signed else Comparison)(
                    month=months[-1], baseline_months=reference_months,
                    baseline_amount=canonical_decimal(baseline_amount),
                    spending_amount=canonical_decimal(values[-1]),
                    change_amount=canonical_decimal(change_amount),
                    growth_percent=(canonical_decimal(100 * numerator / baseline_total)
                                    if baseline_total > 0 else None),
                )
                previous = values[-2] if _month_index(months[-1]) - _month_index(months[-2]) == 1 else None
                mom = (canonical_decimal(100 * (values[-1] - previous) / previous)
                       if previous is not None and previous > 0 else None)
        categories.append((ReportLifestyleCategory if signed else LifestyleCategory)(
            category_id=cid, category_title=title,
            samples=[{"month": m, "amount": canonical_decimal(x)} for m, x in zip(months, values)],
            comparison=comparison, latest_month_over_month_percent=mom,
            is_above_threshold=above_threshold, suppression_reason=reason,
        ))
    return categories, [
        {"month": m, "amount": h.uncategorized_amount} for m, h in zip(months, histories)]


def evaluate_partner(
    partner_id: str, partner_slot: str, partner: str, months: list[str],
    histories: list[CCSpendHistory], threshold: Decimal,
) -> LifestylePartner:
    categories, uncategorized = evaluate_categories(months, histories, threshold)
    return LifestylePartner(
        partner_id=partner_id, partner_slot=partner_slot, partner=partner, status="ready",
        categories=categories, uncategorized_samples=uncategorized,
    )


@dataclass(frozen=True)
class SavedPartner:
    partner_id: str | None
    label: str
    slot: str
    history: CCSpendHistory | None


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate saved key")
        obj[key] = value
    return obj


def _invalid_constant(value):
    raise ValueError("nonfinite saved constant")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("nonfinite saved number")
    return number


def _read_envelope(month: str) -> dict | None:
    path = storage.bills_dashboard_path(month)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    record = json.loads(raw, object_pairs_hook=_unique_object,
                        parse_constant=_invalid_constant, parse_float=_finite_float)
    if not isinstance(record, dict) or record.get("month") != month:
        raise ValueError("invalid saved envelope")
    version = record.get("schema_version", 1)
    if type(version) is not int or not 1 <= version <= 7:
        raise ValueError("invalid saved schema")
    return record


def _read_month(month: str) -> list[SavedPartner] | None:
    record = _read_envelope(month)
    if record is None:
        return None
    version = record.get("schema_version", 1)
    partners = record.get("partners")
    if not isinstance(partners, list):
        raise ValueError("invalid saved partners")
    rows = []
    seen = set()
    for partner in partners:
        if not isinstance(partner, dict):
            raise ValueError("invalid saved partner")
        pid = partner.get("partner_id", "")
        if not isinstance(pid, str) or (pid and not pid.strip()):
            raise ValueError("invalid saved identity")
        if pid:
            if pid in seen:
                raise ValueError("duplicate saved partner")
            seen.add(pid)
        label = partner.get("partner", "")
        slot = partner.get("partner_slot", "")
        if not isinstance(label, str) or not isinstance(slot, str) or slot not in {"a", "b", ""}:
            raise ValueError("invalid saved display metadata")
        history = partner.get("cc_spend_history")
        if history is not None:
            if version < 6:
                raise ValueError("history incompatible with saved schema")
            history = CCSpendHistory.model_validate(history)
        rows.append(SavedPartner(pid or None, label, slot, history))
    return rows


def read_lifestyle_creep(selection: Selection) -> LifestyleCreepResponse:
    """Read only selected reference months and target; corruption cancels evaluation."""
    months = list(selection.window_months)
    current = _current_month()
    # API clock wins. Saved complete status cannot close an open month.
    unsafe = [m for m in months if m >= current]
    if unsafe:
        return LifestyleCreepResponse(
            month=selection.month, reference_start=selection.reference_start,
            reference_end=selection.reference_end, window_months=months,
            evaluation_months=[selection.month], baseline_months=len(months) - 1,
            threshold_percent=canonical_decimal(selection.threshold),
            status="insufficient_history", partners=[],
            issues=[HistoryIssue(
                month=m, partner_id=None,
                code="partial_month" if m == current else "unavailable_history",
                reason="open_month" if m == current else "future_month",
            ) for m in unsafe],
        )
    # Parse every loaded row before exposing any partner verdict.
    loaded = [_read_month(m) for m in months]
    ids = sorted({p.partner_id for rows in loaded if rows is not None
                  for p in rows if p.partner_id is not None})
    issues: set[tuple[str, str | None, str, str | None]] = set()
    by_month = []
    for month, rows in zip(months, loaded):
        by_month.append({p.partner_id: p for p in rows or [] if p.partner_id is not None})
        if rows is None:
            issues.add((month, None, "missing_snapshot", None))
        elif not rows and not ids:
            issues.add((month, None, "no_stable_partners", None))
        else:
            for p in rows:
                if p.partner_id is None:
                    issues.add((month, None, "missing_partner_identity", None))
    partners = []
    for pid in ids:
        observations = [rows.get(pid) for rows in by_month]
        histories = []
        for i, (month, p) in enumerate(zip(months, observations)):
            if loaded[i] is None:
                continue
            if p is None:
                issues.add((month, pid, "missing_partner", None))
            elif p.history is None:
                issues.add((month, pid, "legacy_history", None))
            elif p.history.status == "partial":
                issues.add((month, pid, "partial_month", p.history.reason))
            elif p.history.status == "unavailable":
                issues.add((month, pid, "unavailable_history", p.history.reason))
            else:
                histories.append(p.history)
        ready = len(histories) == len(months)
        if ready and len({h.scope_key for h in histories}) != 1:
            ready = False
            issues.update((month, pid, "scope_changed", None) for month in months)
        label = next((p.label for p in reversed(observations) if p and p.label), pid)
        slot = next(p.slot for p in reversed(observations) if p)
        if ready:
            partners.append(evaluate_partner(pid, slot, label, months, histories, selection.threshold))
        else:
            partners.append(LifestylePartner(partner_id=pid, partner_slot=slot, partner=label,
                                             status="insufficient_history", categories=[],
                                             uncategorized_samples=[]))
    ready_count = sum(p.status == "ready" for p in partners)
    status = ("insufficient_history" if not ready_count else
              "partial" if issues or ready_count != len(partners) else "ready")
    ordered = sorted(issues, key=lambda i: (i[0], i[1] is not None, i[1] or "", i[2]))
    return LifestyleCreepResponse(
        month=selection.month, reference_start=selection.reference_start,
        reference_end=selection.reference_end, window_months=months,
        evaluation_months=[selection.month], baseline_months=len(months) - 1,
        threshold_percent=canonical_decimal(selection.threshold), status=status, partners=partners,
        issues=[HistoryIssue(month=m, partner_id=p, code=c, reason=r) for m, p, c, r in ordered],
    )
