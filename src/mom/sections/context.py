"""Shared display context for MoM section renderers."""

from html import escape

DEFAULT_PARTNER_LABELS = {"partner_a": "Partner A", "partner_b": "Partner B"}


def labels(value: dict[str, str] | None = None) -> dict[str, str]:
    """Return safe partner display labels with neutral defaults."""
    return {**DEFAULT_PARTNER_LABELS, **(value or {})}


def heading(number: int | None, title: str) -> str:
    """Build a section heading supplied by a caller-owned registry."""
    prefix = f"{number}. " if number is not None else ""
    return f"{prefix}{escape(title)}"
