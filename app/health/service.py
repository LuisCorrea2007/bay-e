"""Non-diagnostic health observation service.

BAY-E may store measurements, calculate simple trends and flag values as
'unusual for review'. It does not diagnose conditions or prescribe treatment.
Clinical thresholds must be supplied by a validated profile/device integration,
not invented by the language model.
"""
from __future__ import annotations

from statistics import mean
import time

from app.core import db
from app.core.events import BUS


def record(metric: str, value: float, unit: str, *, source: str = "sensor", person_id: str = "", quality: float = 1.0) -> dict:
    item = db.health_add_measurement(
        metric=metric,
        value=float(value),
        unit=unit,
        source=source,
        person_id=person_id,
        quality=max(0.0, min(1.0, quality)),
    )
    BUS.publish("health.measurement", item, source="health")
    return item


def trend(metric: str, *, person_id: str = "", limit: int = 30) -> dict:
    rows = db.health_list_measurements(metric=metric, person_id=person_id, limit=limit)
    values = [float(r["value"]) for r in rows if float(r.get("quality", 0)) >= 0.5]
    if not values:
        return {"metric": metric, "count": 0, "mean": None, "delta": None}
    chronological = list(reversed(values))
    return {
        "metric": metric,
        "count": len(values),
        "mean": mean(values),
        "delta": chronological[-1] - chronological[0] if len(chronological) > 1 else 0.0,
        "latest": chronological[-1],
        "notice": "Tendencia descriptiva; no constituye diagnóstico médico.",
    }
