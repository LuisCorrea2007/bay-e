"""
BAY-E · Gestión de conexiones WebSocket y bucle vital en segundo plano.

Cada cliente conectado recibe su propia cola de eventos. El bucle `life_loop`:
  * ejecuta el heartbeat del cerebro (emociones, batería, autonomía),
  * simula detecciones de visión cuando el módulo está activo,
  * emite snapshots a todas las colas.

Cuando exista hardware real, basta con reemplazar `life_loop` por listeners
de ROS 2 / cámara / micrófono que llamen a BAYE.perceive_vision(), hear(), etc.
"""
import asyncio
import json
import random
import time
from typing import Optional

from fastapi import WebSocket

from .brain import BAYE
from .config import HEARTBEAT_INTERVAL
from . import db

# ----------------------------------------------------------------- clientes
CLIENTS: set[WebSocket] = set()
_QUEUES: dict[int, asyncio.Queue] = {}


def _emit(event: dict) -> None:
    """Difunde un evento a todos los clientes conectados."""
    for q in list(_QUEUES.values()):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass  # cliente lento: se le saltan eventos efímeros


def broadcast_state() -> None:
    _emit(BAYE.snapshot())


BAYE.broadcast = lambda snap: _emit(snap)  # gancho usado por brain.publish_now


async def ws_handler(websocket: WebSocket) -> None:
    """Ciclo de vida de una conexión WS: suscripción → pump → limpieza."""
    await websocket.accept()
    CLIENTS.add(websocket)
    q: asyncio.Queue = asyncio.Queue(maxsize=120)
    _QUEUES[id(websocket)] = q

    async def pump():
        while True:
            ev = await q.get()
            await websocket.send_text(json.dumps(ev, ensure_ascii=False))

    async def recv():
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            handle_client_msg(msg, _emit)

    try:
        # snapshot inicial inmediato para pintar la cara sin esperar
        await websocket.send_text(json.dumps(BAYE.snapshot(), ensure_ascii=False))
        await asyncio.gather(pump(), recv())
    except Exception:
        pass
    finally:
        _QUEUES.pop(id(websocket), None)
        CLIENTS.discard(websocket)


# ----------------------------------------------------------------- mensajes cliente
def handle_client_msg(msg: dict, emit) -> None:
    t = msg.get("type")
    if t == "command":
        ack = BAYE.command(msg.get("cmd"), msg.get("payload"))
        emit(ack)
        broadcast_state()
    elif t == "chat":
        text = (msg.get("text") or "").strip()
        if text:
            asyncio.create_task(BAYE.chat_turn(text, emit))
    elif t == "ping":
        emit({"type": "pong", "ts": time.time()})


# ----------------------------------------------------------------- visión simulada
DETECTIONS = [
    {"label": "Ana", "kind": "person", "confidence": 0.94},
    {"label": "Carlos", "kind": "person", "confidence": 0.81},
    {"label": "Mini (gato)", "kind": "animal", "confidence": 0.88},
    {"label": "taza", "kind": "object", "confidence": 0.76},
    {"label": "sofá", "kind": "object", "confidence": 0.95},
    {"label": "pelota roja", "kind": "object", "confidence": 0.58},
    {"label": "movimiento leve", "kind": "motion", "confidence": 0.42},
    {"label": "ventana abierta", "kind": "scene", "confidence": 0.67},
    {"label": "desconocido", "kind": "object", "confidence": 0.31},
]


def vision_tick() -> None:
    """Simula una detección visual (se sustituye por el módulo real de visión)."""
    cam_on = BAYE.s["sensors"]["camera"] and any(m["id"] == "vision" and m["enabled"] for m in BAYE.s["modules"])
    if not cam_on or BAYE.s["private_mode"]:
        return
    det = dict(random.choice(DETECTIONS))
    det["confidence"] = round(min(0.99, max(0.2, det["confidence"] + random.uniform(-0.15, 0.1))), 2)
    det.update({"id": f"d_{int(time.time()*1000)%100000}", "ts": time.time(),
                # caja normalizada simulada sobre el fotograma
                "box": {"x": round(random.uniform(0.05, 0.6), 3), "y": round(random.uniform(0.1, 0.6), 3),
                        "w": round(random.uniform(0.15, 0.35), 3), "h": round(random.uniform(0.2, 0.4), 3)}})
    BAYE.perceive_vision(det)
    _emit({"type": "detection", "detection": det})


# ----------------------------------------------------------------- bucle principal
async def life_loop() -> None:
    """Bucle vital global. Se lanza como task al arrancar FastAPI."""
    tick = 0
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)
        try:
            await BAYE.heartbeat()
            tick += 1
            if tick % 2 == 0:              # ~ cada 3 s una detección potencial
                vision_tick()
            broadcast_state()
        except Exception as e:             # nunca dejar morir el corazón
            db.log("error", "core", "Latido interrumpido (se recupera)", repr(e))
