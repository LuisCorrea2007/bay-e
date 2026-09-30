"""
BAY-E · API REST modular.

Router REST sin prefijo propio. main.py lo monta en /api/v1 y conserva /api como alias legado:
  /state /chat /memories /tasks /settings /logs /vision /modules /privacy /updates /history

Diseñado para que los módulos reales (visión, ROS2, TTS) sustituyan solo el
interior de las funciones sin cambiar el contrato HTTP.
"""
import ipaddress
import json
import time
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response

from ..core import db
from ..core.brain import BAYE, EMO_KEYS, MODES
from ..core.config import APP_VERSION, BACKUP_DIR, CAM_DIR, DEFAULT_SETTINGS
from ..core.ws import broadcast_state
from ..core.events import BUS
from ..core.guardian import GUARDIAN
from ..core.diagnostics import snapshot as diagnostics_snapshot
from ..core.privacy import enforce_retention
from ..core.mobile_auth import create_pairing_code, claim_pairing_code, token_hash, verify_token
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
from ..learning.conversation import propose as propose_learning
from ..memory.relationship import observe_user_turn
from ..world.model import snapshot as world_snapshot

router = APIRouter()


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


# ================================================================ chat / conversaciones
@router.get("/chat/threads")
def chat_threads():
    return {"threads": db.list_threads()}


@router.post("/chat/threads")
def chat_threads_create(payload: dict = Body(default={})):
    return {"thread": db.create_thread(payload.get("title", "Nuevo chat"))}


@router.put("/chat/threads/{thread_id}")
def chat_threads_update(thread_id: str, payload: dict = Body(...)):
    out = db.update_thread(thread_id, title=payload.get("title"), archived=payload.get("archived"))
    if not out:
        raise HTTPException(404, "chat no encontrado")
    return {"thread": out}


@router.delete("/chat/threads/{thread_id}")
def chat_threads_delete(thread_id: str):
    ok = db.delete_thread(thread_id)
    if not ok:
        raise HTTPException(400 if thread_id == "default" else 404, "no se puede borrar este chat")
    return {"ok": True}


@router.get("/chat/history")
def chat_history(thread_id: str = "default", limit: int = Query(300, ge=1, le=2000)):
    return {"messages": db.list_messages(limit, thread_id=thread_id)}


@router.get("/chat/search")
def chat_search(q: str, limit: int = 50):
    q = " ".join((q or "").split()).strip()
    if len(q) < 2:
        raise HTTPException(400, "búsqueda demasiado corta")
    return {"results": db.search_messages(q, limit=max(1, min(200, limit)))}


@router.put("/chat/messages/{msg_id}")
def chat_message_update(msg_id: str, payload: dict = Body(...)):
    msg = db.update_message(msg_id, payload.get("content", ""))
    if not msg:
        raise HTTPException(404, "mensaje no encontrado")
    db.log("info", "chat", "Mensaje editado", f"msg={msg_id}")
    return {"message": msg}


@router.delete("/chat/messages/{msg_id}")
def chat_message_delete(msg_id: str):
    ok = db.delete_message(msg_id)
    if not ok:
        raise HTTPException(404, "mensaje no encontrado")
    db.log("sensitive", "chat", "Mensaje borrado", f"msg={msg_id}")
    return {"ok": True}


@router.post("/chat/send")
async def chat_send(payload: dict = Body(...)):
    """Conversación persistente por hilo usando el cerebro real de BAY-E."""
    text = (payload.get("text") or "").strip()
    thread_id = (payload.get("thread_id") or "default").strip()
    if not text:
        raise HTTPException(400, "mensaje vacío")
    msg = db.add_message("user", text, thread_id=thread_id)
    learning_candidate = propose_learning(text, msg["id"])
    relationship_event = None
    if not BAYE.s.get("private_mode", False):
        relationship_event = observe_user_turn(text, msg["id"])
    if learning_candidate:
        BUS.publish(
            "learning.candidate",
            {"id": learning_candidate["id"], "kind": learning_candidate["kind"]},
            source="learning",
        )
    BAYE.hear(text)
    BAYE.set_activity("thinking", 2.0)
    history = db.list_messages(120, thread_id=thread_id)
    reply, emotion, model_reply = await BAYE.generate_reply(text, history=history)
    bmsg = db.add_message("baye", reply, emotion=emotion, thread_id=thread_id)
    BAYE.set_activity("speaking", max(2.0, len(reply) / 12))
    broadcast_state()
    return {
        "user": msg,
        "baye": bmsg,
        "thread": db.get_thread(thread_id),
        "model": {"provider": model_reply.provider, "model": model_reply.model, "degraded": model_reply.degraded},
        "learning_candidate": learning_candidate,
        "relationship_event": relationship_event,
    }


