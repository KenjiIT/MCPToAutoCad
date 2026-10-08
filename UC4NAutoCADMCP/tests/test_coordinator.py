import json
from pathlib import Path

from client import api, coordinator, planner
from client.planner import Proposal, Step
from fastapi.testclient import TestClient


def test_coordinator_full_catalog_stages_and_saved_history(http_server, tmp_path, monkeypatch):
    monkeypatch.setattr(coordinator, "DATABASE", tmp_path / "history.sqlite3")
    headers = {"Authorization": "Bearer " + api.TOKEN}
    calls = []

    def fake_plan(prompt, tools, model, images, **options):
        context = json.loads(prompt.split("\n", 1)[1])
        calls.append(context)
        assert "entity_create_circle" in {tool["name"] for tool in tools}
        assert len(tools) > 35  # Not limited by the legacy UI tool selection.
        assert context["original_request"] == "Tạo hai đường tròn R5 và R7."
        count = len(context["stages"])
        if count == 2:
            assert context["current_observation"]["drawing_info"]["data"]["entity_count"] >= 2
            return Proposal(
                summary="Đã tạo đủ hai đường tròn.",
                unresolved_questions=[],
                steps=[],
                decision="complete",
            )
        if count:
            evidence = context["stages"][0]["result"]
            assert evidence["ok"]
            assert evidence["results"][0]["data"]
        return Proposal(
            summary=f"Giai đoạn {count + 1}",
            unresolved_questions=[],
            steps=(
                [Step(tool="drawing_new", arguments_json='{"bootstrap":false}', explanation="Tạo.")]
                if count == 0 else []
            ) + [
                Step(
                    tool="entity_create_circle",
                    arguments_json=json.dumps({"cx": count * 20, "cy": 0, "radius": 5 + count * 2}),
                    explanation="Tạo đường tròn theo yêu cầu.",
                )
            ],
        )

    monkeypatch.setattr(api, "plan", fake_plan)
    with TestClient(api.app) as web:
        connection = web.post(
            "/api/connect",
            headers=headers,
            json={key: http_server[key] for key in ("endpoint", "mcp_token")},
        )
        assert connection.status_code == 200, connection.text
        first = web.post(
            "/api/plan",
            headers=headers,
            json={"prompt": "Tạo hai đường tròn R5 và R7.", "tool_names": ["system_status"]},
        )
        assert first.status_code == 200, first.text
        first = first.json()
        assert "_job" not in first
        first_url = f"/api/plans/{first['id']}/execute"
        assert web.post(first_url, headers=headers, json={"confirmed": False}).status_code == 422
        result = web.post(first_url, headers=headers, json={"confirmed": True})
        assert result.status_code == 200, result.text
        second = result.json()["coordinator"]
        assert second["stage"] == 2
        assert second["state"] == "ready"
        # The second stage is proposed but has no execution evidence until approval.
        history = web.get(f"/api/jobs/{first['job_id']}", headers=headers).json()
        assert history["stages"][1]["state"] == "awaiting_approval"
        assert "result" not in history["stages"][1]
        assert web.post(first_url, headers=headers, json={"confirmed": True}).status_code == 409
        result = web.post(
            f"/api/plans/{second['id']}/execute", headers=headers, json={"confirmed": True}
        )
        assert result.status_code == 200, result.text
        assert result.json()["coordinator"]["decision"] == "complete"
        assert len(calls) == 3
        assert "id" not in result.json()["coordinator"]
        stale = web.post(
            "/api/plan", headers=headers,
            json={"prompt": "Tạo hai đường tròn R5 và R7."},
        ).json()
        external = web.post(
            "/api/manual-plan", headers=headers,
            json={"steps": [{"tool": "entity_create_circle", "arguments": {
                "cx": 50, "cy": 0, "radius": 9,
            }}]},
        ).json()
        changed = web.post(
            f"/api/plans/{external['id']}/execute", headers=headers, json={"confirmed": True},
        )
        assert changed.json()["ok"]
        blocked = web.post(
            f"/api/plans/{stale['id']}/execute", headers=headers, json={"confirmed": True},
        )
        assert blocked.status_code == 400
        assert "metadata" in blocked.json()["detail"]
    # History can be read after closing the live client session.
    history = coordinator.load_job(first["job_id"])
    assert history["state"] == "complete"
    assert len(history["stages"]) == 2


def test_evaluation_failure_preserves_successful_execution(http_server, tmp_path, monkeypatch):
    monkeypatch.setattr(coordinator, "DATABASE", tmp_path / "history.sqlite3")
    headers = {"Authorization": "Bearer " + api.TOKEN}

    def fake_plan(prompt, tools, model, images, **options):
        context = json.loads(prompt.split("\n", 1)[1])
        if context["stages"]:
            raise ValueError("AI timeout")
        return Proposal(
            summary="Đọc bản vẽ.",
            unresolved_questions=[],
            steps=[Step(tool="system_status", arguments_json="{}", explanation="Kiểm tra.")],
        )

    monkeypatch.setattr(api, "plan", fake_plan)
    with TestClient(api.app) as web:
        web.post(
            "/api/connect",
            headers=headers,
            json={key: http_server[key] for key in ("endpoint", "mcp_token")},
        )
        proposal = web.post("/api/plan", headers=headers, json={"prompt": "Đọc bản vẽ."}).json()
        result = web.post(
            f"/api/plans/{proposal['id']}/execute", headers=headers, json={"confirmed": True}
        )
        assert result.status_code == 200, result.text
        assert result.json()["ok"]
        assert result.json()["coordinator"]["decision"] == "evaluation_failed"
        history = coordinator.load_job(proposal["job_id"])
        assert history["stages"][0]["result"]["ok"]
        assert history["state"] == "evaluation_failed"


