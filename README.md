# BAY-E

BAY-E is a local-first autonomous companion-robot platform. Its interaction
model is inspired by the warmth and care of Baymax, while its future physical
platform is designed around a compact tracked WALL-E-like body.

The project is not a chatbot skin. It separates perception, memory, cognition,
autonomy, deterministic safety and physical robot adapters so BAY-E can evolve
from a desktop companion into a real home robot without replacing its mind.

## What works now

- FastAPI local core + HTML/CSS/JavaScript live console
- animated BAY-E face: blink, gaze, listening, thinking, speaking and emotion
- WebSocket live state/event stream
- persistent SQLite chat, memories, tasks, settings, emotion history and world data
- episodic/semantic/person/object/spatial/routine memory CRUD
- hybrid model router: OpenAI Responses API -> llama.cpp -> Ollama -> deterministic fallback
- memory-aware and world-aware conversation
- dynamic emotional/drives engine with persistence across restarts
- autonomous goal proposals without fake physical execution
- task/routine scheduler
- safe skills and checkpointed workflows
- Event Bus + Guardian health registry
- deterministic Safety Governor between cognition and hardware
- real browser camera capture
- OpenCV face + motion perception
- optional local YOLOv8 ONNX object/animal detection
- persistent semantic World Model and real observation history
- evidence-based routine/pattern discovery
- opt-in local face identity using YuNet + SFace, with explicit consent
- browser wake-word mode in compatible browsers
- Piper TTS and whisper.cpp backend adapters, with browser voice fallback
- health/wellness measurement and trend panel (non-diagnostic)
- optional ROS 2 bridge: cmd_vel, head target, battery, hardware heartbeat, room and Nav2 goal submission
- Mac/Linux and Windows launchers; no Docker required
- automated Python + JavaScript CI

## Truthfulness rule

BAY-E does not claim that it saw, moved, measured, learned or reached a place
unless the corresponding real input or hardware adapter confirms it. Synthetic
behavior exists only behind explicit demo mode.

## Quick start

macOS / Linux:

```bash
bash start.command
```

Windows:

```bat
start.bat
```

Then open http://127.0.0.1:8300.

No model service is required to boot. BAY-E prefers OpenAI when `OPENAI_API_KEY`
is configured server-side, then falls back to llama.cpp, Ollama and finally a
deterministic safe responder.

Never place an API key in browser JavaScript or commit it to Git. Copy
`.env.example` to `.env` and configure `OPENAI_API_KEY` locally.

See [docs/SETUP.md](docs/SETUP.md) for local AI, camera, voice and ROS 2 setup.

## Architecture

```
Chat-first UI / live face
      |
 REST + WebSocket
      |
BAY-E Core
 |-- Companion / emotions / drives
 |-- Cognition / logical agents / model router
 |-- Memory / retrieval
 |-- World Model / learning
 |-- Skills / workflows / scheduler
 |-- Health observation
 |-- Event Bus / Guardian
 |-- Safety Governor
      |
Adapters
 |-- Vision / OpenCV / optional YOLO
 |-- Audio / Piper / whisper.cpp
 |-- Face identity (opt-in)
 |-- ROS 2 / Nav2
      |
future MCU + tracked body + head + arms + sensors
```

## Physical safety

AI/model output never writes motor PWM or servo power directly. Physical motion
requires all of the following:

1. the Motors module enabled,
2. ROS 2 bridge enabled in settings,
3. `BAYE_ROS2_ENABLE=1`,
4. a live `/baye/hardware_alive` heartbeat,
5. Safety Governor approval.

STOP remains admissible even when other control paths fail.

## Health boundary

BAY-E can store measurements and show descriptive trends. It is not a medical
device and does not autonomously diagnose conditions or prescribe medication.
The old open-source Baymax health projects were studied as research references;
their diagnosis/prescription logic was not copied into this system.

## Privacy

- private mode stops browser camera and wake-word listening
- memories can be edited/deleted/exported
- facial identity is opt-in and requires explicit consent
- enrollment photos are not persisted; only local feature vectors are stored
- deleting all memories also removes local facial identity profiles
- runtime databases/captures/backups are excluded from Git

## Open-source research influences

The architecture was informed by public Baymax projects including
The-Semicolons/Baymax, neild0/BayMax, titungpemba/Baymax-AI,
amanunreal/baymax, laofahai/baymax, joehsmash/baymax,
FelixSeptem/baymax and ParsifalC/NetEaseBaymaxDemo.

BAY-E reimplements concepts rather than copying source from repositories without
a clear license. Any source incorporated later from MIT/Apache projects must
retain the applicable notices.

## Development

```bash
python -m unittest discover -s tests -v
node --check static/js/views.js
uvicorn main:app --reload
```

Current development line: **v1.1.0-dev**.