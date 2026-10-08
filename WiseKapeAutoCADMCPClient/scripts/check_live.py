"""Read-only acceptance check against the running client and AutoCAD."""

import json
import sys
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8")
root = Path(__file__).resolve().parents[1]
headers = {"Authorization": "Bearer " + (root / "data/operator-token.txt").read_text().strip()}
with httpx.Client(base_url="http://127.0.0.1:8771", headers=headers, timeout=190) as web:
    response = web.post("/api/connect", json={"endpoint": "http://127.0.0.1:8769/mcp"})
    response.raise_for_status()
    connection = response.json()
    print(json.dumps(connection, ensure_ascii=False, indent=2))
    response = web.post(
        "/api/manual-plan",
        json={
            "steps": [
                {"tool": "system_about", "arguments": {}},
                {"tool": "drawing_info", "arguments": {}},
                {"tool": "system_get_variable", "arguments": {"name": "INSUNITS"}},
            ]
        },
    )
    response.raise_for_status()
    proposal = response.json()
    response = web.post(f"/api/plans/{proposal['id']}/execute", json={"confirmed": True})
    response.raise_for_status()
    manual = response.json()
    print("Read-only results:", [r["tool"] for r in manual["results"]])
    assert manual["ok"], manual
    response = web.post(
        "/api/plan",
        json={
            "prompt": "Đọc tên bản vẽ hiện tại bằng drawing_info, không thay đổi bản vẽ.",
            "tool_names": ["drawing_info", "system_status"],
            "model": "default",
        },
    )
    response.raise_for_status()
    ai = response.json()
    print("AI proposal:", json.dumps(ai, ensure_ascii=False, indent=2))
    assert ai.get("id") and ai["steps"]
    assert all(s["tool"] in {"drawing_info", "system_status"} for s in ai["steps"])
    response = web.post(f"/api/plans/{ai['id']}/execute", json={"confirmed": True})
    response.raise_for_status()
    ai_result = response.json()
    assert ai_result["ok"], ai_result
    (root / "data/live-check.json").write_text(
        json.dumps(
            {
                "connection": connection,
                "manual_result": manual,
                "ai_proposal": ai,
                "ai_result": ai_result,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("Live COM and Codex AI check passed.")
