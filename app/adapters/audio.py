"""Local voice adapter contracts for whisper.cpp and Piper.

The web UI can use browser speech APIs immediately. This adapter provides the
backend path used later by robot microphones/speakers.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from app.core.guardian import GUARDIAN
from app.core import db


class AudioAdapter:
    def __init__(self) -> None:
        self.whisper_bin = os.getenv("BAYE_WHISPER_BIN", "whisper-cli")
        self.piper_bin = os.getenv("BAYE_PIPER_BIN", "piper")

    def _model_path(self, kind: str, env_name: str, default: str) -> str:
        env = os.getenv(env_name)
        if env:
            return os.path.expanduser(env)
        try:
            hw = db.get_setting("settings:hardware", {}) or {}
            path = (hw.get("model_paths") or {}).get(kind)
            if path:
                return os.path.expanduser(str(path))
        except Exception:
            pass
        return os.path.expanduser(default)

    @property
    def whisper_model(self) -> str:
        return self._model_path("stt", "BAYE_WHISPER_MODEL", "~/models/ggml-base.bin")

    @property
    def piper_model(self) -> str:
        return self._model_path("tts", "BAYE_PIPER_MODEL", "~/models/es_ES.onnx")

    @property
    def stt_available(self) -> bool:
        return bool(shutil.which(self.whisper_bin) and Path(self.whisper_model).exists())

    @property
    def tts_available(self) -> bool:
        return bool(shutil.which(self.piper_bin) and Path(self.piper_model).exists())

    def transcribe_wav(self, wav_path: str) -> str:
        if not self.stt_available:
            raise RuntimeError("whisper.cpp is not configured")
        cmd = [self.whisper_bin, "-m", self.whisper_model, "-f", wav_path, "--no-timestamps", "-otxt"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if proc.returncode:
            raise RuntimeError(proc.stderr.strip() or "whisper.cpp failed")
        txt_path = Path(wav_path + ".txt")
        text = txt_path.read_text(encoding="utf-8").strip() if txt_path.exists() else proc.stdout.strip()
        GUARDIAN.report("stt", "ok", "whisper.cpp")
        return text

    def synthesize_wav(self, text: str) -> bytes:
        if not self.tts_available:
            raise RuntimeError("Piper is not configured")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as out:
            out_path = out.name
        try:
            proc = subprocess.run(
                [self.piper_bin, "--model", self.piper_model, "--output_file", out_path],
                input=text, capture_output=True, text=True, timeout=60,
            )
            if proc.returncode:
                raise RuntimeError(proc.stderr.strip() or "Piper failed")
            GUARDIAN.report("tts", "ok", "piper")
            return Path(out_path).read_bytes()
        finally:
            Path(out_path).unlink(missing_ok=True)


AUDIO = AudioAdapter()