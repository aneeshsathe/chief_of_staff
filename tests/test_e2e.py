"""End-to-end integration tests for the cos CLI pipeline.

All external services (Google APIs, Apple Notes subprocess, LLM calls, cognee)
are mocked so these tests run offline without any credentials.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from cos.agents.base import AgentInput, AgentOutput
from cos.config.contexts import list_contexts, switch_context
from cos.config.settings import (
    AppConfig,
    AppleNotesConfig,
    CalendarConfig,
    ContextConfig,
    EmailAccountConfig,
    ModelsConfig,
    SyncConfig,
    load_config,
    save_config,
)
from cos.core.errors import CosMemoryError
from cos.core.types import CalendarEvent, EmailMessage, Note
from cos.integrations.registry import HealthStatus, IntegrationHealth, IntegrationRegistry
from cos.memory.engine import MemoryEngine
from cos.models.providers import LLMResponse


# ---------------------------------------------------------------------------
# Shared sample data factories
# ---------------------------------------------------------------------------


def _sample_email(
    idx: int = 1,
    subject: str = "Q4 roadmap review - action needed",
    sender: str = "alice@company.com",
    sender_name: str = "Alice Chen",
    snippet: str = "Please review and approve the attached roadmap before Friday.",
) -> EmailMessage:
    return EmailMessage(
        id=f"msg-{idx:04d}",
        account_id="work@company.com",
        sender=f"{sender_name} <{sender}>",
        sender_name=sender_name,
        to=["me@company.com"],
        cc=[],
        subject=subject,
        body=f"Hi,\n\n{snippet}\n\nBest,\n{sender_name}",
        snippet=snippet,
        date=datetime(2026, 2, 18, 9, 0, 0, tzinfo=timezone.utc),
        thread_id=f"thread-{idx:04d}",
        labels=["UNREAD", "INBOX"],
        is_unread=True,
    )


def _sample_event(
    idx: int = 1,
    title: str = "Weekly Engineering Sync",
    start_hour: int = 10,
    end_hour: int = 11,
    attendees: list[str] | None = None,
) -> CalendarEvent:
    if attendees is None:
        attendees = ["alice@company.com", "bob@company.com"]
    return CalendarEvent(
        id=f"evt-{idx:04d}",
        calendar_id="primary",
        title=title,
        description="Weekly sync for the engineering team",
        start=datetime(2026, 2, 18, start_hour, 0, 0, tzinfo=timezone.utc),
        end=datetime(2026, 2, 18, end_hour, 0, 0, tzinfo=timezone.utc),
        attendees=attendees,
        location="Zoom",
        meeting_link="https://zoom.us/j/12345",
        is_all_day=False,
    )


def _sample_note(
    idx: int = 1,
    title: str = "Project Alpha Notes",
    body: str = "Key insights from last week's planning session.",
) -> Note:
    return Note(
        id=f"note-{idx:04d}",
        title=title,
        body=body,
        folder="Chief of Staff",
        modified=datetime(2026, 2, 17, 15, 30, 0),
    )


def _sample_llm_response(
    content: str = "## Morning Briefing\n\nYou have 2 meetings today and 3 priority emails.",
    model: str = "claude-sonnet-4-6",
    input_tokens: int = 1200,
    output_tokens: int = 400,
) -> LLMResponse:
    return LLMResponse(
        content=content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=model,
    )


def _make_app_config(tmp_path: Path | None = None) -> AppConfig:
    """Build a realistic AppConfig with two contexts."""
    sync = SyncConfig(
        apple_notes=AppleNotesConfig(enabled=True, folder="Chief of Staff"),
    )
    if tmp_path is not None:
        sync = SyncConfig(
            memory_path=tmp_path / "memory",
            apple_notes=AppleNotesConfig(enabled=True, folder="Chief of Staff"),
        )
    return AppConfig(
        active_context="day_job",
        contexts={
            "day_job": ContextConfig(
                label="VP Data Science",
                email_accounts=[
                    EmailAccountConfig(id="work", type="google", address="me@company.com")
                ],
                calendars=[CalendarConfig(id="work_cal", type="google", calendar_id="primary")],
                priorities=["roadmap", "hiring", "data platform"],
            ),
            "advisory": ContextConfig(
                label="Startup Advisor",
                email_accounts=[
                    EmailAccountConfig(id="personal", type="google", address="me@personal.com")
                ],
                calendars=[],
            ),
        },
        sync=sync,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def app_config(tmp_path: Path) -> AppConfig:
    return _make_app_config(tmp_path)


@pytest.fixture()
def mock_credentials() -> MagicMock:
    creds = MagicMock()
    creds.valid = True
    creds.expired = False
    creds.refresh_token = "mock-refresh-token"
    creds.token = "mock-token"
    return creds


@pytest.fixture()
def sample_emails() -> list[EmailMessage]:
    return [
        _sample_email(1, "Q4 roadmap review - action needed", "alice@company.com", "Alice Chen"),
        _sample_email(2, "Hiring committee update", "hr@company.com", "HR Team"),
        _sample_email(3, "Data platform incident resolved", "oncall@company.com", "On-Call Bot"),
    ]


@pytest.fixture()
def sample_events() -> list[CalendarEvent]:
    return [
        _sample_event(1, "Weekly Engineering Sync", 10, 11, ["alice@company.com"]),
        _sample_event(2, "1:1 with CEO", 14, 14, ["ceo@company.com"]),
    ]


@pytest.fixture()
def sample_notes() -> list[Note]:
    return [
        _sample_note(1, "Project Alpha Notes", "Key insights from planning."),
        _sample_note(2, "Hiring pipeline", "Three strong candidates for ML lead role."),
    ]


@pytest.fixture()
def sample_llm_response() -> LLMResponse:
    return _sample_llm_response()


# ---------------------------------------------------------------------------
# Cognee mock fixture (mirrored from test_memory_engine.py)
# ---------------------------------------------------------------------------


def _make_cognee_mock():
    mock = MagicMock()
    mock.add = AsyncMock()
    mock.cognify = AsyncMock()
    mock.memify = AsyncMock()
    mock.prune = MagicMock()
    mock.prune.prune_data = AsyncMock()
    mock.prune.prune_system = AsyncMock()
    mock.search = AsyncMock(return_value=[])
    mock.config = MagicMock()
    mock.config.data_root_directory = MagicMock()
    mock.config.system_root_directory = MagicMock()

    search_type_mock = MagicMock()
    search_type_mock.INSIGHTS = "INSIGHTS"
    search_type_mock.CHUNKS = "CHUNKS"

    return mock, search_type_mock


@pytest.fixture()
def cognee_mock():
    mock_cognee, mock_search_type_mod = _make_cognee_mock()

    api_mod = ModuleType("cognee.api")
    v1_mod = ModuleType("cognee.api.v1")
    search_mod = ModuleType("cognee.api.v1.search")
    search_mod.SearchType = mock_search_type_mod

    with patch.dict(
        sys.modules,
        {
            "cognee": mock_cognee,
            "cognee.api": api_mod,
            "cognee.api.v1": v1_mod,
            "cognee.api.v1.search": search_mod,
        },
    ):
        yield mock_cognee, mock_search_type_mod


# ---------------------------------------------------------------------------
# Scenario 1 – Full briefing pipeline (mock all externals)
# ---------------------------------------------------------------------------


class TestFullBriefingPipeline:
    """End-to-end tests for _daily_briefing with all external services mocked.

    Because _daily_briefing uses lazy imports (imports inside the function body),
    we patch at the source module level rather than the cos.cli.briefing namespace.
    """

    @pytest.mark.asyncio
    async def test_briefing_happy_path(
        self,
        app_config: AppConfig,
        mock_credentials: MagicMock,
        sample_emails: list[EmailMessage],
        sample_events: list[CalendarEvent],
        sample_notes: list[Note],
        sample_llm_response: LLMResponse,
    ) -> None:
        """Full pipeline: emails + events + notes -> LLM -> printed briefing."""
        from cos.cli.briefing import _daily_briefing

        # Patch call_worker at cos.agents.briefer since that module imports it
        # at module level via `from cos.models.router import call_worker`.
        with (
            patch("cos.config.settings.load_config", return_value=app_config),
            patch(
                "cos.integrations.google.auth.get_credentials",
                return_value=mock_credentials,
            ),
            patch(
                "cos.integrations.google.gmail.GmailClient.get_unread_emails",
                new_callable=AsyncMock,
                return_value=sample_emails,
            ),
            patch(
                "cos.integrations.google.gcal.GCalClient.get_todays_events",
                new_callable=AsyncMock,
                return_value=sample_events,
            ),
            patch(
                "cos.integrations.apple_notes.AppleNotesClient.list_notes",
                new_callable=AsyncMock,
                return_value=sample_notes,
            ),
            patch(
                "cos.agents.briefer.call_worker",
                new_callable=AsyncMock,
                return_value=sample_llm_response,
            ) as mock_call_worker,
            patch("cos.cli.formatters.console"),
        ):
            await _daily_briefing(
                context=None,
                dry_run=False,
                verbose=False,
                cost_report=False,
            )

        mock_call_worker.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_briefing_agent_receives_all_data(
        self,
        app_config: AppConfig,
        mock_credentials: MagicMock,
        sample_emails: list[EmailMessage],
        sample_events: list[CalendarEvent],
        sample_notes: list[Note],
        sample_llm_response: LLMResponse,
    ) -> None:
        """The agent's run() receives emails, events, and notes in AgentInput."""
        from cos.cli.briefing import _daily_briefing

        captured_inputs: list[AgentInput] = []

        async def _capture_run(agent_self, agent_input: AgentInput) -> AgentOutput:
            captured_inputs.append(agent_input)
            return AgentOutput(
                content=sample_llm_response.content,
                input_tokens=sample_llm_response.input_tokens,
                output_tokens=sample_llm_response.output_tokens,
                model=sample_llm_response.model,
                cost_usd=0.005,
            )

        with (
            patch("cos.config.settings.load_config", return_value=app_config),
            patch("cos.integrations.google.auth.get_credentials", return_value=mock_credentials),
            patch(
                "cos.integrations.google.gmail.GmailClient.get_unread_emails",
                new_callable=AsyncMock,
                return_value=sample_emails,
            ),
            patch(
                "cos.integrations.google.gcal.GCalClient.get_todays_events",
                new_callable=AsyncMock,
                return_value=sample_events,
            ),
            patch(
                "cos.integrations.apple_notes.AppleNotesClient.list_notes",
                new_callable=AsyncMock,
                return_value=sample_notes,
            ),
            patch("cos.agents.briefer.BriefingAgent.run", _capture_run),
            patch("cos.cli.formatters.console"),
        ):
            await _daily_briefing(
                context=None,
                dry_run=False,
                verbose=False,
                cost_report=False,
            )

        assert len(captured_inputs) == 1
        agent_input = captured_inputs[0]
        assert len(agent_input.data["emails"]) == len(sample_emails)
        assert len(agent_input.data["events"]) == len(sample_events)
        assert len(agent_input.data["notes"]) == len(sample_notes)
        assert agent_input.context_name == app_config.current_context.label

    @pytest.mark.asyncio
    async def test_briefing_cost_report_passes_tokens_and_cost(
        self,
        app_config: AppConfig,
        mock_credentials: MagicMock,
        sample_emails: list[EmailMessage],
        sample_events: list[CalendarEvent],
        sample_notes: list[Note],
        sample_llm_response: LLMResponse,
    ) -> None:
        """When cost_report=True, print_briefing receives non-zero tokens and cost."""
        from cos.cli.briefing import _daily_briefing

        with (
            patch("cos.config.settings.load_config", return_value=app_config),
            patch("cos.integrations.google.auth.get_credentials", return_value=mock_credentials),
            patch(
                "cos.integrations.google.gmail.GmailClient.get_unread_emails",
                new_callable=AsyncMock,
                return_value=sample_emails,
            ),
            patch(
                "cos.integrations.google.gcal.GCalClient.get_todays_events",
                new_callable=AsyncMock,
                return_value=sample_events,
            ),
            patch(
                "cos.integrations.apple_notes.AppleNotesClient.list_notes",
                new_callable=AsyncMock,
                return_value=sample_notes,
            ),
            patch(
                "cos.agents.briefer.call_worker",
                new_callable=AsyncMock,
                return_value=sample_llm_response,
            ),
            patch("cos.cli.briefing.print_briefing") as mock_print,
        ):
            await _daily_briefing(
                context=None,
                dry_run=False,
                verbose=False,
                cost_report=True,
            )

        _, kwargs = mock_print.call_args
        assert kwargs["tokens"] == sample_llm_response.input_tokens + sample_llm_response.output_tokens
        assert kwargs["cost_usd"] > 0

    @pytest.mark.asyncio
    async def test_briefing_dry_run_does_not_call_llm(
        self,
        app_config: AppConfig,
        mock_credentials: MagicMock,
        sample_emails: list[EmailMessage],
        sample_events: list[CalendarEvent],
        sample_notes: list[Note],
    ) -> None:
        """In dry-run mode the LLM is never called."""
        from cos.cli.briefing import _daily_briefing

        with (
            patch("cos.config.settings.load_config", return_value=app_config),
            patch("cos.integrations.google.auth.get_credentials", return_value=mock_credentials),
            patch(
                "cos.integrations.google.gmail.GmailClient.get_unread_emails",
                new_callable=AsyncMock,
                return_value=sample_emails,
            ),
            patch(
                "cos.integrations.google.gcal.GCalClient.get_todays_events",
                new_callable=AsyncMock,
                return_value=sample_events,
            ),
            patch(
                "cos.integrations.apple_notes.AppleNotesClient.list_notes",
                new_callable=AsyncMock,
                return_value=sample_notes,
            ),
            patch("cos.agents.briefer.call_worker", new_callable=AsyncMock) as mock_llm,
            patch("cos.cli.formatters.console"),
        ):
            await _daily_briefing(
                context=None,
                dry_run=True,
                verbose=False,
                cost_report=False,
            )

        mock_llm.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_briefing_no_data_prints_error_not_crash(
        self,
        app_config: AppConfig,
    ) -> None:
        """When all integrations fail and no data is available, print_error is called."""
        from cos.cli.briefing import _daily_briefing

        with (
            patch("cos.config.settings.load_config", return_value=app_config),
            patch(
                "cos.integrations.google.auth.get_credentials",
                side_effect=Exception("no creds"),
            ),
            patch(
                "cos.integrations.apple_notes.AppleNotesClient.list_notes",
                new_callable=AsyncMock,
                side_effect=Exception("Notes unavailable"),
            ),
            patch("cos.cli.briefing.print_error") as mock_error,
            patch("cos.agents.briefer.call_worker", new_callable=AsyncMock) as mock_llm,
        ):
            await _daily_briefing(
                context=None,
                dry_run=False,
                verbose=False,
                cost_report=False,
            )

        mock_llm.assert_not_awaited()
        mock_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_briefing_gmail_failure_falls_back_gracefully(
        self,
        app_config: AppConfig,
        mock_credentials: MagicMock,
        sample_events: list[CalendarEvent],
        sample_notes: list[Note],
        sample_llm_response: LLMResponse,
    ) -> None:
        """Gmail failure is caught; briefing still runs with events + notes."""
        from cos.cli.briefing import _daily_briefing

        with (
            patch("cos.config.settings.load_config", return_value=app_config),
            patch("cos.integrations.google.auth.get_credentials", return_value=mock_credentials),
            patch(
                "cos.integrations.google.gmail.GmailClient.get_unread_emails",
                new_callable=AsyncMock,
                side_effect=Exception("Gmail API down"),
            ),
            patch(
                "cos.integrations.google.gcal.GCalClient.get_todays_events",
                new_callable=AsyncMock,
                return_value=sample_events,
            ),
            patch(
                "cos.integrations.apple_notes.AppleNotesClient.list_notes",
                new_callable=AsyncMock,
                return_value=sample_notes,
            ),
            patch(
                "cos.agents.briefer.call_worker",
                new_callable=AsyncMock,
                return_value=sample_llm_response,
            ) as mock_llm,
            patch("cos.cli.formatters.console"),
        ):
            await _daily_briefing(
                context=None,
                dry_run=False,
                verbose=False,
                cost_report=False,
            )

        # LLM should still be called since we have events + notes
        mock_llm.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_briefing_context_override(
        self,
        app_config: AppConfig,
        mock_credentials: MagicMock,
        sample_events: list[CalendarEvent],
        sample_notes: list[Note],
        sample_llm_response: LLMResponse,
    ) -> None:
        """Passing --context overrides the active context."""
        from cos.cli.briefing import _daily_briefing

        captured_inputs: list[AgentInput] = []

        async def _capture_run(agent_self, agent_input: AgentInput) -> AgentOutput:
            captured_inputs.append(agent_input)
            return AgentOutput(
                content=sample_llm_response.content,
                model=sample_llm_response.model,
            )

        with (
            patch("cos.config.settings.load_config", return_value=app_config),
            patch("cos.integrations.google.auth.get_credentials", return_value=mock_credentials),
            patch(
                "cos.integrations.google.gmail.GmailClient.get_unread_emails",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "cos.integrations.google.gcal.GCalClient.get_todays_events",
                new_callable=AsyncMock,
                return_value=sample_events,
            ),
            patch(
                "cos.integrations.apple_notes.AppleNotesClient.list_notes",
                new_callable=AsyncMock,
                return_value=sample_notes,
            ),
            patch("cos.agents.briefer.BriefingAgent.run", _capture_run),
            patch("cos.cli.formatters.console"),
        ):
            await _daily_briefing(
                context="advisory",
                dry_run=False,
                verbose=False,
                cost_report=False,
            )

        assert len(captured_inputs) == 1
        assert captured_inputs[0].context_name == "Startup Advisor"


