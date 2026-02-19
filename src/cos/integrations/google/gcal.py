"""Google Calendar API integration - read today's events."""

from __future__ import annotations

from datetime import UTC, datetime, time

import structlog
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from cos.core.errors import IntegrationError
from cos.core.types import CalendarEvent
from cos.integrations.registry import HealthStatus, IntegrationHealth, registry

log = structlog.get_logger("integrations.gcal")


class GCalClient:
    """Google Calendar API client."""

    SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

    def __init__(self, credentials: Credentials, calendar_id: str = "primary") -> None:
        self.calendar_id = calendar_id
        self.credentials = credentials
        self._service = build("calendar", "v3", credentials=credentials)

    async def get_todays_events(self) -> list[CalendarEvent]:
        """Fetch today's calendar events."""
        return await self.get_events_for_date(datetime.now(UTC).date())

    async def get_events_for_date(self, date) -> list[CalendarEvent]:
        """Fetch events for a specific date."""
        time_min = datetime.combine(date, time.min, tzinfo=UTC)
        time_max = datetime.combine(date, time.max, tzinfo=UTC)
        return await self.get_events(time_min, time_max)

    async def get_events(self, time_min: datetime, time_max: datetime) -> list[CalendarEvent]:
        """Fetch events within a time range."""
        try:
            results = (
                self._service.events()
                .list(
                    calendarId=self.calendar_id,
                    timeMin=time_min.isoformat(),
                    timeMax=time_max.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = []
            for item in results.get("items", []):
                event = self._parse_event(item)
                if event:
                    events.append(event)
            return events
        except Exception as e:
            raise IntegrationError(f"Calendar fetch failed for {self.calendar_id}: {e}") from e

    def _parse_event(self, item: dict) -> CalendarEvent | None:
        """Parse a raw calendar event into a CalendarEvent."""
        try:
            start_raw = item.get("start", {})
            end_raw = item.get("end", {})

            is_all_day = "date" in start_raw and "dateTime" not in start_raw

            if is_all_day:
                start = datetime.fromisoformat(start_raw["date"])
                end = datetime.fromisoformat(end_raw["date"])
            else:
                start = datetime.fromisoformat(start_raw.get("dateTime", ""))
                end = datetime.fromisoformat(end_raw.get("dateTime", ""))

            attendees = [a.get("email", "") for a in item.get("attendees", []) if a.get("email")]

            # Extract meeting link
            meeting_link = ""
            if "hangoutLink" in item:
                meeting_link = item["hangoutLink"]
            elif "conferenceData" in item:
                entry_points = item["conferenceData"].get("entryPoints", [])
                for ep in entry_points:
                    if ep.get("entryPointType") == "video":
                        meeting_link = ep.get("uri", "")
                        break

            return CalendarEvent(
                id=item["id"],
                calendar_id=self.calendar_id,
                title=item.get("summary", "(no title)"),
                description=item.get("description", ""),
                start=start,
                end=end,
                attendees=attendees,
                location=item.get("location", ""),
                meeting_link=meeting_link,
                is_all_day=is_all_day,
            )
        except Exception as e:
            log.debug("Failed to parse event", event_id=item.get("id", "unknown"), error=str(e))
            return None


async def _gcal_health_check() -> IntegrationHealth:
    return IntegrationHealth(
        name="calendar", status=HealthStatus.UNCONFIGURED, message="Run 'cos config init' to set up"
    )


registry.register("calendar", _gcal_health_check)
