"""
cato/platform.py — Windows compatibility layer for CATO.

Provides cross-platform path handling, safe Unicode printing,
signal handler setup, and the canonical data directory.

Usage::

    from cato.platform import IS_WINDOWS, safe_path, safe_print, get_data_dir
    from cato.platform import setup_signal_handlers

    data_dir = get_data_dir()          # %APPDATA%/cato on Windows, ~/.cato on POSIX
    p = safe_path("~/some/path")       # always a resolved Path
    safe_print("Hello \u2713")         # safe on cp1252 terminals
    setup_signal_handlers(my_shutdown) # SIGINT everywhere, SIGTERM on POSIX only
"""

from __future__ import annotations

import atexit
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

IS_WINDOWS: bool = sys.platform == "win32"


# ---------------------------------------------------------------------------
# Data directory
# ---------------------------------------------------------------------------

def get_data_dir() -> Path:
    """
    Return the canonical Cato data directory.

    - Windows: %APPDATA%/cato  (e.g. C:/Users/Alice/AppData/Roaming/cato)
    - POSIX:   ~/.cato

    The directory is created if it does not exist.
    """
    if IS_WINDOWS:
        appdata = os.environ.get("APPDATA")
        if appdata:
            base = Path(appdata) / "cato"
        else:
            # Fallback if APPDATA is somehow unset
            base = Path.home() / "AppData" / "Roaming" / "cato"
    else:
        base = Path.home() / ".cato"

    base.mkdir(parents=True, exist_ok=True)
    return base


# ---------------------------------------------------------------------------
# Path normalisation
# ---------------------------------------------------------------------------

def safe_path(p: "str | Path") -> Path:
    """
    Normalize any path string or Path to a valid, expanded, resolved Path.

    Handles:
    - ~ expansion
    - Backslash / forward-slash normalisation on Windows
    - Relative path resolution against cwd
    """
    path = Path(str(p))
    # Expand ~ and ~user
    path = path.expanduser()
    # On Windows, Path handles backslash natively; on POSIX we normalise
    # any accidental backslashes coming from config files written on Windows.
    if not IS_WINDOWS:
        path = Path(str(path).replace("\\", "/"))
    return path.resolve()


# ---------------------------------------------------------------------------
# Safe Unicode printing
# ---------------------------------------------------------------------------

def safe_print(text: str) -> None:
    """
    Print *text* to stdout with Unicode fallback for Windows cp1252 terminals.

    On cp1252 terminals (common on Windows), characters outside the
    Windows-1252 range are replaced with '?' rather than crashing.
    On all other platforms this is equivalent to print().
    """
    if IS_WINDOWS:
        try:
            encoding = sys.stdout.encoding or "cp1252"
            encoded = text.encode(encoding, errors="replace").decode(encoding)
            print(encoded)
        except (UnicodeEncodeError, LookupError):
            # Last-resort ASCII fallback
            print(text.encode("ascii", errors="replace").decode("ascii"))
    else:
        print(text)


# ---------------------------------------------------------------------------
# Signal handlers
# ---------------------------------------------------------------------------

def setup_signal_handlers(shutdown_fn: Callable[[], None]) -> None:
    """
    Register *shutdown_fn* as the handler for graceful shutdown signals.

    - SIGINT  (Ctrl-C) — registered on all platforms.
    - SIGTERM           — registered on POSIX only (not available on Windows).
    - atexit            — registered on all platforms as a final safety net.

    The shutdown function is called at most once (idempotent guard).
    """
    _called: list[bool] = [False]

    def _handler(signum: int, frame: object) -> None:  # noqa: ARG001
        if not _called[0]:
            _called[0] = True
            logger.info("Signal %s received — initiating shutdown", signum)
            try:
                shutdown_fn()
            except Exception as exc:  # noqa: BLE001
                logger.error("Error during signal shutdown: %s", exc)
        sys.exit(0)

    def _atexit_handler() -> None:
        if not _called[0]:
            _called[0] = True
            try:
                shutdown_fn()
            except Exception as exc:  # noqa: BLE001
                logger.error("Error during atexit shutdown: %s", exc)

    # SIGINT is available everywhere
    signal.signal(signal.SIGINT, _handler)

    # SIGTERM is POSIX-only
    if not IS_WINDOWS:
        try:
            signal.signal(signal.SIGTERM, _handler)
        except (OSError, ValueError) as exc:
            logger.debug("Could not register SIGTERM: %s", exc)

    atexit.register(_atexit_handler)
    logger.debug(
        "Signal handlers registered (SIGINT%s + atexit)",
        "+SIGTERM" if not IS_WINDOWS else "",
    )
