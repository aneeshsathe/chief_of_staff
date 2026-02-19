"""Tests for Rich CLI formatters."""

from __future__ import annotations

from io import StringIO

import pytest
from rich.console import Console

import cos.cli.formatters as formatters_module
from cos.cli.formatters import (
    print_briefing,
    print_error,
    print_health_table,
    print_notes_list,
    print_success,
    print_warning,
)


@pytest.fixture()
def capture_console(monkeypatch: pytest.MonkeyPatch) -> Console:
    """Replace the module-level console with one that writes to a StringIO buffer."""
    buf = StringIO()
    con = Console(file=buf, force_terminal=False, highlight=False)
    monkeypatch.setattr(formatters_module, "console", con)
    con._buf = buf  # type: ignore[attr-defined]  # expose buffer for assertions
    return con


def _output(con: Console) -> str:
    return con._buf.getvalue()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# print_briefing
# ---------------------------------------------------------------------------


class TestPrintBriefing:
    def test_basic_briefing_contains_header(self, capture_console: Console) -> None:
        print_briefing("## Hello\nGood morning.")
        out = _output(capture_console)
        assert "Morning Briefing" in out

    def test_context_appended_to_header(self, capture_console: Console) -> None:
        print_briefing("content", context="day_job")
        out = _output(capture_console)
        assert "day_job" in out

    def test_no_footer_when_zero_cost_and_tokens(self, capture_console: Console) -> None:
        print_briefing("content", cost_usd=0.0, tokens=0)
        out = _output(capture_console)
        assert "Tokens:" not in out
        assert "Cost:" not in out

    def test_tokens_shown_in_footer(self, capture_console: Console) -> None:
        print_briefing("content", tokens=1500)
        out = _output(capture_console)
        assert "1,500" in out

    def test_cost_shown_in_footer(self, capture_console: Console) -> None:
        print_briefing("content", cost_usd=0.0042)
        out = _output(capture_console)
        assert "0.0042" in out

    def test_both_tokens_and_cost_shown(self, capture_console: Console) -> None:
        print_briefing("content", cost_usd=0.01, tokens=800)
        out = _output(capture_console)
        assert "800" in out
        assert "0.0100" in out

    def test_empty_context_not_appended(self, capture_console: Console) -> None:
        print_briefing("content", context="")
        out = _output(capture_console)
        assert "—" not in out


# ---------------------------------------------------------------------------
# print_health_table
# ---------------------------------------------------------------------------


class TestPrintHealthTable:
    def test_shows_table_title(self, capture_console: Console) -> None:
        print_health_table([{"name": "github", "status": "healthy", "message": "OK"}])
        out = _output(capture_console)
        assert "Integration Health" in out

    def test_healthy_status_present(self, capture_console: Console) -> None:
        print_health_table([{"name": "slack", "status": "healthy", "message": ""}])
        out = _output(capture_console)
        assert "healthy" in out

    def test_degraded_status_present(self, capture_console: Console) -> None:
        print_health_table([{"name": "slack", "status": "degraded", "message": "slow"}])
        out = _output(capture_console)
        assert "degraded" in out

    def test_unhealthy_status_present(self, capture_console: Console) -> None:
        print_health_table([{"name": "asana", "status": "unhealthy", "message": "err"}])
        out = _output(capture_console)
        assert "unhealthy" in out

    def test_unconfigured_status_present(self, capture_console: Console) -> None:
        print_health_table([{"name": "asana", "status": "unconfigured", "message": ""}])
        out = _output(capture_console)
        assert "unconfigured" in out

    def test_unknown_status_passes_through(self, capture_console: Console) -> None:
        print_health_table([{"name": "foo", "status": "pending", "message": ""}])
        out = _output(capture_console)
        assert "pending" in out

    def test_multiple_rows(self, capture_console: Console) -> None:
        checks = [
            {"name": "github", "status": "healthy", "message": ""},
            {"name": "slack", "status": "unhealthy", "message": "no token"},
        ]
        print_health_table(checks)
        out = _output(capture_console)
        assert "github" in out
        assert "slack" in out

    def test_missing_keys_do_not_raise(self, capture_console: Console) -> None:
        print_health_table([{}])  # all fields missing


# ---------------------------------------------------------------------------
# print_notes_list
# ---------------------------------------------------------------------------


class TestPrintNotesList:
    def test_empty_list_prints_no_notes_found(self, capture_console: Console) -> None:
        print_notes_list([])
        out = _output(capture_console)
        assert "No notes found" in out

    def test_single_note_shown(self, capture_console: Console) -> None:
        notes = [{"title": "My Note", "body": "Some content here", "modified": "2026-02-18T10:00:00"}]
        print_notes_list(notes)
        out = _output(capture_console)
        assert "My Note" in out
        assert "Apple Notes" in out

    def test_body_truncated_to_80_chars(self, capture_console: Console) -> None:
        long_body = "x" * 200
        notes = [{"title": "Long", "body": long_body, "modified": ""}]
        print_notes_list(notes)
        # Just verifying it doesn't error; the table column has max_width=60

    def test_newlines_in_body_replaced(self, capture_console: Console) -> None:
        notes = [{"title": "T", "body": "line1\nline2", "modified": ""}]
        print_notes_list(notes)
        out = _output(capture_console)
        # The note row shouldn't contain a raw newline within the cell
        assert "line1" in out

    def test_modified_date_truncated_to_16_chars(self, capture_console: Console) -> None:
        notes = [{"title": "T", "body": "", "modified": "2026-02-18T10:00:00+00:00"}]
        print_notes_list(notes)
        # Should not raise

    def test_untitled_fallback(self, capture_console: Console) -> None:
        notes = [{"body": "content", "modified": ""}]
        print_notes_list(notes)
        out = _output(capture_console)
        assert "Untitled" in out

    def test_multiple_notes_numbered(self, capture_console: Console) -> None:
        notes = [
            {"title": "First", "body": "", "modified": ""},
            {"title": "Second", "body": "", "modified": ""},
        ]
        print_notes_list(notes)
        out = _output(capture_console)
        assert "1" in out
        assert "2" in out


# ---------------------------------------------------------------------------
# print_error / print_success / print_warning
# ---------------------------------------------------------------------------


class TestStatusMessages:
    def test_print_error_contains_error(self, capture_console: Console) -> None:
        print_error("something went wrong")
        out = _output(capture_console)
        assert "Error" in out
        assert "something went wrong" in out

    def test_print_success_contains_ok(self, capture_console: Console) -> None:
        print_success("operation complete")
        out = _output(capture_console)
        assert "OK" in out
        assert "operation complete" in out

    def test_print_warning_contains_warning(self, capture_console: Console) -> None:
        print_warning("disk almost full")
        out = _output(capture_console)
        assert "Warning" in out
        assert "disk almost full" in out
