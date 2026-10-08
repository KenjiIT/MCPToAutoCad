import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_ai_settings(tmp_path, monkeypatch):
    from client import api, coordinator

    catalog = [
        {
            "id": "test-model", "model": "test-model", "displayName": "Test model",
            "isDefault": True, "defaultReasoningEffort": "medium",
            "supportedReasoningEfforts": [
                {"reasoningEffort": value, "description": value}
                for value in ("low", "medium", "high")
            ],
            "inputModalities": ["text", "image"],
        },
        {
            "id": "text-model", "model": "text-model", "displayName": "Text model",
            "isDefault": False, "defaultReasoningEffort": "low",
            "supportedReasoningEfforts": [{"reasoningEffort": "low", "description": "Fast"}],
            "inputModalities": ["text"],
        },
    ]
    monkeypatch.setattr(api.agent, "list_models", lambda refresh=False: catalog)
    monkeypatch.setattr(api, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(coordinator, "DATABASE", tmp_path / "coordinator.sqlite3")
    return catalog


@pytest.fixture
def http_server(tmp_path):
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    drawings = tmp_path / "drawings"
    token = "integration-test-mcp-token"
    env = {**os.environ, "PYTHONUTF8": "1", "MCP_AUTH_TOKEN": token}
    log_path = tmp_path / "server.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                str(root / "mcp_server" / "run.py"),
                "--backend",
                "ezdxf",
                "--port",
                str(port),
                "--drawings-dir",
                str(drawings),
            ],
            cwd=root / "mcp_server",
            env=env,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            deadline = time.monotonic() + 30
            while True:
                if process.poll() is not None or time.monotonic() > deadline:
                    pytest.fail(log_path.read_text(encoding="utf-8"))
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.1)

            def stop():
                if process.poll() is not None:
                    return
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        capture_output=True,
                        check=False,
                    )
                else:
                    process.terminate()
                process.wait(timeout=10)

            yield {
                "endpoint": f"http://127.0.0.1:{port}/mcp",
                "mcp_token": token,
                "drawings": drawings,
                "process": process,
                "stop": stop,
            }
        finally:
            if os.name == "nt" and process.poll() is None:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                )
            elif process.poll() is None:
                process.terminate()
            process.wait(timeout=10)
