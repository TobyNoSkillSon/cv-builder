from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import venv
from dataclasses import dataclass
from pathlib import Path

from .paths import data_root, default_bin_dir

_RECEIPT_SCHEMA = 1
_TOOL_NAME = "cv-builder"
_MANAGED_MARKER = "cv-builder managed launcher"


class InstallerError(RuntimeError):
    pass


@dataclass(frozen=True)
class InstallPaths:
    root: Path
    browser_dir: Path
    receipt: Path
    fallback_env: Path
    bin_dir: Path

    @classmethod
    def defaults(cls) -> "InstallPaths":
        root = data_root()
        return cls(
            root=root,
            browser_dir=root / "browsers",
            receipt=root / "install.json",
            fallback_env=root / "venv",
            bin_dir=default_bin_dir(),
        )


def _run(
    command: list[str | Path],
    *,
    env: dict[str, str] | None = None,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(item) for item in command],
        check=True,
        text=True,
        env=env,
        capture_output=capture,
    )


def _environment_python(environment: Path) -> Path:
    candidates = (
        environment / "Scripts" / "python.exe",
        environment / "bin" / "python",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise InstallerError(f"cannot locate Python in installed environment: {environment}")


def _is_windows() -> bool:
    return os.name == "nt"


def _launcher_candidates(bin_dir: Path) -> tuple[Path, ...]:
    if _is_windows():
        return (bin_dir / "cv-builder.exe", bin_dir / "cv-builder.cmd", bin_dir / "cv-builder")
    return (bin_dir / "cv-builder",)


def _find_launcher(bin_dir: Path) -> Path:
    for candidate in _launcher_candidates(bin_dir):
        if candidate.exists() or candidate.is_symlink():
            return candidate
    raise InstallerError(f"installation did not create a cv-builder launcher in {bin_dir}")


def _browser_environment(paths: InstallPaths) -> dict[str, str]:
    environment = os.environ.copy()
    environment["PLAYWRIGHT_BROWSERS_PATH"] = str(paths.browser_dir)
    environment["CV_BUILDER_HOME"] = str(paths.root)
    return environment


def _write_receipt(paths: InstallPaths, payload: dict[str, object]) -> None:
    paths.root.mkdir(parents=True, exist_ok=True)
    temporary = paths.root / ".install.json.tmp"
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, paths.receipt)


