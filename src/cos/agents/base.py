"""Base agent interface and shared types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class AgentInput(BaseModel):
    """Input to an agent."""

    context_name: str = "default"
    data: dict[str, Any] = Field(default_factory=dict)
    query: str = ""


class AgentOutput(BaseModel):
    """Output from an agent."""

    content: str = ""
    structured: dict[str, Any] = Field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    cost_usd: float = 0.0


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    name: str = "base"

    @abstractmethod
    async def run(self, input: AgentInput) -> AgentOutput:
        """Execute the agent's task."""
        ...
