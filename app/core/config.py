"""
BAY-E · Configuración global del sistema.
Rutas, constantes y valores por defecto.
"""
from pathlib import Path

# ---------------------------------------------------------------- rutas
ROOT_DIR = Path(__file__).resolve().parents[2]          # /workspace
DATA_DIR = ROOT_DIR / "data"                            # datos persistentes
DB_PATH = DATA_DIR / "baye.db"                          # SQLite (memoria)
CAM_DIR = DATA_DIR / "camera"                           # fotogramas de cámara
BACKUP_DIR = DATA_DIR / "backups"                       # backups exportados

for _d in (DATA_DIR, CAM_DIR, BACKUP_DIR):
    _d.mkdir(parents=True, exist_ok=True)

APP_VERSION = "1.1.0-dev"
APP_NAME = "BAY-E"

# Frecuencia del heartbeat del estado interno (segundos).
# El heartbeat NO implica sensores ni movimiento físicos.
HEARTBEAT_INTERVAL = 1.5

# ---------------------------------------------------------------- identidad
DEFAULT_IDENTITY = {
    "name": "BAY-E",
    "species": "Compañero robótico doméstico",
    "birthday": "2026-09-30",
    "voice": "cálida · suave",
    "language": "es",
    "personality": "baymax",           # baymax | walle | personalizado
    "pronoun": "él/ella (neutro: BAY-E)",
}

# ---------------------------------------------------------------- módulos
# Cada módulo tiene un conmutador on/off. Cuando exista hardware real,
# el adaptador correspondiente registrará aquí su estado "online".
DEFAULT_MODULES = [
    {"id": "vision",        "name": "Visión",            "icon": "eye",     "enabled": False, "version": "0.9.4", "desc": "Contrato de visión listo; el adaptador de cámara/modelo real se conecta por separado."},
    {"id": "voice",         "name": "Voz (TTS)",         "icon": "speaker", "enabled": False, "version": "1.2.0", "desc": "Síntesis de voz cálida. Preparado para Piper / XTTS."},
    {"id": "stt",           "name": "Escucha (STT)",     "icon": "mic",     "enabled": False, "version": "0.8.1", "desc": "Reconocimiento de speech. Preparado para Whisper local."},
    {"id": "memory",        "name": "Memoria",           "icon": "brain",   "enabled": True,  "version": "1.1.2", "desc": "Memorias episódicas, semánticas, personas, objetos, espacio y rutinas."},
    {"id": "emotions",      "name": "Emociones",         "icon": "heart",   "enabled": True,  "version": "1.0.0", "desc": "Motor afectivo: energía, curiosidad, ánimo y expresión facial."},
    {"id": "navigation",    "name": "Navegación",        "icon": "compass", "enabled": False, "version": "0.7.3", "desc": "Contrato preparado para ROS 2/Nav2. Desactivado hasta conectar hardware real."},
    {"id": "motors",        "name": "Chasis / Motores",  "icon": "cpu",     "enabled": False, "version": "—",     "desc": "Puente hardware real (ROS 2 / microcontrolador). No se simula movimiento por defecto."},
    {"id": "security",      "name": "Seguridad física",  "icon": "shield",  "enabled": True,  "version": "1.0.1", "desc": "Anti-colisión, pendientes, escaleras y zonas restringidas."},
    {"id": "learning",      "name": "Aprendizaje",       "icon": "sparkle", "enabled": True,  "version": "0.5.0", "desc": "Adaptación de personalidad y preferencias del usuario."},
]

AVAILABLE_VOICES = ["cálida · suave", "juguetona", "serena", "guardián", "piloto"]
AVAILABLE_LANGUAGES = {"es": "Español", "en": "English", "ca": "Català", "fr": "Français"}

# ---------------------------------------------------------------- defaults
DEFAULT_SETTINGS = {
    "system": {"demo_mode": False, "allow_synthetic_events": False},
    "ai": {
        "provider_order": "llama.cpp,ollama",
        "llama_url": "http://127.0.0.1:8080",
        "llama_model": "local",
        "ollama_url": "http://127.0.0.1:11434",
        "ollama_model": "qwen2.5:3b"
    },
    "identity": dict(DEFAULT_IDENTITY),
    "audio": {"tts_enabled": True, "wake_word": "bay-e", "volume": 0.8, "rate": 1.0},
    "vision": {"camera_enabled": True, "fps": 12, "detect_people": True, "detect_animals": True, "save_captures": True},
    "privacy": {"private_mode": False, "retention_days": 180, "restricted_zones": ["Estudio"], "forbidden_objects": ["Documentos personales"]},
    "personality": {"auto_emotions": True, "curiosity_level": 0.7, "affection": 0.9, "humor": 0.5, "handicap_speak": True},
    "autonomy": {"enabled": True, "explore_when_bored": True, "sleep_at_night": True, "return_base_battery": 22.0},
    "hardware": {"ros2_bridge": False, "ros_domain_id": 0, "base_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0, "frame_id": "map"}, "model_paths": {"llm": "~/models/baye-brain.gguf", "vision": "~/models/yolov8n.onnx", "tts": "~/models/es_ES.onnx", "stt": "~/models/ggml-base.bin"}},
    "security": {"max_speed": 0.6, "stairs_allowed": False, "night_patrol": False, "child_lock": False},
}