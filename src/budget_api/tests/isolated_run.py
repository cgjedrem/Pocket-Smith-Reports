"""Opt-in synthetic-only pytest runner/plugin. PYTEST_DONT_REWRITE."""

from __future__ import annotations

from contextlib import contextmanager, ExitStack
import os
from pathlib import Path
import runpy
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import threading

import pytest

_installed = False
_audit_installed = False
_renderer_roots = set()
_launch = threading.local()
_root = Path(__file__).resolve().parents[3]
_temporary_roots = {
    os.path.normcase(path).replace("\\", "/").removeprefix("//?/").rstrip("/")
    for path in (tempfile.gettempdir(), os.path.realpath(tempfile.gettempdir()))
}


class UnsafeTestAccess(RuntimeError):
    pass


def guard_path(value) -> None:
    if not isinstance(value, (str, bytes, os.PathLike)):
        return
    value = os.fsdecode(value)

    def check(value):
        path = os.path.normcase(value).replace("\\", "/").removeprefix("//?/")
        if any(path.startswith(root + "/") for root in _temporary_roots):
            return
        if "/data/private" in path or path.endswith("/.env"):
            raise UnsafeTestAccess("Protected financial path blocked by synthetic test guard")
    check(os.path.abspath(value))
    check(os.path.realpath(value))


def _renderer_options(command, kwargs):
    extractor = shutil.which("pdftotext")
    if (not extractor or len(command) != 3 or command[0] != extractor or command[2] != "-"
            or kwargs.get("env") is not None):
        raise UnsafeTestAccess("Unisolated subprocess blocked by synthetic test guard")
    executable = Path(extractor).resolve()
    if any(executable.is_relative_to(Path(root)) for root in _temporary_roots):
        raise UnsafeTestAccess("Temporary renderer executable blocked by synthetic test guard")
    pdf = Path(command[1])
    guard_path(pdf)
    resolved = pdf.resolve()
    if (not pdf.is_absolute() or pdf.suffix.lower() != ".pdf" or not pdf.is_file()
            or not any(resolved.is_relative_to(root) for root in _renderer_roots)):
        raise UnsafeTestAccess("Renderer input must be an isolated temporary PDF")
    if kwargs.get("cwd") is not None and Path(kwargs["cwd"]).resolve() != resolved.parent:
        raise UnsafeTestAccess("Renderer cwd must match isolated PDF directory")
    if kwargs.get("stdout") != subprocess.PIPE or kwargs.get("stderr") != subprocess.PIPE:
        raise UnsafeTestAccess("Renderer output must be captured, not written to files")
    if kwargs.get("stdin") not in (None, subprocess.DEVNULL):
        raise UnsafeTestAccess("Renderer stdin must be disabled")
    return {**kwargs, "cwd": str(resolved.parent), "stdin": subprocess.DEVNULL}


def _library_cache_options(command, kwargs):
    trusted = {"/sbin/ldconfig", "/usr/sbin/ldconfig"}
    expected = {
        "stdin": subprocess.DEVNULL, "stdout": subprocess.PIPE,
        "stderr": subprocess.DEVNULL, "env": {"LC_ALL": "C", "LANG": "C"},
    }
    if (sys.platform != "linux" or len(command) != 2
            or command[0] not in trusted or command[1] != "-p" or kwargs != expected):
        raise UnsafeTestAccess("Only exact read-only system library-cache lookup allowed")
    executable = Path(command[0]).resolve()
    if executable.as_posix() not in trusted:
        raise UnsafeTestAccess("Untrusted library-cache executable blocked")
    metadata = executable.stat()
    if (metadata.st_uid != 0 or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_mode & 0o022 or not metadata.st_mode & 0o111):
        raise UnsafeTestAccess("Library-cache executable must be root-owned and non-writable")
    return kwargs


