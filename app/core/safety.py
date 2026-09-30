"""Deterministic safety governor for BAY-E.

The cognitive layer may request an action; this module decides whether that
action is admissible.  AI/model output never talks to motors directly.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


MOTION_COMMANDS = {"up", "down", "left", "right", "forward", "backward", "stop"}


@dataclass(slots=True)
class SafetyDecision:
    allowed: bool
    reason: str
    code: str
    normalized: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SafetyGovernor:
    def evaluate_motion(self, direction: str, state: dict[str, Any]) -> SafetyDecision:
        direction = (direction or "stop").lower().strip()
        if direction not in MOTION_COMMANDS:
            return SafetyDecision(False, "Dirección no reconocida.", "invalid_direction", {"dir": "stop"})

        # STOP is always admissible, even with no hardware.
        if direction == "stop":
            return SafetyDecision(True, "Parada segura.", "safe_stop", {"dir": "stop"})

        modules = {m.get("id"): m for m in state.get("modules", [])}
        motor = modules.get("motors", {})
        hw = state.get("settings", {}).get("hardware", {})

        if not motor.get("enabled") or not hw.get("ros2_bridge", False):
            return SafetyDecision(
                False,
                "Movimiento bloqueado: todavía no hay un puente de hardware real habilitado.",
                "hardware_unavailable",
                {"dir": "stop"},
            )

        if not state.get("hardware_connected", False):
            return SafetyDecision(
                False,
                "Movimiento bloqueado: no existe heartbeat del cuerpo físico.",
                "hardware_heartbeat_missing",
                {"dir": "stop"},
            )

        security = state.get("security", {})
        if security.get("status") not in ("ok", "clear"):
            return SafetyDecision(
                False,
                "Movimiento bloqueado por el estado de seguridad.",
                "security_not_clear",
                {"dir": "stop"},
            )

        if state.get("private_mode"):
            # Privacy does not normally forbid motion, but until physical
            # sensors are wired it is safer not to move blind.
            sensors = state.get("sensors", {})
            if not sensors.get("camera"):
                return SafetyDecision(False, "Movimiento bloqueado: percepción visual desactivada.", "blind_motion", {"dir": "stop"})

        return SafetyDecision(True, "Movimiento autorizado por la capa determinista.", "allowed", {"dir": direction})


SAFETY = SafetyGovernor()