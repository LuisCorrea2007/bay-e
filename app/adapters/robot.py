"""Robot adapter boundary.

The default adapter is intentionally offline. A future ROS2 implementation
will implement this exact interface and still be gated by SafetyGovernor.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.guardian import GUARDIAN


@dataclass(slots=True)
class RobotTelemetry:
    connected: bool = False
    battery: float | None = None
    charging: bool = False
    room: str | None = None
    pose: dict[str, float] | None = None


class RobotAdapter:
    name = "offline"

    def telemetry(self) -> RobotTelemetry:
        return RobotTelemetry()

    def move(self, direction: str) -> dict[str, Any]:
        raise RuntimeError("robot hardware adapter is offline")

    def look(self, yaw: float, pitch: float) -> dict[str, Any]:
        raise RuntimeError("robot hardware adapter is offline")

    def navigate(self, goal: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("robot navigation adapter is offline")


ROBOT = RobotAdapter()
GUARDIAN.report("robot", "offline", "No ROS2/hardware adapter connected")
