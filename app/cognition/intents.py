"""Deterministic intent layer for high-trust user commands.

The LLM remains conversational. Explicit data mutations are parsed here so
memory/tasks are not modified merely because a model hallucinated an action.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.autonomy.skills import SKILLS


@dataclass(slots=True)
class IntentResult:
    handled: bool
    text: str = ""
    emotion: str = "curious"
    payload: dict[str, Any] | None = None


def handle(text: str) -> IntentResult:
    raw = (text or "").strip()
    if not raw:
        return IntentResult(False)

    m = re.match(r"^(?:recuerda|acuérdate|acuerdate)\s+(?:que\s+)?(.+)$", raw, re.I)
    if m:
        content = m.group(1).strip()
        mem = SKILLS.run("memory.remember", content=content, type="semantic")
        return IntentResult(True, f"Lo recordaré: {content}", "curious", {"memory": mem})

    m = re.match(r"^(?:qué|que)\s+(?:recuerdas|sabes)\s+(?:de|sobre)\s+(.+?)[?]?$", raw, re.I)
    if m:
        q = m.group(1).strip()
        hits = SKILLS.run("memory.search", query=q, limit=5)
        if not hits:
            return IntentResult(True, f"No tengo recuerdos confirmados sobre {q}.", "thinking", {"memories": []})
        lines = "; ".join(x["content"] for x in hits[:3])
        return IntentResult(True, f"Recuerdo esto sobre {q}: {lines}", "curious", {"memories": hits})

    m = re.match(r"^(?:crea|añade|agrega)\s+(?:una\s+)?tarea\s+(?:para\s+)?(.+)$", raw, re.I)
    if m:
        title = m.group(1).strip()
        task = SKILLS.run("task.create", title=title)
        return IntentResult(True, f"He creado la tarea: {title}", "happy", {"task": task})

    m = re.match(r"^(?:abre|muéstrame|muestrame|ve a|ir a)\s+(?:la\s+|el\s+)?(memoria|visión|vision|corazón|corazon|salud|control|ajustes|configuración|configuracion|tareas|mapa|privacidad|logs?)$", raw, re.I)
    if m:
        key = m.group(1).lower()
        views = {
            "memoria": "memory", "visión": "vision", "vision": "vision",
            "corazón": "heart", "corazon": "heart", "salud": "health",
            "control": "control", "ajustes": "settings", "configuración": "settings",
            "configuracion": "settings", "tareas": "tasks", "mapa": "map",
            "privacidad": "privacy", "log": "logs", "logs": "logs",
        }
        view = views[key]
        return IntentResult(True, f"Abriendo {key}.", "curious", {"ui_action": {"type": "navigate", "view": view}})

    if re.match(r"^(?:qué|que)\s+(?:ves|conoces)\s+(?:en|del)\s+(?:mundo|entorno)[?]?$", raw, re.I):
        world = SKILLS.run("world.snapshot")
        entities = world.get("entities", [])
        if not entities:
            return IntentResult(True, "Aún no tengo entidades del entorno confirmadas.", "thinking", {"world": world})
        summary = ", ".join(f"{x['kind']}: {x['label']}" for x in entities[:8])
        return IntentResult(True, f"En mi modelo del mundo tengo: {summary}.", "curious", {"world": world})

    return IntentResult(False)