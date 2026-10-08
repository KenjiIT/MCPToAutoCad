import json

import ezdxf
import httpx
from client import api
from client.bridge import ROOT
from fastapi.testclient import TestClient


def test_real_mcp_dxf_and_approval(http_server):
    headers = {"Authorization": "Bearer " + api.TOKEN}
    target = http_server["drawings"] / "smoke-circle.dxf"
    connection_body = {key: http_server[key] for key in ("endpoint", "mcp_token")}
    with TestClient(api.app) as web:
        assert web.get("/health").json()["ok"]
        assert web.post("/api/connect", json=connection_body).status_code == 401
        assert httpx.post(http_server["endpoint"], json={}).status_code == 401
        unauthorized = web.post(
            "/api/connect", headers=headers, json={"endpoint": http_server["endpoint"]}
        )
        assert unauthorized.status_code == 400
        connection = web.post("/api/connect", headers=headers, json=connection_body)
        assert connection.status_code == 200, connection.text
        assert connection.json()["status"]["backend"] == "ezdxf"
        assert connection.json()["transport"] == "streamable-http"
        tools = web.get("/api/tools", headers=headers).json()
        assert any(t["name"] == "entity_create_circle" for t in tools)
        long_plan = web.post(
            "/api/manual-plan",
            headers=headers,
            json={"steps": [{"tool": "system_status", "arguments": {}} for _ in range(12)]},
        )
        assert long_plan.status_code == 200, long_plan.text
        long_result = web.post(
            f"/api/plans/{long_plan.json()['id']}/execute",
            headers=headers,
            json={"confirmed": True},
        )
        assert long_result.status_code == 200, long_result.text
        assert long_result.json()["ok"], long_result.text
        assert len(long_result.json()["results"]) == 12
        invalid = web.post(
            "/api/manual-plan",
            headers=headers,
            json={
                "steps": [
                    {"tool": "entity_create_circle", "arguments": {"cx": 0, "cy": 0, "radius": -1}}
                ]
            },
        )
        assert invalid.status_code == 422
        unknown = web.post(
            "/api/manual-plan",
            headers=headers,
            json={"steps": [{"tool": "invented_tool", "arguments": {}}]},
        )
        assert unknown.status_code == 422
        proposal = web.post(
            "/api/manual-plan",
            headers=headers,
            json={
                "steps": [
                    {"tool": "drawing_new", "arguments": {"bootstrap": False}},
                    {
                        "tool": "entity_create_circle",
                        "arguments": {"cx": 10, "cy": 20, "radius": 5},
                    },
                    {"tool": "drawing_save_as", "arguments": {"path": str(target)}},
                    {"tool": "drawing_info", "arguments": {}},
                ]
            },
        ).json()
        url = f"/api/plans/{proposal['id']}/execute"
        assert web.post(url, headers=headers, json={"confirmed": False}).status_code == 422
        result = web.post(url, headers=headers, json={"confirmed": True})
        assert result.status_code == 200, result.text
        assert result.json()["ok"], result.text
        assert len(result.json()["results"]) == 4
        assert web.post(url, headers=headers, json={"confirmed": True}).status_code == 409
        document = ezdxf.readfile(target)
        circles = list(document.modelspace().query("CIRCLE"))
        assert len(circles) == 1
        assert circles[0].dxf.radius == 5
        assert tuple(circles[0].dxf.center) == (10, 20, 0)
        stale = web.post(
            "/api/manual-plan",
            headers=headers,
            json={"steps": [{"tool": "system_status", "arguments": {}}]},
        ).json()
        web.post("/api/connect", headers=headers, json=connection_body)
        assert (
            web.post(
                f"/api/plans/{stale['id']}/execute", headers=headers, json={"confirmed": True}
            ).status_code
            == 409
        )
        # A real refused path halts the following call, preserving earlier results.
        outside = ROOT / "outside-allowlist.dxf"
        failed = web.post(
            "/api/manual-plan",
            headers=headers,
            json={
                "steps": [
                    {"tool": "system_status", "arguments": {}},
                    {"tool": "drawing_save_as", "arguments": {"path": str(outside)}},
                    {"tool": "system_status", "arguments": {}},
                ]
            },
        ).json()
        result = web.post(
            f"/api/plans/{failed['id']}/execute", headers=headers, json={"confirmed": True}
        ).json()
        assert not result["ok"]
        assert len(result["results"]) == 2
        assert not outside.exists()
        (ROOT / "data" / "smoke-result.json").write_text(
            json.dumps(
                {
                    "connection": connection.json(),
                    "failure_stop": result,
                    "verified_dxf": str(target),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    # Closing the client leaves the independent HTTP server and drawing alive.
    assert http_server["process"].poll() is None
    with TestClient(api.app) as web:
        response = web.post("/api/connect", headers=headers, json=connection_body)
        assert response.status_code == 200, response.text
        assert response.json()["status"]["backend"] == "ezdxf"
        empty = web.post(
            "/api/manual-plan",
            headers=headers,
            json={"steps": [{"tool": "drawing_info", "arguments": {}}]},
        ).json()
        result = web.post(
            f"/api/plans/{empty['id']}/execute", headers=headers, json={"confirmed": True}
        ).json()
        assert result["results"][0]["data"]["entity_count"] == 1
        stale = web.post(
            "/api/manual-plan",
            headers=headers,
            json={"steps": [{"tool": "drawing_info", "arguments": {}}]},
        ).json()
        http_server["stop"]()
        status = web.get("/api/status", headers=headers)
        assert status.status_code == 200
        assert not status.json()["status"]["connected"]
        assert status.json()["session"] is None
        failed = web.post(
            f"/api/plans/{stale['id']}/execute", headers=headers, json={"confirmed": True}
        )
        assert failed.status_code == 400
