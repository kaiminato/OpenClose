"""Locate bundled files both from source and inside a PyInstaller build."""
from __future__ import annotations

import sys
from pathlib import Path


def base_dir() -> Path:
    """Project folder when run from source; the bundle folder when frozen by PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def asset(name: str) -> Path:
    return base_dir() / "assets" / name
