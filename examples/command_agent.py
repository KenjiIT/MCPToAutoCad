"""Executable contract example, NOT an AI model. Replace its analyzer with your own agent."""

import json
import sys

from ai_autocad.agents import DemoAgent
from ai_autocad.models import AnalysisInput

payload = json.load(sys.stdin)
if payload["protocol_version"] != "1.0":
    raise SystemExit("Unsupported analysis protocol")
request = AnalysisInput.model_validate(payload["input"])
proposal = DemoAgent().analyze(request)
print(proposal.model_dump_json())