# ---------------------------------------------------------------------------
# Scenario 2 – Config lifecycle
# ---------------------------------------------------------------------------


class TestConfigLifecycle:
    """Test the full configuration round-trip and context management."""

    def test_save_and_load_round_trip(self, tmp_path: Path) -> None:
        """Config survives a save-then-load round trip."""
        config = _make_app_config(tmp_path)
        config_path = tmp_path / "config.yaml"
        save_config(config, config_path)

        loaded = load_config(config_path)
        assert loaded.active_context == "day_job"
        assert "day_job" in loaded.contexts
        assert "advisory" in loaded.contexts
        assert loaded.contexts["day_job"].label == "VP Data Science"
        assert loaded.contexts["advisory"].label == "Startup Advisor"

    def test_email_accounts_round_trip(self, tmp_path: Path) -> None:
        """Email account settings survive the YAML round trip."""
        config = _make_app_config(tmp_path)
        config_path = tmp_path / "config.yaml"
        save_config(config, config_path)
        loaded = load_config(config_path)

        day_job = loaded.contexts["day_job"]
        assert len(day_job.email_accounts) == 1
        assert day_job.email_accounts[0].id == "work"
        assert day_job.email_accounts[0].address == "me@company.com"

    def test_calendar_config_round_trip(self, tmp_path: Path) -> None:
        """Calendar settings survive the YAML round trip."""
        config = _make_app_config(tmp_path)
        config_path = tmp_path / "config.yaml"
        save_config(config, config_path)
        loaded = load_config(config_path)

        day_job = loaded.contexts["day_job"]
        assert len(day_job.calendars) == 1
        assert day_job.calendars[0].calendar_id == "primary"

    def test_model_config_round_trip(self, tmp_path: Path) -> None:
        """Model settings survive the YAML round trip."""
        config = _make_app_config(tmp_path)
        config_path = tmp_path / "config.yaml"
        save_config(config, config_path)
        loaded = load_config(config_path)

        assert loaded.models.worker.model == "claude-sonnet-4-6"
        assert loaded.models.router.model == "claude-haiku-4-5"
        assert loaded.models.worker.provider == "anthropic"

    def test_sync_settings_round_trip(self, tmp_path: Path) -> None:
        """Sync / Apple Notes settings survive the YAML round trip."""
        config = _make_app_config(tmp_path)
        config_path = tmp_path / "config.yaml"
        save_config(config, config_path)
        loaded = load_config(config_path)

        assert loaded.sync.apple_notes.enabled is True
        assert loaded.sync.apple_notes.folder == "Chief of Staff"

    def test_switch_context_updates_active(self) -> None:
        """switch_context returns a new config with the new active context."""
        config = _make_app_config()
        assert config.active_context == "day_job"

        new_config = switch_context(config, "advisory")
        assert new_config.active_context == "advisory"
        assert new_config.current_context.label == "Startup Advisor"
        # Original is unchanged (immutable copy)
        assert config.active_context == "day_job"

    def test_switch_context_invalid_raises_key_error(self) -> None:
        """switch_context raises KeyError for unknown context names."""
        config = _make_app_config()
        with pytest.raises(KeyError, match="nonexistent"):
            switch_context(config, "nonexistent")

    def test_get_context_valid_name(self) -> None:
        """get_context returns the correct ContextConfig for a valid name."""
        config = _make_app_config()
        ctx = config.get_context("advisory")
        assert ctx.label == "Startup Advisor"

    def test_get_context_invalid_name_raises(self) -> None:
        """get_context raises KeyError for an unknown name."""
        config = _make_app_config()
        with pytest.raises(KeyError, match="bogus"):
            config.get_context("bogus")

    def test_get_context_defaults_to_active(self) -> None:
        """get_context() with no arg returns the active context."""
        config = _make_app_config()
        ctx = config.get_context()
        assert ctx.label == "VP Data Science"

    def test_list_contexts_includes_active_marker(self) -> None:
        """list_contexts marks the active context correctly."""
        config = _make_app_config()
        result = list_contexts(config)
        names = {name for name, _label, _active in result}
        assert "day_job" in names
        assert "advisory" in names
        active_entries = [(n, l, a) for n, l, a in result if a]
        assert len(active_entries) == 1
        assert active_entries[0][0] == "day_job"

    def test_current_context_fallback_when_active_missing(self) -> None:
        """current_context falls back to first context when active_context is unknown."""
        config = AppConfig(
            active_context="missing",
            contexts={"only": ContextConfig(label="Only Context")},
        )
        assert config.current_context.label == "Only Context"

    def test_current_context_default_when_no_contexts(self) -> None:
        """current_context returns a default ContextConfig when contexts dict is empty."""
        config = AppConfig(active_context="anything", contexts={})
        ctx = config.current_context
        assert ctx.label == "default"

    def test_load_missing_config_returns_defaults(self, tmp_path: Path) -> None:
        """load_config on a missing path returns a default AppConfig."""
        loaded = load_config(tmp_path / "does_not_exist.yaml")
        assert loaded.active_context == "default"
        assert loaded.contexts == {}


