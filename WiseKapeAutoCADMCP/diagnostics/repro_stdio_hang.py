"""Reproduce the observed hang when a backend-backed tool is called over stdio."""

import asyncio
import os
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def main() -> int:
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["AUTOCAD_MCP_BACKEND"] = "ezdxf"
    params = StdioServerParameters(
        command=str(root / ".venv" / "Scripts" / "python.exe"),
        args=["-m", "autocad_mcp"],
        env=env,
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"initialized; tools={len(tools.tools)}; backend=ezdxf", flush=True)
            try:
                async with asyncio.timeout(10):
                    result = await session.call_tool(
                        "system", {"operation": "health", "data": {}}
                    )
            except TimeoutError:
                print("REPRO: system.health did not respond within 10 seconds", flush=True)
                return 1

            print(
                "RESULT:",
                " ".join(getattr(item, "text", "") for item in result.content),
                flush=True,
            )
            return 0 if not result.isError else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
