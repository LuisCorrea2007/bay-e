"""BAY-E Guardian: lightweight health/watchdog registry.

This is the Python-side successor to the crash-protection idea explored in
older Baymax projects.  It records module health and exposes deterministic
status; automatic process restarts will live in adapters/services later.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import time
from threading import RLock


@dataclass(slots=True)
class ModuleHealth:
    name: str
    status: str = "unknown"      # unknown | ok | degraded | failed | offline
    detail: str = ""
    updated_at: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class Guardian:
    def __init__(self) -> None:
        self._lock = RLock()
        self._modules: dict[str, ModuleHealth] = {}

    def report(self, name: str, status: str, detail: str = "") -> None:
        with self._lock:
            self._modules[name] = ModuleHealth(
                name=name,
                status=status,
                detail=detail,
                updated_at=time.time(),
            )

    def snapshot(self) -> dict:
        with self._lock:
            items = {k: v.to_dict() for k, v in self._modules.items()}
        overall = "ok"
        if any(v["status"] == "failed" for v in items.values()):
            overall = "failed"
        elif any(v["status"] in ("degraded", "offline") for v in items.values()):
            overall = "degraded"
        return {"overall": overall, "modules": items}


GUARDIAN = Guardian()
