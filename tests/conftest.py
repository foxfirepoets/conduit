"""
tests/conftest.py — Session-scoped package bootstrap for Conduit tests.

Installs the `cato.*` sys.modules shim ONCE per pytest session so all test
files share the same module objects. This file is auto-loaded by pytest before
any test file imports, so the real modules are wired up before any stub can
overwrite them.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

CONDUIT_ROOT = Path(__file__).parent.parent

# Data dir for module-level platform — individual tests pass data_dir to ConduitBridge
import tempfile as _tempfile
_SESSION_DATA_DIR = Path(_tempfile.gettempdir()) / "conduit_test_session"


def bootstrap_cato(data_dir: Path = _SESSION_DATA_DIR) -> None:
    """
    Wire sys.modules so relative imports inside conduit source files resolve.
    Safe to call multiple times — subsequent calls are no-ops.
    """
    # cato (top-level namespace package)
    cato_pkg = types.ModuleType("cato")
    cato_pkg.__path__ = [str(CONDUIT_ROOT)]
    cato_pkg.__package__ = "cato"
    existing = sys.modules.setdefault("cato", cato_pkg)
    cato_pkg = existing  # always use the one that won the race

    # cato.conduit_platform — only install if not already there
    for _mod_alias in ("cato.platform", "cato.conduit_platform"):
        if _mod_alias not in sys.modules:
            platform_mod = types.ModuleType(_mod_alias)
            _data_dir = data_dir  # capture
            platform_mod.get_data_dir = lambda: _data_dir  # type: ignore[attr-defined]
            sys.modules[_mod_alias] = platform_mod
            setattr(cato_pkg, _mod_alias.split(".")[-1], platform_mod)  # type: ignore[attr-defined]

    # cato.audit — load real audit.py
    if "cato.audit" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "cato.audit",
            str(CONDUIT_ROOT / "audit.py"),
            submodule_search_locations=[],
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = "cato"
        sys.modules["cato.audit"] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        cato_pkg.audit = mod  # type: ignore[attr-defined]

    # cato.tools sub-package
    tools_pkg = types.ModuleType("cato.tools")
    tools_pkg.__path__ = [str(CONDUIT_ROOT / "tools")]
    tools_pkg.__package__ = "cato.tools"
    existing_tools = sys.modules.setdefault("cato.tools", tools_pkg)
    tools_pkg = existing_tools
    cato_pkg.tools = tools_pkg  # type: ignore[attr-defined]

    # Load each tool module once.
    # IMPORTANT: browser.py must load before test_audit_chain.py can install its stub.
    for mod_name, file_name in [
        ("cato.tools.browser", "browser.py"),
        ("cato.tools.conduit_bridge", "conduit_bridge.py"),
        ("cato.tools.conduit_crawl", "conduit_crawl.py"),
        ("cato.tools.conduit_monitor", "conduit_monitor.py"),
        ("cato.tools.conduit_proof", "conduit_proof.py"),
    ]:
        if mod_name not in sys.modules:
            spec = importlib.util.spec_from_file_location(
                mod_name,
                str(CONDUIT_ROOT / "tools" / file_name),
                submodule_search_locations=[],
            )
            assert spec and spec.loader
            mod = importlib.util.module_from_spec(spec)
            mod.__package__ = "cato.tools"
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)  # type: ignore[union-attr]


# Bootstrap immediately when conftest is loaded (before any test file imports).
# This ensures the real BrowserTool is in sys.modules before test_audit_chain.py
# can install its _StubBrowserTool.
bootstrap_cato()
