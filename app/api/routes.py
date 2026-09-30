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

from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response

from ..core import db
from ..core.brain import BAYE, EMO_KEYS, MODES
from ..core.config import APP_VERSION, BACKUP_DIR, CAM_DIR, DEFAULT_SETTINGS
from ..core.ws import broadcast_state
from ..core.events import BUS
from ..core.guardian import GUARDIAN
from ..adapters.audio import AUDIO
from ..adapters.vision import VISION
from ..autonomy.skills import SKILLS
from ..cognition.agents import manifest as agent_manifest
from ..cognition.model_router import MODELS
from ..core.workflows import WORKFLOWS
from ..health.service import record as health_record, trend as health_trend
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
    return {"user": msg, "baye": bmsg, "model": {"provider": model_reply.provider, "model": model_reply.model, "degraded": model_reply.degraded}}


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


@router.post("/memories/{mid}/archive")
def memories_archive(mid: str, payload: dict = Body(...)):
    return {"ok": True, "memory": db.update_memory(mid, archived=bool(payload.get("on")))}


@router.post("/memories/merge")
def memories_merge(payload: dict = Body(...)):
    out = db.merge_memories(payload.get("primary"), payload.get("secondary"))
    if not out:
        raise HTTPException(404, "memorias no encontradas")
    db.log("info", "memory", "Memorias fusionadas", str(payload))
    return {"ok": True, "memory": out}


@router.get("/memories/export")
def memories_export():
    data = db.export_memories()
    return JSONResponse(data, headers={"Content-Disposition": 'attachment; filename="baye-memories.json"'})


@router.post("/memories/import")
async def memories_import(file: UploadFile = File(...)):
    raw = await file.read()
    try:
        items = json.loads(raw.decode("utf-8"))
    except Exception:
        raise HTTPException(400, "JSON inválido")
    n = db.import_memories(items if isinstance(items, list) else items.get("memories", []))
    db.log("info", "memory", f"Importadas {n} memorias", "")
    return {"ok": True, "imported": n}


# ================================================================ tareas
@router.get("/tasks")
def tasks_list():
    return {"tasks": db.list_tasks()}


@router.post("/tasks")
def tasks_create(payload: dict = Body(...)):
    t = db.add_task(title=payload.get("title", "tarea"),
                    description=payload.get("description", ""),
                    scheduled_at=float(payload.get("scheduled_at") or 0),
                    repeat=payload.get("repeat", ""),
                    room=payload.get("room", ""))
    db.log("info", "tasks", f"Tarea creada: {t['title']}", "")
    return {"ok": True, "task": t}


@router.put("/tasks/{tid}")
def tasks_update(tid: str, payload: dict = Body(...)):
    t = db.update_task(tid, **payload)
    if not t:
        raise HTTPException(404, "tarea no encontrada")
    if payload.get("status") == "done":
        t["done_log"].append(time.strftime("%Y-%m-%d %H:%M"))
        db.update_task(tid, done_log=t["done_log"])
    return {"ok": True, "task": t}


@router.delete("/tasks/{tid}")
def tasks_delete(tid: str):
    return {"ok": db.delete_task(tid)}


# ================================================================ configuración
@router.get("/settings")
def settings_get():
    return {"settings": BAYE.s["settings"], "voices": DEFAULT_SETTINGS["identity"] and
            ["cálida · suave", "juguetona", "serena", "guardián", "piloto"],
            "languages": {"es": "Español", "en": "English", "ca": "Català", "fr": "Français"}}


@router.put("/settings/{section}")
def settings_put(section: str, payload: dict = Body(...)):
    if section not in BAYE.s["settings"]:
        raise HTTPException(404, f"sección desconocida: {section}")
    merged = {**BAYE.s["settings"][section], **payload}
    BAYE.s["settings"][section] = merged
    db.set_setting(f"settings:{section}", merged)
    # efectos inmediatos
    if section == "autonomy":
        BAYE.s["autonomy"] = bool(merged.get("enabled"))
    if section == "privacy":
        BAYE.s["private_mode"] = bool(merged.get("private_mode"))
    if section == "system":
        BAYE.s["demo_mode"] = bool(merged.get("demo_mode", False))
    if section == "identity":
        pass  # el frontend re-pinta nombre/voz al recibir state
    db.log("info", "settings", f"Configuración actualizada: {section}", json.dumps(payload)[:300])
    broadcast_state()
    return {"ok": True, "section": section, "value": merged}


