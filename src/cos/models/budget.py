"""Token tracking and cost estimation."""

from __future__ import annotations

from dataclasses import dataclass, field

# Approximate costs per 1M tokens (USD)
MODEL_COSTS: dict[str, tuple[float, float]] = {
    # (input_cost_per_1M, output_cost_per_1M)
    "claude-haiku-4-5": (0.80, 4.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-6": (15.00, 75.00),
    "gemini-2.0-flash": (0.10, 0.40),
}


@dataclass
class UsageTracker:
    """Track token usage and costs across a session."""

    entries: list[dict] = field(default_factory=list)

    def record(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Record usage and return estimated cost."""
        cost = estimate_cost(model, input_tokens, output_tokens)
        self.entries.append(
            {
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost,
            }
        )
        return cost

    @property
    def total_cost(self) -> float:
        return sum(e["cost_usd"] for e in self.entries)

    @property
    def total_input_tokens(self) -> int:
        return sum(e["input_tokens"] for e in self.entries)

    @property
    def total_output_tokens(self) -> int:
        return sum(e["output_tokens"] for e in self.entries)

    def summary(self) -> dict:
        return {
            "total_cost_usd": round(self.total_cost, 6),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "calls": len(self.entries),
        }


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a model call."""
    costs = MODEL_COSTS.get(model, (3.0, 15.0))  # Default to Sonnet pricing
    input_cost = (input_tokens / 1_000_000) * costs[0]
    output_cost = (output_tokens / 1_000_000) * costs[1]
    return input_cost + output_cost