@router.post("/chat/flag")
def chat_flag(payload: dict = Body(...)):
    """Acciones por mensaje: recordar, olvidar, fijar, repetir o convertir en tarea."""
    msg_id = payload.get("id")
    action = payload.get("action")
    msgs = {m["id"]: m for m in db.list_messages(3000)}
    m = msgs.get(msg_id)
    if not m:
        raise HTTPException(404, "mensaje no encontrado")

    if action == "remember":
        mem = db.add_memory(type="episodic", content=m["content"], source="chat", confidence=0.85, tags=["del-chat"])
        db.set_message_flag(msg_id, "memory", True)
        BAYE.s["last_memory"] = mem["content"]
        broadcast_state()
        return {"ok": True, "memory": mem}
    if action == "forget":
        db.set_message_flag(msg_id, "memory", False)
        n = 0
        for mm in db.list_memories(q=m["content"][:40]):
            if mm["source"] == "chat" and mm["content"] == m["content"]:
                db.delete_memory(mm["id"])
                n += 1
        return {"ok": True, "deleted": n}
    if action == "pin":
        val = not bool(m["fixed"])
        db.set_message_flag(msg_id, "fixed", val)
        return {"ok": True, "fixed": val}
    if action == "repeat":
        return {"ok": True, "text": m["content"]}
    if action == "task":
        t = db.add_task(title=m["content"][:70], description=f"Originada del mensaje {msg_id}")
        return {"ok": True, "task": t}
    if action == "memory":
        return chat_flag({"id": msg_id, "action": "remember"})
    raise HTTPException(400, f"acción desconocida: {action}")


# ================================================================ corazón / mente editable
@router.get("/mind/rules")
def mind_rules(kind: str = "", enabled_only: bool = False):
    return {"rules": db.list_mind_rules(kind=kind, enabled_only=enabled_only)}


@router.post("/mind/rules")
def mind_rules_create(payload: dict = Body(...)):
    content = (payload.get("content") or "").strip()
    if not content:
        raise HTTPException(400, "contenido vacío")
    rule = db.add_mind_rule(
        payload.get("kind", "note"),
        content,
        priority=int(payload.get("priority", 50)),
        enabled=bool(payload.get("enabled", True)),
    )
    BUS.publish("mind.rule_created", rule, source="user")
    return {"rule": rule}


@router.put("/mind/rules/{rule_id}")
def mind_rules_update(rule_id: str, payload: dict = Body(...)):
    rule = db.update_mind_rule(rule_id, **payload)
    if not rule:
        raise HTTPException(404, "regla no encontrada")
    BUS.publish("mind.rule_updated", rule, source="user")
    return {"rule": rule}


@router.delete("/mind/rules/{rule_id}")
def mind_rules_delete(rule_id: str):
    ok = db.delete_mind_rule(rule_id)
    if not ok:
        raise HTTPException(404, "regla no encontrada")
    BUS.publish("mind.rule_deleted", {"id": rule_id}, source="user")
    return {"ok": True}


@router.get("/relationship")
def relationship_state():
    """Continuidad visible sin afirmar conciencia o emociones biológicas."""
    return db.relationship_summary(limit=30)


@router.get("/mind/state")
def mind_state():
    s = BAYE.snapshot()
    return {
        "emotion": s.get("expression", {}).get("emotion"),
        "emotions": s.get("emotions", {}),
        "mode": s.get("mode"),
        "activity": s.get("activity"),
        "objective": s.get("current_task"),
        "last_thought": s.get("last_thought"),
        "next_decision": s.get("next_decision"),
        "reason": s.get("reason"),
        "learning": s.get("learning"),
        "doubt": s.get("doubt"),
        "rules": db.list_mind_rules(enabled_only=True),
    }


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


