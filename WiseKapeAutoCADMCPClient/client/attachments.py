"""Extract file context without executing uploaded content or changing CAD."""

import io
import json
import re
import uuid
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pymupdf
from openpyxl import load_workbook
from PIL import Image

from .bridge import ROOT

UPLOAD_ROOT = ROOT / "data" / "drawings" / "imports"
MAX_BYTES = 20 * 1024 * 1024
MAX_TEXT = 200_000
EXTENSIONS = {
    ".txt",
    ".md",
    ".json",
    ".csv",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".docx",
    ".xlsx",
}


def validate_archive(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if sum(item.file_size for item in archive.infolist()) > 50 * 1024 * 1024:
            raise ValueError("Tài liệu giải nén vượt 50 MB; hãy chia file nhỏ hơn.")


def load_attachment(attachment_id):
    if not re.fullmatch(r"[a-f0-9]{32}", attachment_id):
        raise ValueError("Mã file không hợp lệ.")
    folder = UPLOAD_ROOT / attachment_id
    metadata = json.loads((folder / "attachment.json").read_text(encoding="utf-8"))
    # All executable paths are reconstructed locally, never taken from metadata or user paths.
    metadata["path"] = str(folder / ("source" + metadata["extension"]))
    metadata["images"] = [str(folder / name) for name in metadata["image_files"]]
    return metadata


def ingest(filename, data):
    name = filename.replace("\\", "/").rsplit("/", 1)[-1][:200]
    extension = Path(name).suffix.lower()
    if extension not in EXTENSIONS:
        raise ValueError("Hỗ trợ TXT, MD, JSON, CSV, DOCX, XLSX, PDF, PNG, JPG và WEBP.")
    if not data or len(data) > MAX_BYTES:
        raise ValueError("File phải có nội dung và không vượt quá 20 MB.")
    attachment_id = uuid.uuid4().hex
    folder = UPLOAD_ROOT / attachment_id
    folder.mkdir(parents=True)
    source = folder / ("source" + extension)
    source.write_bytes(data)
    metadata = {
        "id": attachment_id,
        "name": name,
        "extension": extension,
        "size": len(data),
        "image_files": [],
        "text": "",
        "kind": "text",
    }
    try:
        if extension in {".txt", ".md", ".csv", ".json"}:
            text = data.decode("utf-8-sig")
            if not text.strip() or "\x00" in text:
                raise ValueError("File văn bản rỗng hoặc không phải UTF-8.")
            if len(text) > MAX_TEXT:
                raise ValueError("Văn bản vượt 200.000 ký tự; hãy chia file nhỏ hơn.")
            if extension == ".json":
                json.loads(text)
            metadata["text"] = text
            metadata["summary"] = f"Đã đọc toàn bộ {len(text):,} ký tự UTF-8."
        elif extension in {".png", ".jpg", ".jpeg", ".webp"}:
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                width, height = image.size
                if width * height > 20_000_000:
                    raise ValueError("Ảnh vượt 20 megapixel; hãy dùng ảnh nhỏ hơn.")
                if getattr(image, "n_frames", 1) != 1:
                    raise ValueError("Chỉ hỗ trợ ảnh tĩnh một frame.")
                if image.format not in {"PNG", "JPEG", "WEBP"}:
                    raise ValueError("Nội dung không phải PNG, JPEG hoặc WEBP.")
            metadata.update(
                kind="image",
                image_files=[source.name],
                summary=f"Ảnh {width} × {height}; sẽ gửi hình ảnh cho AI khi lập phương án.",
            )
        elif extension == ".pdf":
            with pymupdf.open(stream=data, filetype="pdf") as doc:
                if doc.needs_pass:
                    raise ValueError("PDF có mật khẩu; hãy nhập bản PDF đã mở khóa.")
                if not 1 <= len(doc) <= 12:
                    raise ValueError("PDF cần từ 1 đến 12 trang; hãy tách tài liệu dài hơn.")
                text = ""
                for index, page in enumerate(doc):
                    text += f"\n--- Trang {index + 1} ---\n" + page.get_text()
                    if len(text) > MAX_TEXT:
                        raise ValueError("Nội dung PDF vượt 200.000 ký tự; hãy chia file.")
                    extent = max(page.rect.width, page.rect.height)
                    if extent <= 0:
                        raise ValueError("PDF có kích thước trang không hợp lệ.")
                    scale = min(2, 2000 / extent)
                    filename = f"page-{index + 1}.png"
                    page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).save(
                        folder / filename
                    )
                    metadata["image_files"].append(filename)
                metadata.update(
                    kind="pdf",
                    text=text,
                    pages=len(doc),
                    summary=f"Đã đọc {len(doc)} trang; gửi cả chữ và ảnh trang cho AI.",
                )
        elif extension == ".docx":
            validate_archive(data)
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                xml = ET.fromstring(archive.read("word/document.xml"))
            ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            paragraphs = [
                "".join(node.text or "" for node in paragraph.iter(ns + "t"))
                for paragraph in xml.iter(ns + "p")
            ]
            metadata["text"] = "\n".join(paragraphs)
            metadata["summary"] = "Đã đọc chữ và ô bảng trong nội dung chính của Word. "
            metadata["summary"] += "Ảnh, header/footer và đối tượng nhúng chưa được đọc."
        elif extension == ".xlsx":
            validate_archive(data)
            workbook = load_workbook(source, read_only=True, data_only=False, keep_links=False)
            sheets = []
            count = 0
            try:
                for sheet in workbook:
                    rows = []
                    if sheet.max_row > 10_000 or sheet.max_column > 100:
                        raise ValueError("Excel vượt 10.000 hàng hoặc 100 cột mỗi sheet.")
                    for row in sheet.iter_rows(values_only=True):
                        if not any(value is not None for value in row):
                            continue
                        count += len(row)
                        if count > 50_000:
                            raise ValueError("Excel vượt 50.000 ô; hãy chia file nhỏ hơn.")
                        rows.append([str(value) if value is not None else "" for value in row])
                    sheets.append({"sheet": sheet.title, "rows": rows})
            finally:
                workbook.close()
            metadata["text"] = json.dumps(sheets, ensure_ascii=False)
            metadata["summary"] = (
                f"Đã đọc {len(sheets)} sheet, {count} ô. "
                "Công thức giữ dạng chữ; ảnh/biểu đồ chưa được đọc."
            )
        if len(metadata["text"]) > MAX_TEXT:
            raise ValueError("Nội dung vượt 200.000 ký tự; hãy chia file nhỏ hơn.")
        if extension in {".docx", ".xlsx"} and not metadata["text"].strip():
            raise ValueError("Tài liệu không có nội dung văn bản đọc được.")
        (folder / "attachment.json").write_text(
            json.dumps(metadata, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        # Only these newly created files are removed if extraction fails.
        for item in folder.iterdir():
            item.unlink()
        folder.rmdir()
        raise
    return load_attachment(attachment_id)


def public_attachment(metadata):
    return {key: metadata[key] for key in ("id", "name", "kind", "size", "summary")} | {
        "preview": metadata["text"][:4000],
        "pages": metadata.get("pages"),
    }
