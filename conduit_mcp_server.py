"""Standalone stdio MCP server for Conduit.

Run with:  python conduit_mcp_server.py
or via:    python -m conduit_mcp_server
"""

from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path
from typing import Any

# Ensure Conduit's own directory is on the path regardless of where Python is invoked from.
_CONDUIT_ROOT = Path(__file__).resolve().parent
if str(_CONDUIT_ROOT) not in sys.path:
    sys.path.insert(0, str(_CONDUIT_ROOT))

# Install the cato.* namespace shim so relative imports inside tools/* resolve.
def _bootstrap_cato() -> None:
    cato_pkg = types.ModuleType("cato")
    cato_pkg.__path__ = [str(_CONDUIT_ROOT)]
    cato_pkg.__package__ = "cato"
    sys.modules.setdefault("cato", cato_pkg)

    for _alias in ("cato.platform", "cato.conduit_platform"):
        if _alias not in sys.modules:
            import importlib.util as _ilu
            _spec = _ilu.spec_from_file_location(_alias, str(_CONDUIT_ROOT / "conduit_platform.py"))
            assert _spec and _spec.loader
            _pmod = _ilu.module_from_spec(_spec)
            _spec.loader.exec_module(_pmod)  # type: ignore[union-attr]
            sys.modules[_alias] = _pmod
            attr_name = "conduit_platform" if "conduit_platform" in _alias else "platform"
            setattr(sys.modules["cato"], attr_name, _pmod)

    tools_pkg = types.ModuleType("cato.tools")
    tools_pkg.__path__ = [str(_CONDUIT_ROOT / "tools")]
    tools_pkg.__package__ = "cato.tools"
    sys.modules.setdefault("cato.tools", tools_pkg)
    sys.modules["cato"].tools = sys.modules["cato.tools"]  # type: ignore[attr-defined]

_bootstrap_cato()

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# ---------------------------------------------------------------------------
# Lazy bridge — only import heavy deps when first tool call arrives
# ---------------------------------------------------------------------------
_bridge: Any = None


