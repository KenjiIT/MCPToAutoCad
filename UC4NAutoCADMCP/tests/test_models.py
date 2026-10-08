import io
import json
import time

import pytest
from client import api, codex_agent, planner
from client.codex_agent import CodexAgent, resolve_selection
from fastapi.testclient import TestClient


def test_model_catalog_settings_and_validation(isolated_ai_settings):
    headers = {"Authorization": "Bearer " + api.TOKEN}
    with TestClient(api.app) as web:
        assert web.get("/api/models").status_code == 401
        response = web.get("/api/models?refresh=true", headers=headers)
        assert response.status_code == 200
        assert response.json()["models"] == isolated_ai_settings
        invalid = web.post("/api/ai-settings", headers=headers, json={"model": "invented"})
        assert invalid.status_code == 422
        invalid = web.post("/api/ai-settings", headers=headers, json={
            "model": "text-model", "reasoning_effort": "high",
        })
        assert invalid.status_code == 422
        valid = {"model": "test-model", "reasoning_effort": "high", "engine": "agent"}
        response = web.post("/api/ai-settings", headers=headers, json=valid)
        assert response.status_code == 200
        assert web.get("/api/models", headers=headers).json()["settings"] == valid
        assert json.loads(api.SETTINGS_FILE.read_text()) == valid
        assert resolve_selection("default", None) == ("test-model", "medium")
        with pytest.raises(ValueError, match="ảnh"):
            resolve_selection("text-model", "low", has_images=True)


def test_agent_protocol_uses_selected_model_and_effort(monkeypatch):
    agent = CodexAgent()
    calls = []
    monkeypatch.setattr(agent, "_start", lambda: None)
    agent.folder = type("Folder", (), {"name": "isolated-workspace"})()

    def rpc(method, params, deadline):
        calls.append((method, params))
        if method == "thread/start":
            return {"thread": {"id": "thread-1"}, "model": "test-model"}
        if method == "turn/start":
            return {"turn": {"id": "turn-1"}}
        return {}

    monkeypatch.setattr(agent, "_rpc", rpc)
    answer = '{"decision":"complete"}'
    agent.inbox.put({"method": "item/completed", "params": {
        "item": {"type": "agentMessage", "text": answer},
    }})
    agent.inbox.put({"method": "turn/completed", "params": {
        "turn": {"id": "turn-1", "status": "completed"},
    }})
    result = agent.propose("Trusted skill", "Request", [], "test-model", "high", [], {})
    assert result == answer
    thread = calls[0][1]
    assert thread["developerInstructions"] == "Trusted skill"
    assert thread["sandbox"] == "read-only"
    assert thread["approvalPolicy"] == "never"
    turn = calls[1][1]
    assert turn["model"] == "test-model"
    assert turn["effort"] == "high"
    assert agent.snapshot()["phase"] == "completed"


def test_agent_refuses_tool_execution_requests(monkeypatch):
    agent = CodexAgent()
    sent = []
    monkeypatch.setattr(agent, "_send", sent.append)
    agent.inbox.put({"id": 12, "method": "item/tool/call", "params": {
        "tool": "entity_create_circle", "arguments": {"radius": 5},
    }})
    with pytest.raises(ValueError, match="từ chối"):
        agent._next(time.monotonic() + 1)
    assert sent[0]["id"] == 12
    assert "error" in sent[0]


def test_agent_launch_handles_bom_and_hyphenated_mcp_name(tmp_path, monkeypatch):
    config_dir = tmp_path / ".codex"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text(
        '[mcp_servers.example-cad]\ncommand = "example.exe"\n', encoding="utf-8-sig"
    )
    monkeypatch.setattr(codex_agent.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setattr(planner, "locate_codex", lambda: "fake-codex")
    launches = []

    class FakeProcess:
        def __init__(self, argv, **kwargs):
            launches.append(argv)
            self.stdin = io.StringIO()
            self.stdout = io.StringIO()

        def poll(self):
            return 0

        def wait(self, timeout):
            return 0

    monkeypatch.setattr(codex_agent.subprocess, "Popen", FakeProcess)
    local_agent = CodexAgent()
    monkeypatch.setattr(local_agent, "_rpc", lambda *args: {})
    try:
        local_agent._start()
        assert "mcp_servers.example-cad.enabled=false" in launches[0]
        assert not any('mcp_servers."' in argument for argument in launches[0])
    finally:
        local_agent.close()
