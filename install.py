#!/usr/bin/env python3
from pathlib import Path

from cv_builder.installer import install


if __name__ == "__main__":
    raise SystemExit(install(Path(__file__).resolve().parent))
