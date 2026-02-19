"""Comms agent - email triage and drafting (Phase 2)."""

from __future__ import annotations

from cos.agents.base import AgentInput, AgentOutput, BaseAgent


class CommsAgent(BaseAgent):
    """Email triage and response drafting. Phase 2."""

    name = "comms"

    async def run(self, input: AgentInput) -> AgentOutput:
        raise NotImplementedError("CommsAgent is Phase 2")
