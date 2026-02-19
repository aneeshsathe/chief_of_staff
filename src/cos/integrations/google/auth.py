"""Google OAuth flow and credential management."""

from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from cos.config.secrets import get_google_token, store_google_token
from cos.config.settings import COS_DIR
from cos.core.errors import AuthError

# All scopes needed for cos
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]

CLIENT_SECRETS_PATH = COS_DIR / "client_secret.json"


def get_credentials(account_id: str = "default") -> Credentials:
    """Get valid Google credentials for an account, refreshing or re-authing as needed."""
    token_data = get_google_token(account_id)

    if token_data:
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        if creds.valid:
            return creds
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                _save_credentials(account_id, creds)
                return creds
            except Exception as e:
                raise AuthError(f"Failed to refresh token for {account_id}: {e}") from e

    raise AuthError(
        f"No valid credentials for account '{account_id}'. Run 'cos config init' to authenticate."
    )


def run_oauth_flow(
    account_id: str = "default", client_secrets_path: Path | None = None
) -> Credentials:
    """Run the OAuth flow interactively and store the credentials."""
    secrets_path = client_secrets_path or CLIENT_SECRETS_PATH
    if not secrets_path.exists():
        raise AuthError(
            f"Client secrets file not found at {secrets_path}. "
            "Download it from Google Cloud Console and place it there."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
    creds = flow.run_local_server(port=0)
    _save_credentials(account_id, creds)
    return creds


def _save_credentials(account_id: str, creds: Credentials) -> None:
    """Save credentials to keychain."""
    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else SCOPES,
    }
    store_google_token(account_id, token_data)


def has_credentials(account_id: str = "default") -> bool:
    """Check if we have stored credentials for an account."""
    return get_google_token(account_id) is not None
