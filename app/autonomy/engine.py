"""Drive-based autonomous goal engine.

This engine creates *intentions*. Physical execution belongs to navigation /
robot adapters and must pass through the Safety Governor.
"""
from __future__ import annotations

import time

from app.core.events import BUS


class AutonomyEngine:
    def __init__(self) -> None:
        self.last_goal_at = 0.0

    def propose(self, state: dict) -> dict | None:
        if not state.get("autonomy") or state.get("private_mode"):
            return None
        e = state.get("emotions", {})
        now = time.time()
        if now - self.last_goal_at < 60:
            return None

        if float(e.get("boredom", 0)) > 0.78 and float(e.get("energy", 0)) > 0.35:
            goal = {
                "id": f"auto_{int(now)}",
                "kind": "explore",
                "label": "Buscar novedad de forma segura",
                "priority": 0.35,
                "created_at": now,
                "requires_physical_body": True,
            }
        elif float(e.get("sociability", 0)) < 0.2 and float(e.get("energy", 0)) > 0.3:
            goal = {
                "id": f"auto_{int(now)}",
                "kind": "social_checkin",
                "label": "Estar disponible para interacción social",
                "priority": 0.2,
                "created_at": now,
                "requires_physical_body": False,
            }
        else:
            return None

        self.last_goal_at = now
        BUS.publish("goal.proposed", goal, source="autonomy")
        return goal


AUTONOMY = AutonomyEngine()