# ---------------------------------------------------------------------------
# Scenario 3 – Status health check pipeline
# ---------------------------------------------------------------------------


class TestStatusHealthCheckPipeline:
    """Test _health_check with mocked integrations registry.

    Because _health_check uses lazy imports, we patch at the source module level.
    """

    @pytest.mark.asyncio
    async def test_health_check_renders_table(self, app_config: AppConfig, tmp_path: Path) -> None:
        """_health_check calls print_health_table with rows from the registry."""
        from cos.cli.status import _health_check

        fake_results = [
            IntegrationHealth("gmail", HealthStatus.UNCONFIGURED, "Run 'cos config init'"),
            IntegrationHealth("calendar", HealthStatus.UNCONFIGURED, "Run 'cos config init'"),
            IntegrationHealth("apple_notes", HealthStatus.HEALTHY, "Account: iCloud"),
        ]

        fake_sync = {
            "path": str(tmp_path / "memory"),
            "exists": False,
            "icloud_available": False,
            "is_icloud_path": False,
            "status": "unhealthy",
        }

        with (
            patch("cos.config.settings.load_config", return_value=app_config),
            patch(
                "cos.integrations.registry.IntegrationRegistry.check_all",
                new_callable=AsyncMock,
                return_value=fake_results,
            ),
            patch("cos.memory.sync.get_sync_status", return_value=fake_sync),
            patch("cos.cli.status.print_health_table") as mock_table,
        ):
            await _health_check(verbose=False)

        mock_table.assert_called_once()
        rows = mock_table.call_args[0][0]

        # Should contain integration rows + memory_store + config
        names = {r["name"] for r in rows}
        assert "gmail" in names
        assert "calendar" in names
        assert "apple_notes" in names
        assert "memory_store" in names
        assert "config" in names

    @pytest.mark.asyncio
    async def test_health_check_icloud_row_added_when_icloud_path(
        self, app_config: AppConfig, tmp_path: Path
    ) -> None:
        """When memory path is an iCloud path, an icloud_sync row is added."""
        from cos.cli.status import _health_check

        fake_results: list[IntegrationHealth] = []
        fake_sync = {
            "path": "/Users/test/Library/Mobile Documents/com~apple~CloudDocs/cos-data",
            "exists": True,
            "icloud_available": True,
            "is_icloud_path": True,
            "status": "healthy",
        }

        with (
            patch("cos.config.settings.load_config", return_value=app_config),
            patch(
                "cos.integrations.registry.IntegrationRegistry.check_all",
                new_callable=AsyncMock,
                return_value=fake_results,
            ),
            patch("cos.memory.sync.get_sync_status", return_value=fake_sync),
            patch("cos.cli.status.print_health_table") as mock_table,
        ):
            await _health_check(verbose=False)

        rows = mock_table.call_args[0][0]
        names = {r["name"] for r in rows}
        assert "icloud_sync" in names

    @pytest.mark.asyncio
    async def test_health_check_statuses_propagated(
        self, app_config: AppConfig, tmp_path: Path
    ) -> None:
        """Status strings from the registry are passed through unchanged."""
        from cos.cli.status import _health_check

        fake_results = [
            IntegrationHealth("gmail", HealthStatus.HEALTHY, "All good"),
            IntegrationHealth("calendar", HealthStatus.DEGRADED, "Slow API"),
        ]
        fake_sync = {
            "path": str(tmp_path),
            "exists": True,
            "icloud_available": False,
            "is_icloud_path": False,
            "status": "healthy",
        }

        with (
            patch("cos.config.settings.load_config", return_value=app_config),
            patch(
                "cos.integrations.registry.IntegrationRegistry.check_all",
                new_callable=AsyncMock,
                return_value=fake_results,
            ),
            patch("cos.memory.sync.get_sync_status", return_value=fake_sync),
            patch("cos.cli.status.print_health_table") as mock_table,
        ):
            await _health_check(verbose=False)

        rows = mock_table.call_args[0][0]
        by_name = {r["name"]: r for r in rows}
        assert by_name["gmail"]["status"] == "healthy"
        assert by_name["calendar"]["status"] == "degraded"


