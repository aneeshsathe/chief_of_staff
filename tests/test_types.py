"""Tests for core types."""

from __future__ import annotations

from datetime import datetime, timezone

from cos.core.types import (
    Briefing,
    BriefingSection,
    CalendarEvent,
    EmailMessage,
    Note,
    Priority,
)


def test_email_message():
    email = EmailMessage(
        id="msg1",
        account_id="work",
        sender="alice@example.com",
        subject="Q4 Planning",
        body="Let's discuss...",
        date=datetime.now(timezone.utc),
    )
    assert email.is_unread is True
    assert email.sender_name == ""


def test_calendar_event():
    event = CalendarEvent(
        id="evt1",
        calendar_id="primary",
        title="Team Standup",
        start=datetime(2026, 2, 18, 9, 0, tzinfo=timezone.utc),
        end=datetime(2026, 2, 18, 9, 30, tzinfo=timezone.utc),
        attendees=["alice@example.com", "bob@example.com"],
    )
    assert len(event.attendees) == 2
    assert event.is_all_day is False


def test_note():
    note = Note(id="n1", title="Meeting Notes", body="Action items: ...")
    assert note.folder == ""


def test_briefing():
    briefing = Briefing(
        date=datetime.now(timezone.utc),
        context="day_job",
        sections=[
            BriefingSection(title="Schedule", content="3 meetings today", priority=Priority.HIGH),
        ],
        summary="Busy day ahead",
        action_items=["Review PR #42", "Prep for 2pm meeting"],
    )
    assert len(briefing.sections) == 1
    assert len(briefing.action_items) == 2
