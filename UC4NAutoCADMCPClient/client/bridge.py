"""Connect to an independently managed MCP server over Streamable HTTP."""

import asyncio
import json
import uuid
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlsplit

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def serialize(result):
    return {
        "is_error": result.is_error,
        "data": result.data,
        "content": [item.model_dump(mode="json") for item in result.content],
    }


def validate_steps(steps, catalog):
    if not steps:
        raise ValueError("Phương án cần ít nhất 1 bước.")
    for step in steps:
        tool = catalog.get(step["tool"])
        if tool is None:
            raise ValueError(f"Tool không có trong phiên MCP: {step['tool']}")
        if not isinstance(step["arguments"], dict):
            raise ValueError("Tham số phải là JSON object.")
        Draft202012Validator(tool["inputSchema"]).validate(step["arguments"])


class Bridge:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.catalog = {}
        self.session = None
        self.backend = None
        self.endpoint = None
        self.status = {"connected": False}

    async def request(self, action, **payload):
        future = asyncio.get_running_loop().create_future()
        await self.queue.put((action, payload, future))
        return await asyncio.shield(future)

    async def run(self):
        client = None
        try:
            while True:
                action, payload, future = await self.queue.get()
                try:
                    if action in {"connect", "stop"}:
                        self.session = None
                        self.catalog = {}
                        self.status = {"connected": False}
                        if client is not None:
                            previous = client
                            client = None
                            with suppress(Exception):
                                await previous.__aexit__(None, None, None)
                        if action == "stop":
                            future.set_result(None)
                            return
                        endpoint = payload["endpoint"].strip()
                        url = urlsplit(endpoint)
                        if (
                            url.scheme not in {"http", "https"}
                            or not url.hostname
                            or url.username
                            or url.password
                            or url.fragment
                        ):
                            raise ValueError("Endpoint MCP phải là URL HTTP/HTTPS hợp lệ.")
                        self.endpoint = endpoint
                        token = payload.get("mcp_token", "")
                        transport = StreamableHttpTransport(
                            url=endpoint,
                            headers={"Authorization": "Bearer " + token} if token else {},
                        )
                        candidate = Client(transport, timeout=150, init_timeout=10)
                        await candidate.__aenter__()
                        client = candidate
                        self.catalog = {
                            t.name: t.model_dump(mode="json") for t in await client.list_tools()
                        }
                        result = await client.call_tool("system_status", {}, raise_on_error=False)
                        self.status = result.data or {}
                        if result.is_error or not self.status.get("connected"):
                            raise ValueError(json.dumps(self.status, ensure_ascii=False))
                        self.session = uuid.uuid4().hex
                        self.backend = self.status.get("backend")
                        value = self.snapshot()
                    elif action == "reconnect":
                        if client is None or "system_reconnect" not in self.catalog:
                            raise ValueError(
                                "Server chưa có tool system_reconnect. Hãy khởi động lại MCP server đã cập nhật."
                            )
                        result = await client.call_tool(
                            "system_reconnect", {}, raise_on_error=False
                        )
                        self.status = result.data or {"connected": False}
                        if result.is_error or not self.status.get("connected"):
                            self.session = None
                            raise ValueError(json.dumps(self.status, ensure_ascii=False))
                        self.catalog = {
                            t.name: t.model_dump(mode="json") for t in await client.list_tools()
                        }
                        self.session = uuid.uuid4().hex
                        self.backend = self.status.get("backend")
                        value = self.snapshot()
                    elif action == "status":
                        if client is not None and self.session:
                            result = await client.call_tool(
                                "system_status", {}, raise_on_error=False
                            )
                            self.status = result.data or {"connected": False}
                            if result.is_error or not self.status.get("connected"):
                                self.session = None
                        value = self.snapshot()
                    elif action in {"catalog", "observe"}:
                        if client is None or not self.session or payload["session"] != self.session:
                            raise ValueError("Phiên MCP đã đổi. Hãy kết nối và lập phương án mới.")
                        if action == "catalog":
                            self.catalog = {
                                t.name: t.model_dump(mode="json") for t in await client.list_tools()
                            }
                            value = list(self.catalog.values())
                        else:
                            value = {}
                            for name in ("system_status", "drawing_info"):
                                if name in self.catalog:
                                    result = await client.call_tool(name, {}, raise_on_error=False)
                                    value[name] = serialize(result)
                                    if name == "system_status" and (
                                        result.is_error or not (result.data or {}).get("connected")
                                    ):
                                        raise ValueError("MCP không còn kết nối với bản vẽ.")
                    elif action == "execute":
                        if client is None or not self.session or payload["session"] != self.session:
                            raise ValueError("Phiên MCP đã đổi. Hãy lập phương án mới.")
                        steps = payload["steps"]
                        validate_steps(steps, self.catalog)
                        expected = payload.get("expected_drawing")
                        if expected:
                            current = await client.call_tool(
                                "drawing_info", {}, raise_on_error=False
                            )
                            fields = ("name", "full_path", "units", "entity_count")
                            if current.is_error or any(
                                (current.data or {}).get(key) != expected.get(key) for key in fields
                            ):
                                raise ValueError(
                                    "Bản vẽ hoặc metadata đã đổi. Hãy lập lại phương án."
                                )
                        results = []
                        for step in steps:
                            try:
                                result = await client.call_tool(
                                    step["tool"], step["arguments"], raise_on_error=False
                                )
                            except Exception as exc:
                                results.append(
                                    {
                                        "tool": step["tool"],
                                        "is_error": True,
                                        "error": str(exc),
                                        "outcome_unknown": True,
                                    }
                                )
                                self.session = None
                                self.status = {"connected": False, "error": str(exc)}
                                break
                            results.append({"tool": step["tool"], **serialize(result)})
                            if result.is_error:
                                break
                        value = {"ok": not any(r["is_error"] for r in results), "results": results}
                    else:
                        raise ValueError("Unknown bridge action")
                    future.set_result(value)
                except Exception as exc:
                    if action in {"connect", "status", "catalog", "observe"}:
                        self.session = None
                        self.status = {"connected": False, "error": str(exc)}
                    if action == "status":
                        future.set_result(self.snapshot())
                    else:
                        future.set_exception(exc)
        finally:
            if client is not None:
                with suppress(Exception):
                    await client.__aexit__(None, None, None)

    def snapshot(self):
        return {
            "session": self.session,
            "backend": self.backend,
            "transport": "streamable-http",
            "endpoint": self.endpoint,
            "status": self.status,
            "tool_count": len(self.catalog),
        }
