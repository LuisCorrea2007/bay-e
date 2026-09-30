"""Cross-platform BAY-E launcher (no Docker)."""
from __future__ import annotations

import os
import threading
import time
import webbrowser

import uvicorn
from dotenv import load_dotenv

load_dotenv()


def _open() -> None:
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:8300")


if __name__ == "__main__":
    threading.Thread(target=_open, daemon=True).start()
    uvicorn.run("main:app", host="127.0.0.1", port=int(os.getenv("BAYE_PORT", "8300")), reload=False)