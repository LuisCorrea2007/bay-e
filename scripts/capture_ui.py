from pathlib import Path
from playwright.sync_api import sync_playwright
import time

OUT = Path("screenshots")
OUT.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
    page.goto("http://127.0.0.1:8300", wait_until="networkidle")
    page.wait_for_timeout(2500)
    page.screenshot(path=str(OUT / "01-dashboard.png"), full_page=True)

    # Chat: exercise the real REST/WebSocket-backed UI. With no local LLM in CI,
    # BAY-E truthfully falls back to its deterministic provider.
    page.click('[data-nav="chat"]')
    page.wait_for_timeout(500)
    page.fill("#chat-input", "Hola BAY-E, recuerda que mi objeto de prueba está en el escritorio.")
    page.click("#chat-send")
    page.wait_for_timeout(4500)
    page.screenshot(path=str(OUT / "02-chat-funcionando.png"), full_page=True)

    # Memory view: verify the explicit memory command persisted.
    page.fill("#chat-input", "recuerda que las llaves de prueba están en el escritorio")
    page.click("#chat-send")
    page.wait_for_timeout(3200)
    page.click('[data-nav="memory"]')
    page.wait_for_timeout(1800)
    page.fill("#mem-q", "llaves de prueba")
    page.wait_for_timeout(1000)
    page.screenshot(path=str(OUT / "03-memoria-persistente.png"), full_page=True)

    # Heart/emotions.
    page.click('[data-nav="heart"]')
    page.wait_for_timeout(1000)
    page.screenshot(path=str(OUT / "04-corazon-emociones.png"), full_page=True)

    # Vision screen: real software state, without inventing a camera in CI.
    page.click('[data-nav="vision"]')
    page.wait_for_timeout(1000)
    page.screenshot(path=str(OUT / "05-vision-sin-hardware.png"), full_page=True)

    # Health view.
    page.click('[data-nav="health"]')
    page.wait_for_timeout(700)
    page.fill("#health-value", "72")
    page.click("#health-save")
    page.wait_for_timeout(1000)
    page.screenshot(path=str(OUT / "06-salud-medicion.png"), full_page=True)

    browser.close()
