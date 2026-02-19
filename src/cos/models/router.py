"""Tiered model routing based on task type."""

from __future__ import annotations

from cos.config.settings import AppConfig, ModelConfig
from cos.models.providers import LLMResponse, call_anthropic, call_google


async def call_model(
    config: ModelConfig,
    *,
    system: str,
    messages: list[dict[str, str]],
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> LLMResponse:
    """Route a call to the appropriate model provider."""
    if config.provider == "google":
        return await call_google(
            model=config.model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    # Default to Anthropic
    return await call_anthropic(
        model=config.model,
        system=system,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )


async def call_worker(
    config: AppConfig, *, system: str, messages: list[dict[str, str]], **kwargs
) -> LLMResponse:
    return await call_model(config.models.worker, system=system, messages=messages, **kwargs)


async def call_router(
    config: AppConfig, *, system: str, messages: list[dict[str, str]], **kwargs
) -> LLMResponse:
    return await call_model(config.models.router, system=system, messages=messages, **kwargs)


async def call_judge(
    config: AppConfig, *, system: str, messages: list[dict[str, str]], **kwargs
) -> LLMResponse:
    return await call_model(config.models.judge, system=system, messages=messages, **kwargs)
