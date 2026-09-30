"""Optional local YOLOv8 ONNX detector through OpenCV DNN.

The detector is local-only. It auto-reloads when the configured model path
changes in BAY-E settings or environment variables.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.core import db


COCO80 = [
    "person","bicycle","car","motorcycle","airplane","bus","train","truck","boat","traffic light",
    "fire hydrant","stop sign","parking meter","bench","bird","cat","dog","horse","sheep","cow",
    "elephant","bear","zebra","giraffe","backpack","umbrella","handbag","tie","suitcase","frisbee",
    "skis","snowboard","sports ball","kite","baseball bat","baseball glove","skateboard","surfboard",
    "tennis racket","bottle","wine glass","cup","fork","knife","spoon","bowl","banana","apple",
    "sandwich","orange","broccoli","carrot","hot dog","pizza","donut","cake","chair","couch",
    "potted plant","bed","dining table","toilet","tv","laptop","mouse","remote","keyboard","cell phone",
    "microwave","oven","toaster","sink","refrigerator","book","clock","vase","scissors","teddy bear",
    "hair drier","toothbrush"
]
ANIMALS = {"bird","cat","dog","horse","sheep","cow","elephant","bear","zebra","giraffe"}


class ObjectDetector:
    def __init__(self) -> None:
        self.available = False
        self.net = None
        self.labels = COCO80
        self.cv2 = None
        self.np = None
        self._signature = ""
        self._ensure_loaded()

    def _configured_paths(self) -> tuple[Path | None, Path | None]:
        model_raw = os.getenv("BAYE_VISION_ONNX", "")
        if not model_raw:
            try:
                hw = db.get_setting("settings:hardware", {}) or {}
                model_raw = str((hw.get("model_paths") or {}).get("vision") or "")
            except Exception:
                model_raw = ""
        labels_raw = os.getenv("BAYE_VISION_LABELS", "")
        model = Path(os.path.expanduser(model_raw)) if model_raw else None
        labels = Path(os.path.expanduser(labels_raw)) if labels_raw else None
        return model, labels

    def _ensure_loaded(self) -> None:
        model, labels = self._configured_paths()
        sig = f"{model}:{labels}"
        if sig == self._signature:
            return
        self._signature = sig
        self.available = False
        self.net = None
        self.labels = COCO80
        if not model or not model.is_file():
            return
        try:
            import cv2
            import numpy as np
            self.cv2, self.np = cv2, np
            self.net = cv2.dnn.readNetFromONNX(str(model))
            if labels and labels.is_file():
                self.labels = [x.strip() for x in labels.read_text(encoding="utf-8").splitlines() if x.strip()]
            self.available = True
        except Exception:
            self.available = False
            self.net = None

    def detect(self, frame, *, conf_threshold: float = 0.45, iou_threshold: float = 0.45) -> list[dict[str, Any]]:
        self._ensure_loaded()
        if not self.available:
            return []
        cv2, np = self.cv2, self.np
        size = 640
        blob = cv2.dnn.blobFromImage(frame, 1/255.0, (size, size), swapRB=True, crop=False)
        self.net.setInput(blob)
        rows = np.squeeze(self.net.forward())
        if rows.ndim == 1:
            rows = rows[None, :]
        if rows.shape[0] < rows.shape[1] and rows.shape[0] < 200:
            rows = rows.T

        boxes, scores, classes = [], [], []
        for row in rows:
            if len(row) < 6:
                continue
            class_scores = row[4:]
            cls = int(np.argmax(class_scores))
            conf = float(class_scores[cls])
            if conf < conf_threshold:
                continue
            cx, cy, bw, bh = map(float, row[:4])
            x = max(0.0, cx - bw/2)
            y = max(0.0, cy - bh/2)
            boxes.append([int(x), int(y), int(max(1, bw)), int(max(1, bh))])
            scores.append(conf)
            classes.append(cls)

        if not boxes:
            return []
        indices = cv2.dnn.NMSBoxes(boxes, scores, conf_threshold, iou_threshold)
        if len(indices) == 0:
            return []

        detections = []
        for idx in np.array(indices).reshape(-1)[:30]:
            x, y, bw, bh = boxes[int(idx)]
            cls = classes[int(idx)]
            label = self.labels[cls] if cls < len(self.labels) else f"class_{cls}"
            low = label.lower()
            kind = "animal" if low in ANIMALS else "person" if low == "person" else "object"
            detections.append({
                "label": label,
                "kind": kind,
                "confidence": float(scores[int(idx)]),
                "box": {
                    "x": max(0.0, min(1.0, x / size)),
                    "y": max(0.0, min(1.0, y / size)),
                    "w": max(0.0, min(1.0, bw / size)),
                    "h": max(0.0, min(1.0, bh / size)),
                },
                "source": "opencv_dnn_yolov8_onnx",
            })
        return detections


OBJECTS = ObjectDetector()
