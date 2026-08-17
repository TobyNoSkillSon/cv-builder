from __future__ import annotations

import argparse
import shutil
import sys
from importlib.resources import files
from pathlib import Path

from .config import AppConfig, ConfigError, application_name, write_config
from .pipeline import BuildError, build


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="cv-builder",
        description="Create and render a deterministic, editable CV workspace.",
    )
    commands = root.add_subparsers(dest="command", required=True)

    new = commands.add_parser("new", help="Create a complete CV application workspace.")
    new.add_argument("employer")
    new.add_argument("role")

    commands.add_parser("build", help="Snapshot, render, verify and open the current CV.")
    return root


def _template(name: str) -> str:
    return files("cv_builder").joinpath("templates", name).read_text(encoding="utf-8")


def _new(employer: str, role: str, parent: Path) -> dict[str, object]:
    config = AppConfig.from_dict({"employer": employer, "role": role})
    app = parent / application_name(config.employer, config.role)
    if app.exists() or app.is_symlink():
        raise ConfigError(f"refusing to overwrite application: {app}")
    app.mkdir(parents=False)
    try:
        (app / "iterations").mkdir()
        (app / "offer.md").write_text(
            f"# {config.role} — {config.employer}\n\n[[PASTE_JOB_DESCRIPTION_HERE]]\n",
            encoding="utf-8",
        )
        (app / "cv.html").write_text(_template("cv.html"), encoding="utf-8")
        (app / "cv.css").write_text(_template("cv.css"), encoding="utf-8")
        write_config(app, config)
    except Exception:
        shutil.rmtree(app)
        raise
    return {
        "command": "new",
        "ok": True,
        "app": str(app.resolve()),
        "edit": ["offer.md", "cv.html"],
        "next": f"cd {str(app.resolve())!r} && cv-builder build",
    }


def _emit(value: dict[str, object]) -> None:
    command = str(value.get("command", "result")).upper()
    atoms = [f"{key}={item!r}" for key, item in value.items() if key != "command"]
    print(command + (" " + " ".join(atoms) if atoms else ""))


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "new":
            result = _new(args.employer, args.role, Path.cwd())
        elif args.command == "build":
            result = build(Path.cwd())
            result["command"] = "build"
        else:
            raise ConfigError(f"unknown command: {args.command}")
        _emit(result)
        return 0
    except (ConfigError, BuildError, OSError, ValueError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("ERROR interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
