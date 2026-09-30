"""Chat-first command interpreter for BAY-E.

Natural-language commands that mutate state or invoke high-trust capabilities
are resolved deterministically before the LLM.  This preserves the friendly
chat UX while keeping memory, autonomy and robot control auditable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from app.autonomy.skills import SKILLS
from app.core import db
from app.core.diagnostics import snapshot as diagnostics_snapshot
from app.health.service import record as health_record
from app.memory.retrieval import retrieve
from app.world.model import snapshot as world_snapshot


@dataclass(slots=True)
class ChatCommand:
    handled: bool
    text: str = ""
    emotion: str = "curious"
    brain_command: str | None = None
    brain_payload: dict[str, Any] = field(default_factory=dict)
    ui_action: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def parse(text: str, state: dict[str, Any]) -> ChatCommand:
    raw = _norm(text)
    low = raw.lower()
    if not raw:
        return ChatCommand(False)

    # ---------- memories
    m = re.match(r"^(?:recuerda|acuérdate|acuerdate)\s+(?:que\s+)?(.+)$", raw, re.I)
    if m:
        content = m.group(1).strip()
        mem = SKILLS.run("memory.remember", content=content, type="semantic")
        return ChatCommand(True, f"Lo recordaré: {content}", "happy", data={"memory": mem})

    m = re.match(r"^(?:qué|que)\s+(?:recuerdas|sabes)\s+(?:de|sobre)\s+(.+?)[?]?$", raw, re.I)
    if m:
        topic = m.group(1).strip()
        hits = retrieve(topic, limit=5)
        if not hits:
            return ChatCommand(True, f"No tengo recuerdos confirmados sobre {topic}.", "thinking")
        summary = "; ".join(h["content"] for h in hits[:3])
        return ChatCommand(True, f"Recuerdo esto sobre {topic}: {summary}", "curious", data={"memories": hits})

    m = re.match(r"^(?:borra|elimina|olvida)\s+(?:la\s+)?memoria\s+(m_[a-z0-9]+)$", low, re.I)
    if m:
        mid = m.group(1)
        if db.delete_memory(mid):
            return ChatCommand(True, f"Eliminé la memoria {mid}.", "neutral_face")
        return ChatCommand(True, f"No encontré la memoria {mid}.", "thinking")

    if re.search(r"\b(?:abre|muestra|enséñame|enseñame)\s+(?:la\s+)?memoria\b", low):
        return ChatCommand(True, "Abro mi memoria.", "curious", ui_action="memory")

    # ---------- tasks
    m = re.match(r"^(?:crea|añade|agrega)\s+(?:una\s+)?tarea\s+(?:para\s+)?(.+)$", raw, re.I)
    if m:
        title = m.group(1).strip()
        task = SKILLS.run("task.create", title=title)
        return ChatCommand(True, f"Listo. Creé la tarea: {title}", "happy", ui_action="tasks", data={"task": task})

    if re.search(r"\b(?:abre|muestra)\s+(?:mis\s+)?tareas\b", low):
        return ChatCommand(True, "Aquí están tus tareas.", "curious", ui_action="tasks")

    # ---------- world / vision
    if re.search(r"\b(?:qué|que)\s+(?:ves|estás viendo|estas viendo)\b", low):
        recent = state.get("_recent_dets") or []
        if not recent:
            return ChatCommand(True, "Ahora mismo no tengo una observación visual confirmada.", "thinking", ui_action="vision")
        labels = []
        for d in recent[-6:]:
            label = str(d.get("label") or "algo")
            if label not in labels:
                labels.append(label)
        return ChatCommand(True, "Estoy viendo: " + ", ".join(labels) + ".", "curious", ui_action="vision")

    if re.search(r"\b(?:qué|que)\s+(?:conoces|sabes)\s+(?:del|sobre el)\s+(?:entorno|mundo|hogar|casa)\b", low):
        world = world_snapshot()
        ents = world.get("entities", [])
        if not ents:
            return ChatCommand(True, "Mi modelo del hogar todavía no tiene entidades confirmadas.", "thinking", ui_action="map")
        txt = ", ".join(f"{e['kind']}: {e['label']}" for e in ents[:8])
        return ChatCommand(True, f"En mi modelo del mundo tengo {txt}.", "curious", ui_action="map")

    if re.search(r"\b(?:abre|muestra)\s+(?:la\s+)?(?:cámara|camara|visión|vision)\b", low):
        return ChatCommand(True, "Abro mi visión.", "attentive", ui_action="vision")

    # ---------- emotions / companion
    if re.search(r"\b(?:cómo|como)\s+(?:te\s+)?(?:sientes|encuentras)\b", low):
        e = state.get("emotions", {})
        return ChatCommand(
            True,
            "Ahora mismo estoy "
            f"con energía {int(float(e.get('energy', 0))*100)}%, "
            f"curiosidad {int(float(e.get('curiosity', 0))*100)}% y "
            f"ánimo {int(float(e.get('mood', 0))*100)}%.",
            state.get("expression", {}).get("emotion", "curious"),
            ui_action="heart",
        )

    if re.search(r"\b(?:abre|muestra)\s+(?:tu\s+)?(?:corazón|corazon|emociones)\b", low):
        return ChatCommand(True, "Te muestro mi estado emocional.", "happy", ui_action="heart")

    # ---------- robot/autonomy: requests go through BayeBrain.command -> SafetyGovernor
    if re.search(r"\b(?:detente|para|alto|stop)\b", low):
        return ChatCommand(True, "Me detengo.", "attentive", brain_command="move", brain_payload={"dir": "stop"})

    if re.search(r"\b(?:explora|recorre)\b", low):
        return ChatCommand(True, "Intentaré explorar de forma segura.", "curious", brain_command="set_mode", brain_payload={"mode": "explore"}, ui_action="control")

    if re.search(r"\b(?:sígueme|sigueme|ven conmigo)\b", low):
        return ChatCommand(True, "Intentaré seguirte manteniendo distancia segura.", "attentive", brain_command="set_mode", brain_payload={"mode": "follow"}, ui_action="control")

    if re.search(r"\bpatrulla\b", low):
        return ChatCommand(True, "Inicio una solicitud de patrulla segura.", "curious", brain_command="set_mode", brain_payload={"mode": "patrol"}, ui_action="control")

    if re.search(r"\b(?:vuelve|regresa)\s+(?:a\s+)?(?:la\s+)?base\b", low):
        return ChatCommand(True, "Solicito volver a la base.", "attentive", brain_command="return_base", ui_action="control")

    if re.search(r"\b(?:activa|enciende)\s+(?:la\s+)?autonomía\b", low):
        return ChatCommand(True, "Autonomía activada.", "happy", brain_command="toggle_autonomy", brain_payload={"on": True})

    if re.search(r"\b(?:desactiva|apaga)\s+(?:la\s+)?autonomía\b", low):
        return ChatCommand(True, "Autonomía desactivada.", "neutral_face", brain_command="toggle_autonomy", brain_payload={"on": False})

    if re.search(r"\b(?:duerme|descansa|reposa)\b", low):
        return ChatCommand(True, "Entraré en reposo.", "sleepy", brain_command="set_mode", brain_payload={"mode": "rest"})

    if re.search(r"\b(?:despierta|levántate|levantate)\b", low):
        return ChatCommand(True, "Estoy despierto.", "happy", brain_command="wake")

    if re.search(r"\b(?:parada de emergencia|emergency stop|e-stop)\b", low):
        return ChatCommand(True, "Parada de emergencia activada.", "worried", brain_command="emergency_stop", ui_action="control")

    # ---------- system diagnostics
    if re.search(r"\b(?:estado del sistema|diagnóstico|diagnostico|cómo estás funcionando|como estas funcionando)\b", low):
        d = diagnostics_snapshot()
        robot = d.get("robot", {})
        model = d.get("models", {})
        provider = model.get("last_provider", "fallback")
        body = "conectado" if robot.get("connected") else "sin cuerpo conectado"
        return ChatCommand(
            True,
            f"Mi núcleo está activo. Modelo: {provider}. Robot: {body}. Guardian: {d.get('guardian', {}).get('overall', 'unknown')}.",
            "attentive",
            ui_action="logs",
            data={"diagnostics": d},
        )

    # ---------- health logging (non-diagnostic)
    m = re.match(r"^(?:registra|guarda|anota)\s+(?:mi\s+)?(?:pulso|frecuencia cardíaca|frecuencia cardiaca)\s+(\d+(?:\.\d+)?)$", low)
    if m:
        item = health_record("heart_rate", float(m.group(1)), "bpm", source="user")
        return ChatCommand(True, f"Registré una frecuencia cardíaca de {m.group(1)} bpm. Es un registro, no un diagnóstico.", "attentive", ui_action="health", data={"measurement": item})

    # ---------- direct UI navigation
    for words, view, label in [
        (("ajustes","configuración","configuracion"), "settings", "ajustes"),
        (("privacidad",), "privacy", "privacidad"),
        (("logs","eventos"), "logs", "eventos"),
        (("mapa",), "map", "mapa del hogar"),
        (("módulos","modulos"), "modules", "módulos"),
        (("mente",), "mind", "mente"),
    ]:
        if any(re.search(rf"\b(?:abre|muestra)\s+(?:los|las|el|la|tu|tus|mis)?\s*{re.escape(w)}\b", low) for w in words):
            return ChatCommand(True, f"Abro {label}.", "curious", ui_action=view)

    return ChatCommand(False)
