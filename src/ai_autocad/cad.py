"""Only this boundary may translate approved geometry into a CAD transport."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Protocol

from .models import DrawingProposal


class CadUnavailable(Exception):
    pass


def compile_geometry(proposal: DrawingProposal) -> list[dict]:
    result = []
    for entity in proposal.entities:
        x, y = entity.origin.x, entity.origin.y
        w, h = entity.width.value_mm, entity.height.value_mm
        result.append(
            {
                "id": entity.id,
                "layer": entity.layer,
                "closed": True,
                "vertices_mm": [[x, y], [x + w, y], [x + w, y + h], [x, y + h]],
            }
        )
    return result


class CadAdapter(Protocol):
    name: str

    def check_ready(self, target: str) -> None: ...

    def execute(self, execution_id: str, target: str, geometry: list[dict]) -> list[dict]: ...


class SimulationCad:
    """Persists and reads back virtual entities; never connects to AutoCAD or writes DWG."""

    name = "simulation"

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as conn, conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS executions (
                id TEXT PRIMARY KEY, target TEXT NOT NULL, geometry TEXT NOT NULL
            )""")

    def check_ready(self, target: str) -> None:
        if not target.startswith("simulation:"):
            raise CadUnavailable("Simulation target must start with simulation:")

    def execute(self, execution_id: str, target: str, geometry: list[dict]) -> list[dict]:
        self.check_ready(target)
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute(
                "INSERT INTO executions VALUES (?, ?, ?)",
                (execution_id, target, json.dumps(geometry, allow_nan=False)),
            )
        with closing(sqlite3.connect(self.path)) as conn:
            row = conn.execute(
                "SELECT geometry FROM executions WHERE id = ?", (execution_id,)
            ).fetchone()
        return json.loads(row[0])


class UnverifiedAutocad:
    name = "autocad"

    def check_ready(self, target: str) -> None:
        raise CadUnavailable(
            "Real AutoCAD writes are disabled: external write transport has not passed conformance"
        )

    def execute(self, execution_id: str, target: str, geometry: list[dict]) -> list[dict]:
        self.check_ready(target)
        raise CadUnavailable("No verified AutoCAD write adapter")


def load_cad(config: Path, data_dir: Path) -> CadAdapter:
    settings = json.loads(config.read_text("utf-8"))
    if settings["adapter"] == "simulation":
        return SimulationCad(data_dir / "simulation.sqlite3")
    if settings["adapter"] == "autocad":
        # A config flag alone can never enable an unimplemented write path.
        return UnverifiedAutocad()
    raise ValueError("Unknown CAD adapter")
