"""Neutral aggregate observations and actions for MoM reports."""

from typing import Any, Dict, List, Optional
import statistics

EXCLUDED_SECTIONS = {"savings", "excluded"}


def _expense_categories(agg: Dict[str, Any]):
    for title, category in agg.get("cats", {}).items():
        if (
            category.get("is_reimbursement")
            or category.get("section") in EXCLUDED_SECTIONS
        ):
            continue
        total = sum(category.get("total") or [])
        if total:
            yield title, total


def _largest_cat(agg: Dict[str, Any]) -> Optional[str]:
    categories = list(_expense_categories(agg))
    if not categories:
        return None
    title, total = max(categories, key=lambda item: item[1])
    return f"<b>{title}</b> is the largest expense category at {total:,.0f} over the period."


def _highest_spend_month(agg: Dict[str, Any]) -> Optional[str]:
    months = agg.get("months") or []
    spend = agg.get("series", {}).get("real_spend", {}).get("total") or []
    if not months or not spend:
        return None
    index = max(range(min(len(months), len(spend))), key=lambda item: spend[item])
    return f"<b>{months[index]}</b> has the highest recorded real spend at {spend[index]:,.0f}."


def _lowest_net_cash_month(agg: Dict[str, Any]) -> Optional[str]:
    months = agg.get("months") or []
    net_cash = agg.get("series", {}).get("net_cash", {}).get("total") or []
    if not months or not net_cash:
        return None
    index = min(range(min(len(months), len(net_cash))), key=lambda item: net_cash[item])
    return f"<b>{months[index]}</b> has the lowest recorded net cash at {net_cash[index]:,.0f}."


def _spend_variability(agg: Dict[str, Any]) -> Optional[str]:
    spend = agg.get("series", {}).get("real_spend", {}).get("total") or []
    if len(spend) < 2:
        return None
    return f"Real spend ranged from {min(spend):,.0f} to {max(spend):,.0f} with an average of {statistics.mean(spend):,.0f} per reported month."


def _reimbursement_count(agg: Dict[str, Any]) -> Optional[str]:
    count = len(agg.get("paired_reimbs") or [])
    return (
        f"The period includes <b>{count}</b> paired reimbursement records."
        if count
        else None
    )


def generate_observations(agg: Dict[str, Any]) -> List[str]:
    observations = [
        result
        for rule in (
            _largest_cat,
            _highest_spend_month,
            _lowest_net_cash_month,
            _spend_variability,
            _reimbursement_count,
        )
        if (result := rule(agg))
    ]
    return [f"{index}. {value}" for index, value in enumerate(observations, start=1)]


def _action_review_largest_category(agg: Dict[str, Any]) -> Optional[str]:
    categories = list(_expense_categories(agg))
    if not categories:
        return None
    title, _ = max(categories, key=lambda item: item[1])
    return f"Review <b>{title}</b> against the current budget and documented spending policy."


def _action_review_variability(agg: Dict[str, Any]) -> Optional[str]:
    spend = agg.get("series", {}).get("real_spend", {}).get("total") or []
    return (
        "Review months with the largest spend variance before setting future budgets."
        if len(spend) > 1 and min(spend) != max(spend)
        else None
    )


def generate_actions(agg: Dict[str, Any]) -> List[str]:
    actions = [
        result
        for rule in (_action_review_largest_category, _action_review_variability)
        if (result := rule(agg))
    ]
    return [f"{index}. {value}" for index, value in enumerate(actions, start=1)]


def generate_recommendations(agg: Dict[str, Any]) -> List[str]:
    return generate_observations(agg)
