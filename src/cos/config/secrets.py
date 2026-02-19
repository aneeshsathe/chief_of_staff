"""Keyring-based credential management."""

from __future__ import annotations

import json

import keyring

SERVICE_NAME = "cos-chief-of-staff"


def store_credential(key: str, value: str) -> None:
    """Store a credential in the system keychain."""
    keyring.set_password(SERVICE_NAME, key, value)


def get_credential(key: str) -> str | None:
    """Retrieve a credential from the system keychain."""
    return keyring.get_password(SERVICE_NAME, key)


def delete_credential(key: str) -> None:
    """Delete a credential from the system keychain."""
    try:
        keyring.delete_password(SERVICE_NAME, key)
    except keyring.errors.PasswordDeleteError:
        pass


def store_google_token(account_id: str, token_data: dict) -> None:
    """Store Google OAuth token data for an account."""
    store_credential(f"google-token-{account_id}", json.dumps(token_data))


def get_google_token(account_id: str) -> dict | None:
    """Retrieve Google OAuth token data for an account."""
    raw = get_credential(f"google-token-{account_id}")
    if raw:
        return json.loads(raw)
    return None
