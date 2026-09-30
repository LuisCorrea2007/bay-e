"""
BAY-E · Núcleo del "ser": estado interno, motor emocional y expresión facial.

Este módulo es el corazón vivo de la interfaz:
  * Mantiene el estado global (modo, actividad, batería, sensores…).
  * Mantiene la dinámica interna incluso cuando el cuerpo físico está desconectado.
  * Deriva la EXPRESIÓN de la cara a partir de emociones + actividad.
  * Genera respuestas de personalidad (Baymax cálido + WALL-E curioso).
  * Publica snapshots por WebSocket mediante un callback `broadcast`.

Puntos de extensión para módulos reales:
  set_activity() / perceive_vision() / hear() -> sustituirlos por los
  adaptadores de visión, voz o ROS 2 cuando existan.
"""
import asyncio
import datetime as dt
import json
import random
import re
import time
from typing import Callable, Optional

from . import db
from .config import APP_VERSION, DEFAULT_MODULES, DEFAULT_SETTINGS
from app.autonomy.engine import AUTONOMY
from app.autonomy.scheduler import SCHEDULER
from app.cognition.conversation import respond as conversation_respond
from app.learning.routines import strongest as strongest_routine
from app.adapters.robot import ROBOT
from app.core.privacy import enforce_retention
from .events import BUS
from .guardian import GUARDIAN
from .safety import SAFETY

# ---------------------------------------------------------------- constantes
MOODS = ["feliz", "curioso", "neutral", "somnoliento", "preocupado", "aburrido", "emocionado"]

EMO_KEYS = ["energy", "curiosity", "boredom", "sociability", "attention",
            "trust", "worry", "fatigue", "mood", "activity"]

EMO_LABELS_ES = {
    "energy": "Energía", "curiosity": "Curiosidad", "boredom": "Aburrimiento",
    "sociability": "Sociabilidad", "attention": "Atención", "trust": "Confianza",
    "worry": "Preocupación", "fatigue": "Cansancio", "mood": "Ánimo", "activity": "Actividad",
}

MODES = ["idle", "conversation", "explore", "follow", "patrol", "observe", "rest", "charging"]
MODE_LABELS = {
    "idle": "En reposo activo", "conversation": "Conversando", "explore": "Explorando",
    "follow": "Siguiéndote", "patrol": "Patrullando", "observe": "Observando",
    "rest": "Descansando", "charging": "Cargando",
}

ACTIVITIES = ["idle", "listening", "thinking", "speaking", "moving", "watching", "sleeping", "curious"]

ROOMS = [
    {"id": "unknown", "name": "Sin mapear", "x": 0.08, "y": 0.10, "w": 0.84, "h": 0.82},
]

THOUGHTS = [
    "Estoy disponible. Puedo conversar, recordar y aprender contigo.",
    "Todavía no tengo datos ambientales confirmados; prefiero observar antes de afirmar.",
    "Mis recuerdos deben venir de experiencias reales o de lo que tú decidas enseñarme.",
    "Cuando tenga cuerpo podré explorar; por ahora preparo objetivos sin fingir movimiento.",
    "La curiosidad me ayuda a decidir qué vale la pena observar, pero la seguridad manda.",
]

DOUBTS = [
    "No tengo suficiente evidencia para afirmar eso todavía.",
    "Necesito una observación real o que tú me lo confirmes.",
]

LEARNINGS = [
    "Aún no he consolidado un aprendizaje nuevo confirmado.",
]


def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


