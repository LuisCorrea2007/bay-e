"""BAY-E skill registry.

Skills expose safe semantic actions. They never drive motors directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.core import db
from app.memory.retrieval import retrieve
from app.world.model import snapshot as world_snapshot


@dataclass(slots=True)
class Skill:
    name: str
    description: str
    handler: Callable[..., Any]
    physical: bool = False


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def list(self) -> list[dict]:
        return [{"name": s.name, "description": s.description, "physical": s.physical} for s in self._skills.values()]

    def run(self, name: str, **kwargs: Any) -> Any:
        if name not in self._skills:
            raise KeyError(name)
        return self._skills[name].handler(**kwargs)


SKILLS = SkillRegistry()
SKILLS.register(Skill("memory.search", "Buscar recuerdos confirmados.", lambda query, limit=6: retrieve(query, limit=limit)))
SKILLS.register(Skill("memory.recent", "Listar recuerdos recientes confirmados.", lambda limit=6: db.list_memories()[:int(limit)]))
SKILLS.register(Skill("memory.remember", "Crear una memoria explícita del usuario.", lambda content, type="semantic": db.add_memory(type=type, content=content, source="user", confidence=1.0, tags=["explicito"])))

def _forget(query: str) -> dict:
    hits = retrieve(query, limit=20)
    deleted = []
    for mem in hits:
        if query.lower() in (mem.get("content") or "").lower() or float(mem.get("_score", 0)) >= 1.5:
            if db.delete_memory(mem["id"]):
                deleted.append(mem["id"])
    return {"deleted": len(deleted), "ids": deleted}

SKILLS.register(Skill("memory.forget", "Borrar recuerdos confirmados que coincidan con una orden explícita.", _forget))
SKILLS.register(Skill("world.snapshot", "Leer entidades y relaciones conocidas.", lambda: world_snapshot()))
SKILLS.register(Skill("task.create", "Crear una tarea o rutina.", lambda title, description="": db.add_task(title=title, description=description)))
SKILLS.register(Skill("task.list", "Listar tareas y rutinas.", lambda: db.list_tasks()))