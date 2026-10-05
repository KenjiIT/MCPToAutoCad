import hmac
import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.security import APIKeyHeader

from .agents import AgentFailure, AgentRegistry
from .cad import CadUnavailable, load_cad
from .models import (
    AnalysisInput,
    ApprovalRequest,
    CreateRequest,
    DrawingProposal,
    ExecuteRequest,
    RevisionRequest,
)
from .preview import render_svg
from .workflow import Conflict, Workflow

PROJECT_ROOT = Path(__file__).resolve().parents[2]
operator_header = APIKeyHeader(name="X-Operator-Token", auto_error=False)


def create_app(
    data_dir: Path | None = None,
    agents_config: Path | None = None,
    cad_config: Path | None = None,
    operator_token: str | None = None,
) -> FastAPI:
    data_dir = data_dir or Path(os.environ.get("AI_AUTOCAD_DATA_DIR", PROJECT_ROOT / "data"))
    agents_config = agents_config or Path(
        os.environ.get(
            "AI_AUTOCAD_AGENTS_CONFIG",
            PROJECT_ROOT / "config/agents.json",
        )
    )
    cad_config = cad_config or PROJECT_ROOT / "config/cad.json"
    token = (
        operator_token
        if operator_token is not None
        else os.environ.get(
            "AI_AUTOCAD_OPERATOR_TOKEN",
            "",
        )
    )
    registry = AgentRegistry(agents_config)
    cad = load_cad(cad_config, data_dir)
    workflow = Workflow(data_dir / "workflow.sqlite3", registry, cad)
    app = FastAPI(title="AI AutoCAD base", version="0.1.0")
    app.state.workflow = workflow

    def require_operator(provided: str | None = Depends(operator_header)):
        if len(token) < 32:
            raise HTTPException(503, "Configure an operator token with at least 32 characters")
        if not provided or not hmac.compare_digest(provided.encode(), token.encode()):
            raise HTTPException(403, "Human operator credential required")

    @app.exception_handler(Conflict)
    async def conflict_handler(_, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(KeyError)
    async def missing_handler(_, exc):
        return JSONResponse(status_code=404, content={"detail": "Request not found"})

    @app.exception_handler(AgentFailure)
    async def agent_handler(_, exc):
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(CadUnavailable)
    async def cad_handler(_, exc):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "cad_mode": cad.name,
            "real_cad_verified": False,
            "operator_configured": len(token) >= 32,
        }

    @app.get("/agents")
    def agents():
        return [
            {"id": s.id, "kind": s.kind, "modalities": s.modalities}
            for s in registry.specs.values()
        ]

    @app.get("/contracts/proposal")
    def proposal_schema():
        return DrawingProposal.model_json_schema()

    @app.get("/contracts/input")
    def input_schema():
        return AnalysisInput.model_json_schema()

    @app.post("/requests", status_code=201)
    def create(request: CreateRequest):
        return workflow.create(request)

    @app.get("/requests/{job_id}")
    def get(job_id: str):
        return workflow.get(job_id)

    @app.get("/requests/{job_id}/events")
    def events(job_id: str):
        return workflow.events(job_id)

    @app.get("/requests/{job_id}/preview.svg")
    def preview(job_id: str):
        proposal = DrawingProposal.model_validate(workflow.get(job_id)["proposal"])
        return Response(
            render_svg(proposal),
            media_type="image/svg+xml",
            headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"},
        )

    @app.put("/requests/{job_id}/proposal")
    def revise(job_id: str, request: RevisionRequest):
        return workflow.revise(job_id, request)

    @app.post("/requests/{job_id}/approve", dependencies=[Depends(require_operator)])
    def approve(job_id: str, request: ApprovalRequest):
        return workflow.approve(job_id, request)

    @app.post("/requests/{job_id}/execute", dependencies=[Depends(require_operator)])
    def execute(job_id: str, request: ExecuteRequest):
        return workflow.execute(job_id, request)

    return app
