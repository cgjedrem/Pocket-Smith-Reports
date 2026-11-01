from pathlib import Path
import os
import runpy
import socket
import stat
import subprocess
import sys
from types import SimpleNamespace

import pytest

from budget_api.tests.isolated_run import UnsafeTestAccess, guard_path


@pytest.fixture
def renderer_probe(tmp_path, monkeypatch):
    from budget_api.tests import isolated_run
    executable = str(Path(sys.base_prefix) / ("pdftotext.exe" if os.name == "nt" else "pdftotext"))
    monkeypatch.setattr(isolated_run.shutil, "which", lambda name: executable if name == "pdftotext" else None)
    pdf = tmp_path / "synthetic.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    return [executable, str(pdf), "-"], {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE}


def test_renderer_accepts_only_isolated_pdf_and_captured_output(renderer_probe):
    from budget_api.tests.isolated_run import _renderer_options
    command, kwargs = renderer_probe
    options = _renderer_options(command, kwargs)
    assert options == {**kwargs, "cwd": str(Path(command[1]).parent), "stdin": subprocess.DEVNULL}


def test_renderer_wrapper_reaches_launch_only_after_validation(renderer_probe, monkeypatch):
    command, kwargs = renderer_probe
    calls = []

    class SyntheticLaunchStopped(Exception):
        pass

    def intercept(self, args, *positional, **options):
        calls.append(args)
        raise SyntheticLaunchStopped()

    monkeypatch.setattr(subprocess.Popen, "_execute_child", intercept)
    with pytest.raises(SyntheticLaunchStopped):
        subprocess.Popen(command, **kwargs)
    assert calls == [command]


@pytest.mark.parametrize("change", [
    "other_executable", "temporary_executable", "protected_pdf", "outside_isolation",
    "relative_pdf", "non_pdf", "output_file", "extra_flag", "cwd", "env", "stdout", "stdin",
])
def test_renderer_rejects_unscoped_commands(renderer_probe, tmp_path, monkeypatch, change):
    from budget_api.tests import isolated_run
    command, kwargs = renderer_probe
    if change == "other_executable":
        command[0] += ".other"
    elif change == "temporary_executable":
        command[0] = str(tmp_path / "pdftotext")
        monkeypatch.setattr(isolated_run.shutil, "which", lambda name: command[0])
    elif change == "protected_pdf":
        command[1] = str(Path.cwd() / "data/private/never-open-sentinel.pdf")
    elif change == "outside_isolation":
        monkeypatch.setattr(isolated_run, "_renderer_roots", set())
    elif change == "relative_pdf":
        command[1] = "synthetic.pdf"
    elif change == "non_pdf":
        command[1] = str(tmp_path / "synthetic.json")
    elif change == "output_file":
        command[2] = str(tmp_path / "output.txt")
    elif change == "extra_flag":
        command.append("-opw")
    else:
        kwargs[change] = {
            "cwd": str(Path.cwd()), "env": {}, "stdout": None, "stdin": subprocess.PIPE,
        }[change]
    with pytest.raises(UnsafeTestAccess):
        isolated_run._renderer_options(command, kwargs)


def test_renderer_rejects_shell_and_executable_overrides(renderer_probe):
    command, kwargs = renderer_probe
    for override in [{"shell": True}, {"executable": command[0]}]:
        with pytest.raises(UnsafeTestAccess):
            subprocess.Popen(command, **kwargs, **override)


@pytest.fixture
def library_cache_probe(monkeypatch):
    from budget_api.tests import isolated_run
    monkeypatch.setattr(isolated_run.sys, "platform", "linux")
    resolve, path_stat = Path.resolve, Path.stat
    trusted = {"/sbin/ldconfig", "/usr/sbin/ldconfig"}
    metadata = SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG | 0o755)
    monkeypatch.setattr(Path, "resolve", lambda self, **kw:
                        Path("/usr/sbin/ldconfig") if self.as_posix() in trusted else resolve(self, **kw))
    monkeypatch.setattr(Path, "stat", lambda self, **kw:
                        metadata if self.as_posix() in trusted else path_stat(self, **kw))
    return ["/sbin/ldconfig", "-p"], {
        "stdin": subprocess.DEVNULL, "stdout": subprocess.PIPE,
        "stderr": subprocess.DEVNULL, "env": {"LC_ALL": "C", "LANG": "C"},
    }, metadata


