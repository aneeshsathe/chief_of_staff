"""LLM provider wrappers for Anthropic and Google."""

from __future__ import annotations

from dataclasses import dataclass

import anthropic
import structlog

log = structlog.get_logger("models.providers")

_anthropic_client: anthropic.AsyncAnthropic | None = None


def _get_anthropic_client() -> anthropic.AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.AsyncAnthropic()
    return _anthropic_client


@dataclass
class LLMResponse:
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""


async def call_anthropic(
    *,
    model: str,
    system: str,
    messages: list[dict[str, str]],
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> LLMResponse:
    """Call Anthropic API."""
    client = _get_anthropic_client()
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=messages,
    )
    content = ""
    for block in response.content:
        if block.type == "text":
            content += block.text

    return LLMResponse(
        content=content,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        model=model,
    )


async def call_google(
    *,
    model: str,
    system: str,
    messages: list[dict[str, str]],
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> LLMResponse:
    """Call Google Generative AI API."""
    from google import genai

    client = genai.Client()
    # Convert messages to Google format
    contents = []
    for msg in messages:
        contents.append(
            genai.types.Content(
                role="user" if msg["role"] == "user" else "model",
                parts=[genai.types.Part(text=msg["content"])],
            )
        )

    response = await client.aio.models.generate_content(
        model=model,
        contents=contents,
        config=genai.types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=temperature,
        ),
    )

    return LLMResponse(
        content=response.text or "",
        input_tokens=getattr(response.usage_metadata, "prompt_token_count", 0)
        if response.usage_metadata
        else 0,
        output_tokens=getattr(response.usage_metadata, "candidates_token_count", 0)
        if response.usage_metadata
        else 0,
        model=model,
    )
