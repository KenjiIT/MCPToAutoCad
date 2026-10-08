# Slacker AutoCAD MCP: local trial

This folder is a checkout of [Slacker-LLC/autocad-mcp](https://github.com/Slacker-LLC/autocad-mcp), with local setup scripts and `http_host.py` added. Upstream targets a running AutoCAD 2026 session over Windows ActiveX/COM and normally uses stdio. The HTTP host adapts its same tool schemas and handlers to Streamable HTTP for the U-C4N browser client.

## Start

In PowerShell, from this folder:

```powershell
.\setup-local.ps1
.\start-http.ps1 -Background
```

The endpoint is `http://127.0.0.1:8770/mcp`. In the U-C4N client at `http://127.0.0.1:8767`, use that endpoint and leave the MCP bearer token blank. Start with the read-only `autocad_status`, `list_open_drawings`, and `get_active_drawing_info` tools.

The U-C4N web app still requires its own operator token from `UC4NAutoCADMCPClient/data/operator-token.txt` in the **Token client** field. That token authenticates the browser to the client app; it is not sent to Slacker. The adapter reports the MCP session as connected even before a drawing is open, with `cad_connected` and `message` showing AutoCAD readiness separately. Open a drawing before calling CAD editing tools.

AutoCAD 2026 must already be open with a drawing. The adapter disables worker-thread dispatch so all tool calls stay serialized on the HTTP server's COM thread. Only use drawing-changing tools when ready to modify the active AutoCAD document.

To run in the foreground, omit `-Background`. Logs for background mode are in `data/http.stdout.log` and `data/http.stderr.log`; stop with `./stop-http.ps1`.

The upstream checkout and license notices are preserved. Local adapter/setup files are additions; upstream source was not modified.
