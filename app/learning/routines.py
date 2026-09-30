"""Evidence-based routine discovery from real observations."""
from __future__ import annotations

from collections import Counter
import datetime as dt
import time

from app.core import db


def discover(*, days: int = 30, min_count: int = 3, limit: int = 20) -> list[dict]:
    since = time.time() - max(1, days) * 86400
    rows = db.list_observations(since=since, limit=10000)
    buckets = Counter()
    for row in rows:
        stamp = dt.datetime.fromtimestamp(float(row["ts"]))
        hour_bucket = (stamp.hour // 2) * 2
        key = (row["kind"], row["label"], row.get("room") or "unknown", hour_bucket)
        buckets[key] += 1
    out = []
    for (kind, label, room, hour), count in buckets.most_common():
        if count < min_count:
            continue
        out.append({
            "kind": kind,
            "label": label,
            "room": room,
            "hour_start": hour,
            "hour_end": (hour + 2) % 24,
            "count": count,
            "confidence": min(0.95, 0.45 + count * 0.05),
            "description": f"{label} aparece con frecuencia en {room} entre {hour:02d}:00 y {(hour+2)%24:02d}:00.",
        })
        if len(out) >= limit:
            break
    return out


def strongest() -> dict | None:
    patterns = discover(limit=1)
    return patterns[0] if patterns else None
