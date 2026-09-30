"""Task/routine scheduler.

It emits due-task events but never executes arbitrary physical actions by
itself. Execution must be mapped to a registered skill/workflow.
"""
from __future__ import annotations

import time

from app.core import db
from app.core.events import BUS


class Scheduler:
    def __init__(self) -> None:
        self._announced: dict[str, float] = {}

    def tick(self, now: float | None = None) -> list[dict]:
        now = now or time.time()
        due = []
        for task in db.list_tasks():
            scheduled = float(task.get("scheduled_at") or 0)
            if task.get("status") not in ("pending", "running") or not scheduled or scheduled > now:
                continue
            key = f"{task['id']}:{scheduled}"
            if self._announced.get(task["id"]) == scheduled:
                continue
            self._announced[task["id"]] = scheduled
            due.append(task)
            BUS.publish("task.due", task, source="scheduler")
        return due


SCHEDULER = Scheduler()


def next_occurrence(ts: float, repeat: str) -> float:
    if not ts or not repeat:
        return 0.0
    import datetime as dt
    d = dt.datetime.fromtimestamp(ts)
    if repeat == "hourly":
        return (d + dt.timedelta(hours=1)).timestamp()
    if repeat == "daily":
        return (d + dt.timedelta(days=1)).timestamp()
    if repeat == "weekly":
        return (d + dt.timedelta(days=7)).timestamp()
    if repeat == "weekdays":
        n = d + dt.timedelta(days=1)
        while n.weekday() >= 5:
            n += dt.timedelta(days=1)
        return n.timestamp()
    return 0.0
