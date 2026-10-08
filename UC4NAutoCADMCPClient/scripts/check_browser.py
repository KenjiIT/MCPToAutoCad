"""Exercise HTTP connection, file upload and a read-only tool with Edge."""

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
    page.goto("http://127.0.0.1:8767")
    page.locator("#token").fill((root / "data/operator-token.txt").read_text().strip())
    page.locator("#connect").click()
    page.wait_for_function(
        "document.querySelector('#badge').textContent.includes('tools')", timeout=90000
    )
    assert page.locator("#endpoint").input_value() == "http://127.0.0.1:8768/mcp"
    page.locator("#file").set_input_files(
        {
            "name": "requirements.txt",
            "mimeType": "text/plain",
            "buffer": b"Read drawing name. Do not modify the drawing.",
        }
    )
    page.wait_for_function(
        "document.querySelector('#fileInfo').textContent.includes('requirements.txt')"
    )
    assert page.locator("#prompt").input_value() == ""
    page.locator("#toolSelect").select_option("system_status")
    page.locator("#manual").click()
    page.wait_for_function(
        "document.querySelector('#proposal').textContent.includes('system_status')"
    )
    assert page.locator("#execute").is_disabled()
    page.locator("#confirmed").check()
    page.locator("#execute").click()
    page.wait_for_function(
        "document.querySelector('#result').textContent.includes('connected')", timeout=90000
    )
    assert '"ok": true' in page.locator("#result").inner_text()
    assert page.locator("#execute").is_disabled()
    page.locator("#token").fill("")
    page.screenshot(path=str(root / "data/client-preview.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert not errors, errors
    browser.close()
    print("Edge UI check passed: HTTP connect, upload, approval, real read tool, mobile layout.")
