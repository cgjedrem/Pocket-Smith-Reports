"""Atomic .env read/write — API_KEY line only.

No python-dotenv. Manual parse. Never returns raw key.
Validation (get_me probe) is done by routers/settings.py in a later slice.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from budget_api.services.storage import REPOSITORY_ROOT

ENV_PATH = REPOSITORY_ROOT / ".env"
_API_KEY_PREFIX = "API_KEY="


def read_api_key_configured() -> bool:
    """True if .env exists and has API_KEY=... with non-empty value. Never returns key."""
    if not ENV_PATH.exists():
        return False
    try:
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(_API_KEY_PREFIX):
            value = stripped[len(_API_KEY_PREFIX) :].strip()
            if value:
                return True
    return False


def read_api_key_value() -> str | None:
    """Return API key value or None if not configured. Internal/trusted callers only."""
    if not ENV_PATH.exists():
        return None
    try:
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(_API_KEY_PREFIX):
            value = stripped[len(_API_KEY_PREFIX) :].strip()
            if value:
                return value
    return None


def write_api_key(key: str) -> None:
    """Atomic .env write — replace or append API_KEY line, preserve all other lines.

    Temp file + os.replace for atomicity (mirrors storage.atomic_write_json pattern).
    """
    if not key or not key.strip():
        raise ValueError("API key must be non-empty")
    key = key.strip()
    existing_lines: list[str] = []
    if ENV_PATH.exists():
        try:
            existing_lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
        except OSError:
            existing_lines = []

    replaced = False
    out_lines: list[str] = []
    for line in existing_lines:
        if line.strip().startswith(_API_KEY_PREFIX):
            out_lines.append(f"{_API_KEY_PREFIX}{key}")
            replaced = True
        else:
            out_lines.append(line)
    if not replaced:
        out_lines.append(f"{_API_KEY_PREFIX}{key}")

    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(out_lines) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=ENV_PATH.parent, delete=False, suffix=".env.tmp"
    ) as temporary:
        temporary.write(content)
        tmp_path = Path(temporary.name)
    try:
        os.replace(tmp_path, ENV_PATH)
    except OSError:
        tmp_path.unlink(missing_ok=True)
        raise
