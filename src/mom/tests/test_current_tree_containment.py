"""Static containment guard for tracked relevant repository text."""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
PRIVATE_PATH = re.compile(
    r"(?:[a-zA-Z]:[\\/](?:[Uu]sers|[Hh]ome|[Tt]mp)[\\/]|/(?:Users|home|tmp)/)",
)
SENSITIVE_ASSIGNMENT = re.compile(
    r'(?im)^\s*(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password)(?:\s*:\s*[^=,\n]+)?\s*(?:=\s*(?![a-z_]\w*\s*\()["\']?\S+|:\s*["\']\S+)',
)
DATED_EXPORT_LITERAL = re.compile(
    r"(?i)\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)_20\d{2}\b",
)
ISO_DATE_LITERAL = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")
MOM_SUPPORTED_ENTRYPOINTS = ("build_mom.py", "render_mom.py")


def test_sensitive_assignment_permits_typed_parameter_annotations():
    assert not SENSITIVE_ASSIGNMENT.search("def request(\n    api_key: str,\n):\n")
    assert not SENSITIVE_ASSIGNMENT.search("api_key = _read_env_api_key()")
    assert SENSITIVE_ASSIGNMENT.search('api_key = "secret"')
    assert SENSITIVE_ASSIGNMENT.search('api_key: str = "secret"')
    assert SENSITIVE_ASSIGNMENT.search('api_key: "secret"')


def _tracked_text_paths() -> list[Path]:
    paths = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
    ).split(b"\0")
    tracked_paths = [
        ROOT / relative_path.decode("utf-8") for relative_path in paths if relative_path
    ]
    return [
        path
        for path in tracked_paths
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES
    ]


def test_tracked_relevant_text_has_no_private_paths_or_credentials():
    matches = []
    for path in _tracked_text_paths():
        text = path.read_text(encoding="utf-8")
        relative_path = path.relative_to(ROOT)
        for pattern in (PRIVATE_PATH, SENSITIVE_ASSIGNMENT):
            match = pattern.search(text)
            if match:
                matches.append(f"{relative_path}: {match.group(0)!r}")
    assert not matches, "\n".join(matches)


def test_legacy_v7_tree_uses_configured_periods_and_trip_matching():
    v7_dir = ROOT / "src" / "legacy" / "v7_mega"
    renderer = (v7_dir / "render_mega_v7.py").read_text(encoding="utf-8")
    compare = (v7_dir / "compare.py").read_text(encoding="utf-8")
    trips = (v7_dir / "trips.py").read_text(encoding="utf-8")

    assert "_resolve_month_path" in renderer
    assert "POCKETSMITH_DATA_DIR" in compare
    assert "resolve_month_input" in compare
    assert "MONTHS" in renderer
    assert not DATED_EXPORT_LITERAL.search(renderer)
    assert not ISO_DATE_LITERAL.search(trips)
    assert "location_keywords" in trips
    assert "trip_keywords" in trips
    assert "anchor_amount" in trips
    assert "split_gap_days" in trips
    assert "glob.glob" not in trips


def test_legacy_v7_trips_cli_is_unsupported():
    trips = ROOT / "src" / "legacy" / "v7_mega" / "trips.py"

    result = subprocess.run(
        [sys.executable, str(trips), "*.json"],
        capture_output=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode != 0
    assert "Unsupported: legacy trips.py CLI" in result.stderr


def test_mom_current_tree_uses_strict_monthly_input_contract():
    mom_dir = ROOT / "src" / "mom"
    data_module = (mom_dir / "data.py").read_text(encoding="utf-8")
    build_module = (mom_dir / "build_mom.py").read_text(encoding="utf-8")
    entrypoint_modules = {
        entrypoint: (mom_dir / entrypoint).read_text(encoding="utf-8")
        for entrypoint in MOM_SUPPORTED_ENTRYPOINTS
    }

    assert "resolve_month_input" in data_module
    assert "resolve_month_input" in build_module
    for module in (data_module, *entrypoint_modules.values()):
        assert "yr == 2025" not in module
        assert not DATED_EXPORT_LITERAL.search(module)
