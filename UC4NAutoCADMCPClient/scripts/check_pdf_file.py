"""Check PDF page images reach the real Codex planner; no CAD mutation."""

import json
from pathlib import Path

import httpx
import pymupdf

root = Path(__file__).resolve().parents[1]
headers = {"Authorization": "Bearer " + (root / "data/operator-token.txt").read_text().strip()}
with pymupdf.open() as doc:
    page = doc.new_page()
    page.insert_text((40, 60), "Requirement: Use drawing_info to read current drawing name.")
    page.insert_text((40, 90), "Do not create, modify or save anything in the drawing.")
    content = doc.tobytes()
with httpx.Client(base_url="http://127.0.0.1:8767", headers=headers, timeout=180) as web:
    response = web.post("/api/files", files={"file": ("read-requirements.pdf", content)})
    response.raise_for_status()
    attachment = response.json()
    response = web.post(
        "/api/plan",
        json={
            "attachment_id": attachment["id"],
            "tool_names": ["drawing_info"],
            "model": "default",
        },
    )
    response.raise_for_status()
    proposal = response.json()
    assert proposal.get("id"), proposal
    assert all(step["tool"] == "drawing_info" for step in proposal["steps"])
    (root / "data/pdf-file-check.json").write_text(
        json.dumps(
            {
                "attachment": attachment,
                "proposal": proposal,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("PDF text and page-image Codex plan passed; no CAD calls executed.")
