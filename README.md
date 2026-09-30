# BAY-E

BAY-E is a local-first autonomous companion-robot platform. Its interaction
model is inspired by the warmth and care of Baymax, while its future physical
platform is designed around a compact tracked WALL-E-like body.

The project is not a chatbot skin. It separates perception, memory, cognition,
autonomy, deterministic safety and physical robot adapters so BAY-E can evolve
from a desktop companion into a real home robot without replacing its mind.

## What works now

- FastAPI local core + HTML/CSS/JavaScript live console
- definitive minimal BAY-E face (`●────●`): procedural blink, gaze, listening, thinking, speaking-state micro-motion and emotion without a fake mouth
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

## Chat as heart and mind

The local page is now the primary control surface. It supports multiple chats,
renaming/deleting chats, editing/deleting/copying/reading messages, saving a
message as memory, converting messages into tasks, and an editable Mind panel.

Mind entries are structured as restrictions, principles, goals, confirmed
beliefs and notes. They are injected into BAY-E's conversational context. They
do not expose or edit hidden chain-of-thought.

## Voice and hands-free mode

BAY-E 2.3 adds an explicit **manos libres** control next to push-to-talk. It is
off by default and starts only after a user gesture. When enabled, BAY-E listens
for the wake phrase `BAY-E`; saying only the wake phrase opens a short follow-up
window, while saying `BAY-E <comando>` sends the command directly.

The browser client pauses speech recognition while BAY-E is speaking so its own
TTS is not treated as a new command. Private mode immediately disables
hands-free listening. If the browser reports an already-installed on-device
Spanish recognition model, BAY-E prefers it; otherwise the browser may use its
normal recognition service, which can be remote depending on the browser.

BAY-E Mobile 1.2 now tries the Core's Piper TTS endpoint first so the phone can
use the same local voice as the robot. If Piper is unavailable, it falls back to
the device/webview speech synthesizer.

## Companion learning with review

BAY-E 2.2 adds a conservative learning inbox. Simple non-sensitive first-person
preferences and routines can be detected during chat, but they are stored only
as **pending candidates**. They do not become long-term memory until the user
presses **Recordar** in the Aprendizaje panel.

The deterministic extractor intentionally ignores sensitive categories such as
passwords, financial information, precise home-address language, medical
conditions, religion, political preferences and sexual orientation. Approval
creates a normal memory tagged `learned` and `user-approved`; rejection deletes
the proposal from the local review queue and leaves no memory. Editable personality rules remain subordinate to BAY-E's hard safety,
privacy, sensor-truth and physical-action constraints.

## BAY-E Mobile

The `mobile/` app is a Capacitor Android client for the same BAY-E Core. It
can provide, with permission:

- microphone / speech recognition
- camera frames for the real vision pipeline
- battery state
- network status
- accelerometer/motion telemetry
- one-shot geolocation when the user explicitly taps the location button
- haptic feedback

The phone does **not** create a second personality or memory database. It
connects to the same local Core.

Mobile access uses explicit device pairing. Open BAY-E locally at
`http://127.0.0.1:8300`, go to **Dispositivos**, generate a six-digit one-time
code, then enter that code in BAY-E Mobile. The code expires after five minutes.
The Core stores only a SHA-256 hash of the resulting device token; the Android
app stores the token using native secure storage backed by Android Keystore.
A paired phone can be revoked from the same Devices panel.

Camera, heartbeat, mobile chat and one-shot location endpoints require the
paired device token. One-shot location is ephemeral by default and is not added
to long-term memory unless an explicit `remember=true` request is made.

To expose the Core to the phone on your LAN, set:

```env
BAYE_HOST=0.0.0.0
```

Then enter the computer's LAN address in the Android app, for example
`http://192.168.1.20:8300`.

This HTTP LAN mode is for a trusted local network only. Do not expose the raw
FastAPI port directly to the public Internet; remote access should use TLS plus
a private tunnel/VPN or a dedicated authenticated relay.

BAY-E Mobile enforces this boundary in the client: plain `http://` Core URLs
are accepted only for loopback/private-LAN/link-local/`.local` hosts. Public
or remote hosts must use `https://`. Android WebView mixed content is disabled.

Build the mobile app:

```bash
cd mobile
npm install
npm run build
npx cap add android
npx cap sync android
npx cap open android
```

Capacitor 8 requires Node 22+ for development.

## REST API versioning

The stable REST surface is mounted under `/api/v1`. The previous `/api`
paths remain available as a compatibility alias for existing local clients, but
new web/mobile code uses `/api/v1`. WebSocket remains at `/ws`.

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

Current development baseline: **v2.3.1**.

### 2.0 definition of done

BAY-E 2.0 is the stable software baseline for the companion core. “Stable” here
means the local Core boots without robot hardware, chat/memory/tasks/world state
remain persistent, optional AI/audio/vision providers degrade truthfully, the
browser console exposes the operational subsystems, and physical commands remain
behind deterministic safety + live hardware heartbeat. It does **not** claim the
future tracked body, arms, docking or home SLAM are physically complete until
those adapters and sensors report real telemetry.