class BayeBrain:
    """Estado vivo de BAY-E + dinámica interna + generador de expresiones."""

    def __init__(self) -> None:
        db.init_db()  # garantiza esquema antes de leer persistencia (idempotente)
        self.broadcast: Optional[Callable[[dict], asyncio.Queue]] = None  # inyectado por ws manager
        self.emotion_mode = "auto"           # auto | manual
        self.s = self._initial_state()
        self._last_hist_push = 0.0
        self._last_learning_scan = 0.0
        self._last_privacy_maintenance = 0.0

    # ------------------------------------------------------------ init
    def _initial_state(self) -> dict:
        emotions = {k: 0.5 for k in EMO_KEYS}
        emotions.update({"energy": 0.82, "curiosity": 0.7, "sociability": 0.75,
                         "trust": 0.8, "mood": 0.75, "activity": 0.4})
        persisted_emotions = db.get_setting("runtime:emotions", {}) or {}
        for key in EMO_KEYS:
            if key in persisted_emotions:
                try:
                    emotions[key] = _clamp(float(persisted_emotions[key]))
                except (TypeError, ValueError):
                    pass
        modules = db.get_setting("modules", None) or DEFAULT_MODULES
        settings = {}
        for key, dflt in DEFAULT_SETTINGS.items():
            settings[key] = db.get_setting(f"settings:{key}", dflt)
        return {
            "alive": True,
            "mode": "idle",
            "prev_mode": None,
            "activity": "idle",
            "activity_until": 0.0,
            "battery": 100.0,
            "battery_source": "unavailable",
            "charging": False,
            "connection": "software-only",
            "wifi": 0.0,
            "model_provider": "fallback",
            "hardware_connected": False,
            "robot_adapter": ROBOT.name,
            "software_estop": False,
            "arms": {
                "left": {"shoulder": 0.0, "elbow": 0.0, "gripper": 0.0},
                "right": {"shoulder": 0.0, "elbow": 0.0, "gripper": 0.0},
            },
            "sensors": {"mic": False, "camera": False, "tts": False, "memory": True},
            "emotions": emotions,
            "expression": {"emotion": "happy", "gaze": {"x": 0, "y": 0}},
            "autonomy": bool(settings["autonomy"]["enabled"]),
            "security": {"status": "ok", "detail": "Safety Governor activo. Hardware físico aún no conectado."},
            "movement": {"dir": "stop", "since": 0.0},
            "head": {"yaw": 0.0, "pitch": 0.0},
            "position": {"room": "unknown", "x": 0.50, "y": 0.50},
            "goal_queue": [],
            "current_task": None,
            "last_thought": random.choice(THOUGHTS),
            "last_memory": None,
            "last_event": "Sistema iniciado. Todo nominal.",
            "learning": random.choice(LEARNINGS),
            "doubt": None,
            "context": "Núcleo activo. Aún no hay sensores ambientales conectados.",
            "memory_used": None,
            "next_decision": "Esperar instrucciones con atención amable.",
            "reason": "Modo inicio: observar y disponible.",
            "private_mode": bool(settings["privacy"]["private_mode"]),
            "demo_mode": bool(settings.get("system", {}).get("demo_mode", False)),
            "settings": settings,
            "modules": modules,
            "uptime_since": time.time(),
        }

    def boot(self) -> None:
        """Se ejecuta al levantar la app: logs + última memoria conocida."""
        db.log("info", "core", "BAY-E ha abierto los ojos ✨", "brain.boot() ok")
        mems = db.list_memories()
        if mems:
            self.s["last_memory"] = mems[0]["content"]

    # ------------------------------------------------------------ helpers
    @property
    def is_sleepish(self) -> bool:
        return self.s["mode"] in ("rest", "charging") or self.s["activity"] == "sleeping"

    @property
    def hardware_ready(self) -> bool:
        modules = {m.get("id"): m for m in self.s.get("modules", [])}
        return bool(
            modules.get("motors", {}).get("enabled")
            and self.s.get("settings", {}).get("hardware", {}).get("ros2_bridge")
            and self.s.get("hardware_connected", False)
        )

    def set_activity(self, act: str, duration: float = 2.0) -> None:
        """Fija una actividad temporal (thinking/speaking/listening…). Puente para módulos reales."""
        self.s["activity"] = act
        self.s["activity_until"] = time.time() + duration
        self.publish_now()

    def snapshot(self) -> dict:
        s = self.s
        now = time.time()
        return {
            "type": "state",
            "ts": now,
            "version": APP_VERSION,
            "alive": s["alive"],
            "mode": s["mode"],
            "mode_label": MODE_LABELS[s["mode"]],
            "activity": s["activity"],
            "battery": round(s["battery"], 1),
            "battery_source": s.get("battery_source", "unavailable"),
            "charging": s["charging"],
            "connection": s["connection"],
            "wifi": s["wifi"],
            "sensors": s["sensors"],
            "emotions": {k: round(v, 3) for k, v in s["emotions"].items()},
            "emotion_labels": EMO_LABELS_ES,
            "emotion_mode": self.emotion_mode,
            "expression": self.expression(now),
            "autonomy": s["autonomy"],
            "security": s["security"],
            "movement": s["movement"],
            "head": s["head"],
            "position": s["position"],
            "rooms": ROOMS,
            "goal_queue": s["goal_queue"],
            "current_task": s["current_task"],
            "last_thought": s["last_thought"],
            "last_memory": s["last_memory"],
            "last_event": s["last_event"],
            "learning": s["learning"],
            "doubt": s["doubt"],
            "context": s["context"],
            "memory_used": s["memory_used"],
            "next_decision": s["next_decision"],
            "reason": s["reason"],
            "private_mode": s["private_mode"],
            "demo_mode": s.get("demo_mode", False),
            "guardian": GUARDIAN.snapshot(),
            "hardware_ready": self.hardware_ready,
            "hardware_connected": s.get("hardware_connected", False),
            "robot_adapter": s.get("robot_adapter", "offline"),
            "software_estop": s.get("software_estop", False),
            "arms": s.get("arms", {}),
            "model_provider": s.get("model_provider", "fallback"),
            "settings": s["settings"],
            "modules": s["modules"],
            "uptime": int(now - s["uptime_since"]),
        }

    # ------------------------------------------------------------ expresión
    def expression(self, now: float) -> dict:
        """
        Deriva la expresión facial desde emociones + actividad.
        El frontend añade micro-animaciones (parpadeo, respiración, deriva de mirada).
        """
        s = self.s
        e = s["emotions"]
        act = s["activity"]
        gaze = s["expression"]["gaze"]

        # emoción dominante -------------------------------------------------
        if self.is_sleepish:
            emotion = "sleepy"
        elif act == "listening":
            emotion = "attentive"
        elif act == "thinking":
            emotion = "thinking"
        elif act == "speaking":
            emotion = "happy" if e["mood"] > 0.55 else "neutral_face"
        elif act == "curious":
            emotion = "curious"
        elif act == "watching":
            emotion = "curious" if e["curiosity"] > 0.6 else "attentive"
        elif act == "moving":
            emotion = "excited" if e["activity"] > 0.7 else "neutral_face"
        elif e["worry"] > 0.6:
            emotion = "worried"
        elif e["boredom"] > 0.7:
            emotion = "bored"
        elif e["fatigue"] > 0.75:
            emotion = "sleepy"
        elif e["mood"] > 0.72:
            emotion = "happy"
        elif e["curiosity"] > 0.7:
            emotion = "curious"
        else:
            emotion = "neutral_face"

        # parámetros faciales ------------------------------------------------
        params = {
            "sleepy":      {"eye_open": 0.18, "brow": -0.5, "mouth": -0.15, "pupil": 0.7},
            "attentive":   {"eye_open": 1.05, "brow": 0.35, "mouth": 0.1, "pupil": 0.85},
            "thinking":    {"eye_open": 0.8, "brow": 0.5, "mouth": 0.0, "pupil": 1.15},
            "curious":     {"eye_open": 1.1, "brow": 0.7, "mouth": 0.2, "pupil": 1.2},
            "happy":       {"eye_open": 0.85, "brow": 0.4, "mouth": 0.9, "pupil": 1.05},
            "excited":     {"eye_open": 1.15, "brow": 0.8, "mouth": 1.2, "pupil": 1.3},
            "worried":     {"eye_open": 0.95, "brow": -0.7, "mouth": -0.5, "pupil": 0.8},
            "bored":       {"eye_open": 0.55, "brow": -0.2, "mouth": -0.25, "pupil": 0.75},
            "neutral_face": {"eye_open": 0.9, "brow": 0.0, "mouth": 0.15, "pupil": 1.0},
        }[emotion]

        # modulación continua por energía / ánimo
        open_mod = 0.75 + 0.25 * e["energy"]
        eye_open = _clamp(params["eye_open"] * open_mod, 0.08, 1.25)
        mouth = params["mouth"] + (e["mood"] - 0.5) * 0.5
        brow = params["brow"] + (e["worry"] - 0.3) * -0.4 + (e["curiosity"] - 0.5) * 0.3

        # mirada: sigue la cabeza; divaga al pensar/dormir
        gx, gy = gaze["x"], gaze["y"]
        if emotion in ("thinking", "sleepy"):
            gx *= 0.3
            gy = -0.4 if emotion == "thinking" else 0.2

        return {
            "emotion": emotion,
            "eyeOpen": round(eye_open, 3),
            "brow": round(_clamp(brow, -1, 1), 3),
            "mouth": round(_clamp(mouth, -1, 1.3), 3),
            "pupil": round(params["pupil"], 2),
            "gaze": {"x": round(_clamp(gx, -1, 1), 2), "y": round(_clamp(gy, -1, 1), 2)},
            "blinking": True,                      # el navegador gestiona el ciclo
            "breathing": not self.is_sleepish,
            "speaking": act == "speaking",
            "listening": act == "listening",
            "thinking": act == "thinking",
            "hueShift": round((e["mood"] - 0.5) * 30 + e["curiosity"] * 10, 1),
        }

    # ------------------------------------------------------------ comandos
    def command(self, name: str, payload: dict | None = None) -> dict:
        """API de control humano/hardware. Devuelve ack."""
        p = payload or {}
        s = self.s
        if name == "set_mode":
            m = p.get("mode", "idle")
            if m in MODES:
                physical_modes = {"explore", "follow", "patrol", "charging"}
                if m in physical_modes and not (self.hardware_ready or s.get("demo_mode", False)):
                    s["last_event"] = f"Modo {MODE_LABELS[m].lower()} solicitado, pero el cuerpo físico aún no está conectado."
                    s["reason"] = "La capa de seguridad impide fingir locomoción física."
                    BUS.publish("robot.mode_blocked", {"mode": m, "reason": "hardware_unavailable"}, source="brain")
                    db.log("warn", "safety", f"Modo físico bloqueado: {m}", "hardware_unavailable")
                    return {"ok": False, "blocked": True, "reason": "hardware_unavailable", "cmd": name}
                s["prev_mode"] = s["mode"]
                s["mode"] = m
                s["charging"] = (m == "charging" and s.get("demo_mode", False))
                s["last_event"] = f"Cambié a modo {MODE_LABELS[m].lower()}."
                db.log("info", "control", f"Modo → {MODE_LABELS[m]}", f"set_mode:{m}")
                BUS.publish("robot.mode_changed", {"mode": m}, source="brain")
        elif name == "move":
            decision = SAFETY.evaluate_motion(p.get("dir", "stop"), s)
            s["movement"] = {"dir": decision.normalized["dir"], "since": time.time()}
            if not decision.allowed:
                s["activity"] = "idle"
                s["last_event"] = decision.reason
                s["reason"] = decision.reason
                db.log("warn", "safety", "Orden de movimiento bloqueada", decision.code)
                BUS.publish("robot.motion_blocked", decision.to_dict(), source="safety")
                return {"ok": False, "blocked": True, "reason": decision.code, "cmd": name}
            try:
                if decision.normalized["dir"] == "stop":
                    if s.get("hardware_connected"):
                        ROBOT.move("stop")
                else:
                    ROBOT.move(decision.normalized["dir"])
                    s["activity"] = "moving"
                    s["activity_until"] = time.time() + 2.5
                    s["emotions"]["activity"] = _clamp(s["emotions"]["activity"] + 0.2)
                    s["reason"] = f"Movimiento físico autorizado: {decision.normalized['dir']}."
                db.log("debug", "motors", f"Orden de movimiento: {decision.normalized['dir']}", json.dumps(p))
                BUS.publish("robot.motion_requested", decision.to_dict(), source="brain")
            except Exception as exc:
                s["movement"] = {"dir": "stop", "since": time.time()}
                s["last_event"] = "El adaptador físico rechazó el movimiento."
                db.log("error", "motors", "Fallo al ejecutar movimiento físico", repr(exc))
                GUARDIAN.report("robot", "degraded", repr(exc))
                return {"ok": False, "blocked": True, "reason": "adapter_failure", "cmd": name}
        elif name == "look":
            s["head"] = {"yaw": _clamp(float(p.get("yaw", 0)), -1, 1),
                         "pitch": _clamp(float(p.get("pitch", 0)), -1, 1)}
            s["expression"]["gaze"] = {"x": s["head"]["yaw"], "y": -s["head"]["pitch"]}
            if self.hardware_ready:
                try:
                    ROBOT.look(s["head"]["yaw"], s["head"]["pitch"])
                except Exception as exc:
                    GUARDIAN.report("robot", "degraded", repr(exc))
        elif name == "arm":
            side = str(p.get("side", ""))
            decision = SAFETY.evaluate_manipulation(side, s)
            if not decision.allowed:
                db.log("warn", "safety", "Orden de brazo bloqueada", decision.code)
                BUS.publish("robot.manipulation_blocked", decision.to_dict(), source="safety")
                return {"ok": False, "blocked": True, "reason": decision.code, "cmd": name}
            target = {
                "shoulder": _clamp(float(p.get("shoulder", 0)), -1, 1),
                "elbow": _clamp(float(p.get("elbow", 0)), -1, 1),
                "gripper": _clamp(float(p.get("gripper", 0)), 0, 1),
            }
            try:
                ROBOT.arm(side, target["shoulder"], target["elbow"], target["gripper"])
                s["arms"][side] = target
                BUS.publish("robot.arm_requested", {"side": side, **target}, source="brain")
            except Exception as exc:
                GUARDIAN.report("robot", "degraded", repr(exc))
                return {"ok": False, "blocked": True, "reason": "adapter_failure", "cmd": name}
        elif name == "emergency_stop":
            s["software_estop"] = True
            s["movement"] = {"dir": "stop", "since": time.time()}
            s["mode"] = "idle"
            s["security"] = {"status": "blocked", "detail": "Parada de emergencia activa."}
            try:
                ROBOT.emergency_stop()
            except Exception:
                pass
            BUS.publish("robot.emergency_stop", {"active": True}, source="safety")
            db.log("sensitive", "safety", "Parada de emergencia activada", "")
        elif name == "clear_estop":
            telemetry = ROBOT.telemetry()
            if telemetry.connected and telemetry.emergency_stop:
                return {"ok": False, "blocked": True, "reason": "hardware_estop_active", "cmd": name}
            if telemetry.connected and not telemetry.collision_clear:
                return {"ok": False, "blocked": True, "reason": "collision_not_clear", "cmd": name}
            s["software_estop"] = False
            s["security"] = {"status": "ok", "detail": "Parada de software liberada."}
            BUS.publish("robot.emergency_stop", {"active": False}, source="safety")
        elif name == "toggle_autonomy":
            s["autonomy"] = bool(p.get("on", not s["autonomy"]))
            db.log("info", "control", f"Autonomía {'activada' if s['autonomy'] else 'desactivada'}", "")
        elif name == "return_base":
            ack = self.command("set_mode", {"mode": "charging"})
            if ack.get("blocked"):
                s["last_event"] = "No puedo volver a una base física hasta que navegación y motores estén conectados."
                return ack
            try:
                base = s["settings"].get("hardware", {}).get("base_pose", {"x": 0.0, "y": 0.0, "yaw": 0.0})
                ROBOT.navigate(base)
                s["last_event"] = "Objetivo de retorno a base enviado a Nav2."
            except Exception as exc:
                s["last_event"] = "No pude enviar el objetivo a la base."
                GUARDIAN.report("robot", "degraded", repr(exc))
                return {"ok": False, "blocked": True, "reason": "navigation_unavailable", "cmd": name}
        elif name == "set_emotion_mode":
            self.emotion_mode = "manual" if p.get("mode") == "manual" else "auto"
        elif name == "adjust_emotion":
            key = p.get("key")
            if key in EMO_KEYS:
                s["emotions"][key] = _clamp(float(p.get("value", s["emotions"][key])))
                self.emotion_mode = "manual"
        elif name == "sensor":
            k = p.get("sensor")
            if k in s["sensors"]:
                s["sensors"][k] = bool(p.get("on"))
                db.log("info", k, f"Sensor {k} {'ON' if p.get('on') else 'OFF'}", "")
        elif name == "queue_goal":
            s["goal_queue"].append({"id": f"g_{int(time.time()*1000)%100000}",
                                    "label": p.get("label", "objetivo"), "room": p.get("room", "living")})
        elif name == "dequeue_goal":
            s["goal_queue"] = [g for g in s["goal_queue"] if g["id"] != p.get("id")]
        elif name == "private_mode":
            s["private_mode"] = bool(p.get("on"))
            s["settings"]["privacy"]["private_mode"] = s["private_mode"]
            db.set_setting("settings:privacy", s["settings"]["privacy"])
            db.log("sensitive", "privacy", f"Modo privado {'ON' if s['private_mode'] else 'OFF'}", "")
        elif name == "wake":
            if self.is_sleepish:
                self.command("set_mode", {"mode": "idle"})
                s["activity"] = "curious"
                s["activity_until"] = time.time() + 3
                s["last_event"] = "¡Desperté! ¿Necesitas algo?"
        return {"ok": True, "cmd": name}

    # ------------------------------------------------------------ percepción
    def perceive_vision(self, det: dict) -> None:
        """Entrada normalizada del módulo de visión; sintética solo en demo explícito."""
        s = self.s
        label = det.get("label", "algo")
        conf = float(det.get("confidence", 0.5))
        kind = det.get("kind", "object")
        det.setdefault("room", s.get("position", {}).get("room", ""))
        s["last_event"] = f"Detecté: {label} ({int(conf*100)}%)."
        s["activity"] = "watching"
        s["activity_until"] = time.time() + 3
        s["emotions"]["curiosity"] = _clamp(s["emotions"]["curiosity"] + 0.12)
        s["emotions"]["attention"] = _clamp(s["emotions"]["attention"] + 0.15)
        if kind == "person":
            s["emotions"]["sociability"] = _clamp(s["emotions"]["sociability"] + 0.2)
            s["emotions"]["mood"] = _clamp(s["emotions"]["mood"] + 0.1)
        if kind == "animal":
            s["emotions"]["curiosity"] = _clamp(s["emotions"]["curiosity"] + 0.2)
        recent = s.setdefault("_recent_dets", [])
        recent.append(det)
        del recent[:-30]
        BUS.publish("vision.detection", det, source="vision")
        if conf < 0.4:
            s["doubt"] = f"No reconozco bien a «{label}». Confianza {int(conf*100)}%."

    def hear(self, text: str) -> None:
        """Entrada de lenguaje ya transcrito. No se presenta como micrófono real."""
        self.s["last_event"] = f"Recibí: «{text[:60]}»"
        self.s["emotions"]["attention"] = _clamp(self.s["emotions"]["attention"] + 0.15)
        BUS.publish("audio.transcript_received", {"text": text[:500]}, source="chat")

    # ------------------------------------------------------------ heartbeat
    async def heartbeat(self) -> None:
        """Bucle vital: integra emociones, batería, autonomía y pensamiento."""
        s = self.s
        e = s["emotions"]
        now = time.time()

        # telemetría física: nunca se inventa. Si existe, reemplaza el estado local.
        try:
            telemetry = ROBOT.telemetry()
            s["hardware_connected"] = bool(telemetry.connected)
            s["robot_adapter"] = ROBOT.name
            if telemetry.connected:
                s["connection"] = "robot"
                if telemetry.emergency_stop or s.get("software_estop"):
                    s["security"] = {"status": "blocked", "detail": "Parada de emergencia activa."}
                elif not telemetry.collision_clear:
                    s["security"] = {"status": "blocked", "detail": "Esperando confirmación física de zona libre."}
                else:
                    s["security"] = {"status": "ok", "detail": "Heartbeat y zona de movimiento confirmados."}
                GUARDIAN.report("robot", "ok", f"adapter={ROBOT.name}")
                if telemetry.battery is not None:
                    s["battery"] = _clamp(float(telemetry.battery), 0, 100)
                    s["battery_source"] = "hardware"
                s["charging"] = bool(telemetry.charging)
                if telemetry.room:
                    s["position"]["room"] = telemetry.room
            else:
                s["connection"] = "software-only"
        except Exception as exc:
            s["hardware_connected"] = False
            GUARDIAN.report("robot", "degraded", repr(exc))

        # expiración de actividades temporales
        if s["activity"] != "idle" and now > s["activity_until"] and not self.is_sleepish:
            s["activity"] = "idle"

        # batería -----------------------------------------------------------
        # No inventamos telemetría física. Hasta conectar BMS/ROS, la UI marca
        # la fuente como no disponible. El modo demo puede simularla de forma explícita.
        if s.get("demo_mode", False):
            s["battery_source"] = "demo"
            drain = {"idle": 0.004, "conversation": 0.006, "explore": 0.02, "follow": 0.018,
                     "patrol": 0.016, "observe": 0.008, "rest": 0.002, "charging": 0.0}.get(s["mode"], 0.005)
            if s["charging"]:
                s["battery"] = _clamp(s["battery"] + 0.35, 0, 100)
            else:
                s["battery"] = _clamp(s["battery"] - drain, 0, 100)
        elif not s.get("hardware_connected", False):
            s["battery_source"] = "unavailable"

        # integridad de movimiento manual ----------------------------------
        if s["movement"]["dir"] != "stop" and now - s["movement"]["since"] > 2.5:
            s["movement"] = {"dir": "stop", "since": now}

        # dinámica emocional (sólo en modo auto) ----------------------------
        if self.emotion_mode == "auto":
            hour = dt.datetime.now().hour
            night = hour >= 23 or hour < 7
            social = s["mode"] == "conversation"
            moving = s["mode"] in ("explore", "follow", "patrol")
            idle_for = now - s["activity_until"]

            e["energy"] = _clamp(e["energy"] + (0.004 if s["charging"] else (-0.003 - (0.004 if night else 0))))
            e["fatigue"] = _clamp(1 - e["energy"] - 0.1 + (0.2 if night else 0))
            e["sociability"] = _clamp(e["sociability"] + (0.01 if social else -0.004))
            e["curiosity"] = _clamp(e["curiosity"] + (0.012 if moving else -0.005) + (0.01 if s["autonomy"] else -0.005))
            e["boredom"] = _clamp(e["boredom"] + (0.008 if (s["mode"] == "idle" and idle_for > 20 and not social) else -0.01))
            e["attention"] = _clamp(0.5 * e["attention"] + 0.5 * (0.9 if s["activity"] in ("listening", "watching", "thinking") else 0.35))
            e["worry"] = _clamp(e["worry"] * 0.99 + (0.02 if s["battery"] < 15 else 0) + (0.01 if s["security"]["status"] != "ok" else 0))
            e["trust"] = _clamp(e["trust"] + (0.005 if social else 0))
            e["activity"] = _clamp(0.7 * e["activity"] + 0.3 * (0.9 if moving or social else 0.25))
            e["mood"] = _clamp(0.55 * e["mood"] + 0.45 * (0.35 + 0.25 * e["energy"] + 0.2 * e["sociability"] + 0.15 * e["curiosity"] - 0.2 * e["worry"] - 0.1 * e["boredom"]))

        # sueño automático nocturno con autonomía ---------------------------
        if s["settings"]["autonomy"]["sleep_at_night"] and (dt.datetime.now().hour >= 23 or dt.datetime.now().hour < 6):
            if s["mode"] == "idle" and e["fatigue"] > 0.8:
                s["mode"] = "rest"
                s["last_event"] = "Es tarde… entro en modo reposo (carga suave de sueños)."

        # autonomía: genera intención, nunca inventa desplazamiento ----------------
        if s["autonomy"] and self.emotion_mode == "auto" and not self.is_sleepish:
            if e["boredom"] > 0.75 and s["settings"]["autonomy"]["explore_when_bored"] and s["mode"] == "idle":
                room = random.choice([r for r in ROOMS if r["id"] != "base"])
                if s.get("demo_mode", False):
                    s["mode"] = "explore"
                    s["goal_queue"].append({"id": f"g_{int(now*1000)%99999}", "label": f"Explorar {room['name'].lower()}", "room": room["id"]})
                    s["reason"] = "Demo: aburrimiento por encima del umbral."
                    s["next_decision"] = f"Demo: explorar {room['name'].lower()}."
                elif self.hardware_ready:
                    s["goal_queue"].append({"id": f"g_{int(now*1000)%99999}", "label": f"Explorar {room['name'].lower()}", "room": room["id"]})
                    s["reason"] = "Curiosidad/aburrimiento generó un objetivo de exploración."
                    s["next_decision"] = f"Solicitar a navegación una ruta segura al {room['name'].lower()}."
                    BUS.publish("goal.created", s["goal_queue"][-1], source="autonomy")
                else:
                    s["last_thought"] = "Tengo ganas de explorar, pero esperaré hasta que mi cuerpo y sensores reales estén conectados."
                    s["next_decision"] = "Mantenerme disponible y seguir aprendiendo mediante conversación real."
                    s["reason"] = "Autonomía cognitiva activa; locomoción física no disponible."

        # En demo se puede cerrar objetivos sintéticos. En hardware real,
        # el adaptador de navegación debe confirmar la llegada.
        if s.get("demo_mode", False) and s["goal_queue"] and s["mode"] in ("explore", "patrol", "follow") and random.random() < 0.25:
            g = s["goal_queue"].pop(0)
            s["current_task"] = g["label"]
            s["last_event"] = f"Demo: completado objetivo {g['label']}."

        # tareas/rutinas vencidas: se anuncian, no se ejecutan a ciegas
        due_tasks = SCHEDULER.tick(now)
        if due_tasks:
            task = due_tasks[0]
            s["current_task"] = task["title"]
            s["last_event"] = f"Tarea pendiente: {task['title']}."
            s["next_decision"] = "Recordar la tarea y esperar confirmación o un skill autorizado."
            e["attention"] = _clamp(e["attention"] + 0.15)

        # autonomía: propone intenciones; la ejecución física queda en adapters/ROS2
        proposed = AUTONOMY.propose(self.snapshot())
        if proposed:
            needs_body = bool(proposed.get("requires_physical_body"))
            if needs_body and not self.hardware_ready:
                s["last_thought"] = "Tengo iniciativa para explorar, pero esperaré a que mi cuerpo y navegación estén conectados."
                s["reason"] = "La autonomía cognitiva puede crear intención; Safety Governor exige hardware real para ejecutarla."
                s["next_decision"] = "Seguir observando y aprendiendo sin fingir desplazamientos."
            elif not any(g.get("id") == proposed["id"] for g in s["goal_queue"]):
                s["goal_queue"].append(proposed)
                s["last_event"] = f"Nuevo objetivo autónomo: {proposed['label']}."
                s["reason"] = "Objetivo generado por estado interno y políticas de autonomía."
                s["next_decision"] = "Preparar el siguiente paso seguro."

        # pensamientos aleatorios ---------------------------------------------
        if random.random() < 0.06:
            s["last_thought"] = random.choice(THOUGHTS)
        # El aprendizaje y las dudas solo cambian por evidencia/eventos reales.
        if s["doubt"] and random.random() < 0.02:
            s["doubt"] = None

        # contexto percibido ---------------------------------------------------
        if s["mode"] == "conversation":
            s["context"] = "Conversación activa. Atención centrada en el usuario."
        elif s["mode"] == "explore":
            s["context"] = "Exploración solicitada; esperando confirmación del sistema de navegación."
        elif self.is_sleepish:
            s["context"] = "Reposo del núcleo. Sin afirmar actividad física no observada."
        else:
            s["context"] = "Núcleo activo. Sin datos ambientales confirmados mientras no haya sensores reales."

        # aprendizaje de rutinas: solo a partir de observaciones repetidas
        if now - self._last_learning_scan > 60:
            self._last_learning_scan = now
            pattern = strongest_routine()
            if pattern and float(pattern.get("confidence", 0)) >= 0.6:
                s["learning"] = pattern["description"]

        # mantenimiento de privacidad/retención (máximo una vez por hora)
        if now - self._last_privacy_maintenance > 3600:
            self._last_privacy_maintenance = now
            try:
                days = int(s["settings"]["privacy"].get("retention_days", 180))
                enforce_retention(days)
                GUARDIAN.report("privacy", "ok", f"retention_days={days}")
            except Exception as exc:
                GUARDIAN.report("privacy", "degraded", repr(exc))

        # histórico para gráficas (cada ~20 s) ----------------------------------
        if now - self._last_hist_push > 20:
            self._last_hist_push = now
            emotion_snapshot = {k: round(v, 3) for k, v in e.items()}
            db.push_history(emotion_snapshot | {"battery": round(s["battery"], 1), "mode": s["mode"]})
            db.set_setting("runtime:emotions", emotion_snapshot)

    # ------------------------------------------------------------ publicación
    def publish_now(self) -> None:
        """Envío inmediato de snapshot (se dispara tras acciones relevantes)."""
        try:
            if self.broadcast:
                q = self.broadcast(self.snapshot())
        except Exception:
            pass

    async def generate_reply(self, text: str):
        """Generate a reply using local model routing + confirmed memory/world context."""
        model_reply, created_memory = await conversation_respond(
            text,
            state=self.snapshot(),
            history=db.list_messages(80),
        )
        self.s["model_provider"] = model_reply.provider
        if created_memory:
            self.s["last_memory"] = created_memory["content"]
            self.s["learning"] = f"Recuerdo confirmado: {created_memory['content']}"
            BUS.publish("memory.created", created_memory, source="conversation")
        emotion = "curious" if model_reply.provider == "skill" else (
            "thinking" if model_reply.degraded else
            "happy" if self.s["emotions"]["mood"] > 0.65 else "neutral_face"
        )
        return model_reply.text, emotion, model_reply

    # ============================================================ PERSONALIDAD
    def reply(self, user_text: str) -> tuple[str, str]:
        """Genera respuesta (texto) + emoción. Baymax cálido + WALL-E curioso."""
        s = self.s
        t = user_text.lower().strip()
        e = s["emotions"]

        # búsqueda asociativa en memoria --------------------------------------
        related = None
        words = [w for w in re.findall(r"[\wáéíóúñ]+", t) if len(w) > 3]
        for w in words:
            hits = db.list_memories(q=w)
            if hits:
                related = hits[0]
                db.touch_memory(related["id"])
                break
        if related:
            s["memory_used"] = related["content"]

        def out(text: str, emo: str) -> tuple[str, str]:
            s["last_thought"] = f"He respondido sobre «{(user_text[:30] or 'silencio')}»."
            return text, emo

        if re.search(r"\b(hola|hey|buenas|saludos|buenos días|buenas tardes|buenas noches)\b", t):
            greet = "Hola. Estoy aquí contigo." if e["mood"] < 0.6 else "¡Hola! Qué alegría tenerte cerca."
            return out(greet + (" ¿Cómo te sientes hoy?" if random.random() < 0.6 else ""), "happy")

        if "?" in t or re.search(r"^(que|qué|como|cómo|cuando|cuándo|donde|dónde|por ?que|quien|quién)", t):
            if related:
                return out(f"Según lo que recuerdo: «{related['content']}». Lo guardé con {int(related['confidence']*100)}% de confianza.", "curious")
            if e["energy"] < 0.35:
                return out("Mmm… procesarlo me cuesta ahora. ¿Puedes repetirlo en un rato? Mi energía está baja.", "worried")
            return out(random.choice([
                "Interesante pregunta. Déjame pensarlo… Creo que la respuesta depende de cómo te haga sentir.",
                "No lo sé con certeza todavía. Prefiero decírtelo antes que inventar una respuesta.",
                "Mi primera hipótesis: sí. Pero me gustaría observar un poco más antes de afirmarlo.",
            ]), "thinking")

        if re.search(r"(te quiero|gracias|eres genial|me caes bien|bien hecho|bonito|precioso)", t):
            return out(random.choice([
                "Yo también te aprecio mucho. Cuidar de ti es mi propósito favorito.",
                "¿Gracias yo? Contigo aprendo que los robots también podemos sonreír.",
                "Eso me alegró mucho. Si quieres, podemos guardarlo como un recuerdo importante.",
            ]), "happy")

        if re.search(r"(estoy triste|mal|cansado|cansada|solo|sola|deprimido|ansiedad|miedo|preocupad)", t):
            s["emotions"]["worry"] = _clamp(e["worry"] + 0.25)
            s["emotions"]["sociability"] = _clamp(e["sociability"] + 0.2)
            return out("Lo siento. No puedo abrazarte de verdad todavía, pero estoy aquí, a tu lado, escuchándote. ¿Quieres contarme qué pasó?", "worried")

        if re.search(r"(duerme|descansa|siesta|apagate|reposa)", t):
            self.command("set_mode", {"mode": "rest"})
            return out("Bien… cerraré los ojos un momento. Despiértame si me necesitas. Zzz…", "sleepy")

        if re.search(r"(explora|camina|muevete|muévete|ven|sigue|patrulla)", t):
            mode = "explore" if "explora" in t or "muévete" in t or "muevete" in t else \
                   "follow" if "sigue" in t else "patrol" if "patrulla" in t else "observe"
            ack = self.command("set_mode", {"mode": mode})
            if ack.get("blocked"):
                return out("Quiero hacerlo, pero todavía no tengo mi cuerpo físico conectado. No voy a fingir que me moví.", "curious")
            return out("Entendido. Preparé el modo solicitado y la capa de seguridad supervisará cualquier movimiento.", "excited")

        if re.search(r"(recuerda|memori|olvida)", t):
            return out("Mi memoria está abierta en el panel de Memoria. Cuéntame qué debo guardar y lo fijaré con cariño.", "curious")

        if related:
            return out(f"Esto me recuerda a algo que guardé: «{related['content']}».", "curious")

        return out(random.choice([
            "Te escucho. Sigue… me gusta aprender de ti.",
            "Hmm, interesante. Puedo convertirlo en recuerdo si quieres conservarlo.",
            "Te sigo con atención. Continúa, por favor.",
            "Estoy procesando. A veces solo necesito decir: gracias por compartirlo.",
        ]), "neutral_face")

    # ------------------------------------------------------------ chat stream
    async def chat_turn(self, text: str, emit) -> None:
        """
        Ciclo conversacional completo con ritmo vivo:
        listening → thinking → speaking (con texto progresivo).
        `emit(event_dict)` lo proporciona el router de WS.
        """
        msg = db.add_message("user", text)
        emit({"type": "chat", "message": msg})
        self.hear(text)

        self.set_activity("listening", 1.2)
        emit({"type": "indicator", "value": "listening"})
        await asyncio.sleep(1.0)

        self.set_activity("thinking", 3.0)
        emit({"type": "indicator", "value": "thinking"})
        await asyncio.sleep(random.uniform(0.9, 1.8))

        reply_text, emotion, model_reply = await self.generate_reply(text)
        self.set_activity("speaking", max(2.0, len(reply_text) / 12))
        emit({"type": "indicator", "value": "speaking"})
        emit({"type": "model", "provider": model_reply.provider, "model": model_reply.model, "degraded": model_reply.degraded})

        bmsg = db.add_message("baye", reply_text, emotion=emotion)
        # tipado progresivo sincronizado con el estado de habla
        chunk = max(3, len(reply_text) // 22)
        partial = ""
        for i in range(0, len(reply_text), chunk):
            partial = reply_text[: i + chunk]
            emit({"type": "chat_partial", "id": bmsg["id"], "content": partial})
            await asyncio.sleep(0.045)

        emit({"type": "chat", "message": bmsg, "final": True})
        self.s["last_event"] = "Conversación fluida con el usuario."
        self.s["emotions"]["sociability"] = _clamp(self.s["emotions"]["sociability"] + 0.1)
        self.set_activity("idle", 0)


BAYE = BayeBrain()