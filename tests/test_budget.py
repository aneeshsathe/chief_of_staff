"""Tests for budget tracking."""

from __future__ import annotations

from cos.models.budget import UsageTracker, estimate_cost


def test_estimate_cost_sonnet():
    cost = estimate_cost("claude-sonnet-4-6", 1000, 500)
    expected = (1000 / 1_000_000) * 3.0 + (500 / 1_000_000) * 15.0
    assert abs(cost - expected) < 1e-10


def test_estimate_cost_haiku():
    cost = estimate_cost("claude-haiku-4-5", 1000, 500)
    expected = (1000 / 1_000_000) * 0.80 + (500 / 1_000_000) * 4.0
    assert abs(cost - expected) < 1e-10


def test_usage_tracker():
    tracker = UsageTracker()
    tracker.record("claude-sonnet-4-6", 1000, 500)
    tracker.record("claude-haiku-4-5", 2000, 300)

    assert len(tracker.entries) == 2
    assert tracker.total_input_tokens == 3000
    assert tracker.total_output_tokens == 800
    assert tracker.total_cost > 0

    summary = tracker.summary()
    assert summary["calls"] == 2
