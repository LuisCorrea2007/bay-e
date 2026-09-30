"""Persistent semantic world model.

The model stores entities and typed relations with provenance/confidence.
It is intentionally conservative: observations are recorded as observations,
not promoted to facts without confidence.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from app.core import db
from app.core.events import BUS


def upsert_entity(kind: str, label: str, *, source: str, confidence: float = 0.7, attrs: dict[str, Any] | None = None) -> dict:
    entity = db.world_upsert_entity(
        entity_id=None,
        kind=kind,
        label=label.strip(),
        source=source,
        confidence=max(0.0, min(1.0, confidence)),
        attrs=attrs or {},
    )
    BUS.publish("world.entity_upserted", entity, source="world")
    return entity


def relate(subject_id: str, predicate: str, object_id: str, *, source: str, confidence: float = 0.7, attrs: dict[str, Any] | None = None) -> dict:
    rel = db.world_upsert_relation(
        relation_id=None,
        subject_id=subject_id,
        predicate=predicate,
        object_id=object_id,
        source=source,
        confidence=max(0.0, min(1.0, confidence)),
        attrs=attrs or {},
    )
    BUS.publish("world.relation_upserted", rel, source="world")
    return rel


def ingest_detection(det: dict[str, Any]) -> dict:
    label = str(det.get("label") or "desconocido")
    kind = str(det.get("kind") or "object")
    room = str(det.get("room") or "")
    confidence = float(det.get("confidence", 0.5))
    entity = upsert_entity(
        kind,
        label,
        source="vision",
        confidence=confidence,
        attrs={"last_box": det.get("box"), "last_seen": float(det.get("ts", time.time())), "last_room": room},
    )
    db.add_observation(
        kind=kind, label=label, room=room, source="vision",
        confidence=confidence, ts=float(det.get("ts", time.time())),
    )
    if room and room != "unknown":
        room_entity = upsert_entity(
            "room", room, source="vision", confidence=min(0.95, max(0.6, confidence)),
            attrs={"last_seen": float(det.get("ts", time.time()))},
        )
        relate(
            entity["id"], "located_in", room_entity["id"],
            source="vision", confidence=confidence,
            attrs={"observed_at": float(det.get("ts", time.time()))},
        )
    return entity


def snapshot() -> dict:
    return {
        "entities": db.world_list_entities(),
        "relations": db.world_list_relations(),
    }


BUS.subscribe("vision.detection", lambda event: ingest_detection(event.payload))