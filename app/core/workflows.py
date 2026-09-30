"""Small checkpointed workflow runtime.

Workflows coordinate reusable semantic steps. Physical steps remain adapters
and still pass through SafetyGovernor.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
import time
import uuid
from typing import Any, Callable

from .events import BUS


@dataclass(slots=True)
class WorkflowRun:
    id: str
    name: str
    status: str = "pending"
    step: int = 0
    context: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class WorkflowRuntime:
    def __init__(self) -> None:
        self.definitions: dict[str, list[tuple[str, Callable[[dict], Any]]]] = {}
        self.runs: dict[str, WorkflowRun] = {}

    def register(self, name: str, steps: list[tuple[str, Callable[[dict], Any]]]) -> None:
        self.definitions[name] = steps

    def start(self, name: str, context: dict[str, Any] | None = None) -> dict:
        if name not in self.definitions:
            raise KeyError(name)
        run = WorkflowRun(id="wf_" + uuid.uuid4().hex[:10], name=name, context=context or {})
        self.runs[run.id] = run
        BUS.publish("workflow.started", asdict(run), source="workflow")
        return asdict(run)

    def advance(self, run_id: str) -> dict:
        run = self.runs[run_id]
        steps = self.definitions[run.name]
        if run.step >= len(steps):
            run.status = "done"
            return asdict(run)
        label, fn = steps[run.step]
        run.status = "running"
        try:
            result = fn(run.context)
            run.context[label] = result
            run.step += 1
            run.updated_at = time.time()
            if run.step >= len(steps):
                run.status = "done"
                BUS.publish("workflow.completed", asdict(run), source="workflow")
            else:
                BUS.publish("workflow.checkpoint", asdict(run), source="workflow")
        except Exception as exc:
            run.status = "failed"
            run.error = repr(exc)
            run.updated_at = time.time()
            BUS.publish("workflow.failed", asdict(run), source="workflow")
        return asdict(run)

    def list_runs(self) -> list[dict]:
        return [asdict(r) for r in sorted(self.runs.values(), key=lambda x: x.updated_at, reverse=True)]


WORKFLOWS = WorkflowRuntime()
