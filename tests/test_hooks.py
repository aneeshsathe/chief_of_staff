"""Tests for human-in-the-loop approval hooks."""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

import pytest
from rich.console import Console

import cos.core.hooks as hooks_module
from cos.core.hooks import require_approval


@pytest.fixture()
def capture_console(monkeypatch: pytest.MonkeyPatch) -> Console:
    """Replace the module-level console with a non-terminal buffered console."""
    buf = StringIO()
    con = Console(file=buf, force_terminal=False, highlight=False)
    monkeypatch.setattr(hooks_module, "console", con)
    con._buf = buf  # type: ignore[attr-defined]
    return con


def _output(con: Console) -> str:
    return con._buf.getvalue()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# dry_run mode
# ---------------------------------------------------------------------------


class TestRequireApprovalDryRun:
    def test_dry_run_returns_false(self, capture_console: Console) -> None:
        result = require_approval("send email", dry_run=True)
        assert result is False

    def test_dry_run_prints_dry_run_panel(self, capture_console: Console) -> None:
        require_approval("send email", details="To: alice@example.com", dry_run=True)
        out = _output(capture_console)
        assert "DRY RUN" in out

    def test_dry_run_includes_action(self, capture_console: Console) -> None:
        require_approval("create task", dry_run=True)
        out = _output(capture_console)
        assert "create task" in out

    def test_dry_run_includes_details(self, capture_console: Console) -> None:
        require_approval("delete file", details="path=/tmp/x", dry_run=True)
        out = _output(capture_console)
        assert "path=/tmp/x" in out

    def test_dry_run_does_not_call_typer_confirm(self, capture_console: Console) -> None:
        with patch.object(hooks_module.typer, "confirm") as mock_confirm:
            require_approval("action", dry_run=True)
            mock_confirm.assert_not_called()


# ---------------------------------------------------------------------------
# interactive (non-dry-run) mode
# ---------------------------------------------------------------------------


class TestRequireApprovalInteractive:
    def test_returns_true_when_confirmed(self, capture_console: Console) -> None:
        with patch.object(hooks_module.typer, "confirm", return_value=True):
            result = require_approval("send message")
            assert result is True

    def test_returns_false_when_denied(self, capture_console: Console) -> None:
        with patch.object(hooks_module.typer, "confirm", return_value=False):
            result = require_approval("delete record")
            assert result is False

    def test_prints_approval_panel(self, capture_console: Console) -> None:
        with patch.object(hooks_module.typer, "confirm", return_value=False):
            require_approval("archive emails")
        out = _output(capture_console)
        assert "Approval Required" in out

    def test_action_shown_in_panel(self, capture_console: Console) -> None:
        with patch.object(hooks_module.typer, "confirm", return_value=False):
            require_approval("post to slack")
        out = _output(capture_console)
        assert "post to slack" in out

    def test_details_shown_in_panel(self, capture_console: Console) -> None:
        with patch.object(hooks_module.typer, "confirm", return_value=False):
            require_approval("update config", details="key=value")
        out = _output(capture_console)
        assert "key=value" in out

    def test_confirm_called_with_proceed_prompt(self, capture_console: Console) -> None:
        with patch.object(hooks_module.typer, "confirm", return_value=True) as mock_confirm:
            require_approval("action")
            mock_confirm.assert_called_once()
            args, kwargs = mock_confirm.call_args
            assert "Proceed" in args[0]

    def test_confirm_default_is_false(self, capture_console: Console) -> None:
        with patch.object(hooks_module.typer, "confirm", return_value=False) as mock_confirm:
            require_approval("action")
            _, kwargs = mock_confirm.call_args
            assert kwargs.get("default") is False

    def test_empty_details_does_not_raise(self, capture_console: Console) -> None:
        with patch.object(hooks_module.typer, "confirm", return_value=False):
            result = require_approval("action", details="")
            assert result is False

    def test_dry_run_false_by_default(self, capture_console: Console) -> None:
        """Verify dry_run defaults to False so the real approval path is taken."""
        with patch.object(hooks_module.typer, "confirm", return_value=True) as mock_confirm:
            require_approval("action")
            mock_confirm.assert_called_once()
