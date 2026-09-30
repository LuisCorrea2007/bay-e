"""Hybrid lightweight memory retrieval.

Uses lexical overlap + confidence + recency + pin/use signals. This keeps the
core dependency-light and deterministic. An embedding backend can later be
plugged into the same scoring function.
"""
from __future__ import annotations

import math
import re
import time
from typing import Iterable

from app.core import db


_STOP = {
    "para","como","pero","porque","cuando","donde","quien","este","esta","estos","estas",
    "algo","todo","tengo","quiero","puede","puedes","sobre","desde","hasta","the","and","with",
}


def tokens(text: str) -> set[str]:
    out = set(re.findall(r"[a-záéíóúñ0-9_]{3,}", (text or "").lower()))
    return {x for x in out if x not in _STOP}


def _score(query: str, memory: dict) -> float:
    q = tokens(query)
    body = tokens(" ".join([
        memory.get("content", ""),
        memory.get("detail", ""),
        " ".join(memory.get("tags", [])),
    ]))
    overlap = len(q & body) / max(1, len(q | body))
    confidence = float(memory.get("confidence", 0.5))
    age_days = max(0.0, (time.time() - float(memory.get("updated_at", 0))) / 86400)
    recency = math.exp(-age_days / 90.0)
    usage = min(1.0, math.log1p(int(memory.get("use_count", 0))) / 4.0)
    pin = 1.0 if memory.get("pinned") else 0.0
    return overlap * 0.62 + confidence * 0.14 + recency * 0.10 + usage * 0.06 + pin * 0.08


def retrieve(query: str, *, limit: int = 6, types: Iterable[str] | None = None) -> list[dict]:
    candidates = db.list_memories(include_archived=False)
    allowed = set(types or ())
    if allowed:
        candidates = [m for m in candidates if m.get("type") in allowed]
    ranked = sorted(candidates, key=lambda m: _score(query, m), reverse=True)
    ranked = [m for m in ranked if _score(query, m) > 0.12][:limit]
    for m in ranked:
        db.touch_memory(m["id"])
    return ranked


def context_block(query: str, *, limit: int = 6) -> str:
    hits = retrieve(query, limit=limit)
    if not hits:
        return "(sin recuerdos relevantes confirmados)"
    return "\n".join(
        f"- [{m['type']}] {m['content']} (confianza {int(float(m['confidence'])*100)}%, fuente {m['source']})"
        for m in hits
    )
