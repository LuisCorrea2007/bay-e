"""Opt-in local face identity using OpenCV YuNet + SFace.

No raw enrollment photo is stored. Only the feature vector and profile name
are persisted. Model files must be supplied locally.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any

from app.core import db
from app.core.guardian import GUARDIAN


class FaceIdentity:
    def __init__(self) -> None:
        self.available = False
        self.cv2 = None
        self.np = None
        self.detector = None
        self.recognizer = None
        self._sig = ""
        self._ensure_loaded()

    def _paths(self) -> tuple[Path | None, Path | None]:
        det = os.getenv("BAYE_FACE_DETECTOR_ONNX", "")
        rec = os.getenv("BAYE_FACE_RECOGNIZER_ONNX", "")
        return (
            Path(os.path.expanduser(det)) if det else None,
            Path(os.path.expanduser(rec)) if rec else None,
        )

    def _ensure_loaded(self) -> None:
        det_path, rec_path = self._paths()
        sig = f"{det_path}:{rec_path}"
        if sig == self._sig:
            return
        self._sig = sig
        self.available = False
        if not det_path or not rec_path or not det_path.is_file() or not rec_path.is_file():
            GUARDIAN.report("face_identity", "offline", "YuNet/SFace models not configured")
            return
        try:
            import cv2
            import numpy as np
            self.cv2, self.np = cv2, np
            self.detector = cv2.FaceDetectorYN.create(str(det_path), "", (320, 320), 0.85, 0.3, 5000)
            self.recognizer = cv2.FaceRecognizerSF.create(str(rec_path), "")
            self.available = True
            GUARDIAN.report("face_identity", "ok", "YuNet + SFace")
        except Exception as exc:
            GUARDIAN.report("face_identity", "offline", repr(exc))

    def _decode(self, raw: bytes):
        self._ensure_loaded()
        if not self.available:
            raise RuntimeError("face identity models are not configured")
        frame = self.cv2.imdecode(self.np.frombuffer(raw, dtype=self.np.uint8), self.cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("invalid image")
        return frame

    def _faces(self, frame):
        h, w = frame.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(frame)
        return [] if faces is None else list(faces)

    def _feature(self, frame, face):
        aligned = self.recognizer.alignCrop(frame, face)
        feature = self.recognizer.feature(aligned)
        return feature

    def enroll(self, name: str, raw: bytes, *, consent: bool) -> dict[str, Any]:
        if not consent:
            raise PermissionError("explicit consent is required")
        name = name.strip()
        if not name:
            raise ValueError("name is required")
        frame = self._decode(raw)
        faces = self._faces(frame)
        if len(faces) != 1:
            raise ValueError("enrollment requires exactly one visible face")
        feature = self._feature(frame, faces[0])
        vector = self.np.asarray(feature, dtype="float32").reshape(-1).tolist()
        return db.face_upsert_profile(name=name, embedding=vector, consent_ts=time.time())

    def identify_frame(self, frame) -> list[dict[str, Any]]:
        self._ensure_loaded()
        if not self.available:
            return []
        faces = self._faces(frame)
        profiles = db.face_list_profiles()
        threshold = float(os.getenv("BAYE_FACE_COSINE_THRESHOLD", "0.42"))
        out = []
        h, w = frame.shape[:2]
        for face in faces[:10]:
            feature = self._feature(frame, face)
            best_name, best_score = "", -1.0
            for profile in profiles:
                ref = self.np.asarray(profile["embedding"], dtype="float32").reshape(1, -1)
                score = float(self.recognizer.match(feature, ref, self.cv2.FaceRecognizerSF_FR_COSINE))
                if score > best_score:
                    best_name, best_score = profile["name"], score
            x, y, fw, fh = map(float, face[:4])
            known = bool(best_name and best_score >= threshold)
            out.append({
                "label": best_name if known else "persona desconocida",
                "kind": "person",
                "confidence": min(0.99, max(0.5, best_score if known else 0.55)),
                "identity_score": best_score,
                "identity_known": known,
                "box": {"x": x/w, "y": y/h, "w": fw/w, "h": fh/h},
                "source": "opencv_yunet_sface",
            })
        return out


FACE_IDENTITY = FaceIdentity()