async def _get_bridge():
    global _bridge
    if _bridge is None:
        from tools.conduit_bridge import ConduitBridge
        _bridge = ConduitBridge()
        await _bridge.start()
    return _bridge


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------
TOOLS = [
    Tool(
        name="conduit_navigate",
        description="Navigate to a URL in the stealth headless browser.",
        inputSchema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to navigate to"},
            },
            "required": ["url"],
        },
    ),
    Tool(
        name="conduit_screenshot",
        description="Take a screenshot of the current browser page.",
        inputSchema={
            "type": "object",
            "properties": {
                "full_page": {"type": "boolean", "default": False},
            },
        },
    ),
    Tool(
        name="conduit_extract",
        description="Extract text content from the current page.",
        inputSchema={
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector (optional, defaults to body)"},
            },
        },
    ),
    Tool(
        name="conduit_click",
        description="Click an element on the current page.",
        inputSchema={
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector of element to click"},
            },
            "required": ["selector"],
        },
    ),
    Tool(
        name="conduit_fill",
        description="Fill a form field with text.",
        inputSchema={
            "type": "object",
            "properties": {
                "selector": {"type": "string"},
                "text": {"type": "string"},
            },
            "required": ["selector", "text"],
        },
    ),
    Tool(
        name="conduit_search",
        description="Search the web using multiple engines (DuckDuckGo, Brave, etc.).",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "engine": {"type": "string", "default": "ddg", "description": "Engine: ddg, brave, exa, tavily"},
                "num_results": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="conduit_eval",
        description="Execute JavaScript on the current page. Source is stored verbatim in audit chain.",
        inputSchema={
            "type": "object",
            "properties": {
                "script": {"type": "string", "description": "JavaScript to execute"},
            },
            "required": ["script"],
        },
    ),
    Tool(
        name="conduit_export_proof",
        description="Export a self-verifiable cryptographic proof bundle of all actions taken.",
        inputSchema={
            "type": "object",
            "properties": {
                "output_path": {"type": "string", "description": "Path to write the .tar.gz proof bundle"},
            },
        },
    ),
    Tool(
        name="conduit_marketplace_list",
        description="List marketplace product metadata and supported marketplaces.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="conduit_marketplace_create_job",
        description="Create a queued marketplace extraction job for Upwork or Fiverr.",
        inputSchema={
            "type": "object",
            "properties": {
                "marketplace": {"type": "string", "description": "Marketplace slug: upwork or fiverr"},
                "target_type": {"type": "string", "description": "Marketplace target type"},
                "target_url": {"type": "string", "description": "Target page URL"},
                "account_id": {"type": "string", "description": "Optional marketplace account id"},
                "proxy_label": {"type": "string", "description": "Optional proxy label"},
                "request_payload": {"type": "object", "description": "Optional request metadata"},
            },
            "required": ["marketplace", "target_type", "target_url"],
        },
    ),
    Tool(
        name="conduit_marketplace_targets",
        description="List supported target types for a marketplace.",
        inputSchema={
            "type": "object",
            "properties": {
                "marketplace": {"type": "string", "description": "Marketplace slug: upwork or fiverr"},
            },
            "required": ["marketplace"],
        },
    ),
    Tool(
        name="conduit_marketplace_plan",
        description="Build a normalized marketplace extraction plan before creating a job.",
        inputSchema={
            "type": "object",
            "properties": {
                "marketplace": {"type": "string", "description": "Marketplace slug: upwork or fiverr"},
                "target_type": {"type": "string", "description": "Marketplace target type"},
                "target_url": {"type": "string", "description": "Target page URL"},
                "account_id": {"type": "string", "description": "Optional marketplace account id"},
                "proxy_label": {"type": "string", "description": "Optional proxy label"},
            },
            "required": ["marketplace", "target_type", "target_url"],
        },
    ),
    Tool(
        name="conduit_marketplace_create_account",
        description="Create a named marketplace account record for session reuse.",
        inputSchema={
            "type": "object",
            "properties": {
                "marketplace": {"type": "string"},
                "display_name": {"type": "string"},
                "credential_key": {"type": "string"},
                "proxy_label": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "required": ["marketplace", "display_name"],
        },
    ),
    Tool(
        name="conduit_marketplace_create_proxy",
        description="Create or update a named marketplace proxy route.",
        inputSchema={
            "type": "object",
            "properties": {
                "label": {"type": "string"},
                "host": {"type": "string"},
                "port": {"type": "integer"},
                "protocol": {"type": "string", "default": "http"},
                "username": {"type": "string"},
                "password": {"type": "string"},
                "kind": {"type": "string", "default": "http"},
                "metadata": {"type": "object"},
            },
            "required": ["label", "host", "port"],
        },
    ),
    Tool(
        name="conduit_marketplace_list_proxies",
        description="List named marketplace proxy routes.",
        inputSchema={
            "type": "object",
            "properties": {
                "state": {"type": "string", "description": "Optional proxy state filter"},
            },
        },
    ),
    Tool(
        name="conduit_marketplace_get_proxy",
        description="Fetch one named marketplace proxy route.",
        inputSchema={
            "type": "object",
            "properties": {
                "label": {"type": "string", "description": "Proxy label"},
            },
            "required": ["label"],
        },
    ),
    Tool(
        name="conduit_marketplace_test_proxy",
        description="Launch a temporary browser through a named proxy route and test a URL.",
        inputSchema={
            "type": "object",
            "properties": {
                "label": {"type": "string", "description": "Proxy label"},
                "test_url": {"type": "string", "description": "Optional URL to test", "default": "https://api.ipify.org/"},
            },
            "required": ["label"],
        },
    ),
    Tool(
        name="conduit_marketplace_save_session",
        description="Register a saved marketplace session cookie file for an account.",
        inputSchema={
            "type": "object",
            "properties": {
                "account_id": {"type": "string"},
                "label": {"type": "string"},
                "cookie_path": {"type": "string"},
                "state": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "required": ["account_id", "label", "cookie_path"],
        },
    ),
    Tool(
        name="conduit_marketplace_list_accounts",
        description="List configured marketplace accounts.",
        inputSchema={
            "type": "object",
            "properties": {
                "marketplace": {"type": "string"},
            },
        },
    ),
    Tool(
        name="conduit_marketplace_list_sessions",
        description="List saved marketplace sessions.",
        inputSchema={
            "type": "object",
            "properties": {
                "marketplace": {"type": "string"},
                "account_id": {"type": "string"},
            },
        },
    ),
    Tool(
        name="conduit_marketplace_get_session",
        description="Fetch one saved marketplace session by id.",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Marketplace session id"},
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="conduit_marketplace_bootstrap_session",
        description="Log into a marketplace account using its credential key and persist a fresh saved session.",
        inputSchema={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Marketplace account id"},
                "target_url": {"type": "string", "description": "Optional target URL to bootstrap against"},
            },
            "required": ["account_id"],
        },
    ),
    Tool(
        name="conduit_marketplace_run_job",
        description="Execute a queued marketplace extraction job using Conduit's audited browser.",
        inputSchema={
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Marketplace job id"},
            },
            "required": ["job_id"],
        },
    ),
    Tool(
        name="conduit_marketplace_enqueue_job",
        description="Queue a marketplace job for background execution in the current server process.",
        inputSchema={
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Marketplace job id"},
            },
            "required": ["job_id"],
        },
    ),
    Tool(
        name="conduit_marketplace_queue_status",
        description="Inspect queued/running/completed marketplace jobs in the current server process.",
        inputSchema={
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Optional marketplace job id"},
            },
        },
    ),
    Tool(
        name="conduit_marketplace_get_job",
        description="Fetch one marketplace extraction job by id.",
        inputSchema={
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Marketplace job id"},
            },
            "required": ["job_id"],
        },
    ),
    Tool(
        name="conduit_marketplace_list_jobs",
        description="List marketplace extraction jobs.",
        inputSchema={
            "type": "object",
            "properties": {
                "marketplace": {"type": "string", "description": "Optional marketplace filter"},
                "status": {"type": "string", "description": "Optional status filter"},
            },
        },
    ),
    Tool(
        name="conduit_marketplace_list_results",
        description="List persisted marketplace extraction results.",
        inputSchema={
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Optional job id filter"},
            },
        },
    ),
    Tool(
        name="conduit_marketplace_get_result",
        description="Fetch one persisted marketplace extraction result by id.",
        inputSchema={
            "type": "object",
            "properties": {
                "result_id": {"type": "string", "description": "Marketplace result id"},
            },
            "required": ["result_id"],
        },
    ),
    Tool(
        name="conduit_marketplace_export_result",
        description="Export one marketplace result as JSONL or CSV.",
        inputSchema={
            "type": "object",
            "properties": {
                "result_id": {"type": "string", "description": "Marketplace result id"},
                "fmt": {"type": "string", "description": "Export format: jsonl or csv", "default": "jsonl"},
            },
            "required": ["result_id"],
        },
    ),
]


