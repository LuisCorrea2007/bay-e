from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("redesign-shots")
OUT.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
    page.on("pageerror", lambda exc: print("PAGEERROR:", exc))
    page.on("console", lambda msg: print("CONSOLE:", msg.type, msg.text))
    page.goto("http://127.0.0.1:8300", wait_until="networkidle")
    print("READY:", page.evaluate("document.readyState"))
    print("BODY VIEW:", page.get_attribute("body", "data-view"))
    print("APP TYPE:", page.evaluate("typeof App"))
    print("VIEWS TYPE:", page.evaluate("typeof Views"))
    page.wait_for_timeout(2200)
    page.screenshot(path=str(OUT / "01-chat-first.png"), full_page=True)

    # Verify conversational system action.
    page.fill("#chat-input", "estado del sistema")
    page.click("#chat-send")
    page.wait_for_timeout(4200)
    page.screenshot(path=str(OUT / "02-chat-estado.png"), full_page=True)

    # Verify deterministic memory through chat.
    page.fill("#chat-input", "recuerda que mi taza favorita es negra")
    page.click("#chat-send")
    page.wait_for_timeout(3800)
    page.fill("#chat-input", "qué recuerdas de mi taza favorita?")
    page.click("#chat-send")
    page.wait_for_timeout(3800)
    page.screenshot(path=str(OUT / "03-chat-memoria.png"), full_page=True)

    # Verify chat-driven navigation and emotional UI.
    page.fill("#chat-input", "qué sientes?")
    page.click("#chat-send")
    page.wait_for_timeout(3500)
    page.screenshot(path=str(OUT / "04-corazon-desde-chat.png"), full_page=True)

    # Return to chat and verify health command.
    page.click('[data-nav="chat"]')
    page.wait_for_timeout(500)
    page.fill("#chat-input", "registra mi pulso 72")
    page.click("#chat-send")
    page.wait_for_timeout(3500)
    page.screenshot(path=str(OUT / "05-salud-desde-chat.png"), full_page=True)

    browser.close()