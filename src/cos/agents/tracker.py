"""Tracker agent - task aggregation (Phase 3)."""

from __future__ import annotations

from cos.agents.base import AgentInput, AgentOutput, BaseAgent


class TrackerAgent(BaseAgent):
    """Aggregates tasks from Asana + GitHub. Phase 3."""

    name = "tracker"

    async def run(self, input: AgentInput) -> AgentOutput:
        raise NotImplementedError("TrackerAgent is Phase 3")