# ---------------------------------------------------------------------------
# Scenario 4 – Notes pipeline (mock subprocess)
# ---------------------------------------------------------------------------


def _make_proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


def _make_note_applescript_output(
    note_id: str = "x-coredata://ABC/ICNote/p1",
    title: str = "Meeting Notes",
    modified: str = "Wednesday, February 18, 2026 at 09:00:00 AM",
    body: str = "<div>Project alpha progress.</div>",
) -> str:
    return f"{note_id}|||{title}|||{modified}|||{body}<<>>"


class TestNotesPipeline:
    """Test _list_notes and _search_notes with mocked subprocess.

    Because _list_notes and _search_notes use lazy imports, we patch load_config
    at the source module level.
    """

    @pytest.mark.asyncio
    async def test_list_notes_returns_parsed_notes(self, app_config: AppConfig) -> None:
        """_list_notes fetches, parses, and displays notes."""
        from cos.cli.notes import _list_notes

        raw_output = (
            _make_note_applescript_output("id1", "Meeting Notes", body="<p>Project alpha.</p>")
            + _make_note_applescript_output("id2", "Action Items", body="<p>Follow up with HR.</p>")
        )
        proc = _make_proc(stdout=raw_output)

        with (
            patch("cos.config.settings.load_config", return_value=app_config),
            patch("subprocess.run", return_value=proc),
            patch("cos.cli.notes.print_notes_list") as mock_display,
        ):
            await _list_notes(folder=None, verbose=False)

        mock_display.assert_called_once()
        notes_passed = mock_display.call_args[0][0]
        assert len(notes_passed) == 2
        titles = {n["title"] for n in notes_passed}
        assert "Meeting Notes" in titles
        assert "Action Items" in titles

    @pytest.mark.asyncio
    async def test_list_notes_html_stripped(self, app_config: AppConfig) -> None:
        """HTML tags are stripped from note body before display."""
        from cos.cli.notes import _list_notes

        raw_output = _make_note_applescript_output(
            body="<b>Bold</b> and <em>italic</em> content"
        )
        proc = _make_proc(stdout=raw_output)

        with (
            patch("cos.config.settings.load_config", return_value=app_config),
            patch("subprocess.run", return_value=proc),
            patch("cos.cli.notes.print_notes_list") as mock_display,
        ):
            await _list_notes(folder=None, verbose=False)

        notes_passed = mock_display.call_args[0][0]
        assert len(notes_passed) == 1
        body = notes_passed[0]["body"]
        assert "<b>" not in body
        assert "Bold" in body
        assert "italic" in body

    @pytest.mark.asyncio
    async def test_list_notes_empty_result(self, app_config: AppConfig) -> None:
        """An empty AppleScript output results in an empty list passed to display."""
        from cos.cli.notes import _list_notes

        proc = _make_proc(stdout="")

        with (
            patch("cos.config.settings.load_config", return_value=app_config),
            patch("subprocess.run", return_value=proc),
            patch("cos.cli.notes.print_notes_list") as mock_display,
        ):
            await _list_notes(folder=None, verbose=False)

        notes_passed = mock_display.call_args[0][0]
        assert notes_passed == []

    @pytest.mark.asyncio
    async def test_list_notes_error_calls_print_error(self, app_config: AppConfig) -> None:
        """When osascript returns an error, print_error is called, no crash."""
        from cos.cli.notes import _list_notes

        proc = _make_proc(returncode=1, stderr="Notes: permission denied")

        with (
            patch("cos.config.settings.load_config", return_value=app_config),
            patch("subprocess.run", return_value=proc),
            patch("cos.cli.notes.print_error") as mock_error,
        ):
            await _list_notes(folder=None, verbose=False)

        mock_error.assert_called_once()
        assert "Failed to read Apple Notes" in mock_error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_list_notes_folder_override(self, app_config: AppConfig) -> None:
        """An explicit folder arg overrides the config's apple_notes.folder."""
        from cos.cli.notes import _list_notes

        proc = _make_proc(stdout="")

        with (
            patch("cos.config.settings.load_config", return_value=app_config),
            patch("subprocess.run", return_value=proc) as mock_run,
        ):
            await _list_notes(folder="My Custom Folder", verbose=False)

        script_arg = mock_run.call_args[0][0][2]
        assert "My Custom Folder" in script_arg

    @pytest.mark.asyncio
    async def test_search_notes_passes_query(self, app_config: AppConfig) -> None:
        """The search query is interpolated into the AppleScript."""
        from cos.cli.notes import _search_notes

        proc = _make_proc(stdout="")

        with (
            patch("cos.config.settings.load_config", return_value=app_config),
            patch("subprocess.run", return_value=proc) as mock_run,
            patch("cos.cli.notes.print_notes_list"),
        ):
            await _search_notes(query="project alpha", folder=None, verbose=False)

        script_arg = mock_run.call_args[0][0][2]
        assert "project alpha" in script_arg

    @pytest.mark.asyncio
    async def test_search_notes_returns_matching_notes(self, app_config: AppConfig) -> None:
        """Notes matching the query are parsed and displayed."""
        from cos.cli.notes import _search_notes

        raw_output = _make_note_applescript_output(
            title="Project Alpha Notes", body="<p>Details about project alpha.</p>"
        )
        proc = _make_proc(stdout=raw_output)

        with (
            patch("cos.config.settings.load_config", return_value=app_config),
            patch("subprocess.run", return_value=proc),
            patch("cos.cli.notes.print_notes_list") as mock_display,
        ):
            await _search_notes(query="alpha", folder=None, verbose=False)

        notes = mock_display.call_args[0][0]
        assert len(notes) == 1
        assert notes[0]["title"] == "Project Alpha Notes"

    @pytest.mark.asyncio
    async def test_search_notes_timeout_calls_print_error(self, app_config: AppConfig) -> None:
        """Subprocess timeout is caught and reported via print_error."""
        from cos.cli.notes import _search_notes

        with (
            patch("cos.config.settings.load_config", return_value=app_config),
            patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="osascript", timeout=30),
            ),
            patch("cos.cli.notes.print_error") as mock_error,
        ):
            await _search_notes(query="anything", folder=None, verbose=False)

        mock_error.assert_called_once()


