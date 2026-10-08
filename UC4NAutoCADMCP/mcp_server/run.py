"""Independent HTTP host for the unchanged U-C4N MCP server."""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="U-C4N MCP Streamable HTTP server")
    parser.add_argument("--backend", choices=["com", "ezdxf"], default="com")
    parser.add_argument("--port", type=int, default=8768)
    parser.add_argument("--drawings-dir", type=Path, default=ROOT / "data" / "drawings")
    args = parser.parse_args()
    drawings = args.drawings_dir.resolve()
    drawings.mkdir(parents=True, exist_ok=True)
    os.environ.update(
        AUTOCAD_MCP_BACKEND=args.backend,
        ALLOWED_PATHS=str(drawings),
        TOOL_PROFILE="full",
        TOOL_PACKS="all",
        DISCOVERY_MODE="off",
        ENABLE_3D="false",
        DANGEROUS_COMMANDS_ENABLED="false",
    )
    sys.path.insert(0, str(ROOT / "upstream"))
    from fastmcp import Context
    from server import mcp

    @mcp.tool(
        annotations={"title": "Reconnect AutoCAD", "readOnlyHint": True},
        tags={"system"},
    )
    async def system_reconnect(ctx: Context = None) -> dict:
        """Drop a stale COM connection and reconnect to the running CAD application."""
        backend = ctx.lifespan_context.get("backend")
        if backend is None:
            return {
                "backend": "none",
                "connected": False,
                "error": ctx.lifespan_context.get("init_error"),
            }
        if getattr(backend, "name", None) == "com":
            await backend.disconnect()
            await backend.connect()
        return await backend.system_status()

    mcp.run(transport="http", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
