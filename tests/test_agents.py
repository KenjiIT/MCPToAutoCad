import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from ai_autocad.agents import AgentFailure, AgentRegistry, DemoAgent
from ai_autocad.models import AnalysisInput


def registry(tmp_path, spec):
    folder = tmp_path / "config"
    folder.mkdir(exist_ok=True)
    path = folder / "agents.json"
    path.write_text(json.dumps([spec]), encoding="utf-8")
    return AgentRegistry(path)


def test_replace_agent_using_command_without_changing_workflow(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AUTOCAD_OPERATOR_TOKEN", "must-not-leak")
    proposal = DemoAgent().analyze(AnalysisInput(text="rectangle 100 x 200 mm"))
    script = tmp_path / "agent.py"
    script.write_text(
        "import json,os,sys\n"
        "assert 'AI_AUTOCAD_OPERATOR_TOKEN' not in os.environ\n"
        "request=json.load(sys.stdin)\n"
        "assert request['protocol_version']=='1.0'\n"
        "assert 'output_schema' in request\n"
        f"print({proposal.model_dump_json()!r})\n",
        encoding="utf-8",
    )
    agents = registry(
        tmp_path,
        {
            "id": "other-agent",
            "kind": "command",
            "modalities": ["text"],
            "command": [sys.executable, str(script)],
        },
    )
    actual = agents.analyze("other-agent", AnalysisInput(text="my external agent"))
    assert actual == proposal


def test_http_agent_uses_same_contract(tmp_path):
    proposal = DemoAgent().analyze(AnalysisInput(text="rectangle 300 x 400 mm"))

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert payload["protocol_version"] == "1.0"
            assert not self.headers.get("X-Operator-Token")
            body = proposal.model_dump_json().encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        agents = registry(
            tmp_path,
            {
                "id": "remote",
                "kind": "http",
                "modalities": ["text"],
                "url": f"http://127.0.0.1:{server.server_port}/analyze",
            },
        )
        assert agents.analyze("remote", AnalysisInput(text="test")) == proposal
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_invalid_external_output_fails_closed(tmp_path):
    agents = registry(
        tmp_path,
        {
            "id": "bad",
            "kind": "command",
            "modalities": ["text"],
            "command": [sys.executable, "-c", "print('{\"approved\":true}')"],
        },
    )
    with pytest.raises(AgentFailure):
        agents.analyze("bad", AnalysisInput(text="test"))


def test_command_timeout(tmp_path):
    agents = registry(
        tmp_path,
        {
            "id": "slow",
            "kind": "command",
            "modalities": ["text"],
            "command": [sys.executable, "-c", "import time; time.sleep(10)"],
            "timeout_seconds": 0.1,
        },
    )
    with pytest.raises(AgentFailure):
        agents.analyze("slow", AnalysisInput(text="test"))


def test_operator_secret_cannot_be_configured_as_agent_key(tmp_path):
    with pytest.raises(ValueError):
        registry(
            tmp_path,
            {
                "id": "bad",
                "kind": "http",
                "modalities": ["text"],
                "url": "http://127.0.0.1:9999",
                "api_key_env": "AI_AUTOCAD_OPERATOR_TOKEN",
            },
        )