# ---------------------------------------------------------------------------
# Scenario 5 – Memory engine lifecycle (mock cognee)
# ---------------------------------------------------------------------------


class TestMemoryEngineLifecycle:
    """Test the full memory lifecycle: initialize -> add -> cognify -> search -> reset."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, cognee_mock, tmp_path: Path) -> None:
        """Happy path: all lifecycle methods succeed in sequence."""
        mock_cognee, _ = cognee_mock
        mock_cognee.search.return_value = [{"content": "relevant fact about project alpha"}]

        engine = MemoryEngine(data_path=tmp_path / "memory")

        # initialize
        await engine.initialize()
        assert engine._initialized is True

        # add
        await engine.add("Project Alpha: kicked off with team of 5.", dataset="briefings")
        mock_cognee.add.assert_awaited_once_with(
            "Project Alpha: kicked off with team of 5.", dataset_name="briefings"
        )

        # cognify
        await engine.cognify()
        mock_cognee.cognify.assert_awaited_once()

        # search
        results = await engine.search("project alpha")
        assert len(results) == 1
        assert "project alpha" in results[0]["content"]

        # reset
        await engine.reset()
        mock_cognee.prune.prune_data.assert_awaited_once()
        mock_cognee.prune.prune_system.assert_awaited_once_with(metadata=True)

    @pytest.mark.asyncio
    async def test_initialize_is_idempotent(self, cognee_mock, tmp_path: Path) -> None:
        """Calling initialize twice only configures cognee once."""
        mock_cognee, _ = cognee_mock
        engine = MemoryEngine(data_path=tmp_path / "memory")

        await engine.initialize()
        await engine.initialize()

        # Config should be called once per directory setting
        assert mock_cognee.config.data_root_directory.call_count == 1
        assert mock_cognee.config.system_root_directory.call_count == 1

    @pytest.mark.asyncio
    async def test_add_wraps_exception_as_memory_error(self, cognee_mock) -> None:
        """Exceptions from cognee.add are wrapped in CosMemoryError."""
        mock_cognee, _ = cognee_mock
        mock_cognee.add.side_effect = RuntimeError("disk full")

        engine = MemoryEngine()
        with pytest.raises(CosMemoryError, match="Failed to add to memory"):
            await engine.add("some content")

    @pytest.mark.asyncio
    async def test_cognify_wraps_exception(self, cognee_mock) -> None:
        """Exceptions from cognee.cognify are wrapped in CosMemoryError."""
        mock_cognee, _ = cognee_mock
        mock_cognee.cognify.side_effect = RuntimeError("graph build failed")

        engine = MemoryEngine()
        with pytest.raises(CosMemoryError, match="Failed to cognify"):
            await engine.cognify()

    @pytest.mark.asyncio
    async def test_search_returns_normalised_dicts(self, cognee_mock) -> None:
        """Search results are normalised to plain dicts."""
        mock_cognee, _ = cognee_mock
        mock_cognee.search.return_value = [
            {"insight": "team velocity is improving"},
            {"insight": "hiring pipeline needs attention"},
        ]
        engine = MemoryEngine()
        results = await engine.search("team performance")
        assert len(results) == 2
        assert all(isinstance(r, dict) for r in results)

    @pytest.mark.asyncio
    async def test_search_empty_returns_empty_list(self, cognee_mock) -> None:
        """When cognee returns nothing, search returns an empty list."""
        mock_cognee, _ = cognee_mock
        mock_cognee.search.return_value = []
        engine = MemoryEngine()
        results = await engine.search("obscure query")
        assert results == []

    @pytest.mark.asyncio
    async def test_missing_cognee_raises_memory_error(self) -> None:
        """If cognee is not installed, CosMemoryError is raised on initialize."""
        engine = MemoryEngine()
        with patch.dict(sys.modules, {"cognee": None}):
            with pytest.raises(CosMemoryError, match="cognee is not installed"):
                await engine.initialize()

    @pytest.mark.asyncio
    async def test_data_path_created_on_initialize(self, cognee_mock, tmp_path: Path) -> None:
        """MemoryEngine creates the data directory during initialization."""
        mock_cognee, _ = cognee_mock
        data_dir = tmp_path / "cos_memory" / "nested"
        engine = MemoryEngine(data_path=data_dir)
        await engine.initialize()
        assert data_dir.exists()

    @pytest.mark.asyncio
    async def test_memify_calls_cognee(self, cognee_mock) -> None:
        """memify delegates to cognee.memify."""
        mock_cognee, _ = cognee_mock
        engine = MemoryEngine()
        await engine.memify()
        mock_cognee.memify.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reset_wraps_exception(self, cognee_mock) -> None:
        """Exceptions from cognee.prune are wrapped in CosMemoryError."""
        mock_cognee, _ = cognee_mock
        mock_cognee.prune.prune_data.side_effect = RuntimeError("prune failed")
        engine = MemoryEngine()
        with pytest.raises(CosMemoryError, match="Failed to reset memory"):
            await engine.reset()


# ---------------------------------------------------------------------------
# Scenario 6 – CLI invocation tests via CliRunner
# ---------------------------------------------------------------------------


class TestCLIInvocation:
    """Smoke-test that CLI commands are registered and return help text without crashing."""

    def test_cos_help(self, runner: CliRunner) -> None:
        from cos.cli.app import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "briefing" in result.output.lower() or "AI Chief of Staff" in result.output

    def test_briefing_help(self, runner: CliRunner) -> None:
        from cos.cli.app import app

        result = runner.invoke(app, ["briefing", "--help"])
        assert result.exit_code == 0
        assert "daily" in result.output.lower() or "briefing" in result.output.lower()

    def test_briefing_daily_help(self, runner: CliRunner) -> None:
        from cos.cli.app import app

        result = runner.invoke(app, ["briefing", "daily", "--help"])
        assert result.exit_code == 0
        assert "--dry-run" in result.output or "--context" in result.output

    def test_config_help(self, runner: CliRunner) -> None:
        from cos.cli.app import app

        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0
        assert "config" in result.output.lower()

    def test_config_show_help(self, runner: CliRunner) -> None:
        from cos.cli.app import app

        result = runner.invoke(app, ["config", "show", "--help"])
        assert result.exit_code == 0

    def test_status_help(self, runner: CliRunner) -> None:
        from cos.cli.app import app

        result = runner.invoke(app, ["status", "--help"])
        assert result.exit_code == 0
        assert "health" in result.output.lower() or "status" in result.output.lower()

    def test_status_health_help(self, runner: CliRunner) -> None:
        from cos.cli.app import app

        result = runner.invoke(app, ["status", "health", "--help"])
        assert result.exit_code == 0

    def test_notes_help(self, runner: CliRunner) -> None:
        from cos.cli.app import app

        result = runner.invoke(app, ["notes", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output.lower() or "search" in result.output.lower()

    def test_notes_list_help(self, runner: CliRunner) -> None:
        from cos.cli.app import app

        result = runner.invoke(app, ["notes", "list", "--help"])
        assert result.exit_code == 0

    def test_notes_search_help(self, runner: CliRunner) -> None:
        from cos.cli.app import app

        result = runner.invoke(app, ["notes", "search", "--help"])
        assert result.exit_code == 0

    def test_briefing_daily_dry_run_no_crash(self, runner: CliRunner, tmp_path: Path) -> None:
        """briefing daily --dry-run with mocked integrations doesn't crash."""
        from cos.cli.app import app

        config = _make_app_config(tmp_path)

        proc = _make_proc(stdout="")

        with (
            patch("cos.config.settings.load_config", return_value=config),
            patch("cos.integrations.google.auth.get_credentials", side_effect=Exception("no creds")),
            patch("subprocess.run", return_value=proc),
            patch("cos.cli.formatters.console"),
        ):
            result = runner.invoke(app, ["briefing", "daily", "--dry-run"])

        # dry run should not crash (exit 0)
        assert result.exit_code == 0

    def test_config_contexts_lists_contexts(self, runner: CliRunner, tmp_path: Path) -> None:
        """config contexts lists context names."""
        from cos.cli.app import app

        config = _make_app_config(tmp_path)

        with patch("cos.config.settings.load_config", return_value=config):
            result = runner.invoke(app, ["config", "contexts"])

        assert result.exit_code == 0
        assert "day_job" in result.output or "VP Data Science" in result.output

    def test_status_memory_command(self, runner: CliRunner, tmp_path: Path) -> None:
        """status memory renders memory path info without crashing."""
        from cos.cli.app import app

        config = _make_app_config(tmp_path)
        fake_sync = {
            "path": str(tmp_path / "memory"),
            "exists": False,
            "icloud_available": False,
            "is_icloud_path": False,
            "status": "unhealthy",
        }

        with (
            patch("cos.config.settings.load_config", return_value=config),
            patch("cos.memory.sync.get_sync_status", return_value=fake_sync),
        ):
            result = runner.invoke(app, ["status", "memory"])

        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Bonus – BriefingAgent unit tests
