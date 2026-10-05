from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


Text = Annotated[str, Field(min_length=1, max_length=2000)]
Coordinate = Annotated[float, Field(ge=-1_000_000, le=1_000_000)]


class Measurement(Contract):
    value_mm: float = Field(gt=0, le=1_000_000)
    source: Literal["user", "image_annotation", "inferred", "proposed"]
    evidence: Text


class Point(Contract):
    x: Coordinate
    y: Coordinate


class Rectangle(Contract):
    kind: Literal["rectangle"]
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    origin: Point
    placement_evidence: Text
    width: Measurement
    height: Measurement
    layer: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")


class DrawingProposal(Contract):
    schema_version: Literal["1.0"]
    summary: Text
    units: Literal["mm"]
    coordinate_system: Literal["WCS"]
    geometry_meaning: Text
    entities: list[Rectangle] = Field(max_length=100)
    assumptions: list[Text] = Field(max_length=50)
    unresolved_questions: list[Text] = Field(max_length=50)

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [entity.id for entity in self.entities]
        if len(ids) != len(set(ids)):
            raise ValueError("Entity IDs must be unique")
        if not self.entities and not self.unresolved_questions:
            raise ValueError("An empty proposal must explain what information is missing")
        return self

    def review_items(self) -> list[str]:
        items = list(self.assumptions)
        for entity in self.entities:
            for field in ("width", "height"):
                measurement = getattr(entity, field)
                if measurement.source in ("inferred", "proposed"):
                    items.append(
                        f"{entity.id}.{field}: {measurement.value_mm:g} mm "
                        f"({measurement.source}); {measurement.evidence}"
                    )
        return items


class Attachment(Contract):
    """Opaque reference owned by the caller; the core never fetches arbitrary files/URLs."""

    kind: Literal["image", "audio"]
    reference: Text
    description: Text


class AnalysisInput(Contract):
    text: str = Field(min_length=1, max_length=20000)
    attachments: list[Attachment] = Field(default_factory=list, max_length=10)


class CreateRequest(Contract):
    agent_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    target_document: str = Field(min_length=1, max_length=260)
    input: AnalysisInput


class RevisionRequest(Contract):
    expected_revision: int = Field(ge=1)
    proposal: DrawingProposal


class ApprovalRequest(Contract):
    revision: int = Field(ge=1)
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    accepted_review_items: list[str]


class ExecuteRequest(Contract):
    revision: int = Field(ge=1)
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