# ---------------------------------------------------------------------------
# Action dispatch
# ---------------------------------------------------------------------------
async def _dispatch(tool_name: str, arguments: dict) -> str:
    bridge = await _get_bridge()

    action_map = {
        "conduit_navigate": "navigate",
        "conduit_screenshot": "screenshot",
        "conduit_extract": "extract",
        "conduit_click": "click",
        "conduit_fill": "fill",
        "conduit_search": "search",
        "conduit_eval": "eval",
        "conduit_export_proof": "export_proof",
        "conduit_marketplace_list": "marketplace_list",
        "conduit_marketplace_targets": "marketplace_targets",
        "conduit_marketplace_plan": "marketplace_plan",
        "conduit_marketplace_create_job": "marketplace_create_job",
        "conduit_marketplace_create_account": "marketplace_create_account",
        "conduit_marketplace_create_proxy": "marketplace_create_proxy",
        "conduit_marketplace_list_proxies": "marketplace_list_proxies",
        "conduit_marketplace_get_proxy": "marketplace_get_proxy",
        "conduit_marketplace_test_proxy": "marketplace_test_proxy",
        "conduit_marketplace_save_session": "marketplace_save_session",
        "conduit_marketplace_list_accounts": "marketplace_list_accounts",
        "conduit_marketplace_list_sessions": "marketplace_list_sessions",
        "conduit_marketplace_get_session": "marketplace_get_session",
        "conduit_marketplace_bootstrap_session": "marketplace_bootstrap_session",
        "conduit_marketplace_run_job": "marketplace_execute_job",
        "conduit_marketplace_enqueue_job": "marketplace_enqueue_job",
        "conduit_marketplace_queue_status": "marketplace_queue_status",
        "conduit_marketplace_get_job": "marketplace_get_job",
        "conduit_marketplace_list_jobs": "marketplace_list_jobs",
        "conduit_marketplace_list_results": "marketplace_list_results",
        "conduit_marketplace_get_result": "marketplace_get_result",
        "conduit_marketplace_export_result": "marketplace_export_result",
    }

    action = action_map.get(tool_name)
    if action is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    args = {"action": action, **arguments}
    try:
        result = await bridge.execute(args)
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------
def create_server() -> Server:
    server = Server("conduit-browser")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOLS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        result = await _dispatch(name, arguments or {})
        return [TextContent(type="text", text=result)]

    return server


async def main():
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