def install_guards() -> None:
    global _installed, _audit_installed
    if _installed:
        return
    os.environ["BILLS_CALC_LOG"] = "0"
    os.environ.pop("POCKET_SMITH_API_KEY_FILE", None)
    original_popen = subprocess.Popen

    class GuardedPopen(original_popen):
        def __init__(self, args, *positional, **kwargs):
            if kwargs.get("shell") or kwargs.get("executable") or not isinstance(args, (list, tuple)):
                raise UnsafeTestAccess("Unisolated subprocess blocked by synthetic test guard")
            command = list(args)
            if command == ["git", "-C", str(_root), "ls-files", "-z"]:
                pass
            elif command and command[0] == sys.executable:
                command = [sys.executable, "-m", "budget_api.tests.isolated_run", "--child", *command[1:]]
            else:
                if positional:
                    raise UnsafeTestAccess("Renderer options must use keyword arguments")
                if command and command[0] in {"/sbin/ldconfig", "/usr/sbin/ldconfig"}:
                    kwargs = _library_cache_options(command, kwargs)
                else:
                    kwargs = _renderer_options(command, kwargs)
            _launch.command = subprocess.list2cmdline(command) if os.name == "nt" else command
            try:
                super().__init__(command, *positional, **kwargs)
            finally:
                _launch.command = None

    subprocess.Popen = GuardedPopen

    def audit(event, args):
        if not _installed:
            return
        if event in {"open", "os.listdir", "os.scandir", "os.remove", "os.mkdir", "os.rmdir"}:
            guard_path(args[0])
        elif event in {"os.rename", "os.link", "os.symlink"}:
            guard_path(args[0])
            guard_path(args[1])
        elif event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
            # Windows asyncio self-pipe only. Match stdlib frame and exact socket.
            caller = sys._getframe(1)
            fallback = getattr(socket, "_fallback_socketpair", None)
            if (event == "socket.connect" and fallback is not None
                    and caller.f_code is fallback.__code__
                    and args[0] is caller.f_locals.get("csock")
                    and args[1] == (caller.f_locals.get("addr"), caller.f_locals.get("port"))):
                return
            raise UnsafeTestAccess("External network blocked by synthetic test guard")
        elif event == "subprocess.Popen":
            # Wrapper-approved listing, guarded Python, native lookup, temp PDF only.
            if getattr(_launch, "command", None) != args[1]:
                raise UnsafeTestAccess("Unisolated subprocess blocked by synthetic test guard")

    if not _audit_installed:
        sys.addaudithook(audit)
        _audit_installed = True
    _installed = True


@contextmanager
def guarded(directory=None):
    """Activate guards for this scope; leave unrelated pytest tests unchanged."""
    global _installed
    active, popen = _installed, subprocess.Popen
    environment = {key: os.environ.get(key) for key in ("BILLS_CALC_LOG", "POCKET_SMITH_API_KEY_FILE")}
    roots = _renderer_roots.copy()
    if directory is not None:
        root = Path(directory).resolve()
        if not any(root.is_relative_to(Path(temp)) for temp in _temporary_roots):
            raise UnsafeTestAccess("Isolation root must be temporary")
    install_guards()
    if directory is not None:
        _renderer_roots.add(root)
    try:
        yield
    finally:
        _renderer_roots.clear()
        _renderer_roots.update(roots)
        if not active:
            _installed = False
            subprocess.Popen = popen
            for key, value in environment.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


@contextmanager
def redirected_paths(directory):
    """Redirect storage and imported legacy aliases; restore on scope exit."""
    from budget_api.services import env_writer, storage

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    private_roots = {storage.PRIVATE_DATA_DIR, _root / "data" / "private"}
    with ExitStack() as stack:
        previous_env_file = os.environ.get("ENV_FILE")
        if previous_env_file is None:
            stack.callback(os.environ.pop, "ENV_FILE", None)
        else:
            stack.callback(os.environ.__setitem__, "ENV_FILE", previous_env_file)
        os.environ["ENV_FILE"] = str(directory.parent / ".env")
        for module in tuple(sys.modules.values()):
            filename = getattr(module, "__file__", None)
            if not filename or not str(filename).startswith(str(_root / "src")):
                continue
            for name, value in tuple(vars(module).items()):
                if not isinstance(value, Path):
                    continue
                target = None
                if name == "PRIVATE_DATA_DIR":
                    target = directory
                elif name in {"ENV_PATH", "ENV_FILE"}:
                    target = directory.parent / ".env"
                elif value.parent in private_roots:
                    target = directory / value.name
                if target is not None:
                    stack.callback(setattr, module, name, value)
                    setattr(module, name, target)
        yield directory


@contextmanager
def isolated_environment():
    """Fresh temporary defaults before app imports; no server or live data."""
    with tempfile.TemporaryDirectory(prefix="runway-suite-") as directory:
        with guarded(directory), redirected_paths(Path(directory) / "private") as private:
            yield private


@pytest.hookimpl(tryfirst=True)
def pytest_load_initial_conftests(early_config, parser, args):
    # Explicit -p only. Run before any feature/legacy conftest imports.
    stack = ExitStack()
    early_config.add_cleanup(stack.close)
    private = stack.enter_context(isolated_environment())
    early_config.option.basetemp = str(private.parent / "tests")


@pytest.fixture(autouse=True)
def private_defaults(tmp_path):
    # Plugin opt-in. Catch imported legacy aliases before each test.
    with redirected_paths(tmp_path / "isolated-defaults"):
        yield


def main() -> int:
    os.environ["BILLS_CALC_LOG"] = "0"
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    if sys.argv[1:2] == ["--child"]:
        with isolated_environment():
            args = sys.argv[2:]
            if args[:1] == ["-m"] and len(args) >= 2:
                sys.argv = args[1:]
                runpy.run_module(args[1], run_name="__main__", alter_sys=True)
            elif args and args[0].endswith(".py"):
                sys.argv = args
                runpy.run_path(args[0], run_name="__main__")
            else:
                raise UnsafeTestAccess("Unsupported child invocation")
            return 0
    return pytest.main([
        *sys.argv[1:], "-p", "budget_api.tests.isolated_run", "-p", "pytest_asyncio.plugin",
    ])


if __name__ == "__main__":
    from budget_api.tests.isolated_run import main as run
    raise SystemExit(run())
