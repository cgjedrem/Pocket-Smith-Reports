"""Bills router — F2-BE sub-feature 2 dashboard read + sub-feature 3 events + sub-feature 4 event detail.

GET /api/bills/dashboard?month=YYYY-MM — pure file read, no PS calls.
GET /api/bills/dashboard/events?month=YYYY-MM[&...filters] — flatten + filter + sort.
GET /api/bills/dashboard/event?id=X&month=YYYY-MM — one event by id, first-match-wins.

All endpoints: Cache-Control: no-store via middleware allow-list.
"""

from __future__ import annotations

import json
import re
import sys
import traceback
from datetime import date

from fastapi import APIRouter, HTTPException, Query, status

from budget_api.services import storage

router = APIRouter()

# YYYY-MM strict — rejects "2026-7", "foo", "../etc/passwd", "".
_MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")

# Sub-feature 4 — event id. Alphanumeric + _ + -, 1-64 chars.
_EVENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# Sub-feature 3 — type allow-list, mirrors models/bills.py Literal.
_TYPE_ALLOW = {"bill", "buy", "savings", "salary"}

# Silent limit clamp cap. User-sent limit > cap → cap. limit<1 → 400.
_LIMIT_CAP = 1000
_LIMIT_DEFAULT = 500


@router.get("/bills/dashboard")
def dashboard(month: str = Query(...)) -> dict:
    """Read bills dashboard snapshot for `month` from disk. No-store, no validate."""
    # L4 Q4=b — always fresh, no caching. Middleware sets no-store on all
    # /api/bills/* responses (covers 200, 400, 404, 500).

    # Manual pattern check — override FastAPI's auto-422 message (L2 Q1 final).
    if not _MONTH_PATTERN.match(month):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid month format",
        )

    path = storage.bills_dashboard_path(month)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No snapshot for {month}. "
                f"Run GET /api/sync?start_month={month}&end_month={month} to generate one."
            ),
        )
    except Exception:
        # OSError (permission, disk) + UnicodeDecodeError + anything unexpected.
        # Log full traceback, return documented generic 500 body.
        print(traceback.format_exc(), file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="internal error reading snapshot",
        )
    try:
        snapshot = json.loads(raw)
    except Exception:
        # JSONDecodeError + anything unexpected during parse.
        # Log full traceback, return documented generic 500 body.
        print(traceback.format_exc(), file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="internal error reading snapshot",
        )
    # PR65 review: month kind is stamped at SYNC time, but the FE gates
    # past/current rendering on the LOCAL clock — a snapshot synced on
    # Aug 31 served on Sep 1 must not claim is_current. Re-derive at read.
    if isinstance(snapshot, dict) and "is_past" in snapshot:
        from budget_api.services.bills_builder import _month_flags

        is_past, is_current, is_future = _month_flags(month)
        snapshot["is_past"] = is_past
        snapshot["is_current"] = is_current
        snapshot["is_future"] = is_future
    return snapshot


@router.get("/bills/dashboard/events")
def events(
    month: str,
    partner: str | None = None,
    partner_id: str | None = None,
    type: str | None = None,  # noqa: A002 — shadows builtin, matches query param
    category: str | None = None,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    order: str = "asc",
    limit: str = "500",
) -> dict:
    """Flatten + filter + sort events for `month`. No-store, manual validation.

    `partner_id` (schema-5 id) supersedes the legacy label `partner` param;
    when both are sent, `partner_id` wins. Pre-field (schema-4) snapshots
    carry no partner_id — filtering by it yields no rows there (never 500).
    """
    # No-store set by middleware on all /api/bills/* responses.

    # Validate (alphabetical order: category, from, limit, month, order, partner, to, type).
    errors: list[str] = []
    if category:
        pass  # exact match only, no validation
    parsed_from: date | None = None
    if from_:
        try:
            parsed_from = date.fromisoformat(from_)
        except ValueError:
            errors.append(f"invalid from date: {from_}")
    parsed_limit: int = _LIMIT_DEFAULT
    # Empty string (from ?limit=) treated same as missing → default.
    if limit is not None and limit != "":
        try:
            parsed_limit = int(limit)
        except ValueError:
            errors.append(f"invalid limit: {limit}")
        else:
            if parsed_limit < 1:
                errors.append("limit must be >= 1")
    if not _MONTH_PATTERN.match(month):
        errors.append("invalid month format")
    if order not in ("asc", "desc"):
        errors.append(f"invalid order: {order}")
    if partner:
        pass  # no validation, exact match only
    parsed_to: date | None = None
    if to:
        try:
            parsed_to = date.fromisoformat(to)
        except ValueError:
            errors.append(f"invalid to date: {to}")
    if type:
        if type not in _TYPE_ALLOW:
            errors.append(f"invalid type: {type}")
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=errors,
        )

    # Normalize: empty string → None for filter logic. partner_id supersedes
    # the legacy label param for one deprecation cycle.
    f_partner_id = partner_id or None
    f_partner = None if f_partner_id is not None else (partner or None)
    f_type = type or None
    f_category = category or None
    # Silent clamp to cap.
    effective_limit = min(parsed_limit, _LIMIT_CAP)

    # Read + parse + shape-guard via shared helper.
    snapshot = _read_snapshot(month)

    # Flatten + filter.
    flat: list[dict] = []
    for partner_block in snapshot["partners"]:
        for event in partner_block.get("events", []):
            if _match(
                event, f_partner, f_partner_id, f_type, f_category,
                parsed_from, parsed_to,
            ):
                flat.append(event)

    # Sort: `order` flips date direction; partner_id + id always asc as
    # tiebreakers (schema-4 fallback: label). Stable sort preserves the first
    # sort within equal-date ties regardless of `order`.
    partner_id_sorted = sorted(
        flat, key=lambda e: (e.get("partner_id") or e["partner"], e["id"])
    )
    sorted_events = sorted(
        partner_id_sorted,
        key=lambda e: e["date"],
        reverse=(order == "desc"),
    )

    # `total` = after filter, before clamp.
    total = len(sorted_events)
    limited = sorted_events[:effective_limit]
    return {"events": limited, "total": total}


