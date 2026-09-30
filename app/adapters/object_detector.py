"""Optional local object detector using an OpenCV DNN YOLO ONNX model.

Configure:
  BAYE_VISION_ONNX=/path/model.onnx
  BAYE_VISION_LABELS=/path/classes.txt

If no model is configured the adapter simply stays offline; face/motion
perception in vision.py still works.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class ObjectDetector:
    def __init__(self) -> None:
        self.available = False
        self.net = None
        self.labels: list[str] = []
        self.cv2 = None
        self.np = None
        model = Path(os.path.expanduser(os.getenv("BAYE_VISION_ONNX", "")))
        labels = Path(os.path.expanduser(os.getenv("BAYE_VISION_LABELS", "")))
        if not model.is_file() or not labels.is_file():
            return
        try:
            import cv2
            import numpy as np
            self.cv2, self.np = cv2, np
            self.net = cv2.dnn.readNetFromONNX(str(model))
            self.labels = [x.strip() for x in labels.read_text(encoding="utf-8").splitlines() if x.strip()]
            self.available = True
        except Exception:
            self.available = False

    def detect(self, frame, *, conf_threshold: float = 0.45) -> list[dict[str, Any]]:
        if not self.available:
            return []
        cv2, np = self.cv2, self.np
        h, w = frame.shape[:2]
        size = 640
        blob = cv2.dnn.blobFromImage(frame, 1/255.0, (size, size), swapRB=True, crop=False)
        self.net.setInput(blob)
        out = self.net.forward()
        rows = np.squeeze(out)
        if rows.ndim == 1:
            rows = rows[None, :]
        # YOLOv8 exports commonly return [84, 8400].
        if rows.shape[0] < rows.shape[1] and rows.shape[0] < 200:
            rows = rows.T
        detections = []
        for row in rows:
            if len(row) < 6:
                continue
            scores = row[4:]
            cls = int(np.argmax(scores))
            conf = float(scores[cls])
            if conf < conf_threshold:
                continue
            cx, cy, bw, bh = map(float, row[:4])
            x = max(0.0, (cx - bw/2) / size)
            y = max(0.0, (cy - bh/2) / size)
            nw = min(1.0 - x, bw / size)
            nh = min(1.0 - y, bh / size)
            label = self.labels[cls] if cls < len(self.labels) else f"class_{cls}"
            kind = "animal" if label.lower() in {"cat","dog","bird","horse","sheep","cow"} else "person" if label.lower()=="person" else "object"
            detections.append({
                "label": label, "kind": kind, "confidence": conf,
                "box": {"x": x, "y": y, "w": nw, "h": nh},
                "source": "opencv_dnn_onnx",
            })
        return detections[:30]


OBJECTS = ObjectDetector()