@pytest.mark.parametrize("executable", ["/sbin/ldconfig", "/usr/sbin/ldconfig"])
def test_library_cache_exact_read_only_lookup_reaches_launch(library_cache_probe, monkeypatch, executable):
    command, kwargs, _ = library_cache_probe
    command[0] = executable
    calls = []

    class SyntheticLaunchStopped(Exception):
        pass

    def intercept(self, args, *positional, **options):
        calls.append(args)
        raise SyntheticLaunchStopped()

    monkeypatch.setattr(subprocess.Popen, "_execute_child", intercept)
    with pytest.raises(SyntheticLaunchStopped):
        subprocess.Popen(command, **kwargs)
    assert calls == [command]


@pytest.mark.parametrize("change", [
    "modify", "extra_args", "relative", "temporary", "symlink", "owner", "writable",
    "non_executable", "directory", "platform", "env", "cwd", "stdout", "stdin", "stderr",
    "shell", "executable", "preexec_fn", "positional",
])
def test_library_cache_rejects_unsafe_variants(library_cache_probe, tmp_path, monkeypatch, change):
    from budget_api.tests import isolated_run
    command, kwargs, metadata = library_cache_probe
    if change == "modify":
        command.pop()
    elif change == "extra_args":
        command += ["-C", str(tmp_path / "cache")]
    elif change == "relative":
        command[0] = "ldconfig"
    elif change == "temporary":
        command[0] = str(tmp_path / "ldconfig")
    elif change == "symlink":
        monkeypatch.setattr(Path, "resolve", lambda self, **kw: tmp_path / "ldconfig")
    elif change == "owner":
        metadata.st_uid = 1000
    elif change == "writable":
        metadata.st_mode |= stat.S_IWGRP
    elif change == "non_executable":
        metadata.st_mode &= ~0o111
    elif change == "directory":
        metadata.st_mode = stat.S_IFDIR | 0o755
    elif change == "platform":
        monkeypatch.setattr(isolated_run.sys, "platform", "win32")
    elif change != "positional":
        kwargs[change] = {
            "env": {"LD_PRELOAD": "/untrusted.so"}, "cwd": str(tmp_path),
            "stdout": None, "stdin": subprocess.PIPE, "stderr": None,
            "shell": True, "executable": command[0], "preexec_fn": lambda: None,
        }[change]
    with pytest.raises(UnsafeTestAccess):
        subprocess.Popen(command, *([0] if change == "positional" else []), **kwargs)


def test_feature_conftest_import_does_not_install_process_guards(monkeypatch):
    from budget_api.tests import isolated_run
    calls = []
    monkeypatch.setattr(isolated_run, "install_guards", lambda: calls.append("installed"))
    before = subprocess.Popen
    runpy.run_path(str(Path(__file__).with_name("conftest.py")))
    assert calls == []
    assert subprocess.Popen is before


def test_ordinary_pytest_plugin_handles_feature_collection_and_legacy_aliases():
    root = Path(__file__).resolve().parents[4]
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "-p", "budget_api.tests.isolated_run", "-p", "pytest_asyncio.plugin",
        str(root / "src/v4_pipeline/tests/test_save_ps_data.py"),
        str(root / "src/budget_api/tests/runway/test_calculation.py") + "::test_contract_arithmetic_and_no_source_writes",
        "-q",
    ], capture_output=True, text=True, cwd=root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "4 passed" in result.stdout


