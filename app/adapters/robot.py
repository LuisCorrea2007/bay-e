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


def _build_robot() -> RobotAdapter:
    import os
    if os.getenv("BAYE_ROS2_ENABLE", "0") == "1":
        try:
            from .ros2_robot import Ros2RobotAdapter
            adapter = Ros2RobotAdapter()
            if adapter.enabled:
                GUARDIAN.report("robot", "degraded", "ROS2 loaded; waiting for hardware heartbeat")
                return adapter
        except Exception as exc:
            GUARDIAN.report("robot", "offline", f"ROS2 unavailable: {exc!r}")
    GUARDIAN.report("robot", "offline", "No physical robot adapter connected")
    return RobotAdapter()


ROBOT = _build_robot()