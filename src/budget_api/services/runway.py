"""Local recorded-spending comparison. No snapshots, credentials, sync, or writes on GET."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal, DecimalException, ROUND_HALF_UP, localcontext
import json
import math
from pathlib import Path
import re

from pydantic import ValidationError

from budget_api.models.category_mappings import DETAILED_CATEGORY_SECTIONS, KPI_ROLES
from budget_api.models.runway import (
    AccountOption, Issue, Measures, MonthObservation, Owner, OwnerObservation,
    OwnerResult, RunwayConfig, RunwayResponse, RunwaySettings, RunwayUpdate, SelectedAccount,
)
from budget_api.services import storage

_ID = re.compile(r"^[1-9][0-9]*$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONEY = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
_UNREADABLE = object()


class InvalidSource(ValueError):
    def __init__(self, code="invalid_source"):
        super().__init__(code)
        self.code = code


class RunwayServiceError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail


def local_now() -> datetime:
    return datetime.now().astimezone()


def _system_midnight(day: date) -> datetime:
    # Resolve offset at that date, not today's offset across DST.
    return datetime.combine(day, time.min).astimezone()


def _midnight(day, now, system_calendar):
    return _system_midnight(day) if system_calendar else datetime.combine(day, time.min, tzinfo=now.tzinfo)


def _issue(code, *, qualification=False, month=None, account_id=None, partner_id=None):
    return Issue(code=code, severity="qualification" if qualification else "blocking",
                 month=month, account_id=account_id, partner_id=partner_id)


def _unique(issues):
    return list({(i.code, i.severity, i.month, i.account_id, i.partner_id): i for i in issues}.values())


def _id(value):
    if type(value) is int and value > 0:
        return str(value)
    if isinstance(value, str) and _ID.fullmatch(value):
        return value
    raise InvalidSource()


def _number(value: Decimal) -> float:
    result = float(value)
    if not math.isfinite(result) or (value != 0 and result == 0):
        raise InvalidSource()
    return result


def _money(value) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise InvalidSource()
    text = str(value)
    if not _MONEY.fullmatch(text):
        raise InvalidSource()
    try:
        amount = Decimal(text)
        if not amount.is_finite():
            raise InvalidSource()
        _number(amount)
        return amount
    except (DecimalException, OverflowError, ValueError):
        raise InvalidSource() from None


def _date(value) -> date:
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        raise InvalidSource()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise InvalidSource() from None


def _timestamp(value) -> datetime:
    if not isinstance(value, str) or "T" not in value:
        raise InvalidSource()
    try:
        result = datetime.fromisoformat(value)
        if result.utcoffset() is None:
            raise ValueError
        return result
    except ValueError:
        raise InvalidSource() from None


def _freshness(stamp, now):
    return "unknown" if stamp is None else ("stale" if now - stamp > timedelta(hours=24) else "fresh")


def _flag(obj, key):
    value = obj.get(key, False)
    if type(value) is not bool:
        raise InvalidSource()
    return value


def _transfer_flag(obj):
    # PocketSmith sends is_transfer null. Null/absent = not transfer. Non-null must be bool.
    return False if obj.get("is_transfer") is None else _flag(obj, "is_transfer")


def _mapping(value):
    if not isinstance(value, dict):
        raise InvalidSource()
    return value


def _read_bytes(path: Path):
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError:
        return _UNREADABLE


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidSource()
        result[key] = value
    return result


def _decode(raw):
    if raw is None:
        return None
    if raw is _UNREADABLE:
        raise InvalidSource()
    try:
        value = json.loads(raw, parse_float=Decimal, object_pairs_hook=_pairs)
        if value is None:
            raise InvalidSource()
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise InvalidSource() from None


def _paths(months=()):
    # Fixed sources only. No filename search or snapshot fallback.
    return [
        storage.PRIVATE_DATA_DIR / "runway_config.json",
        storage.ACCOUNT_MAPPING_PATH, storage.ACCOUNT_CATALOG_PATH,
        storage.SYNC_STATUS_PATH,
        *([storage.CATEGORY_CATALOG_PATH, storage.CATEGORY_ROLES_PATH,
           storage.DETAILED_SECTION_MAPPING_PATH] if months else []),
        *(storage.monthly_ps_raw_path(month) for month in months),
    ]


def _bundle(months=()):
    return {path: _read_bytes(path) for path in _paths(months)}


def _stable(bundle):
    if any(_read_bytes(path) != raw for path, raw in bundle.items()):
        return False
    status = _decode(bundle[storage.SYNC_STATUS_PATH])
    if status is not None:
        status = _mapping(status)
        if status.get("status") not in ("running", "success", "failed"):
            raise InvalidSource()
        if status["status"] == "running":
            return False
    return True


def _config(bundle):
    raw = bundle[storage.PRIVATE_DATA_DIR / "runway_config.json"]
    if raw is None:
        return [], "unconfigured"
    try:
        decoded = _mapping(_decode(raw))
        if set(decoded) != {"schema_version", "liquid_account_ids"}:
            raise InvalidSource()
        config = RunwayConfig.model_validate(decoded)
        return config.liquid_account_ids, "valid" if config.liquid_account_ids else "empty"
    except (ValidationError, InvalidSource):
        raise InvalidSource("invalid_settings") from None


@dataclass
class Currency:
    codes: set[str] = field(default_factory=set)
    unknown: bool = False

    @property
    def code(self):
        return next(iter(self.codes)) if len(self.codes) == 1 else None

    @property
    def status(self):
        if len(self.codes) > 1:
            return "conflict"
        return "unverified" if self.unknown or not self.codes else "verified"


def _currency(*values):
    codes = set()
    for value in values:
        if value is None:
            continue
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z]{3}", value):
            raise InvalidSource()
        codes.add(value.upper())
    return Currency(codes, not codes)


def _currencies(values):
    result = Currency()
    for value in values:
        result.codes.update(value.codes)
        result.unknown |= value.unknown
    return result


def _context(bundle):
    mappings = _mapping(_decode(bundle[storage.ACCOUNT_MAPPING_PATH]))
    partners = _mapping(mappings.get("partners"))
    bindings = _mapping(mappings.get("accounts"))
    if not partners:
        raise InvalidSource("ownership_incomplete")
    owners = []
    for index, (key, value) in enumerate(sorted(partners.items())):
        if not key or not isinstance(value, dict):
            raise InvalidSource("ownership_incomplete")
        label = value.get("label", key)
        if not isinstance(label, str):
            raise InvalidSource()
        owners.append(Owner(partner_id=key, partner_slot=("a", "b")[index] if index < 2 else "", label=label or key))
    for key in bindings:
        _id(key)
    catalog = _decode(bundle[storage.ACCOUNT_CATALOG_PATH])
    accounts = {}
    if catalog is not None:
        rows = _mapping(catalog).get("accounts")
        if not isinstance(rows, list):
            raise InvalidSource()
        for row in rows:
            key = _id(_mapping(row).get("id"))
            accounts[key] = row if key not in accounts else None
    return owners, partners, bindings, accounts, catalog


def _account_options(ids, owners, bindings, accounts):
    options = []
    owner_ids = {owner.partner_id for owner in owners}
    for key in dict.fromkeys([*accounts, *ids]):
        account = accounts.get(key)
        binding = bindings.get(key)
        issues = []
        if not isinstance(account, dict):
            issues.append(_issue("account_missing" if key not in accounts else "invalid_source", account_id=key))
            account = {}
        if not isinstance(binding, dict):
            binding = {}
        owner = binding.get("partner_id")
        if not isinstance(owner, str) or owner not in owner_ids:
            owner = None
            issues.append(_issue("account_unowned", account_id=key))
        kind = binding.get("type")
        if kind not in ("checking", "savings", "cc", "investment"):
            kind = None
        if kind not in {"checking", "savings"}:
            issues.append(_issue("account_type_ineligible", account_id=key))
        try:
            excluded = _flag(binding, "excluded")
        except InvalidSource:
            excluded = True
            issues.append(_issue("invalid_source", account_id=key))
        if excluded:
            issues.append(_issue("account_excluded", account_id=key))
        if account.get("current_balance") is None:
            issues.append(_issue("missing_balance", account_id=key))
        else:
            try:
                _money(account["current_balance"])
            except InvalidSource:
                issues.append(_issue("invalid_balance", account_id=key))
        name = account.get("name", binding.get("name", key))
        options.append(AccountOption(
            id=key, name=name if isinstance(name, str) else key, partner_id=owner,
            type=kind, excluded=excluded, selected=key in ids,
            eligible=not issues, issues=issues,
        ))
    return options


def _settings(bundle, ids=None):
    saved_ids, state = _config(bundle) if ids is None else (ids, "valid" if ids else "empty")
    owners, _, bindings, accounts, _ = _context(bundle)
    options = _account_options(saved_ids, owners, bindings, accounts)
    issues = [issue for option in options if option.selected for issue in option.issues]
    if issues:
        state = "invalid"
    if bundle[storage.ACCOUNT_CATALOG_PATH] is None:
        issues.append(_issue("missing_source"))
    return RunwaySettings(liquid_account_ids=saved_ids, selection_status=state,
                          owners=owners, accounts=options, issues=_unique(issues))


def get_settings() -> RunwaySettings:
    bundle = _bundle()
    try:
        response = _settings(bundle)
        if not _stable(bundle):
            raise RunwayServiceError(409, "Runway sources changed; retry loading settings.")
        return response
    except InvalidSource:
        raise RunwayServiceError(500, "Runway settings or account sources cannot be read safely.") from None


def save_settings(update: RunwayUpdate) -> RunwaySettings:
    bundle = _bundle()
    try:
        response = _settings(bundle, update.liquid_account_ids)
        if response.selection_status == "invalid":
            raise RunwayServiceError(400, "Select only owned, non-excluded checking or savings accounts with valid recorded balances.")
        if not _stable(bundle):
            raise RunwayServiceError(409, "Runway sources changed; retry the selection save.")
        # Build response first. No fallible source reads after replace.
        storage.atomic_write_json(
            storage.PRIVATE_DATA_DIR / "runway_config.json",
            RunwayConfig(liquid_account_ids=update.liquid_account_ids).model_dump(),
        )
        return response
    except (InvalidSource, OSError):
        raise RunwayServiceError(500, "Runway settings could not be saved safely.") from None


def _month_window(now):
    current = now.date().replace(day=1)
    months = []
    for _ in range(3):
        current = (current - timedelta(days=1)).replace(day=1)
        months.append(current.isoformat()[:7])
    return list(reversed(months))


def _classification(bundle, partners):
    catalog = _decode(bundle[storage.CATEGORY_CATALOG_PATH])
    roles = _decode(bundle[storage.CATEGORY_ROLES_PATH])
    sections = _decode(bundle[storage.DETAILED_SECTION_MAPPING_PATH])
    roles = {} if roles is None else _mapping(roles)
    sections = {} if sections is None else _mapping(_mapping(sections).get("category_sections", {}))
    excluded = set()
    for partner in partners.values():
        if partner.get("savings_category_id") is not None:
            excluded.add(_id(partner["savings_category_id"]))
    nodes, parents = {}, {}
    if catalog is not None:
        rows = _mapping(catalog).get("categories")
        if not isinstance(rows, list):
            raise InvalidSource()
        pending = [(row, None) for row in rows]
        while pending:
            row, parent = pending.pop()
            key = _id(_mapping(row).get("id"))
            if key in nodes:
                raise InvalidSource()
            explicit = row.get("parent_id")
            explicit = _id(explicit) if explicit is not None else None
            if parent is not None and explicit not in {None, parent}:
                raise InvalidSource()
            nodes[key], parents[key] = row, explicit or parent
            children = row.get("children", [])
            if not isinstance(children, list):
                raise InvalidSource()
            pending.extend((child, key) for child in children)
        for key, row in nodes.items():
            title = row.get("title", "")
            if not isinstance(title, str):
                raise InvalidSource()
            if _transfer_flag(row) or "cc payment" in title.lower():
                excluded.add(key)
    # Referenced config values validated at classification; unrelated values ignored.
    def is_excluded(key, embedded):
        title = embedded.get("title", "")
        if not isinstance(title, str):
            raise InvalidSource()
        if _transfer_flag(embedded):
            return True
        if "cc payment" in title.lower():
            return True
        seen = set()
        while key is not None:
            if key in seen:
                raise InvalidSource()
            seen.add(key)
            role = roles.get(key)
            section = sections.get(key)
            if role is not None and (not isinstance(role, str) or role not in KPI_ROLES):
                raise InvalidSource()
            if section is not None and (not isinstance(section, str) or section not in DETAILED_CATEGORY_SECTIONS):
                raise InvalidSource()
            if key in excluded or role in {"exclude", "savings", "investment"} or section in {"cc_payments", "excluded", "savings"}:
                return True
            key = parents.get(key)
        return False

    # Reject cycles even if an earlier exclusion would stop traversal.
    for key in parents:
        seen = set()
        while key is not None:
            if key in seen:
                raise InvalidSource()
            seen.add(key)
            parent = parents.get(key)
            if parent is not None and parent not in nodes:
                raise InvalidSource()
            key = parent
    return is_excluded, catalog is None


def _provenance(raw, month, now, row, system_calendar):
    if isinstance(raw, list):
        return raw
    raw = _mapping(raw)
    transactions = raw.get("transactions")
    if not isinstance(transactions, list):
        raise InvalidSource()
    if "provenance" not in raw:
        return transactions
    proof = _mapping(raw["provenance"])
    start = _date(proof["coverage_start"]) if "coverage_start" in proof else None
    end = _date(proof["coverage_end"]) if "coverage_end" in proof else None
    stamp = _timestamp(proof["collected_at"]) if "collected_at" in proof else None
    row.coverage_start = start.isoformat() if start else None
    row.coverage_end = end.isoformat() if end else None
    row.collected_at = stamp.isoformat() if stamp else None
    row.freshness = _freshness(stamp, now)
    first = date.fromisoformat(month + "-01")
    next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    last = next_month - timedelta(days=1)
    if stamp is not None and stamp > now:
        raise InvalidSource()
    complete = proof.get("complete")
    if "complete" in proof and type(complete) is not bool:
        raise InvalidSource()
    if (start is None) != (end is None) or (start and end and start > end):
        raise InvalidSource()
    if complete is False or (start is not None and (start != first or end != last)):
        raise InvalidSource("partial_source")
    boundary = _midnight(next_month, now, system_calendar)
    if stamp is not None and stamp < boundary:
        raise InvalidSource("partial_source")
    if complete is True:
        if start != first or end != last or stamp is None:
            raise InvalidSource()
        row.coverage = "complete"
    return transactions


def _empty_observation(month, owners):
    return MonthObservation(
        month=month, status="excluded", coverage="unverified", issues=[],
        owners=[OwnerObservation(partner_id=o.partner_id, spending=None,
                                 currency_code=None, currency_status="unverified") for o in owners],
    )


@dataclass
class Spending:
    row: MonthObservation
    amounts: dict[str, Decimal] = field(default_factory=dict)
    currencies: dict[str, Currency] = field(default_factory=dict)


def _fingerprint(item):
    # Tag every value. User arrays/objects cannot impersonate scalar encodings.
    if isinstance(item, dict):
        # JSON keys are strings. Key order irrelevant; metadata retained.
        return ("object", tuple((key, _fingerprint(value)) for key, value in sorted(item.items())))
    if isinstance(item, list):
        return ("array", tuple(_fingerprint(value) for value in item))
    if isinstance(item, Decimal):
        # Preserve decoded scale/sign. No numeric coercion or rounding.
        return ("decimal", str(item))
    if item is None:
        return ("null",)
    if type(item) is bool:
        return ("bool", item)
    if type(item) is int:
        return ("int", item)
    if type(item) is str:
        return ("string", item)
    if type(item) is float:
        # Decoder accepts NaN/Infinity. Money validation still rejects them.
        return ("float", item.hex())
    raise InvalidSource()


def _identity_conflicts(bundle, months):
    seen, conflicts = {}, set()
    for month in months:
        try:
            raw = _decode(bundle[storage.monthly_ps_raw_path(month)])
            transactions = raw if isinstance(raw, list) else _mapping(raw).get("transactions")
            if not isinstance(transactions, list):
                continue
        except InvalidSource:
            continue  # Observation reports malformed source.
        for transaction in transactions:
            try:
                item = _mapping(transaction)
                key = _id(item.get("id"))
                fingerprint = _fingerprint(item)
            except (InvalidSource, RecursionError):
                continue  # Keep scanning other identities in invalid months.
            if key not in seen:
                seen[key] = (fingerprint, set())
            previous, affected = seen[key]
            affected.add(month)
            if previous != fingerprint:
                conflicts.add(key)
    return {month for key in conflicts for month in seen[key][1]}


def _observe(raw, month, now, owners, bindings, accounts, classify, classification_unknown, system_calendar,
             identity_conflict=False):
    row = _empty_observation(month, owners)
    amounts = {owner.partner_id: Decimal(0) for owner in owners}
    currencies = {owner.partner_id: Currency() for owner in owners}
    try:
        if raw is None:
            raise InvalidSource("missing_source")
        transactions = _provenance(_decode(raw), month, now, row, system_calendar)
        if identity_conflict:
            raise InvalidSource()
        seen = {}
        for transaction in transactions:
            item = _mapping(transaction)
            key = _id(item.get("id"))
            fingerprint = _fingerprint(item)
            if key in seen:
                if seen[key] != fingerprint:
                    raise InvalidSource()
                continue
            seen[key] = fingerprint
            account = _mapping(item.get("transaction_account"))
            account_id = _id(account.get("id"))
            when = _date(item.get("date"))
            if when.isoformat()[:7] != month:
                raise InvalidSource()
            amount = _money(item.get("amount"))
            if item.get("status") not in ("posted", "pending"):
                raise InvalidSource()
            transfer = _transfer_flag(item)
            category = item.get("category")
            category = {} if category is None else _mapping(category)
            category_id = _id(category.get("id")) if category else None
            category_transfer = _transfer_flag(category)
            if not isinstance(category.get("title", ""), str):
                raise InvalidSource()
            binding = bindings.get(account_id, {})
            binding = _mapping(binding)
            if _flag(binding, "excluded") or item["status"] == "pending" or amount >= 0 or transfer or category_transfer:
                continue
            kind = binding.get("type")
            if kind in ("savings", "investment") or classify(category_id, category):
                continue
            owner = binding.get("partner_id")
            if kind not in ("checking", "cc") or not isinstance(owner, str) or owner not in amounts:
                raise InvalidSource("ownership_incomplete")
            if account_id in accounts and accounts[account_id] is None:
                raise InvalidSource()
            catalog_account = accounts.get(account_id, {})
            currency = _currency(item.get("currency_code"), account.get("currency_code"),
                                 catalog_account.get("currency_code"))
            currencies[owner] = _currencies([currencies[owner], currency])
            if currencies[owner].status == "conflict":
                raise InvalidSource("currency_conflict")
            amounts[owner] += abs(amount)
        if row.coverage != "complete" and any(value == 0 for value in amounts.values()):
            raise InvalidSource("unproven_zero")
        for owner in row.owners:
            currency = currencies[owner.partner_id]
            owner.spending = _number(amounts[owner.partner_id])
            owner.currency_code, owner.currency_status = currency.code, currency.status
        household_currency = _currencies(currencies.values())
        if household_currency.status == "conflict":
            row.issues.append(_issue("currency_conflict", month=month))
        else:
            row.household_spending = _number(sum(amounts.values(), Decimal(0)))
            row.household_currency_code = household_currency.code
        row.status = "included"
        if row.coverage != "complete":
            row.issues.append(_issue("coverage_unverified", qualification=True, month=month))
        if classification_unknown:
            row.issues.append(_issue("classification_unverified", qualification=True, month=month))
    except (InvalidSource, DecimalException, OverflowError) as error:
        code = error.code if isinstance(error, InvalidSource) and not identity_conflict else "invalid_source"
        row.coverage = {"missing_source": "missing", "partial_source": "partial", "unproven_zero": "unverified"}.get(code, "invalid")
        row.status = "excluded"
        row.issues.append(_issue(code, month=month))
        for owner in row.owners:
            owner.spending = None
        row.household_spending = None
        amounts, currencies = {}, {}
    if row.freshness != "fresh":
        row.issues.append(_issue("source_stale" if row.freshness == "stale" else "source_date_unknown",
                                 qualification=True, month=month))
    return Spending(row, amounts, currencies)


def _selected(options, accounts, now, system_calendar):
    selected, balances, currencies = [], {}, {}
    for option in options:
        if not option.selected:
            continue
        account = accounts.get(option.id) or {}
        issues = list(option.issues)
        balance = None
        try:
            balance = _money(account.get("current_balance"))
        except InvalidSource:
            pass
        try:
            currency = _currency(account.get("currency_code"))
        except InvalidSource:
            currency = Currency(unknown=True)
            issues.append(_issue("invalid_source", account_id=option.id))
        stamp = None
        raw_date, precision = None, "unknown"
        value = account.get("current_balance_date")
        try:
            if value is not None:
                if isinstance(value, str) and _DATE.fullmatch(value):
                    stamp = _midnight(_date(value), now, system_calendar)
                    precision = "date"
                else:
                    stamp = _timestamp(value)
                    precision = "datetime"
                if stamp > now:
                    raise InvalidSource()
                raw_date = value
        except InvalidSource:
            stamp, precision = None, "unknown"
            issues.append(_issue("balance_date_unverified", qualification=True, account_id=option.id))
        freshness = _freshness(stamp, now)
        if freshness != "fresh":
            issues.append(_issue("balance_stale" if freshness == "stale" else "balance_date_unknown",
                                 qualification=True, account_id=option.id))
        if currency.status == "unverified":
            issues.append(_issue("currency_unverified", qualification=True, account_id=option.id))
        selected.append(SelectedAccount(
            **option.model_dump(exclude={"issues"}), issues=_unique(issues),
            balance=_number(balance) if balance is not None else None,
            currency_code=currency.code, currency_status=currency.status,
            balance_date=raw_date, balance_date_precision=precision, balance_freshness=freshness,
        ))
        balances[option.id], currencies[option.id] = balance, currency
    return selected, balances, currencies


def _measures(owner_id, ids, selected, balances, balance_currencies, observations, global_issues):
    issues = list(global_issues)
    scope = selected if owner_id is None else [a for a in selected if a.partner_id == owner_id]
    scoped_ids = list(ids or []) if owner_id is None else [a.id for a in scope]
    reserves, average, ratio, display = None, None, None, None
    reserve_currency, spend_currency = Currency(), Currency()
    unresolved = any(a.partner_id is None for a in selected)
    issues.extend(i for account in scope for i in account.issues)
    if not scoped_ids:
        issues.append(_issue("no_selection", partner_id=owner_id))
    invalid_selection = (unresolved or len(scope) != len(scoped_ids)
                         or any(not a.eligible or any(i.severity == "blocking" for i in a.issues) for a in scope))
    if invalid_selection:
        issues.append(_issue("invalid_selection", partner_id=owner_id))
    if ids is None:
        issues.append(_issue("invalid_settings"))
    if scoped_ids and not invalid_selection:
        reserve_currency = _currencies(balance_currencies[a.id] for a in scope)
        if reserve_currency.status != "conflict":
            reserves = sum((balances[a.id] for a in scope), Decimal(0))
    included = [ob for ob in observations if ob.row.status == "included"]
    if len(included) < 2:
        issues.append(_issue("insufficient_history"))
    else:
        currency_rows, amount_rows = [], []
        for observation in included:
            issues.extend(i for i in observation.row.issues if i.code != "currency_conflict")
            if owner_id is None:
                currency_rows.extend(observation.currencies.values())
                amount_rows.append(sum(observation.amounts.values(), Decimal(0)))
            else:
                currency_rows.append(observation.currencies[owner_id])
                amount_rows.append(observation.amounts[owner_id])
        spend_currency = _currencies(currency_rows)
        if spend_currency.status != "conflict":
            average = sum(amount_rows, Decimal(0)) / len(included)
    if len(included) < 3:
        issues.append(_issue("excluded_months", qualification=True))
    currency = _currencies([reserve_currency, spend_currency])
    if currency.status == "conflict":
        issues.append(_issue("currency_conflict", partner_id=owner_id))
    elif currency.status == "unverified":
        issues.append(_issue("currency_unverified", qualification=True, partner_id=owner_id))
    if reserves is not None and reserves <= 0:
        issues.append(_issue("nonpositive_reserves", partner_id=owner_id))
    if average is not None and average <= 0:
        issues.append(_issue("nonpositive_burn", partner_id=owner_id))
    try:
        # Validate independent measures before ratio; never emit false zero/Infinity.
        reserve_number = _number(reserves) if reserves is not None else None
    except InvalidSource:
        reserve_number, reserves = None, None
        issues.append(_issue("invalid_source"))
    try:
        average_number = _number(average) if average is not None else None
    except InvalidSource:
        average_number, average = None, None
        issues.append(_issue("invalid_source"))
    if not any(i.severity == "blocking" for i in issues) and reserves is not None and average is not None:
        try:
            value = reserves / average
            ratio = _number(value)
            if value < Decimal("0.05"):
                display = "<0.1"
            else:
                with localcontext() as context:
                    context.prec = max(28, value.adjusted() + 3)
                    display = str(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
        except (InvalidSource, DecimalException, OverflowError):
            ratio, display = None, None
            issues.append(_issue("invalid_source"))
    return Measures(
        selected_account_ids=scoped_ids, reserves=reserve_number, average_monthly_spending=average_number,
        runway_months=ratio, runway_display=display, currency_code=currency.code,
        reserves_currency_code=reserve_currency.code, spending_currency_code=spend_currency.code,
        currency_status=currency.status, status="unavailable" if ratio is None else ("qualified" if issues else "available"),
        issues=_unique(issues),
    )


def calculate_runway(*, now: datetime | None = None) -> RunwayResponse:
    # Cover finite float exponent range plus cancellation and accumulation.
    with localcontext() as context:
        context.prec = 700
        return _calculate_runway(now or local_now(), system_calendar=now is None)


def _calculate_runway(now: datetime, *, system_calendar: bool) -> RunwayResponse:
    months = _month_window(now)
    bundle = _bundle(months)
    issues, owners, selected, observations = [], [], [], []
    ids, state = None, "invalid_settings"
    balances, balance_currencies = {}, {}
    catalog_date, catalog_freshness = None, "unknown"
    try:
        ids, state = _config(bundle)
    except InvalidSource:
        issues.append(_issue("invalid_settings"))
    try:
        owners, partners, bindings, accounts, catalog = _context(bundle)
        options = _account_options(ids or [], owners, bindings, accounts)
        selected, balances, balance_currencies = _selected(options, accounts, now, system_calendar)
        if ids and any(not a.eligible for a in selected):
            state = "invalid"
        if catalog is not None and "provenance" in catalog:
            proof = _mapping(catalog["provenance"])
            if "collected_at" in proof:
                stamp = _timestamp(proof["collected_at"])
                if stamp > now:
                    raise InvalidSource()
                catalog_date, catalog_freshness = stamp.isoformat(), _freshness(stamp, now)
        if catalog_freshness != "fresh":
            issues.append(_issue("source_stale" if catalog_freshness == "stale" else "source_date_unknown", qualification=True))
        classify, classification_unknown = _classification(bundle, partners)
        conflicts = _identity_conflicts(bundle, months)
        observations = [
            _observe(bundle[storage.monthly_ps_raw_path(month)], month, now, owners,
                     bindings, accounts, classify, classification_unknown, system_calendar,
                     identity_conflict=month in conflicts)
            for month in months
        ]
    except (InvalidSource, DecimalException, RecursionError) as error:
        code = error.code if isinstance(error, InvalidSource) else "invalid_source"
        issues.append(_issue(code))
    if ids and not selected:
        selected, balances, balance_currencies = _selected(
            _account_options(ids, owners, {}, {}), {}, now, system_calendar,
        )
    try:
        if not _stable(bundle):
            issues.append(_issue("sources_changing"))
    except InvalidSource:
        issues.append(_issue("invalid_source"))
    if any(i.code in {"sources_changing", "invalid_source", "ownership_incomplete"} and i.severity == "blocking" for i in issues):
        # Bundle uncertainty invalidates every derived monetary measure.
        observations = []
        balances = {key: None for key in balances}
        for account in selected:
            account.balance = None
            account.eligible = False
            account.issues.append(_issue("invalid_source", account_id=account.id))
    if not observations:
        observations = [Spending(_empty_observation(month, owners)) for month in months]
        for observation in observations:
            observation.row.coverage = "invalid"
            observation.row.issues = [i.model_copy(update={"month": observation.row.month}) for i in issues if i.severity == "blocking"]
    stamps = {
        _timestamp(value) for value in
        [catalog_date, *(ob.row.collected_at for ob in observations)] if value is not None
    }
    if len(stamps) > 1:
        issues.append(_issue("source_times_differ", qualification=True))
    owner_results = [
        OwnerResult(owner=owner, **_measures(owner.partner_id, ids, selected, balances,
                    balance_currencies, observations, issues).model_dump())
        for owner in owners
    ]
    household = _measures(None, ids, selected, balances, balance_currencies, observations, issues)
    included = [ob.row.month for ob in observations if ob.row.status == "included"]
    return RunwayResponse(
        calculated_at=now.isoformat(), as_of_month=now.strftime("%Y-%m"), candidate_months=months,
        included_months=included, included_month_count=len(included), selection_status=state,
        selected_account_ids=ids, selected_accounts=selected, catalog_collected_at=catalog_date,
        catalog_freshness=catalog_freshness, observations=[ob.row for ob in observations],
        owners=owner_results, household=household, issues=_unique(issues),
    )