# ================================================================ logs
@router.get("/logs")
def logs_list(limit: int = 300, level: str = "", module: str = "", sensitive: bool = False):
    return {"logs": db.list_logs(limit=limit, level=level, module=module, only_sensitive=sensitive)}


# ================================================================ visión
@router.get("/vision/frame")
def vision_frame():
    """Fotograma simulado. Con hardware real: devolver JPEG/MJPEG del driver."""
    frames = sorted(CAM_DIR.glob("frame_*.jpg"))
    if frames:
        return FileResponse(frames[-1], media_type="image/jpeg")
    # placeholder SVG (siempre existe) -> se sirve desde static
    return FileResponse(Path(__file__).resolve().parents[2] / "static" / "camera_sim.svg",
                        media_type="image/svg+xml")


@router.get("/vision/detections")
def vision_detections():
    return {"detections": BAYE.s.get("_recent_dets", [])}


# ================================================================ módulos / updates
@router.get("/modules")
def modules_list():
    return {"version": APP_VERSION, "modules": BAYE.s["modules"]}


@router.post("/modules/{mid}/toggle")
def modules_toggle(mid: str, payload: dict = Body(...)):
    for m in BAYE.s["modules"]:
        if m["id"] == mid:
            m["enabled"] = bool(payload.get("on"))
            db.set_setting("modules", BAYE.s["modules"])
            db.log("info", "modules", f"Módulo {m['name']} {'activado' if m['enabled'] else 'desactivado'}", "")
            broadcast_state()
            return {"ok": True, "modules": BAYE.s["modules"]}
    raise HTTPException(404, "módulo no encontrado")


@router.post("/updates/check")
def updates_check():
    """No inventa actualizaciones: un proveedor real se conectará más adelante."""
    return {"ok": True, "current": APP_VERSION, "available": [], "source": "not_configured"}


@router.post("/updates/install")
def updates_install(payload: dict = Body(...)):
    raise HTTPException(409, "No hay proveedor de actualizaciones configurado. BAY-E no simulará una instalación.")


@router.post("/backups")
def backups_create():
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = BACKUP_DIR / f"baye-backup-{stamp}.json"
    out.write_text(json.dumps({"memories": db.export_memories(),
                               "settings": BAYE.s["settings"],
                               "modules": BAYE.s["modules"]}, ensure_ascii=False, indent=2))
    db.log("sensitive", "backup", f"Backup creado: {out.name}", "")
    return {"ok": True, "file": str(out)}


@router.get("/backups")
def backups_list():
    return {"backups": [{"name": p.name, "size": p.stat().st_size,
                         "ts": p.stat().st_mtime} for p in sorted(BACKUP_DIR.glob("*.json"), reverse=True)]}


@router.post("/backups/restore")
def backups_restore(payload: dict = Body(...)):
    name = payload.get("name", "")
    p = BACKUP_DIR / name
    if not p.exists():
        raise HTTPException(404, "backup no encontrado")
    data = json.loads(p.read_text())
    n = db.import_memories(data.get("memories", []))
    db.log("sensitive", "backup", f"Restaurado backup {name} ({n} memorias)", "")
    return {"ok": True, "restored": n}


# ================================================================ privacidad
@router.post("/privacy/purge")
def privacy_purge(payload: dict = Body(...)):
    """Borrado masivo: all | type | person | before(date ISO)."""
    mode = payload.get("mode", "all")
    crit: dict = {}
    if mode == "type":
        crit["type"] = payload.get("type")
    elif mode == "person":
        crit["person_content_like"] = payload.get("person", "")
    elif mode == "before":
        crit["before"] = float(payload.get("timestamp", 0))
    elif mode != "all":
        raise HTTPException(400, "modo desconocido")
    if mode == "all":
        conn_n = len(db.export_memories())
        db.delete_memories_by()          # borra todo (sin filtros)
    else:
        conn_n = db.delete_memories_by(**crit)
    db.log("sensitive", "privacy", f"Purga de memoria ({mode}): {conn_n} elementos borrados", json.dumps(payload))
    BAYE.s["last_memory"] = None
    broadcast_state()
    return {"ok": True, "deleted": conn_n}


