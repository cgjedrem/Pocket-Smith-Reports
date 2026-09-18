"""LG-002 containment guard: personal identifiers absent from the tracked tree.

Mirrors the three verification vectors of docs/open-source-launch-gates.md
(LG-002) so CI fails on any reintroduction:

1. Content vector — case-insensitive substring over tracked file contents.
2. Path vector    — tracked path names (git grep does not inspect these).
3. Encoded vector — base64 byte-offset-0 literals of the identifiers.

Carve-outs (identical to LG-002): .charter/, .specify/,
docs/open-source-launch-gates.md, and specs/001-depersonalize-identifiers/**
(the governance docs that must name the identifiers to be meaningful; they are
excluded from the published history-reset repo per LG-001).
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# Identifier strings are assembled from fragments so this guard does not trip
# its own scan (git grep/LG-002 make no exception for the guard file itself).
# IDs refer to the I-001/I-002/I-003 inventory in docs/open-source-launch-gates.md.
IDENTIFIER_PATTERN = (
    "chris" + "tian",  # I-001
    "ra" + "sma",  # I-002
    "gjed" + "rem",  # I-003
)
# Diminutive remnants (I-001/I-002 abbreviations) that the substring vector
# cannot cover without false positives — matched as case-insensitive
# whole words instead (fragments assembled, as above).
IDENTIFIER_WORD_REGEX = re.compile(
    r"\b(?:ch" + "ris|r" + "sm)\b",
    flags=re.IGNORECASE,
)
ENCODED_LITERALS = (
    "Q2hy" + "aXN0aWFu",  # base64, I-001 case-sensitive variant
    "Y2hy" + "aXN0aWFu",  # base64, I-001 lowercase variant
    "UmFz" + "bWE",  # base64, I-002 case-sensitive variant
    "cmFz" + "bWE",  # base64, I-002 lowercase variant
    "R2pl" + "ZHJlbQ",  # base64, I-003 case-sensitive variant
    "Z2pl" + "ZHJlbQ",  # base64, I-003 lowercase variant
)
ALLOWLIST_PREFIXES = (".charter/", ".specify/", "specs/001-depersonalize-identifiers/")
ALLOWLIST_PATHS = ("docs/open-source-launch-gates.md",)


def _tracked_paths() -> list[str]:
    raw = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
    ).split(b"\0")
    return [path.decode("utf-8") for path in raw if path]


def _is_carve_out(relative_path: str) -> bool:
    return relative_path in ALLOWLIST_PATHS or relative_path.startswith(
        ALLOWLIST_PREFIXES,
    )


def test_lg002_content_vector_has_no_identifiers_outside_carve_outs():
    matches = []
    for relative_path in _tracked_paths():
        if _is_carve_out(relative_path):
            continue
        path = ROOT / relative_path
        if not path.is_file():
            continue
        lowered = path.read_bytes().decode("utf-8", errors="ignore").lower()
        for identifier in IDENTIFIER_PATTERN:
            if identifier in lowered:
                matches.append(f"{relative_path}: contains '{identifier}'")
    assert not matches, "\n".join(matches)


def test_lg002_content_vector_has_no_identifier_diminutives():
    matches = []
    for relative_path in _tracked_paths():
        if _is_carve_out(relative_path):
            continue
        path = ROOT / relative_path
        if not path.is_file():
            continue
        text = path.read_bytes().decode("utf-8", errors="ignore")
        for hit in IDENTIFIER_WORD_REGEX.findall(text):
            matches.append(f"{relative_path}: contains diminutive '{hit}'")
    assert not matches, "\n".join(matches)


def test_lg002_path_vector_has_no_identifiers_in_tracked_paths():
    matches = []
    for relative_path in _tracked_paths():
        if _is_carve_out(relative_path):
            continue
        lowered = relative_path.lower()
        for identifier in IDENTIFIER_PATTERN:
            if identifier in lowered:
                matches.append(f"tracked path: {relative_path}")
    assert not matches, "\n".join(matches)


def test_lg002_encoded_vector_has_no_base64_literals():
    matches = []
    for relative_path in _tracked_paths():
        if _is_carve_out(relative_path):
            continue
        path = ROOT / relative_path
        if not path.is_file():
            continue
        text = path.read_bytes().decode("utf-8", errors="ignore")
        for literal in ENCODED_LITERALS:
            if literal in text:
                matches.append(f"{relative_path}: contains base64 '{literal}'")
    assert not matches, "\n".join(matches)
