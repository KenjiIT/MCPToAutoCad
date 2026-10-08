"""Verify file upload -> real Codex plan -> read-only MCP call in Edge."""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
with sync_playwright() as pw:
    browser = pw.chromium.launch(
        executable_path="C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
        headless=True,
    )
    page = browser.new_page(viewport={"width": 1360, "height": 950})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://127.0.0.1:8771")
    page.locator("#token").fill((root / "data/operator-token.txt").read_text().strip())
    page.locator("#connect").click()
    page.wait_for_function(
        "document.querySelector('#badge').textContent.includes('tools')", timeout=90000
    )
    page.locator("#file").set_input_files(
        {
            "name": "requirements.txt",
            "mimeType": "text/plain",
            "buffer": (
                "Yêu cầu: chỉ đọc tên bản vẽ hiện tại bằng drawing_info. "
                "Không thay đổi hoặc lưu bản vẽ."
            ).encode("utf-8"),
        }
    )
    page.wait_for_function("document.querySelector('#plan').textContent.includes('từ file')")
    assert page.locator("#prompt").input_value() == ""
    assert "requirements.txt" in page.locator("#fileInfo").inner_text()
    page.locator("#plan").click()
    page.wait_for_function(
        "document.querySelector('#proposal').textContent.includes('source_file')", timeout=180000
    )
    proposal = json.loads(page.locator("#proposal").inner_text())
    assert all(step["tool"] == "drawing_info" for step in proposal["steps"])
    assert page.locator("#execute").is_disabled()
    page.locator("#confirmed").check()
    page.locator("#execute").click()
    page.wait_for_function(
        "document.querySelector('#result').textContent.includes('entity_count')", timeout=90000
    )
    assert json.loads(page.locator("#result").inner_text())["ok"]
    page.locator("#fileDetails").evaluate("node => node.open = true")
    page.locator("#token").fill("")
    page.screenshot(path=str(root / "data/file-input-preview.png"), full_page=True)
    page.locator("#clearFile").click()
    assert page.locator("#file").input_value() == ""
    assert page.locator("#execute").is_disabled()
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert not errors, errors
    browser.close()
    print("File-only browser and real Codex/MCP check passed.")
