"""Judge agent - multi-agent synthesis (Phase 2)."""

from __future__ import annotations

from cos.agents.base import AgentInput, AgentOutput, BaseAgent


class JudgeAgent(BaseAgent):
    """Synthesizes output from multiple worker agents. Phase 2."""

    name = "judge"

    async def run(self, input: AgentInput) -> AgentOutput:
        raise NotImplementedError("JudgeAgent is Phase 2")
