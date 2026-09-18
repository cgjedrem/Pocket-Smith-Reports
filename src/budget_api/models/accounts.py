"""Account pydantic models — AccountBindingUpdate, Account, AccountList."""

from __future__ import annotations

from pydantic import BaseModel


class AccountBindingUpdate(BaseModel):
    """PUT /api/accounts/{id}/binding body — type validated manually in router."""

    partner_id: str | None = None
    type: str | None = None
    excluded: bool = False


class Account(BaseModel):
    """Merged PS account + local binding."""

    id: str  # PS account ID
    name: str  # from PS
    partner_id: str | None  # from account_mappings.json
    type: str | None  # checking/cc/savings/null
    excluded: bool  # auto-set true if account gone from PS


class AccountList(BaseModel):
    """GET /api/accounts response."""

    accounts: list[Account]
