"""Tests for AppleNotesClient via mocked subprocess."""

from __future__ import annotations

import subprocess
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from cos.core.errors import IntegrationError
from cos.core.types import Note
from cos.integrations.apple_notes import (
    AppleNotesClient,
    _parse_applescript_date,
    _apple_notes_health_check,
)
from cos.integrations.registry import HealthStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


def _make_note_output(
    note_id: str = "x-coredata://123",
    title: str = "My Note",
    modified: str = "Wednesday, February 18, 2026 at 09:00:00 AM",
    body: str = "<div>Hello world</div>",
) -> str:
    return f"{note_id}|||{title}|||{modified}|||{body}<<>>"


# ---------------------------------------------------------------------------
# AppleNotesClient.list_notes
# ---------------------------------------------------------------------------


class TestListNotes:
    @pytest.mark.asyncio
    async def test_returns_empty_list_on_empty_output(self) -> None:
        proc = _make_proc(stdout="")
        with patch("subprocess.run", return_value=proc):
            client = AppleNotesClient()
            notes = await client.list_notes()
            assert notes == []

    @pytest.mark.asyncio
    async def test_returns_note_on_valid_output(self) -> None:
        raw = _make_note_output()
        proc = _make_proc(stdout=raw)
        with patch("subprocess.run", return_value=proc):
            client = AppleNotesClient()
            notes = await client.list_notes()
            assert len(notes) == 1
            assert notes[0].title == "My Note"

    @pytest.mark.asyncio
    async def test_html_stripped_from_body(self) -> None:
        raw = _make_note_output(body="<p><b>Bold</b> text</p>")
        proc = _make_proc(stdout=raw)
        with patch("subprocess.run", return_value=proc):
            notes = await AppleNotesClient().list_notes()
            assert "<" not in notes[0].body
            assert "Bold" in notes[0].body

    @pytest.mark.asyncio
    async def test_multiple_notes_parsed(self) -> None:
        raw = _make_note_output(note_id="id1", title="Note A") + _make_note_output(
            note_id="id2", title="Note B"
        )
        proc = _make_proc(stdout=raw)
        with patch("subprocess.run", return_value=proc):
            notes = await AppleNotesClient().list_notes()
            assert len(notes) == 2
            titles = {n.title for n in notes}
            assert {"Note A", "Note B"} == titles

    @pytest.mark.asyncio
    async def test_raises_on_non_zero_returncode(self) -> None:
        proc = _make_proc(returncode=1, stderr="Notes: not found")
        with patch("subprocess.run", return_value=proc):
            with pytest.raises(IntegrationError, match="AppleScript error"):
                await AppleNotesClient().list_notes()

    @pytest.mark.asyncio
    async def test_raises_on_timeout(self) -> None:
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="osascript", timeout=30)):
            with pytest.raises(IntegrationError, match="timed out"):
                await AppleNotesClient().list_notes()

    @pytest.mark.asyncio
    async def test_raises_on_generic_exception(self) -> None:
        with patch("subprocess.run", side_effect=OSError("no osascript")):
            with pytest.raises(IntegrationError, match="Apple Notes error"):
                await AppleNotesClient().list_notes()

    @pytest.mark.asyncio
    async def test_folder_passed_to_osascript(self) -> None:
        proc = _make_proc(stdout="")
        with patch("subprocess.run", return_value=proc) as mock_run:
            client = AppleNotesClient(folder="Work Notes")
            await client.list_notes()
            call_args = mock_run.call_args
            script_arg = call_args[0][0][2]  # ["osascript", "-e", <script>]
            assert "Work Notes" in script_arg

    @pytest.mark.asyncio
    async def test_default_folder_is_chief_of_staff(self) -> None:
        client = AppleNotesClient()
        assert client.folder == "Chief of Staff"

    @pytest.mark.asyncio
    async def test_note_id_stripped(self) -> None:
        raw = _make_note_output(note_id="  note-123  ")
        proc = _make_proc(stdout=raw)
        with patch("subprocess.run", return_value=proc):
            notes = await AppleNotesClient().list_notes()
            assert notes[0].id == "note-123"

    @pytest.mark.asyncio
    async def test_partial_block_skipped(self) -> None:
        # Block with fewer than 4 pipe-separated parts
        raw = "id1|||title only<<>>"
        proc = _make_proc(stdout=raw)
        with patch("subprocess.run", return_value=proc):
            notes = await AppleNotesClient().list_notes()
            assert notes == []

    @pytest.mark.asyncio
    async def test_note_folder_set_correctly(self) -> None:
        raw = _make_note_output()
        proc = _make_proc(stdout=raw)
        with patch("subprocess.run", return_value=proc):
            client = AppleNotesClient(folder="My Folder")
            notes = await client.list_notes()
            assert notes[0].folder == "My Folder"


