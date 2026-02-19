"""Router agent - intent classification and fan-out (Phase 2)."""

from __future__ import annotations

from cos.agents.base import AgentInput, AgentOutput, BaseAgent


class RouterAgent(BaseAgent):
    """Classifies intent and fans out to worker agents. Phase 2."""

    name = "router"

    async def run(self, input: AgentInput) -> AgentOutput:
        raise NotImplementedError("RouterAgent is Phase 2")
