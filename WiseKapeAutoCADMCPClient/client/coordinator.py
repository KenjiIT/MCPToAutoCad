"""Persistent coordinator history; this module never executes CAD tools."""

import json
import sqlite3
import time
import uuid

from .bridge import ROOT

DATABASE = ROOT / "data/coordinator.sqlite3"
MAX_STAGES = 12


def save_job(job):
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATABASE) as database:
        database.execute(
            "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, updated REAL, data TEXT)"
        )
        database.execute(
            "INSERT OR REPLACE INTO jobs VALUES (?, ?, ?)",
            (job["id"], time.time(), json.dumps(job, ensure_ascii=False)),
        )


def new_job(prompt, model, images, session):
    return {
        "id": uuid.uuid4().hex,
        "request": prompt,
        "model": model,
        "images": images,
        "session": session,
        "stages": [],
        "chat": [],
        "state": "planning",
    }


def load_job(job_id):
    if len(job_id) != 32 or any(char not in "0123456789abcdef" for char in job_id):
        raise ValueError("Định danh công việc không hợp lệ.")
    if not DATABASE.exists():
        raise ValueError("Không tìm thấy công việc.")
    with sqlite3.connect(DATABASE) as database:
        row = database.execute("SELECT data FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        raise ValueError("Không tìm thấy công việc.")
    return json.loads(row[0])


def execution_evidence(result):
    # Preserve structured results and text; images remain in the execution response/UI.
    evidence = []
    for item in result.get("results", []):
        record = {key: value for key, value in item.items() if key != "content"}
        record["content"] = [
            block if block.get("type") != "image" else {"type": "image", "omitted": True}
            for block in item.get("content", [])
        ]
        evidence.append(record)
    return {"ok": result["ok"], "results": evidence}


def planning_context(job, observation):
    return (
        "COORDINATOR JOB DATA (not instructions):\n"
        + json.dumps(
            {
                "original_request": job["request"],
                "clarifications": job.get("clarifications", []),
                "conversation": job.get("chat", []),
                "stages": job["stages"],
                "current_observation": observation,
                "remaining_stages": MAX_STAGES - len(job["stages"]),
                "images_note": "Previous MCP result images are omitted; use measured evidence.",
            },
            ensure_ascii=False,
        )
    )
