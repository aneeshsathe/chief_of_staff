"""Configuration management via Pydantic Settings + YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pydantic
import yaml
from pydantic import BaseModel, Field

from cos.core.errors import ConfigError

COS_DIR = Path.home() / ".cos"
DEFAULT_CONFIG_PATH = COS_DIR / "config.yaml"
DEFAULT_MEMORY_PATH = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/cos-data"


class EmailAccountConfig(BaseModel):
    id: str
    type: str = "google"
    address: str = ""


class CalendarConfig(BaseModel):
    id: str
    type: str = "google"
    calendar_id: str = "primary"


class GitHubConfig(BaseModel):
    org: str = ""
    repos: list[str] = Field(default_factory=list)


class SlackConfig(BaseModel):
    workspace: str = ""
    channels: list[str] = Field(default_factory=list)


class AsanaConfig(BaseModel):
    workspace_gid: str = ""
    projects: list[str] = Field(default_factory=list)


class IntegrationsConfig(BaseModel):
    github: GitHubConfig | None = None
    slack: SlackConfig | None = None
    asana: AsanaConfig | None = None


class ContextConfig(BaseModel):
    label: str
    email_accounts: list[EmailAccountConfig] = Field(default_factory=list)
    calendars: list[CalendarConfig] = Field(default_factory=list)
    integrations: IntegrationsConfig = Field(default_factory=IntegrationsConfig)
    priorities: list[str] = Field(default_factory=list)


class AppleNotesConfig(BaseModel):
    enabled: bool = True
    folder: str = "Chief of Staff"
    tag: str = "#cos"


class SyncConfig(BaseModel):
    memory_path: Path = DEFAULT_MEMORY_PATH
    apple_notes: AppleNotesConfig = Field(default_factory=AppleNotesConfig)


class ModelConfig(BaseModel):
    provider: str = "anthropic"
    model: str = ""


class ModelsConfig(BaseModel):
    router: ModelConfig = Field(default_factory=lambda: ModelConfig(model="claude-haiku-4-5"))
    worker: ModelConfig = Field(default_factory=lambda: ModelConfig(model="claude-sonnet-4-6"))
    judge: ModelConfig = Field(default_factory=lambda: ModelConfig(model="claude-sonnet-4-6"))
    judge_strategic: ModelConfig = Field(
        default_factory=lambda: ModelConfig(model="claude-opus-4-6")
    )
    summarizer: ModelConfig = Field(
        default_factory=lambda: ModelConfig(provider="google", model="gemini-2.0-flash")
    )


class AppConfig(BaseModel):
    active_context: str = "default"
    contexts: dict[str, ContextConfig] = Field(default_factory=dict)
    sync: SyncConfig = Field(default_factory=SyncConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)

    @property
    def current_context(self) -> ContextConfig:
        if self.active_context in self.contexts:
            return self.contexts[self.active_context]
        if self.contexts:
            return next(iter(self.contexts.values()))
        return ContextConfig(label="default")

    def get_context(self, name: str | None = None) -> ContextConfig:
        key = name or self.active_context
        if key in self.contexts:
            return self.contexts[key]
        raise KeyError(f"Context '{key}' not found. Available: {list(self.contexts.keys())}")


def load_config(path: Path | None = None) -> AppConfig:
    """Load config from YAML file, falling back to defaults."""
    config_path = path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return AppConfig()

    raw = yaml.safe_load(config_path.read_text()) or {}
    try:
        return AppConfig.model_validate(raw)
    except pydantic.ValidationError as e:
        raise ConfigError(
            f"Invalid configuration in {config_path}: {e}"
        ) from e


def save_config(config: AppConfig, path: Path | None = None) -> None:
    """Save config to YAML file."""
    config_path = path or DEFAULT_CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)

    data = config.model_dump(mode="json")
    # Convert Path objects to strings for YAML
    _convert_paths(data)
    config_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))


def _convert_paths(obj: Any) -> None:
    """Recursively convert Path-like values to strings for YAML serialization."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, Path):
                obj[k] = str(v)
            else:
                _convert_paths(v)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, Path):
                obj[i] = str(v)
            else:
                _convert_paths(v)
