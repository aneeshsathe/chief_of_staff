"""Tests for LLMResponse dataclass, estimate_cost, and UsageTracker."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cos.models.budget import MODEL_COSTS, UsageTracker, estimate_cost
from cos.models.providers import LLMResponse


# ---------------------------------------------------------------------------
# LLMResponse dataclass
# ---------------------------------------------------------------------------


class TestLLMResponse:
    def test_default_values(self) -> None:
        resp = LLMResponse(content="hello")
        assert resp.content == "hello"
        assert resp.input_tokens == 0
        assert resp.output_tokens == 0
        assert resp.model == ""

    def test_all_fields_set(self) -> None:
        resp = LLMResponse(
            content="result",
            input_tokens=500,
            output_tokens=250,
            model="claude-sonnet-4-6",
        )
        assert resp.content == "result"
        assert resp.input_tokens == 500
        assert resp.output_tokens == 250
        assert resp.model == "claude-sonnet-4-6"

    def test_empty_content(self) -> None:
        resp = LLMResponse(content="")
        assert resp.content == ""

    def test_equality(self) -> None:
        r1 = LLMResponse(content="x", input_tokens=1, output_tokens=2, model="m")
        r2 = LLMResponse(content="x", input_tokens=1, output_tokens=2, model="m")
        assert r1 == r2

    def test_inequality(self) -> None:
        r1 = LLMResponse(content="a")
        r2 = LLMResponse(content="b")
        assert r1 != r2


# ---------------------------------------------------------------------------
# estimate_cost
# ---------------------------------------------------------------------------


class TestEstimateCost:
    def test_haiku_pricing(self) -> None:
        cost = estimate_cost("claude-haiku-4-5", 1_000_000, 1_000_000)
        input_rate, output_rate = MODEL_COSTS["claude-haiku-4-5"]
        expected = input_rate + output_rate
        assert abs(cost - expected) < 1e-9

    def test_sonnet_pricing(self) -> None:
        cost = estimate_cost("claude-sonnet-4-6", 1_000_000, 1_000_000)
        input_rate, output_rate = MODEL_COSTS["claude-sonnet-4-6"]
        expected = input_rate + output_rate
        assert abs(cost - expected) < 1e-9

    def test_opus_pricing(self) -> None:
        cost = estimate_cost("claude-opus-4-6", 1_000_000, 1_000_000)
        input_rate, output_rate = MODEL_COSTS["claude-opus-4-6"]
        expected = input_rate + output_rate
        assert abs(cost - expected) < 1e-9

    def test_gemini_flash_pricing(self) -> None:
        cost = estimate_cost("gemini-2.0-flash", 1_000_000, 1_000_000)
        input_rate, output_rate = MODEL_COSTS["gemini-2.0-flash"]
        expected = input_rate + output_rate
        assert abs(cost - expected) < 1e-9

    def test_unknown_model_falls_back_to_sonnet(self) -> None:
        sonnet_cost = estimate_cost("claude-sonnet-4-6", 1000, 500)
        unknown_cost = estimate_cost("some-future-model", 1000, 500)
        assert abs(sonnet_cost - unknown_cost) < 1e-9

    def test_zero_tokens_gives_zero_cost(self) -> None:
        assert estimate_cost("claude-sonnet-4-6", 0, 0) == 0.0

    def test_only_input_tokens(self) -> None:
        cost = estimate_cost("claude-sonnet-4-6", 1_000_000, 0)
        expected = MODEL_COSTS["claude-sonnet-4-6"][0]
        assert abs(cost - expected) < 1e-9

    def test_only_output_tokens(self) -> None:
        cost = estimate_cost("claude-sonnet-4-6", 0, 1_000_000)
        expected = MODEL_COSTS["claude-sonnet-4-6"][1]
        assert abs(cost - expected) < 1e-9

    def test_small_token_counts(self) -> None:
        cost = estimate_cost("claude-haiku-4-5", 100, 50)
        assert cost > 0
        assert cost < 0.01  # Very small cost for 150 tokens

    def test_cost_increases_with_tokens(self) -> None:
        cost_small = estimate_cost("claude-sonnet-4-6", 100, 50)
        cost_large = estimate_cost("claude-sonnet-4-6", 10000, 5000)
        assert cost_large > cost_small

    def test_opus_more_expensive_than_haiku(self) -> None:
        haiku_cost = estimate_cost("claude-haiku-4-5", 1000, 1000)
        opus_cost = estimate_cost("claude-opus-4-6", 1000, 1000)
        assert opus_cost > haiku_cost

    def test_returns_float(self) -> None:
        result = estimate_cost("claude-sonnet-4-6", 1000, 500)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# UsageTracker
# ---------------------------------------------------------------------------


class TestUsageTracker:
    def test_empty_tracker_defaults(self) -> None:
        tracker = UsageTracker()
        assert tracker.entries == []
        assert tracker.total_cost == 0.0
        assert tracker.total_input_tokens == 0
        assert tracker.total_output_tokens == 0

    def test_record_adds_entry(self) -> None:
        tracker = UsageTracker()
        tracker.record("claude-sonnet-4-6", 1000, 500)
        assert len(tracker.entries) == 1

    def test_record_returns_cost(self) -> None:
        tracker = UsageTracker()
        cost = tracker.record("claude-sonnet-4-6", 1000, 500)
        expected = estimate_cost("claude-sonnet-4-6", 1000, 500)
        assert abs(cost - expected) < 1e-12

    def test_multiple_records_accumulate(self) -> None:
        tracker = UsageTracker()
        tracker.record("claude-sonnet-4-6", 1000, 500)
        tracker.record("claude-haiku-4-5", 2000, 300)
        assert len(tracker.entries) == 2

    def test_total_input_tokens_summed(self) -> None:
        tracker = UsageTracker()
        tracker.record("claude-sonnet-4-6", 1000, 0)
        tracker.record("claude-haiku-4-5", 2000, 0)
        assert tracker.total_input_tokens == 3000

    def test_total_output_tokens_summed(self) -> None:
        tracker = UsageTracker()
        tracker.record("claude-sonnet-4-6", 0, 500)
        tracker.record("claude-haiku-4-5", 0, 300)
        assert tracker.total_output_tokens == 800

    def test_total_cost_is_sum(self) -> None:
        tracker = UsageTracker()
        c1 = tracker.record("claude-sonnet-4-6", 1000, 500)
        c2 = tracker.record("claude-haiku-4-5", 2000, 300)
        assert abs(tracker.total_cost - (c1 + c2)) < 1e-12

    def test_summary_keys(self) -> None:
        tracker = UsageTracker()
        tracker.record("claude-sonnet-4-6", 1000, 500)
        summary = tracker.summary()
        assert "calls" in summary
        assert "total_cost_usd" in summary
        assert "total_input_tokens" in summary
        assert "total_output_tokens" in summary

    def test_summary_calls_count(self) -> None:
        tracker = UsageTracker()
        tracker.record("claude-sonnet-4-6", 1000, 500)
        tracker.record("claude-haiku-4-5", 200, 100)
        summary = tracker.summary()
        assert summary["calls"] == 2

    def test_summary_cost_rounded(self) -> None:
        tracker = UsageTracker()
        tracker.record("claude-sonnet-4-6", 1, 1)
        summary = tracker.summary()
        # Result should be rounded to 6 decimal places
        assert isinstance(summary["total_cost_usd"], float)

    def test_entry_structure(self) -> None:
        tracker = UsageTracker()
        tracker.record("claude-sonnet-4-6", 100, 50)
        entry = tracker.entries[0]
        assert entry["model"] == "claude-sonnet-4-6"
        assert entry["input_tokens"] == 100
        assert entry["output_tokens"] == 50
        assert "cost_usd" in entry

    def test_zero_token_record(self) -> None:
        tracker = UsageTracker()
        cost = tracker.record("claude-sonnet-4-6", 0, 0)
        assert cost == 0.0
        assert tracker.total_cost == 0.0

    def test_summary_on_empty_tracker(self) -> None:
        tracker = UsageTracker()
        summary = tracker.summary()
        assert summary["calls"] == 0
        assert summary["total_cost_usd"] == 0.0
        assert summary["total_input_tokens"] == 0
        assert summary["total_output_tokens"] == 0


# ---------------------------------------------------------------------------
# MODEL_COSTS registry
# ---------------------------------------------------------------------------


class TestModelCosts:
    def test_all_expected_models_present(self) -> None:
        expected = {"claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-6", "gemini-2.0-flash"}
        assert expected.issubset(MODEL_COSTS.keys())

    def test_each_model_has_input_and_output_rate(self) -> None:
        for model, rates in MODEL_COSTS.items():
            assert len(rates) == 2, f"{model} should have (input_rate, output_rate)"
            input_rate, output_rate = rates
            assert input_rate >= 0
            assert output_rate >= 0

    def test_output_more_expensive_than_input(self) -> None:
        for model, (input_rate, output_rate) in MODEL_COSTS.items():
            assert output_rate >= input_rate, (
                f"{model}: output tokens should cost at least as much as input tokens"
            )
