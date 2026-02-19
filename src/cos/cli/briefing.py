"""cos briefing command group."""

from __future__ import annotations

import anyio
import typer

from cos.cli.formatters import console, print_briefing, print_error, print_warning

briefing_app = typer.Typer(name="briefing", help="Generate briefings")


@briefing_app.command("daily")
def daily(
    context: str = typer.Option(None, "--context", "-c", help="Context to use"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be fetched without calling LLM"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    cost_report: bool = typer.Option(False, "--cost-report", help="Show token usage and cost"),
) -> None:
    """Generate a daily morning briefing."""
    anyio.run(_daily_briefing, context, dry_run, verbose, cost_report)


async def _daily_briefing(
    context: str | None,
    dry_run: bool,
    verbose: bool,
    cost_report: bool,
) -> None:
    from cos.config.settings import load_config
    from cos.core.logging import setup_logging

    setup_logging(verbose=verbose)
    config = load_config()

    if context:
        config = config.model_copy(update={"active_context": context})

    ctx = config.current_context

    # Gather data from integrations
    emails: list[dict] = []
    events: list[dict] = []
    notes: list[dict] = []

    # Try Gmail
    try:
        from cos.integrations.google.auth import get_credentials
        from cos.integrations.google.gmail import GmailClient

        for acct in ctx.email_accounts:
            creds = get_credentials(acct.id)
            client = GmailClient(creds, acct.id)
            raw_emails = await client.get_unread_emails(max_results=30)
            emails.extend([e.model_dump() for e in raw_emails])
    except Exception as e:
        print_warning(f"Gmail: {e}")

    # Try Calendar
    try:
        from cos.integrations.google.auth import get_credentials
        from cos.integrations.google.gcal import GCalClient

        for cal in ctx.calendars:
            creds = get_credentials(
                cal.id
                if cal.id != cal.calendar_id
                else ctx.email_accounts[0].id
                if ctx.email_accounts
                else "default"
            )
            client = GCalClient(creds, cal.calendar_id)
            raw_events = await client.get_todays_events()
            events.extend(
                [
                    {
                        "title": ev.title,
                        "start": ev.start.strftime("%H:%M") if not ev.is_all_day else "All day",
                        "end": ev.end.strftime("%H:%M") if not ev.is_all_day else "",
                        "attendees": ev.attendees,
                        "location": ev.location,
                        "meeting_link": ev.meeting_link,
                    }
                    for ev in raw_events
                ]
            )
    except Exception as e:
        print_warning(f"Calendar: {e}")

    # Try Apple Notes
    try:
        from cos.integrations.apple_notes import AppleNotesClient

        if config.sync.apple_notes.enabled:
            notes_client = AppleNotesClient(config.sync.apple_notes.folder)
            raw_notes = await notes_client.list_notes()
            notes = [n.model_dump() for n in raw_notes[:10]]
    except Exception as e:
        print_warning(f"Apple Notes: {e}")

    if dry_run:
        console.print(
            f"[dim]Would briefing with: {len(emails)} emails, {len(events)} events, {len(notes)} notes[/dim]"
        )
        return

    if not emails and not events and not notes:
        print_error(
            "No data available. Make sure integrations are configured.\n"
            "Run 'cos config init' to set up, or use --verbose to see errors."
        )
        return

    # Generate briefing
    from cos.agents.base import AgentInput
    from cos.agents.briefer import BriefingAgent

    agent = BriefingAgent(config)
    result = await agent.run(
        AgentInput(
            context_name=ctx.label,
            data={"emails": emails, "events": events, "notes": notes},
        )
    )

    print_briefing(
        result.content,
        context=ctx.label,
        cost_usd=result.cost_usd if cost_report else 0,
        tokens=(result.input_tokens + result.output_tokens) if cost_report else 0,
    )
