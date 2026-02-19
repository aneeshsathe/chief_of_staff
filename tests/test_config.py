"""Tests for configuration system."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from cos.config.settings import AppConfig, ContextConfig, EmailAccountConfig, load_config, save_config
from cos.config.contexts import list_contexts, switch_context


def test_default_config():
    config = AppConfig()
    assert config.active_context == "default"
    assert config.contexts == {}
    assert config.models.worker.model == "claude-sonnet-4-6"
    assert config.models.router.model == "claude-haiku-4-5"


def test_config_with_contexts():
    config = AppConfig(
        active_context="day_job",
        contexts={
            "day_job": ContextConfig(
                label="VP Data Science",
                email_accounts=[EmailAccountConfig(id="work", type="google", address="test@example.com")],
            ),
            "advisory": ContextConfig(label="Startup Advisor"),
        },
    )
    assert config.current_context.label == "VP Data Science"
    assert len(config.current_context.email_accounts) == 1


def test_list_contexts():
    config = AppConfig(
        active_context="day_job",
        contexts={
            "day_job": ContextConfig(label="Day Job"),
            "advisory": ContextConfig(label="Advisory"),
        },
    )
    result = list_contexts(config)
    assert len(result) == 2
    assert ("day_job", "Day Job", True) in result
    assert ("advisory", "Advisory", False) in result


def test_switch_context():
    config = AppConfig(
        active_context="day_job",
        contexts={
            "day_job": ContextConfig(label="Day Job"),
            "advisory": ContextConfig(label="Advisory"),
        },
    )
    new_config = switch_context(config, "advisory")
    assert new_config.active_context == "advisory"
    assert new_config.current_context.label == "Advisory"


def test_switch_context_invalid():
    config = AppConfig(active_context="day_job", contexts={"day_job": ContextConfig(label="Day Job")})
    with pytest.raises(KeyError, match="nonexistent"):
        switch_context(config, "nonexistent")


def test_save_and_load_config(tmp_path: Path):
    config = AppConfig(
        active_context="test",
        contexts={"test": ContextConfig(label="Test Context")},
    )
    config_path = tmp_path / "config.yaml"
    save_config(config, config_path)

    loaded = load_config(config_path)
    assert loaded.active_context == "test"
    assert loaded.contexts["test"].label == "Test Context"


def test_load_missing_config(tmp_path: Path):
    config = load_config(tmp_path / "nonexistent.yaml")
    assert config.active_context == "default"