# ================================================================ aprendizaje revisable
@router.get("/learning/candidates")
def learning_candidates(status: str = "pending", limit: int = Query(100, ge=1, le=500)):
    return {"candidates": db.list_learning_candidates(status=status, limit=limit)}


@router.post("/learning/candidates/{candidate_id}/resolve")
def learning_candidate_resolve(candidate_id: str, payload: dict = Body(...)):
    action = str(payload.get("action") or "").strip().lower()
    if action not in {"approve", "reject"}:
        raise HTTPException(400, "action debe ser approve o reject")
    try:
        item = db.resolve_learning_candidate(candidate_id, action)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if not item:
        raise HTTPException(404, "candidato no encontrado")
    if action == "approve" and item.get("memory_id"):
        memory = db.get_memory(item["memory_id"])
        if memory:
            BAYE.s["last_memory"] = memory["content"]
        db.log("info", "learning", "Aprendizaje aprobado por el usuario", f"id={candidate_id}")
        BUS.publish("learning.approved", {"id": candidate_id, "memory_id": item["memory_id"]}, source="user")
    else:
        db.log("info", "learning", "Aprendizaje descartado por el usuario", f"id={candidate_id}")
        BUS.publish("learning.rejected", {"id": candidate_id}, source="user")
    broadcast_state()
    return {"ok": True, "candidate": item, "memory": db.get_memory(item["memory_id"]) if item.get("memory_id") else None}


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
        if t.get("repeat"):
            nxt = next_occurrence(float(t.get("scheduled_at") or time.time()), t["repeat"])
            t = db.update_task(tid, done_log=t["done_log"], scheduled_at=nxt, status="pending")
        else:
            t = db.update_task(tid, done_log=t["done_log"]) or t
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
    def deep_merge(base: dict, patch: dict) -> dict:
        out = dict(base)
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(out.get(key), dict):
                out[key] = deep_merge(out[key], value)
            else:
                out[key] = value
        return out

    merged = deep_merge(BAYE.s["settings"][section], payload)
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
    face_deleted = 0
    if mode == "all":
        conn_n = len(db.export_memories())
        db.delete_memories_by()          # borra toda la memoria textual
        face_deleted = db.face_purge()   # los embeddings de identidad son memoria personal
    else:
        conn_n = db.delete_memories_by(**crit)
        if mode == "person" and payload.get("person"):
            face_deleted = db.face_delete_by_name(str(payload["person"]))
    db.log("sensitive", "privacy", f"Purga de memoria ({mode}): {conn_n} memorias, {face_deleted} perfiles biométricos", json.dumps(payload))
    BAYE.s["last_memory"] = None
    broadcast_state()
    return {"ok": True, "deleted": conn_n, "face_profiles_deleted": face_deleted}


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
    return MODELS.status()


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


@router.get("/vision/people")
def vision_people():
    profiles = []
    for p in db.face_list_profiles():
        profiles.append({
            "id": p["id"], "name": p["name"], "consent_ts": p["consent_ts"],
            "created_at": p["created_at"], "updated_at": p["updated_at"],
        })
    return {"available": FACE_IDENTITY.available, "profiles": profiles}


@router.post("/vision/people/enroll")
async def vision_people_enroll(
    frame: UploadFile = File(...),
    name: str = Form(...),
    consent: bool = Form(False),
):
    if BAYE.s["private_mode"]:
        raise HTTPException(403, "modo privado activo")
    if not consent:
        raise HTTPException(400, "se requiere consentimiento explícito")
    raw = await frame.read()
    if len(raw) > 5_000_000:
        raise HTTPException(413, "fotograma demasiado grande")
    try:
        profile = FACE_IDENTITY.enroll(name, raw, consent=True)
    except PermissionError as exc:
        raise HTTPException(403, str(exc))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    db.log("sensitive", "vision", f"Perfil facial creado con consentimiento: {name}", f"id={profile['id']}")
    public = {k: profile[k] for k in ("id","name","consent_ts","created_at","updated_at")}
    return {"ok": True, "profile": public}