def _read_receipt(paths: InstallPaths) -> dict[str, object] | None:
    if not paths.receipt.is_file():
        return None
    try:
        value = json.loads(paths.receipt.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallerError(f"cannot read installation receipt {paths.receipt}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema") != _RECEIPT_SCHEMA:
        raise InstallerError(f"unsupported installation receipt: {paths.receipt}")
    return value


def _path_on_path(directory: Path) -> bool:
    target = os.path.normcase(str(directory.resolve()))
    return any(
        os.path.normcase(str(Path(item).expanduser().resolve())) == target
        for item in os.environ.get("PATH", "").split(os.pathsep)
        if item
    )


def _install_browser(python: Path, paths: InstallPaths) -> None:
    if paths.browser_dir.is_symlink():
        raise InstallerError(f"refusing symlinked private browser directory: {paths.browser_dir}")
    paths.browser_dir.mkdir(parents=True, exist_ok=True)
    _run([python, "-m", "playwright", "install", "chromium"], env=_browser_environment(paths))


def _cmd_escape(value: Path) -> str:
    return str(value).replace("%", "%%")


def _write_managed_launcher(launcher: Path, python: Path, root: Path, *, replace: bool = False) -> Path:
    launcher.parent.mkdir(parents=True, exist_ok=True)
    if launcher.exists() or launcher.is_symlink():
        existing = launcher.read_text(encoding="utf-8", errors="replace") if launcher.is_file() else ""
        if not replace and _MANAGED_MARKER not in existing:
            raise InstallerError(f"refusing to replace existing launcher not owned by CV Builder: {launcher}")
        launcher.unlink()
    if _is_windows():
        content = (
            f"@echo off\r\nREM {_MANAGED_MARKER}\r\n"
            f'set "CV_BUILDER_HOME={_cmd_escape(root)}"\r\n'
            f'"{_cmd_escape(python)}" -m cv_builder.cli %*\r\n'
        )
    else:
        content = (
            f"#!/bin/sh\n# {_MANAGED_MARKER}\n"
            f"export CV_BUILDER_HOME={shlex.quote(str(root))}\n"
            f"exec {shlex.quote(str(python))} -m cv_builder.cli \"$@\"\n"
        )
    launcher.write_text(content, encoding="utf-8")
    if not _is_windows():
        launcher.chmod(0o755)
    return launcher


def _install_with_uv(repo: Path, uv: Path, paths: InstallPaths) -> dict[str, object]:
    tool_dir = Path(_run([uv, "tool", "dir"], capture=True).stdout.strip()).expanduser().resolve()
    bin_dir = Path(_run([uv, "tool", "dir", "--bin"], capture=True).stdout.strip()).expanduser().resolve()
    environment = tool_dir / _TOOL_NAME
    launcher = bin_dir / ("cv-builder.cmd" if _is_windows() else "cv-builder")
    if launcher.exists() or launcher.is_symlink():
        existing = launcher.read_text(encoding="utf-8", errors="replace") if launcher.is_file() else ""
        if _MANAGED_MARKER not in existing:
            raise InstallerError(f"refusing to replace existing launcher not owned by CV Builder: {launcher}")
    receipt = {
        "schema": _RECEIPT_SCHEMA,
        "method": "uv",
        "environment": str(environment),
        "launcher": str(launcher),
        "browser_dir": str(paths.browser_dir),
        "uv": str(uv),
        "uv_tool_dir": str(tool_dir),
        "uv_bin_dir": str(bin_dir),
    }
    _write_receipt(paths, receipt)
    _run([uv, "tool", "install", "--force", str(repo)])
    python = _environment_python(environment)
    generated = _find_launcher(bin_dir)
    if generated != launcher and (generated.exists() or generated.is_symlink()):
        generated.unlink()
    launcher = _write_managed_launcher(launcher, python, paths.root, replace=True)
    _install_browser(python, paths)
    _run([launcher, "--help"], env=_browser_environment(paths), capture=True)
    return receipt


def _write_fallback_launcher(paths: InstallPaths, python: Path) -> Path:
    launcher = paths.bin_dir / ("cv-builder.cmd" if _is_windows() else "cv-builder")
    return _write_managed_launcher(launcher, python, paths.root)


def _install_with_venv(repo: Path, paths: InstallPaths) -> dict[str, object]:
    launcher = paths.bin_dir / ("cv-builder.cmd" if _is_windows() else "cv-builder")
    receipt = {
        "schema": _RECEIPT_SCHEMA,
        "method": "venv",
        "environment": str(paths.fallback_env),
        "launcher": str(launcher),
        "browser_dir": str(paths.browser_dir),
        "uv": None,
    }
    _write_receipt(paths, receipt)
    venv.EnvBuilder(with_pip=True, clear=True).create(paths.fallback_env)
    python = _environment_python(paths.fallback_env)
    _run([python, "-m", "pip", "install", str(repo)])
    _install_browser(python, paths)
    launcher = _write_fallback_launcher(paths, python)
    _run([launcher, "--help"], env=_browser_environment(paths), capture=True)
    return receipt


def install(repo: Path, *, paths: InstallPaths | None = None) -> int:
    try:
        if sys.version_info < (3, 11):
            raise InstallerError("CV Builder requires Python 3.11 or newer")
        repo = repo.resolve()
        if not (repo / "pyproject.toml").is_file() or not (repo / "SKILL.md").is_file():
            raise InstallerError(f"not a CV Builder repository: {repo}")
        paths = paths or InstallPaths.defaults()
        existing = _read_receipt(paths)
        uv_value = None if os.environ.get("CV_BUILDER_DISABLE_UV") == "1" else shutil.which("uv")
        method = "uv" if uv_value else "venv"
        if existing and existing.get("method") != method:
            raise InstallerError(
                f"CV Builder is already installed with {existing.get('method')}; run uninstall.py before changing installer method"
            )

        print("Installing CV Builder CLI only. Harness skills are not modified.")
        print(f"Method: {'uv tool' if uv_value else 'Python venv and pip fallback'}")
        print(f"Private browser/data directory: {paths.root}")
        paths.root.mkdir(parents=True, exist_ok=True)
        if uv_value:
            receipt = _install_with_uv(repo, Path(uv_value).resolve(), paths)
        else:
            receipt = _install_with_venv(repo, paths)
        _write_receipt(paths, receipt)

        launcher = Path(str(receipt["launcher"]))
        print("\nInstallation successful.")
        print(f"CLI: {launcher}")
        print(f"Skill source for manual installation: {repo / 'SKILL.md'}")
        if not _path_on_path(launcher.parent):
            print(f"WARNING: {launcher.parent} is not on PATH. Add it and restart the shell.")
        print("Manually install the skill into the intended harness, then refresh or restart that harness.")
        print("After restarting, load the cv-builder skill to verify that it is visible.")
        return 0
    except (InstallerError, OSError, subprocess.CalledProcessError) as exc:
        residue = " A receipt was preserved when possible; run uninstall.py before retrying."
        print(f"ERROR {exc}.{residue}", file=sys.stderr)
        return 1


def _remove_managed_launcher(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    if _MANAGED_MARKER not in text:
        raise InstallerError(f"refusing to remove launcher without CV Builder ownership marker: {path}")
    path.unlink()


def _validate_uninstall_receipt(
    paths: InstallPaths, receipt: dict[str, object]
) -> tuple[str, Path, Path, Path, Path | None, bool]:
    method = receipt.get("method")
    if method not in {"uv", "venv"}:
        raise InstallerError(f"unknown installation method in receipt: {method!r}")
    launcher = Path(str(receipt.get("launcher", ""))).expanduser()
    environment = Path(str(receipt.get("environment", ""))).expanduser()
    browser = Path(os.path.abspath(Path(str(receipt.get("browser_dir", ""))).expanduser()))
    expected_browser = Path(os.path.abspath(paths.browser_dir.expanduser()))
    if browser != expected_browser:
        raise InstallerError(f"refusing unexpected browser path: {browser}")
    if browser.is_symlink():
        raise InstallerError(f"refusing symlinked browser directory: {browser}")
    if launcher.name not in {"cv-builder", "cv-builder.cmd", "cv-builder.exe"}:
        raise InstallerError(f"refusing unexpected launcher path: {launcher}")
    uv: Path | None = None
    if method == "venv":
        if environment.resolve() != paths.fallback_env.resolve():
            raise InstallerError(f"refusing unexpected environment path: {environment}")
        if launcher.parent.resolve() != paths.bin_dir.resolve():
            raise InstallerError(f"refusing unexpected launcher directory: {launcher}")
    else:
        tool_dir = Path(str(receipt.get("uv_tool_dir", ""))).expanduser().resolve()
        bin_dir = Path(str(receipt.get("uv_bin_dir", ""))).expanduser().resolve()
        if environment.resolve() != (tool_dir / _TOOL_NAME).resolve():
            raise InstallerError(f"refusing unexpected uv tool environment: {environment}")
        if launcher.parent.resolve() != bin_dir:
            raise InstallerError(f"refusing unexpected uv launcher directory: {launcher}")
        uv_value = str(receipt.get("uv") or "")
        uv = Path(uv_value) if uv_value else None
        if not uv or not uv.is_file():
            raise InstallerError("the recorded uv executable is unavailable; refusing a manual deletion of uv-managed state")
    launcher_owned = False
    if launcher.exists() or launcher.is_symlink():
        text = launcher.read_text(encoding="utf-8", errors="replace") if launcher.is_file() else ""
        launcher_owned = _MANAGED_MARKER in text
        if method == "venv" and not launcher_owned:
            raise InstallerError(f"refusing launcher without CV Builder ownership marker: {launcher}")
    return str(method), launcher, environment, browser, uv, launcher_owned


def uninstall(*, paths: InstallPaths | None = None) -> int:
    try:
        paths = paths or InstallPaths.defaults()
        receipt = _read_receipt(paths)
        if receipt is None:
            print("CV Builder has no recorded installation; nothing was removed.")
            return 0

        method, launcher, environment, browser, uv, launcher_owned = _validate_uninstall_receipt(paths, receipt)
        if method == "uv":
            assert uv is not None
            uv_environment = os.environ.copy()
            uv_environment["UV_TOOL_DIR"] = str(environment.parent)
            uv_environment["UV_TOOL_BIN_DIR"] = str(launcher.parent)
            result = subprocess.run(
                [str(uv), "tool", "uninstall", _TOOL_NAME],
                text=True,
                env=uv_environment,
            )
            if result.returncode != 0 and (environment.exists() or launcher.exists() or launcher.is_symlink()):
                raise InstallerError("uv could not uninstall the cv-builder tool environment")
            if launcher.exists() or launcher.is_symlink():
                if not launcher_owned:
                    raise InstallerError(f"uv left an unowned launcher in place; refusing to remove it: {launcher}")
                _remove_managed_launcher(launcher)
        else:
            _remove_managed_launcher(launcher)
            shutil.rmtree(environment, ignore_errors=True)

        shutil.rmtree(browser, ignore_errors=True)
        paths.receipt.unlink(missing_ok=True)
        try:
            paths.root.rmdir()
        except OSError:
            pass

        print("CV Builder CLI environment, launcher, receipt, and private browser files were removed.")
        print("The repository, shared browsers, and manually installed harness skills were not touched.")
        return 0
    except (InstallerError, OSError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
