import json
from pathlib import Path

from ai_autocad.models import AnalysisInput, DrawingProposal

root = Path(__file__).resolve().parents[1] / "contracts"
root.mkdir(exist_ok=True)
for name, model in (("analysis-input.v1", AnalysisInput), ("drawing-proposal.v1", DrawingProposal)):
    (root / f"{name}.schema.json").write_text(
        json.dumps(model.model_json_schema(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
print("Exported versioned analysis input and proposal JSON schemas")
