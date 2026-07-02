"""
Screenshots just the countdown section of docs/index.html so it can be
attached as a photo to the daily Telegram message.

Runs headless in CI right before send_countdown.py, so the numbers in the
image are always current for that day.
"""

import pathlib
from playwright.sync_api import sync_playwright

HTML_PATH = pathlib.Path(__file__).parent / "docs" / "index.html"
OUT_PATH = pathlib.Path(__file__).parent / "countdown.png"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 700, "height": 520})
        page.goto(f"file://{HTML_PATH.resolve()}")
        # let the countdown JS run at least one tick before capturing
        page.wait_for_timeout(600)
        page.locator("#countdown-section").screenshot(path=str(OUT_PATH))
        browser.close()
    print(f"Saved {OUT_PATH}")


if __name__ == "__main__":
    main()
