from __future__ import annotations

import os
from pathlib import Path


def data_root() -> Path:
    override = os.environ.get("CV_BUILDER_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "cv-builder"
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "cv-builder"


def default_bin_dir() -> Path:
    override = os.environ.get("CV_BUILDER_BIN_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".local" / "bin"
