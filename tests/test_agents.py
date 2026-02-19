"""Tests for agent base classes."""

from __future__ import annotations

import pytest

from cos.agents.base import AgentInput, AgentOutput


def test_agent_input_defaults():
    input = AgentInput()
    assert input.context_name == "default"
    assert input.data == {}
    assert input.query == ""


def test_agent_input_with_data():
    input = AgentInput(
        context_name="day_job",
        data={"emails": [{"subject": "Test"}]},
        query="What's my morning look like?",
    )
    assert input.context_name == "day_job"
    assert len(input.data["emails"]) == 1


def test_agent_output_defaults():
    output = AgentOutput()
    assert output.content == ""
    assert output.cost_usd == 0.0


def test_agent_output_with_data():
    output = AgentOutput(
        content="Your morning briefing...",
        input_tokens=500,
        output_tokens=1000,
        model="claude-sonnet-4-6",
        cost_usd=0.0165,
    )
    assert output.input_tokens == 500
    assert output.model == "claude-sonnet-4-6"