def test_fresh_process_synthetic_integration_recipe(tmp_path):
    script = tmp_path / "synthetic_route_probe.py"
    script.write_text(
        """import os
import sys
import time
from unittest.mock import patch
from budget_api.tests.isolated_run import isolated_environment
from budget_api.tests.runway.synthetic import A, MONTHS, NOW, World

assert os.environ["BILLS_CALC_LOG"] == "0"
assert "budget_api.main" not in sys.modules
with isolated_environment() as private:
    from budget_api.services import env_writer, storage
    assert storage.PRIVATE_DATA_DIR == private
    assert env_writer.ENV_PATH == private.parent / ".env"
    assert os.environ["ENV_FILE"] == str(env_writer.ENV_PATH)
    assert not env_writer.ENV_PATH.exists()
    world = World(private)
    world.use_large_history()
    assert len(world.data["account_mappings.json"]["accounts"]) == 20
    assert sum(len(world.data[f"{month}_ps_raw.json"]["transactions"]) for month in MONTHS) == 10000
    world.write()
    before = {p.name: p.read_bytes() for p in private.iterdir() if p.name != "runway_config.json"}
    from budget_api.services import runway
    from budget_api.main import app
    from fastapi.testclient import TestClient
    with patch.object(runway, "local_now", lambda: NOW), TestClient(app) as client:
        settings = client.get("/api/settings/runway")
        assert settings.status_code == 200
        started = time.perf_counter()
        response = client.get("/api/bills/runway")
        elapsed = time.perf_counter() - started
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        body = response.json()
        assert body["included_months"] == MONTHS
        assert abs(body["household"]["average_monthly_spending"] - 100000 / 3) < 1e-8
        assert body["household"]["runway_display"] == "3.6"
        assert elapsed < 2
        saved = client.put("/api/settings/runway", json={"liquid_account_ids": [A]})
        assert saved.status_code == 200
        assert client.get("/api/bills/runway").json()["household"]["reserves"] == 90000
        assert client.get("/api/bills/dashboard?month=2026-10").status_code == 404
    assert before == {p.name: p.read_bytes() for p in private.iterdir() if p.name != "runway_config.json"}
    print(f"Synthetic ASGI: 10000 transactions, 20 mappings, {elapsed:.3f}s")
""",
        encoding="utf-8",
    )
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Synthetic ASGI: 10000 transactions, 20 mappings" in result.stdout
    print(result.stdout.strip())


def test_protected_sentinel_rejected_without_opening():
    root = Path.cwd()
    for path in [root / "data/private/never-open-sentinel.json", root / ".env"]:
        for value in [path, str(path), os.fsencode(path)]:
            with pytest.raises(UnsafeTestAccess):
                guard_path(value)


def test_temp_alias_cannot_bypass_protected_path_guard(tmp_path, monkeypatch):
    original = os.path.realpath
    alias = tmp_path / "synthetic-alias.json"
    protected = Path.cwd() / "data/private/never-open-sentinel.json"
    monkeypatch.setattr(
        os.path, "realpath",
        lambda value, **kwargs: str(protected) if os.fsdecode(value) == str(alias) else original(value, **kwargs),
    )
    with pytest.raises(UnsafeTestAccess):
        guard_path(alias)


def test_network_fails_before_connection():
    with socket.socket() as connection:
        with pytest.raises(UnsafeTestAccess):
            connection.connect(("127.0.0.1", 9))


def test_storage_and_env_are_temporary(tmp_private_dir, tmp_env_file):
    from budget_api.services import storage, env_writer
    assert storage.PRIVATE_DATA_DIR == tmp_private_dir
    assert env_writer.ENV_PATH == tmp_env_file
    assert not tmp_env_file.exists()


def test_child_interpreter_inherits_financial_path_guard(tmp_path):
    script = tmp_path / "synthetic_guard_probe.py"
    script.write_text(
        "from pathlib import Path\n"
        "from budget_api.tests.isolated_run import UnsafeTestAccess\n"
        "try:\n"
        "    (Path.cwd() / 'data/private/never-open-sentinel.json').read_bytes()\n"
        "except UnsafeTestAccess:\n"
        "    print('guarded')\n"
        "else:\n"
        "    raise AssertionError('guard missing')\n",
        encoding="utf-8",
    )
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "guarded"


def test_arbitrary_subprocess_blocked():
    with pytest.raises(UnsafeTestAccess):
        subprocess.run(["not-an-allowed-command"])