# ================================================================ histórico emociones
@router.get("/history")
def history(limit: int = 240):
    return {"history": db.get_history(limit)}

# ================================================================ núcleo / observabilidad
@router.get("/core/events")
def core_events(limit: int = Query(100, ge=1, le=500)):
    return {"events": BUS.recent(limit)}


@router.get("/guardian")
def guardian_state():
    return GUARDIAN.snapshot()

# ================================================================ capacidades reales
@router.get("/models")
def models_state():
    return {
        "last_provider": MODELS.last_provider,
        "providers": [p.name for p in MODELS.providers],
        "fallback": MODELS.fallback.name,
    }


@router.get("/skills")
def skills_list():
    return {"skills": SKILLS.list()}


@router.get("/world")
def world_get():
    return world_snapshot()


@router.get("/vision/status")
def vision_status():
    return {"available": VISION.available, "private_mode": BAYE.s["private_mode"], "camera_enabled": BAYE.s["sensors"]["camera"]}


@router.post("/vision/observe")
async def vision_observe(frame: UploadFile = File(...)):
    if BAYE.s["private_mode"]:
        raise HTTPException(403, "modo privado activo")
    if not BAYE.s["sensors"]["camera"]:
        raise HTTPException(409, "sensor de cámara desactivado")
    raw = await frame.read()
    if len(raw) > 5_000_000:
        raise HTTPException(413, "fotograma demasiado grande")
    try:
        observation = VISION.observe_jpeg(raw)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    for det in observation.get("detections", []):
        BAYE.perceive_vision(det)
    broadcast_state()
    return observation


@router.get("/audio/status")
def audio_status():
    return {"stt_available": AUDIO.stt_available, "tts_available": AUDIO.tts_available}


@router.post("/health/measurements")
def health_measurement(payload: dict = Body(...)):
    if not payload.get("metric") or payload.get("value") is None or not payload.get("unit"):
        raise HTTPException(400, "metric, value y unit son obligatorios")
    item = health_record(
        str(payload["metric"]),
        float(payload["value"]),
        str(payload["unit"]),
        source=str(payload.get("source", "user")),
        person_id=str(payload.get("person_id", "")),
        quality=float(payload.get("quality", 1.0)),
    )
    return {"ok": True, "measurement": item, "notice": "Registro descriptivo; no constituye diagnóstico."}


@router.get("/health/trend/{metric}")
def health_metric_trend(metric: str, person_id: str = "", limit: int = Query(30, ge=1, le=500)):
    return health_trend(metric, person_id=person_id, limit=limit)

@router.get("/agents")
def agents_list():
    return {"agents": agent_manifest()}


@router.get("/workflows")
def workflows_list():
    return {"runs": WORKFLOWS.list_runs(), "definitions": sorted(WORKFLOWS.definitions)}


@router.post("/audio/tts")
def audio_tts(payload: dict = Body(...)):
    text = str(payload.get("text", "")).strip()
    if not text:
        raise HTTPException(400, "texto vacío")
    if len(text) > 3000:
        raise HTTPException(413, "texto demasiado largo")
    if not AUDIO.tts_available:
        raise HTTPException(503, "Piper no está configurado")
    try:
        wav = AUDIO.synthesize_wav(text)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    return Response(content=wav, media_type="audio/wav")


@router.post("/audio/transcribe")
async def audio_transcribe(audio: UploadFile = File(...)):
    if not AUDIO.stt_available:
        raise HTTPException(503, "whisper.cpp no está configurado")
    raw = await audio.read()
    if len(raw) > 25_000_000:
        raise HTTPException(413, "audio demasiado grande")
    suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(raw)
        path = tmp.name
    try:
        text = AUDIO.transcribe_wav(path)
    finally:
        Path(path).unlink(missing_ok=True)
    BAYE.hear(text)
    return {"text": text}
