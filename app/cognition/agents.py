"""Logical multi-agent runtime for BAY-E.

Agents are roles, not necessarily separate LLM processes. This mirrors modern
agent-runtime architecture without wasting memory by launching many models.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True, slots=True)
class AgentSpec:
    id: str
    purpose: str
    authority: str
    can_request_physical_actions: bool = False


AGENTS = {
    "companion": AgentSpec("companion", "Conversation, warmth, continuity and social interaction.", "advisory"),
    "memory": AgentSpec("memory", "Retrieve and consolidate confirmed memories.", "data"),
    "perception": AgentSpec("perception", "Interpret evidence from camera/audio/sensors.", "evidence"),
    "exploration": AgentSpec("exploration", "Propose curiosity-driven exploration goals.", "planner", True),
    "health": AgentSpec("health", "Describe measurements/trends and suggest appropriate escalation.", "advisory"),
    "safety": AgentSpec("safety", "Deterministically approve or block physical actions.", "veto", True),
}


def manifest() -> list[dict[str, Any]]:
    return [asdict(a) for a in AGENTS.values()]


def operational_context(state: dict[str, Any]) -> str:
    active = ", ".join(AGENTS)
    return (
        f"Agentes lógicos activos: {active}. "
        f"Seguridad tiene veto sobre acciones físicas. "
        f"Hardware conectado={state.get('hardware_ready', False)}."
    )
