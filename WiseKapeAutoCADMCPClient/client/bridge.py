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


def result_payload(result):
    """Decode JSON returned by WiseKape's category-based MCP tools."""
    data = result.data
    if isinstance(data, dict) and "result" in data:
        data = data["result"]
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            pass
    if not isinstance(data, (dict, list)):
        for item in result.content:
            text = getattr(item, "text", None)
            if text:
                try:
                    data = json.loads(text)
                    break
                except json.JSONDecodeError:
                    continue
    return data if isinstance(data, dict) else {"value": data}


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
        self.wisekape = False

    async def call_status(self, client):
        if self.wisekape:
            result = await client.call_tool("system", {"operation": "health"}, raise_on_error=False)
            payload = result_payload(result)
            return {**payload, "connected": not result.is_error and payload.get("ok") is True}
        result = await client.call_tool("system_status", {}, raise_on_error=False)
        return result.data or {"connected": False}

    async def call_drawing_info(self, client):
        if self.wisekape:
            result = await client.call_tool("drawing", {"operation": "info"}, raise_on_error=False)
            payload = result_payload(result)
            drawing = payload.get("payload", {})
            path = drawing.get("save_path") or ""
            return {
                "name": Path(path).name if path else "Untitled.dxf",
                "full_path": path,
                "units": drawing.get("units"),
                "entity_count": drawing.get("entity_count", 0),
                **drawing,
            }, result
        result = await client.call_tool("drawing_info", {}, raise_on_error=False)
        return result.data or {}, result

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
                        self.wisekape = False
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
                        self.wisekape = "system" in self.catalog and "drawing" in self.catalog and "system_status" not in self.catalog
                        self.status = await self.call_status(client)
                        if not self.status.get("connected"):
                            raise ValueError(json.dumps(self.status, ensure_ascii=False))
                        self.session = uuid.uuid4().hex
                        self.backend = self.status.get("backend")
                        value = self.snapshot()
                    elif action == "reconnect":
                        if client is None:
                            raise ValueError("Chưa có kết nối MCP để làm mới.")
                        if self.wisekape:
                            self.status = await self.call_status(client)
                        else:
                            result = await client.call_tool("system_reconnect", {}, raise_on_error=False)
                            self.status = result.data or {"connected": False}
                        if not self.status.get("connected"):
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
                            self.status = await self.call_status(client)
                            if not self.status.get("connected"):
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
                            if self.wisekape:
                                system_result = await client.call_tool("system", {"operation": "health"}, raise_on_error=False)
                                system_data = self.status if not system_result.is_error else {"connected": False}
                                drawing_data, drawing_result = await self.call_drawing_info(client)
                                value["system_status"] = {"is_error": system_result.is_error, "data": system_data, "content": [item.model_dump(mode="json") for item in system_result.content]}
                                value["drawing_info"] = {"is_error": drawing_result.is_error, "data": drawing_data, "content": [item.model_dump(mode="json") for item in drawing_result.content]}
                                if system_result.is_error or not system_data.get("connected"):
                                    raise ValueError("MCP không còn kết nối tới server WiseKape.")
                            else:
                                for name in ("system_status", "drawing_info"):
                                    if name in self.catalog:
                                        result = await client.call_tool(name, {}, raise_on_error=False)
                                        value[name] = serialize(result)
                                        if name == "system_status" and (result.is_error or not (result.data or {}).get("connected")):
                                            raise ValueError("MCP không còn kết nối với bản vẽ.")
                    elif action == "execute":
                        if client is None or not self.session or payload["session"] != self.session:
                            raise ValueError("Phiên MCP đã đổi. Hãy lập phương án mới.")
                        steps = payload["steps"]
                        validate_steps(steps, self.catalog)
                        expected = payload.get("expected_drawing")
                        if expected:
                            current_data, current = await self.call_drawing_info(client)
                            fields = ("name", "full_path", "units", "entity_count")
                            if current.is_error or any(
                                current_data.get(key) != expected.get(key) for key in fields
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
