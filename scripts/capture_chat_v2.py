from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("screenshots-v2")
OUT.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
    page.goto("http://127.0.0.1:8300", wait_until="networkidle")
    page.wait_for_timeout(2200)
    page.screenshot(path=str(OUT / "01-chat-home.png"), full_page=True)

    # Real deterministic command through chat.
    page.fill("#chat-input", "¿Cómo te sientes?")
    page.click("#chat-send")
    page.wait_for_timeout(3500)
    # command intentionally navigates to heart; return to chat to show transcript
    page.click('[data-nav="chat"]')
    page.wait_for_timeout(600)
    page.screenshot(path=str(OUT / "02-chat-command.png"), full_page=True)

    page.fill("#chat-input", "recuerda que mis llaves de prueba están en el escritorio")
    page.click("#chat-send")
    page.wait_for_timeout(3200)
    page.fill("#chat-input", "abre memoria")
    page.click("#chat-send")
    page.wait_for_timeout(1800)
    page.fill("#mem-q", "llaves de prueba")
    page.wait_for_timeout(900)
    page.screenshot(path=str(OUT / "03-chat-opens-memory.png"), full_page=True)

    page.click('[data-nav="chat"]')
    page.wait_for_timeout(500)
    page.fill("#chat-input", "explora la casa")
    page.click("#chat-send")
    page.wait_for_timeout(3200)
    page.click('[data-nav="chat"]')
    page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / "04-safety-from-chat.png"), full_page=True)

    browser.close()