def test_chat_can_resume_after_evaluation_failure(http_server, tmp_path, monkeypatch):
    monkeypatch.setattr(coordinator, "DATABASE", tmp_path / "history.sqlite3")
    headers = {"Authorization": "Bearer " + api.TOKEN}

    calls = 0

    def fake_plan(prompt, tools, model, images, **options):
        nonlocal calls
        calls += 1
        context = json.loads(prompt.split("\n", 1)[1])
        if not context["stages"]:
            return Proposal(
                summary="Tạo bản vẽ.", unresolved_questions=[],
                steps=[Step(tool="system_status", arguments_json="{}", explanation="Kiểm tra.")],
            )
        if calls == 2:
            raise ValueError("invalid geometry")
        return Proposal(
            summary="Tiếp tục từ trạng thái hiện tại.", unresolved_questions=[],
            steps=[Step(tool="system_status", arguments_json="{}", explanation="Kiểm tra lại.")],
        )

    monkeypatch.setattr(api, "plan", fake_plan)
    with TestClient(api.app) as web:
        web.post(
            "/api/connect", headers=headers,
            json={key: http_server[key] for key in ("endpoint", "mcp_token")},
        )
        first = web.post("/api/plan", headers=headers, json={"prompt": "Tạo bản vẽ."}).json()
        executed = web.post(
            f"/api/plans/{first['id']}/execute", headers=headers, json={"confirmed": True}
        )
        assert executed.json()["coordinator"]["decision"] == "evaluation_failed"
        resumed = web.post(
            "/api/chat", headers=headers,
            json={"job_id": first["job_id"], "message": "Hãy lập lại phương án."},
        )
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["decision"] == "plan"
        assert resumed.json()["stage"] == 2


def test_clarification_keeps_original_request(http_server, tmp_path, monkeypatch):
    monkeypatch.setattr(coordinator, "DATABASE", tmp_path / "history.sqlite3")
    headers = {"Authorization": "Bearer " + api.TOKEN}

    def fake_plan(prompt, tools, model, images, **options):
        context = json.loads(prompt.split("\n", 1)[1])
        assert context["original_request"] == "Vẽ đường tròn."
        if not context["clarifications"]:
            return Proposal(summary="Thiếu bán kính.", unresolved_questions=["Bán kính?"], steps=[])
        assert context["clarifications"] == ["Bán kính 5 mm."]
        return Proposal(
            summary="Vẽ R5.", unresolved_questions=[],
            steps=[Step(
                tool="entity_create_circle", arguments_json='{"cx":0,"cy":0,"radius":5}',
                explanation="Theo thông tin bổ sung.",
            )],
        )

    monkeypatch.setattr(api, "plan", fake_plan)
    with TestClient(api.app) as web:
        web.post(
            "/api/connect", headers=headers,
            json={key: http_server[key] for key in ("endpoint", "mcp_token")},
        )
        question = web.post("/api/plan", headers=headers, json={"prompt": "Vẽ đường tròn."}).json()
        assert question["decision"] == "questions"
        answer = web.post(
            "/api/plan", headers=headers,
            json={"job_id": question["job_id"], "prompt": "Bán kính 5 mm."},
        )
        assert answer.status_code == 200, answer.text
        assert answer.json()["job_id"] == question["job_id"]
        assert answer.json()["state"] == "ready"


def test_cli_includes_skill_and_requires_every_output_field(tmp_path, monkeypatch):
    skill = tmp_path / "SKILL.md"
    skill.write_text("Trusted coordinator instructions from project.", encoding="utf-8")
    monkeypatch.setattr(planner, "SKILL_FILE", skill)
    monkeypatch.setattr(planner, "locate_codex", lambda: "fake-codex")
    inputs = []

    class FakeProcess:
        returncode = 0

        def __init__(self, argv, **kwargs):
            schema = json.loads(Path(argv[argv.index("--output-schema") + 1]).read_text())
            assert set(schema["required"]) == set(schema["properties"])
            self.answer = Path(argv[argv.index("--output-last-message") + 1])
            assert argv[argv.index("--model") + 1] == "test-model"
            assert 'model_reasoning_effort="high"' in argv

        def communicate(self, message, timeout):
            inputs.append(message)
            self.answer.write_text(json.dumps({
                "summary": "Need dimensions", "unresolved_questions": ["Radius?"],
                "steps": [], "decision": "plan",
            }))

    monkeypatch.setattr(planner.subprocess, "Popen", FakeProcess)
    result = planner.plan("Draw a circle", [], "test-model", reasoning_effort="high")
    assert result.unresolved_questions == ["Radius?"]
    assert skill.read_text(encoding="utf-8") in inputs[0]
