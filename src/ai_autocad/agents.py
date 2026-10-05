"""Provider-neutral adapters. An agent can propose geometry, never approve or execute it."""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Literal, Protocol

import httpx
from pydantic import Field, ValidationError

from .models import AnalysisInput, Contract, DrawingProposal


class AgentFailure(Exception):
    pass


class AgentSpec(Contract):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    kind: Literal["demo", "command", "http"]
    modalities: list[Literal["text", "image", "audio"]]
    command: list[str] = Field(default_factory=list)
    url: str | None = None
    api_key_env: str | None = None
    timeout_seconds: float = Field(default=60.0, gt=0, le=300)


class AnalysisAgent(Protocol):
    def analyze(self, request: AnalysisInput) -> DrawingProposal: ...


INSTRUCTIONS = """Return only a DrawingProposal JSON object matching output_schema.
Never issue CAD commands, approve a proposal, or include executable code.
Use mm and WCS. Preserve the evidence source for each measurement.
Missing or ambiguous dimensions go in unresolved_questions, not invented measurements.
Mark inferred/proposed dimensions honestly; confirmation is not physical measurement.
Explain origin, layer, geometry meaning, and all assumptions for human review.
Attachment references are opaque; if you cannot read one, ask for the missing information.
Schema v1 supports only axis-aligned 2D rectangle outlines; unsupported requests need questions.
"""


def envelope(request: AnalysisInput) -> dict:
    return {
        "protocol_version": "1.0",
        "instructions": INSTRUCTIONS,
        "input": request.model_dump(),
        "output_schema": DrawingProposal.model_json_schema(),
    }


class DemoAgent:
    """Deterministic fixture, NOT a general language/vision model."""

    def analyze(self, request: AnalysisInput) -> DrawingProposal:
        result = {
            "schema_version": "1.0",
            "summary": "Demo: rectangular outline",
            "units": "mm",
            "coordinate_system": "WCS",
            "geometry_meaning": "Single outline only; no walls, doors or construction detail",
            "entities": [],
            "assumptions": [],
            "unresolved_questions": [],
        }
        match = re.fullmatch(
            r"rectangle\s+(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*mm",
            request.text.strip(),
            flags=re.IGNORECASE,
        )
        if not match or request.attachments:
            result["unresolved_questions"] = [
                "Demo accepts only: rectangle 5000 x 4000 mm. "
                "Choose an external agent for natural language, image or audio analysis."
            ]
        else:
            result["assumptions"] = ["Origin (0, 0) WCS; layer AI_PREVIEW; outline only."]
            result["entities"] = [
                {
                    "kind": "rectangle",
                    "id": "outline_1",
                    "origin": {"x": 0.0, "y": 0.0},
                    "placement_evidence": "Proposed origin at WCS (0, 0), pending human review",
                    "layer": "AI_PREVIEW",
                    "width": {
                        "value_mm": float(match[1]),
                        "source": "user",
                        "evidence": request.text,
                    },
                    "height": {
                        "value_mm": float(match[2]),
                        "source": "user",
                        "evidence": request.text,
                    },
                }
            ]
        return DrawingProposal.model_validate(result)


class ExternalAgent:
    def __init__(self, spec: AgentSpec, cwd: Path):
        self.spec, self.cwd = spec, cwd

    def analyze(self, request: AnalysisInput) -> DrawingProposal:
        spec = self.spec
        payload = envelope(request)
        try:
            if spec.kind == "command":
                # Do not inherit the human approval token or unrelated API credentials.
                allowed = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE")
                env = {key: os.environ[key] for key in allowed if key in os.environ}
                env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
                if spec.api_key_env and spec.api_key_env in os.environ:
                    env[spec.api_key_env] = os.environ[spec.api_key_env]
                completed = subprocess.run(
                    spec.command,
                    input=json.dumps(payload, ensure_ascii=False),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    shell=False,
                    cwd=self.cwd,
                    env=env,
                    timeout=spec.timeout_seconds,
                    check=True,
                )
                raw = completed.stdout
            else:
                headers = {}
                if spec.api_key_env:
                    key = os.environ.get(spec.api_key_env)
                    if not key:
                        raise AgentFailure(f"Missing credential environment: {spec.api_key_env}")
                    headers["Authorization"] = f"Bearer {key}"
                with httpx.Client(timeout=spec.timeout_seconds, trust_env=False) as client:
                    response = client.post(spec.url, json=payload, headers=headers)
                    response.raise_for_status()
                    raw = response.text
            if len(raw.encode("utf-8")) > 1_000_000:
                raise AgentFailure("Agent response exceeds 1 MB")
            return DrawingProposal.model_validate_json(raw)
        except (subprocess.SubprocessError, OSError, httpx.HTTPError, ValidationError) as exc:
            # External output may contain credentials; do not reflect it in the API.
            raise AgentFailure(
                f"Agent failed or returned invalid contract: {type(exc).__name__}"
            ) from exc


class AgentRegistry:
    def __init__(self, path: Path):
        specs = [AgentSpec.model_validate(item) for item in json.loads(path.read_text("utf-8"))]
        if len({spec.id for spec in specs}) != len(specs):
            raise ValueError("Duplicate agent IDs")
        self.specs = {spec.id: spec for spec in specs}
        self.cwd = path.resolve().parent.parent
        for spec in specs:
            if spec.api_key_env == "AI_AUTOCAD_OPERATOR_TOKEN":
                raise ValueError("Operator credential must never be passed to an agent")
            if spec.kind == "command" and not spec.command:
                raise ValueError("Command agent requires an argv list")
            if spec.kind == "http":
                if not spec.url or httpx.URL(spec.url).scheme not in ("http", "https"):
                    raise ValueError("HTTP agent requires an http(s) endpoint")

    def analyze(self, agent_id: str, request: AnalysisInput) -> DrawingProposal:
        spec = self.specs.get(agent_id)
        if not spec:
            raise AgentFailure("Unknown agent ID")
        required = {"text", *(item.kind for item in request.attachments)}
        if not required.issubset(spec.modalities):
            raise AgentFailure("Agent does not support the requested input modalities")
        agent = DemoAgent() if spec.kind == "demo" else ExternalAgent(spec, self.cwd)
        try:
            return agent.analyze(request)
        except ValidationError as exc:
            raise AgentFailure("Agent returned an invalid drawing proposal") from exc
