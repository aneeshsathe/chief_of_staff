"""Scheduler agent - calendar and scheduling (Phase 2)."""

from __future__ import annotations

from cos.agents.base import AgentInput, AgentOutput, BaseAgent


class SchedulerAgent(BaseAgent):
    """Calendar analysis and conflict detection. Phase 2."""

    name = "scheduler"

    async def run(self, input: AgentInput) -> AgentOutput:
        raise NotImplementedError("SchedulerAgent is Phase 2")
