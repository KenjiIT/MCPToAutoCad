"""Real HTTP smoke test using isolated temporary data and simulation only."""

import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx


def main():
    root = Path(__file__).resolve().parents[1]
    token = secrets.token_urlsafe(32)
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="ai-autocad-smoke-") as temporary:
        env = os.environ.copy()
        env.update(
            AI_AUTOCAD_OPERATOR_TOKEN=token,
            AI_AUTOCAD_DATA_DIR=temporary,
            AI_AUTOCAD_AGENTS_CONFIG=str(root / "config/agents.json"),
        )
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "ai_autocad.api:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=root,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False) as client:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError("Smoke server exited during startup")
                    try:
                        health = client.get("/health").json()
                        break
                    except httpx.ConnectError:
                        time.sleep(0.1)
                else:
                    raise RuntimeError("Smoke server did not start")
                assert health["cad_mode"] == "simulation"
                response = client.post(
                    "/requests",
                    json={
                        "agent_id": "demo",
                        "target_document": "simulation:smoke",
                        "input": {"text": "rectangle 5000 x 4000 mm"},
                    },
                )
                response.raise_for_status()
                job = response.json()
                path = f"/requests/{job['id']}"
                revision = {"revision": job["revision"], "digest": job["digest"]}
                headers = {"X-Operator-Token": token}
                assert (
                    client.post(path + "/execute", json=revision, headers=headers).status_code
                    == 409
                )
                preview = client.get(path + "/preview.svg")
                preview.raise_for_status()
                assert "5000" in preview.text and "4000" in preview.text
                response = client.post(
                    path + "/approve",
                    headers=headers,
                    json={
                        **revision,
                        "accepted_review_items": job["review_items"],
                    },
                )
                response.raise_for_status()
                response = client.post(path + "/execute", headers=headers, json=revision)
                response.raise_for_status()
                result = response.json()
                assert result["status"] == "completed"
                assert result["result"]["mode"] == "simulation"
                assert result["result"]["verified_readback"]
                print(
                    json.dumps(
                        {
                            "http_smoke": "passed",
                            "execution_mode": "simulation",
                            "approval_gate": "blocked before confirmation",
                            "readback": "5000 x 4000 mm rectangle verified",
                            "real_autocad_modified": False,
                        },
                        indent=2,
                    )
                )
        finally:
            # Windows venv python.exe may launch another python process. Stop this
            # exact test process tree so no listener or SQLite handle is left behind.
            if os.name == "nt" and process.poll() is None:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    main()
