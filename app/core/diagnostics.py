"""Unified diagnostics snapshot for BAY-E."""
from __future__ import annotations

from app.adapters.audio import AUDIO
from app.adapters.face_identity import FACE_IDENTITY
from app.adapters.object_detector import OBJECTS
from app.adapters.robot import ROBOT
from app.adapters.vision import VISION
from app.cognition.model_router import MODELS
from app.core.guardian import GUARDIAN


def snapshot() -> dict:
    telemetry = ROBOT.telemetry()
    return {
        "guardian": GUARDIAN.snapshot(),
        "models": MODELS.status(),
        "vision": {
            "opencv": bool(VISION.available),
            "object_detector": bool(OBJECTS.available),
            "face_identity": bool(FACE_IDENTITY.available),
        },
        "audio": {
            "stt": bool(AUDIO.stt_available),
            "tts": bool(AUDIO.tts_available),
        },
        "robot": {
            "adapter": ROBOT.name,
            "connected": bool(telemetry.connected),
            "battery": telemetry.battery,
            "charging": telemetry.charging,
            "room": telemetry.room,
            "emergency_stop": telemetry.emergency_stop,
            "collision_clear": telemetry.collision_clear,
        },
    }
