"""Streamable HTTP adapter for Slacker's stdio MCP server.

The upstream server remains the source of the tool schemas and handlers. This
small host lets the existing U-C4N browser client connect over HTTP.
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import sys
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.tools.function_tool import FunctionTool
from fastmcp.tools.tool import ToolResult
from mcp.types import ImageContent, TextContent

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from autocad_mcp.server import TOOLS, call_tool  # noqa: E402


def make_tool(tool: Any) -> FunctionTool:
    """Expose one upstream MCP tool with its original JSON schema."""
    schema = tool.inputSchema
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    parameters = [
        inspect.Parameter(
            name,
            inspect.Parameter.KEYWORD_ONLY,
            default=inspect.Parameter.empty if name in required else None,
            annotation=Any,
        )
        for name in properties
    ]

    async def invoke(**arguments: Any) -> ToolResult:
        # FastMCP supplies None for omitted optional signature parameters.
        # Slacker distinguishes an absent key from a supplied value; for
        # example rotation_deg must be absent for aligned dimensions.
        arguments = {
            name: value
            for name, value in arguments.items()
            if name in required or value is not None
        }
        content = await call_tool(tool.name, arguments)
        payload = json.loads(next(item.text for item in content if isinstance(item, TextContent)))
        return ToolResult(content=content, is_error=payload.get("ok") is False)

    invoke.__name__ = f"slacker_{tool.name}"
    invoke.__signature__ = inspect.Signature(parameters)  # type: ignore[attr-defined]
    return FunctionTool(
        name=tool.name,
        description=tool.description,
        parameters=schema,
        fn=invoke,
        run_in_thread=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Slacker AutoCAD MCP over Streamable HTTP")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args()

    mcp = FastMCP("slacker-autocad-mcp")
    for tool in TOOLS:
        mcp.add_tool(make_tool(tool))

    # The reference U-C4N client uses these two conventional tool names as
    # connection and drawing-context probes. Keep aliases here so the upstream
    # Slacker tool names and schemas remain intact.
    @mcp.tool
    async def system_status() -> dict[str, Any]:
        """Compatibility status probe for the U-C4N HTTP client."""
        content = await call_tool("autocad_status", {})
        payload = json.loads(next(item.text for item in content if isinstance(item, TextContent)))
        data = payload.get("data", {})
        document = data.get("active_document", {})
        return {
            # The U-C4N client uses this field to accept the MCP session. The
            # session is live even when AutoCAD has no active drawing yet.
            "connected": True,
            "cad_connected": bool(payload.get("ok")),
            "backend": "com",
            "message": payload.get("message"),
            "active_document": document,
        }

    @mcp.tool
    async def drawing_info() -> dict[str, Any]:
        """Compatibility drawing-context probe for the U-C4N HTTP client."""
        content = await call_tool("get_active_drawing_info", {})
        payload = json.loads(next(item.text for item in content if isinstance(item, TextContent)))
        document = payload.get("data", {}).get("drawing", {})
        return {
            "name": document.get("name"),
            "full_path": document.get("path"),
            "units": document.get("insunits_name"),
            "entity_count": None,
            "insunits": document.get("insunits"),
            "saved": document.get("saved"),
            "readonly": document.get("readonly"),
            "coordinates_contract": document.get("coordinates_contract"),
        }

    mcp.run(transport="http", host=args.host, port=args.port, path="/mcp")


if __name__ == "__main__":
    main()
