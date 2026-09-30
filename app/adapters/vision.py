"""Real image observation adapter using OpenCV when installed."""
from __future__ import annotations

import time
from threading import RLock
from typing import Any

from app.core.events import BUS
from app.core.guardian import GUARDIAN


class VisionAdapter:
    def __init__(self) -> None:
        self._prev_gray = None
        self._lock = RLock()
        self.available = False
        self.cv2 = None
        self.np = None
        self.face_cascade = None
        try:
            import cv2
            import numpy as np
            self.cv2 = cv2
            self.np = np
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            self.available = True
            GUARDIAN.report("vision", "ok", "OpenCV ready")
        except Exception as exc:
            GUARDIAN.report("vision", "offline", repr(exc))

    def observe_jpeg(self, raw: bytes) -> dict[str, Any]:
        if not self.available:
            raise RuntimeError("OpenCV vision adapter is not available")
        cv2, np = self.cv2, self.np
        frame = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("invalid image")
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = float(gray.mean() / 255.0)

        detections: list[dict[str, Any]] = []
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(45, 45))
        for x, y, fw, fh in faces[:5]:
            det = {
                "id": f"face_{int(time.time()*1000)}_{x}",
                "label": "persona",
                "kind": "person",
                "confidence": 0.72,
                "ts": time.time(),
                "box": {"x": x/w, "y": y/h, "w": fw/w, "h": fh/h},
                "source": "opencv_haar",
            }
            detections.append(det)

        motion = 0.0
        with self._lock:
            if self._prev_gray is not None and self._prev_gray.shape == gray.shape:
                diff = cv2.absdiff(self._prev_gray, gray)
                motion = float((diff > 25).mean())
            self._prev_gray = gray

        if motion > 0.06:
            detections.append({
                "id": f"motion_{int(time.time()*1000)}",
                "label": "movimiento",
                "kind": "motion",
                "confidence": min(0.99, 0.45 + motion * 3.0),
                "ts": time.time(),
                "box": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0},
                "source": "opencv_frame_diff",
            })

        event = {
            "ts": time.time(),
            "width": w,
            "height": h,
            "brightness": round(brightness, 3),
            "motion": round(motion, 4),
            "detections": detections,
        }
        BUS.publish("vision.frame_observed", event, source="vision")
        GUARDIAN.report("vision", "ok", f"{w}x{h}; detections={len(detections)}")
        return event


VISION = VisionAdapter()