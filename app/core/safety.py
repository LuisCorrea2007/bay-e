"""Deterministic physical safety boundary for BAY-E.

Cognition may request actions, but only this layer decides whether an action is
admissible. Model output never controls PWM, motor drivers or servos directly.
Unknown or hazardous manipulation is denied for autonomous behavior.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


MOTION_COMMANDS = {"up", "down", "left", "right", "forward", "backward", "stop"}
HAZARDOUS_LABELS = {
    "knife", "cuchillo", "blade", "navaja", "scissors", "tijeras",
    "medicine", "medicina", "medicamento", "pill", "pastilla",
    "socket", "enchufe", "outlet", "chemical", "quimico", "químico",
    "glass", "vidrio", "hot liquid", "liquido caliente", "líquido caliente",
    "fire", "fuego", "cable", "wire",
}


@dataclass(slots=True)
class SafetyDecision:
    allowed: bool
    reason: str
    code: str
    normalized: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SafetyGovernor:
    """Pure, deterministic policy. It never calls a model."""

    def evaluate_manipulation(
        self,
        side: str,
        state: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> SafetyDecision:
        context = context or {}
        base = {"side": side, "target": str(context.get("target", "")).strip()}
        if side not in ("left", "right"):
            return SafetyDecision(False, "Brazo no reconocido.", "invalid_arm", base)
        if not state.get("hardware_connected", False):
            return SafetyDecision(False, "Manipulación bloqueada: cuerpo físico sin heartbeat.", "hardware_heartbeat_missing", base)
        if state.get("software_estop", False):
            return SafetyDecision(False, "Manipulación bloqueada por parada de emergencia.", "emergency_stop", base)
        if state.get("security", {}).get("status") not in ("ok", "clear"):
            return SafetyDecision(False, "Manipulación bloqueada por seguridad.", "security_not_clear", base)

        # Proximity constraints are conservative because an arm can injure even
        # when the target object itself is harmless.
        pet_distance = context.get("pet_distance_m")
        if pet_distance is not None and float(pet_distance) < 1.0:
            return SafetyDecision(False, "Brazo bloqueado: hay una mascota demasiado cerca.", "pet_proximity", base)
        person_distance = context.get("person_distance_m")
        if person_distance is not None and float(person_distance) < 0.55:
            return SafetyDecision(False, "Brazo bloqueado: hay una persona demasiado cerca.", "person_proximity", base)

        target_kind = str(context.get("target_kind", "")).strip().lower()
        target = base["target"].casefold()
        risk = str(context.get("risk", "")).strip().lower()
        autonomous = bool(context.get("autonomous", False))
        if target_kind in {"person", "animal", "pet"}:
            return SafetyDecision(False, "BAY-E no usa el gripper sobre personas o animales.", "living_target", base)
        if any(word in target for word in HAZARDOUS_LABELS) or risk in {"hazardous", "dangerous"}:
            return SafetyDecision(False, "Objeto potencialmente peligroso: manipulación bloqueada.", "hazardous_object", base)
        if autonomous and (not target or risk in {"", "unknown", "uncertain"}):
            return SafetyDecision(False, "BAY-E no manipula objetos desconocidos de forma autónoma.", "unknown_object", base)

        return SafetyDecision(True, "Manipulación autorizada por la capa determinista.", "allowed", base)

    def evaluate_motion(
        self,
        direction: str,
        state: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> SafetyDecision:
        context = context or {}
        direction = (direction or "stop").lower().strip()
        if direction not in MOTION_COMMANDS:
            return SafetyDecision(False, "Dirección no reconocida.", "invalid_direction", {"dir": "stop", "speed": 0.0})

        # STOP is always admissible, including during degraded/offline states.
        if direction == "stop":
            return SafetyDecision(True, "Parada segura.", "safe_stop", {"dir": "stop", "speed": 0.0})

        if state.get("software_estop", False):
            return SafetyDecision(False, "Movimiento bloqueado por parada de emergencia.", "emergency_stop", {"dir": "stop", "speed": 0.0})

        modules = {m.get("id"): m for m in state.get("modules", [])}
        motor = modules.get("motors", {})
        settings = state.get("settings", {})
        hw = settings.get("hardware", {})

        if not motor.get("enabled") or not hw.get("ros2_bridge", False):
            return SafetyDecision(False, "Movimiento bloqueado: no hay puente de hardware real habilitado.", "hardware_unavailable", {"dir": "stop", "speed": 0.0})
        if not state.get("hardware_connected", False):
            return SafetyDecision(False, "Movimiento bloqueado: no existe heartbeat del cuerpo físico.", "hardware_heartbeat_missing", {"dir": "stop", "speed": 0.0})
        if state.get("security", {}).get("status") not in ("ok", "clear"):
            return SafetyDecision(False, "Movimiento bloqueado por el estado de seguridad.", "security_not_clear", {"dir": "stop", "speed": 0.0})
        if state.get("private_mode") and not state.get("sensors", {}).get("camera"):
            return SafetyDecision(False, "Movimiento bloqueado: percepción visual desactivada.", "blind_motion", {"dir": "stop", "speed": 0.0})

        max_speed = max(0.05, min(1.0, float(settings.get("security", {}).get("max_speed", 0.6))))
        requested = max(0.0, min(max_speed, float(context.get("speed", max_speed))))
        pet_distance = context.get("pet_distance_m")
        person_distance = context.get("person_distance_m")
        if pet_distance is not None and float(pet_distance) < 1.5:
            requested = min(requested, 0.18)
        if person_distance is not None and float(person_distance) < 1.0:
            requested = min(requested, 0.22)

        return SafetyDecision(True, "Movimiento autorizado por la capa determinista.", "allowed", {"dir": direction, "speed": round(requested, 3)})


SAFETY = SafetyGovernor()
