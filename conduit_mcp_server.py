"""Standalone stdio MCP server for Conduit.

Run with:  python conduit_mcp_server.py
or via:    python -m conduit_mcp_server
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

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
        try:
            from tools.conduit_bridge import ConduitBridge
        except ImportError:
            # Fallback path when installed as package
            import importlib
            cb = importlib.import_module("conduit_bridge", package="tools")
            ConduitBridge = cb.ConduitBridge
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
