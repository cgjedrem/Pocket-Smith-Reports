"""Strict monthly source filename contract for report inputs."""

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

InputKind = Literal["live", "synthetic"]
MONTH_NAMES = (
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
)


class InputContractError(ValueError):
    """Raised when a required monthly input violates the contract."""


def monthly_filename(month: str, input_kind: InputKind) -> str:
    """Return exact required filename for one YYYY-MM report month."""
    try:
        parsed = datetime.strptime(month, "%Y-%m")
    except ValueError as error:
        raise InputContractError(f"Month must use YYYY-MM: {month!r}") from error
    if parsed.strftime("%Y-%m") != month:
        raise InputContractError(f"Month must use YYYY-MM: {month!r}")
    if input_kind == "live":
        return f"{month}_ps_raw.json"
    if input_kind == "synthetic":
        return f"sample_{MONTH_NAMES[parsed.month - 1]}_{parsed.year}.json"
    raise InputContractError(f"Unsupported input kind: {input_kind!r}")


def resolve_month_input(month: str, data_dir: Path, input_kind: InputKind) -> Path:
    """Return readable, valid JSON input at its exact contract path."""
    path = Path(data_dir) / monthly_filename(month, input_kind)
    if not path.is_file():
        raise InputContractError(f"Required month {month} is missing: {path}")
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InputContractError(
            f"Required month {month} is invalid: {path}"
        ) from error
    return path
