"""
BAY-E · Aplicación FastAPI (punto de entrada).

    uvicorn main:app --reload            # desarrollo
    uvicorn main:app --host 0.0.0.0 --port 8000

Estructura:
  * Jinja2 -> templates/index.html (SPA ligera, sin React)
  * /ws    -> tiempo real (estado vivo, chat, detecciones)
  * /api/* -> REST modular (memoria, tareas, ajustes, logs…)
  * life_loop -> corazón de simulación; sustituible por ROS 2 / hardware.
"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from jinja2 import Environment, FileSystemLoader

from app.api.routes import router as api_router
from app.core import db
from app.core.brain import BAYE
from app.core.config import APP_NAME, APP_VERSION, ROOT_DIR
from app.core.ws import life_loop, ws_handler

# ------------------------------------------------------------------ arranque
@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()                 # esquema + semilla primera vez (seed() interno)
    BAYE.boot()                  # despierta al ser
    task = asyncio.create_task(life_loop())   # corazón latiendo
    yield
    task.cancel()


app = FastAPI(title=f"{APP_NAME} · Compañero Robótico", version=APP_VERSION, lifespan=lifespan)

# Clientes móviles Capacitor usan un origen local propio. El Core continúa siendo
# local; no se habilita CORS universal.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "https://localhost",
        "capacitor://localhost",
        "ionic://localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------ estáticos
app.mount("/static", StaticFiles(directory=ROOT_DIR / "static"), name="static")
app.include_router(api_router)

# ------------------------------------------------------------------ plantillas
jinja = Environment(loader=FileSystemLoader(ROOT_DIR / "templates"), autoescape=True)


@app.get("/", response_class=HTMLResponse)
def index():
    """Interfaz completa de BAY-E (SPA con vistas conmutables)."""
    tpl = jinja.get_template("index.html")
    return tpl.render(version=APP_VERSION, name=APP_NAME)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_handler(websocket)


@app.get("/health")
def health():
    return {"ok": True, "name": APP_NAME, "version": APP_VERSION, "alive": BAYE.s["alive"]}