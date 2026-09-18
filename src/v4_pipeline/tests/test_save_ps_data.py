"""Tests for local PocketSmith export save CLI failures."""

import sys

import pytest

import save_ps_data


def test_cli_reports_invalid_month_as_parser_error(tmp_path, monkeypatch, capsys):
    source = tmp_path / "export.json"
    source.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["save_ps_data.py", str(source), "--month", "2030-4"],
    )

    with pytest.raises(SystemExit, match="2"):
        save_ps_data.main()

    error = capsys.readouterr().err
    assert "Month must use YYYY-MM" in error
    assert "Traceback" not in error


def test_cli_reports_missing_source_as_parser_error(tmp_path, monkeypatch, capsys):
    missing_source = tmp_path / "missing.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["save_ps_data.py", str(missing_source), "--month", "2030-04"],
    )

    with pytest.raises(SystemExit, match="2"):
        save_ps_data.main()

    error = capsys.readouterr().err
    assert "Source export not found" in error
    assert "Traceback" not in error


def test_cli_reports_copy_error_as_parser_error(tmp_path, monkeypatch, capsys):
    source = tmp_path / "export.json"
    source.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["save_ps_data.py", str(source), "--month", "2030-04"],
    )

    def fail_copy(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(save_ps_data.shutil, "copyfile", fail_copy)

    with pytest.raises(SystemExit, match="2"):
        save_ps_data.main()

    error = capsys.readouterr().err
    assert "Could not save local export" in error
    assert "disk full" in error
    assert "Traceback" not in error