# ---------------------------------------------------------------------------


class TestBriefingAgent:
    """Unit tests for BriefingAgent in isolation."""

    @pytest.mark.asyncio
    async def test_agent_calls_call_worker_with_system_prompt(
        self, app_config: AppConfig, sample_llm_response: LLMResponse
    ) -> None:
        """BriefingAgent.run calls call_worker with a non-empty system prompt."""
        from cos.agents.briefer import BriefingAgent

        agent = BriefingAgent(app_config)
        agent_input = AgentInput(
            context_name="VP Data Science",
            data={
                "emails": [_sample_email().model_dump()],
                "events": [_sample_event().model_dump()],
                "notes": [],
            },
        )

        with patch(
            "cos.agents.briefer.call_worker",
            new_callable=AsyncMock,
            return_value=sample_llm_response,
        ) as mock_call:
            output = await agent.run(agent_input)

        mock_call.assert_awaited_once()
        _, kwargs = mock_call.call_args
        assert len(kwargs["system"]) > 50  # Non-trivial system prompt
        assert kwargs["messages"][0]["role"] == "user"

        assert output.content == sample_llm_response.content
        assert output.input_tokens == sample_llm_response.input_tokens
        assert output.output_tokens == sample_llm_response.output_tokens
        assert output.model == sample_llm_response.model

    @pytest.mark.asyncio
    async def test_agent_cost_calculated(
        self, app_config: AppConfig, sample_llm_response: LLMResponse
    ) -> None:
        """BriefingAgent.run estimates a non-negative cost."""
        from cos.agents.briefer import BriefingAgent

        agent = BriefingAgent(app_config)
        agent_input = AgentInput(
            context_name="VP Data Science",
            data={"emails": [], "events": [_sample_event().model_dump()], "notes": []},
        )

        with patch(
            "cos.agents.briefer.call_worker",
            new_callable=AsyncMock,
            return_value=sample_llm_response,
        ):
            output = await agent.run(agent_input)

        assert output.cost_usd >= 0.0

    def test_build_user_message_contains_context_name(self, app_config: AppConfig) -> None:
        """The user message includes the context label."""
        from cos.agents.briefer import BriefingAgent

        agent = BriefingAgent(app_config)
        msg = agent._build_user_message([], [], [], "VP Data Science")
        assert "VP Data Science" in msg

    def test_build_user_message_includes_email_details(self, app_config: AppConfig) -> None:
        """Email sender and subject appear in the user message."""
        from cos.agents.briefer import BriefingAgent

        agent = BriefingAgent(app_config)
        email = _sample_email(subject="Q4 roadmap review", sender_name="Alice Chen")
        msg = agent._build_user_message([email.model_dump()], [], [], "Work")
        assert "Q4 roadmap review" in msg
        assert "Alice Chen" in msg

    def test_build_user_message_includes_event_details(self, app_config: AppConfig) -> None:
        """Event title and times appear in the user message."""
        from cos.agents.briefer import BriefingAgent

        agent = BriefingAgent(app_config)
        event = _sample_event(title="Engineering Sync", start_hour=10, end_hour=11)
        msg = agent._build_user_message([], [event.model_dump()], [], "Work")
        assert "Engineering Sync" in msg

    def test_build_user_message_no_events_says_deep_work(self, app_config: AppConfig) -> None:
        """When no events are present, the message mentions deep work."""
        from cos.agents.briefer import BriefingAgent

        agent = BriefingAgent(app_config)
        msg = agent._build_user_message([], [], [], "Work")
        assert "deep work" in msg.lower()

    def test_build_user_message_notes_section_included(self, app_config: AppConfig) -> None:
        """Notes appear in the user message when provided."""
        from cos.agents.briefer import BriefingAgent

        agent = BriefingAgent(app_config)
        note = _sample_note(title="My Important Note")
        msg = agent._build_user_message([], [], [note.model_dump()], "Work")
        assert "My Important Note" in msg
