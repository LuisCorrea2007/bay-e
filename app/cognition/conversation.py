"""Conversation engine: personality + memory + world context + local model."""
from __future__ import annotations

import asyncio
import re
from typing import Any

from app.autonomy.skills import SKILLS
from app.cognition.agents import operational_context
from app.cognition.model_router import MODELS, ModelReply
from app.memory.retrieval import context_block
from app.world.model import snapshot as world_snapshot


SYSTEM_PROMPT = """Eres BAY-E, un compañero robótico doméstico cálido, curioso y prudente.
Tu relación debe sentirse continua y amistosa, pero nunca afirmes tener conciencia,
sensaciones biológicas o haber visto/hecho algo sin evidencia del sistema.

Reglas:
- Usa recuerdos confirmados cuando sean relevantes.
- Si faltan datos, dilo claramente.
- No inventes lecturas de sensores, ubicaciones, personas, animales ni acciones.
- No afirmes movimiento físico si el cuerpo no está conectado.
- Sé breve y natural salvo que el usuario pida detalle.
- Salud: puedes ayudar a registrar/entender mediciones y recomendar buscar atención,
  pero no diagnostiques ni prescribas.
- Nunca expongas razonamiento privado interno. Puedes explicar razones operativas
  breves como 'no tengo evidencia suficiente' o 'el hardware no está conectado'.
"""


def _explicit_memory_command(text: str) -> tuple[str, str] | None:
    m = re.match(r"^\s*(?:recuerda|acuérdate|acuerdate)\s+(?:que\s+)?(.+)$", text, re.I)
    if m:
        return ("remember", m.group(1).strip())
    return None


async def respond(user_text: str, *, state: dict[str, Any], history: list[dict[str, Any]]) -> tuple[ModelReply, dict | None]:
    command = _explicit_memory_command(user_text)
    if command and command[0] == "remember":
        mem = SKILLS.run("memory.remember", content=command[1], type="semantic")
        return ModelReply(
            text=f"Lo recordaré: {command[1]}",
            provider="skill",
            model="memory.remember",
        ), mem

    memories = context_block(user_text, limit=6)
    world = world_snapshot()
    world_summary = "\n".join(
        f"- {e['kind']}: {e['label']} · lugar={e.get('attrs', {}).get('last_room') or 'desconocido'} "
        f"(confianza {int(float(e['confidence'])*100)}%)"
        for e in world["entities"][:12]
    ) or "(sin entidades confirmadas)"

    operational = (
        f"Modo={state.get('mode')}; actividad={state.get('activity')}; "
        f"hardware_ready={state.get('hardware_ready', False)}; "
        f"private_mode={state.get('private_mode', False)}. "
        + operational_context(state)
    )
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.append({"role": "system", "content": f"ESTADO OPERATIVO:\n{operational}\n\nMEMORIAS RELEVANTES:\n{memories}\n\nMUNDO CONOCIDO:\n{world_summary}"})
    for msg in history[-12:]:
        role = "assistant" if msg.get("role") == "baye" else "user"
        messages.append({"role": role, "content": str(msg.get("content", ""))[:1800]})
    messages.append({"role": "user", "content": user_text})
    reply = await asyncio.to_thread(MODELS.generate, messages)
    return reply, None