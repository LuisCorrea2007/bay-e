"""Continuidad relacional de BAY-E.

Registra hitos conversacionales explícitos y no sensibles para que la relación
tenga continuidad sin inventar sentimientos ni perfilar categorías sensibles.
Los hechos de largo plazo siguen pasando por la bandeja de aprendizaje y
requieren aprobación humana.
"""
from __future__ import annotations

import re
import unicodedata

from app.core import db
from app.learning.conversation import SENSITIVE_TERMS


_PATTERNS = [
    (re.compile(r"\bgracias\\b", re.I), "gratitude", "El usuario expresó agradecimiento.", 0.35, 0.7),
    (re.compile(r"\b(?:buenas noches|hasta mañana|nos vemos|hasta luego)\b", re.I), "farewell", "La conversación terminó con una despedida.", 0.25, 0.25),
    (re.compile(r"\b(?:hola bay-?e|buenos días bay-?e|buenas tardes bay-?e)\b", re.I), "greeting", "El usuario inició una interacción dirigiéndose a BAY-E.", 0.2, 0.2),
    (re.compile(r"\b(?:te enseñaré|te voy a enseñar|quiero enseñarte)\b", re.I), "teaching", "El usuario manifestó intención de enseñar algo a BAY-E.", 0.55, 0.35),
    (re.compile(r"\b(?:hicimos|logramos|terminamos|completamos)\b", re.I), "shared_progress", "El usuario mencionó progreso o una actividad realizada en conjunto.", 0.55, 0.45),
]


def _fold(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(ch))


def _sensitive(text: str) -> bool:
    folded = _fold(text)
    return any(_fold(term) in folded for term in SENSITIVE_TERMS if len(_fold(term)) > 4)


def observe_user_turn(text: str, source_message_id: str = "") -> dict | None:
    clean = " ".join((text or "").split()).strip()
    if not clean or len(clean) > 800 or _sensitive(clean):
        return None
    for pattern, kind, summary, salience, valence in _PATTERNS:
        if pattern.search(clean):
            return db.add_relationship_event(
                kind=kind,
                summary=summary,
                source="chat",
                source_id=source_message_id,
                salience=salience,
                valence=valence,
                tags=["non-sensitive", "continuity"],
            )
    return None


def context_block(limit: int = 8) -> str:
    snapshot = db.relationship_summary(limit=limit)
    events = snapshot["recent_events"]
    if not events:
        return "(sin hitos relacionales registrados todavía)"
    return "\n".join(
        f"- {event['summary']} ({event['kind']})"
        for event in reversed(events)
    )
