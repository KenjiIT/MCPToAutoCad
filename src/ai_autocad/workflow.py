import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .agents import AgentRegistry
from .cad import CadAdapter, compile_geometry
from .models import ApprovalRequest, CreateRequest, DrawingProposal, ExecuteRequest, RevisionRequest


class Conflict(Exception):
    pass


def digest_for(proposal: DrawingProposal, target: str, adapter: str) -> str:
    data = {"proposal": proposal.model_dump(), "target_document": target, "cad_adapter": adapter}
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class Workflow:
    def __init__(
        self,
        path: Path,
        agents: AgentRegistry,
        cad: CadAdapter,
        approval_ttl: int = 900,
    ):
        self.path, self.agents, self.cad, self.approval_ttl = path, agents, cad, approval_ttl
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, body TEXT NOT NULL)"
            )
            conn.execute("""CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
                at REAL NOT NULL, kind TEXT NOT NULL, details TEXT NOT NULL
            )""")

    @contextmanager
    def transaction(self):
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _read(self, conn, job_id):
        row = conn.execute("SELECT body FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            raise KeyError(job_id)
        return json.loads(row[0])

    def _save(self, conn, job, kind, details):
        conn.execute("INSERT OR REPLACE INTO jobs VALUES (?, ?)", (job["id"], json.dumps(job)))
        conn.execute(
            "INSERT INTO events (job_id, at, kind, details) VALUES (?, ?, ?, ?)",
            (job["id"], time.time(), kind, json.dumps(details)),
        )

    def get(self, job_id):
        with self.transaction() as conn:
            return self._read(conn, job_id)

    def events(self, job_id):
        with self.transaction() as conn:
            self._read(conn, job_id)
            rows = conn.execute(
                "SELECT seq, at, kind, details FROM events WHERE job_id = ? ORDER BY seq", (job_id,)
            ).fetchall()
        return [{"seq": s, "at": t, "kind": k, "details": json.loads(d)} for s, t, k, d in rows]

    def create(self, request: CreateRequest):
        proposal = self.agents.analyze(request.agent_id, request.input)
        job = {
            "id": str(uuid.uuid4()),
            "revision": 1,
            "status": "draft",
            "agent_id": request.agent_id,
            "input": request.input.model_dump(),
            "target_document": request.target_document,
            "cad_adapter": self.cad.name,
            "proposal": proposal.model_dump(),
            "review_items": proposal.review_items(),
            "digest": digest_for(proposal, request.target_document, self.cad.name),
            "approval": None,
            "result": None,
        }
        with self.transaction() as conn:
            self._save(conn, job, "proposed", {"revision": 1, "proposal": job["proposal"]})
        return job

    def revise(self, job_id: str, request: RevisionRequest):
        with self.transaction() as conn:
            job = self._read(conn, job_id)
            if job["status"] not in ("draft", "approved"):
                raise Conflict("Cannot revise an executing or finished job; create a new request")
            if request.expected_revision != job["revision"]:
                raise Conflict("Stale revision")
            job.update(
                revision=job["revision"] + 1,
                status="draft",
                approval=None,
                proposal=request.proposal.model_dump(),
                review_items=request.proposal.review_items(),
                digest=digest_for(request.proposal, job["target_document"], job["cad_adapter"]),
            )
            self._save(
                conn,
                job,
                "revised",
                {
                    "revision": job["revision"],
                    "proposal": job["proposal"],
                },
            )
        return job

    @staticmethod
    def _check_version(job, request):
        if job["revision"] != request.revision or job["digest"] != request.digest:
            raise Conflict("Proposal changed; review and confirm the current version")
        proposal = DrawingProposal.model_validate(job["proposal"])
        if job["digest"] != digest_for(proposal, job["target_document"], job["cad_adapter"]):
            raise Conflict("Stored proposal integrity check failed")
        return proposal

    def approve(self, job_id: str, request: ApprovalRequest):
        with self.transaction() as conn:
            job = self._read(conn, job_id)
            proposal = self._check_version(job, request)
            if job["status"] != "draft":
                raise Conflict("Only a draft may be approved")
            if proposal.unresolved_questions or not proposal.entities:
                raise Conflict("Resolve missing information before approval")
            if request.accepted_review_items != proposal.review_items():
                raise Conflict(
                    "Explicitly accept every review item, including estimated dimensions"
                )
            job["status"] = "approved"
            job["approval"] = {
                "revision": job["revision"],
                "digest": job["digest"],
                "expires_at": time.time() + self.approval_ttl,
                "accepted_review_items": request.accepted_review_items,
                "actor": "operator",
            }
            self._save(conn, job, "approved", job["approval"])
        return job

    def execute(self, job_id: str, request: ExecuteRequest):
        with self.transaction() as conn:
            job = self._read(conn, job_id)
            proposal = self._check_version(job, request)
            if job["status"] == "completed":
                return job  # Repeated click returns the existing result; never draws twice.
            if job["status"] != "approved" or not job["approval"]:
                raise Conflict("Human approval is required before execution")
            approval = job["approval"]
            if approval["expires_at"] <= time.time():
                raise Conflict("Approval expired; revise/review and confirm again")
            if approval["digest"] != job["digest"] or approval["revision"] != job["revision"]:
                raise Conflict("Approval does not match this proposal")
            if self.cad.name != job["cad_adapter"]:
                raise Conflict("CAD adapter changed; create and review a new request")
            self.cad.check_ready(job["target_document"])
            job["status"] = "executing"
            job["execution_id"] = str(uuid.uuid4())
            self._save(conn, job, "execution_started", {"execution_id": job["execution_id"]})
        # Persist the claim BEFORE CAD side effects. Crashes remain 'executing'; no blind retries.
        expected = compile_geometry(proposal)
        try:
            actual = self.cad.execute(job["execution_id"], job["target_document"], expected)
            if actual != expected:
                raise Conflict("Read-back geometry differs from the approved proposal")
            job["status"] = "completed"
            job["result"] = {
                "mode": self.cad.name,
                "verified_readback": True,
                "entities": actual,
                "execution_id": job["execution_id"],
            }
        except Exception as exc:
            # A transport failure may occur AFTER drawing; never retry automatically.
            job["status"] = "needs_reconciliation"
            job["result"] = {"error_type": type(exc).__name__, "verified_readback": False}
        with self.transaction() as conn:
            self._save(conn, job, job["status"], job["result"])
        return job
