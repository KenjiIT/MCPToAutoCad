# AI AutoCAD working rules

- Read README.md and docs/ARCHITECTURE.md before changing behavior.
- Keep analysis agents replaceable through the versioned JSON contract. Vendor SDKs belong in adapters, never workflow.py.
- Agent output is a proposal, not permission. Never expose the operator token or direct CAD write tools to analysis providers.
- Every material proposal change invalidates human approval. Bind approval to revision, content digest, target document and adapter.
- Never turn inferred dimensions into measured facts. Preserve provenance and unresolved questions through review and execution.
- Default to simulation. AutoCAD's installed Autodesk MCP bundle does not prove external write support. Follow docs/ADAPT-CHECKLIST.md before implementing/enabling real CAD writes.
- Do not modify a real drawing to test the base. Use simulation or a user-confirmed test drawing and proposal.
- After changing contracts, regenerate contracts/*.schema.json and update conformance tests.
- Required checks: `.venv/Scripts/python.exe -m pytest -q` and `.venv/Scripts/python.exe -m ruff check .`.
- This base has no sandbox for untrusted agent programs and no multi-user authentication. Do not describe its operator token as proof of a human identity.
