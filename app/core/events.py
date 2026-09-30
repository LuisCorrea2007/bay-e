"""BAY-E event bus.

A small in-process event contract used to decouple perception, cognition,
companion state, safety and future robotics adapters.  It deliberately has
no dependency on FastAPI, ROS 2 or a model provider.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
import time
from threading import RLock
from typing import Any, Callable


@dataclass(slots=True)
class Event:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = "core"
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EventBus:
    """Synchronous, bounded event bus for local core coordination.

    Subscribers must be fast and side-effect aware. Slow/network consumers
    should enqueue the event and return immediately.
    """

    def __init__(self, history_size: int = 500) -> None:
        self._subs: dict[str, list[Callable[[Event], None]]] = {}
        self._history: deque[Event] = deque(maxlen=max(10, history_size))
        self._lock = RLock()

    def subscribe(self, event_type: str, callback: Callable[[Event], None]) -> Callable[[], None]:
        with self._lock:
            self._subs.setdefault(event_type, []).append(callback)

        def unsubscribe() -> None:
            with self._lock:
                callbacks = self._subs.get(event_type, [])
                if callback in callbacks:
                    callbacks.remove(callback)

        return unsubscribe

    def publish(self, event_type: str, payload: dict[str, Any] | None = None, *, source: str = "core") -> Event:
        event = Event(type=event_type, payload=payload or {}, source=source)
        with self._lock:
            self._history.append(event)
            callbacks = list(self._subs.get(event_type, ())) + list(self._subs.get("*", ()))
        for callback in callbacks:
            try:
                callback(event)
            except Exception:
                # A faulty observer must never stop the robot core.
                continue
        return event

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in list(self._history)[-max(1, limit):]]


BUS = EventBus()
