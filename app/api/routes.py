"""
BAY-E · API REST modular.

Router único montado bajo /api. Cada sección es una función con prefijo claro:
  /state /chat /memories /tasks /settings /logs /vision /modules /privacy /updates /history

Diseñado para que los módulos reales (visión, ROS2, TTS) sustituyan solo el
interior de las funciones sin cambiar el contrato HTTP.
"""
import json
import time
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response

from ..core import db
from ..core.brain import BAYE, EMO_KEYS, MODES
from ..core.config import APP_VERSION, BACKUP_DIR, CAM_DIR, DEFAULT_SETTINGS
from ..core.ws import broadcast_state
from ..core.events import BUS
from ..core.guardian import GUARDIAN
from ..core.diagnostics import snapshot as diagnostics_snapshot
from ..core.privacy import enforce_retention
from ..adapters.audio import AUDIO
from ..adapters.face_identity import FACE_IDENTITY
from ..adapters.vision import VISION
from ..autonomy.skills import SKILLS
from ..autonomy.scheduler import next_occurrence
from ..cognition.agents import manifest as agent_manifest
from ..cognition.model_router import MODELS
from ..core.workflows import WORKFLOWS
from ..health.service import record as health_record, trend as health_trend
from ..learning.routines import discover as discover_routines
from ..world.model import snapshot as world_snapshot

router = APIRouter(prefix="/api")


# ================================================================ estado general
@router.get("/state")
def get_state():
    """Snapshot completo del ser (para carga inicial sin WS)."""
    return BAYE.snapshot()


@router.post("/command")
def command(payload: dict = Body(...)):
    """Comando manual (modo, movimiento, mirada, sensores, autonomía…)."""
    ack = BAYE.command(payload.get("cmd"), payload.get("payload"))
    broadcast_state()
    return ack


# ================================================================ chat
@router.get("/chat/history")
def chat_history(limit: int = Query(200, ge=1, le=1000)):
    return {"messages": db.list_messages(limit)}


@router.post("/chat/send")
async def chat_send(payload: dict = Body(...)):
    """REST fallback using the same real conversation engine as WebSocket."""
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "mensaje vacío")
    msg = db.add_message("user", text)
    BAYE.hear(text)
    BAYE.set_activity("thinking", 2.0)
    reply, emotion, model_reply = await BAYE.generate_reply(text)
    bmsg = db.add_message("baye", reply, emotion=emotion)
    BAYE.set_activity("speaking", max(2.0, len(reply) / 12))
    broadcast_state()
    return {"user": msg, "baye": bmsg, "model": {"provider": model_reply.provider, "model": model_reply.model, "degraded": model_reply.degraded, "ui_action": model_reply.meta.get("ui_action")}}


@router.post("/chat/flag")
def chat_flag(payload: dict = Body(...)):
    """Acciones por mensaje: recordar | olvidar | fijar | repetir | tarea | memoria."""
    msg_id = payload.get("id")
    action = payload.get("action")
    msgs = {m["id"]: m for m in db.list_messages(1000)}
    m = msgs.get(msg_id)
    if not m:
        raise HTTPException(404, "mensaje no encontrado")

    if action == "remember":                      # convertir en memoria
        mem = db.add_memory(type="episodic", content=m["content"], source="chat",
                            confidence=0.85, tags=["del-chat"])
        db.set_message_flag(msg_id, "memory", True)
        BAYE.s["last_memory"] = mem["content"]
        db.log("info", "memory", "Recuerdo guardado desde el chat", f"msg={msg_id}")
        broadcast_state()
        return {"ok": True, "memory": mem}
    if action == "forget":                        # olvidar: borra la memoria asociada
        db.set_message_flag(msg_id, "memory", False)
        # buscamos memorias creadas desde este mensaje exacto
        n = 0
        for mm in db.list_memories(q=m["content"][:40]):
            if mm["source"] == "chat" and mm["content"] == m["content"]:
                db.delete_memory(mm["id"]); n += 1
        db.log("sensitive", "memory", f"Olvido solicitado ({n} memorias)", f"msg={msg_id}")
        return {"ok": True, "deleted": n}
    if action == "pin":
        val = not bool(m["fixed"])
        db.set_message_flag(msg_id, "fixed", val)
        return {"ok": True, "fixed": val}
    if action == "repeat":
        return {"ok": True, "text": m["content"]}
    if action == "task":                          # convertir en tarea
        t = db.add_task(title=m["content"][:70], description=f"Originada del mensaje {msg_id}",
                        scheduled_at=0, repeat="", room="")
        db.log("info", "tasks", "Tarea creada desde el chat", f"msg={msg_id}")
        return {"ok": True, "task": t}
    if action == "memory":                        # alias semántico de remember
        return chat_flag({"id": msg_id, "action": "remember"})
    raise HTTPException(400, f"acción desconocida: {action}")


# ================================================================ memoria CRUD
@router.get("/memories")
def memories_list(q: str = "", type: str = "", tag: str = "", archived: bool = False):
    return {"memories": db.list_memories(q=q, type=type, tag=tag, include_archived=archived)}


@router.post("/memories")
def memories_create(payload: dict = Body(...)):
    mem = db.add_memory(type=payload.get("type", "semantic"),
                        content=payload.get("content", ""),
                        detail=payload.get("detail", ""),
                        source=payload.get("source", "user"),
                        confidence=float(payload.get("confidence", 0.8)),
                        tags=payload.get("tags", []),
                        relations=payload.get("relations", []),
                        pinned=bool(payload.get("pinned")))
    BAYE.s["last_memory"] = mem["content"]
    db.log("info", "memory", "Nueva memoria creada", f"id={mem['id']}")
    broadcast_state()
    return {"ok": True, "memory": mem}


@router.get("/memories/{mid}")
def memories_get(mid: str):
    mem = db.get_memory(mid)
    if not mem:
        raise HTTPException(404, "memoria no encontrada")
    return mem


@router.put("/memories/{mid}")
def memories_update(mid: str, payload: dict = Body(...)):
    mem = db.update_memory(mid, **payload)
    if not mem:
        raise HTTPException(404, "memoria no encontrada")
    db.log("info", "memory", "Memoria editada", f"id={mid} campos={list(payload)}")
    return {"ok": True, "memory": mem}


@router.delete("/memories/{mid}")
def memories_delete(mid: str):
    ok = db.delete_memory(mid)
    db.log("sensitive", "memory", f"Borrada memoria {mid}", "")
    return {"ok": ok}


@router.post("/memories/{mid}/correct")
def memories_correct(mid: str, payload: dict = Body(...)):
    """Corregir: guarda corrección y aumenta confianza (el usuario validó)."""
    mem = db.update_memory(mid, content=payload.get("content", ""),
                           confidence=min(1.0, (db.get_memory(mid) or {}).get("confidence", 0.5) + 0.1))
    db.log("info", "memory", "Memoria corregida por el usuario", f"id={mid}")
    return {"ok": True, "memory": mem}


@router.post("/memories/{mid}/pin")
def memories_pin(mid: str, payload: dict = Body(...)):
    return {"ok": True, "memory": db.update_memory(mid, pinned=bool(payload.get("on")))}