@router.delete("/vision/people/{profile_id}")
def vision_people_delete(profile_id: str):
    ok = db.face_delete_profile(profile_id)
    if not ok:
        raise HTTPException(404, "perfil no encontrado")
    db.log("sensitive", "vision", f"Perfil facial eliminado: {profile_id}", "")
    return {"ok": True}


@router.get("/audio/status")
def audio_status():
    return {"stt_available": AUDIO.stt_available, "tts_available": AUDIO.tts_available}


@router.get("/health/measurements")
def health_measurements(metric: str = "", person_id: str = "", limit: int = Query(50, ge=1, le=500)):
    return {"measurements": db.health_list_measurements(metric=metric, person_id=person_id, limit=limit)}


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


@router.post("/workflows/start")
def workflows_start(payload: dict = Body(...)):
    name = str(payload.get("name", "")).strip()
    if not name:
        raise HTTPException(400, "nombre de workflow obligatorio")
    try:
        run = WORKFLOWS.start(name, payload.get("context") or {})
    except KeyError:
        raise HTTPException(404, "workflow no registrado")
    return {"ok": True, "run": run}


@router.post("/workflows/{run_id}/advance")
def workflows_advance(run_id: str):
    if run_id not in WORKFLOWS.runs:
        raise HTTPException(404, "ejecución no encontrada")
    return {"ok": True, "run": WORKFLOWS.advance(run_id)}


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

@router.get("/learning/patterns")
def learning_patterns(days: int = Query(30, ge=1, le=365), min_count: int = Query(3, ge=2, le=100)):
    return {"patterns": discover_routines(days=days, min_count=min_count)}

# ================================================================ diagnóstico / mantenimiento
@router.get("/diagnostics")
def diagnostics():
    return diagnostics_snapshot()


@router.post("/privacy/enforce-retention")
def privacy_enforce_retention():
    days = int(BAYE.s["settings"]["privacy"].get("retention_days", 180))
    result = enforce_retention(days)
    broadcast_state()
    return {"ok": True, **result}

# ================================================================ nodos móviles
def _loopback_request(request: Request) -> bool:
    host = request.client.host if request.client else ""
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host in {"localhost", "testclient"}