# ---------------------------------------------------------------------------
# AppleNotesClient.search_notes
# ---------------------------------------------------------------------------


class TestSearchNotes:
    @pytest.mark.asyncio
    async def test_returns_matching_notes(self) -> None:
        raw = _make_note_output(title="Meeting Notes", body="<p>project alpha</p>")
        proc = _make_proc(stdout=raw)
        with patch("subprocess.run", return_value=proc):
            notes = await AppleNotesClient().search_notes("alpha")
            assert len(notes) == 1

    @pytest.mark.asyncio
    async def test_query_included_in_script(self) -> None:
        proc = _make_proc(stdout="")
        with patch("subprocess.run", return_value=proc) as mock_run:
            await AppleNotesClient().search_notes("my search term")
            script_arg = mock_run.call_args[0][0][2]
            assert "my search term" in script_arg

    @pytest.mark.asyncio
    async def test_empty_result_returns_empty_list(self) -> None:
        proc = _make_proc(stdout="")
        with patch("subprocess.run", return_value=proc):
            notes = await AppleNotesClient().search_notes("nothing")
            assert notes == []


# ---------------------------------------------------------------------------
# _parse_applescript_date
# ---------------------------------------------------------------------------


class TestParseApplescriptDate:
    def test_parses_long_format(self) -> None:
        result = _parse_applescript_date("Wednesday, February 18, 2026 at 09:00:00 AM")
        assert isinstance(result, datetime)
        assert result.year == 2026
        assert result.month == 2
        assert result.day == 18

    def test_parses_short_format(self) -> None:
        result = _parse_applescript_date("02/18/2026 09:00:00")
        assert isinstance(result, datetime)
        assert result.year == 2026

    def test_parses_iso_format(self) -> None:
        result = _parse_applescript_date("2026-02-18 09:00:00")
        assert isinstance(result, datetime)
        assert result.month == 2

    def test_returns_none_on_unparseable(self) -> None:
        result = _parse_applescript_date("not a date")
        assert result is None

    def test_returns_none_on_empty_string(self) -> None:
        result = _parse_applescript_date("")
        assert result is None


# ---------------------------------------------------------------------------
# _apple_notes_health_check
# ---------------------------------------------------------------------------


class TestAppleNotesHealthCheck:
    @pytest.mark.asyncio
    async def test_healthy_when_osascript_succeeds(self) -> None:
        proc = _make_proc(returncode=0, stdout="iCloud")
        with patch("subprocess.run", return_value=proc):
            health = await _apple_notes_health_check()
            assert health.status == HealthStatus.HEALTHY
            assert "iCloud" in health.message

    @pytest.mark.asyncio
    async def test_unhealthy_when_osascript_fails(self) -> None:
        proc = _make_proc(returncode=1, stderr="permission denied")
        with patch("subprocess.run", return_value=proc):
            health = await _apple_notes_health_check()
            assert health.status == HealthStatus.UNHEALTHY
            assert "permission denied" in health.message

    @pytest.mark.asyncio
    async def test_unhealthy_on_exception(self) -> None:
        with patch("subprocess.run", side_effect=OSError("osascript not found")):
            health = await _apple_notes_health_check()
            assert health.status == HealthStatus.UNHEALTHY
            assert "osascript not found" in health.message

    @pytest.mark.asyncio
    async def test_name_is_apple_notes(self) -> None:
        proc = _make_proc(returncode=0, stdout="iCloud")
        with patch("subprocess.run", return_value=proc):
            health = await _apple_notes_health_check()
            assert health.name == "apple_notes"
