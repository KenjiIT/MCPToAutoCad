# WiseKape AutoCAD MCP — local project

This isolated working copy is from [`thewisekape/autocad-mcp`](https://github.com/thewisekape/autocad-mcp), separate from `UC4NAutoCADMCP`.

## Install

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup-local.ps1
```

The Python environment is local to this project. The upstream `setup.bat` is not used because it modifies global Claude/Codex configuration and AutoCAD's LISP startup settings.

## Start and stop

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-http.ps1 -Backend ezdxf -Background
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\stop-http.ps1
```

WiseKape listens at `http://127.0.0.1:8769/mcp` using Streamable HTTP. The `ezdxf` backend is headless and does not connect to the AutoCAD instance used by U-C4N. The local `.mcp.json` points to this endpoint. Server logs are in `data/server/`.

The upstream stdio transport reproduced a hang on backend-backed tool calls. Streamable HTTP was verified with `system.health` and `drawing.info`. Use `-Backend com` only when you intend to connect to live AutoCAD; U-C4N and WiseKape would then share that CAD process.

## Upstream source

- Repository: <https://github.com/thewisekape/autocad-mcp>
- Checked out commit: `7034dc444ba5b5680145a1eff52b4d83a262a75a`
- License: Apache-2.0 (see upstream `LICENSE` and `NOTICE`)