def _require_mobile(request: Request, node_id: str) -> dict:
    auth = request.headers.get("authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "dispositivo no autenticado", headers={"WWW-Authenticate": "Bearer"})
    record = db.get_mobile_auth(node_id)
    if not record or bool(record.get("revoked")) or not verify_token(token, record.get("token_hash", "")):
        raise HTTPException(401, "credencial móvil inválida o revocada", headers={"WWW-Authenticate": "Bearer"})
    return record


@router.get("/mobile/nodes")
def mobile_nodes():
    return {"nodes": db.list_mobile_nodes()}


@router.post("/mobile/pair/start")
def mobile_pair_start(request: Request, payload: dict = Body(default={})):
    """Genera un código efímero. Solo la consola abierta en el propio Core puede pedirlo."""
    if not _loopback_request(request):
        raise HTTPException(403, "genera el código desde la consola local de BAY-E")
    pairing = create_pairing_code(int(payload.get("ttl_seconds", 300)))
    db.log("sensitive", "mobile", "Código de emparejamiento móvil generado", f"expires_at={pairing['expires_at']}")
    return {"ok": True, **pairing}


@router.post("/mobile/pair/claim")
def mobile_pair_claim(payload: dict = Body(...)):
    node_id = str(payload.get("id") or "").strip()
    code = str(payload.get("code") or "").strip()
    if not node_id or not code:
        raise HTTPException(400, "id y código son obligatorios")
    token = claim_pairing_code(code)
    if not token:
        raise HTTPException(401, "código inválido, vencido o ya utilizado")
    node = db.pair_mobile_node(
        node_id,
        name=str(payload.get("name") or "Teléfono BAY-E")[:80],
        platform=str(payload.get("platform") or "android")[:30],
        token_hash=token_hash(token),
    )
    db.log("sensitive", "mobile", "Dispositivo móvil emparejado", f"id={node_id}")
    BUS.publish("mobile.paired", {"id": node_id}, source="mobile")
    return {"ok": True, "token": token, "node": node, "core": {"version": APP_VERSION}}


@router.delete("/mobile/nodes/{node_id}")
def mobile_node_revoke(node_id: str, request: Request):
    if not _loopback_request(request):
        raise HTTPException(403, "revoca dispositivos desde la consola local de BAY-E")
    if not db.revoke_mobile_node(node_id):
        raise HTTPException(404, "dispositivo no encontrado")
    db.log("sensitive", "mobile", "Acceso móvil revocado", f"id={node_id}")
    BUS.publish("mobile.revoked", {"id": node_id}, source="user")
    return {"ok": True}


@router.post("/mobile/heartbeat")
def mobile_heartbeat(request: Request, payload: dict = Body(...)):
    node_id = (payload.get("id") or "").strip()
    if not node_id:
        raise HTTPException(400, "id de dispositivo requerido")
    _require_mobile(request, node_id)
    capabilities = payload.get("capabilities") or {}
    telemetry = payload.get("telemetry") or {}
    node = db.upsert_mobile_node(
        node_id,
        name=(payload.get("name") or "Teléfono BAY-E")[:80],
        platform=(payload.get("platform") or "android")[:30],
        capabilities=capabilities,
        telemetry=telemetry,
    )
    if capabilities.get("camera"):
        BAYE.s["sensors"]["camera"] = True
    if capabilities.get("microphone"):
        BAYE.s["sensors"]["mic"] = True
    BUS.publish("mobile.heartbeat", {"id": node_id, "telemetry": telemetry}, source="mobile")
    return {"ok": True, "node": node, "core": {"version": APP_VERSION, "private_mode": BAYE.s["private_mode"]}}


@router.get("/mobile/chat/history")
def mobile_chat_history(
    request: Request,
    node_id: str,
    thread_id: str = "default",
    limit: int = Query(100, ge=1, le=500),
):
    _require_mobile(request, node_id)
    return {"messages": db.list_messages(limit, thread_id=thread_id)}


@router.post("/mobile/chat/send")
async def mobile_chat_send(request: Request, payload: dict = Body(...)):
    node_id = str(payload.get("node_id") or "").strip()
    if not node_id:
        raise HTTPException(400, "node_id requerido")
    _require_mobile(request, node_id)
    safe_payload = dict(payload)
    safe_payload.pop("node_id", None)
    return await chat_send(safe_payload)


@router.post("/mobile/location")
def mobile_location(request: Request, payload: dict = Body(...)):
    """Ubicación de una sola lectura; no se convierte en memoria salvo petición explícita."""
    node_id = str(payload.get("node_id") or "").strip()
    _require_mobile(request, node_id)
    try:
        lat = float(payload["lat"])
        lon = float(payload["lon"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, "lat y lon válidos son obligatorios")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise HTTPException(400, "coordenadas fuera de rango")
    remember = bool(payload.get("remember", False))
    BUS.publish("mobile.location", {"id": node_id, "lat": lat, "lon": lon, "remember": remember}, source="mobile")
    memory = None
    if remember:
        memory = db.add_memory(
            type="spatial",
            content=f"Ubicación compartida desde {node_id}: {lat:.5f}, {lon:.5f}",
            source="sensor",
            confidence=0.95,
            tags=["mobile", "location", "user-approved"],
        )
    return {"ok": True, "remembered": bool(memory), "memory_id": memory["id"] if memory else None}


@router.post("/mobile/vision")
async def mobile_vision(request: Request, node_id: str = Form(...), frame: UploadFile = File(...)):
    """Usa la cámara del teléfono como ojo remoto de BAY-E."""
    _require_mobile(request, node_id)
    if BAYE.s["private_mode"]:
        raise HTTPException(403, "modo privado activo")
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
        det["source_node"] = node_id
        BAYE.perceive_vision(det)
    BUS.publish("mobile.vision", {"id": node_id, "detections": len(observation.get("detections", []))}, source="mobile")
    broadcast_state()
    return observation

