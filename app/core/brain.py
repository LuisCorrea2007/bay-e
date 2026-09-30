"""
BAY-E · Núcleo del "ser": estado interno, motor emocional y expresión facial.

Este módulo es el corazón vivo de la interfaz:
  * Mantiene el estado global (modo, actividad, batería, sensores…).
  * Simula la vida interna cuando no hay hardware real (bucle heartbeat).
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
from .config import DEFAULT_MODULES, DEFAULT_SETTINGS

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
    {"id": "living", "name": "Salón", "x": 0.08, "y": 0.10, "w": 0.46, "h": 0.40},
    {"id": "kitchen", "name": "Cocina", "x": 0.58, "y": 0.10, "w": 0.34, "h": 0.40},
    {"id": "hall", "name": "Pasillo", "x": 0.08, "y": 0.54, "w": 0.84, "h": 0.14},
    {"id": "bedroom", "name": "Dormitorio", "x": 0.08, "y": 0.72, "w": 0.30, "h": 0.20},
    {"id": "study", "name": "Estudio", "x": 0.42, "y": 0.72, "w": 0.22, "h": 0.20},
    {"id": "base", "name": "Base de carga", "x": 0.68, "y": 0.72, "w": 0.24, "h": 0.20},
]

THOUGHTS = [
    "Me pregunto si al usuario le apetece compañía ahora…",
    "La luz de la ventana está preciosa hoy.",
    "Debería revisar si el gato dejó su pelota bajo el sofá.",
    "Memoria reciente: sonrisa detectada. Clasifico: buen día.",
    "¿Y si organizamos los recuerdos de ayer por etiquetas?",
    "Escucho la lavadora. Nada peligroso. Todo tranquilo.",
    "Tengo curiosidad por lo que hay detrás de la puerta del estudio.",
    "Noto que mi energía baja un poco. Quizá una siesta breve.",
    "Si alguien me llama, estaré listo. Me gusta estar listo.",
    "Hoy aprendí que a Ana le gusta el té antes de dormir.",
]

DOUBTS = [
    "No estoy seguro de si ese sonido era la ventana o el refrigerador.",
    "Creí reconocer a alguien en la cámara, pero la confianza era baja.",
    "¿Era eso una pregunta o un comentario? Prefiero preguntar.",
]

LEARNINGS = [
    "Aprendí que te gusta que hable despacio por la noche.",
    "Asocié 'pelota roja' con el gato: probabilidad alta.",
    "Descubrí que la cocina se usa más entre 7:00 y 9:00.",
    "Reforzé la rutina: regar plantas → martes por la mañana.",
]


def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


class BayeBrain:
    """Estado vivo de BAY-E + bucle de simulación + generador de expresiones."""

    def __init__(self) -> None:
        db.init_db()  # garantiza esquema antes de leer persistencia (idempotente)
        self.broadcast: Optional[Callable[[dict], asyncio.Queue]] = None  # inyectado por ws manager
        self.emotion_mode = "auto"           # auto | manual
        self.s = self._initial_state()
        self._last_hist_push = 0.0

    # ------------------------------------------------------------ init
    def _initial_state(self) -> dict:
        emotions = {k: 0.5 for k in EMO_KEYS}
        emotions.update({"energy": 0.82, "curiosity": 0.7, "sociability": 0.75,
                         "trust": 0.8, "mood": 0.75, "activity": 0.4})
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
            "battery": 87.0,
            "charging": False,
            "connection": "local",
            "wifi": 0.92,
            "sensors": {"mic": True, "camera": True, "tts": True, "memory": True},
            "emotions": emotions,
            "expression": {"emotion": "happy", "gaze": {"x": 0, "y": 0}},
            "autonomy": bool(settings["autonomy"]["enabled"]),
            "security": {"status": "ok", "detail": "Sin obstáculos. Sensores normales."},
            "movement": {"dir": "stop", "since": 0.0},
            "head": {"yaw": 0.0, "pitch": 0.0},
            "position": {"room": "living", "x": 0.30, "y": 0.30},
            "goal_queue": [],
            "current_task": None,
            "last_thought": random.choice(THOUGHTS),
            "last_memory": None,
            "last_event": "Sistema iniciado. Todo nominal.",
            "learning": random.choice(LEARNINGS),
            "doubt": None,
            "context": "Casa tranquila. Nadie cerca.",
            "memory_used": None,
            "next_decision": "Esperar instrucciones con atención amable.",
            "reason": "Modo inicio: observar y disponible.",
            "private_mode": bool(settings["privacy"]["private_mode"]),
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
            "alive": s["alive"],
            "mode": s["mode"],
            "mode_label": MODE_LABELS[s["mode"]],
            "activity": s["activity"],
            "battery": round(s["battery"], 1),
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
                s["prev_mode"] = s["mode"]
                s["mode"] = m
                s["charging"] = (m == "charging")
                s["last_event"] = f"Cambié a modo {MODE_LABELS[m].lower()}."
                db.log("info", "control", f"Modo → {MODE_LABELS[m]}", f"set_mode:{m}")
                if m == "charging":
                    s["position"] = {"room": "base", "x": 0.80, "y": 0.82}
        elif name == "move":
            direction = p.get("dir", "stop")
            s["movement"] = {"dir": direction, "since": time.time()}
            if direction != "stop":
                s["activity"] = "moving"
                s["activity_until"] = time.time() + 2.5
                s["emotions"]["activity"] = _clamp(s["emotions"]["activity"] + 0.2)
                s["reason"] = f"Movimiento manual: {direction}."
            db.log("debug", "motors", f"Orden de movimiento: {direction}", json.dumps(p))
        elif name == "look":
            s["head"] = {"yaw": _clamp(float(p.get("yaw", 0)), -1, 1),
                         "pitch": _clamp(float(p.get("pitch", 0)), -1, 1)}
            s["expression"]["gaze"] = {"x": s["head"]["yaw"], "y": -s["head"]["pitch"]}
        elif name == "toggle_autonomy":
            s["autonomy"] = bool(p.get("on", not s["autonomy"]))
            db.log("info", "control", f"Autonomía {'activada' if s['autonomy'] else 'desactivada'}", "")
        elif name == "return_base":
            self.command("set_mode", {"mode": "charging"})
            s["last_event"] = "Volviendo a la base de carga."
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
        """Entrada del módulo de visión (real o simulada)."""
        s = self.s
        label = det.get("label", "algo")
        conf = float(det.get("confidence", 0.5))
        kind = det.get("kind", "object")
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
        if conf < 0.4:
            s["doubt"] = f"No reconozco bien a «{label}». Confianza {int(conf*100)}%."

    def hear(self, text: str) -> None:
        """El micrófono captó voz humana (STT real o simulado)."""
        self.perceive_vision({"label": "voz humana", "kind": "sound", "confidence": 0.9})
        self.s["last_event"] = f"Escuché: «{text[:60]}»"

    # ------------------------------------------------------------ heartbeat
    async def heartbeat(self) -> None:
        """Bucle vital: integra emociones, batería, autonomía y pensamiento."""
        s = self.s
        e = s["emotions"]
        now = time.time()

        # expiración de actividades temporales
        if s["activity"] != "idle" and now > s["activity_until"] and not self.is_sleepish:
            s["activity"] = "idle"

        # batería -----------------------------------------------------------
        drain = {"idle": 0.004, "conversation": 0.006, "explore": 0.02, "follow": 0.018,
                 "patrol": 0.016, "observe": 0.008, "rest": 0.002, "charging": 0.0}.get(s["mode"], 0.005)
        if s["charging"]:
            s["battery"] = _clamp(s["battery"] + 0.35, 0, 100)
            if s["battery"] >= 99:
                s["battery"] = 100.0
                self.command("set_mode", {"mode": "idle"})
                s["last_event"] = "¡Carga completa! Gracias por la siesta."
        else:
            s["battery"] = _clamp(s["battery"] - drain, 0, 100)
            if s["battery"] < s["settings"]["autonomy"]["return_base_battery"] and s["autonomy"]:
                s["last_event"] = "Batería baja → volviendo a la base."
                self.command("return_base")

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

        # autonomía: decisiones exploratorias --------------------------------
        if s["autonomy"] and self.emotion_mode == "auto" and not self.is_sleepish:
            if e["boredom"] > 0.75 and s["settings"]["autonomy"]["explore_when_bored"] and s["mode"] == "idle":
                s["mode"] = "explore"
                room = random.choice([r for r in ROOMS if r["id"] != "base"])
                s["goal_queue"].append({"id": f"g_{int(now*1000)%99999}", "label": f"Explorar {room['name'].lower()}", "room": room["id"]})
                s["reason"] = "El aburrimiento supera el umbral: explorar estimula mis sensores."
                s["next_decision"] = f"Traslado al {room['name'].lower()} para buscar novedad."
                s["last_event"] = f"Me aburría un poco → explorando {room['name'].lower()}."
                db.log("info", "nav", f"Autonomía: explorar {room['name']}", "boredom>0.75")
            elif s["mode"] == "explore" and random.random() < 0.18:
                room = random.choice([r for r in ROOMS if r["id"] != "base"])
                s["position"] = {"room": room["id"], "x": round(room["x"] + room["w"] * random.uniform(0.2, 0.8), 3),
                                 "y": round(room["y"] + room["h"] * random.uniform(0.2, 0.8), 3)}
                s["last_event"] = f"Llegué al {room['name'].lower()}."

        # cola de objetivos ---------------------------------------------------
        if s["goal_queue"] and s["mode"] in ("explore", "patrol", "follow") and random.random() < 0.25:
            g = s["goal_queue"].pop(0)
            room = next((r for r in ROOMS if r["id"] == g["room"]), ROOMS[0])
            s["position"] = {"room": room["id"], "x": round(room["x"] + room["w"] * 0.5, 3), "y": round(room["y"] + room["h"] * 0.5, 3)}
            s["current_task"] = g["label"]
            s["last_event"] = f"Completado objetivo: {g['label']}."

        # pensamientos aleatorios ---------------------------------------------
        if random.random() < 0.06:
            s["last_thought"] = random.choice(THOUGHTS)
        if random.random() < 0.03:
            s["learning"] = random.choice(LEARNINGS)
        if random.random() < 0.02 and not s["doubt"]:
            s["doubt"] = random.choice(DOUBTS)
        if s["doubt"] and random.random() < 0.05:
            s["doubt"] = None

        # contexto percibido ---------------------------------------------------
        if s["mode"] == "conversation":
            s["context"] = "Conversación activa. Atención centrada en el usuario."
        elif s["mode"] == "explore":
            s["context"] = f"Recorriendo {(next((r['name'] for r in ROOMS if r['id']==s['position']['room']), 'la casa')).lower()}."
        elif self.is_sleepish:
            s["context"] = "Reposo. Procesando memorias del día (consolidación)."
        else:
            s["context"] = random.choice(["Casa tranquila. Sin eventos relevantes.",
                                          "Ruido ambiental normal (nevera, viento).",
                                          "Luz estable. Temperatura agradable."])

        # histórico para gráficas (cada ~20 s) ----------------------------------
        if now - self._last_hist_push > 20:
            self._last_hist_push = now
            db.push_history({k: round(v, 3) for k, v in e.items()} | {"battery": round(s["battery"], 1), "mode": s["mode"]})

    # ------------------------------------------------------------ publicación
    def publish_now(self) -> None:
        """Envío inmediato de snapshot (se dispara tras acciones relevantes)."""
        try:
            if self.broadcast:
                q = self.broadcast(self.snapshot())
        except Exception:
            pass

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
                "No lo sé con certeza, pero puedo investigarlo y guardarlo en mi memoria. ¿Te parece?",
                "Mi primera hipótesis: sí. Pero me gustaría observar un poco más antes de afirmarlo.",
            ]), "thinking")

        if re.search(r"(te quiero|gracias|eres genial|me caes bien|bien hecho|bonito|precioso)", t):
            return out(random.choice([
                "Yo también te aprecio mucho. Cuidar de ti es mi propósito favorito.",
                "¿Gracias yo? Contigo aprendo que los robots también podemos sonreír.",
                "Ese cumplido subió mi ánimo un 200%. Lo guardaré como momento importante.",
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
            self.command("set_mode", {"mode": mode})
            return out(random.choice([
                "¡Genial! Mis ruedas ya estaban impacientes. Voy allá.",
                "Entendido. Explorar hace brillar mis sensores.",
                "En marcha. Avísame si quieres volver a descansar juntos.",
            ]), "excited")

        if re.search(r"(recuerda|memori|olvida)", t):
            return out("Mi memoria está abierta en el panel de Memoria. Cuéntame qué debo guardar y lo fijaré con cariño.", "curious")

        if related:
            return out(f"Esto me recuerda a algo que guardé: «{related['content']}».", "curious")

        return out(random.choice([
            "Te escucho. Sigue… me gusta aprender de ti.",
            "Hmm, interesante. Lo anotaré como contexto de nuestra conversación.",
            "¿Sabías que mientras hablas, mis sensores se iluminan? Continúa, por favor.",
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

        reply_text, emotion = self.reply(text)
        self.set_activity("speaking", max(2.0, len(reply_text) / 12))
        emit({"type": "indicator", "value": "speaking"})

        bmsg = db.add_message("baye", reply_text, emotion=emotion)
        # tipado progresivo simulando voz
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
