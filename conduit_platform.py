"""
platform.py — Cross-platform data directory resolution for Conduit.

Returns a writable directory for Conduit's runtime data (SQLite db,
identity key, screenshots, proof bundles, etc.).

Priority:
  1. CONDUIT_DATA_DIR environment variable (override for any OS)
  2. OS default:
     - Windows: %LOCALAPPDATA%\Conduit  (e.g. C:\Users\You\AppData\Local\Conduit)
     - macOS:   ~/Library/Application Support/Conduit
     - Linux:   ~/.local/share/Conduit  (XDG_DATA_HOME compliant)

The directory is created on first call if it does not exist.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_cached: Path | None = None


def get_data_dir() -> Path:
    """Return (and create) the platform-appropriate Conduit data directory."""
    global _cached
    if _cached is not None:
        return _cached

    # 1. Explicit override
    env = os.environ.get("CONDUIT_DATA_DIR")
    if env:
        _cached = Path(env).expanduser().resolve()
        _cached.mkdir(parents=True, exist_ok=True)
        return _cached

    # 2. OS default
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local"))
        _cached = base / "Conduit"
    elif sys.platform == "darwin":
        _cached = Path.home() / "Library" / "Application Support" / "Conduit"
    else:
        xdg = os.environ.get("XDG_DATA_HOME", "")
        base = Path(xdg) if xdg else Path.home() / ".local" / "share"
        _cached = base / "Conduit"

    _cached.mkdir(parents=True, exist_ok=True)
    return _cached
