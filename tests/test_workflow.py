import copy
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai_autocad.api import create_app
from ai_autocad.cad import SimulationCad
from ai_autocad.models import ExecuteRequest
from ai_autocad.workflow import Conflict

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "test-operator-only-credential-123456789"
HEADERS = {"X-Operator-Token": TOKEN}


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(data_dir=tmp_path, operator_token=TOKEN)) as client:
        yield client


def new_job(client, text="rectangle 5000 x 4000 mm"):
    response = client.post(
        "/requests",
        json={
            "agent_id": "demo",
            "target_document": "simulation:room",
            "input": {"text": text},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def version(job):
    return {"revision": job["revision"], "digest": job["digest"]}


def approve(client, job):
    return client.post(
        f"/requests/{job['id']}/approve",
        headers=HEADERS,
        json={
            **version(job),
            "accepted_review_items": job["review_items"],
        },
    )


def test_complete_flow_readback_and_double_click(client):
    job = new_job(client)
    path = f"/requests/{job['id']}"
    assert client.post(path + "/execute", headers=HEADERS, json=version(job)).status_code == 409
    assert client.get(path + "/preview.svg").headers["content-type"].startswith("image/svg+xml")
    assert approve(client, job).status_code == 200
    result = client.post(path + "/execute", headers=HEADERS, json=version(job)).json()
    assert result["status"] == "completed"
    assert result["result"]["mode"] == "simulation"
    assert result["result"]["entities"][0]["vertices_mm"] == [
        [0, 0],
        [5000, 0],
        [5000, 4000],
        [0, 4000],
    ]
    assert client.post(path + "/execute", headers=HEADERS, json=version(job)).json() == result
    events = client.get(path + "/events").json()
    assert [e["kind"] for e in events] == [
        "proposed",
        "approved",
        "execution_started",
        "completed",
    ]


def test_provider_cannot_approve_without_operator_credential(client):
    job = new_job(client)
    response = client.post(
        f"/requests/{job['id']}/approve",
        json={
            **version(job),
            "accepted_review_items": job["review_items"],
        },
    )
    assert response.status_code == 403


def test_revision_invalidates_approval_and_old_confirmation(client):
    job = new_job(client)
    assert approve(client, job).status_code == 200
    proposal = copy.deepcopy(job["proposal"])
    proposal["entities"][0]["width"]["value_mm"] = 6000.0
    path = f"/requests/{job['id']}"
    revised = client.put(
        path + "/proposal",
        json={
            "expected_revision": 1,
            "proposal": proposal,
        },
    ).json()
    assert revised["revision"] == 2 and revised["approval"] is None
    assert revised["digest"] != job["digest"]
    assert approve(client, job).status_code == 409
    assert client.post(path + "/execute", headers=HEADERS, json=version(revised)).status_code == 409
    assert approve(client, revised).status_code == 200


def test_missing_dimensions_cannot_be_approved(client):
    job = new_job(client, "draw a room")
    assert job["proposal"]["unresolved_questions"]
    assert approve(client, job).status_code == 409


def test_assumptions_must_be_accepted(client):
    job = new_job(client)
    response = client.post(
        f"/requests/{job['id']}/approve",
        headers=HEADERS,
        json={
            **version(job),
            "accepted_review_items": [],
        },
    )
    assert response.status_code == 409


def test_estimates_stay_labeled_after_confirmation(client):
    job = new_job(client)
    job["proposal"]["entities"][0]["width"]["source"] = "inferred"
    revised = client.put(
        f"/requests/{job['id']}/proposal",
        json={
            "expected_revision": 1,
            "proposal": job["proposal"],
        },
    ).json()
    assert any("inferred" in item for item in revised["review_items"])
    result = approve(client, revised).json()
    assert result["proposal"]["entities"][0]["width"]["source"] == "inferred"


@pytest.mark.parametrize("mutation", ["extra", "negative", "string_number", "duplicate", "units"])
def test_bad_agent_contract_is_rejected(client, mutation):
    job = new_job(client)
    proposal = job["proposal"]
    if mutation == "extra":
        proposal["execute_command"] = "anything"
    elif mutation == "negative":
        proposal["entities"][0]["height"]["value_mm"] = -5
    elif mutation == "string_number":
        proposal["entities"][0]["height"]["value_mm"] = "4000"
    elif mutation == "duplicate":
        proposal["entities"].append(proposal["entities"][0])
    else:
        proposal["units"] = "m"
    assert (
        client.put(
            f"/requests/{job['id']}/proposal",
            json={
                "expected_revision": 1,
                "proposal": proposal,
            },
        ).status_code
        == 422
    )


def test_expired_confirmation(client):
    client.app.state.workflow.approval_ttl = -1
    job = new_job(client)
    assert approve(client, job).status_code == 200
    assert (
        client.post(
            f"/requests/{job['id']}/execute", headers=HEADERS, json=version(job)
        ).status_code
        == 409
    )


def test_state_survives_restart(tmp_path):
    with TestClient(create_app(data_dir=tmp_path, operator_token=TOKEN)) as first:
        job = new_job(first)
        assert approve(first, job).status_code == 200
    with TestClient(create_app(data_dir=tmp_path, operator_token=TOKEN)) as second:
        assert second.get(f"/requests/{job['id']}").json()["status"] == "approved"


def test_real_cad_blocked_even_when_config_claims_verified(tmp_path):
    config = tmp_path / "cad.json"
    config.write_text(json.dumps({"adapter": "autocad", "verified": True}))
    with TestClient(
        create_app(data_dir=tmp_path, cad_config=config, operator_token=TOKEN)
    ) as client:
        job = new_job(client)
        assert approve(client, job).status_code == 200
        response = client.post(f"/requests/{job['id']}/execute", headers=HEADERS, json=version(job))
        assert response.status_code == 503
        assert client.get(f"/requests/{job['id']}").json()["status"] == "approved"


def test_transport_failure_never_retries_blindly(client):
    class BrokenCad:
        name = "simulation"
        calls = 0

        def check_ready(self, target):
            pass

        def execute(self, *args):
            self.calls += 1
            raise TimeoutError("May have drawn before timeout")

    broken = BrokenCad()
    client.app.state.workflow.cad = broken
    job = new_job(client)
    approve(client, job)
    path = f"/requests/{job['id']}/execute"
    result = client.post(path, headers=HEADERS, json=version(job)).json()
    assert result["status"] == "needs_reconciliation"
    assert client.post(path, headers=HEADERS, json=version(job)).status_code == 409
    assert broken.calls == 1


def test_concurrent_execution_claims_once(client, tmp_path):
    entered, release = threading.Event(), threading.Event()

    class SlowCad(SimulationCad):
        def execute(self, *args):
            entered.set()
            assert release.wait(5)
            return super().execute(*args)

    workflow = client.app.state.workflow
    workflow.cad = SlowCad(tmp_path / "slow.sqlite3")
    job = new_job(client)
    approve(client, job)
    req = ExecuteRequest(**version(job))
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(workflow.execute, job["id"], req)
        assert entered.wait(5)
        try:
            with pytest.raises(Conflict):
                workflow.execute(job["id"], req)
        finally:
            release.set()
        assert first.result()["status"] == "completed"


def test_database_tampering_invalidates_digest(client):
    job = new_job(client)
    approve(client, job)
    workflow = client.app.state.workflow
    with sqlite3.connect(workflow.path) as conn:
        stored = json.loads(conn.execute("SELECT body FROM jobs").fetchone()[0])
        stored["target_document"] = "simulation:other"
        conn.execute("UPDATE jobs SET body = ?", (json.dumps(stored),))
    response = client.post(f"/requests/{job['id']}/execute", headers=HEADERS, json=version(job))
    assert response.status_code == 409


def test_missing_operator_config_is_closed(tmp_path):
    with TestClient(create_app(data_dir=tmp_path, operator_token="")) as client:
        job = new_job(client)
        assert approve(client, job).status_code == 503


def test_unsupported_image_rejected(client):
    response = client.post(
        "/requests",
        json={
            "agent_id": "demo",
            "target_document": "simulation:room",
            "input": {
                "text": "analyze",
                "attachments": [
                    {"kind": "image", "reference": "asset:1", "description": "room photo"},
                ],
            },
        },
    )
    assert response.status_code == 502


def test_bad_readback_is_not_reported_as_success(client):
    class WrongGeometry:
        name = "simulation"

        def check_ready(self, target):
            pass

        def execute(self, *args):
            return []

    client.app.state.workflow.cad = WrongGeometry()
    job = new_job(client)
    approve(client, job)
    result = client.post(
        f"/requests/{job['id']}/execute", headers=HEADERS, json=version(job)
    ).json()
    assert result["status"] == "needs_reconciliation"
    assert result["result"]["verified_readback"] is False


def test_zero_dimension_from_demo_returns_controlled_error(client):
    response = client.post(
        "/requests",
        json={
            "agent_id": "demo",
            "target_document": "simulation:test",
            "input": {"text": "rectangle 0 x 4000 mm"},
        },
    )
    assert response.status_code == 502


def test_committed_contracts_match_runtime_schema():
    from ai_autocad.models import AnalysisInput, DrawingProposal

    for name, model in (
        ("analysis-input.v1", AnalysisInput),
        ("drawing-proposal.v1", DrawingProposal),
    ):
        stored = json.loads((ROOT / "contracts" / f"{name}.schema.json").read_text("utf-8"))
        assert stored == model.model_json_schema()
