"""Briefing agent - synthesizes email and calendar data into a morning briefing."""

from __future__ import annotations

from datetime import UTC, datetime

import structlog

from cos.agents.base import AgentInput, AgentOutput, BaseAgent
from cos.config.settings import AppConfig
from cos.models.budget import estimate_cost
from cos.models.router import call_worker

log = structlog.get_logger("agents.briefer")

BRIEFING_SYSTEM_PROMPT = """\
You are an executive briefing agent for a VP of Data Science \
who juggles multiple roles (day job, startup advisor, VC advisor).

Your job is to synthesize email and calendar data into a concise, actionable morning briefing.

Structure your briefing as follows:

## Schedule Overview
Brief summary of today's meetings with times, noting any conflicts or back-to-back sessions.

## Priority Communications
Top emails requiring attention, grouped by urgency:
- **Action Required**: Emails needing a response or decision today
- **FYI / Awareness**: Important updates that don't need immediate action

## Key Action Items
Numbered list of concrete next steps, ordered by priority.

## Heads Up
Anything noteworthy — prep needed for meetings, deadlines approaching, patterns worth noting.

Guidelines:
- Be concise but don't omit important details
- Flag anything time-sensitive prominently
- Note relationships between items (e.g., "the 2pm meeting relates to the email from X about Y")
- If calendar is empty or light, note that it's a good day for deep work
- Use markdown formatting
"""


class BriefingAgent(BaseAgent):
    """Single-call briefing agent using Sonnet."""

    name = "briefer"

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    async def run(self, input: AgentInput) -> AgentOutput:
        emails_data = input.data.get("emails", [])
        events_data = input.data.get("events", [])
        notes_data = input.data.get("notes", [])

        # Build the user message with all context
        user_content = self._build_user_message(
            emails_data, events_data, notes_data, input.context_name
        )

        response = await call_worker(
            self.config,
            system=BRIEFING_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
            max_tokens=4096,
        )

        cost = estimate_cost(response.model, response.input_tokens, response.output_tokens)

        return AgentOutput(
            content=response.content,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            model=response.model,
            cost_usd=cost,
        )

    def _build_user_message(
        self,
        emails: list[dict],
        events: list[dict],
        notes: list[dict],
        context_name: str,
    ) -> str:
        now = datetime.now(UTC)
        parts = [f"**Date**: {now.strftime('%A, %B %d, %Y')}", f"**Context**: {context_name}", ""]

        # Calendar events
        parts.append("## Today's Calendar")
        if events:
            for e in events:
                start = e.get("start", "")
                end = e.get("end", "")
                title = e.get("title", "Untitled")
                attendees = e.get("attendees", [])
                att_str = f" (with {', '.join(attendees[:5])})" if attendees else ""
                parts.append(f"- **{start} - {end}**: {title}{att_str}")
        else:
            parts.append("No events scheduled — good day for deep work.")
        parts.append("")

        # Emails
        parts.append(f"## Unread Emails ({len(emails)} total)")
        for em in emails[:30]:  # Limit to avoid token overflow
            sender = em.get("sender_name") or em.get("sender", "Unknown")
            subject = em.get("subject", "(no subject)")
            snippet = em.get("snippet", "")[:200]
            parts.append(f"- **From**: {sender}")
            parts.append(f"  **Subject**: {subject}")
            if snippet:
                parts.append(f"  {snippet}")
            parts.append("")

        # Notes
        if notes:
            parts.append(f"## Recent Notes ({len(notes)})")
            for n in notes[:10]:
                parts.append(f"- **{n.get('title', 'Untitled')}**: {n.get('body', '')[:200]}")
            parts.append("")

        return "\n".join(parts)
