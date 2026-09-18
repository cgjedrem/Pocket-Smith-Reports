"""Bills-suite clock isolation.

Bills fixtures are anchored in August 2026 (current month = "2026-08",
event/savings chains built around it), but the builder classifies months
against the real wall clock (`bills_builder.datetime.now()`). The suite
therefore only passed while the calendar agreed: it broke CI on the
2026-09-01 month rollover (runs 33512355188 / 33512535473) with the
same commit that was green on 2026-08-31 (run 33385741392).
"""

from __future__ import annotations

import pytest

from budget_api.services import bills_builder


class _FrozenDatetime(bills_builder.datetime):
    """datetime pinned to 2026-08-31 — the last-green fixture epoch."""

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls(2026, 8, 31, 12, 0, 0)
        return cls(2026, 8, 31, 10, 0, 0, tzinfo=tz)


@pytest.fixture(autouse=True)
def frozen_bills_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Freeze the builder's clock for every bills test.

    Single patch point: `_current_month`, `_month_flags`, the
    current-month envelope `today` (bills_builder.py:785) and the
    synced_at stamp all read `bills_builder.datetime`, and test
    modules' from-imported `_current_month` shares the same function
    object — all derive from this freeze. Tests that need a different
    clock override it themselves (see
    test_month_flags_uses_local_time_not_utc).
    """
    monkeypatch.setattr(bills_builder, "datetime", _FrozenDatetime)