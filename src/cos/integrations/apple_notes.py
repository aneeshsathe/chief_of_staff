"""Apple Notes reader via AppleScript bridge."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime

import anyio

from cos.core.errors import IntegrationError
from cos.core.types import Note
from cos.integrations.registry import HealthStatus, IntegrationHealth, registry

APPLESCRIPT_LIST_NOTES = """
tell application "Notes"
    set noteList to ""
    set targetFolder to folder "{folder}" of default account
    repeat with n in notes of targetFolder
        set d to "|||"
        set noteList to noteList & id of n & d & name of n & d & modification date of n & d & body of n & "<<>>"
    end repeat
    return noteList
end tell
"""

APPLESCRIPT_SEARCH_NOTES = """
tell application "Notes"
    set noteList to ""
    set targetFolder to folder "{folder}" of default account
    set d to "|||"
    repeat with n in notes of targetFolder
        if body of n contains "{query}" or name of n contains "{query}" then
            set noteList to noteList & id of n & d & name of n & d & modification date of n & d & body of n & "<<>>"
        end if
    end repeat
    return noteList
end tell
"""


def _escape_applescript(s: str) -> str:
    """Escape a string for safe interpolation inside an AppleScript double-quoted string.

    AppleScript uses backslash as an escape character inside double-quoted
    strings, so backslashes must be escaped first, then double quotes.
    """
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    return s


class AppleNotesClient:
    """Read notes from Apple Notes via AppleScript."""

    def __init__(self, folder: str = "Chief of Staff") -> None:
        self.folder = folder

    async def list_notes(self) -> list[Note]:
        """List all notes in the configured folder."""
        script = APPLESCRIPT_LIST_NOTES.format(folder=_escape_applescript(self.folder))
        return await anyio.to_thread.run_sync(lambda: self._run_and_parse(script))

    async def search_notes(self, query: str) -> list[Note]:
        """Search notes by text content."""
        script = APPLESCRIPT_SEARCH_NOTES.format(
            folder=_escape_applescript(self.folder),
            query=_escape_applescript(query),
        )
        return await anyio.to_thread.run_sync(lambda: self._run_and_parse(script))

    def _run_and_parse(self, script: str) -> list[Note]:
        """Execute AppleScript and parse results."""
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise IntegrationError(f"AppleScript error: {result.stderr}")

            output = result.stdout.strip()
            if not output:
                return []

            notes = []
            for block in output.split("<<>>"):
                block = block.strip()
                if not block:
                    continue
                parts = block.split("|||", 3)
                if len(parts) < 4:
                    continue
                note_id, title, mod_date_str, body = parts

                # Strip HTML tags from body (Apple Notes returns HTML)
                clean_body = re.sub(r"<[^>]+>", "", body).strip()

                notes.append(
                    Note(
                        id=note_id.strip(),
                        title=title.strip(),
                        body=clean_body,
                        folder=self.folder,
                        modified=_parse_applescript_date(mod_date_str.strip()),
                    )
                )
            return notes
        except subprocess.TimeoutExpired as e:
            raise IntegrationError("Apple Notes query timed out") from e
        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(f"Apple Notes error: {e}") from e


def _parse_applescript_date(date_str: str) -> datetime | None:
    """Parse AppleScript date string."""
    formats = [
        "%A, %B %d, %Y at %I:%M:%S %p",
        "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


async def _apple_notes_health_check() -> IntegrationHealth:
    """Check if Apple Notes is accessible."""
    try:
        result = subprocess.run(
            ["osascript", "-e", 'tell application "Notes" to return name of default account'],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return IntegrationHealth(
                name="apple_notes",
                status=HealthStatus.HEALTHY,
                message=f"Account: {result.stdout.strip()}",
            )
        return IntegrationHealth(
            name="apple_notes",
            status=HealthStatus.UNHEALTHY,
            message=result.stderr.strip(),
        )
    except Exception as e:
        return IntegrationHealth(name="apple_notes", status=HealthStatus.UNHEALTHY, message=str(e))


registry.register("apple_notes", _apple_notes_health_check)
