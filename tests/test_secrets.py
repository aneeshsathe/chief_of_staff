"""Tests for keyring credential management in cos.config.secrets."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

import cos.config.secrets as secrets_module
from cos.config.secrets import (
    SERVICE_NAME,
    delete_credential,
    get_credential,
    get_google_token,
    store_credential,
    store_google_token,
)


# ---------------------------------------------------------------------------
# store_credential
# ---------------------------------------------------------------------------


class TestStoreCredential:
    def test_calls_keyring_set_password(self) -> None:
        with patch.object(secrets_module.keyring, "set_password") as mock_set:
            store_credential("my_key", "my_value")
            mock_set.assert_called_once_with(SERVICE_NAME, "my_key", "my_value")

    def test_service_name_constant(self) -> None:
        assert SERVICE_NAME == "cos-chief-of-staff"

    def test_stores_empty_string(self) -> None:
        with patch.object(secrets_module.keyring, "set_password") as mock_set:
            store_credential("k", "")
            mock_set.assert_called_once_with(SERVICE_NAME, "k", "")


# ---------------------------------------------------------------------------
# get_credential
# ---------------------------------------------------------------------------


class TestGetCredential:
    def test_returns_stored_value(self) -> None:
        with patch.object(secrets_module.keyring, "get_password", return_value="secret") as mock_get:
            result = get_credential("api_key")
            mock_get.assert_called_once_with(SERVICE_NAME, "api_key")
            assert result == "secret"

    def test_returns_none_when_not_found(self) -> None:
        with patch.object(secrets_module.keyring, "get_password", return_value=None):
            result = get_credential("missing")
            assert result is None

    def test_passes_key_correctly(self) -> None:
        with patch.object(secrets_module.keyring, "get_password", return_value="x") as mock_get:
            get_credential("some-key")
            _, args, _ = mock_get.mock_calls[0]
            assert args[1] == "some-key"


# ---------------------------------------------------------------------------
# delete_credential
# ---------------------------------------------------------------------------


class TestDeleteCredential:
    def test_calls_keyring_delete_password(self) -> None:
        with patch.object(secrets_module.keyring, "delete_password") as mock_del:
            delete_credential("old_key")
            mock_del.assert_called_once_with(SERVICE_NAME, "old_key")

    def test_swallows_password_delete_error(self) -> None:
        with patch.object(
            secrets_module.keyring,
            "delete_password",
            side_effect=secrets_module.keyring.errors.PasswordDeleteError,
        ):
            # Should not raise
            delete_credential("nonexistent")

    def test_does_not_swallow_other_errors(self) -> None:
        with patch.object(
            secrets_module.keyring,
            "delete_password",
            side_effect=RuntimeError("unexpected"),
        ):
            with pytest.raises(RuntimeError, match="unexpected"):
                delete_credential("key")


# ---------------------------------------------------------------------------
# store_google_token
# ---------------------------------------------------------------------------


class TestStoreGoogleToken:
    def test_serializes_token_as_json(self) -> None:
        token_data = {"access_token": "abc", "expires_in": 3600}
        with patch.object(secrets_module.keyring, "set_password") as mock_set:
            store_google_token("work", token_data)
            mock_set.assert_called_once()
            _, args, _ = mock_set.mock_calls[0]
            key = args[1]
            stored_value = args[2]
            assert key == "google-token-work"
            assert json.loads(stored_value) == token_data

    def test_account_id_included_in_key(self) -> None:
        with patch.object(secrets_module.keyring, "set_password") as mock_set:
            store_google_token("personal", {"token": "xyz"})
            _, args, _ = mock_set.mock_calls[0]
            assert "personal" in args[1]

    def test_empty_token_dict_stored(self) -> None:
        with patch.object(secrets_module.keyring, "set_password") as mock_set:
            store_google_token("acc", {})
            _, args, _ = mock_set.mock_calls[0]
            assert json.loads(args[2]) == {}


# ---------------------------------------------------------------------------
# get_google_token
# ---------------------------------------------------------------------------


class TestGetGoogleToken:
    def test_returns_parsed_dict(self) -> None:
        token_data = {"access_token": "tok", "token_type": "Bearer"}
        raw = json.dumps(token_data)
        with patch.object(secrets_module.keyring, "get_password", return_value=raw):
            result = get_google_token("work")
            assert result == token_data

    def test_returns_none_when_not_found(self) -> None:
        with patch.object(secrets_module.keyring, "get_password", return_value=None):
            result = get_google_token("work")
            assert result is None

    def test_uses_correct_key_format(self) -> None:
        with patch.object(secrets_module.keyring, "get_password", return_value=None) as mock_get:
            get_google_token("myaccount")
            mock_get.assert_called_once_with(SERVICE_NAME, "google-token-myaccount")

    def test_nested_token_data_preserved(self) -> None:
        token_data = {"access_token": "t", "scopes": ["email", "calendar"]}
        raw = json.dumps(token_data)
        with patch.object(secrets_module.keyring, "get_password", return_value=raw):
            result = get_google_token("acc")
            assert result["scopes"] == ["email", "calendar"]
