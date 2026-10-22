import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def browser_page(tmp_path_factory):
    from playwright.sync_api import sync_playwright

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {**os.environ, "SKILLPATH_CACHE_DIR": str(tmp_path_factory.mktemp("browser-cache"))}
    root = Path(__file__).resolve().parents[1]
    env["PYTHONPATH"] = str(root)
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "browser_app:app", "--app-dir", "tests", "--port", str(port)],
        cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(300):
            if process.poll() is not None:
                pytest.fail(process.stderr.read().decode())
            try:
                urllib.request.urlopen(url, timeout=1).close()
                break
            except urllib.error.URLError:
                time.sleep(0.1)
        else:
            pytest.fail("Browser fixture server did not start")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=os.environ.get("SKILLPATH_BROWSER_EXECUTABLE"))
            page = browser.new_page()
            yield page, url
            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_extraction_filter_errors_theme_and_refresh(browser_page):
    from playwright.sync_api import expect

    page, url = browser_page
    page.goto(url)
    page.get_by_label("Job description").fill("Python experience required.")
    page.get_by_role("button", name="Extract skills").click()
    expect(page.locator("#results")).to_contain_text("Python")
    page.get_by_text("Matched context").click()
    expect(page.locator("#results")).to_contain_text("required:")
    page.get_by_role("button", name="Switch to dark theme").click()
    page.reload()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    page.goto(url + "/market")
    expect(page.locator("#corpus-summary")).to_contain_text("4 postings")
    page.get_by_role("button", name="2 companies", exact=True).click()
    expect(page.get_by_role("dialog")).to_contain_text("Acme · 2 postings")
    page.get_by_role("button", name="Close details").click()
    page.get_by_role("button", name="Python", exact=True).click()
    expect(page.get_by_role("dialog")).to_contain_text("2 of 4 postings")
    page.get_by_role("dialog").get_by_text("Acme · 1 postings", exact=True).click()
    expect(page.get_by_role("dialog")).to_contain_text("Data Engineer")
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog")).not_to_be_visible()
    page.get_by_label("Job title contains").fill("analyst")
    page.get_by_role("button", name="Analyze", exact=True).click()
    expect(page.locator("#corpus-summary")).to_contain_text("1 postings")
    page.get_by_label("Advanced regex").check()
    page.get_by_label("Job title contains").fill("[")
    page.get_by_role("button", name="Analyze", exact=True).click()
    expect(page.locator("#results")).to_contain_text("Bad title filter")
    page.get_by_label("Job title contains").fill("engineer")
    page.get_by_role("button", name="Refresh now").click()
    expect(page.locator("#refresh-status")).to_contain_text("Refreshing")
    expect(page.locator("#refresh-button")).to_be_enabled(timeout=20000)
    expect(page.locator("#corpus-summary")).to_contain_text("2 postings")
