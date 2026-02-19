"""Multi-context management utilities."""

from __future__ import annotations

from cos.config.settings import AppConfig


def list_contexts(config: AppConfig) -> list[tuple[str, str, bool]]:
    """Return list of (name, label, is_active) for all contexts."""
    return [
        (name, ctx.label, name == config.active_context) for name, ctx in config.contexts.items()
    ]


def switch_context(config: AppConfig, name: str) -> AppConfig:
    """Return a new config with a different active context."""
    if name not in config.contexts:
        raise KeyError(f"Context '{name}' not found. Available: {list(config.contexts.keys())}")
    return config.model_copy(update={"active_context": name})


def get_all_email_accounts(config: AppConfig) -> list[tuple[str, str]]:
    """Return all email accounts across all contexts as (context_name, account_id)."""
    accounts = []
    for ctx_name, ctx in config.contexts.items():
        for acct in ctx.email_accounts:
            accounts.append((ctx_name, acct.id))
    return accounts


def get_all_calendars(config: AppConfig) -> list[tuple[str, str]]:
    """Return all calendars across all contexts as (context_name, calendar_id)."""
    cals = []
    for ctx_name, ctx in config.contexts.items():
        for cal in ctx.calendars:
            cals.append((ctx_name, cal.id))
    return cals