@router.get("/bills/dashboard/event")
def event_detail(
    id: str,  # noqa: A002 — shadows builtin, matches query param
    month: str,
) -> dict:
    """Return one event by id for the given month. Bare dict, first-match-wins."""
    # No-store set by middleware on all /api/bills/* responses.

    # Validate (alphabetical: id, month).
    errors: list[str] = []
    if not _EVENT_ID_PATTERN.match(id):
        errors.append("invalid event id format")
    if not _MONTH_PATTERN.match(month):
        errors.append("invalid month format")
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=errors,
        )

    # Read + shape-guard via shared helper.
    snapshot = _read_snapshot(month)

    # First-match-wins across partners.
    for partner_block in snapshot["partners"]:
        for event in partner_block.get("events", []):
            if event.get("id") == id:
                return event
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Event {id} not found in {month}",
    )


def _match(
    event: dict,
    partner: str | None,
    partner_id: str | None,
    type_: str | None,
    category: str | None,
    parsed_from: date | None,
    parsed_to: date | None,
) -> bool:
    """AND-match event against all filters. None = wildcard."""
    if partner is not None and event["partner"] != partner:
        return False
    if partner_id is not None and event.get("partner_id", "") != partner_id:
        return False
    if type_ is not None and event["type"] != type_:
        return False
    if category is not None and event["title"] != category:
        return False
    if parsed_from is not None and event["date"] < parsed_from.isoformat():
        return False
    if parsed_to is not None and event["date"] > parsed_to.isoformat():
        return False
    return True


def _read_snapshot(month: str) -> dict:
    """Read + parse + shape-guard snapshot. Shared by events() + event_detail().

    Raises 404 (snapshot missing), 500 (corrupt/shape errors).
    Caller MUST validate `month` first; this helper trusts the input.
    """
    path = storage.bills_dashboard_path(month)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No snapshot for {month}. "
                f"Run GET /api/sync?start_month={month}&end_month={month} to generate one."
            ),
        )
    except Exception:
        # OSError (permission, disk) + UnicodeDecodeError + anything unexpected.
        # Log full traceback, return documented generic 500 body.
        print(traceback.format_exc(), file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="internal error reading snapshot",
        )
    try:
        snapshot = json.loads(raw)
    except Exception:
        # JSONDecodeError + anything unexpected during parse.
        # Log full traceback, return documented generic 500 body.
        print(traceback.format_exc(), file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="internal error reading snapshot",
        )

    # Shape check — wrong shape → 500 with specific message. Log to stderr (no exc).
    if not isinstance(snapshot, dict):
        print(f"snapshot shape error for {month}: missing partners", file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="internal error reading snapshot: missing partners",
        )
    partners_field = snapshot.get("partners")
    if not isinstance(partners_field, list):
        print(f"snapshot shape error for {month}: missing partners", file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="internal error reading snapshot: missing partners",
        )
    for partner_block in partners_field:
        # partner_block must be a dict before we call .get() — otherwise AttributeError.
        if not isinstance(partner_block, dict):
            print(
                f"snapshot shape error for {month}: partner block is not a dict",
                file=sys.stderr,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="internal error reading snapshot: partner block is not a dict",
            )
        if not isinstance(partner_block.get("events"), list):
            print(
                f"snapshot shape error for {month}: events is not a list",
                file=sys.stderr,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="internal error reading snapshot: events is not a list",
            )
    return snapshot
