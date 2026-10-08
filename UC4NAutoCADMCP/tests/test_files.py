import io
import json
import zipfile

import pymupdf
import pytest
from client import api, attachments
from client.planner import Proposal, Step
from fastapi.testclient import TestClient
from openpyxl import Workbook
from PIL import Image


@pytest.fixture(autouse=True)
def isolated_uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(attachments, "UPLOAD_ROOT", tmp_path / "imports")


def test_word_excel_and_pdf_content():
    word = io.BytesIO()
    with zipfile.ZipFile(word, "w") as archive:
        archive.writestr(
            "word/document.xml",
            """<w:document
        xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
        <w:body><w:p><w:r><w:t>Vẽ đường tròn</w:t></w:r></w:p>
        <w:tbl><w:tr><w:tc><w:p><w:r><w:t>Bán kính 25 mm</w:t></w:r></w:p>
        </w:tc></w:tr></w:tbl></w:body></w:document>""",
        )
    metadata = attachments.ingest("requirements.docx", word.getvalue())
    assert "Vẽ đường tròn\nBán kính 25 mm" in metadata["text"]

    workbook = Workbook()
    workbook.active.title = "Yêu cầu"
    workbook.active.append(["Bán kính", 25, "mm"])
    workbook.active.append(["Công thức", "=2*25"])
    excel = io.BytesIO()
    workbook.save(excel)
    metadata = attachments.ingest("requirements.xlsx", excel.getvalue())
    sheets = json.loads(metadata["text"])
    assert sheets[0]["sheet"] == "Yêu cầu"
    assert sheets[0]["rows"][0] == ["Bán kính", "25", "mm"]
    assert sheets[0]["rows"][1][1] == "=2*25"

    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((40, 50), "Radius 25 mm")
        pdf.new_page()  # A scanned/visual page still becomes an AI image input.
        metadata = attachments.ingest("requirements.pdf", pdf.tobytes())
    assert metadata["pages"] == 2
    assert "Radius 25 mm" in metadata["text"]
    assert len(metadata["images"]) == 2
    assert all(Image.open(path).width > 0 for path in metadata["images"])


def test_invalid_files_and_limits():
    for name, data in [
        ("file.exe", b"bad"),
        ("bad.json", b"{"),
        ("bad.pdf", b"not a PDF"),
        ("bad.png", b"not an image"),
        ("empty.txt", b""),
        ("binary.txt", b"\x00hello"),
    ]:
        with pytest.raises(Exception):
            attachments.ingest(name, data)
    assert not list(attachments.UPLOAD_ROOT.glob("*/source.*"))
    with pymupdf.open() as pdf:
        for _ in range(13):
            pdf.new_page()
        with pytest.raises(ValueError, match="12"):
            attachments.ingest("long.pdf", pdf.tobytes())
    with pytest.raises(ValueError, match="200.000"):
        attachments.ingest("large.txt", b"a" * (attachments.MAX_TEXT + 1))
    with pytest.raises(ValueError):
        attachments.load_attachment("../../operator-token.txt")


def test_file_only_plan_and_image_forwarding(monkeypatch):
    headers = {"Authorization": "Bearer " + api.TOKEN}
    monkeypatch.setattr(api.bridge, "session", "file-session")
    monkeypatch.setattr(
        api.bridge,
        "catalog",
        {"drawing_info": {"name": "drawing_info", "inputSchema": {"type": "object"}}},
    )
    calls = []

    async def fake_request(action, **payload):
        if action == "catalog":
            return list(api.bridge.catalog.values())
        if action == "observe":
            return {}
        raise AssertionError(action)

    monkeypatch.setattr(api, "request", fake_request)

    def fake_plan(prompt, tools, model, images, **options):
        calls.append((prompt, images))
        return Proposal(
            summary="Đọc tên bản vẽ",
            unresolved_questions=[],
            steps=[
                Step(tool="drawing_info", arguments_json="{}", explanation="Đọc metadata")
                for _ in range(12)
            ],
        )

    monkeypatch.setattr(api, "plan", fake_plan)
    with TestClient(api.app) as web:
        assert web.post("/api/files", files={"file": ("a.txt", b"test")}).status_code == 401
        uploaded = web.post(
            "/api/files",
            headers=headers,
            files={"file": ("../../requirements.txt", "Đọc tên bản vẽ hiện tại".encode("utf-8"))},
        )
        assert uploaded.status_code == 200, uploaded.text
        file = uploaded.json()
        assert file["name"] == "requirements.txt"
        response = web.post(
            "/api/plan",
            headers=headers,
            json={"attachment_id": file["id"], "tool_names": ["drawing_info"]},
        )
        assert response.status_code == 200, response.text
        assert response.json()["source_file"] == "requirements.txt"
        assert len(response.json()["steps"]) == 12
        assert "Đọc tên bản vẽ hiện tại" in calls[0][0]
        assert calls[0][1] == []
        assert (
            web.post(
                "/api/plan", headers=headers, json={"tool_names": ["drawing_info"]}
            ).status_code
            == 422
        )
        image = io.BytesIO()
        Image.new("RGB", (30, 20), "white").save(image, format="PNG")
        uploaded = web.post(
            "/api/files", headers=headers, files={"file": ("reference.png", image.getvalue())}
        ).json()
        response = web.post(
            "/api/plan",
            headers=headers,
            json={"attachment_id": uploaded["id"], "tool_names": ["drawing_info"]},
        )
        assert response.status_code == 200
        assert len(calls[-1][1]) == 1
        monkeypatch.setattr(api, "MAX_BYTES", 10)
        assert (
            web.post(
                "/api/files", headers=headers, files={"file": ("large.txt", b"a" * 11)}
            ).status_code
            == 413
        )
