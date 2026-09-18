import json
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

from input_contract import InputContractError, monthly_filename, resolve_month_input

PULL_SCRIPT = Path(__file__).resolve().parents[2] / "pull-month-ps-paginate.py"


def _load_pull_script():
    spec = importlib.util.spec_from_file_location("pull_month_ps_paginate", PULL_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_monthly_filename_uses_exact_live_and_synthetic_contracts():
    assert monthly_filename("2026-04", "live") == "2026-04_ps_raw.json"
    assert monthly_filename("2026-04", "synthetic") == "sample_apr_2026.json"


def test_resolver_selects_only_the_explicit_source_kind(tmp_path: Path):
    live_path = tmp_path / "2026-04_ps_raw.json"
    fixture_path = tmp_path / "sample_apr_2026.json"
    live_path.write_text(json.dumps({"source": "live"}), encoding="utf-8")
    fixture_path.write_text(json.dumps({"source": "synthetic"}), encoding="utf-8")

    assert resolve_month_input("2026-04", tmp_path, "live") == live_path
    assert resolve_month_input("2026-04", tmp_path, "synthetic") == fixture_path


def test_resolver_rejects_alternate_filename_without_fallback(tmp_path: Path):
    (tmp_path / "ps_apr_2026.json").write_text("{}", encoding="utf-8")

    with pytest.raises(InputContractError, match="Required month 2026-04 is missing"):
        resolve_month_input("2026-04", tmp_path, "live")


def test_resolver_rejects_bad_input_before_publish(tmp_path: Path):
    (tmp_path / "2026-04_ps_raw.json").write_text("not json", encoding="utf-8")

    with pytest.raises(InputContractError, match="Required month 2026-04 is invalid"):
        resolve_month_input("2026-04", tmp_path, "live")


def test_pull_script_is_disabled_before_credential_or_snapshot_access():
    pull_script = _load_pull_script()

    with pytest.raises(SystemExit) as error:
        pull_script.main([])

    assert error.value.code == 2


def test_pull_script_cli_reports_staged_sync_migration():
    result = subprocess.run(
        [sys.executable, str(PULL_SCRIPT), "2026", "4"],
        capture_output=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 2
    assert "Legacy one-month sync is disabled" in result.stderr
    assert "src/live_sync.py transactions" in result.stderr
