"""Aprendizaje conversacional prudente de BAY-E.

Este módulo NO escribe recuerdos de largo plazo automáticamente. Detecta hechos
simples de primera persona y los coloca en una bandeja de revisión. El usuario
debe aprobar cada candidato antes de que se convierta en memoria persistente.

El extractor deliberadamente evita categorías sensibles y frases ambiguas.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

from app.core import db


SENSITIVE_TERMS = {
    "contraseña", "password", "clave", "pin", "tarjeta", "cuenta bancaria",
    "cedula", "cédula", "pasaporte", "religion", "religión", "partido político",
    "partido politico", "voto", "votar", "orientación sexual", "orientacion sexual",
    "diagnóstico", "diagnostico", "enfermedad", "medicación", "medicacion",
    "medicina", "depresión", "depresion", "ansiedad", "embarazo", "salario",
    "sueldo", "deuda", "dirección", "direccion", "domicilio", "vivo en", "vivienda",
    "casa en", "ubicación", "ubicacion", "médico", "medico", "hospital", "terapia",
    "pastilla", "insulina", "diabetes", "presión", "presion", "iglesia", "misa",
    "templo", "candidato", "presidente", "alcalde", "ideología", "ideologia",
}

PATTERNS: list[tuple[re.Pattern[str], str, str, float]] = [
    (re.compile(r"^\s*me gusta(?:n)?\s+(.{2,180})[.!?]?\s*$", re.I),
     "semantic", "Al usuario le gusta {value}.", 0.84),
    (re.compile(r"^\s*no me gusta(?:n)?\s+(.{2,180})[.!?]?\s*$", re.I),
     "semantic", "Al usuario no le gusta {value}.", 0.84),
    (re.compile(r"^\s*prefiero\s+(.{2,180})[.!?]?\s*$", re.I),
     "semantic", "El usuario prefiere {value}.", 0.86),
    (re.compile(r"^\s*mi (?:comida|color|música|musica|película|pelicula|serie|juego|deporte) favorit[oa] es\s+(.{2,160})[.!?]?\s*$", re.I),
     "semantic", "Una preferencia favorita del usuario es {value}.", 0.88),
    (re.compile(r"^\s*tengo un(?:a)?\s+(perro|perra|gato|gata|mascota)\s+(?:que se llama|llamad[oa])\s+([\wÁÉÍÓÚÜÑáéíóúüñ -]{1,60})[.!?]?\s*$", re.I),
     "semantic", "El usuario tiene {value}.", 0.9),
    (re.compile(r"^\s*(?:normalmente|usualmente|por lo general)\s+(.{3,180})[.!?]?\s*$", re.I),
     "routine", "Rutina declarada por el usuario: {value}.", 0.72),
]


def _fold(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text.lower())
        if not unicodedata.combining(ch)
    )


def _safe(text: str) -> bool:
    folded = _fold(text)
    for term in SENSITIVE_TERMS:
        needle = _fold(term)
        if len(needle) <= 4 and " " not in needle:
            if re.search(r"\b" + re.escape(needle) + r"\b", folded):
                return False
        elif needle in folded:
            return False
    return True


def _clean(value: str) -> str:
    return value.strip().rstrip(".!?").strip()


def propose(user_text: str, source_message_id: str = "") -> Optional[dict]:
    """Devuelve/crea como máximo un candidato conservador por turno."""
    text = " ".join((user_text or "").split()).strip()
    if len(text) < 4 or len(text) > 260 or not _safe(text):
        return None

    for pattern, kind, template, confidence in PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        groups = [_clean(g) for g in match.groups() if g]
        if not groups:
            continue
        if len(groups) == 2 and groups[0].lower() in {"perro","perra","gato","gata","mascota"}:
            value = f"{groups[0]} llamado {groups[1]}"
        else:
            value = groups[-1]
        if len(value) < 2 or not _safe(value):
            return None
        content = template.format(value=value)
        return db.add_learning_candidate(
            kind=kind,
            content=content,
            source_message_id=source_message_id,
            confidence=confidence,
            reason="Detectado en conversación; requiere aprobación humana antes de entrar en memoria.",
        )
    return None
