"""Shared Pydantic models used across the application."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Priority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    FYI = "fyi"


class EmailMessage(BaseModel):
    id: str
    account_id: str
    sender: str
    sender_name: str = ""
    to: list[str] = Field(default_factory=list)
    cc: list[str] = Field(default_factory=list)
    subject: str
    body: str
    snippet: str = ""
    date: datetime
    thread_id: str = ""
    labels: list[str] = Field(default_factory=list)
    is_unread: bool = True


class CalendarEvent(BaseModel):
    id: str
    calendar_id: str
    title: str
    description: str = ""
    start: datetime
    end: datetime
    attendees: list[str] = Field(default_factory=list)
    location: str = ""
    meeting_link: str = ""
    is_all_day: bool = False


class TaskItem(BaseModel):
    id: str
    source: str  # "asana", "github", etc.
    title: str
    description: str = ""
    project: str = ""
    status: str = ""
    assignee: str = ""
    due: datetime | None = None
    url: str = ""


class Note(BaseModel):
    id: str
    title: str
    body: str
    folder: str = ""
    created: datetime | None = None
    modified: datetime | None = None


class BriefingSection(BaseModel):
    title: str
    content: str
    priority: Priority = Priority.MEDIUM
    source: str = ""


class Briefing(BaseModel):
    date: datetime
    context: str
    sections: list[BriefingSection] = Field(default_factory=list)
    summary: str = ""
    action_items: list[str] = Field(default_factory=list)
    token_usage: int = 0
    cost_usd: float = 0.0
