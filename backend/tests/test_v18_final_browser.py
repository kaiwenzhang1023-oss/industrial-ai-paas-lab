"""Optional real Chromium smoke, separate from static Workbench contract."""
from pathlib import Path
import pytest

def test_workbench_real_browser_render():
    playwright = pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright
    page_path = Path(__file__).resolve().parents[1] / "app" / "web" / "v17.html"
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as exc:
            pytest.fail(f"CHROMIUM_NOT_INSTALLED_OR_UNAVAILABLE: {exc}")
        try:
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda err: errors.append(str(err)))
            response = page.goto(page_path.as_uri(), wait_until="domcontentloaded")
            assert page.locator("body").count() == 1
            assert len(page.locator("body").inner_text().strip()) > 20
            assert not errors, f"Browser JS errors: {errors}"
        finally:
            browser.close()
