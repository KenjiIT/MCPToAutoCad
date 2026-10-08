"""Run the upstream WiseKape MCP server over Streamable HTTP."""

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(description="WiseKape AutoCAD MCP over HTTP")
    parser.add_argument("--backend", choices=("ezdxf", "com", "file_ipc"), default="ezdxf")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8769)
    args = parser.parse_args()

    os.environ["AUTOCAD_MCP_BACKEND"] = args.backend
    from autocad_mcp.server import mcp

    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
