# BAY-E

BAY-E is an autonomous companion-robot project. The current repository contains
the live web console plus the first local Python core. The long-term target is a
warm, persistent companion with a mobile WALL-E-like body, perception, memory,
autonomy and deterministic physical safety.

## Current status

Working now:
- FastAPI web app
- animated live BAY-E face
- WebSocket state stream
- SQLite chat/memory/tasks/settings/logs
- editable emotional state and personality UI
- memory CRUD/import/export
- goal/task/control console
- deterministic Safety Governor foundation
- Guardian health registry
- internal Event Bus

Not real yet:
- camera/object recognition
- microphone STT
- TTS voice
- ROS 2 / Nav2
- motors, arms, head hardware
- physical battery telemetry
- autonomous home navigation
- model/LLM provider integration

**Important:** BAY-E does not claim movement, vision or sensor observations when
those adapters are not connected. Synthetic events are off by default.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Open http://127.0.0.1:8000

## Tests

```bash
python -m unittest discover -s tests -v
```

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Safety / health boundary

AI/model output will never directly control PWM or motor power. Physical actions
must pass through deterministic safety and hardware adapters.

Health capabilities are planned as measurement/trend/alert assistance. BAY-E is
not an autonomous diagnostic or prescription system.
