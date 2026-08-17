from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cv_builder.installer import (
    InstallPaths,
    _MANAGED_MARKER,
    _install_with_uv,
    _install_with_venv,
    _write_fallback_launcher,
    _write_managed_launcher,
    install,
    uninstall,
)


def make_paths(root: Path) -> InstallPaths:
    data = root / "data"
    return InstallPaths(
        root=data,
        browser_dir=data / "browsers",
        receipt=data / "install.json",
        fallback_env=data / "venv",
        bin_dir=root / "bin",
    )


def make_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='cv-builder'\n", encoding="utf-8")
    (repo / "SKILL.md").write_text("skill", encoding="utf-8")
    return repo


class InstallerTests(unittest.TestCase):
    def test_install_prefers_uv_and_records_only_cli_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = make_paths(root)
            repo = make_repo(root)
            uv = root / "uv"
            uv.write_text("uv", encoding="utf-8")
            launcher = root / "uv-bin/cv-builder"
            launcher.parent.mkdir()
            launcher.write_text("launcher", encoding="utf-8")
            receipt = {
                "schema": 1,
                "method": "uv",
                "environment": str(root / "uv-tools/cv-builder"),
                "launcher": str(launcher),
                "browser_dir": str(paths.browser_dir),
                "uv": str(uv),
                "uv_tool_dir": str(root / "uv-tools"),
                "uv_bin_dir": str(root / "uv-bin"),
            }
            with mock.patch("cv_builder.installer.shutil.which", return_value=str(uv)), mock.patch(
                "cv_builder.installer._install_with_uv", return_value=receipt
            ) as install_uv, mock.patch("cv_builder.installer._path_on_path", return_value=True):
                code = install(repo, paths=paths)
            self.assertEqual(code, 0)
            install_uv.assert_called_once()
            saved = json.loads(paths.receipt.read_text(encoding="utf-8"))
            self.assertEqual(saved["method"], "uv")
            self.assertNotIn("skill", saved)

    def test_install_falls_back_to_standard_venv_without_uv(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = make_paths(root)
            repo = make_repo(root)
            launcher = paths.bin_dir / "cv-builder"
            receipt = {
                "schema": 1,
                "method": "venv",
                "environment": str(paths.fallback_env),
                "launcher": str(launcher),
                "browser_dir": str(paths.browser_dir),
                "uv": None,
            }
            with mock.patch.dict(os.environ, {"CV_BUILDER_DISABLE_UV": "1"}), mock.patch(
                "cv_builder.installer._install_with_venv", return_value=receipt
            ) as install_venv, mock.patch("cv_builder.installer._path_on_path", return_value=True):
                code = install(repo, paths=paths)
            self.assertEqual(code, 0)
            install_venv.assert_called_once()
            self.assertEqual(json.loads(paths.receipt.read_text(encoding="utf-8"))["method"], "venv")

    def test_fallback_launcher_has_ownership_marker(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = make_paths(root)
            python = root / "venv/bin/python"
            python.parent.mkdir(parents=True)
            python.write_text("", encoding="utf-8")
            launcher = _write_fallback_launcher(paths, python)
            self.assertIn(_MANAGED_MARKER, launcher.read_text(encoding="utf-8"))

    def test_windows_launcher_quotes_environment_assignment(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            launcher = root / "cv-builder.cmd"
            python = root / "Python %TOOLS% & More/python.exe"
            data = root / "Data %HOME% & Files"
            with mock.patch("cv_builder.installer._is_windows", return_value=True):
                _write_managed_launcher(launcher, python, data)
            text = launcher.read_text(encoding="utf-8")
            self.assertIn('set "CV_BUILDER_HOME=', text)
            self.assertIn("Data %%HOME%% & Files", text)
            self.assertIn("Python %%TOOLS%% & More", text)
            self.assertNotIn("Data %HOME% & Files", text)

    def test_windows_uv_install_refuses_foreign_cmd_launcher_before_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = make_paths(root)
            repo = make_repo(root)
            uv = root / "uv"
            uv.write_text("uv", encoding="utf-8")
            bin_dir = root / "uv-bin"
            bin_dir.mkdir()
            foreign = bin_dir / "cv-builder.cmd"
            foreign.write_text("foreign launcher", encoding="utf-8")
            calls: list[list[str]] = []

            def fake_run(command, *, env=None, capture=False):
                items = [str(item) for item in command]
                calls.append(items)
                if items[-2:] == ["tool", "dir"]:
                    return subprocess.CompletedProcess(items, 0, stdout=str(root / "uv-tools") + "\n")
                if items[-3:] == ["tool", "dir", "--bin"]:
                    return subprocess.CompletedProcess(items, 0, stdout=str(bin_dir) + "\n")
                raise AssertionError(f"unexpected mutation command: {items}")

            with mock.patch("cv_builder.installer._is_windows", return_value=True), mock.patch(
                "cv_builder.installer._run", side_effect=fake_run
            ):
                with self.assertRaisesRegex(Exception, "not owned"):
                    _install_with_uv(repo, uv, paths)
            self.assertEqual(foreign.read_text(encoding="utf-8"), "foreign launcher")
            self.assertFalse(any("install" in call for call in calls))

    def test_fallback_launcher_refuses_foreign_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = make_paths(root)
            paths.bin_dir.mkdir()
            (paths.bin_dir / "cv-builder").write_text("foreign", encoding="utf-8")
            python = root / "python"
            python.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(Exception, "not owned"):
                _write_fallback_launcher(paths, python)

    def test_uninstall_venv_removes_only_recorded_cv_builder_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = make_paths(root)
            paths.fallback_env.mkdir(parents=True)
            paths.browser_dir.mkdir()
            (paths.browser_dir / "browser").write_text("owned", encoding="utf-8")
            paths.bin_dir.mkdir()
            launcher = paths.bin_dir / "cv-builder"
            launcher.write_text(f"#!/bin/sh\n# {_MANAGED_MARKER}\n", encoding="utf-8")
            unrelated = root / "manual-skill/SKILL.md"
            unrelated.parent.mkdir()
            unrelated.write_text("keep", encoding="utf-8")
            paths.receipt.write_text(json.dumps({
                "schema": 1,
                "method": "venv",
                "environment": str(paths.fallback_env),
                "launcher": str(launcher),
                "browser_dir": str(paths.browser_dir),
                "uv": None,
            }), encoding="utf-8")
            self.assertEqual(uninstall(paths=paths), 0)
            self.assertFalse(paths.fallback_env.exists())
            self.assertFalse(paths.browser_dir.exists())
            self.assertFalse(launcher.exists())
            self.assertFalse(paths.receipt.exists())
            self.assertEqual(unrelated.read_text(encoding="utf-8"), "keep")

    def test_uninstall_uv_delegates_only_named_tool_and_preserves_skill(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = make_paths(root)
            paths.root.mkdir(parents=True)
            paths.browser_dir.mkdir()
            uv = root / "uv"
            uv.write_text("uv", encoding="utf-8")
            launcher = root / "uv-bin/cv-builder"
            launcher.parent.mkdir()
            launcher.write_text(f"# {_MANAGED_MARKER}\n", encoding="utf-8")
            environment = root / "uv-tools/cv-builder"
            environment.mkdir(parents=True)
            skill = root / "harness/skills/cv-builder/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("manual", encoding="utf-8")
            paths.receipt.write_text(json.dumps({
                "schema": 1,
                "method": "uv",
                "environment": str(environment),
                "launcher": str(launcher),
                "browser_dir": str(paths.browser_dir),
                "uv": str(uv),
                "uv_tool_dir": str(root / "uv-tools"),
                "uv_bin_dir": str(root / "uv-bin"),
            }), encoding="utf-8")

            def fake_run(command, text, env):
                self.assertEqual(command, [str(uv), "tool", "uninstall", "cv-builder"])
                self.assertEqual(env["UV_TOOL_DIR"], str(root / "uv-tools"))
                self.assertEqual(env["UV_TOOL_BIN_DIR"], str(root / "uv-bin"))
                launcher.unlink()
                environment.rmdir()
                return subprocess.CompletedProcess(command, 0)

            with mock.patch("cv_builder.installer.subprocess.run", side_effect=fake_run) as called:
                self.assertEqual(uninstall(paths=paths), 0)
            called.assert_called_once()
            self.assertEqual(skill.read_text(encoding="utf-8"), "manual")

    def test_uv_receipt_paths_must_match_recorded_tool_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = make_paths(root)
            paths.root.mkdir(parents=True)
            paths.browser_dir.mkdir()
            uv = root / "uv"
            uv.write_text("uv", encoding="utf-8")
            environment = root / "unrelated/cv-builder"
            environment.mkdir(parents=True)
            launcher = root / "unrelated-bin/cv-builder"
            launcher.parent.mkdir()
            launcher.write_text(f"# {_MANAGED_MARKER}\n", encoding="utf-8")
            paths.receipt.write_text(json.dumps({
                "schema": 1,
                "method": "uv",
                "environment": str(environment),
                "launcher": str(launcher),
                "browser_dir": str(paths.browser_dir),
                "uv": str(uv),
                "uv_tool_dir": str(root / "real-tools"),
                "uv_bin_dir": str(root / "real-bin"),
            }), encoding="utf-8")
            with mock.patch("cv_builder.installer.subprocess.run") as run:
                self.assertEqual(uninstall(paths=paths), 1)
            run.assert_not_called()
            self.assertTrue(environment.exists())
            self.assertTrue(launcher.exists())
            self.assertTrue(paths.browser_dir.exists())

    def test_symlinked_browser_directory_is_rejected_without_deleting_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = make_paths(root)
            paths.root.mkdir(parents=True)
            target = root / "unrelated-browser-data"
            target.mkdir()
            (target / "keep.txt").write_text("keep", encoding="utf-8")
            paths.browser_dir.symlink_to(target, target_is_directory=True)
            paths.fallback_env.mkdir()
            paths.bin_dir.mkdir()
            launcher = paths.bin_dir / "cv-builder"
            launcher.write_text(f"# {_MANAGED_MARKER}\n", encoding="utf-8")
            paths.receipt.write_text(json.dumps({
                "schema": 1,
                "method": "venv",
                "environment": str(paths.fallback_env),
                "launcher": str(launcher),
                "browser_dir": str(paths.browser_dir),
                "uv": None,
            }), encoding="utf-8")
            self.assertEqual(uninstall(paths=paths), 1)
            self.assertEqual((target / "keep.txt").read_text(encoding="utf-8"), "keep")
            self.assertTrue(paths.fallback_env.exists())
            self.assertTrue(launcher.exists())

    def test_malformed_receipt_fails_before_any_removal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = make_paths(root)
            paths.fallback_env.mkdir(parents=True)
            paths.bin_dir.mkdir()
            launcher = paths.bin_dir / "cv-builder"
            launcher.write_text(f"# {_MANAGED_MARKER}\n", encoding="utf-8")
            unexpected_browser = root / "unrelated-browser"
            unexpected_browser.mkdir()
            paths.receipt.write_text(json.dumps({
                "schema": 1,
                "method": "venv",
                "environment": str(paths.fallback_env),
                "launcher": str(launcher),
                "browser_dir": str(unexpected_browser),
                "uv": None,
            }), encoding="utf-8")
            self.assertEqual(uninstall(paths=paths), 1)
            self.assertTrue(paths.fallback_env.exists())
            self.assertTrue(launcher.exists())
            self.assertTrue(unexpected_browser.exists())

    def test_partial_uv_install_with_unmarked_generated_launcher_can_be_cleaned(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = make_paths(root)
            paths.root.mkdir(parents=True)
            paths.browser_dir.mkdir()
            uv = root / "uv"
            uv.write_text("uv", encoding="utf-8")
            tool_dir = root / "uv-tools"
            environment = tool_dir / "cv-builder"
            environment.mkdir(parents=True)
            bin_dir = root / "uv-bin"
            bin_dir.mkdir()
            launcher = bin_dir / "cv-builder"
            launcher.write_text("uv generated launcher", encoding="utf-8")
            paths.receipt.write_text(json.dumps({
                "schema": 1,
                "method": "uv",
                "environment": str(environment),
                "launcher": str(launcher),
                "browser_dir": str(paths.browser_dir),
                "uv": str(uv),
                "uv_tool_dir": str(tool_dir),
                "uv_bin_dir": str(bin_dir),
            }), encoding="utf-8")

            def fake_run(command, text, env):
                self.assertEqual(env["UV_TOOL_DIR"], str(tool_dir))
                self.assertEqual(env["UV_TOOL_BIN_DIR"], str(bin_dir))
                launcher.unlink()
                environment.rmdir()
                return subprocess.CompletedProcess(command, 0)

            with mock.patch("cv_builder.installer.subprocess.run", side_effect=fake_run) as run:
                self.assertEqual(uninstall(paths=paths), 0)
            run.assert_called_once()
            self.assertFalse(paths.receipt.exists())
            self.assertFalse(paths.browser_dir.exists())

    def test_failed_uv_install_preserves_receipt_for_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = make_paths(root)
            repo = make_repo(root)
            uv = root / "uv"
            uv.write_text("uv", encoding="utf-8")

            def fake_run(command, *, env=None, capture=False):
                items = [str(item) for item in command]
                if items[-2:] == ["tool", "dir"]:
                    return subprocess.CompletedProcess(items, 0, stdout=str(root / "uv-tools") + "\n")
                if items[-3:] == ["tool", "dir", "--bin"]:
                    return subprocess.CompletedProcess(items, 0, stdout=str(root / "uv-bin") + "\n")
                raise subprocess.CalledProcessError(1, items)

            with mock.patch("cv_builder.installer._run", side_effect=fake_run):
                with self.assertRaises(subprocess.CalledProcessError):
                    _install_with_uv(repo, uv, paths)
            receipt = json.loads(paths.receipt.read_text(encoding="utf-8"))
            self.assertEqual(receipt["method"], "uv")
            self.assertEqual(Path(receipt["uv_tool_dir"]), (root / "uv-tools").resolve())
            self.assertEqual(Path(receipt["uv_bin_dir"]), (root / "uv-bin").resolve())

    def test_failed_install_preserves_receipt_for_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = make_paths(root)
            repo = make_repo(root)

            def create_environment(_builder):
                python = paths.fallback_env / "bin/python"
                python.parent.mkdir(parents=True)
                python.write_text("", encoding="utf-8")

            with mock.patch("cv_builder.installer.venv.EnvBuilder.create", side_effect=create_environment), mock.patch(
                "cv_builder.installer._run"
            ), mock.patch("cv_builder.installer._install_browser", side_effect=OSError("download failed")):
                with self.assertRaisesRegex(OSError, "download failed"):
                    _install_with_venv(repo, paths)
            receipt = json.loads(paths.receipt.read_text(encoding="utf-8"))
            self.assertEqual(receipt["method"], "venv")
            self.assertEqual(Path(receipt["environment"]), paths.fallback_env)

    def test_uninstall_without_receipt_changes_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = make_paths(root)
            unrelated = root / "unrelated.txt"
            unrelated.write_text("keep", encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(uninstall(paths=paths), 0)
            self.assertTrue(unrelated.exists())
            self.assertIn("nothing was removed", output.getvalue())


if __name__ == "__main__":
    unittest.main()
