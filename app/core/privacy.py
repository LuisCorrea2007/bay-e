"""Privacy maintenance for persistent local data."""
from __future__ import annotations

import time

from app.core import db
from app.core.events import BUS


def enforce_retention(retention_days: int) -> dict:
    days = max(1, int(retention_days))
    cutoff = time.time() - days * 86400
    deleted = db.delete_memories_by(before=cutoff)
    if deleted:
        BUS.publish("privacy.retention_applied", {"deleted": deleted, "cutoff": cutoff, "days": days}, source="privacy")
        db.log("sensitive", "privacy", f"Retención automática: {deleted} memorias eliminadas", f"days={days}")
    return {"deleted": deleted, "cutoff": cutoff, "days": days}
