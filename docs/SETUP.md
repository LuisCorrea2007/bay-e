# BAY-E setup

BAY-E is local-first and does not require Docker.

## Basic UI/core

### macOS / Linux

```bash
bash start.command
```

### Windows

Run `start.bat`.

The launcher creates `.venv`, installs Python requirements and opens
http://127.0.0.1:8300.

## Local brain

BAY-E can use either:

1. a llama.cpp OpenAI-compatible server at `http://127.0.0.1:8080`, or
2. Ollama at `http://127.0.0.1:11434`.

Provider order, URLs and model names can also be edited in **Ajustes > Cerebro IA**.
If neither service is available, BAY-E uses a deterministic fallback instead
of pretending to have generated an intelligent answer.

## Camera

Open **Visión** and press the sensor button. The browser asks for camera
permission and sends downscaled JPEG frames to the local FastAPI process.
OpenCV performs real face/motion analysis. For local object/animal detection,
configure an ONNX detector with `BAYE_VISION_ONNX` and class labels with
`BAYE_VISION_LABELS`.

## Audio

Browser speech input/output works where the browser supports it. For fully
local backend audio, configure whisper.cpp and Piper using the variables in
`.env.example`. The software detects whether they are available.

## Physical robot / ROS 2

The ROS 2 adapter is disabled by default. Enabling it requires:

- `BAYE_ROS2_ENABLE=1`
- **Ajustes > Hardware / ROS 2 > Puente ROS 2** enabled
- the Motors module enabled
- a live `/baye/hardware_alive` Bool heartbeat

Only after all four conditions are true can Safety Governor authorize motion.

Topics currently supported:
- publish `/cmd_vel`
- publish `/baye/head_target`
- subscribe `/battery_state`
- subscribe `/baye/current_room`
- subscribe `/baye/hardware_alive`
- Nav2 action `navigate_to_pose`

## Health boundary

The Health view records measurements and descriptive trends. It is not a
medical device, does not diagnose disease and does not prescribe medication.

## Reconocimiento de personas, opcional

BAY-E no crea perfiles faciales automáticamente. Para esta función configura
modelos locales OpenCV YuNet y SFace con:

- `BAYE_FACE_DETECTOR_ONNX`
- `BAYE_FACE_RECOGNIZER_ONNX`

Luego abre **Visión > Aprender persona**. El enrolamiento exige confirmar
consentimiento explícito. BAY-E procesa el fotograma localmente y persiste el
vector facial y el nombre; no conserva la foto usada para el enrolamiento.

Los perfiles se pueden revisar y borrar desde Visión. El borrado de todas las
memorias y el borrado por persona también eliminan los perfiles biométricos
correspondientes.

## Activación por nombre

En Chat, el botón «BAY-E» activa una escucha continua usando la API de voz del
navegador cuando está disponible. Esta función es voluntaria y se desactiva
automáticamente al activar modo privado.
